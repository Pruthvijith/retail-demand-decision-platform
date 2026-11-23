"""Synthetic sales simulator, including occasional right-censoring by stockouts."""

import math
import random
from datetime import date, timedelta

from retail_decisions.warehouse import connect, load_product, load_sale


PRODUCTS = [
    ("sku_01", "grocery", 2, 18, 2.99),
    ("sku_02", "grocery", 3, 26, 3.49),
    ("sku_03", "home", 5, 9, 11.99),
    ("sku_04", "home", 4, 14, 8.49),
    ("sku_05", "personal_care", 3, 11, 6.99),
    ("sku_06", "personal_care", 5, 21, 4.99),
]


def populate(path: str, days: int = 180, stores: int = 3, seed: int = 7) -> dict:
    if days < 90 or stores < 1:
        raise ValueError("Use >=90 days and >=1 stores for meaningful backtesting")
    rng = random.Random(seed)
    start = date(2026, 1, 1)
    inserted = 0
    with connect(path) as db:
        for sku, category, lead, _, _ in PRODUCTS:
            load_product(db, sku, category, lead)
        for store in range(stores):
            for sku, _, _, base, price in PRODUCTS:
                for index in range(days):
                    day = start + timedelta(days=index)
                    planned_promo = int((index // 14) % 4 == 1 and (store + index) % 3 == 0)
                    weekend = 1.20 if day.weekday() in (5, 6) else 1.0
                    seasonality = 1.0 + 0.12 * math.sin(index * 2 * math.pi / 30)
                    expected = base * (1 + store * 0.15) * weekend * seasonality
                    expected *= 1.4 if planned_promo else 1
                    demand = max(0, round(expected + rng.gauss(0, math.sqrt(expected + 1))))
                    opening = max(demand + rng.randint(3, 35), 1)
                    if rng.random() < 0.025:
                        opening = rng.randint(1, max(1, demand))
                    sold = min(demand, opening)
                    # True latent demand exists in the simulator but is never written to the mart.
                    inserted += int(load_sale(
                        db, f"sales_{store}_{sku}_{index}", f"store_{store:02d}", sku,
                        day, sold, planned_promo, price * (0.9 if planned_promo else 1.0), opening))
    return {"rows_inserted": inserted, "seed": seed, "days": days,
            "stores": stores, "source": "seeded synthetic retail sales"}
