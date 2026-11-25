"""Inspect a published datasource (VDS read-metadata) and pick fields for data apps."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from utilities.tableau_datasource_wire import _signin, _signout


def read_datasource_metadata(datasource_luid: str) -> list[dict[str, Any]]:
    """Return VDS field metadata rows for a published datasource."""
    server, token, _site_id = _signin()
    try:
        body = json.dumps({"datasource": {"datasourceLuid": datasource_luid}}).encode()
        req = urllib.request.Request(
            f"{server}/api/v1/vizql-data-service/read-metadata",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Tableau-Auth": token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
        data = payload.get("data") or []
        if not isinstance(data, list):
            raise ValueError("Unexpected VDS metadata shape")
        return data
    finally:
        _signout(server, token)


def _caption(field: dict[str, Any]) -> str:
    return str(field.get("fieldCaption") or field.get("fieldName") or "").strip()


def _role(field: dict[str, Any]) -> str:
    return str(field.get("fieldRole") or "").upper()


def _dtype(field: dict[str, Any]) -> str:
    return str(field.get("dataType") or "").upper()


def _pick(
    fields: list[dict[str, Any]],
    *,
    role: str | None = None,
    dtypes: tuple[str, ...] | None = None,
    name_hints: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    scored: list[tuple[int, dict[str, Any]]] = []
    for f in fields:
        if role and _role(f) != role:
            continue
        if dtypes and _dtype(f) not in dtypes:
            continue
        cap = _caption(f).lower()
        if not cap or cap.startswith("measure names") or cap == "number of records":
            continue
        score = 0
        for i, hint in enumerate(name_hints):
            if hint in cap:
                score += 100 - i
        scored.append((score, f))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], _caption(x[1]).lower()))
    return scored[0][1]


def profile_datasource(datasource_luid: str) -> dict[str, Any]:
    """
    Build a compact field profile used to author a data app from scratch.

    Returns measure/date/dimension captions plus wiring column specs.
    """
    fields = read_datasource_metadata(datasource_luid)
    visible = [f for f in fields if not f.get("hidden")]

    measure = (
        _pick(
            visible,
            role="MEASURE",
            dtypes=("REAL", "INTEGER", "FLOAT", "DOUBLE"),
            name_hints=("sales", "revenue", "amount", "profit", "value", "qty", "quantity"),
        )
        or _pick(visible, role="MEASURE")
    )
    measure2 = None
    if measure:
        measure2 = _pick(
            [f for f in visible if _caption(f) != _caption(measure)],
            role="MEASURE",
            dtypes=("REAL", "INTEGER", "FLOAT", "DOUBLE"),
            name_hints=("profit", "margin", "cost", "quantity", "count"),
        )

    date_field = _pick(
        visible,
        role="DIMENSION",
        dtypes=("DATE", "DATETIME"),
        name_hints=("order date", "date", "created", "ship date", "close"),
    ) or _pick(visible, dtypes=("DATE", "DATETIME"))

    dim1 = _pick(
        visible,
        role="DIMENSION",
        dtypes=("STRING",),
        name_hints=("region", "category", "segment", "state", "country", "product", "type"),
    ) or _pick(visible, role="DIMENSION", dtypes=("STRING", "BOOLEAN"))

    dim2 = None
    if dim1:
        dim2 = _pick(
            [f for f in visible if _caption(f) != _caption(dim1)],
            role="DIMENSION",
            dtypes=("STRING",),
            name_hints=("category", "sub-category", "segment", "region", "product", "ship"),
        ) or _pick(
            [f for f in visible if _caption(f) != _caption(dim1)],
            role="DIMENSION",
            dtypes=("STRING",),
        )

    count_dim = _pick(
        visible,
        role="DIMENSION",
        dtypes=("STRING", "INTEGER"),
        name_hints=("order id", "order", "customer", "id", "row"),
    )

    def _col_spec(field: dict[str, Any] | None) -> dict[str, str] | None:
        if not field:
            return None
        caption = _caption(field)
        dtype = _dtype(field)
        role = _role(field)
        if dtype in ("DATE", "DATETIME"):
            return {
                "caption": caption,
                "datatype": "date" if dtype == "DATE" else "datetime",
                "role": "dimension",
                "type": "ordinal",
                "aggregation": "Count",
            }
        if role == "MEASURE" or dtype in ("REAL", "INTEGER", "FLOAT", "DOUBLE"):
            return {
                "caption": caption,
                "datatype": "integer" if dtype == "INTEGER" else "real",
                "role": "measure",
                "type": "quantitative",
                "aggregation": "Sum",
            }
        return {
            "caption": caption,
            "datatype": "string",
            "role": "dimension",
            "type": "nominal",
            "aggregation": "Count",
        }

    chosen = [measure, measure2, date_field, dim1, dim2, count_dim]
    columns: list[dict[str, str]] = []
    seen: set[str] = set()
    for f in chosen:
        spec = _col_spec(f)
        if not spec:
            continue
        key = spec["caption"].lower()
        if key in seen:
            continue
        seen.add(key)
        columns.append(spec)

    if not measure:
        raise ValueError(
            "Datasource has no usable measure field for a data app. "
            "Pick another published datasource."
        )

    return {
        "datasourceLuid": datasource_luid,
        "fieldCount": len(visible),
        "measure": _caption(measure),
        "measure2": _caption(measure2) if measure2 else "",
        "dateField": _caption(date_field) if date_field else "",
        "dimension1": _caption(dim1) if dim1 else "",
        "dimension2": _caption(dim2) if dim2 else "",
        "countField": _caption(count_dim) if count_dim else "",
        "columns": columns,
        "brand": os.environ.get("SITE_NAME") or "Data App",
    }


def slug_datapp_name(datasource_name: str, suffix: str = "Data App") -> str:
    """Build a valid datapp display name from a datasource name."""
    base = re.sub(r"[^A-Za-z0-9 ._-]+", " ", datasource_name or "App").strip()
    base = re.sub(r"\s+", " ", base)[:60].strip(" .-_") or "App"
    name = f"{base} {suffix}".strip()
    return name[:100]


def _vds_query(datasource_luid: str, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run one VizQL Data Service query; return data rows."""
    server, token, _site_id = _signin()
    try:
        body = json.dumps(
            {
                "datasource": {"datasourceLuid": datasource_luid},
                "query": {"fields": fields},
            }
        ).encode()
        req = urllib.request.Request(
            f"{server}/api/v1/vizql-data-service/query-datasource",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Tableau-Auth": token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode())
        data = payload.get("data") or []
        return data if isinstance(data, list) else []
    finally:
        _signout(server, token)


def _row_number(row: dict[str, Any], hint: str, fallback_index: int = 0) -> float:
    keys = list(row.keys())
    hint_l = (hint or "").lower()
    for k in keys:
        if hint_l and hint_l in str(k).lower():
            try:
                return float(row[k])
            except (TypeError, ValueError):
                continue
    if fallback_index < len(keys):
        try:
            return float(row[keys[fallback_index]])
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _row_text(row: dict[str, Any], hint: str, fallback_index: int = 0) -> str:
    keys = list(row.keys())
    hint_l = (hint or "").lower()
    for k in keys:
        if hint_l and hint_l in str(k).lower():
            return str(row[k] if row[k] is not None else "")
    if fallback_index < len(keys):
        return str(row[keys[fallback_index]] if row[keys[fallback_index]] is not None else "")
    return ""


def _month_key(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    # Already YYYY-MM or ISO datetime
    m = re.match(r"(\d{4}-\d{2})", text)
    if m:
        return m.group(1)
    return text[:7] if len(text) >= 7 else text


def synthetic_preview_sample(profile: dict[str, Any]) -> dict[str, Any]:
    """Profile-labeled placeholder sample (never Superstore region/category names)."""
    dim1 = profile.get("dimension1") or "Segment"
    dim2 = profile.get("dimension2") or "Category"
    return {
        "live": False,
        "kpis": {"primary": 1250000, "secondary": 84000, "count": 3200, "ratio": 0.067},
        "months": [
            {"month": f"2024-{str(i).zfill(2)}", "value": 70000 + i * 9000}
            for i in range(1, 13)
        ],
        "dim1": [
            {"name": f"{dim1} A", "value": 420000},
            {"name": f"{dim1} B", "value": 310000},
            {"name": f"{dim1} C", "value": 260000},
            {"name": f"{dim1} D", "value": 180000},
        ],
        "dim2": [
            {"name": f"{dim2} 1", "value": 390000},
            {"name": f"{dim2} 2", "value": 340000},
            {"name": f"{dim2} 3", "value": 280000},
        ],
    }


def build_live_preview_sample(profile: dict[str, Any]) -> dict[str, Any]:
    """
    Query the published datasource for real aggregates used in browser preview.
    Falls back to synthetic_preview_sample on any query failure.
    """
    luid = (profile.get("datasourceLuid") or "").strip()
    measure = profile.get("measure") or ""
    measure2 = profile.get("measure2") or ""
    date_field = profile.get("dateField") or ""
    dim1 = profile.get("dimension1") or ""
    dim2 = profile.get("dimension2") or ""
    count_field = profile.get("countField") or ""
    if not luid or not measure:
        return synthetic_preview_sample(profile)

    try:
        kpi_fields: list[dict[str, Any]] = [{"fieldCaption": measure, "function": "SUM"}]
        if measure2:
            kpi_fields.append({"fieldCaption": measure2, "function": "SUM"})
        if count_field:
            kpi_fields.append({"fieldCaption": count_field, "function": "COUNT"})
        kpi_rows = _vds_query(luid, kpi_fields)
        kpi_row = kpi_rows[0] if kpi_rows else {}
        primary = _row_number(kpi_row, measure, 0)
        secondary = _row_number(kpi_row, measure2, 1) if measure2 else 0.0
        count = int(_row_number(kpi_row, count_field, 2)) if count_field else 0
        ratio = (secondary / primary) if (measure2 and primary) else None

        months: list[dict[str, Any]] = []
        if date_field:
            month_rows = _vds_query(
                luid,
                [
                    {"fieldCaption": date_field, "function": "TRUNC_MONTH"},
                    {"fieldCaption": measure, "function": "SUM"},
                ],
            )
            for r in month_rows:
                months.append(
                    {
                        "month": _month_key(_row_text(r, date_field, 0)),
                        "value": _row_number(r, measure, 1),
                    }
                )
            months = [m for m in months if m["month"]]
            months.sort(key=lambda m: m["month"])

        def _dim_rows(caption: str) -> list[dict[str, Any]]:
            if not caption:
                return []
            rows = _vds_query(
                luid,
                [
                    {"fieldCaption": caption},
                    {"fieldCaption": measure, "function": "SUM"},
                ],
            )
            out = [
                {
                    "name": _row_text(r, caption, 0) or "(null)",
                    "value": _row_number(r, measure, 1),
                }
                for r in rows
            ]
            out.sort(key=lambda x: x["value"], reverse=True)
            return out[:8]

        sample = {
            "live": True,
            "kpis": {
                "primary": primary,
                "secondary": secondary,
                "count": count,
                "ratio": ratio if ratio is not None else 0.0,
            },
            "months": months or synthetic_preview_sample(profile)["months"],
            "dim1": _dim_rows(dim1) or synthetic_preview_sample(profile)["dim1"],
            "dim2": _dim_rows(dim2) or synthetic_preview_sample(profile)["dim2"],
        }
        return sample
    except Exception:
        fallback = synthetic_preview_sample(profile)
        fallback["live"] = False
        return fallback
