import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    price_paise: int
    category_slug: str | None
    status: str
    stock_quantity: int
    created_at: datetime


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    price_paise: int = Field(gt=0, le=100_000_000)
    description: str | None = Field(default=None, max_length=2000)
    category_slug: str | None = Field(default=None, max_length=64)
    stock_quantity: int = Field(default=0, ge=0)
