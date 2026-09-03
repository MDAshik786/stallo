import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


class ProductRepository:
    """Every query is scoped to one seller.

    seller_id is a constructor argument, not a method argument, so there is no
    call site where it can be forgotten. Nothing above this layer — service,
    route, or agent tool — can widen the scope.
    """

    def __init__(self, session: Session, seller_id: uuid.UUID) -> None:
        self._session = session
        self._seller_id = seller_id

    def list(self, *, status: str | None = None, limit: int = 20) -> list[Product]:
        stmt = select(Product).where(Product.seller_id == self._seller_id)
        if status:
            stmt = stmt.where(Product.status == status)
        stmt = stmt.order_by(Product.created_at.desc()).limit(limit)
        return list(self._session.scalars(stmt))

    def get(self, product_id: uuid.UUID) -> Product | None:
        stmt = select(Product).where(
            Product.id == product_id,
            Product.seller_id == self._seller_id,
        )
        return self._session.scalars(stmt).one_or_none()

    def create(self, product: Product) -> Product:
        product.seller_id = self._seller_id
        self._session.add(product)
        self._session.commit()
        self._session.refresh(product)
        return product
