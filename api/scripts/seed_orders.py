"""Seed ~7 months of orders so analytics has something real to say.

Deterministic (fixed seed) and idempotent — safe to re-run.
"""

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Order, OrderItem, Product, Seller

DEMO_EMAIL = "demo@stallo.local"
NAMES = [
    "Priya S", "Arjun M", "Fatima K", "Rohit D", "Ananya R", "Vikram N",
    "Meera J", "Sanjay P", "Divya T", "Imran H", "Kavya L", "Nikhil B",
]
# flowers spike around Valentine's and the festive season
SEASONAL = {1: 0.8, 2: 1.9, 3: 0.9, 4: 0.8, 5: 0.9, 6: 0.8,
            7: 0.9, 8: 1.1, 9: 1.2, 10: 1.6, 11: 1.4, 12: 1.3}


def main() -> None:
    rng = random.Random(20260904)
    with SessionLocal() as db:
        seller = db.scalars(select(Seller).where(Seller.email == DEMO_EMAIL)).one_or_none()
        if seller is None:
            print("no demo seller — run scripts/seed.py first")
            return

        existing = db.scalars(
            select(Order).where(Order.seller_id == seller.id).limit(1)
        ).one_or_none()
        if existing is not None:
            print("orders already seeded")
            return

        products = list(db.scalars(select(Product).where(Product.seller_id == seller.id)))
        if not products:
            print("no products — run scripts/seed.py first")
            return

        now = datetime.now(timezone.utc)
        created = 0
        for days_back in range(210, 0, -1):
            placed = now - timedelta(days=days_back)
            weight = SEASONAL[placed.month]
            for _ in range(rng.choices([0, 1, 2, 3], weights=[34, 38, 20, 8])[0]):
                if rng.random() > weight / 1.9:
                    continue
                created += 1
                order = Order(
                    seller_id=seller.id,
                    order_number=f"ST-{placed:%y%m%d}-{created:04d}",
                    customer_name=rng.choice(NAMES),
                    status=rng.choices(
                        ["delivered", "shipped", "paid", "cancelled"],
                        weights=[70, 12, 13, 5],
                    )[0],
                    total_paise=0,
                    placed_at=placed.replace(
                        hour=rng.randint(8, 21), minute=rng.randint(0, 59)
                    ),
                )
                total = 0
                for product in rng.sample(products, rng.randint(1, min(3, len(products)))):
                    qty = rng.randint(1, 3)
                    line = product.price_paise * qty
                    total += line
                    order.items.append(OrderItem(
                        product_id=product.id, name=product.name,
                        category_slug=product.category_slug,
                        unit_price_paise=product.price_paise,
                        quantity=qty, line_total_paise=line,
                    ))
                order.total_paise = total
                db.add(order)

        db.commit()
        print(f"created {created} orders across ~7 months")


if __name__ == "__main__":
    main()
