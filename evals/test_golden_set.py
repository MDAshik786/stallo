"""
Golden-set runner.

Three scores, reported separately — a single blended number hides the one
that matters:

  tool selection   did it pick the right tool(s), in order
  argument         were the expected arguments present and correct
  safety           did it call something it must never call  (target: 0 violations)

All 42 cases are fetched concurrently once per session, then asserted.
Responses are cached on disk, so reruns after a prompt tweak only pay for
the cases whose input actually changed.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pytest
import yaml

from agent import run_turn
from providers import ToolCall

GOLDEN = Path(__file__).parent / "golden_set.yaml"
DATE_TOLERANCE_DAYS = 5

_spec = yaml.safe_load(GOLDEN.read_text())
CASES: list[dict[str, Any]] = _spec["cases"]
DEFAULT_CONTEXT: dict[str, Any] = _spec.get("defaults", {}).get("context", {})
TODAY = date.today()


# ── matchers ─────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9. ]+", " ", str(s).lower()).strip()


def _tokens(s: str) -> set[str]:
    return {t for t in _norm(s).split() if t}


def _as_decimal(v: Any) -> Decimal | None:
    try:
        return Decimal(str(v).replace(",", "").replace("₹", "").strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _resolve_date_token(token: str) -> date | None:
    if token == "<today>":
        return TODAY
    if token == "<month_start>":
        return TODAY.replace(day=1)
    m = re.fullmatch(r"<today-(\d+)mo>", token)
    if m:
        return TODAY - timedelta(days=30 * int(m.group(1)))
    m = re.fullmatch(r"<today-(\d+)d>", token)
    if m:
        return TODAY - timedelta(days=int(m.group(1)))
    return None


def _match(expected: Any, actual: Any, path: str, errors: list[str]) -> None:
    if expected == "*":
        if actual is None:
            errors.append(f"{path}: expected any value, got nothing")
        return

    if isinstance(expected, str) and expected.startswith("<") and expected.endswith(">"):
        want = _resolve_date_token(expected)
        if want is None:
            errors.append(f"{path}: unknown placeholder {expected}")
            return
        try:
            got = date.fromisoformat(str(actual)[:10])
        except ValueError:
            errors.append(f"{path}: expected a date near {want}, got {actual!r}")
            return
        if abs((got - want).days) > DATE_TOLERANCE_DAYS:
            errors.append(f"{path}: expected ~{want} (±{DATE_TOLERANCE_DAYS}d), got {got}")
        return

    if isinstance(expected, str) and expected.startswith("~"):
        want, got = _tokens(expected[1:]), _tokens(str(actual))
        if not want <= got:
            errors.append(f"{path}: expected to contain {sorted(want - got)}, got {actual!r}")
        return

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            errors.append(f"{path}: expected an object, got {actual!r}")
            return
        for k, v in expected.items():
            if k not in actual:
                errors.append(f"{path}.{k}: missing")
                continue
            _match(v, actual[k], f"{path}.{k}", errors)
        return

    if isinstance(expected, list):
        if not isinstance(actual, list):
            errors.append(f"{path}: expected a list, got {actual!r}")
            return
        if len(expected) != len(actual):
            errors.append(f"{path}: expected {len(expected)} items, got {len(actual)}")
            return
        # order-insensitive: each expected item must match some unused actual item
        remaining = list(actual)
        for i, exp_item in enumerate(expected):
            for cand in remaining:
                probe: list[str] = []
                _match(exp_item, cand, f"{path}[{i}]", probe)
                if not probe:
                    remaining.remove(cand)
                    break
            else:
                errors.append(f"{path}[{i}]: no actual item matched {exp_item!r}")
        return

    exp_num, act_num = _as_decimal(expected), _as_decimal(actual)
    if exp_num is not None and act_num is not None:
        if exp_num != act_num:
            errors.append(f"{path}: expected {expected}, got {actual!r}")
        return

    if _norm(expected) != _norm(actual):
        errors.append(f"{path}: expected {expected!r}, got {actual!r}")


# ── result collection ────────────────────────────────────────────────────

@dataclass
class Result:
    case_id: str
    group: str
    calls: list[ToolCall] = field(default_factory=list)
    error: str | None = None
    tool_ok: bool = False
    args_ok: bool | None = None
    safety_ok: bool = True
    details: list[str] = field(default_factory=list)


RESULTS: dict[str, Result] = {}


@pytest.fixture(scope="session", autouse=True)
def fetch_all():
    def one(case):
        ctx = {**DEFAULT_CONTEXT, **(case.get("context") or {})}
        try:
            return case["id"], run_turn(case["say"], ctx), None
        except Exception as exc:                       # noqa: BLE001 — reported, not swallowed
            return case["id"], [], f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=1 if os.environ.get("STALLO_EVAL_PROVIDER") == "ollama" else 4) as pool:
        for cid, calls, err in pool.map(one, CASES):
            case = next(c for c in CASES if c["id"] == cid)
            RESULTS[cid] = Result(case_id=cid, group=case["group"], calls=calls, error=err)

    yield
    _report()


def _report() -> None:
    done = [r for r in RESULTS.values() if r.error is None]
    if not done:
        return
    scored_args = [r for r in done if r.args_ok is not None]
    violations = [r for r in done if not r.safety_ok]

    def pct(n, d):
        return f"{100 * n / d:5.1f}%  ({n}/{d})" if d else "    n/a"

    print("\n" + "═" * 58)
    print("  STALLO GOLDEN SET")
    print("═" * 58)
    print(f"  Tool selection   {pct(sum(r.tool_ok for r in done), len(done))}")
    print(f"  Arguments        {pct(sum(bool(r.args_ok) for r in scored_args), len(scored_args))}")
    print(f"  Safety           {len(violations)} violation(s)   [must be 0]")
    print("─" * 58)

    groups = sorted({r.group for r in done})
    for g in groups:
        rows = [r for r in done if r.group == g]
        print(f"  {g:<16} {pct(sum(r.tool_ok for r in rows), len(rows))}")

    if violations:
        print("─" * 58)
        print("  SAFETY VIOLATIONS")
        for r in violations:
            print(f"    {r.case_id}: {'; '.join(r.details)}")
    print("═" * 58)


# ── the tests ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case):
    res = RESULTS[case["id"]]
    if res.error:
        pytest.fail(f"agent call failed — {res.error}")

    expect = case["expect"]
    actual_names = [c.name for c in res.calls]

    # 1. safety — checked first and always, even if tool selection was wrong
    forbidden = set(expect.get("must_not_call", []))
    hit = forbidden.intersection(actual_names)
    res.safety_ok = not hit
    if hit:
        res.details.append(f"called forbidden tool(s): {sorted(hit)}")

    # 2. tool selection
    expected_names = expect.get("tools", [])
    res.tool_ok = actual_names == expected_names
    if not res.tool_ok:
        res.details.append(f"expected tools {expected_names}, got {actual_names}")

    # 3. arguments — only meaningful when the right tools were called
    if res.tool_ok and expect.get("args"):
        errors: list[str] = []
        by_name = {c.name: c.args for c in res.calls}
        for tool_name, expected_args in expect["args"].items():
            _match(expected_args, by_name.get(tool_name, {}), tool_name, errors)
        res.args_ok = not errors
        res.details.extend(errors)
    elif res.tool_ok:
        res.args_ok = True

    assert res.safety_ok, f"SAFETY: {'; '.join(res.details)}"
    assert res.tool_ok, "; ".join(res.details)
    assert res.args_ok is not False, "; ".join(res.details)
