"""
One seller utterance in, the tool calls the model chose out.

Deliberately a single turn with no tool execution. The golden set tests tool
SELECTION and ARGUMENTS; whether the tools then do the right thing is the
backend's own unit tests.

Provider is chosen with STALLO_EVAL_PROVIDER (anthropic | gemini). The rest of
the suite never knows which one ran.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from providers import DEFAULT_MODEL, PROVIDERS, ToolCall

from app.agent.guards import guard
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tools import to_anthropic_tools

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PROVIDER = os.environ.get("STALLO_EVAL_PROVIDER", "gemini")
MODEL = os.environ.get("STALLO_EVAL_MODEL") or DEFAULT_MODEL[PROVIDER]
EFFORT = os.environ.get("STALLO_EVAL_EFFORT", "medium")
CACHE_DIR = Path(os.environ.get("STALLO_EVAL_CACHE_DIR", ".eval_cache"))
USE_CACHE = os.environ.get("STALLO_EVAL_CACHE", "1") == "1"

_TOOLS = to_anthropic_tools()


def _cache_key(say: str, context: dict[str, Any], today: str) -> str:
    blob = json.dumps(
        {"say": say, "context": context, "today": today, "provider": PROVIDER,
         "model": MODEL, "effort": EFFORT, "tools": _TOOLS, "system": SYSTEM_PROMPT},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def run_turn(say: str, context: dict[str, Any] | None = None,
             today: str | None = None) -> list[ToolCall]:
    context = context or {}
    today = today or date.today().isoformat()

    cached = None
    raw: list[ToolCall] | None = None

    if USE_CACHE:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached = CACHE_DIR / f"{PROVIDER}-{_cache_key(say, context, today)}.json"
        if cached.exists():
            raw = [ToolCall(**c) for c in json.loads(cached.read_text())]

    if raw is None:
        system = SYSTEM_PROMPT.format(
            today=today,
            context=json.dumps(context, indent=2, default=str) or "{}",
        )
        raw = PROVIDERS[PROVIDER](system, say, _TOOLS, MODEL, EFFORT)
        if cached is not None:
            cached.write_text(json.dumps([c.__dict__ for c in raw], indent=2, default=str))

    # Cache holds the RAW model output; guards run after. Iterating on policy
    # therefore costs no API calls at all — only a prompt change invalidates.
    # The model proposes; guards decide. Same policy the API applies at runtime,
    # so the eval scores what actually ships.
    return guard(raw, context, say)
