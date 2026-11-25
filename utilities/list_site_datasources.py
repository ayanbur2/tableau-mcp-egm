"""List published datasources on the configured Tableau site (REST)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from utilities.tableau_datasource_wire import _signin, _signout


def list_site_datasources(page_size: int = 1000) -> list[dict[str, Any]]:
    """
    Return published datasources for the signed-in site.

    Each item: {id, name, projectId, projectName, contentUrl, type, updatedAt}
    """
    server, token, site_id = _signin()
    try:
        items: list[dict[str, Any]] = []
        page = 1
        total: int | None = None
        while True:
            qs = urllib.parse.urlencode({"pageSize": page_size, "pageNumber": page})
            req = urllib.request.Request(
                f"{server}/api/3.26/sites/{site_id}/datasources?{qs}",
                headers={
                    "X-Tableau-Auth": token,
                    "Accept": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    payload = json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:400]
                raise RuntimeError(f"list datasources failed ({exc.code}): {detail}") from exc

            block = payload.get("datasources") or {}
            raw = block.get("datasource") or []
            if isinstance(raw, dict):
                raw = [raw]
            pagination = payload.get("pagination") or {}
            try:
                total = int(pagination.get("totalAvailable") or total or 0)
            except (TypeError, ValueError):
                total = total or 0

            for ds in raw:
                if not isinstance(ds, dict):
                    continue
                ds_id = str(ds.get("id") or "").strip()
                if not ds_id:
                    continue
                project = ds.get("project") or {}
                items.append(
                    {
                        "id": ds_id,
                        "name": str(ds.get("name") or ds_id).strip(),
                        "projectId": str(project.get("id") or "").strip(),
                        "projectName": str(project.get("name") or "").strip(),
                        "contentUrl": str(ds.get("contentUrl") or "").strip(),
                        "type": str(ds.get("type") or "").strip(),
                        "updatedAt": str(ds.get("updatedAt") or "").strip(),
                    }
                )

            if not raw:
                break
            if total and len(items) >= total:
                break
            if len(raw) < page_size:
                break
            page += 1
            if page > 50:
                break

        items.sort(key=lambda d: (d.get("name") or "").lower())
        return items
    finally:
        _signout(server, token)
