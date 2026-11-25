"""Server-side chart builder: VDS query → ECharts ```chart block for Studio UI."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from utilities.datasource_profile import (
    build_live_preview_sample,
    profile_datasource,
)


class QueryChartArgs(BaseModel):
    datasource_luid: str = Field(description="Active published datasource LUID (UUID)")
    chart_type: str = Field(
        default="auto",
        description="auto|line|bar|pie|scatter — pick for the user question",
    )
    intent: str = Field(
        default="",
        description="Short user ask, e.g. monthly sales trend, top cities by net sales",
    )
    dimension_hint: Optional[str] = Field(
        default=None,
        description="Preferred dimension caption if known (Region, City, Segment…)",
    )
    measure_hint: Optional[str] = Field(
        default=None,
        description="Preferred measure caption if known (Sales, Net Sales…)",
    )
    title: Optional[str] = Field(default=None, description="Optional chart title")
    top_n: int = Field(default=10, description="Max categories for bar/pie (3–15)")


def _fmt_num(n: float) -> str:
    try:
        v = float(n)
    except (TypeError, ValueError):
        return str(n)
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}K"
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.2f}"


def _pick_chart_type(requested: str, intent: str, has_months: bool, cat_count: int) -> str:
    req = (requested or "auto").strip().lower()
    if req in {"line", "bar", "pie", "scatter"}:
        return req
    text = f"{intent} {requested}".lower()
    if any(w in text for w in ("scatter", "dağılım", "correlation", "ilişki")):
        return "scatter"
    if any(w in text for w in ("pie", "share", "oran", "pasta", "breakdown %")):
        return "pie"
    if any(w in text for w in ("trend", "monthly", "aylık", "over time", "zaman", "line")):
        return "line" if has_months else "bar"
    if any(w in text for w in ("top", "rank", "bar", "il", "city", "region", "segment", "karşılaştır")):
        return "bar"
    if has_months:
        return "line"
    if 0 < cat_count <= 5:
        return "pie"
    return "bar"


def _match_dim(profile: dict[str, Any], hint: Optional[str]) -> tuple[str, list[dict[str, Any]], str]:
    """Return (caption, rows, sample_key) for the best dimension series."""
    sample = profile.get("previewSample") or {}
    dim1 = profile.get("dimension1") or ""
    dim2 = profile.get("dimension2") or ""
    rows1 = list(sample.get("dim1") or [])
    rows2 = list(sample.get("dim2") or [])
    hint_l = (hint or "").lower().strip()

    if hint_l:
        if dim1 and hint_l in dim1.lower():
            return dim1, rows1, "dim1"
        if dim2 and hint_l in dim2.lower():
            return dim2, rows2, "dim2"
        # Prefer dim with more rows if hint doesn't match captions
    if rows1 and (not rows2 or len(rows1) >= len(rows2)):
        return dim1 or "Category", rows1, "dim1"
    if rows2:
        return dim2 or "Category", rows2, "dim2"
    return dim1 or dim2 or "Category", rows1 or rows2, "dim1"


def _echarts_line(title: str, months: list[dict[str, Any]], measure: str) -> dict[str, Any]:
    cats = [m.get("month") or m.get("name") or "" for m in months]
    vals = [float(m.get("value") or 0) for m in months]
    return {
        "title": {"text": title},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": cats},
        "yAxis": {"type": "value", "name": measure},
        "series": [{"type": "line", "name": measure, "smooth": True, "data": vals}],
    }


def _echarts_bar(title: str, rows: list[dict[str, Any]], measure: str) -> dict[str, Any]:
    cats = [str(r.get("name") or "") for r in rows]
    vals = [float(r.get("value") or 0) for r in rows]
    return {
        "title": {"text": title},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": cats, "axisLabel": {"rotate": 30}},
        "yAxis": {"type": "value", "name": measure},
        "series": [{"type": "bar", "name": measure, "data": vals}],
    }


def _echarts_pie(title: str, rows: list[dict[str, Any]], measure: str) -> dict[str, Any]:
    data = [{"name": str(r.get("name") or ""), "value": float(r.get("value") or 0)} for r in rows]
    return {
        "title": {"text": title},
        "tooltip": {"trigger": "item"},
        "series": [{"type": "pie", "radius": "65%", "name": measure, "data": data}],
    }


def _echarts_scatter(title: str, rows: list[dict[str, Any]], x_name: str, y_name: str) -> dict[str, Any]:
    # rows as {name, x, y}
    data = [[float(r.get("x") or 0), float(r.get("y") or 0)] for r in rows]
    return {
        "title": {"text": title},
        "tooltip": {"trigger": "item"},
        "xAxis": {"type": "value", "name": x_name},
        "yAxis": {"type": "value", "name": y_name},
        "series": [{"type": "scatter", "symbolSize": 12, "data": data}],
    }


def build_query_chart_markdown(
    datasource_luid: str,
    chart_type: str = "auto",
    intent: str = "",
    dimension_hint: Optional[str] = None,
    measure_hint: Optional[str] = None,
    title: Optional[str] = None,
    top_n: int = 10,
) -> str:
    """
    Query the datasource and return Studio-ready markdown including a ```chart block.
    Weak LLMs should paste this tool output into the user-facing reply (verbatim chart block).
    """
    luid = (datasource_luid or "").strip()
    if not luid:
        raise ValueError("datasource_luid is required")

    n = max(3, min(int(top_n or 10), 15))
    profile = profile_datasource(luid)
    # Prefer live aggregates; fall back inside builder
    profile["previewSample"] = build_live_preview_sample(profile)
    sample = profile.get("previewSample") or {}
    live = bool(sample.get("live"))
    measure = (measure_hint or profile.get("measure") or "Measure").strip()
    months = list(sample.get("months") or [])
    dim_caption, dim_rows, _key = _match_dim(profile, dimension_hint)
    dim_rows = dim_rows[:n]

    kind = _pick_chart_type(chart_type, intent, has_months=bool(months), cat_count=len(dim_rows))
    chart_title = (title or "").strip()
    option: dict[str, Any]
    lead: str
    bullets: list[str]

    if kind == "line" and not months:
        kind = "bar"
    if kind == "scatter" and not dim_rows:
        kind = "bar"

    if kind == "line":
        chart_title = chart_title or f"{measure} by month"
        option = _echarts_line(chart_title, months, measure)
        lead = (
            f"Live monthly trend for **{measure}** "
            f"({len(months)} points{', live query' if live else ', provisional'})."
        )
        bullets = [
            f"- First: `{months[0].get('month')}` → {_fmt_num(months[0].get('value') or 0)}",
            f"- Last: `{months[-1].get('month')}` → {_fmt_num(months[-1].get('value') or 0)}",
        ]
        peak = max(months, key=lambda m: float(m.get("value") or 0))
        bullets.append(f"- Peak: `{peak.get('month')}` → {_fmt_num(peak.get('value') or 0)}")
    elif kind == "pie":
        chart_title = chart_title or f"{measure} by {dim_caption}"
        rows = dim_rows[: min(5, n)]
        option = _echarts_pie(chart_title, rows, measure)
        total = sum(float(r.get("value") or 0) for r in rows) or 1.0
        lead = f"**{measure}** share by **{dim_caption}** (top {len(rows)})."
        bullets = [
            f"- {r.get('name')}: {_fmt_num(r.get('value') or 0)} "
            f"({100 * float(r.get('value') or 0) / total:.1f}%)"
            for r in rows[:5]
        ]
    elif kind == "scatter":
        scatter_rows = [
            {"name": r.get("name"), "x": i + 1, "y": float(r.get("value") or 0)}
            for i, r in enumerate(dim_rows)
        ]
        chart_title = chart_title or f"{measure} scatter by {dim_caption}"
        option = _echarts_scatter(chart_title, scatter_rows, dim_caption, measure)
        lead = f"Scatter of **{measure}** across **{dim_caption}** members."
        bullets = [f"- Points: {len(scatter_rows)} · measure `{measure}`"]
    else:
        kind = "bar"
        chart_title = chart_title or f"Top {len(dim_rows)} {dim_caption} by {measure}"
        option = _echarts_bar(chart_title, dim_rows, measure)
        lead = (
            f"**{measure}** by **{dim_caption}** "
            f"(top {len(dim_rows)}{', live query' if live else ''})."
        )
        bullets = [
            f"- {r.get('name')}: {_fmt_num(r.get('value') or 0)}" for r in dim_rows[:5]
        ]

    followups = [
        {
            "label": f"{measure} trend",
            "prompt": f"{measure} aylık trendini göster ve grafik çiz.",
        },
        {
            "label": f"Top {dim_caption}",
            "prompt": f"{dim_caption} bazında {measure} en yüksek ilk 10 hangileri? Grafik çiz.",
        },
    ]

    chart_json = json.dumps(option, ensure_ascii=False)
    body = (
        f"{lead}\n\n"
        + "\n".join(bullets)
        + "\n\n"
        + f"```chart\n{chart_json}\n```\n\n"
        + "```followup\n"
        + json.dumps(followups, ensure_ascii=False)
        + "\n```\n"
    )
    return body


def extract_chart_blocks(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(r"```chart\s*([\s\S]*?)```", text, flags=re.IGNORECASE)


def ensure_chart_from_tool_messages(final_text: str, messages: list[Any]) -> str:
    """
    If the model omitted ```chart but local_query_chart returned one, append it.
    """
    text = final_text or ""
    if extract_chart_blocks(text):
        return text

    tool_blobs: list[str] = []
    for msg in messages or []:
        name = getattr(msg, "name", None) or ""
        content = getattr(msg, "content", None)
        if name != "local_query_chart":
            continue
        if isinstance(content, list):
            # LC sometimes uses content blocks
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("text"):
                    parts.append(str(block["text"]))
                else:
                    parts.append(str(block))
            content = "\n".join(parts)
        if isinstance(content, str) and "```chart" in content:
            tool_blobs.append(content)

    if not tool_blobs:
        return text

    blob = tool_blobs[-1]
    # Prefer appending just chart + followup fences if model already wrote prose
    chart_bits = re.findall(r"```chart\s*[\s\S]*?```", blob, flags=re.IGNORECASE)
    follow_bits = re.findall(r"```followup\s*[\s\S]*?```", blob, flags=re.IGNORECASE)
    extra = "\n\n".join(chart_bits + follow_bits).strip()
    if not extra:
        extra = blob.strip()
    if not text.strip():
        return blob.strip()
    return text.rstrip() + "\n\n" + extra + "\n"
