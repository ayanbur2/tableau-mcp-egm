"""LLM-authored Tableau data-app artifacts (app.js + styles.css) — not template fill."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from langchain_openai import ChatOpenAI

from utilities.executive_data_app import resolve_theme


AUTHOR_SYSTEM = """You are a senior Tableau data-app engineer following design-data-app + build-data-app.
You invent a NEW viz-extension UI for ONE business question — never copy a fixed CRM/glass template.
Output ONLY valid JSON with keys: takeaway (string), appJs (string), stylesCss (string).
No markdown fences. No commentary outside JSON.

Design (WHAT) — bake into takeaway + UI:
- takeaway MUST be a BLUF sentence (the answer), not a topic label.
- Name an archetype in the layout: strategic (few KPIs), operational (actionable), or analytical (richer).
- Encode by judgment: position/length for precise values; line for time; sorted bars for ranking.
- Grey most marks; one accent hue for the insight. Bars from zero. No 3-D / no deceptive dual axis.
- Overview first; detail on demand. Cut panels with no "so what?".

Hard rules for appJs (HOW / sandbox):
1. Vanilla JS IIFE. Target document.getElementById('app').
2. Support TWO modes:
   - Preview: if window.__DATA_APP_PREVIEW__ is true, render from window.__PREVIEW_SAMPLE__
     (object with kpis/months/dim1/dim2 and field captions in window.__PREVIEW_PROFILE__).
   - Live: else call tableau.extensions.initializeAsync(), then resolve datasources with
     tableau.extensions.workbook.getAllDataSourcesAsync() (fallback: worksheetContent.worksheet.getDataSourcesAsync).
     NEVER use tableau.extensions.dashboardContent — this is a viz/worksheet extension; dashboardContent is undefined and throws.
     Then call ds.queryAsync(query) with the exact field captions provided. Match columns by field name, not position.
     NEVER use getSummaryDataAsync for the live data-app path.
3. Include: var BOUND_DATASOURCE_ID = '';
4. Bake field captions as a JS object literal in app.js — do not rely on window.__THEME__ (absent in Tableau).
5. No CDN, no React, no innerHTML with field values — use textContent/createElement/SVG/Canvas.
6. Paint a loading/error shell BEFORE initializeAsync; surface every error on-screen.
7. Show datasource name + an "as of" timestamp in the chrome when possible.
8. Prefer one primary view + optional KPI strip. Invent layout/typography for THIS brief + theme.

Hard rules for stylesCss:
- Self-contained CSS. Use the provided theme accent colors.
- Expressive, not generic Bootstrap. Mobile-friendly. Prefer whitespace grouping over heavy borders.
"""


def _compact_fields(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "datasourceName": profile.get("datasourceName") or profile.get("brand") or "",
        "measure": profile.get("measure"),
        "measure2": profile.get("measure2") or "",
        "dateField": profile.get("dateField") or "",
        "dimension1": profile.get("dimension1") or "",
        "dimension2": profile.get("dimension2") or "",
        "countField": profile.get("countField") or "",
        "columns": profile.get("columns") or [],
        "fieldCount": profile.get("fieldCount"),
    }


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def _validate_app_js(app_js: str) -> None:
    if not app_js or len(app_js) < 200:
        raise ValueError("Generated app.js is too short")
    required = ["BOUND_DATASOURCE_ID", "__DATA_APP_PREVIEW__", "getElementById", "queryAsync"]
    missing = [tok for tok in required if tok not in app_js]
    if missing:
        raise ValueError(f"Generated app.js missing required tokens: {', '.join(missing)}")
    if "cdn." in app_js.lower() or "unpkg.com" in app_js.lower() or "jsdelivr" in app_js.lower():
        raise ValueError("Generated app.js must not load CDN scripts")
    if "dashboardContent" in app_js:
        raise ValueError(
            "Generated app.js must not use dashboardContent — this is a viz extension; "
            "use workbook.getAllDataSourcesAsync() / worksheetContent instead"
        )
    if "getSummaryDataAsync" in app_js:
        raise ValueError(
            "Generated app.js must not use getSummaryDataAsync — use ds.queryAsync for live queries"
        )
    if "initializeAsync" not in app_js:
        raise ValueError("Generated app.js must include initializeAsync for the live path")
    if "getAllDataSourcesAsync" not in app_js and "worksheetContent" not in app_js:
        raise ValueError(
            "Generated app.js must resolve datasources via getAllDataSourcesAsync or worksheetContent"
        )


def author_data_app_files(
    *,
    profile: dict[str, Any],
    brief: str,
    theme: str = "green",
) -> dict[str, Any]:
    """
    Ask the LLM to invent app.js + styles.css for this datasource/brief.
    Returns {takeaway, appJs, stylesCss, theme, model}.
    """
    theme_key, palette = resolve_theme(theme)
    model_name = (os.environ.get("DATA_APP_AUTHOR_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-5.4-mini").strip()
    llm = ChatOpenAI(model=model_name, temperature=0.4)

    user_payload = {
        "brief": (brief or "").strip()
        or "Build the most useful single-message executive view for this datasource.",
        "theme": theme_key,
        "palette": palette,
        "fields": _compact_fields(profile),
        "previewSampleShape": {
            "kpis": {"primary": "number", "secondary": "number", "count": "number", "ratio": "number|null"},
            "months": [{"month": "YYYY-MM", "value": "number"}],
            "dim1": [{"name": "string", "value": "number"}],
            "dim2": [{"name": "string", "value": "number"}],
        },
        "constraints": [
            "Do not recreate the previous glass CRM sidebar template unless the brief asks for it.",
            "Use only the provided field captions in queryAsync.",
            "Match theme accent colors from palette.",
        ],
    }

    msg = llm.invoke(
        [
            ("system", AUTHOR_SYSTEM),
            (
                "user",
                "Create a brand-new data app artifact for this context:\n"
                + json.dumps(user_payload, ensure_ascii=False, indent=2),
            ),
        ]
    )
    content = getattr(msg, "content", None) or str(msg)
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )

    payload = _extract_json(str(content))
    app_js = str(payload.get("appJs") or "").strip()
    styles_css = str(payload.get("stylesCss") or "").strip()
    takeaway = str(payload.get("takeaway") or "").strip()
    _validate_app_js(app_js)
    if not styles_css or len(styles_css) < 40:
        raise ValueError("Generated styles.css is too short")

    # Ensure bound id stub exists for scaffold binder.
    if "var BOUND_DATASOURCE_ID" not in app_js:
        app_js = "var BOUND_DATASOURCE_ID = '';\n" + app_js

    return {
        "takeaway": takeaway,
        "appJs": app_js,
        "stylesCss": styles_css,
        "theme": theme_key,
        "model": model_name,
    }


def write_generated_preview_html(
    *,
    app_name: str,
    app_js: str,
    styles_css: str,
    profile: dict[str, Any],
    sample: dict[str, Any],
    takeaway: str = "",
    rebuild_id: str = "",
) -> str:
    """Browser preview that boots authored app.js with preview sample (no Extensions host)."""
    preview_profile = _compact_fields(profile)
    banner = (
        f"Generated artifact {rebuild_id} · {preview_profile.get('datasourceName') or app_name}"
        + (f" · {takeaway}" if takeaway else "")
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Cache-Control" content="no-store" />
  <title>{app_name} — generated preview</title>
  <style>
{styles_css}
  .gen-banner {{
    max-width: 1200px; margin: 0.6rem auto 0; padding: 0 1rem;
    font: 650 0.72rem/1.3 "DM Sans", system-ui, sans-serif;
    letter-spacing: 0.04em; text-transform: uppercase; color: #334155;
  }}
  .gen-banner span {{
    display: inline-block; padding: 0.28rem 0.6rem; border-radius: 999px;
    background: #e2e8f0; border: 1px solid #cbd5e1;
  }}
  </style>
</head>
<body>
  <div class="gen-banner"><span>{banner}</span></div>
  <div id="app"></div>
  <script>
    window.__DATA_APP_PREVIEW__ = true;
    window.__PREVIEW_PROFILE__ = {json.dumps(preview_profile, ensure_ascii=False)};
    window.__PREVIEW_SAMPLE__ = {json.dumps(sample, ensure_ascii=False)};
  </script>
  <script>
{app_js}
  </script>
</body>
</html>
"""
