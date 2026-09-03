import uuid

from app.models import Product
from app.repositories.products import ProductRepository
from app.schemas import ProductCreate


class ProductService:
    def __init__(self, repo: ProductRepository) -> None:
        self._repo = repo

    def list(self, *, status: str | None = None, limit: int = 20) -> list[Product]:
        return self._repo.list(status=status, limit=limit)

    def get(self, product_id: uuid.UUID) -> Product | None:
        return self._repo.get(product_id)

    def create(self, data: ProductCreate) -> Product:
        return self._repo.create(Product(**data.model_dump()))
