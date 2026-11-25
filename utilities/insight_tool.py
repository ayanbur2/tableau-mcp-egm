"""End-user insights from live VDS aggregates — no tool JSON / scripts in the answer."""

from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import BaseModel, Field

from utilities.chart_tool import _fmt_num, _match_dim
from utilities.datasource_profile import build_live_preview_sample, profile_datasource

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)

# Tool / API tokens that must never appear in end-user answers
_BANNED_TOOL_TOKENS = (
    "get-datasource-metadata",
    "query-datasource",
    "list-datasources",
    "list-workbooks",
    "local_generate_data_app",
    "datasourceLuid",
    "datasourceluid",
    "```json",
    "tool_call",
    "tool calls",
)
# Note: do NOT ban local_query_chart / local_business_insight here — chart markdown
# followups / comments must survive polish so the UI can render ```chart blocks.


class InsightArgs(BaseModel):
    datasource_luid: str = Field(description="Active published datasource LUID (UUID)")
    question: str = Field(description="The user's business question in their language")
    datasource_name: Optional[str] = Field(default=None, description="Display name for attribution")


def _norm(text: str) -> str:
    """Normalize fancy apostrophes / spaces for matching."""
    t = text or ""
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    t = t.replace("\u00a0", " ")
    return t


def _is_turkish(text: str) -> bool:
    t = text or ""
    if re.search(r"[çğıöşüÇĞİÖŞÜ]", t):
        return True
    keys = (
        "hangi", "satış", "satis", "ayda", "yüksek", "yuksek", "toplam", "bölge",
        "bolge", "göre", "gore", "nedir", "kaç", "kac", "en yüksek", "grafik",
        "segment", "memnuniyet", "arpu",
    )
    low = t.lower()
    return any(k in low for k in keys)


def extract_luid(*texts: str) -> str:
    for text in texts:
        m = _UUID_RE.search(text or "")
        if m:
            return m.group(0)
    return ""


def looks_like_tool_theater(text: str) -> bool:
    """Detect answers that narrate fake tool calls instead of answering."""
    if not text:
        return False
    t = _norm(text).lower()
    hard = (
        "get-datasource-metadata",
        "query-datasource",
        "list-datasources",
        "```json",
        "datasourceluid",
    )
    if any(h in t for h in hard):
        return True
    soft = (
        "tool'ü",
        "tool'u",
        "toolünü",
        "toolunu",
        "tool'ünü",
        "kullanabiliriz",
        "kullanabilirsin",
        "bu tool",
        "following tool",
        "i will use the",
        "we can use the",
        "analiz edeceğim",
        "analiz edecegim",
        "metadata'sını",
        "metadatasini",
    )
    return sum(1 for m in soft if m in t) >= 2


def contains_banned_tool_tokens(text: str) -> bool:
    t = _norm(text).lower()
    return any(tok.lower() in t for tok in _BANNED_TOOL_TOKENS)


def strip_tool_theater(text: str) -> str:
    """Remove fake tool JSON / scaffolding; keep ```chart / ```followup / ```echarts."""
    if not text:
        return ""
    cleaned = _norm(text)
    # Only strip JSON / tool fences — never chart rendering blocks
    cleaned = re.sub(r"```json\s*[\s\S]*?```", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```(?:tool|tools|xml)\s*[\s\S]*?```", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\[Active Datasource:[^\]]*\]\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    keep = []
    for line in cleaned.splitlines():
        low = line.lower()
        if any(
            s in low
            for s in (
                "get-datasource-metadata",
                "query-datasource",
                "list-datasources",
                "list-workbooks",
                "tool'",
                "toolü",
                "toolu",
                "bu tool",
                "kullanabiliriz",
                "kullanabilirsin",
                "datasourceluid",
                "metadata",
                "doğruladım",
                "dogruladim",
                "aldım.",
                "aldim.",
            )
        ):
            continue
        keep.append(line)
    out = "\n".join(keep).strip()
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def _segment_breakdown(name: str, measure: str, dim_caption: str, dim_rows: list, live: bool, tr: bool) -> str:
    rows = dim_rows[:8]
    if not rows:
        return ""
    if tr:
        lines = [
            f"**{name}** — **{dim_caption}** bazında **{measure}**"
            + (" (canlı veri)" if live else "")
            + ":",
            "",
        ]
        for r in rows:
            lines.append(f"- **{r.get('name')}**: {_fmt_num(r.get('value') or 0)}")
        top = rows[0]
        lines.append("")
        lines.append(
            f"Öne çıkan: **{top.get('name')}** ({_fmt_num(top.get('value') or 0)}). "
            "Diğer metrikler (ARPU, memnuniyet) bu kaynakta ayrı alan olarak bulunursa "
            "onları da aynı kırılımda sorabilirsin."
        )
        return "\n".join(lines)
    lines = [
        f"**{name}** — **{measure}** by **{dim_caption}**"
        + (" (live)" if live else "")
        + ":",
        "",
    ]
    for r in rows:
        lines.append(f"- **{r.get('name')}**: {_fmt_num(r.get('value') or 0)}")
    top = rows[0]
    lines.append("")
    lines.append(
        f"Leader: **{top.get('name')}** ({_fmt_num(top.get('value') or 0)})."
    )
    return "\n".join(lines)


def build_business_insight(
    datasource_luid: str,
    question: str,
    datasource_name: Optional[str] = None,
) -> str:
    """
    Answer a business question with live aggregates in end-user language.
    Never mentions tools, APIs, or JSON payloads.
    """
    luid = (datasource_luid or "").strip()
    if not luid:
        raise ValueError("datasource_luid is required")

    profile = profile_datasource(luid)
    profile["previewSample"] = build_live_preview_sample(profile)
    sample = profile.get("previewSample") or {}
    live = bool(sample.get("live"))
    measure = (profile.get("measure") or "Measure").strip()
    months = list(sample.get("months") or [])
    # Prefer Segment-like dimensions when the question mentions segment
    hint = None
    q_raw = question or ""
    q = q_raw.lower()
    if "segment" in q:
        hint = "segment"
    elif any(k in q for k in ("il", "city", "şehir", "sehir")):
        hint = "city"
    elif any(k in q for k in ("bölge", "bolge", "region")):
        hint = "region"
    dim_caption, dim_rows, _ = _match_dim(profile, hint)
    name = (datasource_name or "").strip()
    if not name or name.lower() in {"selected", "selected datasource", "active"}:
        name = "Seçili veri kaynağı" if _is_turkish(q_raw) else "the selected datasource"
    tr = _is_turkish(q_raw)
    columns = [str(c) for c in (profile.get("columns") or [])]
    cols_l = " | ".join(columns).lower()

    def _has_field(*needles: str) -> bool:
        return any(n.lower() in cols_l for n in needles)

    # Asked for metrics that are not in this datasource → say so (don't dump sales-by-segment)
    missing_asks = []
    if any(k in q for k in ("arpu",)):
        if not _has_field("arpu"):
            missing_asks.append("ARPU")
    if any(k in q for k in ("memnuniyet", "satisfaction", "nps", "csat")):
        if not _has_field("satisfaction", "memnuniyet", "nps", "csat"):
            missing_asks.append("memnuniyet/satisfaction" if tr else "satisfaction")
    if any(k in q for k in ("churn", "chürn", "iptal")):
        if not _has_field("churn", "iptal"):
            missing_asks.append("churn")
    if any(k in q for k in ("indirim", "discount")):
        if not _has_field("discount", "indirim"):
            missing_asks.append("indirim/discount" if tr else "discount")

    if missing_asks and not any(
        k in q for k in ("hangi ay", "aylık", "aylik", "monthly", "toplam satış", "total sales")
    ):
        available = ", ".join(
            x for x in [measure, profile.get("measure2") or "", dim_caption, profile.get("dateField") or ""] if x
        )
        if tr:
            body = (
                f"**{name}** içinde sorduğun alan(lar) bulunamadı: **{', '.join(missing_asks)}**.\n\n"
                f"Bu kaynakta şu an kullanılabilir başlıklar: {available or 'sınırlı alan seti'}.\n"
                f"İstersen **{measure}**’i **{dim_caption}** veya aylık trend olarak gösterebilirim."
            )
        else:
            body = (
                f"**{name}** does not expose: **{', '.join(missing_asks)}**.\n\n"
                f"Available for analysis: {available or 'a limited field set'}.\n"
                f"I can show **{measure}** by **{dim_caption}** or a monthly trend instead."
            )
        return _with_followups(body, luid, measure, dim_caption, tr)

    # Peak month
    if months and any(
        k in q
        for k in (
            "hangi ay", "en yüksek ay", "en yuksek ay", "peak month", "highest month",
            "best month", "ayda en", "which month",
        )
    ):
        peak = max(months, key=lambda m: float(m.get("value") or 0))
        month = peak.get("month") or "—"
        val = _fmt_num(peak.get("value") or 0)
        if tr:
            body = (
                f"**{name}** verisine göre **{measure}** en yüksek olduğu ay "
                f"**{month}** ({val})"
                f"{' — canlı sorgu' if live else ''}."
            )
        else:
            body = (
                f"According to **{name}**, **{measure}** peaked in **{month}** "
                f"at **{val}**"
                f"{' (live query)' if live else ''}."
            )
        return _with_followups(body, luid, measure, dim_caption, tr)

    # Explicit dimension / ranking asks only
    if dim_rows and any(
        k in q
        for k in (
            "segment", "kırılım", "kirilim", "by segment", "kategori",
            "ilk ", "top ", "hangi il", "hangi bölge", "hangi bolge",
            "ranking", "sıralama", "sirala", "göre satış", "gore satis",
        )
    ) and not any(k in q for k in ("hangi ay", "ayda en")):
        body = _segment_breakdown(name, measure, dim_caption, dim_rows, live, tr)
        measure2 = (profile.get("measure2") or "").strip()
        if measure2 and sample.get("kpis", {}).get("secondary") is not None:
            sec = _fmt_num(sample["kpis"]["secondary"])
            if tr:
                body += f"\n\nİkinci ölçü (**{measure2}**) toplamı: **{sec}**."
            else:
                body += f"\n\nSecondary measure (**{measure2}**) total: **{sec}**."
        return _with_followups(body, luid, measure, dim_caption, tr)

    # Total / KPI
    kpis = sample.get("kpis") or {}
    primary = kpis.get("primary")
    if primary is not None and any(
        k in q for k in ("toplam", "total", "ne kadar", "how much", "kpi", "sum")
    ):
        if tr:
            body = f"**{name}** için **{measure}** toplamı **{_fmt_num(primary)}**."
        else:
            body = f"Total **{measure}** in **{name}** is **{_fmt_num(primary)}**."
        return _with_followups(body, luid, measure, dim_caption, tr)

    # Active datasource confirm / list-style asks
    if any(k in q for k in ("active datasource", "datasource picker", "list-datasources", "alternate")):
        if tr:
            body = (
                f"Aktif veri kaynağı: **{name}** (`{luid}`).\n"
                f"Ana ölçü: **{measure}**. Sol paneldeki picker zaten site datasource listesini yükler; "
                f"alternatif kaynak için picker’dan arayıp seçmen yeterli."
            )
        else:
            body = (
                f"Active datasource: **{name}** (`{luid}`).\n"
                f"Primary measure: **{measure}**. The left picker already lists site datasources — "
                f"search and select there for an alternate source."
            )
        return _with_followups(body, luid, measure, dim_caption, tr)

    # Default: compact snapshot — not a forced segment dump
    bits = []
    if primary is not None:
        bits.append(
            f"**{measure}**: {_fmt_num(primary)}"
            if not tr
            else f"**{measure}** toplamı: {_fmt_num(primary)}"
        )
    if months:
        peak = max(months, key=lambda m: float(m.get("value") or 0))
        if tr:
            bits.append(
                f"En yüksek ay: **{peak.get('month')}** ({_fmt_num(peak.get('value') or 0)})"
            )
        else:
            bits.append(
                f"Peak month: **{peak.get('month')}** ({_fmt_num(peak.get('value') or 0)})"
            )
    if dim_rows:
        top = dim_rows[0]
        if tr:
            bits.append(
                f"Öne çıkan {dim_caption}: **{top.get('name')}** ({_fmt_num(top.get('value') or 0)})"
            )
        else:
            bits.append(
                f"Top {dim_caption}: **{top.get('name')}** ({_fmt_num(top.get('value') or 0)})"
            )

    if tr:
        lead = f"**{name}** için kısa özet" + (" (canlı veri)" if live else "") + ":"
        body = lead + "\n- " + "\n- ".join(bits) if bits else (
            f"**{name}** için bu soruyu mevcut alanlarla net cevaplayamadım. "
            f"Aylık trend veya {dim_caption} kırılımı isteyebilirsin."
        )
    else:
        lead = f"Quick snapshot for **{name}**" + (" (live)" if live else "") + ":"
        body = lead + "\n- " + "\n- ".join(bits) if bits else (
            f"I couldn't answer that precisely from **{name}** with the available fields."
        )
    return _with_followups(body, luid, measure, dim_caption, tr)


def _with_followups(body: str, luid: str, measure: str, dim: str, tr: bool) -> str:
    if tr:
        followups = [
            {
                "label": "Aylık trend",
                "prompt": f"{measure} aylık trendini göster ve grafik çiz.",
            },
            {
                "label": f"Top {dim}",
                "prompt": f"{dim} bazında {measure} en yüksek ilk 10 hangileri?",
            },
        ]
    else:
        followups = [
            {
                "label": f"{measure} trend",
                "prompt": f"Show the monthly {measure} trend as a line chart.",
            },
            {
                "label": f"Top {dim}",
                "prompt": f"What are the top 10 {dim} by {measure}?",
            },
        ]
    return (
        body.strip()
        + "\n\n```followup\n"
        + json.dumps(followups, ensure_ascii=False)
        + "\n```\n"
    )


def polish_for_end_user(
    response_text: str,
    *,
    question: str,
    datasource_luid: str,
    datasource_name: str = "",
    force_insight: bool = False,
) -> str:
    """
    Ensure the user sees an informative answer, not tool scripts.
    Replaces tool-theater replies with a live insight when possible.
    Never destroys an existing ```chart block.
    """
    text = response_text or ""
    # Preserve charts — UI needs the fenced ECharts JSON
    if re.search(r"```chart\b", text, flags=re.IGNORECASE):
        cleaned = strip_tool_theater(text)
        # strip_tool_theater keeps chart fences; return cleaned if still has chart
        if re.search(r"```chart\b", cleaned, flags=re.IGNORECASE):
            return cleaned
        return text

    theater = looks_like_tool_theater(text) or contains_banned_tool_tokens(text)
    cleaned = strip_tool_theater(text)
    still_dirty = contains_banned_tool_tokens(cleaned)

    needs_replace = force_insight or theater or still_dirty or (
        len(cleaned) < 40 and bool(datasource_luid)
    )
    if needs_replace and datasource_luid:
        try:
            return build_business_insight(datasource_luid, question, datasource_name)
        except Exception:
            # Last resort: never return tool scripts
            if cleaned and not contains_banned_tool_tokens(cleaned):
                return cleaned
            return (
                "Bu soruyu canlı veriden yanıtlayamadım. Lütfen datasource seçiliyken tekrar deneyin."
                if _is_turkish(question)
                else "I couldn't answer from live data. Please retry with a datasource selected."
            )
    if cleaned and not contains_banned_tool_tokens(cleaned):
        return cleaned
    return text if not contains_banned_tool_tokens(text) else cleaned
