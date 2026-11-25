"""Named LLM profiles for Studio (OpenAI + OpenAI-compatible gateways)."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _normalize_base_url(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u:
        return ""
    if not u.endswith("/v1"):
        u = f"{u}/v1"
    return u


def build_llm_profiles() -> dict[str, dict[str, Any]]:
    """Server-side profiles. Secrets stay here; UI only sees public fields."""
    openai_model = _env("OPENAI_MODEL") or _env("LLM_MODEL") or "gpt-5.4-mini"
    gateway_url = _normalize_base_url(
        _env("LLM_GATEWAY_URL") or "https://k14y3qdc2f.execute-api.us-east-2.amazonaws.com"
    )
    gateway_key = _env("LLM_GATEWAY_API_KEY")
    gateway_model = _env("LLM_GATEWAY_MODEL") or "us.meta.llama3-1-8b-instruct-v1:0"

    profiles: dict[str, dict[str, Any]] = {
        "openai": {
            "id": "openai",
            "label": "OpenAI Studio",
            "provider": _env("LLM_PROVIDER") or "OpenAI",
            "model": openai_model,
            "theme": "blue",
            "page": "/",
            "api_key": _env("OPENAI_API_KEY"),
            "base_url": None,
            "enabled": bool(_env("OPENAI_API_KEY")),
        },
        "bedrock-gateway": {
            "id": "bedrock-gateway",
            "label": "Bedrock Gateway",
            "provider": _env("LLM_GATEWAY_PROVIDER") or "AWS Bedrock",
            "model": gateway_model,
            "theme": "red",
            "page": "/?llm=bedrock-gateway",
            "api_key": gateway_key,
            "base_url": gateway_url,
            "enabled": bool(gateway_key and gateway_url),
        },
    }
    return profiles


def public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    host = ""
    base = profile.get("base_url") or ""
    if base:
        try:
            host = urlparse(base).netloc
        except Exception:
            host = base
    return {
        "id": profile["id"],
        "label": profile["label"],
        "provider": profile["provider"],
        "model": profile["model"],
        "theme": profile["theme"],
        "page": profile["page"],
        "enabled": bool(profile.get("enabled")),
        "gateway_host": host,
    }


def create_chat_model(profile: dict[str, Any]) -> ChatOpenAI:
    if not profile.get("enabled"):
        raise RuntimeError(f"LLM profile '{profile.get('id')}' is not configured")

    kwargs: dict[str, Any] = {
        "model": profile["model"],
        "temperature": 0,
        "api_key": profile["api_key"],
    }
    if profile.get("base_url"):
        kwargs["base_url"] = profile["base_url"]
    return ChatOpenAI(**kwargs)
