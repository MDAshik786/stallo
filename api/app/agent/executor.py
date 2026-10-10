"""Executes a guarded tool call against the seller's own data.

Two rules hold absolutely:

  * seller_id is never a tool argument. It arrives from the authenticated
    session and is baked into the repository before any tool runs, so the
    model chooses *which* query and *what* filters — never *whose* data.

  * every execution appends to the audit log, success or failure. The log is
    the source of truth: the activity timeline, undo, and debugging are all
    reads of it.
"""

from __future__ import annotations

import time
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.types import ToolCall
from app.models import AgentAction, Product
from app.repositories.analytics import AnalyticsRepository
from app.repositories.orders import OrderRepository
from app.repositories.products import ProductRepository


class ToolError(Exception):
    """A tool could not do what was asked. Surfaced to the seller, logged, not a crash."""


# Models disagree on shape: some return {"amount": 899, "currency": "INR"},
# some the bare number, some the string "₹899" or "1,299.50".
_NOT_A_NUMBER = str.maketrans("", "", "₹$€£, \u00a0")


def to_paise(value: Any) -> int:
    if isinstance(value, dict):
        value = value.get("amount")
    try:
        cleaned = str(value).translate(_NOT_A_NUMBER)
        return int((Decimal(cleaned) * 100).to_integral_value())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ToolError(f"could not read {value!r} as an amount") from exc


def _product_json(p: Product) -> dict[str, Any]:
    return {
        "id": str(p.id), "name": p.name, "price_paise": p.price_paise,
        "category_slug": p.category_slug, "status": p.status,
        "stock_quantity": p.stock_quantity, "description": p.description,
    }


class Executor:
    def __init__(self, db: Session, seller_id: uuid.UUID, run_id: uuid.UUID | None = None):
        self._db = db
        self._seller_id = seller_id
        self._run_id = run_id
        self._products = ProductRepository(db, seller_id)
        self._orders = OrderRepository(db, seller_id)
        self._analytics = AnalyticsRepository(db, seller_id)

    # ── audit log ────────────────────────────────────────────────────────

    def _log(self, tool: str, args: dict, result: dict, status: str,
             undoable: bool = False, inverse: dict | None = None,
             duration_ms: int | None = None) -> AgentAction:
        action = AgentAction(
            seller_id=self._seller_id, run_id=self._run_id, tool=tool, args=args,
            result=result, status=status, undoable=undoable, inverse=inverse,
            duration_ms=duration_ms,
        )
        self._db.add(action)
        self._db.commit()
        self._db.refresh(action)
        return action

    # ── dispatch ─────────────────────────────────────────────────────────

    def run(self, call: ToolCall) -> dict[str, Any]:
        started = time.perf_counter()
        handler = getattr(self, f"_t_{call.name}", None)
        if handler is None:
            result = {"error": f"{call.name} is not implemented yet"}
            self._log(call.name, call.args, result, "refused")
            return result

        try:
            result, undoable, inverse = handler(call.args)
            status = "success"
        except ToolError as exc:
            result, undoable, inverse, status = {"error": str(exc)}, False, None, "failed"

        elapsed = int((time.perf_counter() - started) * 1000)
        action = self._log(call.name, call.args, result, status, undoable, inverse, elapsed)
        return {**result, "action_id": str(action.id)}

    # ── product tools ────────────────────────────────────────────────────

    def _t_create_product(self, args: dict):
        product = self._products.create(Product(
            name=str(args["name"]).strip(),
            price_paise=to_paise(args.get("price")),
            category_slug=args.get("category_slug"),
            description=args.get("description"),
            stock_quantity=int(args.get("stock_quantity") or 0),
            status="draft",
        ))
        return (
            _product_json(product),
            True,
            {"tool": "delete_product", "args": {"product_id": str(product.id)}},
        )

    def _t_update_product(self, args: dict):
        product = self._products.get(uuid.UUID(str(args["product_id"])))
        if product is None:
            raise ToolError("that product does not exist")

        before = _product_json(product)
        if args.get("name"):
            product.name = str(args["name"]).strip()
        if args.get("price") is not None:
            product.price_paise = to_paise(args["price"])
        if args.get("category_slug"):
            product.category_slug = args["category_slug"]
        if args.get("description") is not None:
            product.description = args["description"]
        if args.get("stock_quantity") is not None:
            product.stock_quantity = int(args["stock_quantity"])
        self._db.commit()
        self._db.refresh(product)

        return (
            _product_json(product),
            True,
            {"tool": "_restore_product", "args": {"product_id": str(product.id), "fields": before}},
        )

    def _t_get_product(self, args: dict):
        product = self._products.get(uuid.UUID(str(args["product_id"])))
        if product is None:
            raise ToolError("that product does not exist")
        return _product_json(product), False, None

    def _t_preview_product(self, args: dict):
        return self._t_get_product(args)

    def _t_list_products(self, args: dict):
        rows = self._products.list(status=args.get("status"), limit=int(args.get("limit") or 20))
        return {"products": [_product_json(p) for p in rows]}, False, None

    # ── approval-only writes (reached via resume, never from the model) ──

    def _t_publish_product(self, args: dict):
        product = self._products.get(uuid.UUID(str(args["product_id"])))
        if product is None:
            raise ToolError("that product does not exist")
        product.status = "published"
        self._db.commit()
        self._db.refresh(product)
        return (
            _product_json(product),
            True,
            {"tool": "_set_status", "args": {"product_id": str(product.id), "status": "draft"}},
        )

    def _t_delete_product(self, args: dict):
        product = self._products.get(uuid.UUID(str(args["product_id"])))
        if product is None:
            raise ToolError("that product does not exist")
        snapshot = _product_json(product)
        self._db.delete(product)
        self._db.commit()
        return {"deleted": snapshot}, False, None

    # ── analytics ────────────────────────────────────────────────────────
    #
    # The model supplies filters only. It never writes SQL, never picks an
    # ORDER BY, and never names a seller — AnalyticsRepository was constructed
    # with the tenant before any of this ran.

    def _t_query_revenue(self, args: dict):
        report = self._analytics.revenue(
            start_date=_as_date(args.get("start_date")),
            end_date=_as_date(args.get("end_date")),
            category_slug=args.get("category_slug"),
            group_by=args.get("group_by") or "day",
            comparison=args.get("comparison") or "none",
        )
        return (
            {
                "total_paise": report.total_paise,
                "order_count": report.order_count,
                "group_by": report.group_by,
                "category_slug": report.category_slug,
                "start_date": report.start_date.isoformat(),
                "end_date": report.end_date.isoformat(),
                "previous_total_paise": report.previous_total_paise,
                "change_pct": report.change_pct,
                "buckets": [
                    {"label": b.label, "revenue_paise": b.revenue_paise, "orders": b.orders}
                    for b in report.buckets
                ],
            },
            False,
            None,
        )

    def _t_query_product_sales(self, args: dict):
        rows = self._analytics.product_sales(
            start_date=_as_date(args.get("start_date")),
            end_date=_as_date(args.get("end_date")),
            category_slug=args.get("category_slug"),
            sort=args.get("sort") or "quantity_desc",
            limit=int(args.get("limit") or 10),
        )
        return (
            {"products": [
                {"name": r.name, "category_slug": r.category_slug,
                 "quantity": r.quantity, "revenue_paise": r.revenue_paise}
                for r in rows
            ]},
            False,
            None,
        )

    def _t_query_orders(self, args: dict):
        orders = self._orders.list(status=args.get("status"), limit=int(args.get("limit") or 10))
        return (
            {"orders": [
                {"order_number": o.order_number, "customer_name": o.customer_name,
                 "status": o.status, "total_paise": o.total_paise,
                 "placed_at": o.placed_at.isoformat(), "items": len(o.items)}
                for o in orders
            ]},
            False,
            None,
        )

    # ── audit log tools ──────────────────────────────────────────────────

    def _t_get_agent_action_history(self, args: dict):
        limit = int(args.get("limit") or 10)
        rows = self._db.scalars(
            select(AgentAction)
            .where(AgentAction.seller_id == self._seller_id)
            .order_by(AgentAction.created_at.desc())
            .limit(limit)
        )
        return {"actions": [
            {"id": str(a.id), "tool": a.tool, "status": a.status,
             "at": a.created_at.isoformat(), "undoable": a.undoable and a.undone_at is None}
            for a in rows
        ]}, False, None

    def _t_undo_action(self, args: dict):
        action = self._db.scalars(
            select(AgentAction)
            .where(
                AgentAction.seller_id == self._seller_id,
                AgentAction.undoable.is_(True),
                AgentAction.undone_at.is_(None),
            )
            .order_by(AgentAction.created_at.desc())
            .limit(1)
        ).one_or_none()
        if action is None or not action.inverse:
            raise ToolError("there is nothing to undo")

        inverse = action.inverse
        tool, inv_args = inverse["tool"], inverse["args"]

        if tool == "delete_product":
            self._t_delete_product(inv_args)
        elif tool == "_set_status":
            product = self._products.get(uuid.UUID(inv_args["product_id"]))
            if product:
                product.status = inv_args["status"]
                self._db.commit()
        elif tool == "_restore_product":
            product = self._products.get(uuid.UUID(inv_args["product_id"]))
            if product:
                fields = inv_args["fields"]
                product.name = fields["name"]
                product.price_paise = fields["price_paise"]
                product.category_slug = fields["category_slug"]
                product.description = fields["description"]
                product.stock_quantity = fields["stock_quantity"]
                self._db.commit()
        else:
            raise ToolError(f"cannot reverse {tool}")

        action.undone_at = func_now(self._db)
        self._db.commit()
        return {"undone": {"id": str(action.id), "tool": action.tool}}, False, None


def _as_date(value: Any) -> date:
    """Dates arrive as ISO strings from the model. A missing or unparseable one
    is the caller's mistake, surfaced rather than silently defaulted."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError) as exc:
        raise ToolError(f"could not read {value!r} as a date (expected YYYY-MM-DD)") from exc


def func_now(db: Session):
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
