"""
Synthesize daily sales history for each product.

Fake Store API gives products + carts but no time-series sales.
We generate 180 days of daily quantity & revenue per product with:
- base demand by category (electronics lower volume, higher price)
- linear trend (-0.02 to +0.03 per day)
- weekly seasonality (Sat/Sun lift)
- small monthly seasonality
- Gaussian noise + Poisson sampling for counts

Deterministic (seeded) so runs are reproducible and tests stable.
"""

from __future__ import annotations
import random
import math
from datetime import date, timedelta
from typing import List, Dict
import numpy as np

CATEGORY_BASE = {
    "electronics": 4.5,
    "jewelery": 2.2,
    "men's clothing": 6.0,
    "women's clothing": 6.5,
    # cleaned (apostrophe stripped in staging) – same base
    "mens clothing": 6.0,
    "womens clothing": 6.5,
}

WEEKLY_FACTOR = [0.85, 0.90, 0.95, 1.00, 1.05, 1.35, 1.40]  # Mon..Sun

def synthesize_daily_sales(
    products: List[Dict],
    days: int = 180,
    end_date: date | None = None,
    seed: int = 42,
) -> List[Dict]:
    rng = np.random.default_rng(seed)
    random.seed(seed)
    if end_date is None:
        end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    # Per-product trend slope
    trends = {p["id"]: rng.uniform(-0.015, 0.03) for p in products}

    rows: List[Dict] = []
    for i in range(days):
        cur = start_date + timedelta(days=i)
        weekday = cur.weekday()  # 0 Mon
        weekly = WEEKLY_FACTOR[weekday]
        # monthly wave (approx 30d period, small amplitude)
        monthly = 1 + 0.08 * math.sin(2 * math.pi * i / 30)

        for p in products:
            pid = p["id"]
            cat = p.get("category", "electronics")
            price = float(p.get("price", 20.0))
            base = CATEGORY_BASE.get(cat, 5.0)
            # slight product-specific multiplier
            prod_mult = 0.7 + (hash(str(pid)) % 60) / 100  # 0.7..1.3 deterministic
            trend_mult = 1 + trends[pid] * (i / 30)  # per month
            # mean lambda for Poisson
            lam = max(0.3, base * prod_mult * weekly * monthly * trend_mult)
            lam *= rng.uniform(0.85, 1.15)  # daily noise
            qty = int(rng.poisson(lam))
            # inject occasional spikes (1% days)
            if rng.random() < 0.015:
                qty = int(qty * rng.uniform(2.0, 3.5)) + 3
            if qty == 0 and rng.random() < 0.08:
                qty = 1
            revenue = round(qty * price, 2)
            rows.append({
                "date": cur.isoformat(),
                "product_id": pid,
                "category": cat,
                "title": p.get("title", ""),
                "price": price,
                "quantity": qty,
                "revenue": revenue,
            })
    return rows
