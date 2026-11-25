"""Named Tableau site profiles (Cloud + Server) for Studio MCP switching."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def build_tableau_site_profiles() -> dict[str, dict[str, Any]]:
    """
    Build site profiles from env.

    Primary (legacy) keys SERVER / SITE_NAME / PAT_* become the `cloud` profile
    unless TABLEAU_SITE_CLOUD_* overrides are set. On-prem goes under `onprem`.
    """
    cloud_server = _env("TABLEAU_SITE_CLOUD_SERVER") or _env("SERVER")
    cloud_site = (
        os.environ.get("TABLEAU_SITE_CLOUD_SITE_NAME")
        if "TABLEAU_SITE_CLOUD_SITE_NAME" in os.environ
        else os.environ.get("SITE_NAME", "")
    )
    cloud_site = (cloud_site or "").strip()
    cloud_pat_name = _env("TABLEAU_SITE_CLOUD_PAT_NAME") or _env("PAT_NAME")
    cloud_pat_value = _env("TABLEAU_SITE_CLOUD_PAT_VALUE") or _env("PAT_VALUE")

    onprem_server = _env("TABLEAU_SITE_ONPREM_SERVER")
    onprem_site = (os.environ.get("TABLEAU_SITE_ONPREM_SITE_NAME") or "").strip()
    onprem_pat_name = _env("TABLEAU_SITE_ONPREM_PAT_NAME")
    onprem_pat_value = _env("TABLEAU_SITE_ONPREM_PAT_VALUE")

    profiles: dict[str, dict[str, Any]] = {
        "cloud": {
            "id": "cloud",
            "label": _env("TABLEAU_SITE_CLOUD_LABEL") or "Tableau Cloud",
            "server": cloud_server,
            "site_name": cloud_site,
            "pat_name": cloud_pat_name,
            "pat_value": cloud_pat_value,
            "enabled": bool(cloud_server and cloud_pat_name and cloud_pat_value),
        },
        "onprem": {
            "id": "onprem",
            "label": _env("TABLEAU_SITE_ONPREM_LABEL") or "Tableau Server",
            "server": onprem_server,
            "site_name": onprem_site,
            "pat_name": onprem_pat_name,
            "pat_value": onprem_pat_value,
            "enabled": bool(onprem_server and onprem_pat_name and onprem_pat_value),
        },
    }
    return profiles


def public_site_profile(profile: dict[str, Any]) -> dict[str, Any]:
    host = ""
    server = profile.get("server") or ""
    if server:
        try:
            host = urlparse(server).netloc or server
        except Exception:
            host = server
    site = (profile.get("site_name") or "").strip()
    return {
        "id": profile["id"],
        "label": profile.get("label") or profile["id"],
        "server": server,
        "host": host,
        "site_name": site,
        "site_display": site or "Default site",
        "enabled": bool(profile.get("enabled")),
        "kind": "cloud" if "online.tableau.com" in host else "server",
    }


def apply_site_profile_to_env(profile: dict[str, Any]) -> None:
    """Point legacy MCP env keys at the active profile (stdio child reads these)."""
    os.environ["SERVER"] = (profile.get("server") or "").strip()
    os.environ["SITE_NAME"] = (profile.get("site_name") or "").strip()
    os.environ["PAT_NAME"] = (profile.get("pat_name") or "").strip()
    os.environ["PAT_VALUE"] = (profile.get("pat_value") or "").strip()
    os.environ["AUTH"] = (os.environ.get("AUTH") or "pat").strip() or "pat"
    os.environ["DEFAULT_TABLEAU_SITE_PROFILE"] = str(profile.get("id") or "")
