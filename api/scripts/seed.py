"""Seed one demo seller and a few products. Idempotent — safe to re-run."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Product, Seller

DEMO_EMAIL = "demo@stallo.local"

PRODUCTS = [
    ("Rose Bouquet", 89900, "flowers", "12 fresh red roses, hand-tied.", "published"),
    ("Jasmine Garland", 35000, "flowers", "Two feet of fresh jasmine.", "published"),
    ("Chocolate Gift Box", 49900, "chocolates", "10 assorted chocolates.", "published"),
    ("Gerbera Bunch", 45000, "flowers", "Mixed gerberas, 10 stems.", "draft"),
    ("Money Plant", 29900, "plants", "In a ceramic pot.", "published"),
]


def main() -> None:
    with SessionLocal() as db:
        seller = db.scalars(select(Seller).where(Seller.email == DEMO_EMAIL)).one_or_none()
        if seller is None:
            seller = Seller(store_name="Demo Florist", email=DEMO_EMAIL)
            db.add(seller)
            db.commit()
            db.refresh(seller)
            print(f"created seller {seller.id}")
        else:
            print(f"seller exists {seller.id}")

        existing = {
            p.name for p in db.scalars(select(Product).where(Product.seller_id == seller.id))
        }
        added = 0
        for name, price, category, description, status in PRODUCTS:
            if name in existing:
                continue
            db.add(
                Product(
                    seller_id=seller.id,
                    name=name,
                    price_paise=price,
                    category_slug=category,
                    description=description,
                    status=status,
                    stock_quantity=10,
                )
            )
            added += 1
        db.commit()
        print(f"added {added} product(s)")
        print(f"\nSELLER_ID={seller.id}")


if __name__ == "__main__":
    main()
