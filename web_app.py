# Web UI Libraries
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from contextlib import AsyncExitStack, asynccontextmanager
import asyncio

# MCP libraries
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LangChain Libraries
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import ToolNode, create_react_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

# Set Local MCP Logging
from utilities.logging_config import setup_logging
logger = setup_logging("web_app.log")

# Load System Prompt and Message Formatter
from utilities.prompt import AGENT_SYSTEM_PROMPT
from utilities.chat import format_agent_response
from utilities.data_app_tools import build_local_data_app_tools
from utilities.llm_profiles import build_llm_profiles, create_chat_model, public_profile
from utilities.tableau_site_profiles import (
    apply_site_profile_to_env,
    build_tableau_site_profiles,
    public_site_profile,
)

# Load Environment and set MCP Filepath
import os
import re
from dotenv import load_dotenv
from pathlib import Path
import json

load_dotenv(override=True)
mcp_location = (os.environ.get("TABLEAU_MCP_FILEPATH") or "").strip()
brand_assets_dir = Path(
    r"C:\Users\burak.ayan\.cursor\projects\c-Users-burak-ayan-Desktop-Dev-projects-tableau-mcp\assets"
)


def _tableau_mcp_server_params() -> StdioServerParameters:
    """Launch Tableau MCP per official local-service docs (npx @tableau/mcp-server)."""
    # SITE_NAME may be empty for Tableau Server Default site.
    required = ["SERVER", "PAT_NAME", "PAT_VALUE"]
    missing = [k for k in required if not (os.environ.get(k) or "").strip()]
    if missing:
        raise RuntimeError(f"Missing Tableau MCP env vars: {', '.join(missing)}")

    # Forward full env so PATH/npm work on Windows; force documented auth keys.
    child_env = {
        **os.environ,
        "TRANSPORT": os.environ.get("TRANSPORT", "stdio") or "stdio",
        "AUTH": os.environ.get("AUTH", "pat") or "pat",
        "SERVER": os.environ["SERVER"].strip(),
        "SITE_NAME": (os.environ.get("SITE_NAME") or "").strip(),
        "PAT_NAME": os.environ["PAT_NAME"].strip(),
        "PAT_VALUE": os.environ["PAT_VALUE"].strip(),
        "ENABLE_MCP_SITE_SETTINGS": os.environ.get("ENABLE_MCP_SITE_SETTINGS", "false") or "false",
        "FEATURE_GATE_PROVIDER": os.environ.get("FEATURE_GATE_PROVIDER", "") or "",
        "FEATURE_GATE_PROVIDER_CONFIG": os.environ.get("FEATURE_GATE_PROVIDER_CONFIG", "") or "",
        "TABLEAU_DATA_APP_WORKSPACE_DIR": os.environ.get("TABLEAU_DATA_APP_WORKSPACE_DIR", "") or "",
        # Full local tool surface (docs: ADMIN_TOOLS_ENABLED + empty INCLUDE/EXCLUDE)
        "ADMIN_TOOLS_ENABLED": os.environ.get("ADMIN_TOOLS_ENABLED", "true") or "true",
        "INCLUDE_TOOLS": os.environ.get("INCLUDE_TOOLS", "") or "",
        "EXCLUDE_TOOLS": os.environ.get("EXCLUDE_TOOLS", "") or "",
    }

    if mcp_location:
        return StdioServerParameters(
            command="node",
            args=[mcp_location],
            env=child_env,
        )

    # Official recommended local launch: https://tableau.github.io/tableau-mcp/docs/getting-started
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
    return StdioServerParameters(
        command=npx_cmd,
        args=["-y", "@tableau/mcp-server@latest"],
        env=child_env,
    )

# Set Langfuse Tracing (only if keys are configured and SSL_CERT_FILE is valid)
langfuse_handler = None
_langfuse_public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
if _langfuse_public_key and not _langfuse_public_key.startswith("Public key"):
    _ssl_cert_file = os.environ.get("SSL_CERT_FILE")
    if _ssl_cert_file and not os.path.exists(_ssl_cert_file):
        os.environ.pop("SSL_CERT_FILE", None)
    from langfuse.langchain import CallbackHandler
    langfuse_handler = CallbackHandler()

# Global variables for agent and session
agent = None
session_context = None
available_tools: list[dict] = []
agent_tool_node = None
agent_checkpointer = None
LLM_PROFILES = build_llm_profiles()
active_llm_profile_id = (os.environ.get("DEFAULT_LLM_PROFILE") or "openai").strip() or "openai"
TABLEAU_SITE_PROFILES = build_tableau_site_profiles()
active_tableau_site_id = (os.environ.get("DEFAULT_TABLEAU_SITE_PROFILE") or "cloud").strip() or "cloud"
_mcp_exit_stack: AsyncExitStack | None = None
_site_switch_lock = asyncio.Lock()


def _active_profile() -> dict:
    profile = LLM_PROFILES.get(active_llm_profile_id) or LLM_PROFILES.get("openai")
    if not profile:
        raise RuntimeError("No LLM profiles configured")
    return profile


def _active_site_profile() -> dict:
    profile = TABLEAU_SITE_PROFILES.get(active_tableau_site_id)
    if not profile or not profile.get("enabled"):
        profile = next(
            (p for p in TABLEAU_SITE_PROFILES.values() if p.get("enabled")),
            None,
        )
    if not profile:
        raise RuntimeError("No Tableau site profiles configured")
    return profile


def _rebuild_agent(profile_id: str) -> dict:
    """Swap the chat LLM while keeping the same MCP tool node / checkpointer."""
    global agent, active_llm_profile_id
    if agent_tool_node is None or agent_checkpointer is None:
        raise RuntimeError("Agent tools are not ready yet")
    profile = LLM_PROFILES.get(profile_id)
    if not profile:
        raise KeyError(f"Unknown LLM profile: {profile_id}")
    if not profile.get("enabled"):
        raise RuntimeError(f"LLM profile '{profile_id}' is not configured (missing key/url)")
    llm = create_chat_model(profile)
    agent = create_react_agent(
        model=llm,
        tools=agent_tool_node,
        prompt=AGENT_SYSTEM_PROMPT,
        checkpointer=agent_checkpointer,
    )
    active_llm_profile_id = profile_id
    logger.info("Active LLM profile -> %s (%s / %s)", profile_id, profile["provider"], profile["model"])
    return profile


async def _disconnect_mcp() -> None:
    global _mcp_exit_stack, agent, available_tools, agent_tool_node
    if _mcp_exit_stack is not None:
        try:
            await _mcp_exit_stack.aclose()
        except Exception as exc:
            logger.warning("MCP disconnect warning: %s", exc)
        _mcp_exit_stack = None
    agent = None
    available_tools = []
    agent_tool_node = None


async def _connect_mcp_for_site(site_id: str) -> dict:
    """Apply site profile env, open a fresh Tableau MCP stdio session, rebuild agent."""
    global agent, available_tools, agent_tool_node, agent_checkpointer
    global _mcp_exit_stack, active_tableau_site_id, TABLEAU_SITE_PROFILES

    TABLEAU_SITE_PROFILES = build_tableau_site_profiles()
    profile = TABLEAU_SITE_PROFILES.get(site_id)
    if not profile:
        raise KeyError(f"Unknown Tableau site profile: {site_id}")
    if not profile.get("enabled"):
        raise RuntimeError(f"Tableau site profile '{site_id}' is not configured")

    await _disconnect_mcp()
    apply_site_profile_to_env(profile)

    stack = AsyncExitStack()
    await stack.__aenter__()
    try:
        server_params = _tableau_mcp_server_params()
        read, write = await stack.enter_async_context(stdio_client(server_params))
        client_session = await stack.enter_async_context(ClientSession(read, write))
        await client_session.initialize()

        mcp_tools = await load_mcp_tools(client_session)
        local_data_app_tools = build_local_data_app_tools()
        all_tools = [*mcp_tools, *local_data_app_tools]
        available_tools = [
            {
                "name": getattr(t, "name", ""),
                "description": (getattr(t, "description", None) or "")[:280],
                "source": "local" if getattr(t, "name", "").startswith("local_") else "mcp",
            }
            for t in all_tools
            if getattr(t, "name", None)
        ]
        logger.info(
            "Loaded %s tools (%s mcp, %s local) for site=%s server=%s",
            len(available_tools),
            len(mcp_tools),
            len(local_data_app_tools),
            profile["id"],
            profile.get("server"),
        )

        def _tool_error_to_message(error: Exception) -> str:
            return (
                f"Tool error: {error}. "
                "Fix the arguments and retry. "
                "For query-datasource/get-datasource-metadata, datasourceLuid must be a UUID "
                "from list-datasources (or the Active Datasource in the user message). "
                "Never pass a datasource display name."
            )

        agent_tool_node = ToolNode(all_tools, handle_tool_errors=_tool_error_to_message)
        if agent_checkpointer is None:
            agent_checkpointer = InMemorySaver()

        startup_id = active_llm_profile_id
        if startup_id not in LLM_PROFILES or not LLM_PROFILES[startup_id].get("enabled"):
            startup_id = next(
                (pid for pid, p in LLM_PROFILES.items() if p.get("enabled")),
                None,
            )
        if not startup_id:
            raise RuntimeError("No enabled LLM profiles — set OPENAI_API_KEY or LLM_GATEWAY_API_KEY")
        _rebuild_agent(startup_id)
        active_tableau_site_id = profile["id"]
        _mcp_exit_stack = stack
        return profile
    except Exception:
        try:
            await stack.aclose()
        except Exception:
            pass
        raise


def _friendly_chat_error_message(error: Exception) -> str:
    """Convert low-level tool/runtime errors into user-safe chat responses."""
    error_text = str(error)
    lowered = error_text.lower()

    if "status code 429" in lowered:
        return (
            "Tableau API is rate-limiting requests right now. "
            "Please wait a few seconds and try again."
        )

    if "tool_calls that do not have a corresponding toolmessage" in lowered:
        return (
            "The agent workflow encountered an internal tool sequencing issue for this request. "
            "Please try the same question again."
        )

    return (
        "I couldn't complete that request due to a temporary processing error. "
        "Please try again."
    )

# Global async context manager for MCP connection
@asynccontextmanager
async def lifespan(app: FastAPI):
    global LLM_PROFILES, active_llm_profile_id, TABLEAU_SITE_PROFILES, active_tableau_site_id
    logger.info("Starting up application...")
    LLM_PROFILES = build_llm_profiles()
    active_llm_profile_id = (os.environ.get("DEFAULT_LLM_PROFILE") or "openai").strip() or "openai"
    TABLEAU_SITE_PROFILES = build_tableau_site_profiles()
    preferred = (os.environ.get("DEFAULT_TABLEAU_SITE_PROFILE") or "cloud").strip() or "cloud"
    if preferred not in TABLEAU_SITE_PROFILES or not TABLEAU_SITE_PROFILES[preferred].get("enabled"):
        preferred = next(
            (pid for pid, p in TABLEAU_SITE_PROFILES.items() if p.get("enabled")),
            None,
        )
    if not preferred:
        raise RuntimeError("No Tableau site profiles configured — set Cloud and/or On-prem PAT env vars")

    try:
        await _connect_mcp_for_site(preferred)
        yield
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise
    finally:
        await _disconnect_mcp()

# Create FastAPI app with lifespan
app = FastAPI(
    title="Tableau AI Chat", 
    description="Simple AI chat interface for Tableau data",
    lifespan=lifespan
)

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")
if brand_assets_dir.exists():
    app.mount("/brand-assets", StaticFiles(directory=str(brand_assets_dir)), name="brand-assets")

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    datasource_luid: str | None = None
    datasource_name: str | None = None

class ChatTraceStep(BaseModel):
    id: str = ""
    index: int = 0
    kind: str = ""
    title: str = ""
    detail: str = ""
    meta: dict = {}


class ChatResponse(BaseModel):
    response: str
    steps: list[ChatTraceStep] = []

class McpInfoResponse(BaseModel):
    server: str
    site_name: str
    llm_provider: str = ""
    llm_model: str = ""
    llm_profile_id: str = ""
    llm_profile_label: str = ""
    tableau_site_id: str = ""
    tableau_site_label: str = ""


class LlmProfileSelectRequest(BaseModel):
    profile_id: str


class TableauSiteSelectRequest(BaseModel):
    profile_id: str

def _read_mcp_info_from_project_config() -> tuple[str, str]:
    """Fallback source for MCP server/site when env vars are unavailable."""
    server = ""
    site_name = ""

    candidates = [
        Path("config.stdio.json"),
        Path("config.http.json"),
        Path("tableau-mcp-experimental/config.stdio.json"),
        Path("tableau-mcp-experimental/config.http.json"),
    ]

    for cfg_path in candidates:
        if not cfg_path.exists():
            continue
        try:
            payload = json.loads(cfg_path.read_text(encoding="utf-8"))
            mcp_servers = payload.get("mcpServers", {})
            tableau_cfg = mcp_servers.get("tableau", {})
            env_cfg = tableau_cfg.get("env", {})
            server = (env_cfg.get("SERVER") or "").strip() or server
            site_name = (env_cfg.get("SITE_NAME") or "").strip() or site_name
            if server:
                break
        except Exception:
            continue

    return server, site_name



@app.get("/")
@app.get("/v2")
@app.get("/v2/")
def home():
    """Serve Studio v2 only (classic UI is not served)."""
    return FileResponse(
        "static/v2/index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/index.html")
def legacy_index_redirect():
    """Old classic entrypoint → Studio v2."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/gateway")
@app.get("/gateway/")
def gateway_studio():
    """Bedrock profile deep-link → same Studio v2 with red theme."""
    return RedirectResponse(url="/?llm=bedrock-gateway", status_code=302)


@app.get("/mcp-info")
def mcp_info() -> McpInfoResponse:
    """Expose safe MCP connection info for UI display."""
    server = (os.environ.get("SERVER") or "").strip()
    site_name = (os.environ.get("SITE_NAME") or "").strip()
    if not server:
        config_server, config_site = _read_mcp_info_from_project_config()
        server = config_server or server
        site_name = config_site or site_name
    profile = _active_profile()
    try:
        site = _active_site_profile()
        site_pub = public_site_profile(site)
    except Exception:
        site_pub = {"id": "", "label": ""}
    return McpInfoResponse(
        server=server,
        site_name=site_name,
        llm_provider=str(profile.get("provider") or ""),
        llm_model=str(profile.get("model") or ""),
        llm_profile_id=str(profile.get("id") or ""),
        llm_profile_label=str(profile.get("label") or ""),
        tableau_site_id=str(site_pub.get("id") or ""),
        tableau_site_label=str(site_pub.get("label") or ""),
    )


@app.get("/llm-profiles")
def list_llm_profiles():
    """List named LLM profiles (no secrets)."""
    return {
        "active_profile_id": active_llm_profile_id,
        "profiles": [public_profile(p) for p in LLM_PROFILES.values()],
    }


@app.post("/llm-profiles/active")
def select_llm_profile(request: LlmProfileSelectRequest):
    """Activate a named LLM profile and rebuild the agent (MCP tools stay connected)."""
    try:
        profile = _rebuild_agent(request.profile_id.strip())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Failed to switch LLM profile: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "ok": True,
        "active_profile_id": active_llm_profile_id,
        "profile": public_profile(profile),
    }


@app.get("/tableau-sites")
def list_tableau_sites():
    """List Tableau Cloud / Server site profiles (no secrets)."""
    return {
        "active_profile_id": active_tableau_site_id,
        "profiles": [public_site_profile(p) for p in TABLEAU_SITE_PROFILES.values()],
    }


@app.post("/tableau-sites/active")
async def select_tableau_site(request: TableauSiteSelectRequest):
    """Switch active Tableau site and reconnect MCP tools to that server."""
    site_id = (request.profile_id or "").strip()
    async with _site_switch_lock:
        try:
            profile = await _connect_mcp_for_site(site_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Failed to switch Tableau site: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "ok": True,
        "active_profile_id": active_tableau_site_id,
        "profile": public_site_profile(profile),
    }


@app.get("/tools")
def list_tools():
    """Expose loaded MCP + local tools for the UI shortcut panel."""
    return {
        "count": len(available_tools),
        "tools": available_tools,
    }


@app.get("/datasources")
def list_datasources():
    """Publish site datasources for the left-rail searchable picker."""
    from utilities.list_site_datasources import list_site_datasources

    try:
        items = list_site_datasources()
    except Exception as exc:
        logger.error("list datasources failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"count": len(items), "datasources": items}


@app.get("/preview/{datapp_name}")
def preview_data_app(datapp_name: str):
    """Serve local data-app preview.html for browser review before Tableau publish."""
    from urllib.parse import unquote

    from fastapi.responses import Response

    from utilities.data_app_workspace import default_workspace_root, validate_datapp_name

    name = validate_datapp_name(unquote(datapp_name))
    path = default_workspace_root() / name / "preview.html"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No preview.html for '{name}'. Build/preview the app first.",
        )
    html = path.read_text(encoding="utf-8")
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

def _wants_chart(text: str) -> bool:
    t = (text or "").lower()
    keys = (
        "chart", "grafik", "graph", "plot", "scatter", "çiz", "ciz",
        "line chart", "bar chart", "pie", "görsel", "gorsel", "gorselleştir",
        "görselleştir", "gorsellestir", "visualization", "visualis",
        "üzerinde göster", "uzerinde goster", "görselleştirme", "gorsellestirme",
    )
    # "trend" alone is often an insight ask; require chart-ish companion words
    if any(k in t for k in keys):
        return True
    if "trend" in t and any(k in t for k in ("chart", "grafik", "çiz", "ciz", "line", "görsel", "gorsel")):
        return True
    return False


_PROJECT_ID_RE = re.compile(
    r"(?:projectId\s*[=:]\s*|Publish to\s+[^(]{1,80}\(projectId=)"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.I,
)


def _extract_project_id(text: str) -> str:
    """Return an explicit projectId from the user message, if present."""
    m = _PROJECT_ID_RE.search(text or "")
    if m:
        return m.group(1)
    # Bare UUID only when the message clearly is a publish-to-project choice
    t = (text or "").lower()
    if "project" in t or "publish to" in t:
        m2 = re.search(
            r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
            text or "",
            re.I,
        )
        if m2:
            return m2.group(1)
    return ""


def _wants_publish(text: str) -> bool:
    """True when the user is asking to publish an existing app (not build a new one)."""
    t = (text or "").lower()
    keys = (
        "publish",
        "yayınla",
        "yayinla",
        "yayın",
        "yayin",
        "publish-workbook",
        "tableauya publish",
        "tableau'ya publish",
        "tableau ya publish",
        "publish et",
        "yayinla onay",
        "yayınla onay",
        "onay veriyorum",
        "publish only",
        "publish to ",
    )
    if any(k in t for k in keys):
        # Explicit generate-then-publish phrasing should still allow generate
        if any(
            g in t
            for g in (
                "generate and publish",
                "oluştur ve yayınla",
                "olustur ve yayinla",
                "yeni app",
                "new app",
                "local_generate_data_app",
            )
        ):
            return False
        return True
    # Bare "onay" after a publish offer
    if "onay" in t and any(k in t for k in ("publish", "yayın", "yayin", "tableau")):
        return True
    # Follow-up chip / paste of projectId=... after project picker
    if _extract_project_id(text):
        return True
    return False


def _infer_chart_type(text: str) -> str:
    t = (text or "").lower()
    if "scatter" in t or "dağılım" in t or "dagilim" in t:
        return "scatter"
    if "pie" in t or "pasta" in t:
        return "pie"
    if "bar" in t or "top " in t or "ilk " in t:
        return "bar"
    if "line" in t or "trend" in t or "aylık" in t or "aylik" in t or "monthly" in t:
        return "line"
    return "auto"


@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Handle chat messages - LLM agent answers; no hardcoded Q&A short-circuit."""
    global agent

    if agent is None:
        logger.error("Agent not initialized")
        return ChatResponse(
            response="Agent is not initialized. Please restart the server and try again.",
            steps=[],
        )

    try:
        from utilities.insight_tool import (
            contains_banned_tool_tokens,
            extract_luid,
            looks_like_tool_theater,
            strip_tool_theater,
        )

        user_msg = request.message or ""
        luid = (request.datasource_luid or "").strip() or extract_luid(user_msg)
        ds_name = (request.datasource_name or "").strip()
        wants_chart = _wants_chart(user_msg)
        wants_publish = _wants_publish(user_msg)
        project_id = _extract_project_id(user_msg)
        profile_id = active_llm_profile_id

        content = user_msg
        if wants_publish:
            # Publish existing .twbx only — never regenerate. Ask for project unless chosen.
            content = (
                "[PUBLISH ONLY — HARD RULE]\n"
                "The user wants to publish an already-built data app to Tableau.\n"
                "1. Do NOT call local_generate_data_app.\n"
                "2. Do NOT call local_rebuild_data_app.\n"
                "3. Do NOT invent a new app, preview, or brief.\n"
                "4. Call local_resolve_publish_workbook"
                + (f" with datasource_luid={luid}" if luid else "")
                + " to get workbookFilePath + datappName.\n"
            )
            if project_id:
                content += (
                    f"5. The user already chose projectId={project_id}.\n"
                    "6. Immediately call publish-workbook with that workbookFilePath, "
                    f"name=datappName, projectId={project_id}, overwrite=true, "
                    "and do NOT set personalSpace.\n"
                    "7. Reply with the Tableau workbook URL (or clear error). Keep it short.\n"
                )
            else:
                content += (
                    "5. Call list-projects and list every project as **name** + `projectId`.\n"
                    "6. Ask which project to publish into. Do NOT call publish-workbook yet.\n"
                    "7. End with ```followup chips, one per project, exactly like:\n"
                    "   Publish to <ProjectName> (projectId=<uuid>)\n"
                    "8. Never assume Samples or any default project.\n"
                )
            if luid:
                content += (
                    f"[Active Datasource: {ds_name or 'selected'} | datasourceLuid={luid}]\n"
                )
            content += f"\nUser message:\n{user_msg}"
        elif luid:
            content = (
                f"[Active Datasource: {ds_name or 'selected'} | datasourceLuid={luid}]\n"
                "You are chatting with an end user. Answer THIS question specifically using tools when needed.\n"
                "Rules:\n"
                "- Ground numbers in tool results; do not invent data.\n"
                "- Never show tool names, JSON payloads, code fences for tools, or API scripts.\n"
                "- Do not reuse a generic segment/sales summary unless the question asks for it.\n"
                "- If a field is missing in metadata, say so clearly and suggest a related available field.\n"
            )
            if wants_chart:
                content += (
                    "- For chart/graph requests: call local_query_chart with this datasourceLuid "
                    "and include its ```chart block in your answer so the UI can render it.\n"
                )
            content += f"\nUser question:\n{user_msg}"

        logger.info(
            "chat via LLM profile=%s wants_chart=%s wants_publish=%s luid=%s msg=%s",
            profile_id,
            wants_chart,
            wants_publish,
            luid[:8] + "…" if luid else "",
            user_msg[:80].replace("\n", " "),
        )

        messages = [HumanMessage(content=content)]
        response_text, raw_steps = await format_agent_response(
            agent,
            messages,
            langfuse_handler,
            outbound_prompt=content,
            system_prompt=AGENT_SYSTEM_PROMPT,
            profile_id=profile_id,
        )

        # Chart insurance only: if user asked for a visual and the LLM omitted ```chart,
        # append a real chart block (do not replace the LLM prose).
        if wants_chart and luid and "```chart" not in (response_text or ""):
            try:
                from utilities.chart_tool import build_query_chart_markdown

                chart_md = build_query_chart_markdown(
                    datasource_luid=luid,
                    chart_type=_infer_chart_type(user_msg),
                    intent=user_msg[:240],
                    title=None,
                )
                # Keep LLM text if any; append chart fences from local builder
                import re as _re

                chart_only = "\n\n".join(
                    _re.findall(r"```chart\s*[\s\S]*?```", chart_md, flags=_re.I)
                    + _re.findall(r"```followup\s*[\s\S]*?```", chart_md, flags=_re.I)
                )
                if chart_only:
                    response_text = ((response_text or "").rstrip() + "\n\n" + chart_only).strip()
                else:
                    response_text = ((response_text or "").rstrip() + "\n\n" + chart_md).strip()
                raw_steps.append(
                    {
                        "id": f"step-{len(raw_steps) + 1}",
                        "index": len(raw_steps) + 1,
                        "kind": "tool_result",
                        "title": "Chart insurance · local_query_chart",
                        "detail": "LLM omitted ```chart; server appended a live chart block.",
                        "meta": {"tool": "local_query_chart", "insured": True},
                    }
                )
            except Exception as chart_exc:
                logger.warning("Chart append failed: %s", chart_exc)

        # Strip tool-theater lines only — never replace the whole answer with a template.
        if response_text and "```chart" not in response_text:
            if looks_like_tool_theater(response_text) or contains_banned_tool_tokens(response_text):
                cleaned = strip_tool_theater(response_text)
                if cleaned and len(cleaned) >= 40:
                    response_text = cleaned
                # If stripping emptied the answer, leave a short note (still not a data template)
                elif not cleaned.strip():
                    response_text = (
                        "Bu soruyu net cevaplayamadım. Lütfen soruyu biraz daha somutlaştırıp tekrar dener misin?"
                    )

        steps = [ChatTraceStep(**s) for s in (raw_steps or [])]
        return ChatResponse(response=response_text or "", steps=steps)

    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        return ChatResponse(response=_friendly_chat_error_message(e), steps=[])

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)