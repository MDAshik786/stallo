"""
TODO(auth): DEV STUB — the API trusts the X-Seller-Id header without verifying
it, so any caller can claim any seller_id. Deployed as-is with seed data only.
Replace with a verified JWT before this holds real data.

The shape is what matters and will not change: seller_id is resolved here, from
the request's credentials, and injected downward. It is never a parameter a
caller — or later, an agent tool — gets to choose.
"""

import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories.products import ProductRepository
from app.services.products import ProductService


def get_seller_id(x_seller_id: str | None = Header(default=None)) -> uuid.UUID:
    if not x_seller_id:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "missing X-Seller-Id header (dev stub)"
        )
    try:
        return uuid.UUID(x_seller_id)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "X-Seller-Id is not a uuid")


def get_product_service(
    db: Session = Depends(get_db),
    seller_id: uuid.UUID = Depends(get_seller_id),
) -> ProductService:
    return ProductService(ProductRepository(db, seller_id))
