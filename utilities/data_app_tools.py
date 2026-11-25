"""LangChain tools that complete the local data-app author → package → publish loop."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from utilities.data_app_workspace import (
    bind_datasource_luid,
    default_workspace_root,
    list_files,
    package_twbx,
    read_file,
    scaffold_workspace,
    upsert_files,
    validate_datapp_name,
    workspace_dir,
    write_sales_by_month_app_js,
)
from utilities.data_app_author import author_data_app_files, write_generated_preview_html
from utilities.datasource_profile import (
    build_live_preview_sample,
    profile_datasource,
    slug_datapp_name,
)
from utilities.executive_data_app import (
    resolve_theme,
    write_executive_app_js,
    write_executive_styles_css,
    write_preview_file,
)
from utilities.tableau_datasource_wire import fetch_published_datasource_meta
from utilities.chart_tool import QueryChartArgs, build_query_chart_markdown
from utilities.insight_tool import InsightArgs, build_business_insight


def _root() -> Path:
    configured = (os.environ.get("TABLEAU_DATA_APP_WORKSPACE_DIR") or "").strip()
    return Path(configured) if configured else default_workspace_root()


class ScaffoldArgs(BaseModel):
    datapp_name: str = Field(description="Data app display name, e.g. 'Sales by Month'")
    datasource_luid: Optional[str] = Field(
        default=None,
        description="Published datasource LUID (UUID from list-datasources / Active Datasource)",
    )


class UpsertArgs(BaseModel):
    datapp_name: str
    files_json: str = Field(
        description=(
            "JSON object of relativePath -> file contents. "
            "Paths are relative to package content/ unless prefixed with workspace:. "
            "Example: {\"src/app.js\": \"...\"}"
        )
    )


class ReadArgs(BaseModel):
    datapp_name: str
    relative_path: str = Field(description="e.g. src/app.js or workspace:.data-app-meta.json")


class NameArgs(BaseModel):
    datapp_name: str


class BindArgs(BaseModel):
    datapp_name: str
    datasource_luid: str


class SeedSalesArgs(BaseModel):
    datapp_name: str
    datasource_luid: Optional[str] = Field(
        default=None,
        description="Published datasource LUID (UUID). Required — use the chat Active Datasource.",
    )


class RebuildArgs(BaseModel):
    datasource_luid: str = Field(description="Active published datasource LUID (UUID)")
    datapp_name: Optional[str] = Field(
        default=None,
        description="Optional display name. If omitted, derived from the datasource name.",
    )
    style: str = Field(
        default="executive",
        description="App style: 'executive' (KPI dashboard) or 'trend' (monthly line chart)",
    )
    theme: str = Field(
        default="green",
        description=(
            "Color theme for the UI. Use 'red' when the user asks for kırmızı/red/Vodafone, "
            "'blue' for mavi/blue, 'green' for default emerald."
        ),
    )


class GenerateArgs(BaseModel):
    datasource_luid: str = Field(description="Active published datasource LUID (UUID)")
    brief: str = Field(
        description=(
            "What the app should answer / look like. Include color, chart type, audience, "
            "or business question. Example: 'kırmızı Vodafone satış KPI paneli, aylık trend + bölge'."
        )
    )
    datapp_name: Optional[str] = Field(
        default=None,
        description="Optional display name. Defaults from datasource name.",
    )
    theme: str = Field(
        default="green",
        description="Theme hint: red|green|blue (also inferred from brief when possible).",
    )


class ResolvePublishArgs(BaseModel):
    datasource_luid: Optional[str] = Field(
        default=None,
        description="Optional Active Datasource LUID to prefer matching packaged apps",
    )
    datapp_name: Optional[str] = Field(
        default=None,
        description="Optional exact app/workspace name if known from the prior generate step",
    )


def build_local_data_app_tools() -> list[StructuredTool]:
    def _rebuild(
        datasource_luid: str,
        datapp_name: Optional[str] = None,
        style: str = "executive",
        theme: str = "green",
    ) -> dict:
        """Always wipe + recreate a data app for the given published datasource."""
        luid = (datasource_luid or "").strip()
        if not luid:
            raise ValueError("datasource_luid is required")

        ds_meta = fetch_published_datasource_meta(luid)
        profile = profile_datasource(luid)
        profile["brand"] = ds_meta.get("datasourceName") or "Data App"
        profile["datasourceName"] = ds_meta.get("datasourceName") or ""
        theme_key, _palette = resolve_theme(theme)
        profile["theme"] = theme_key
        rebuild_id = time.strftime("%Y%m%d-%H%M%S")
        profile["rebuildId"] = rebuild_id
        # Live aggregates for THIS datasource — never reuse Superstore sample charts.
        profile["previewSample"] = build_live_preview_sample(profile)

        style_key = (style or "executive").strip().lower()
        if style_key not in ("executive", "trend"):
            style_key = "executive"

        name = validate_datapp_name(
            datapp_name
            or slug_datapp_name(
                ds_meta.get("datasourceName") or "App",
                "Executive App" if style_key == "executive" else "Trend App",
            )
        )

        # Remove previous package so publish cannot pick a stale .twbx.
        old_twbx = _root() / f"{name}.twbx"
        if old_twbx.exists():
            try:
                old_twbx.unlink()
            except OSError:
                pass

        # scaffold_workspace always deletes an existing folder first → true from-scratch rebuild.
        meta = scaffold_workspace(
            name,
            workspace_root=_root(),
            datasource_luid=luid,
            wire_columns=profile.get("columns") or None,
        )

        if style_key == "trend":
            upsert_files(
                _root(),
                name,
                {"src/app.js": write_sales_by_month_app_js(profile)},
            )
            authored = "trend line chart rebuilt from datasource metadata"
        else:
            upsert_files(
                _root(),
                name,
                {
                    "src/app.js": write_executive_app_js(profile),
                    "src/styles.css": write_executive_styles_css(theme_key),
                },
            )
            authored = f"executive dashboard rebuilt ({theme_key} theme) from datasource metadata"

        preview = write_preview_file(workspace_dir(_root(), name), name, profile)
        packaged = package_twbx(_root(), name)
        wired = meta.get("wiredDatasource") or {}
        # Cache-bust so the browser never shows a previous rebuild.
        preview_url = f"http://localhost:8000/preview/{name}?v={rebuild_id}"
        live_preview = bool((profile.get("previewSample") or {}).get("live"))
        return {
            **meta,
            "rebuiltFromScratch": True,
            "rebuildId": rebuild_id,
            "style": style_key,
            "theme": theme_key,
            "fieldProfile": {
                "measure": profile.get("measure"),
                "measure2": profile.get("measure2"),
                "dateField": profile.get("dateField"),
                "dimension1": profile.get("dimension1"),
                "dimension2": profile.get("dimension2"),
                "countField": profile.get("countField"),
                "fieldCount": profile.get("fieldCount"),
            },
            "previewUsesLiveAggregates": live_preview,
            "authored": authored,
            "workbookFilePath": str(packaged),
            "previewHtmlPath": str(preview),
            "previewUrl": preview_url,
            "datasourceWired": bool(wired),
            "wiredDatasourceName": wired.get("wiredDatasourceName") or wired.get("datasourceName"),
            "nextStep": (
                f"Open the NEW previewUrl ({preview_url}). This rebuild ({rebuild_id}) wiped the "
                f"workspace and regenerated UI + {'live' if live_preview else 'profile'} preview "
                f"for {profile.get('datasourceName')} ({luid}). Do NOT reuse an older preview link. "
                "Do NOT publish until asked."
            ),
        }
    def scaffold(datapp_name: str, datasource_luid: Optional[str] = None) -> str:
        if not (datasource_luid or "").strip():
            raise ValueError(
                "datasource_luid is required (UUID). Use the chat Active Datasource "
                "or call list-datasources first — do not assume Superstore."
            )
        meta = scaffold_workspace(
            datapp_name,
            workspace_root=_root(),
            datasource_luid=datasource_luid.strip(),
        )
        return json.dumps(meta, indent=2)

    def upsert(datapp_name: str, files_json: str) -> str:
        files = json.loads(files_json)
        if not isinstance(files, dict):
            raise ValueError("files_json must be a JSON object")
        written = upsert_files(_root(), datapp_name, {str(k): str(v) for k, v in files.items()})
        return json.dumps({"written": written})

    def read(datapp_name: str, relative_path: str) -> str:
        return read_file(_root(), datapp_name, relative_path)

    def list_ws(datapp_name: str) -> str:
        return json.dumps(list_files(_root(), datapp_name), indent=2)

    def bind(datapp_name: str, datasource_luid: str) -> str:
        path = bind_datasource_luid(_root(), datapp_name, datasource_luid)
        return json.dumps({"updated": path, "datasourceLuid": datasource_luid})

    def package(datapp_name: str) -> str:
        path = package_twbx(_root(), datapp_name)
        return json.dumps(
            {
                "workbookFilePath": str(path),
                "publishHint": (
                    "When the user asks to publish: list-projects, ask which project to use, "
                    "THEN call publish-workbook with workbookFilePath set to this exact path, "
                    "name=<datapp_name>, the chosen projectId, "
                    "overwrite=true. Do not use personalSpace."
                ),
            }
        )

    def seed_sales(datapp_name: str, datasource_luid: Optional[str] = None) -> str:
        # Prefer LLM-authored JS artifact over fixed trend template.
        return generate_app(
            datasource_luid or "",
            brief=(
                f"Create an original monthly trend data app for '{datapp_name}'. "
                "Primary view: measure over time as a line/area chart. Invent fresh JS/CSS."
            ),
            datapp_name=datapp_name,
            theme="green",
        )

    def seed_executive(datapp_name: str, datasource_luid: Optional[str] = None) -> str:
        return generate_app(
            datasource_luid or "",
            brief=(
                f"Create an original executive performance data app for '{datapp_name}'. "
                "KPIs + one primary chart + one breakdown. Invent fresh JS/CSS — no fixed CRM template."
            ),
            datapp_name=datapp_name,
            theme="green",
        )

    def rebuild_app(
        datasource_luid: str,
        datapp_name: Optional[str] = None,
        style: str = "executive",
        theme: str = "green",
    ) -> str:
        return json.dumps(
            _rebuild(datasource_luid, datapp_name=datapp_name, style=style, theme=theme),
            indent=2,
        )

    def _infer_theme(brief: str, theme: str) -> str:
        blob = f"{brief} {theme}".lower()
        if any(tok in blob for tok in ("kirmizi", "kırmızı", "red", "vodafone", "crimson")):
            return "red"
        if any(tok in blob for tok in ("mavi", "blue", "navy")):
            return "blue"
        if (theme or "").strip():
            return theme
        return "green"

    def generate_app(
        datasource_luid: str,
        brief: str,
        datapp_name: Optional[str] = None,
        theme: str = "green",
    ) -> str:
        """LLM invents app.js/css, then scaffold+wire+package for publish."""
        luid = (datasource_luid or "").strip()
        if not luid:
            raise ValueError("datasource_luid is required")
        if not (brief or "").strip():
            raise ValueError("brief is required — describe the app to invent")

        ds_meta = fetch_published_datasource_meta(luid)
        profile = profile_datasource(luid)
        profile["brand"] = ds_meta.get("datasourceName") or "Data App"
        profile["datasourceName"] = ds_meta.get("datasourceName") or ""
        theme_key, _ = resolve_theme(_infer_theme(brief, theme))
        profile["theme"] = theme_key
        rebuild_id = time.strftime("%Y%m%d-%H%M%S")
        profile["rebuildId"] = rebuild_id
        profile["previewSample"] = build_live_preview_sample(profile)

        authored = author_data_app_files(profile=profile, brief=brief, theme=theme_key)
        name = validate_datapp_name(
            datapp_name
            or slug_datapp_name(ds_meta.get("datasourceName") or "App", "Generated App")
        )

        old_twbx = _root() / f"{name}.twbx"
        if old_twbx.exists():
            try:
                old_twbx.unlink()
            except OSError:
                pass

        meta = scaffold_workspace(
            name,
            workspace_root=_root(),
            datasource_luid=luid,
            wire_columns=profile.get("columns") or None,
        )
        upsert_files(
            _root(),
            name,
            {
                "src/app.js": authored["appJs"],
                "src/styles.css": authored["stylesCss"],
            },
        )

        ws = workspace_dir(_root(), name)
        preview_html = write_generated_preview_html(
            app_name=name,
            app_js=authored["appJs"],
            styles_css=authored["stylesCss"],
            profile=profile,
            sample=profile.get("previewSample") or {},
            takeaway=authored.get("takeaway") or "",
            rebuild_id=rebuild_id,
        )
        preview_path = ws / "preview.html"
        preview_path.write_text(preview_html, encoding="utf-8")

        meta_path = ws / ".data-app-meta.json"
        try:
            meta_obj = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        except Exception:
            meta_obj = {}
        meta_obj.update(
            {
                "authoredMode": "llm-generated",
                "rebuildId": rebuild_id,
                "theme": theme_key,
                "brief": brief,
                "takeaway": authored.get("takeaway") or "",
                "authorModel": authored.get("model"),
            }
        )
        meta_path.write_text(json.dumps(meta_obj, indent=2), encoding="utf-8")

        packaged = package_twbx(_root(), name)
        preview_url = f"http://localhost:8000/preview/{name}?v={rebuild_id}"
        wired = meta.get("wiredDatasource") or {}
        return json.dumps(
            {
                **meta,
                "authoredMode": "llm-generated",
                "rebuiltFromScratch": True,
                "rebuildId": rebuild_id,
                "theme": theme_key,
                "brief": brief,
                "takeaway": authored.get("takeaway") or "",
                "authorModel": authored.get("model"),
                "fieldProfile": {
                    "measure": profile.get("measure"),
                    "measure2": profile.get("measure2"),
                    "dateField": profile.get("dateField"),
                    "dimension1": profile.get("dimension1"),
                    "dimension2": profile.get("dimension2"),
                    "countField": profile.get("countField"),
                    "fieldCount": profile.get("fieldCount"),
                },
                "previewUsesLiveAggregates": bool((profile.get("previewSample") or {}).get("live")),
                "workbookFilePath": str(packaged),
                "previewHtmlPath": str(preview_path.resolve()),
                "previewUrl": preview_url,
                "datasourceWired": bool(wired),
                "wiredDatasourceName": wired.get("wiredDatasourceName") or wired.get("datasourceName"),
                "nextStep": (
                    f"Open NEW generated previewUrl ({preview_url}). This is an LLM-authored "
                    f"app.js artifact for {profile.get('datasourceName')} — not a fixed template. "
                    "Do NOT publish yet. When the user later says publish/yayınla/onay: call "
                    "local_resolve_publish_workbook, list-projects, ask which project, "
                    "THEN publish-workbook — do NOT generate again."
                ),
            },
            indent=2,
        )

    def preview_app(datapp_name: str) -> str:
        """Re-generate or re-template based on workspace authoredMode."""
        name = validate_datapp_name(datapp_name)
        ws = workspace_dir(_root(), name)
        if not ws.exists():
            raise FileNotFoundError(
                f"Workspace not found: {ws}. Call local_generate_data_app instead."
            )
        meta_path = ws / ".data-app-meta.json"
        luid = ""
        authored_mode = ""
        brief = ""
        theme = "green"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                luid = str(meta.get("datasourceLuid") or "").strip()
                authored_mode = str(meta.get("authoredMode") or "")
                brief = str(meta.get("brief") or "")
                theme = str(meta.get("theme") or "green")
            except Exception:
                luid = ""
        if not luid:
            raise ValueError(
                "No datasourceLuid on this workspace. Call local_generate_data_app with the "
                "Active Datasource LUID."
            )
        if authored_mode == "llm-generated":
            return generate_app(
                luid,
                brief or "Refresh the previously generated data app with a new original design.",
                datapp_name=name,
                theme=theme,
            )
        return json.dumps(_rebuild(luid, datapp_name=name, style="executive", theme=theme), indent=2)

    def resolve_publish_workbook(
        datasource_luid: Optional[str] = None,
        datapp_name: Optional[str] = None,
    ) -> str:
        """
        Find an already-packaged .twbx for publish-workbook.
        Prefer exact datapp_name, else newest workspace matching datasource LUID, else newest .twbx.
        """
        root = _root()
        root.mkdir(parents=True, exist_ok=True)
        luid = (datasource_luid or "").strip()
        wanted = (datapp_name or "").strip()

        def _meta_for(ws: Path) -> dict:
            meta_path = ws / ".data-app-meta.json"
            if not meta_path.exists():
                return {}
            try:
                payload = json.loads(meta_path.read_text(encoding="utf-8"))
                return payload if isinstance(payload, dict) else {}
            except Exception:
                return {}

        def _packaged_path(name: str) -> Path | None:
            twbx = root / f"{name}.twbx"
            return twbx if twbx.exists() else None

        # 1) Exact name
        if wanted:
            name = validate_datapp_name(wanted)
            path = _packaged_path(name)
            if path is None:
                # Package existing workspace if present
                ws = workspace_dir(root, name)
                if ws.exists():
                    path = Path(package_twbx(root, name))
            if path and path.exists():
                return json.dumps(
                    {
                        "workbookFilePath": str(path.resolve()),
                        "datappName": name,
                        "matchedBy": "datapp_name",
                        "publishHint": (
                            "Do NOT publish yet unless the user already chose a projectId. "
                            "Call list-projects, ask which project to use, then publish-workbook "
                            f"with this workbookFilePath, name='{name}', the chosen projectId, "
                            "overwrite=true, no personalSpace. Do NOT generate a new app."
                        ),
                    },
                    indent=2,
                )

        # 2) Newest workspace matching datasource LUID that has/can package a twbx
        candidates: list[tuple[float, str, Path, dict]] = []
        for ws in root.iterdir():
            if not ws.is_dir() or ws.name.startswith("."):
                continue
            try:
                name = validate_datapp_name(ws.name)
            except Exception:
                continue
            meta = _meta_for(ws)
            meta_luid = str(meta.get("datasourceLuid") or "").strip()
            if luid and (not meta_luid or meta_luid.lower() != luid.lower()):
                continue
            path = _packaged_path(name)
            if path is None:
                continue
            mtime = path.stat().st_mtime
            candidates.append((mtime, name, path, meta))

        if not candidates and luid:
            # Package newest matching workspace without twbx yet
            unpackaged: list[tuple[float, str]] = []
            for ws in root.iterdir():
                if not ws.is_dir() or ws.name.startswith("."):
                    continue
                try:
                    name = validate_datapp_name(ws.name)
                except Exception:
                    continue
                meta = _meta_for(ws)
                meta_luid = str(meta.get("datasourceLuid") or "").strip()
                if meta_luid.lower() != luid.lower():
                    continue
                unpackaged.append((ws.stat().st_mtime, name))
            if unpackaged:
                unpackaged.sort(reverse=True)
                name = unpackaged[0][1]
                path = Path(package_twbx(root, name))
                return json.dumps(
                    {
                        "workbookFilePath": str(path.resolve()),
                        "datappName": name,
                        "matchedBy": "datasource_luid_packaged_now",
                        "publishHint": (
                            "Do NOT publish yet unless the user already chose a projectId. "
                            "Call list-projects, ask which project to use, then publish-workbook "
                            f"with this workbookFilePath, name='{name}', the chosen projectId, "
                            "overwrite=true, no personalSpace. Do NOT generate a new app."
                        ),
                    },
                    indent=2,
                )

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            _mtime, name, path, meta = candidates[0]
            return json.dumps(
                {
                    "workbookFilePath": str(path.resolve()),
                    "datappName": name,
                    "datasourceLuid": meta.get("datasourceLuid") or luid or "",
                    "matchedBy": "datasource_luid_latest" if luid else "latest_twbx",
                    "publishHint": (
                        "Do NOT publish yet unless the user already chose a projectId. "
                        "Call list-projects, ask which project to use, then publish-workbook "
                        f"with this workbookFilePath, name='{name}', the chosen projectId, "
                        "overwrite=true, no personalSpace. Do NOT generate a new app."
                    ),
                },
                indent=2,
            )

        # 3) Absolute fallback: newest twbx in workspace root
        twbxs = sorted(root.glob("*.twbx"), key=lambda p: p.stat().st_mtime, reverse=True)
        if twbxs:
            path = twbxs[0]
            name = path.stem
            return json.dumps(
                {
                    "workbookFilePath": str(path.resolve()),
                    "datappName": name,
                    "matchedBy": "newest_twbx_fallback",
                    "publishHint": (
                        "Do NOT publish yet unless the user already chose a projectId. "
                        "Call list-projects, ask which project to use, then publish-workbook "
                        f"with this workbookFilePath, name='{name}', the chosen projectId, "
                        "overwrite=true, no personalSpace. Do NOT generate a new app."
                    ),
                },
                indent=2,
            )

        raise FileNotFoundError(
            "No packaged data app (.twbx) found under data_apps. "
            "Generate/preview an app first, then publish."
        )

    def query_chart(
        datasource_luid: str,
        chart_type: str = "auto",
        intent: str = "",
        dimension_hint: Optional[str] = None,
        measure_hint: Optional[str] = None,
        title: Optional[str] = None,
        top_n: int = 10,
    ) -> str:
        """Build a Studio ```chart block from live VDS aggregates."""
        return build_query_chart_markdown(
            datasource_luid=datasource_luid,
            chart_type=chart_type,
            intent=intent,
            dimension_hint=dimension_hint,
            measure_hint=measure_hint,
            title=title,
            top_n=top_n,
        )

    def business_insight(
        datasource_luid: str,
        question: str,
        datasource_name: Optional[str] = None,
    ) -> str:
        """End-user prose answer from live aggregates (no tool scripts)."""
        return build_business_insight(datasource_luid, question, datasource_name)

    return [
        StructuredTool.from_function(
            name="local_business_insight",
            description=(
                "PREFERRED for factual business questions (highest month, totals, top regions). "
                "Returns a short end-user answer from live datasource data. "
                "Paste the tool output as the final answer. Never invent numbers. "
                "Never show tool names, JSON, or API scripts to the user."
            ),
            func=business_insight,
            args_schema=InsightArgs,
        ),
        StructuredTool.from_function(
            name="local_query_chart",
            description=(
                "REQUIRED for any chart/graph/plot/scatter/trend visualization in chat. "
                "Queries the Active Datasource (VDS) and returns markdown that ALREADY contains a "
                "```chart ECharts JSON block the Studio UI can render. "
                "Pass datasource_luid (UUID), chart_type=auto|line|bar|pie|scatter, and intent. "
                "Copy the tool's ```chart (and ```followup) blocks into your final answer VERBATIM. "
                "Do not say you cannot draw charts — call this tool instead of inventing numbers."
            ),
            func=query_chart,
            args_schema=QueryChartArgs,
        ),
        StructuredTool.from_function(
            name="local_scaffold_data_app",
            description=(
                "Create a local Tableau data-app workspace from the official template "
                "(workbook + viz extension package). Use before authoring files."
            ),
            func=scaffold,
            args_schema=ScaffoldArgs,
        ),
        StructuredTool.from_function(
            name="local_upsert_data_app_files",
            description=(
                "Create/replace files in a scaffolded data-app workspace "
                "(e.g. src/app.js, src/styles.css)."
            ),
            func=upsert,
            args_schema=UpsertArgs,
        ),
        StructuredTool.from_function(
            name="local_read_data_app_file",
            description="Read a file from a local data-app workspace.",
            func=read,
            args_schema=ReadArgs,
        ),
        StructuredTool.from_function(
            name="local_list_data_app_files",
            description="List files in a local data-app workspace.",
            func=list_ws,
            args_schema=NameArgs,
        ),
        StructuredTool.from_function(
            name="local_bind_data_app_datasource",
            description="Set BOUND_DATASOURCE_ID in src/app.js to a published datasource LUID.",
            func=bind,
            args_schema=BindArgs,
        ),
        StructuredTool.from_function(
            name="local_package_data_app",
            description="Package the workspace into a .twbx and return workbookFilePath for publish-workbook.",
            func=package,
            args_schema=NameArgs,
        ),
        StructuredTool.from_function(
            name="local_seed_sales_by_month_data_app",
            description=(
                "Rebuild a monthly trend data app FROM SCRATCH for the given datasource_luid "
                "(reads VDS metadata, rewires sqlproxy, regenerates app.js + preview). "
                "Always pass the chat Active Datasource LUID. Return previewUrl; do not publish yet."
            ),
            func=seed_sales,
            args_schema=SeedSalesArgs,
        ),
        StructuredTool.from_function(
            name="local_seed_executive_data_app",
            description=(
                "Rebuild an executive KPI data app FROM SCRATCH for the given datasource_luid "
                "(reads VDS metadata, picks measure/date/dimensions, rewires sqlproxy, regenerates UI). "
                "Always pass the chat Active Datasource LUID. Return previewUrl; do not publish yet."
            ),
            func=seed_executive,
            args_schema=SeedSalesArgs,
        ),
        StructuredTool.from_function(
            name="local_resolve_publish_workbook",
            description=(
                "REQUIRED before publish when the user says publish/yayınla/onay. "
                "Finds the already-packaged .twbx (by datapp_name or latest matching datasource_luid). "
                "Returns workbookFilePath for publish-workbook. "
                "Do NOT call local_generate_data_app on a publish request."
            ),
            func=resolve_publish_workbook,
            args_schema=ResolvePublishArgs,
        ),
        StructuredTool.from_function(
            name="local_generate_data_app",
            description=(
                "PREFERRED for NEW data apps (design-data-app + build-data-app). "
                "Pass a design-informed English brief (BLUF takeaway, role, encodings, colors). "
                "Tool invents NEW app.js + styles.css, scaffolds, wires the published datasource into the .twb, "
                "writes browser previewUrl, packages .twbx. Return NEW previewUrl (?v=). Do NOT publish yet. "
                "Never use when the user only asked to publish an existing app. "
                "Prefer this over bare scaffold-data-app / local_scaffold_data_app / local_rebuild_data_app."
            ),
            func=generate_app,
            args_schema=GenerateArgs,
        ),
        StructuredTool.from_function(
            name="local_rebuild_data_app",
            description=(
                "Fallback TEMPLATE rebuild only (fixed executive/trend skins). Prefer "
                "local_generate_data_app for original UIs. style='executive'|'trend', "
                "theme='red'|'green'|'blue'. Always wipes workspace."
            ),
            func=rebuild_app,
            args_schema=RebuildArgs,
        ),
        StructuredTool.from_function(
            name="local_preview_data_app",
            description=(
                "Re-runs generation/rebuild for an existing workspace (does not reopen a stale "
                "preview). Prefer local_generate_data_app for new asks."
            ),
            func=preview_app,
            args_schema=NameArgs,
        ),
    ]
