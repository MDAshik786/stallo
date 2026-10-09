import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_seller_id
from app.db import get_db
from app.repositories.analytics import AnalyticsRepository
from app.repositories.orders import OrderRepository

router = APIRouter(tags=["orders"])


class OrderItemOut(BaseModel):
    name: str
    quantity: int
    unit_price_paise: int
    line_total_paise: int


class OrderOut(BaseModel):
    id: uuid.UUID
    order_number: str
    customer_name: str
    status: str
    total_paise: int
    placed_at: str
    items: list[OrderItemOut]


class OrderPage(BaseModel):
    orders: list[OrderOut]
    total: int


@router.get("/orders", response_model=OrderPage)
def list_orders(
    status: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    seller_id: uuid.UUID = Depends(get_seller_id),
) -> OrderPage:
    repo = OrderRepository(db, seller_id)
    rows = repo.list(status=status, limit=limit, offset=offset)
    return OrderPage(
        total=repo.count(status=status),
        orders=[
            OrderOut(
                id=o.id, order_number=o.order_number, customer_name=o.customer_name,
                status=o.status, total_paise=o.total_paise,
                placed_at=o.placed_at.isoformat(),
                items=[
                    OrderItemOut(name=i.name, quantity=i.quantity,
                                 unit_price_paise=i.unit_price_paise,
                                 line_total_paise=i.line_total_paise)
                    for i in o.items
                ],
            )
            for o in rows
        ],
    )


class BucketOut(BaseModel):
    label: str
    revenue_paise: int
    orders: int


class RevenueOut(BaseModel):
    start_date: date
    end_date: date
    group_by: str
    category_slug: str | None
    total_paise: int
    order_count: int
    previous_total_paise: int | None
    change_pct: float | None
    buckets: list[BucketOut]


class ProductSalesOut(BaseModel):
    name: str
    category_slug: str | None
    quantity: int
    revenue_paise: int


@router.get("/analytics/revenue", response_model=RevenueOut)
def revenue(
    days: int = Query(default=180, ge=1, le=730),
    group_by: str = Query(default="month", pattern="^(day|week|month|category)$"),
    category_slug: str | None = Query(default=None),
    comparison: str = Query(default="previous_period",
                            pattern="^(none|previous_period|previous_year)$"),
    db: Session = Depends(get_db),
    seller_id: uuid.UUID = Depends(get_seller_id),
) -> RevenueOut:
    today = date.today()
    report = AnalyticsRepository(db, seller_id).revenue(
        start_date=today - timedelta(days=days - 1), end_date=today,
        category_slug=category_slug, group_by=group_by, comparison=comparison,
    )
    return RevenueOut(
        start_date=report.start_date, end_date=report.end_date,
        group_by=report.group_by, category_slug=report.category_slug,
        total_paise=report.total_paise, order_count=report.order_count,
        previous_total_paise=report.previous_total_paise, change_pct=report.change_pct,
        buckets=[BucketOut(label=b.label, revenue_paise=b.revenue_paise, orders=b.orders)
                 for b in report.buckets],
    )


@router.get("/analytics/products", response_model=list[ProductSalesOut])
def product_sales(
    days: int = Query(default=180, ge=1, le=730),
    sort: str = Query(default="revenue_desc",
                      pattern="^(quantity_desc|quantity_asc|revenue_desc|revenue_asc)$"),
    limit: int = Query(default=8, ge=1, le=50),
    db: Session = Depends(get_db),
    seller_id: uuid.UUID = Depends(get_seller_id),
) -> list[ProductSalesOut]:
    today = date.today()
    rows = AnalyticsRepository(db, seller_id).product_sales(
        start_date=today - timedelta(days=days - 1), end_date=today,
        sort=sort, limit=limit,
    )
    return [ProductSalesOut(name=r.name, category_slug=r.category_slug,
                            quantity=r.quantity, revenue_paise=r.revenue_paise)
            for r in rows]
