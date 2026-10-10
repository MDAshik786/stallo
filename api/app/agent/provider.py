"""Model access.

Two providers behind one function. Ollama is the default for local
development — free and unlimited, which is what an eval loop needs. Groq
serves the hosted demo, because a 5.2 GB model cannot live in a 512 MB
container and `localhost` inside that container is the container itself.

Both speak the same OpenAI-shaped tool schema, so the tool definitions,
the guards, and the golden set are identical either way. Nothing above this
file knows which model answered.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

from app.agent.types import ToolCall
from app.config import settings

# config comes through Settings so it is read from .env and the environment
# alike — provider.py reading os.environ directly silently ignored .env
PROVIDER = settings.stallo_agent_provider
OLLAMA_HOST = settings.ollama_host
OLLAMA_MODEL = settings.stallo_agent_model

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = settings.stallo_groq_model

MODEL = GROQ_MODEL if PROVIDER == "groq" else OLLAMA_MODEL


class ModelUnavailable(RuntimeError):
    pass


def _openai_tools(tools: list[dict]) -> list[dict]:
    """Anthropic-shaped tool dicts -> the OpenAI function schema both
    Ollama and Groq accept. The Pydantic JSON Schema passes through."""
    return [
        {"type": "function", "function": {
            "name": t["name"], "description": t["description"],
            "parameters": t["input_schema"]}}
        for t in tools
    ]


def _parse_tool_calls(message: dict[str, Any]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        args: Any = fn.get("arguments", {})
        if isinstance(args, str):
            # Groq returns arguments as a JSON string; Ollama as an object
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        calls.append(ToolCall(fn.get("name", ""), args or {}))
    return calls


def _with_retry(fn, attempts: int = 4, base: float = 1.8):
    """Free tiers rate-limit and shed load. Retry 429/5xx with backoff;
    fail fast on anything else so a real error is not hidden by waiting."""
    for i in range(attempts):
        try:
            return fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (408, 429, 500, 502, 503, 504) or i == attempts - 1:
                raise
            time.sleep(base ** i + random.random())
    raise RuntimeError("unreachable")


def _ollama(system: str, utterance: str, tools: list[dict], history: list[dict]):
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        # reasoning costs ~13x the latency here and does not improve tool choice
        "think": False,
        "messages": [{"role": "system", "content": system}, *history,
                     {"role": "user", "content": utterance}],
        "tools": _openai_tools(tools),
        # 17 tool schemas are ~3.4k tokens; the 4096 default leaves no headroom
        "options": {"temperature": 0, "num_ctx": 16384},
    }
    try:
        r = httpx.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=180)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise ModelUnavailable(
            f"Could not reach the model at {OLLAMA_HOST}. Is `ollama serve` running?"
        ) from exc
    message = r.json().get("message", {})
    return _parse_tool_calls(message), (message.get("content") or "").strip()


def _groq(system: str, utterance: str, tools: list[dict], history: list[dict]):
    key = settings.groq_api_key
    if not key:
        raise ModelUnavailable("GROQ_API_KEY is not set on this deployment.")

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0,
        "messages": [{"role": "system", "content": system}, *history,
                     {"role": "user", "content": utterance}],
        "tools": _openai_tools(tools),
        "tool_choice": "auto",
    }

    def call():
        r = httpx.post(GROQ_URL, json=payload, timeout=90,
                       headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        return r

    try:
        response = _with_retry(call)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise ModelUnavailable(
                "The demo's free model allowance is used up for now. "
                "Try again shortly, or run it locally — the README has the commands."
            ) from exc
        raise ModelUnavailable(f"The model service returned {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise ModelUnavailable("Could not reach the model service.") from exc

    message = (response.json().get("choices") or [{}])[0].get("message", {})
    return _parse_tool_calls(message), (message.get("content") or "").strip()


def complete(system: str, utterance: str, tools: list[dict],
             history: list[dict] | None = None) -> tuple[list[ToolCall], str]:
    """Return (tool calls the model chose, any plain-text reply)."""
    history = history or []
    if PROVIDER == "ollama":
        return _ollama(system, utterance, tools, history)
    if PROVIDER == "groq":
        return _groq(system, utterance, tools, history)
    raise ModelUnavailable(f"unsupported provider: {PROVIDER}")
