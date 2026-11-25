from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from utilities.chart_tool import ensure_chart_from_tool_messages


def _truncate(text: str, limit: int = 4000) -> str:
    t = text or ""
    if len(t) <= limit:
        return t
    return t[: limit - 20] + "\n… [truncated]"


def _content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("text"):
                    parts.append(str(block["text"]))
                elif block.get("type") == "text" and block.get("text"):
                    parts.append(str(block["text"]))
                else:
                    try:
                        parts.append(json.dumps(block, ensure_ascii=False))
                    except Exception:
                        parts.append(str(block))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    try:
        return json.dumps(content, ensure_ascii=False, default=str)
    except Exception:
        return str(content)


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


def extract_agent_steps(
    messages: list[Any],
    *,
    outbound_prompt: str = "",
    system_prompt: str = "",
    profile_id: str = "",
) -> list[dict[str, Any]]:
    """Build Claude-like expandable steps from LangGraph message history."""
    steps: list[dict[str, Any]] = []
    n = 0

    def add(kind: str, title: str, detail: str = "", meta: dict | None = None) -> None:
        nonlocal n
        n += 1
        steps.append(
            {
                "id": f"step-{n}",
                "index": n,
                "kind": kind,
                "title": title,
                "detail": _truncate(detail or "", 6000),
                "meta": meta or {},
            }
        )

    if profile_id:
        add("profile", f"LLM profile · {profile_id}", f"Active profile: {profile_id}")

    if system_prompt:
        add(
            "system",
            "System prompt",
            system_prompt,
            {"source": "AGENT_SYSTEM_PROMPT"},
        )

    if outbound_prompt:
        add(
            "prompt",
            "Outbound user message",
            outbound_prompt,
            {"role": "human"},
        )

    for msg in messages or []:
        cls = type(msg).__name__
        # Skip the initial human we already recorded as outbound_prompt
        if cls in {"HumanMessage", "Human"} and outbound_prompt:
            # Still show later human messages if any
            text = _content_to_text(getattr(msg, "content", ""))
            if text.strip() and text.strip() != outbound_prompt.strip():
                add("prompt", "Follow-up human message", text)
            continue

        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name") or "tool"
                    args = tc.get("args") if "args" in tc else tc.get("arguments")
                    tc_id = tc.get("id") or ""
                else:
                    name = getattr(tc, "name", None) or "tool"
                    args = getattr(tc, "args", None) or getattr(tc, "arguments", None)
                    tc_id = getattr(tc, "id", "") or ""
                add(
                    "tool_call",
                    f"Tool call · {name}",
                    _safe_json(args if args is not None else {}),
                    {"tool": name, "tool_call_id": tc_id},
                )
            # Also capture any assistant reasoning text alongside tool calls
            text = _content_to_text(getattr(msg, "content", "")).strip()
            if text:
                add("thought", "Model note", text)

        elif cls in {"ToolMessage", "Tool"} or getattr(msg, "name", None):
            name = getattr(msg, "name", None) or "tool"
            text = _content_to_text(getattr(msg, "content", ""))
            add(
                "tool_result",
                f"Tool result · {name}",
                text,
                {
                    "tool": name,
                    "tool_call_id": getattr(msg, "tool_call_id", "") or "",
                },
            )

        elif cls in {"AIMessage", "AI", "AssistantMessage"}:
            text = _content_to_text(getattr(msg, "content", "")).strip()
            if text:
                add("answer", "Model response", text)

    return steps


async def format_agent_response(
    agent,
    messages,
    langfuse_handler,
    *,
    outbound_prompt: str = "",
    system_prompt: str = "",
    profile_id: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    """Stream response from agent; return (final_text, trace_steps)."""

    response_text = ""
    last_messages: list[Any] = []
    request_thread_id = f"session_{uuid4().hex}"
    config: dict[str, Any] = {"configurable": {"thread_id": request_thread_id}}
    if langfuse_handler is not None:
        config["callbacks"] = [langfuse_handler]

    async for chunk in agent.astream(
        {"messages": messages},
        config=config,
        stream_mode="values",
    ):
        if "messages" in chunk and chunk["messages"]:
            last_messages = chunk["messages"]
            latest_message = chunk["messages"][-1]
            if hasattr(latest_message, "content"):
                response_text = _content_to_text(latest_message.content)

    response_text = ensure_chart_from_tool_messages(response_text, last_messages)
    fallback_prompt = _content_to_text(messages[0].content) if messages else ""
    steps = extract_agent_steps(
        last_messages,
        outbound_prompt=outbound_prompt or fallback_prompt,
        system_prompt=system_prompt,
        profile_id=profile_id,
    )
    return response_text, steps
