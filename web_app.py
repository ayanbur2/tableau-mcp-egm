# Web UI Libraries
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

# MCP libraries
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LangChain Libraries
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

# Set Local MCP Logging
from utilities.logging_config import setup_logging
logger = setup_logging("web_app.log")

# Load System Prompt and Message Formatter
from utilities.prompt import AGENT_SYSTEM_PROMPT
from utilities.chat import format_agent_response

# Load Environment and set MCP Filepath
import os
from dotenv import load_dotenv
from pathlib import Path
import json

load_dotenv()
mcp_location = os.environ['TABLEAU_MCP_FILEPATH']
brand_assets_dir = Path(
    r"C:\Users\burak.ayan\.cursor\projects\c-Users-burak-ayan-Desktop-Dev-projects-tableau-mcp\assets"
)

# Set Langfuse Tracing
from langfuse.langchain import CallbackHandler
langfuse_handler = CallbackHandler()

# Global variables for agent and session
agent = None
session_context = None


def _friendly_chat_error_message(error: Exception) -> str:
    """Convert low-level tool/runtime errors into user-safe chat responses."""
    error_text = str(error)
    lowered = error_text.lower()

    if "status code 429" in lowered:
        return (
            "Tableau API is rate-limiting requests right now. "
            "Please wait a few seconds and try again."
        )

    if "input validation error" in lowered or "unrecognized_keys" in lowered:
        return (
            "I hit a tool validation issue while building the query. "
            "Please rephrase your question (for example, specify fields and time range clearly) and try again."
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
    global agent
    logger.info("Starting up application...")
    
    try:
        # Setup MCP connection
        # Forward os.environ so the Node tableau-mcp child sees SERVER, SITE_NAME,
        # PAT_NAME, PAT_VALUE, etc. The default StdioServerParameters env only
        # inherits a Windows safe-list (PATH, APPDATA, ...).
        server_params = StdioServerParameters(
            command="node",
            args=[mcp_location],
            env={**os.environ},
        )

        # Use proper async context management
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as client_session:
                # Initialize the connection
                await client_session.initialize()

                # Get tools, filter tools using the .env config
                mcp_tools = await load_mcp_tools(client_session)

                # Set AI Model
                llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0)

                # Create the agent
                checkpointer = InMemorySaver()
                agent = create_react_agent(model=llm, tools=mcp_tools, prompt=AGENT_SYSTEM_PROMPT, checkpointer=checkpointer)
                
                yield
        
    # Error Handling
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

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

class ChatResponse(BaseModel):
    response: str

class McpInfoResponse(BaseModel):
    server: str
    site_name: str

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
def home():
    """Serve the main HTML page"""
    return FileResponse('static/index.html')

@app.get("/index.html")
def static_index():
    return FileResponse('static/index.html')

@app.get("/mcp-info")
def mcp_info() -> McpInfoResponse:
    """Expose safe MCP connection info for UI display."""
    server = (os.environ.get("SERVER") or "").strip()
    site_name = (os.environ.get("SITE_NAME") or "").strip()
    if not server:
        config_server, config_site = _read_mcp_info_from_project_config()
        server = config_server or server
        site_name = config_site or site_name
    return McpInfoResponse(server=server, site_name=site_name)

@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Handle chat messages - this is where the AI magic happens"""
    global agent
    
    if agent is None:
        logger.error("Agent not initialized")
        return ChatResponse(response="Agent is not initialized. Please restart the server and try again.")
    
    try:      
        # Create proper message format for LangGraph
        messages = [HumanMessage(content=request.message)]

        # Get response from agent
        response_text = await format_agent_response(agent, messages, langfuse_handler)
        
        return ChatResponse(response=response_text)
        
    # Error Handling
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        return ChatResponse(response=_friendly_chat_error_message(e))

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)