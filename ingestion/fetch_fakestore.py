"""Fetch products/carts from Fake Store API with retries + fallback."""
from __future__ import annotations
import json
import time
from pathlib import Path
from datetime import date
from typing import List, Dict
import requests

from .config import FAKESTORE_API_BASE, RAW_DIR
from .synthesize import synthesize_daily_sales

FALLBACK_PRODUCTS = [
    {"id": 1, "title": "Fjallraven Backpack", "price": 109.95, "category": "men's clothing", "description": "fallback", "image": "", "rating": {"rate": 3.9, "count": 120}},
    {"id": 2, "title": "Mens Casual T-Shirt", "price": 22.3, "category": "men's clothing", "description": "fallback", "image": "", "rating": {"rate": 4.1, "count": 259}},
    {"id": 3, "title": "Mens Cotton Jacket", "price": 55.99, "category": "men's clothing", "description": "fallback", "image": "", "rating": {"rate": 4.7, "count": 500}},
    {"id": 4, "title": "Mens Slim Fit", "price": 15.99, "category": "men's clothing", "description": "fallback", "image": "", "rating": {"rate": 2.1, "count": 430}},
    {"id": 5, "title": "Dragon Bracelet", "price": 695.0, "category": "jewelery", "description": "fallback", "image": "", "rating": {"rate": 4.6, "count": 400}},
    {"id": 6, "title": "Solid Gold Ring", "price": 168.0, "category": "jewelery", "description": "fallback", "image": "", "rating": {"rate": 3.9, "count": 70}},
    {"id": 9, "title": "WD 2TB External", "price": 64.0, "category": "electronics", "description": "fallback", "image": "", "rating": {"rate": 3.3, "count": 203}},
    {"id": 10, "title": "SanDisk SSD 1TB", "price": 109.0, "category": "electronics", "description": "fallback", "image": "", "rating": {"rate": 2.9, "count": 470}},
    {"id": 15, "title": "Women Snow Jacket", "price": 56.99, "category": "women's clothing", "description": "fallback", "image": "", "rating": {"rate": 2.6, "count": 235}},
    {"id": 16, "title": "Women Leather Jacket", "price": 29.95, "category": "women's clothing", "description": "fallback", "image": "", "rating": {"rate": 2.9, "count": 340}},
]

def _get_with_retries(url: str, retries: int = 3, timeout: int = 10):
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "portfolio-pipeline/1.0"})
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_exc = e
            wait = 1.5 ** attempt
            time.sleep(wait)
    raise last_exc

def fetch_products() -> List[Dict]:
    url = f"{FAKESTORE_API_BASE}/products"
    try:
        data = _get_with_retries(url)
        # basic validation
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError("empty products")
        return data
    except Exception as e:
        print(f"[fetch] products failed ({e}), using fallback ({len(FALLBACK_PRODUCTS)} items)")
        return FALLBACK_PRODUCTS

def fetch_carts() -> List[Dict]:
    url = f"{FAKESTORE_API_BASE}/carts"
    try:
        data = _get_with_retries(url)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"[fetch] carts failed ({e}), returning []")
        return []

def run_fetch_and_synthesize(days: int = 180) -> Dict[str, Path]:
    """Fetches, synthesizes daily sales, writes raw JSON, returns paths."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    products = fetch_products()
    carts = fetch_carts()

    products_path = RAW_DIR / "products.json"
    carts_path = RAW_DIR / "carts.json"
    products_path.write_text(json.dumps(products, indent=2), encoding="utf-8")
    carts_path.write_text(json.dumps(carts, indent=2), encoding="utf-8")
    print(f"[fetch] wrote {len(products)} products -> {products_path}")
    print(f"[fetch] wrote {len(carts)} carts -> {carts_path}")

    sales = synthesize_daily_sales(products, days=days, end_date=date.today(), seed=42)
    sales_path = RAW_DIR / "daily_sales.json"
    sales_path.write_text(json.dumps(sales, indent=2), encoding="utf-8")
    print(f"[synthesize] {len(sales)} daily_sale rows ({days} days x {len(products)} products) -> {sales_path}")

    return {"products": products_path, "carts": carts_path, "sales": sales_path}

if __name__ == "__main__":
    run_fetch_and_synthesize()
