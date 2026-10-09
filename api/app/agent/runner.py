"""The run state machine.

    running -> awaiting_input    -> running -> completed
            -> awaiting_approval -> running -> completed
                                 -> rejected
            -> failed

Clarification and approval are the same mechanism: a tool that suspends the
run instead of returning a value. One idea, two product features — and because
the run lives in Postgres rather than React state, a pending question survives
a refresh, a closed tab, and tomorrow morning.

Approval is structural. The model can propose `publish`; only a resume carrying
the seller's decision executes it. No amount of typed "yes" reaches the write.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.executor import Executor
from app.agent.guards import guard
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.provider import ModelUnavailable, complete
from app.agent.tools import to_anthropic_tools
from app.agent.types import ToolCall
from app.models import AgentAction, AgentRun, Product

SUSPENDING = {"request_choice": "awaiting_input", "request_confirmation": "awaiting_approval"}
_TOOLS = to_anthropic_tools()


def build_context(db: Session, seller_id: uuid.UUID) -> dict[str, Any]:
    """What the model is allowed to know. Ids it may reference come only from here."""
    products = list(db.scalars(
        select(Product).where(Product.seller_id == seller_id)
        .order_by(Product.updated_at.desc()).limit(20)
    ))
    last = db.scalars(
        select(AgentAction).where(AgentAction.seller_id == seller_id)
        .order_by(AgentAction.created_at.desc()).limit(1)
    ).one_or_none()

    focus = None
    for action in db.scalars(
        select(AgentAction).where(
            AgentAction.seller_id == seller_id, AgentAction.status == "success"
        ).order_by(AgentAction.created_at.desc()).limit(5)
    ):
        if isinstance(action.result, dict) and action.result.get("id"):
            focus = action.result["id"]
            break

    return {
        "products": [
            {"id": str(p.id), "name": p.name, "status": p.status,
             "category_slug": p.category_slug, "price_paise": p.price_paise}
            for p in products
        ],
        "focus_product_id": focus,
        "last_action": (
            {"id": str(last.id), "tool": last.tool,
             "undoable": bool(last.undoable and last.undone_at is None)}
            if last else None
        ),
    }


def _system(context: dict[str, Any]) -> str:
    return SYSTEM_PROMPT.format(
        today=date.today().isoformat(),
        context=json.dumps(context, indent=2, default=str),
    )


def _suspend(run: AgentRun, call: ToolCall) -> AgentRun:
    run.status = SUSPENDING[call.name]
    run.suspension = {"kind": call.name, **call.args}
    return run


def _advance(db: Session, run: AgentRun, seller_id: uuid.UUID,
             utterance: str, history: list[dict]) -> AgentRun:
    """One model turn: ask, guard, then either suspend or execute."""
    context = build_context(db, seller_id)
    try:
        raw, text = complete(_system(context), utterance, _TOOLS, history)
    except ModelUnavailable as exc:
        run.status, run.error = "failed", str(exc)
        db.commit()
        return run

    calls = guard(raw, context, utterance)

    if not calls:
        run.status, run.reply = "completed", text or "Done."
        db.commit()
        return run

    first = calls[0]
    if first.name in SUSPENDING:
        _suspend(run, first)
        db.commit()
        return run

    if first.name == "refuse":
        run.status = "completed"
        run.reply = first.args.get("message") or "I can't do that."
        db.commit()
        return run

    executor = Executor(db, seller_id, run.id)
    results = [{"tool": c.name, "result": executor.run(c)} for c in calls]
    run.status = "completed"
    data_tools = {"query_revenue", "query_product_sales", "query_orders",
                  "get_agent_action_history"}
    # For a data question the numbers are the answer; the model's prose
    # restates them less accurately, so the summary wins.
    if any(r["tool"] in data_tools for r in results):
        run.reply = _summarise(results)
    else:
        run.reply = text or _summarise(results)
    run.results = results
    run.messages = [*(run.messages or []), {"role": "assistant", "results": results}]
    db.commit()
    return run


def _rupees(paise: int) -> str:
    """Indian digit grouping: 1,54,646 rather than 154,646."""
    whole = abs(int(paise)) // 100
    text = str(whole)
    if len(text) > 3:
        head, tail = text[:-3], text[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        text = ",".join(groups) + "," + tail
    return f"\u20b9{'-' if paise < 0 else ''}{text}"


def _summarise(results: list[dict]) -> str:
    """Answer in a sentence. A seller asked a question; "Done." is not an
    answer, and neither is a chart with no words around it."""
    for entry in results:
        tool, result = entry["tool"], entry["result"]

        if result.get("error"):
            return result["error"]

        if tool == "create_product" and result.get("name"):
            return f"Created \u201c{result['name']}\u201d as a draft."

        if tool == "update_product" and result.get("name"):
            return f"Updated \u201c{result['name']}\u201d."

        if tool == "query_revenue":
            scope = f" from {result['category_slug']}" if result.get("category_slug") else ""
            line = (
                f"{_rupees(result['total_paise'])}{scope} across "
                f"{result['order_count']} orders, "
                f"{result['start_date']} to {result['end_date']}."
            )
            change, previous = result.get("change_pct"), result.get("previous_total_paise")
            if change is not None:
                direction = "up" if change >= 0 else "down"
                line += (f" That is {direction} {abs(change)}% on the previous "
                         f"period ({_rupees(previous or 0)}).")
            elif previous == 0:
                line += " There is nothing in the previous period to compare against."
            return line

        if tool == "query_product_sales":
            rows = result.get("products") or []
            if not rows:
                return "No sales in that period."
            top = ", ".join(
                f"{r['name']} ({r['quantity']} sold, {_rupees(r['revenue_paise'])})"
                for r in rows[:3]
            )
            return f"Top sellers: {top}."

        if tool == "query_orders":
            rows = result.get("orders") or []
            if not rows:
                return "No orders match that."
            listed = ", ".join(
                f"{r['customer_name']} {_rupees(r['total_paise'])} ({r['status']})"
                for r in rows[:5]
            )
            return f"{len(rows)} order(s): {listed}."

        if tool == "get_agent_action_history":
            actions = result.get("actions") or []
            if not actions:
                return "I have not changed anything yet."
            return ("Recently: "
                    + ", ".join(a["tool"].replace("_", " ") for a in actions[:5]) + ".")

    return "Done."


def start(db: Session, seller_id: uuid.UUID, utterance: str) -> AgentRun:
    run = AgentRun(seller_id=seller_id, utterance=utterance, status="running",
                   messages=[{"role": "user", "content": utterance}])
    db.add(run)
    db.commit()
    db.refresh(run)
    return _advance(db, run, seller_id, utterance, [])


def resume(db: Session, seller_id: uuid.UUID, run: AgentRun,
           answer: str | None = None, approved: bool | None = None) -> AgentRun:
    suspension = run.suspension or {}

    if run.status == "awaiting_approval":
        if not approved:
            run.status, run.reply = "rejected", "Cancelled — nothing was changed."
            run.suspension = None
            db.commit()
            return run

        action = suspension.get("action")
        target = suspension.get("target_id")
        run.suspension = None
        run.status = "running"
        db.commit()

        executor = Executor(db, seller_id, run.id)
        result = executor.run(ToolCall(action, {"product_id": target}))
        run.status = "completed"
        run.reply = (
            result["error"] if result.get("error")
            else f"{action.replace('_', ' ').capitalize()} done."
        )
        db.commit()
        return run

    if run.status == "awaiting_input":
        field = suspension.get("field", "value")
        run.suspension = None
        run.status = "running"
        db.commit()

        # Re-attempt the ORIGINAL request with the gap filled, rather than
        # sending the bare answer. "₹120" on its own reads as a new instruction
        # and the model latches onto focus_product_id — it updated an existing
        # product instead of creating the one the seller actually asked for.
        filled = f"{run.utterance} — the {field} is {answer}"
        history = [
            {"role": "user", "content": run.utterance},
            {"role": "assistant", "content": suspension.get("prompt") or f"Which {field}?"},
        ]
        return _advance(db, run, seller_id, filled, history)

    return run
