import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_product_service
from app.schemas import ProductCreate, ProductOut
from app.services.products import ProductService

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    product_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    service: ProductService = Depends(get_product_service),
) -> list[ProductOut]:
    return service.list(status=product_status, limit=limit)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: uuid.UUID,
    service: ProductService = Depends(get_product_service),
) -> ProductOut:
    product = service.get(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product not found")
    return product


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    service: ProductService = Depends(get_product_service),
) -> ProductOut:
    return service.create(data)
