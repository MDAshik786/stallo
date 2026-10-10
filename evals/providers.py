"""
Model adapters. Everything else in this suite is provider-agnostic — the
golden set, the tool schemas, and the scorer never mention a vendor. Only this
file knows how a particular API wants its tools declared.

Each adapter takes (system, user_text, tools) and returns the tool calls the
model chose, as plain dicts. No tools are executed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app.agent.types import ToolCall  # noqa: E402


# ── Anthropic ────────────────────────────────────────────────────────────

def call_anthropic(system: str, user_text: str, tools: list[dict], model: str,
                   effort: str) -> list[ToolCall]:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=16000,
        system=system,
        tools=tools,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": user_text}],
    )
    return [
        ToolCall(name=b.name, args=b.input)
        for b in response.content
        if b.type == "tool_use"
    ]


# ── Google Gemini ────────────────────────────────────────────────────────

def _with_retry(fn, attempts: int = 5, base: float = 2.0):
    """Free tiers rate-limit and occasionally shed load. Retry 429/503 with
    exponential backoff; fail fast on anything else."""
    import random
    import time

    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            transient = any(c in str(exc) for c in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"))
            if not transient or i == attempts - 1:
                raise
            time.sleep(base ** i + random.random())
    raise RuntimeError("unreachable")


def _to_gemini_tools(tools: list[dict]):
    """Anthropic tool dicts -> one Gemini Tool holding all declarations.

    parameters_json_schema takes raw JSON Schema, so the Pydantic-generated
    schema passes through unchanged — no per-provider schema rewriting.
    """
    from google.genai import types

    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters_json_schema=t["input_schema"],
                )
                for t in tools
            ]
        )
    ]


def call_gemini(system: str, user_text: str, tools: list[dict], model: str,
                effort: str) -> list[ToolCall]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = _with_retry(lambda: client.models.generate_content(
        model=model,
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=system,
            tools=_to_gemini_tools(tools),
            # we score the model's choice; we never execute the tool
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    ))

    calls: list[ToolCall] = []
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else []) or []:
            if part.function_call:
                calls.append(
                    ToolCall(name=part.function_call.name, args=dict(part.function_call.args or {}))
                )
    return calls


# ── Ollama (local) ───────────────────────────────────────────────────────

def call_ollama(system: str, user_text: str, tools: list[dict], model: str,
                effort: str) -> list[ToolCall]:
    """Local model over Ollama's /api/chat. Unlimited and free, which is what
    an eval loop needs; weaker at tool selection than a frontier model."""
    import json as _json

    import httpx

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    payload = {
        "model": model,
        "stream": False,
        # reasoning models burn ~13x the time here for no gain on tool
        # selection; the choice is the output, not the deliberation
        "think": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ],
        # 16 tool schemas alone are ~3.2k tokens; the 4096 default leaves no
        # room for context or output. Raise it, and pin temperature for
        # reproducible eval runs.
        "options": {"temperature": 0, "num_ctx": 16384},
    }

    r = httpx.post(f"{host}/api/chat", json=payload, timeout=300)
    r.raise_for_status()
    message = r.json().get("message", {})

    calls: list[ToolCall] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        args = fn.get("arguments", {})
        if isinstance(args, str):          # some models return a JSON string
            try:
                args = _json.loads(args)
            except _json.JSONDecodeError:
                args = {}
        calls.append(ToolCall(name=fn.get("name", ""), args=args or {}))
    return calls


# ── Groq (free tier, hosted) ─────────────────────────────────────────────

def call_groq(system: str, user_text: str, tools: list[dict], model: str,
              effort: str) -> list[ToolCall]:
    """Same OpenAI-shaped tool schema as Ollama, so the golden set is
    unchanged — only the endpoint differs."""
    import json as _json

    import httpx

    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        timeout=90,
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
        json={
            "model": model,
            "temperature": 0,
            "tool_choice": "auto",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user_text}],
            "tools": [
                {"type": "function", "function": {
                    "name": t["name"], "description": t["description"],
                    "parameters": t["input_schema"]}}
                for t in tools
            ],
        },
    )
    r.raise_for_status()
    message = (r.json().get("choices") or [{}])[0].get("message", {})

    calls: list[ToolCall] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = _json.loads(args)
            except _json.JSONDecodeError:
                args = {}
        calls.append(ToolCall(fn.get("name", ""), args or {}))
    return calls


PROVIDERS: dict[str, Callable[..., list[ToolCall]]] = {
    "anthropic": call_anthropic,
    "gemini": call_gemini,
    "ollama": call_ollama,
    "groq": call_groq,
}

DEFAULT_MODEL = {
    "anthropic": "claude-opus-5",
    "gemini": "gemini-3.6-flash",
    "ollama": "qwen3:8b",
    "groq": "llama-3.3-70b-versatile",
}
