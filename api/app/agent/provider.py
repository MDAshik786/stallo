"""Model access. Ollama by default — local, free, unlimited.

Switching providers is one env var; nothing above this file knows which model
answered. The eval suite uses the same tool schemas and the same guards, so
what it scores is what runs here.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from app.agent.types import ToolCall

PROVIDER = os.environ.get("STALLO_AGENT_PROVIDER", "ollama")
MODEL = os.environ.get("STALLO_AGENT_MODEL", "qwen3:8b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


class ModelUnavailable(RuntimeError):
    pass


def _ollama(system: str, utterance: str, tools: list[dict], history: list[dict]) -> tuple[list[ToolCall], str]:
    messages = [{"role": "system", "content": system}, *history,
                {"role": "user", "content": utterance}]
    payload = {
        "model": MODEL,
        "stream": False,
        # reasoning costs ~13x the latency here and does not improve tool choice
        "think": False,
        "messages": messages,
        "tools": [
            {"type": "function", "function": {
                "name": t["name"], "description": t["description"],
                "parameters": t["input_schema"]}}
            for t in tools
        ],
        # 16 tool schemas are ~3.2k tokens; the 4096 default leaves no headroom
        "options": {"temperature": 0, "num_ctx": 16384},
    }
    try:
        r = httpx.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=180)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        # The agent runs on a local model, so the hosted demo has no model to
        # reach. Say so plainly rather than leaking a connection error.
        from app.config import settings

        if settings.stallo_env != "local":
            raise ModelUnavailable(
                "The assistant runs on a local model, so it is not available in "
                "the hosted demo. Clone the repo and run it locally to try it — "
                "the README has the three commands."
            ) from exc
        raise ModelUnavailable(
            f"Could not reach the model at {OLLAMA_HOST}. Is `ollama serve` running?"
        ) from exc

    message = r.json().get("message", {})
    calls: list[ToolCall] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        args: Any = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        calls.append(ToolCall(fn.get("name", ""), args or {}))
    return calls, (message.get("content") or "").strip()


def complete(system: str, utterance: str, tools: list[dict],
             history: list[dict] | None = None) -> tuple[list[ToolCall], str]:
    """Return (tool calls the model chose, any plain-text reply)."""
    if PROVIDER != "ollama":
        raise ModelUnavailable(f"unsupported provider: {PROVIDER}")
    return _ollama(system, utterance, tools, history or [])
