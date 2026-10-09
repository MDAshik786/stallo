"""Typed analytics queries.

The agent chooses *which* query and *what* filters. It never writes SQL, and
it never chooses whose data: seller_id is a constructor argument taken from
the authenticated session, so a prompt injection can at worst produce a
wrong-but-authorised query, never a cross-tenant read.

There is no free-text parameter here, and no sort or limit the caller can
smuggle in — the builder owns those.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Order, OrderItem

GroupBy = Literal["day", "week", "month", "category"]
Comparison = Literal["none", "previous_period", "previous_year"]
Sort = Literal["quantity_desc", "quantity_asc", "revenue_desc", "revenue_asc"]

# cancelled orders are not revenue
COUNTED = ("paid", "shipped", "delivered")


@dataclass
class Bucket:
    label: str
    revenue_paise: int
    orders: int


@dataclass
class RevenueReport:
    start_date: date
    end_date: date
    group_by: GroupBy
    category_slug: str | None
    total_paise: int
    order_count: int
    buckets: list[Bucket]
    comparison: str
    previous_total_paise: int | None = None
    change_pct: float | None = None


@dataclass
class ProductSalesRow:
    name: str
    category_slug: str | None
    quantity: int
    revenue_paise: int


class AnalyticsRepository:
    def __init__(self, session: Session, seller_id: uuid.UUID) -> None:
        self._session = session
        self._seller_id = seller_id

    # ── scoping ──────────────────────────────────────────────────────────

    def _scoped(self, stmt: Select, start: date, end: date) -> Select:
        """Every analytics query goes through here. Tenant and status filters
        are applied in one place so no new report can forget them."""
        return stmt.where(
            Order.seller_id == self._seller_id,
            Order.status.in_(COUNTED),
            func.date(Order.placed_at) >= start,
            func.date(Order.placed_at) <= end,
        )

    # ── revenue ──────────────────────────────────────────────────────────

    def _totals(self, start: date, end: date, category_slug: str | None) -> tuple[int, int]:
        if category_slug:
            stmt = self._scoped(
                select(
                    func.coalesce(func.sum(OrderItem.line_total_paise), 0),
                    func.count(func.distinct(Order.id)),
                ).select_from(Order).join(OrderItem, OrderItem.order_id == Order.id),
                start, end,
            ).where(OrderItem.category_slug == category_slug)
        else:
            stmt = self._scoped(
                select(func.coalesce(func.sum(Order.total_paise), 0), func.count(Order.id)),
                start, end,
            )
        total, count = self._session.execute(stmt).one()
        return int(total or 0), int(count or 0)

    def revenue(
        self,
        start_date: date,
        end_date: date,
        category_slug: str | None = None,
        group_by: GroupBy = "day",
        comparison: Comparison = "none",
    ) -> RevenueReport:
        total, order_count = self._totals(start_date, end_date, category_slug)

        if group_by == "category":
            stmt = self._scoped(
                select(
                    func.coalesce(OrderItem.category_slug, "uncategorised"),
                    func.sum(OrderItem.line_total_paise),
                    func.count(func.distinct(Order.id)),
                ).select_from(Order).join(OrderItem, OrderItem.order_id == Order.id),
                start_date, end_date,
            )
            if category_slug:
                stmt = stmt.where(OrderItem.category_slug == category_slug)
            rows = self._session.execute(
                stmt.group_by(OrderItem.category_slug).order_by(
                    func.sum(OrderItem.line_total_paise).desc()
                )
            ).all()
            buckets = [Bucket(str(a), int(b or 0), int(c or 0)) for a, b, c in rows]
        else:
            period = func.date_trunc(group_by, Order.placed_at)
            if category_slug:
                stmt = self._scoped(
                    select(period, func.sum(OrderItem.line_total_paise),
                           func.count(func.distinct(Order.id)))
                    .join(OrderItem, OrderItem.order_id == Order.id),
                    start_date, end_date,
                ).where(OrderItem.category_slug == category_slug)
            else:
                stmt = self._scoped(
                    select(period, func.sum(Order.total_paise), func.count(Order.id)),
                    start_date, end_date,
                )
            rows = self._session.execute(stmt.group_by(period).order_by(period)).all()
            fmt = "%Y-%m-%d" if group_by in ("day", "week") else "%Y-%m"
            buckets = [
                Bucket(a.strftime(fmt), int(b or 0), int(c or 0)) for a, b, c in rows
            ]

        report = RevenueReport(
            start_date=start_date, end_date=end_date, group_by=group_by,
            category_slug=category_slug, total_paise=total, order_count=order_count,
            buckets=buckets, comparison=comparison,
        )

        if comparison != "none":
            span = (end_date - start_date).days + 1
            if comparison == "previous_period":
                prev_end = start_date - timedelta(days=1)
                prev_start = prev_end - timedelta(days=span - 1)
            else:
                prev_start = start_date.replace(year=start_date.year - 1)
                prev_end = end_date.replace(year=end_date.year - 1)
            previous, _ = self._totals(prev_start, prev_end, category_slug)
            report.previous_total_paise = previous
            report.change_pct = (
                round((total - previous) / previous * 100, 1) if previous else None
            )

        return report

    # ── per-product ──────────────────────────────────────────────────────

    def product_sales(
        self,
        start_date: date,
        end_date: date,
        category_slug: str | None = None,
        sort: Sort = "quantity_desc",
        limit: int = 10,
    ) -> list[ProductSalesRow]:
        qty = func.sum(OrderItem.quantity)
        revenue = func.sum(OrderItem.line_total_paise)

        stmt = self._scoped(
            select(OrderItem.name, OrderItem.category_slug, qty, revenue)
            .select_from(Order)
            .join(OrderItem, OrderItem.order_id == Order.id),
            start_date, end_date,
        )
        if category_slug:
            stmt = stmt.where(OrderItem.category_slug == category_slug)

        # the caller picks from this map; it never supplies an ORDER BY
        order_by = {
            "quantity_desc": qty.desc(), "quantity_asc": qty.asc(),
            "revenue_desc": revenue.desc(), "revenue_asc": revenue.asc(),
        }[sort]

        rows = self._session.execute(
            stmt.group_by(OrderItem.name, OrderItem.category_slug)
            .order_by(order_by)
            .limit(max(1, min(limit, 50)))
        ).all()
        return [ProductSalesRow(a, b, int(c or 0), int(d or 0)) for a, b, c, d in rows]
