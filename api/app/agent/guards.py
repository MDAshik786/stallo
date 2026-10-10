"""Deterministic policy applied to the model's chosen tool calls.

The model proposes; this decides. Every rule here was added because the golden
set caught the model getting it wrong, and because prompting alone did not fix
it — a longer prompt measured *worse*. An invariant that must hold is code, not
a sentence in a system prompt.

Guards never execute anything. They rewrite an unsafe call into the call that
should have been made: a suspension (request_choice / request_confirmation) or
a refusal.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.agent.tools import REGISTRY, Exposure
from app.agent.types import ToolCall

# tools whose args name a thing that must already exist
_ID_FIELDS = ("product_id", "variant_id", "target_id")

# which write each resume-only tool must be approved through
_CONFIRMABLE = {
    "publish_product": "publish_product",
    "delete_product": "delete_product",
    "delete_variant": "delete_variant",
}


def _choice(field: str, prompt: str) -> ToolCall:
    return ToolCall("request_choice", {"field": field, "prompt": prompt})


def _refuse(reason: str, message: str) -> ToolCall:
    return ToolCall("refuse", {"reason": reason, "message": message})


def _known_ids(context: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("products", "variants"):
        for row in context.get(key) or []:
            if isinstance(row, dict) and row.get("id"):
                ids.add(str(row["id"]))
    if context.get("focus_product_id"):
        ids.add(str(context["focus_product_id"]))
    return ids


def _amount(value: Any) -> Decimal | None:
    """Pull a numeric amount out of a Money-shaped arg, however the model wrote it."""
    if isinstance(value, dict):
        value = value.get("amount")
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("₹", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _digits(text: str) -> set[str]:
    """Numbers as the seller wrote them, normalised for comparison."""
    cleaned = text.replace(",", "").replace("\u20b9", " ")
    found = set()
    for raw in re.findall(r"\d+(?:\.\d+)?", cleaned):
        found.add(raw)
        found.add(raw.rstrip("0").rstrip(".") if "." in raw else raw)
        try:
            found.add(str(int(float(raw))))
        except ValueError:
            pass
    return found


def _grounded(value: Any, utterance: str) -> bool:
    """Did this number come from the seller, or did the model invent it?

    The golden set caught "add a jasmine bouquet" producing a confident
    price of 1500. The arguments were structurally perfect — only grounding
    tells invented apart from stated.
    """
    amount = _amount(value)
    if amount is None:
        return True
    candidates = {
        str(amount),
        str(amount.normalize()),
        format(amount, "f").rstrip("0").rstrip("."),
    }
    try:
        if amount == amount.to_integral_value():
            candidates.add(str(int(amount)))
    except (InvalidOperation, ValueError):
        pass
    return bool(candidates & _digits(utterance))



# A name is grounded when it reuses a word the seller actually typed. These
# carry no information on their own, so a "name" made only of them is a
# placeholder the model invented.
_FILLER = {
    "a", "an", "the", "add", "new", "create", "product", "item", "thing",
    "please", "for", "to", "my", "store", "some", "this", "that", "unnamed",
}


def _name_grounded(name: Any, utterance: str) -> bool:
    words = {w for w in re.findall(r"[a-z0-9]+", str(name).lower()) if w not in _FILLER}
    if not words:
        return False
    return bool(words & set(re.findall(r"[a-z0-9]+", utterance.lower())))


# The agent may choose dates only when the seller gave a resolvable time
# reference. "last three months" resolves; "during Diwali" does not — festival
# dates move every year, and a confident guess is worse than a question.
_TEMPORAL = re.compile(
    r"\b(today|yesterday|tonight|this (week|month|quarter|year)"
    r"|last (week|month|quarter|year)|past|previous|recent|so far|to date|ytd"
    r"|since|between|from|\d{4}-\d{2}-\d{2}|(19|20)\d{2}"
    r"|\d+\s*(day|days|week|weeks|month|months|year|years)"
    r"|one|two|three|four|five|six|seven|eight|nine|ten|twelve"
    r"|jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?"
    r"|sep(tember)?|oct(ober)?|nov(ember)?|dec(ember)?|q[1-4])\b",
    re.IGNORECASE,
)

# Required and ungrounded -> ask. Optional and ungrounded -> drop it and use
# the default. Asking "how many are in stock?" when the seller only said "add a
# rose bouquet for Rs899" is noise; inventing a price is a real hazard.
_ASK_IF_UNGROUNDED = ("price",)
_DROP_IF_UNGROUNDED = ("stock_quantity", "description")


# The seller sees these questions, so we write them. A model asked
# "What price (in paise) should the Lavender Bunch be listed at?" — paise is
# an internal storage unit and no seller thinks in it.
_OUR_WORDING = {
    "name": "What should this product be called?",
    "price": "What price should I set?",
    "stock_quantity": "How many are in stock?",
    "product_id": "Which product do you mean?",
    "variant_id": "Which one do you mean?",
    "date_range": (
        "Which dates should I look at? Festival and event dates move every "
        "year, so I'd rather not guess."
    ),
}


def guard(
    calls: list[ToolCall],
    context: dict[str, Any] | None = None,
    utterance: str = "",
) -> list[ToolCall]:
    """Return the calls that may proceed, with unsafe ones rewritten."""
    context = context or {}
    known = _known_ids(context)
    out: list[ToolCall] = []

    for call in calls:
        args = call.args or {}

        # 1. A resume-only write reached us directly. The model does not get to
        #    publish or delete — only an approved resume does.
        if call.name in _CONFIRMABLE:
            target = next((args[f] for f in _ID_FIELDS if args.get(f)), None)
            out.append(ToolCall("request_confirmation", {
                "action": _CONFIRMABLE[call.name],
                "target_id": target,
                "summary": f"{call.name.replace('_', ' ')} — needs your approval",
            }))
            continue

        # 2. Unknown tool name. Small models occasionally invent one.
        if call.name not in REGISTRY:
            out.append(_refuse("unsupported_capability",
                               f"I don't have a tool called {call.name}."))
            continue

        # 3. Creating a product needs a name and a price the seller actually gave.
        if call.name == "create_product":
            name = str(args.get("name") or "").strip()
            if not name or (utterance and not _name_grounded(name, utterance)):
                out.append(_choice("name", "What should this product be called?"))
                continue
            amount = _amount(args.get("price"))
            if amount is None:
                out.append(_choice("price", "What price should I set?"))
                continue
            if amount <= 0:
                out.append(_refuse("invalid_value", "A price has to be greater than zero."))
                continue

        # 4. Any price anywhere must be positive.
        if "price" in args:
            amount = _amount(args.get("price"))
            if amount is not None and amount <= 0:
                out.append(_refuse("invalid_value", "A price has to be greater than zero."))
                continue

        if "stock_quantity" in args:
            try:
                if int(args["stock_quantity"]) < 0:
                    out.append(_refuse("invalid_value", "Stock cannot be negative."))
                    continue
            except (TypeError, ValueError):
                out.append(_choice("stock_quantity", "How many are in stock?"))
                continue

        # 5. Undo is only offered when the audit log says the action is undoable.
        if call.name == "undo_action":
            last = context.get("last_action") or {}
            if not last:
                out.append(_refuse("not_undoable", "There's nothing to undo yet."))
                continue
            if last.get("undoable") is False:
                blocked = last.get("blocked_by") or "it can no longer be reversed"
                out.append(_refuse("not_undoable", f"I can't undo that — {blocked}."))
                continue

        # 6. Numbers must come from the seller, not from the model's imagination.
        if utterance:
            ungrounded = next(
                (f for f in _ASK_IF_UNGROUNDED
                 if f in args and args[f] is not None and not _grounded(args[f], utterance)),
                None,
            )
            if ungrounded:
                out.append(_choice(ungrounded, "What price should I set?"))
                continue

            invented = {
                f for f in _DROP_IF_UNGROUNDED
                if args.get(f) is not None and not (
                    _grounded(args[f], utterance)
                    if f != "description"
                    else str(args[f]).lower() in utterance.lower()
                )
            }
            if invented:
                args = {k: v for k, v in args.items() if k not in invented}
                call = ToolCall(call.name, args)

        # 7. Dates need a time reference the seller actually gave.
        if utterance and call.name in ("query_revenue", "query_product_sales") and (
            args.get("start_date") or args.get("end_date")
        ):
            if not _TEMPORAL.search(utterance):
                out.append(_choice(
                    "date_range",
                    "Which dates should I look at? Festival and event dates move "
                    "every year, so I'd rather not guess.",
                ))
                continue

        # 8. Never act on an id that isn't in front of us.
        bad_id = next(
            (f for f in _ID_FIELDS if args.get(f) and str(args[f]) not in known),
            None,
        )
        if bad_id:
            out.append(_choice(bad_id, "Which one do you mean?"))
            continue

        # 9. We own the wording of any question the seller reads.
        if call.name == "request_choice":
            better = _OUR_WORDING.get(str(args.get("field", "")))
            if better and args.get("prompt") != better:
                call = ToolCall(call.name, {**args, "prompt": better})

        out.append(call)

    # 10. Collapse a duplicate suspension — one question at a time.
    deduped: list[ToolCall] = []
    for call in out:
        if call.name in ("request_choice", "request_confirmation", "refuse") and deduped:
            if deduped[-1].name == call.name and deduped[-1].args == call.args:
                continue
        deduped.append(call)
    return deduped


def model_callable(name: str) -> bool:
    entry = REGISTRY.get(name)
    return bool(entry) and entry[1] is not Exposure.RESUME_ONLY
