"""Executive data-app UI (live Extensions) + browser preview — glass CRM skin."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


THEME_PALETTES: dict[str, dict[str, str]] = {
    "green": {
        "ink": "#0c1f1a",
        "muted": "#5b6f68",
        "bg": "#e8f0ec",
        "sidebar": "#14352c",
        "sidebar2": "#0f2922",
        "accent": "#22c55e",
        "accentDeep": "#16a34a",
        "accentSoft": "rgba(34, 197, 94, 0.14)",
        "accentLight": "#4ade80",
        "accentRgb": "34, 197, 94",
        "glow": "rgba(34, 197, 94, 0.35)",
        "bgGlow1": "#c8e6d8",
        "bgGlow2": "#d7e5f0",
        "barTrack": "#e7efea",
        "ctaText": "#052e1a",
        "border": "rgba(15, 41, 34, 0.08)",
        "shadow": "rgba(15, 41, 34, 0.10)",
    },
    "red": {
        "ink": "#1f0a0d",
        "muted": "#7a5560",
        "bg": "#f7eef1",
        "sidebar": "#4c0b14",
        "sidebar2": "#2a060c",
        "accent": "#e11d48",
        "accentDeep": "#be123c",
        "accentSoft": "rgba(225, 29, 72, 0.14)",
        "accentLight": "#fb7185",
        "accentRgb": "225, 29, 72",
        "glow": "rgba(225, 29, 72, 0.38)",
        "bgGlow1": "#f0c4cd",
        "bgGlow2": "#e7d5e0",
        "barTrack": "#f3e4e8",
        "ctaText": "#4c0510",
        "border": "rgba(76, 11, 20, 0.10)",
        "shadow": "rgba(76, 11, 20, 0.12)",
    },
    "blue": {
        "ink": "#0b1220",
        "muted": "#5b6b86",
        "bg": "#eef3f9",
        "sidebar": "#102a56",
        "sidebar2": "#0b1c3a",
        "accent": "#2563eb",
        "accentDeep": "#1d4ed8",
        "accentSoft": "rgba(37, 99, 235, 0.14)",
        "accentLight": "#60a5fa",
        "accentRgb": "37, 99, 235",
        "glow": "rgba(37, 99, 235, 0.35)",
        "bgGlow1": "#c7d7f5",
        "bgGlow2": "#d7e5f0",
        "barTrack": "#e4ebf5",
        "ctaText": "#0b1c3a",
        "border": "rgba(16, 42, 86, 0.10)",
        "shadow": "rgba(16, 42, 86, 0.12)",
    },
}


def resolve_theme(theme: str | None) -> tuple[str, dict[str, str]]:
    key = (theme or "green").strip().lower()
    aliases = {
        "kirmizi": "red",
        "kırmızı": "red",
        "crimson": "red",
        "vodafone": "red",
        "emerald": "green",
        "default": "green",
        "mavi": "blue",
    }
    key = aliases.get(key, key)
    if key not in THEME_PALETTES:
        key = "green"
    return key, THEME_PALETTES[key]


PREVIEW_SAMPLE: dict[str, Any] = {
    "kpis": {"primary": 2297200.86, "secondary": 286397.02, "count": 5009, "ratio": 0.1247},
    "months": [
        {"month": "2023-01", "value": 185042},
        {"month": "2023-02", "value": 156311},
        {"month": "2023-03", "value": 201884},
        {"month": "2023-04", "value": 178420},
        {"month": "2023-05", "value": 214903},
        {"month": "2023-06", "value": 192774},
        {"month": "2023-07", "value": 208661},
        {"month": "2023-08", "value": 225118},
        {"month": "2023-09", "value": 261440},
        {"month": "2023-10", "value": 239805},
        {"month": "2023-11", "value": 318902},
        {"month": "2023-12", "value": 301940},
    ],
    "dim1": [
        {"name": "West", "value": 725458},
        {"name": "East", "value": 678781},
        {"name": "Central", "value": 501240},
        {"name": "South", "value": 391722},
    ],
    "dim2": [
        {"name": "Technology", "value": 836154},
        {"name": "Furniture", "value": 741999},
        {"name": "Office Supplies", "value": 719048},
    ],
}


def write_executive_styles_css(theme: str | None = None) -> str:
    theme_key, p = resolve_theme(theme)
    return f"""@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

:root {{
  --theme: {theme_key};
  --ink: {p['ink']};
  --muted: {p['muted']};
  --panel: rgba(255, 255, 255, 0.78);
  --panel-solid: #ffffff;
  --bg: {p['bg']};
  --sidebar: {p['sidebar']};
  --sidebar-2: {p['sidebar2']};
  --accent: {p['accent']};
  --accent-deep: {p['accentDeep']};
  --accent-soft: {p['accentSoft']};
  --accent-light: {p['accentLight']};
  --glass: rgba(255, 255, 255, 0.55);
  --border: {p['border']};
  --shadow: 0 18px 40px {p['shadow']};
  --radius: 18px;
  --radius-sm: 14px;
  --cta-text: {p['ctaText']};
  --bar-track: {p['barTrack']};
}}

* {{ box-sizing: border-box; }}
html, body {{ height: 100%; }}
body {{
  margin: 0;
  font-family: "DM Sans", "Segoe UI", system-ui, sans-serif;
  color: var(--ink);
  background:
    radial-gradient(900px 520px at 12% -10%, {p['bgGlow1']} 0%, transparent 55%),
    radial-gradient(720px 480px at 100% 0%, {p['bgGlow2']} 0%, transparent 50%),
    linear-gradient(160deg, {p['bg']} 0%, #eef3f0 45%, #e7edf2 100%);
}}

#app {{ min-height: 100%; }}

.shell {{
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  min-height: 100vh;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0.85rem;
  gap: 0.85rem;
}}

.sidebar {{
  background: linear-gradient(180deg, var(--sidebar) 0%, var(--sidebar-2) 100%);
  border-radius: 22px;
  padding: 1rem 0.7rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.55rem;
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
}}
.sidebar::before {{
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(120px 80px at 50% 0%, {p['glow']}, transparent 70%),
    linear-gradient(180deg, rgba(255,255,255,0.08), transparent 40%);
  pointer-events: none;
}}
.side-logo {{
  width: 42px; height: 42px; border-radius: 14px;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.18);
  display: grid; place-items: center;
  color: #fff; font-weight: 700; font-size: 0.85rem;
  margin-bottom: 0.55rem;
  backdrop-filter: blur(10px);
  z-index: 1;
}}
.nav-btn {{
  width: 44px; height: 44px; border-radius: 14px;
  display: grid; place-items: center;
  color: rgba(255,255,255,0.55);
  background: transparent;
  border: 0;
  cursor: default;
  z-index: 1;
  transition: background 160ms ease, color 160ms ease, transform 160ms ease;
}}
.nav-btn.active {{
  background: var(--accent);
  color: var(--cta-text);
  box-shadow: 0 8px 18px {p['glow']};
}}
.nav-btn svg {{ width: 20px; height: 20px; }}
.nav-spacer {{ flex: 1; }}

.main {{
  background: var(--panel);
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  border: 1px solid rgba(255,255,255,0.55);
  border-radius: 24px;
  box-shadow: var(--shadow);
  padding: 1.15rem 1.25rem 1.35rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  animation: rise 420ms ease both;
}}

@keyframes rise {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to {{ opacity: 1; transform: none; }}
}}
@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to {{ opacity: 1; transform: none; }}
}}

.topbar {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}}
.greeting .eyebrow {{
  font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--accent-deep); font-weight: 650; margin-bottom: 0.25rem;
}}
.greeting h1 {{
  margin: 0; font-size: 1.7rem; font-weight: 700; letter-spacing: -0.03em; line-height: 1.15;
}}
.greeting .takeaway {{
  margin: 0.4rem 0 0; color: var(--muted); font-size: 0.95rem; max-width: 36rem; line-height: 1.45;
}}
.top-actions {{
  display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap; justify-content: flex-end;
}}
.search-pill, .chip, .cta {{
  height: 40px; border-radius: 999px; border: 1px solid var(--border);
  background: rgba(255,255,255,0.72); display: inline-flex; align-items: center;
  padding: 0 0.95rem; color: var(--muted); font-size: 0.85rem;
}}
.search-pill {{ min-width: 180px; gap: 0.45rem; }}
.cta {{
  background: linear-gradient(135deg, var(--accent), var(--accent-deep));
  color: var(--cta-text); font-weight: 650; border: 0;
  box-shadow: 0 10px 20px {p['glow']};
}}

.kpis {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
}}
.kpi {{
  background: var(--panel-solid);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.95rem 1rem 0.7rem;
  box-shadow: 0 10px 24px {p['shadow']};
  position: relative;
  overflow: hidden;
  animation: fadeUp 480ms ease both;
}}
.kpi:nth-child(2) {{ animation-delay: 40ms; }}
.kpi:nth-child(3) {{ animation-delay: 80ms; }}
.kpi:nth-child(4) {{ animation-delay: 120ms; }}
.kpi .label {{
  font-size: 0.78rem; color: var(--muted); font-weight: 500; margin-bottom: 0.35rem;
}}
.kpi .value {{
  font-size: 1.55rem; font-weight: 700; letter-spacing: -0.03em; margin-bottom: 0.15rem;
}}
.kpi .delta {{
  display: inline-flex; align-items: center; gap: 0.25rem;
  font-size: 0.75rem; font-weight: 650; color: var(--accent-deep);
  background: var(--accent-soft); padding: 0.15rem 0.45rem; border-radius: 999px;
}}
.kpi .delta.down {{ color: #b45309; background: rgba(180, 83, 9, 0.12); }}
.kpi .spark {{ position: absolute; right: 0.55rem; bottom: 0.35rem; opacity: 0.9; }}

.layout {{
  display: grid;
  grid-template-columns: 1.55fr 0.9fr;
  gap: 0.85rem;
  align-items: stretch;
}}
.panel {{
  background: var(--panel-solid);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.05rem 0.85rem;
  box-shadow: 0 10px 24px {p['shadow']};
  animation: fadeUp 520ms ease both;
}}
.panel h2 {{
  margin: 0 0 0.75rem; font-size: 0.98rem; font-weight: 650; letter-spacing: -0.01em;
}}
.stack {{ display: grid; gap: 0.85rem; }}
.gauge-wrap {{
  display: grid; place-items: center; padding: 0.35rem 0 0.2rem;
}}
.gauge-label {{
  text-align: center; margin-top: -0.35rem;
}}
.gauge-label .big {{
  font-size: 1.8rem; font-weight: 700; letter-spacing: -0.03em;
}}
.gauge-label .sub {{ color: var(--muted); font-size: 0.8rem; margin-top: 0.15rem; }}

.bar-row {{
  display: grid; grid-template-columns: 6.5rem 1fr 4.2rem;
  gap: 0.55rem; align-items: center; margin-bottom: 0.55rem; font-size: 0.82rem;
}}
.bar-track {{
  height: 10px; background: var(--bar-track); border-radius: 999px; overflow: hidden;
}}
.bar-fill {{
  height: 100%; width: 0;
  background: linear-gradient(90deg, var(--accent), var(--accent-light));
  border-radius: 999px;
  transition: width 700ms cubic-bezier(.2,.7,.2,1);
}}
.bar-fill.alt {{ background: linear-gradient(90deg, var(--accent-deep), var(--accent)); }}
.bar-val {{ text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }}
.note {{ margin: 0.45rem 0 0; color: var(--muted); font-size: 0.78rem; }}
.error {{ color: #b00020; padding: 2rem 1rem; }}
.loading {{
  color: var(--muted); padding: 3rem 1rem; text-align: center;
  animation: fadeUp 360ms ease both;
}}

@media (max-width: 980px) {{
  .shell {{ grid-template-columns: 1fr; padding: 0.6rem; }}
  .sidebar {{ flex-direction: row; justify-content: flex-start; padding: 0.65rem 0.75rem; }}
  .nav-spacer {{ display: none; }}
  .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .layout {{ grid-template-columns: 1fr; }}
  .topbar {{ flex-direction: column; }}
}}
@media (max-width: 560px) {{
  .kpis {{ grid-template-columns: 1fr; }}
  .search-pill {{ display: none; }}
}}
"""


def write_executive_app_js(profile: dict | None = None) -> str:
    profile = profile or {}
    theme_key, palette = resolve_theme(profile.get("theme"))
    plan = {
        "brand": profile.get("brand") or profile.get("datasourceName") or "Executive",
        "measure": profile.get("measure") or "Sales",
        "measure2": profile.get("measure2") or "",
        "dateField": profile.get("dateField") or "",
        "dimension1": profile.get("dimension1") or "",
        "dimension2": profile.get("dimension2") or "",
        "countField": profile.get("countField") or "",
        "theme": theme_key,
        "accent": palette["accent"],
        "accentDeep": palette["accentDeep"],
        "accentLight": palette["accentLight"],
    }
    template = r"""(function () {
  'use strict';

  var PLAN = __PLAN__;
  var root = document.getElementById('app');
  var BOUND_DATASOURCE_ID = '';

  function extractData(result) {
    return result && Array.isArray(result.data) ? result.data : [];
  }

  function getDataSources() {
    var wb = tableau.extensions.workbook;
    if (wb && typeof wb.getAllDataSourcesAsync === 'function') {
      return wb.getAllDataSourcesAsync();
    }
    var wc = tableau.extensions.worksheetContent;
    if (wc && wc.worksheet && typeof wc.worksheet.getDataSourcesAsync === 'function') {
      return wc.worksheet.getDataSourcesAsync();
    }
    return Promise.resolve([]);
  }

  function findDataSource(list) {
    if (!BOUND_DATASOURCE_ID) return (list && list.length) ? list[0] : null;
    var found = null;
    (list || []).forEach(function (ds) {
      if (ds && ds.id === BOUND_DATASOURCE_ID) found = ds;
    });
    if (!found) throw new Error('Bound datasource is not available on this workbook.');
    return found;
  }

  function money(n) {
    var abs = Math.abs(n);
    if (abs >= 1e6) return (n < 0 ? '-' : '') + '$' + (abs / 1e6).toFixed(2) + 'M';
    if (abs >= 1e3) return (n < 0 ? '-' : '') + '$' + (abs / 1e3).toFixed(0) + 'K';
    return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  function pct(n) { return (n * 100).toFixed(1) + '%'; }

  function fieldValue(row, re, fallbackIndex) {
    var keys = Object.keys(row || {});
    var hit = keys.find(function (k) { return re.test(k); });
    if (hit) return row[hit];
    return keys[fallbackIndex] != null ? row[keys[fallbackIndex]] : null;
  }

  function monthKey(value) {
    if (value == null) return '';
    var d = new Date(value);
    if (!isNaN(d.getTime())) {
      var m = String(d.getUTCMonth() + 1).padStart(2, '0');
      return d.getUTCFullYear() + '-' + m;
    }
    return String(value);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function svgIcon(pathD) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.8');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', pathD);
    svg.appendChild(p);
    return svg;
  }

  function greeting() {
    var h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 18) return 'Good afternoon';
    return 'Good evening';
  }

  function sparkline(values, width, height) {
    width = width || 88; height = height || 28;
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'spark');
    svg.setAttribute('width', String(width));
    svg.setAttribute('height', String(height));
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    if (!values || values.length < 2) return svg;
    var min = Math.min.apply(null, values);
    var max = Math.max.apply(null, values);
    var span = Math.max(max - min, 1);
    var coords = values.map(function (v, i) {
      var x = (i * (width - 2)) / Math.max(values.length - 1, 1) + 1;
      var y = height - 2 - ((v - min) / span) * (height - 4);
      return { x: x, y: y };
    });
    var d = smoothPath(coords);
    var line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    line.setAttribute('d', d);
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', PLAN.accent || '#22c55e');
    line.setAttribute('stroke-width', '2');
    svg.appendChild(line);
    return svg;
  }

  function smoothPath(coords) {
    if (!coords.length) return '';
    if (coords.length === 1) return 'M' + coords[0].x + ' ' + coords[0].y;
    var d = 'M' + coords[0].x + ' ' + coords[0].y;
    for (var i = 0; i < coords.length - 1; i++) {
      var p0 = coords[i === 0 ? i : i - 1];
      var p1 = coords[i];
      var p2 = coords[i + 1];
      var p3 = coords[i + 2] || p2;
      var cp1x = p1.x + (p2.x - p0.x) / 6;
      var cp1y = p1.y + (p2.y - p0.y) / 6;
      var cp2x = p2.x - (p3.x - p1.x) / 6;
      var cp2y = p2.y - (p3.y - p1.y) / 6;
      d += ' C' + cp1x + ' ' + cp1y + ',' + cp2x + ' ' + cp2y + ',' + p2.x + ' ' + p2.y;
    }
    return d;
  }

  function renderBars(container, rows, alt) {
    var max = Math.max.apply(null, rows.map(function (r) { return r.value; }).concat([1]));
    rows.slice(0, 6).forEach(function (r) {
      var row = el('div', 'bar-row');
      row.appendChild(el('div', null, r.name));
      var track = el('div', 'bar-track');
      var fill = el('div', 'bar-fill' + (alt ? ' alt' : ''));
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(el('div', 'bar-val', money(r.value)));
      container.appendChild(row);
      requestAnimationFrame(function () {
        fill.style.width = Math.max(2, (r.value / max) * 100) + '%';
      });
    });
  }

  function renderTrend(container, points) {
    var width = 640, height = 250, padL = 18, padR = 12, padT = 16, padB = 28;
    var maxY = Math.max.apply(null, points.map(function (p) { return p.y; }).concat([1]));
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', String(height));
    var defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    var grad = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
    grad.setAttribute('id', 'areaFill');
    grad.setAttribute('x1', '0'); grad.setAttribute('y1', '0');
    grad.setAttribute('x2', '0'); grad.setAttribute('y2', '1');
    var accent = PLAN.accent || '#22c55e';
    var accentDeep = PLAN.accentDeep || '#16a34a';
    var s1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
    s1.setAttribute('offset', '0%'); s1.setAttribute('stop-color', accent); s1.setAttribute('stop-opacity', '0.35');
    var s2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
    s2.setAttribute('offset', '100%'); s2.setAttribute('stop-color', accent); s2.setAttribute('stop-opacity', '0.02');
    grad.appendChild(s1); grad.appendChild(s2); defs.appendChild(grad); svg.appendChild(defs);

    var coords = points.map(function (p, i) {
      var x = padL + (i * (width - padL - padR)) / Math.max(points.length - 1, 1);
      var y = height - padB - (p.y / maxY) * (height - padT - padB);
      return { x: x, y: y, label: p.x };
    });
    if (!coords.length) return;
    var lineD = smoothPath(coords);
    var areaD = lineD + ' L' + coords[coords.length - 1].x + ' ' + (height - padB) +
      ' L' + coords[0].x + ' ' + (height - padB) + ' Z';
    var fill = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    fill.setAttribute('d', areaD);
    fill.setAttribute('fill', 'url(#areaFill)');
    svg.appendChild(fill);
    var line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    line.setAttribute('d', lineD);
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', accentDeep);
    line.setAttribute('stroke-width', '2.8');
    line.setAttribute('stroke-linecap', 'round');
    svg.appendChild(line);
    var last = coords[coords.length - 1];
    var dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', String(last.x));
    dot.setAttribute('cy', String(last.y));
    dot.setAttribute('r', '4.5');
    dot.setAttribute('fill', accentDeep);
    svg.appendChild(dot);
    container.appendChild(svg);
  }

  function renderGauge(container, ratio) {
    var pctVal = Math.max(0, Math.min(1, ratio == null ? 0 : ratio));
    var size = 210, stroke = 16;
    var r = (size / 2) - stroke;
    var c = 2 * Math.PI * r;
    var arc = c * 0.75;
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', String(size));
    svg.setAttribute('height', String(size * 0.72));
    svg.setAttribute('viewBox', '0 0 ' + size + ' ' + (size * 0.72));
    var g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('transform', 'translate(' + (size / 2) + ' ' + (size / 2) + ') rotate(135)');
    function ring(offset, color, width) {
      var circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', '0'); circle.setAttribute('cy', '0'); circle.setAttribute('r', String(r));
      circle.setAttribute('fill', 'none');
      circle.setAttribute('stroke', color);
      circle.setAttribute('stroke-width', String(width || stroke));
      circle.setAttribute('stroke-linecap', 'round');
      circle.setAttribute('stroke-dasharray', arc + ' ' + c);
      circle.setAttribute('stroke-dashoffset', String(offset));
      return circle;
    }
    g.appendChild(ring(0, '#e7efea', stroke));
    g.appendChild(ring(arc * (1 - pctVal), PLAN.accent || '#22c55e', stroke));
    svg.appendChild(g);
    var wrap = el('div', 'gauge-wrap');
    wrap.appendChild(svg);
    var label = el('div', 'gauge-label');
    label.appendChild(el('div', 'big', pct(pctVal)));
    label.appendChild(el('div', 'sub', PLAN.measure2 ? (PLAN.measure2 + ' / ' + PLAN.measure) : 'of target window'));
    wrap.appendChild(label);
    container.appendChild(wrap);
  }

  function buildShell() {
    root.textContent = '';
    var shell = el('div', 'shell');
    var side = el('aside', 'sidebar');
    var logo = el('div', 'side-logo', (PLAN.brand || 'A').charAt(0).toUpperCase());
    side.appendChild(logo);
    var icons = [
      ['M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4', true],
      ['M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', false],
      ['M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z', false],
      ['M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z', false]
    ];
    icons.forEach(function (item) {
      var btn = el('div', 'nav-btn' + (item[1] ? ' active' : ''));
      btn.appendChild(svgIcon(item[0]));
      side.appendChild(btn);
    });
    side.appendChild(el('div', 'nav-spacer'));
    var settings = el('div', 'nav-btn');
    settings.appendChild(svgIcon('M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4'));
    side.appendChild(settings);
    var main = el('main', 'main');
    shell.appendChild(side);
    shell.appendChild(main);
    root.appendChild(shell);
    return main;
  }

  function deltaFromSeries(series) {
    if (!series || series.length < 2) return { text: 'live', down: false };
    var a = series[series.length - 2];
    var b = series[series.length - 1];
    if (!a) return { text: 'live', down: false };
    var change = ((b - a) / Math.abs(a)) * 100;
    return {
      text: (change >= 0 ? '+' : '') + change.toFixed(1) + '%',
      down: change < 0
    };
  }

  function renderDashboard(model) {
    var main = buildShell();
    var top = el('div', 'topbar');
    var greet = el('div', 'greeting');
    greet.appendChild(el('div', 'eyebrow', PLAN.brand));
    greet.appendChild(el('h1', null, greeting() + '.'));
    greet.appendChild(el('p', 'takeaway',
      PLAN.measure + ' is ' + money(model.kpis.primary) +
      (model.kpis.ratio != null ? (' · ratio ' + pct(model.kpis.ratio)) : '') + '.'
    ));
    top.appendChild(greet);
    var actions = el('div', 'top-actions');
    var search = el('div', 'search-pill', 'Search metrics');
    actions.appendChild(search);
    actions.appendChild(el('div', 'chip', '6 months'));
    actions.appendChild(el('div', 'cta', '+ New view'));
    top.appendChild(actions);
    main.appendChild(top);

    var monthVals = (model.months || []).map(function (m) { return m.y; });
    var kpis = el('div', 'kpis');
    var cards = [
      { label: PLAN.measure, value: money(model.kpis.primary), series: monthVals }
    ];
    if (PLAN.measure2) {
      cards.push({
        label: PLAN.measure2,
        value: money(model.kpis.secondary),
        series: monthVals.map(function (v, i) { return v * (0.08 + (i % 5) * 0.01); })
      });
    }
    if (PLAN.countField) {
      cards.push({ label: PLAN.countField + ' count', value: String(model.kpis.count), series: monthVals });
    }
    if (model.kpis.ratio != null && PLAN.measure2) {
      cards.push({ label: 'Ratio', value: pct(model.kpis.ratio), series: monthVals });
    }
    while (cards.length < 4) {
      cards.push({
        label: (PLAN.dimension1 || 'Top slice'),
        value: model.dim1 && model.dim1[0] ? money(model.dim1[0].value) : '—',
        series: monthVals
      });
    }
    cards.slice(0, 4).forEach(function (card) {
      var node = el('div', 'kpi');
      node.appendChild(el('div', 'label', card.label));
      node.appendChild(el('div', 'value', card.value));
      var d = deltaFromSeries(card.series);
      var delta = el('div', 'delta' + (d.down ? ' down' : ''), d.text);
      node.appendChild(delta);
      node.appendChild(sparkline(card.series));
      kpis.appendChild(node);
    });
    main.appendChild(kpis);

    var layout = el('div', 'layout');
    if (model.months && model.months.length) {
      var trendPanel = el('div', 'panel');
      trendPanel.appendChild(el('h2', null, PLAN.measure + ' vs prior periods'));
      renderTrend(trendPanel, model.months);
      trendPanel.appendChild(el('p', 'note', model.months.length + ' months · live query'));
      layout.appendChild(trendPanel);
    }

    var sideStack = el('div', 'stack');
    var gaugePanel = el('div', 'panel');
    gaugePanel.appendChild(el('h2', null, PLAN.measure2 ? 'Secondary share' : 'Performance share'));
    renderGauge(gaugePanel, model.kpis.ratio != null ? Math.min(Math.abs(model.kpis.ratio), 1) : 0.69);
    sideStack.appendChild(gaugePanel);

    if (model.dim1 && model.dim1.length) {
      var p1 = el('div', 'panel');
      p1.appendChild(el('h2', null, 'By ' + PLAN.dimension1));
      renderBars(p1, model.dim1, false);
      sideStack.appendChild(p1);
    } else if (model.dim2 && model.dim2.length) {
      var p2 = el('div', 'panel');
      p2.appendChild(el('h2', null, 'By ' + PLAN.dimension2));
      renderBars(p2, model.dim2, true);
      sideStack.appendChild(p2);
    }
    layout.appendChild(sideStack);
    main.appendChild(layout);
  }

  function normalizeMonthRows(rows) {
    return rows.map(function (r) {
      return {
        x: monthKey(fieldValue(r, /date|month/i, 0)),
        y: Number(fieldValue(r, new RegExp(PLAN.measure.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'), 1)) || 0
      };
    }).sort(function (a, b) { return a.x < b.x ? -1 : 1; });
  }

  function normalizeNamed(rows, nameHint) {
    var re = nameHint ? new RegExp(nameHint.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i') : /./;
    return rows.map(function (r) {
      return {
        name: String(fieldValue(r, re, 0) || ''),
        value: Number(fieldValue(r, new RegExp(PLAN.measure.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'), 1)) || 0
      };
    }).sort(function (a, b) { return b.value - a.value; });
  }

  function queryErrorMessage(err) {
    if (!err) return 'unknown error';
    var parts = [];
    if (err.errorCode) parts.push(String(err.errorCode));
    if (err.message) parts.push(String(err.message));
    return parts.length ? parts.join(': ') : String(err);
  }

  function runQuery(ds, label, fields) {
    return ds.queryAsync({ fields: fields }).catch(function (err) {
      throw new Error(label + ' — ' + queryErrorMessage(err));
    });
  }

  root.textContent = '';
  root.appendChild(el('p', 'loading', 'Loading ' + PLAN.brand + '…'));

  tableau.extensions.initializeAsync().then(function () {
    return getDataSources();
  }).then(function (list) {
    var ds = findDataSource(list);
    if (!ds) throw new Error('No datasource is available on this workbook.');

    var jobs = [];
    var kpiFields = [{ fieldCaption: PLAN.measure, function: 'SUM' }];
    if (PLAN.measure2) kpiFields.push({ fieldCaption: PLAN.measure2, function: 'SUM' });
    if (PLAN.countField) kpiFields.push({ fieldCaption: PLAN.countField, function: 'COUNT' });
    jobs.push(runQuery(ds, 'KPIs', kpiFields));

    if (PLAN.dateField) {
      jobs.push(runQuery(ds, 'Trend', [
        { fieldCaption: PLAN.dateField, function: 'TRUNC_MONTH' },
        { fieldCaption: PLAN.measure, function: 'SUM' }
      ]));
    } else {
      jobs.push(Promise.resolve({ data: [] }));
    }

    if (PLAN.dimension1) {
      jobs.push(runQuery(ds, 'Dim1', [
        { fieldCaption: PLAN.dimension1 },
        { fieldCaption: PLAN.measure, function: 'SUM' }
      ]));
    } else {
      jobs.push(Promise.resolve({ data: [] }));
    }

    if (PLAN.dimension2) {
      jobs.push(runQuery(ds, 'Dim2', [
        { fieldCaption: PLAN.dimension2 },
        { fieldCaption: PLAN.measure, function: 'SUM' }
      ]));
    } else {
      jobs.push(Promise.resolve({ data: [] }));
    }

    return Promise.all(jobs);
  }).then(function (results) {
    var kpiRow = extractData(results[0])[0] || {};
    var primary = Number(fieldValue(kpiRow, new RegExp(PLAN.measure.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'), 0)) || 0;
    var secondary = PLAN.measure2
      ? (Number(fieldValue(kpiRow, new RegExp(PLAN.measure2.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'), 1)) || 0)
      : 0;
    var count = PLAN.countField
      ? (Number(fieldValue(kpiRow, new RegExp(PLAN.countField.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'), 2)) || 0)
      : 0;
    renderDashboard({
      kpis: {
        primary: primary,
        secondary: secondary,
        count: count,
        ratio: (PLAN.measure2 && primary) ? (secondary / primary) : null
      },
      months: normalizeMonthRows(extractData(results[1])),
      dim1: normalizeNamed(extractData(results[2]), PLAN.dimension1),
      dim2: normalizeNamed(extractData(results[3]), PLAN.dimension2)
    });
  }).catch(function (err) {
    root.textContent = '';
    var p = el('p', 'error');
    p.textContent = 'Live query unavailable: ' + queryErrorMessage(err);
    root.appendChild(p);
  });
})();
"""
    return template.replace("__PLAN__", json.dumps(plan))


def write_executive_preview_html(app_name: str = "Executive Data App", profile: dict | None = None) -> str:
    profile = profile or {}
    live_sample = profile.get("previewSample")
    if not isinstance(live_sample, dict):
        live_sample = PREVIEW_SAMPLE
    rebuild_id = str(profile.get("rebuildId") or "")
    live_flag = bool(live_sample.get("live"))
    theme_key, palette = resolve_theme(profile.get("theme"))
    sample = {
        "brand": profile.get("brand") or profile.get("datasourceName") or app_name,
        "measure": profile.get("measure") or "Measure",
        "measure2": profile.get("measure2") or "Secondary",
        "dimension1": profile.get("dimension1") or "Dimension 1",
        "dimension2": profile.get("dimension2") or "Dimension 2",
        "countField": profile.get("countField") or "Records",
        "kpis": live_sample.get("kpis") or PREVIEW_SAMPLE["kpis"],
        "months": live_sample.get("months") or PREVIEW_SAMPLE["months"],
        "dim1": live_sample.get("dim1") or PREVIEW_SAMPLE["dim1"],
        "dim2": live_sample.get("dim2") or PREVIEW_SAMPLE["dim2"],
        "rebuildId": rebuild_id,
        "live": live_flag,
        "theme": theme_key,
        "accent": palette["accent"],
        "accentDeep": palette["accentDeep"],
    }
    banner = (
        f"Fresh rebuild {rebuild_id} · theme {theme_key} · "
        + ("LIVE aggregates from selected datasource" if live_flag else "profile-labeled sample")
    )
    css = write_executive_styles_css(theme_key)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate" />
  <meta http-equiv="Pragma" content="no-cache" />
  <title>{app_name} — browser preview</title>
  <style>
{css}
  .preview-banner {{
    max-width: 1280px; margin: 0.55rem auto 0; padding: 0 1rem;
  }}
  .preview-banner span {{
    display: inline-block; font-size: 0.72rem; letter-spacing: 0.05em; text-transform: uppercase;
    color: #166534; background: rgba(34,197,94,0.14); border: 1px solid rgba(22,163,74,0.25);
    padding: 0.28rem 0.6rem; border-radius: 999px; font-weight: 650;
  }}
  </style>
</head>
<body>
  <div class="preview-banner"><span>{banner}</span></div>
  <div id="app"></div>
  <script>
  (function () {{
    var PLAN = {{
      brand: {json.dumps(sample["brand"])},
      measure: {json.dumps(sample["measure"])},
      measure2: {json.dumps(sample["measure2"])},
      dimension1: {json.dumps(sample["dimension1"])},
      dimension2: {json.dumps(sample["dimension2"])},
      countField: {json.dumps(sample["countField"])},
      theme: {json.dumps(sample["theme"])},
      accent: {json.dumps(sample["accent"])},
      accentDeep: {json.dumps(sample["accentDeep"])}
    }};
    var model = {{
      kpis: {json.dumps(sample["kpis"])},
      months: {json.dumps([{"x": m["month"], "y": m["value"]} for m in sample["months"]])},
      dim1: {json.dumps(sample["dim1"])},
      dim2: {json.dumps(sample["dim2"])}
    }};
    var S = {{
      live: {json.dumps(bool(sample.get("live")))},
      rebuildId: {json.dumps(sample.get("rebuildId") or "")}
    }};
    var root = document.getElementById('app');

    function money(n) {{
      var abs = Math.abs(n);
      if (abs >= 1e6) return (n < 0 ? '-' : '') + '$' + (abs / 1e6).toFixed(2) + 'M';
      if (abs >= 1e3) return (n < 0 ? '-' : '') + '$' + (abs / 1e3).toFixed(0) + 'K';
      return String(Math.round(n));
    }}
    function pct(n) {{ return (n * 100).toFixed(1) + '%'; }}
    function el(tag, cls, text) {{
      var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n;
    }}
    function smoothPath(coords) {{
      if (!coords.length) return '';
      var d = 'M' + coords[0].x + ' ' + coords[0].y;
      for (var i = 0; i < coords.length - 1; i++) {{
        var p0 = coords[i === 0 ? i : i - 1];
        var p1 = coords[i];
        var p2 = coords[i + 1];
        var p3 = coords[i + 2] || p2;
        var cp1x = p1.x + (p2.x - p0.x) / 6;
        var cp1y = p1.y + (p2.y - p0.y) / 6;
        var cp2x = p2.x - (p3.x - p1.x) / 6;
        var cp2y = p2.y - (p3.y - p1.y) / 6;
        d += ' C' + cp1x + ' ' + cp1y + ',' + cp2x + ' ' + cp2y + ',' + p2.x + ' ' + p2.y;
      }}
      return d;
    }}
    function sparkline(values) {{
      var width = 88, height = 28;
      var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('class', 'spark');
      svg.setAttribute('width', width); svg.setAttribute('height', height);
      svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
      var min = Math.min.apply(null, values), max = Math.max.apply(null, values), span = Math.max(max - min, 1);
      var coords = values.map(function (v, i) {{
        return {{
          x: (i * (width - 2)) / Math.max(values.length - 1, 1) + 1,
          y: height - 2 - ((v - min) / span) * (height - 4)
        }};
      }});
      var line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      line.setAttribute('d', smoothPath(coords));
      line.setAttribute('fill', 'none'); line.setAttribute('stroke', PLAN.accent); line.setAttribute('stroke-width', '2');
      svg.appendChild(line);
      return svg;
    }}
    function renderTrend(container, points) {{
      var width = 640, height = 250, padL = 18, padR = 12, padT = 16, padB = 28;
      var maxY = Math.max.apply(null, points.map(function (p) {{ return p.y; }}).concat([1]));
      var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
      svg.setAttribute('width', '100%'); svg.setAttribute('height', String(height));
      var defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      var grad = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
      grad.setAttribute('id', 'areaFill'); grad.setAttribute('x1', '0'); grad.setAttribute('y1', '0');
      grad.setAttribute('x2', '0'); grad.setAttribute('y2', '1');
      var s1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
      s1.setAttribute('offset', '0%'); s1.setAttribute('stop-color', PLAN.accent); s1.setAttribute('stop-opacity', '0.35');
      var s2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
      s2.setAttribute('offset', '100%'); s2.setAttribute('stop-color', PLAN.accent); s2.setAttribute('stop-opacity', '0.02');
      grad.appendChild(s1); grad.appendChild(s2); defs.appendChild(grad); svg.appendChild(defs);
      var coords = points.map(function (p, i) {{
        return {{
          x: padL + (i * (width - padL - padR)) / Math.max(points.length - 1, 1),
          y: height - padB - (p.y / maxY) * (height - padT - padB)
        }};
      }});
      var lineD = smoothPath(coords);
      var areaD = lineD + ' L' + coords[coords.length - 1].x + ' ' + (height - padB) +
        ' L' + coords[0].x + ' ' + (height - padB) + ' Z';
      var fill = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      fill.setAttribute('d', areaD); fill.setAttribute('fill', 'url(#areaFill)'); svg.appendChild(fill);
      var line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      line.setAttribute('d', lineD); line.setAttribute('fill', 'none');
      line.setAttribute('stroke', PLAN.accentDeep); line.setAttribute('stroke-width', '2.8'); svg.appendChild(line);
      container.appendChild(svg);
    }}
    function renderGauge(container, ratio) {{
      var pctVal = Math.max(0, Math.min(1, ratio));
      var size = 210, stroke = 16, r = (size / 2) - stroke, c = 2 * Math.PI * r, arc = c * 0.75;
      var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', size); svg.setAttribute('height', size * 0.72);
      svg.setAttribute('viewBox', '0 0 ' + size + ' ' + (size * 0.72));
      var g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('transform', 'translate(' + (size / 2) + ' ' + (size / 2) + ') rotate(135)');
      function ring(offset, color) {{
        var circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', '0'); circle.setAttribute('cy', '0'); circle.setAttribute('r', r);
        circle.setAttribute('fill', 'none'); circle.setAttribute('stroke', color);
        circle.setAttribute('stroke-width', stroke); circle.setAttribute('stroke-linecap', 'round');
        circle.setAttribute('stroke-dasharray', arc + ' ' + c);
        circle.setAttribute('stroke-dashoffset', String(offset));
        return circle;
      }}
      g.appendChild(ring(0, '#e7efea'));
      g.appendChild(ring(arc * (1 - pctVal), PLAN.accent));
      svg.appendChild(g);
      var wrap = el('div', 'gauge-wrap'); wrap.appendChild(svg);
      var label = el('div', 'gauge-label');
      label.appendChild(el('div', 'big', pct(pctVal)));
      label.appendChild(el('div', 'sub', PLAN.measure2 + ' / ' + PLAN.measure));
      wrap.appendChild(label); container.appendChild(wrap);
    }}

    var shell = el('div', 'shell');
    var side = el('aside', 'sidebar');
    side.appendChild(el('div', 'side-logo', (PLAN.brand || 'A').charAt(0).toUpperCase()));
    ['active','','',''].forEach(function (cls, i) {{
      var b = el('div', 'nav-btn' + (cls ? ' ' + cls : ''));
      b.textContent = ['⌂','▤','◎','▦'][i];
      side.appendChild(b);
    }});
    var main = el('main', 'main');
    var top = el('div', 'topbar');
    var greet = el('div', 'greeting');
    greet.appendChild(el('div', 'eyebrow', PLAN.brand));
    greet.appendChild(el('h1', null, 'Good afternoon.'));
    greet.appendChild(el('p', 'takeaway',
      PLAN.measure + ' for ' + PLAN.brand +
      (S.live ? ' · live query aggregates' : ' · provisional sample') +
      (S.rebuildId ? (' · rebuild ' + S.rebuildId) : '') + '.'
    ));
    top.appendChild(greet);
    var actions = el('div', 'top-actions');
    actions.appendChild(el('div', 'search-pill', 'Search metrics'));
    actions.appendChild(el('div', 'chip', '6 months'));
    actions.appendChild(el('div', 'cta', '+ New view'));
    top.appendChild(actions);
    main.appendChild(top);

    var monthVals = model.months.map(function (m) {{ return m.y; }});
    var kpis = el('div', 'kpis');
    [
      [PLAN.measure, money(model.kpis.primary)],
      [PLAN.measure2, money(model.kpis.secondary)],
      [PLAN.countField, String(model.kpis.count)],
      ['Ratio', pct(model.kpis.ratio)]
    ].forEach(function (pair) {{
      var card = el('div', 'kpi');
      card.appendChild(el('div', 'label', pair[0]));
      card.appendChild(el('div', 'value', pair[1]));
      card.appendChild(el('div', 'delta', '+4.2%'));
      card.appendChild(sparkline(monthVals));
      kpis.appendChild(card);
    }});
    main.appendChild(kpis);

    var layout = el('div', 'layout');
    var trend = el('div', 'panel');
    trend.appendChild(el('h2', null, PLAN.measure + ' vs prior periods'));
    renderTrend(trend, model.months);
    trend.appendChild(el('p', 'note', 'Preview sample · live query uses ' + PLAN.measure));
    layout.appendChild(trend);

    var stack = el('div', 'stack');
    var gauge = el('div', 'panel');
    gauge.appendChild(el('h2', null, 'Secondary share'));
    renderGauge(gauge, Math.min(Math.abs(model.kpis.ratio), 1));
    stack.appendChild(gauge);
    var bars = el('div', 'panel');
    bars.appendChild(el('h2', null, 'By ' + PLAN.dimension1));
    var max = Math.max.apply(null, model.dim1.map(function (r) {{ return r.value; }}).concat([1]));
    model.dim1.forEach(function (r) {{
      var row = el('div', 'bar-row');
      row.appendChild(el('div', null, r.name));
      var track = el('div', 'bar-track'); var fill = el('div', 'bar-fill');
      track.appendChild(fill); row.appendChild(track);
      row.appendChild(el('div', 'bar-val', money(r.value)));
      bars.appendChild(row);
      requestAnimationFrame(function () {{ fill.style.width = Math.max(8, (r.value / max) * 100) + '%'; }});
    }});
    stack.appendChild(bars);
    layout.appendChild(stack);
    main.appendChild(layout);
    shell.appendChild(side); shell.appendChild(main);
    root.appendChild(shell);
  }})();
  </script>
</body>
</html>
"""


def write_preview_file(workspace_dir: Path, app_name: str, profile: dict | None = None) -> Path:
    path = workspace_dir / "preview.html"
    path.write_text(write_executive_preview_html(app_name, profile), encoding="utf-8")
    return path.resolve()
