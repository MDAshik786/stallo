import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order


class OrderRepository:
    """seller_id is fixed at construction — same rule as every other repository."""

    def __init__(self, session: Session, seller_id: uuid.UUID) -> None:
        self._session = session
        self._seller_id = seller_id

    def list(self, *, status: str | None = None, limit: int = 25, offset: int = 0) -> list[Order]:
        stmt = select(Order).where(Order.seller_id == self._seller_id)
        if status:
            stmt = stmt.where(Order.status == status)
        return list(
            self._session.scalars(
                stmt.order_by(Order.placed_at.desc()).limit(limit).offset(offset)
            )
        )

    def count(self, *, status: str | None = None) -> int:
        stmt = select(func.count(Order.id)).where(Order.seller_id == self._seller_id)
        if status:
            stmt = stmt.where(Order.status == status)
        return int(self._session.scalar(stmt) or 0)

    def get(self, order_id: uuid.UUID) -> Order | None:
        return self._session.scalars(
            select(Order).where(Order.id == order_id, Order.seller_id == self._seller_id)
        ).one_or_none()
