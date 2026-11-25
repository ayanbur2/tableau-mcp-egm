"""Wire a published Tableau datasource into a data-app workbook as sqlproxy (live query)."""

from __future__ import annotations

import os
import re
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _signin() -> tuple[str, str, str]:
    server = os.environ["SERVER"].rstrip("/")
    site = os.environ["SITE_NAME"]
    pat_name = os.environ["PAT_NAME"]
    pat_value = os.environ["PAT_VALUE"]
    body = (
        "<tsRequest>"
        f'<credentials personalAccessTokenName="{pat_name}" '
        f'personalAccessTokenSecret="{pat_value}">'
        f'<site contentUrl="{site}" />'
        "</credentials></tsRequest>"
    )
    req = urllib.request.Request(
        f"{server}/api/3.26/auth/signin",
        data=body.encode(),
        headers={"Content-Type": "application/xml"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        xml = resp.read().decode()
    token = re.search(r'token="([^"]+)"', xml).group(1)
    site_id = re.search(r'<site[^>]*id="([^"]+)"', xml).group(1)
    return server, token, site_id


def _signout(server: str, token: str) -> None:
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                f"{server}/api/3.26/auth/signout",
                data=b"",
                headers={"X-Tableau-Auth": token},
                method="POST",
            ),
            timeout=15,
        ).read()
    except Exception:
        pass


def fetch_published_datasource_meta(datasource_luid: str) -> dict[str, Any]:
    """Resolve published datasource name + contentUrl for sqlproxy wiring."""
    server, token, site_id = _signin()
    try:
        req = urllib.request.Request(
            f"{server}/api/3.26/sites/{site_id}/datasources/{datasource_luid}",
            headers={"X-Tableau-Auth": token},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            meta_xml = resp.read().decode()
        name_m = re.search(r'<datasource[^>]*name="([^"]+)"', meta_xml)
        content_m = re.search(r'contentUrl="([^"]+)"', meta_xml)
        ds_name = name_m.group(1) if name_m else datasource_luid
        content_url = content_m.group(1) if content_m else ds_name.replace(" ", "")
        host = urlparse(server).hostname or server.replace("https://", "").replace("http://", "")
        return {
            "datasourceLuid": datasource_luid,
            "datasourceName": ds_name,
            "contentUrl": content_url,
            "serverHost": host,
            "siteContentUrl": os.environ["SITE_NAME"],
            "server": server,
        }
    finally:
        _signout(server, token)


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


_DEFAULT_COLUMNS = [
    {"caption": "Sales", "datatype": "real", "role": "measure", "type": "quantitative", "aggregation": "Sum"},
    {"caption": "Profit", "datatype": "real", "role": "measure", "type": "quantitative", "aggregation": "Sum"},
    {"caption": "Order Date", "datatype": "date", "role": "dimension", "type": "ordinal", "aggregation": "Count"},
    {"caption": "Region", "datatype": "string", "role": "dimension", "type": "nominal", "aggregation": "Count"},
    {"caption": "Category", "datatype": "string", "role": "dimension", "type": "nominal", "aggregation": "Count"},
]


def _normalize_columns(columns: list[dict[str, str]] | None) -> list[dict[str, str]]:
    if not columns:
        return list(_DEFAULT_COLUMNS)
    out: list[dict[str, str]] = []
    for c in columns:
        caption = (c.get("caption") or "").strip()
        if not caption:
            continue
        out.append(
            {
                "caption": caption,
                "datatype": c.get("datatype") or "string",
                "role": c.get("role") or "dimension",
                "type": c.get("type") or "nominal",
                "aggregation": c.get("aggregation") or "Count",
            }
        )
    return out or list(_DEFAULT_COLUMNS)


def _column_xml(col: dict[str, str]) -> str:
    return (
        f"      <column aggregation='{col['aggregation']}' caption='{_xml_escape(col['caption'])}' "
        f"datatype='{col['datatype']}' name='[{_xml_escape(col['caption'])}]' "
        f"role='{col['role']}' type='{col['type']}' />"
    )


def _column_instance_xml(col: dict[str, str]) -> str:
    # nominal -> nk, ordinal -> ok, quantitative -> qk (Tableau instance naming)
    suffix = {"nominal": "nk", "ordinal": "ok", "quantitative": "qk"}.get(col["type"], "nk")
    return (
        f"            <column-instance column='[{_xml_escape(col['caption'])}]' derivation='None' "
        f"name='[none:{_xml_escape(col['caption'])}:{suffix}]' pivot='key' type='{col['type']}' />"
    )


def build_sqlproxy_datasource_xml(
    meta: dict[str, Any],
    columns: list[dict[str, str]] | None = None,
) -> tuple[str, str, str]:
    """Build workbook-local sqlproxy datasource XML. Returns (xml, internal_name, caption)."""
    caption = meta["datasourceName"]
    content_url = meta["contentUrl"]
    site = meta["siteContentUrl"]
    host = meta["serverHost"]
    slug = re.sub(r"[^a-z0-9]+", "", content_url.lower())[:28] or "ds"
    internal_name = f"sqlproxy.{slug}"
    cols = _normalize_columns(columns)

    columns_xml = "\n".join(_column_xml(c) for c in cols)
    xml = (
        f"    <datasource caption='{_xml_escape(caption)}' inline='true' "
        f"name='{internal_name}' version='18.1'>\n"
        f"      <repository-location id='{_xml_escape(content_url)}' "
        f"path='/t/{_xml_escape(site)}/datasources' site='{_xml_escape(site)}' />\n"
        f"      <connection channel='https' class='sqlproxy' "
        f"dbname='{_xml_escape(content_url)}' directory='/dataserver' port='443' "
        f"server='{_xml_escape(host)}' "
        f"server-ds-friendly-name='{_xml_escape(caption)}' username=''>\n"
        f"        <relation name='sqlproxy' table='[sqlproxy]' type='table' />\n"
        f"      </connection>\n"
        f"{columns_xml}\n"
        f"    </datasource>"
    )
    return xml, internal_name, caption


def _build_view_dependency_block(
    internal_name: str,
    caption: str,
    columns: list[dict[str, str]] | None = None,
) -> str:
    cols = _normalize_columns(columns)
    cols_xml = "\n".join(_column_xml(c) for c in cols)
    instances = "\n".join(_column_instance_xml(c) for c in cols)
    return (
        "<datasources>\n"
        f"            <datasource caption='{_xml_escape(caption)}' name='{internal_name}' />\n"
        "          </datasources>\n"
        f"          <datasource-dependencies datasource='{internal_name}'>\n"
        f"{cols_xml}\n"
        f"{instances}\n"
        "          </datasource-dependencies>"
    )


def wire_published_datasource_into_workspace(
    workspace_dir: Path,
    twb_path: Path,
    datasource_luid: str,
    columns: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Wire the published datasource as a live sqlproxy connection (required for
    Extensions API queryAsync / VizQL Data Service). Does not embed Excel extracts.
    """
    meta = fetch_published_datasource_meta(datasource_luid)
    ds_xml, internal_name, caption = build_sqlproxy_datasource_xml(meta, columns=columns)

    twb_text = twb_path.read_text(encoding="utf-8")

    # Replace workbook-level datasources (anchored before <worksheets> to avoid nested matches)
    twb_text_new, n = re.subn(
        r"<datasources\s*/>\s*(<worksheets>)",
        f"<datasources>\n{ds_xml}\n  </datasources>\n  \\1",
        twb_text,
        count=1,
    )
    if n == 0:
        twb_text_new, n = re.subn(
            r"<datasources>\s*</datasources>\s*(<worksheets>)",
            f"<datasources>\n{ds_xml}\n  </datasources>\n  \\1",
            twb_text,
            count=1,
            flags=re.DOTALL,
        )
    if n == 0:
        twb_text_new, n = re.subn(
            r"<datasources>[\s\S]*?</datasources>\s*(<worksheets>)",
            f"<datasources>\n{ds_xml}\n  </datasources>\n  \\1",
            twb_text,
            count=1,
        )
    if n == 0:
        raise ValueError("Could not locate workbook <datasources> before <worksheets>")
    twb_text = twb_text_new

    view_block = _build_view_dependency_block(internal_name, caption, columns=columns)

    # Replace worksheet/view datasources (+ optional prior dependencies)
    twb_text_new, n = re.subn(
        r"(<worksheet\b[^>]*>[\s\S]*?<view>\s*)"
        r"(?:<datasources\s*/>|<datasources>[\s\S]*?</datasources>)"
        r"(?:\s*<datasource-dependencies[\s\S]*?</datasource-dependencies>)?",
        r"\1" + view_block,
        twb_text,
        count=1,
    )
    twb_text = twb_text_new if n else twb_text

    twb_path.write_text(twb_text, encoding="utf-8")

    # Remove stale embedded Data/ extract from older wiring attempts
    data_dir = workspace_dir / "Data"
    if data_dir.exists():
        import shutil

        shutil.rmtree(data_dir, ignore_errors=True)

    return {
        **meta,
        "wiredDatasourceName": caption,
        "wiredDatasourceInternalName": internal_name,
        "connectionClass": "sqlproxy",
        "workspaceDir": str(workspace_dir.resolve()),
        "twbPath": str(twb_path.resolve()),
        "hasDataFolder": False,
    }
