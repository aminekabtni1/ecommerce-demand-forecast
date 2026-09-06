"""Load raw JSON into DuckDB (raw schema). Idempotent: recreates raw tables."""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
import pandas as pd

from .config import RAW_DIR, DUCKDB_PATH, DATA_DIR

def _ensure_raw_files():
    if not (RAW_DIR / "products.json").exists():
        from .fetch_fakestore import run_fetch_and_synthesize
        run_fetch_and_synthesize()

def load_to_duckdb(duckdb_path: str | Path = DUCKDB_PATH) -> dict:
    _ensure_raw_files()
    duckdb_path = Path(duckdb_path)
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)

    products = json.loads((RAW_DIR / "products.json").read_text(encoding="utf-8"))
    carts = json.loads((RAW_DIR / "carts.json").read_text(encoding="utf-8"))
    sales = json.loads((RAW_DIR / "daily_sales.json").read_text(encoding="utf-8"))

    # Normalize products: flatten rating
    prod_rows = []
    for p in products:
        rating = p.get("rating") or {}
        prod_rows.append({
            "product_id": p.get("id"),
            "title": p.get("title"),
            "price": float(p.get("price", 0)),
            "category": p.get("category"),
            "description": p.get("description"),
            "image": p.get("image"),
            "rating_rate": float(rating.get("rate", 0)) if rating.get("rate") is not None else None,
            "rating_count": int(rating.get("count", 0)) if rating.get("count") is not None else None,
        })
    df_products = pd.DataFrame(prod_rows)

    # carts -> flatten products array into rows for traceability
    cart_rows = []
    for c in carts:
        cart_id = c.get("id")
        user_id = c.get("userId")
        date_str = c.get("date")
        for prod in c.get("products", []):
            cart_rows.append({
                "cart_id": cart_id,
                "user_id": user_id,
                "cart_date": date_str,
                "product_id": prod.get("productId"),
                "quantity": int(prod.get("quantity", 0)),
            })
    df_carts = pd.DataFrame(cart_rows) if cart_rows else pd.DataFrame(columns=["cart_id","user_id","cart_date","product_id","quantity"])

    df_sales = pd.DataFrame(sales)
    if not df_sales.empty:
        df_sales["date"] = pd.to_datetime(df_sales["date"]).dt.date

    con = duckdb.connect(str(duckdb_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        # products
        con.execute("DROP TABLE IF EXISTS raw.products")
        con.execute("CREATE TABLE raw.products AS SELECT * FROM df_products")
        # carts
        con.execute("DROP TABLE IF EXISTS raw.carts")
        if not df_carts.empty:
            con.execute("CREATE TABLE raw.carts AS SELECT * FROM df_carts")
        else:
            con.execute("CREATE TABLE raw.carts (cart_id INTEGER, user_id INTEGER, cart_date VARCHAR, product_id INTEGER, quantity INTEGER)")
        # daily_sales (synthesized)
        con.execute("DROP TABLE IF EXISTS raw.daily_sales")
        con.execute("CREATE TABLE raw.daily_sales AS SELECT * FROM df_sales")

        # Quick counts
        counts = {
            "products": con.execute("SELECT COUNT(*) FROM raw.products").fetchone()[0],
            "carts": con.execute("SELECT COUNT(*) FROM raw.carts").fetchone()[0],
            "daily_sales": con.execute("SELECT COUNT(*) FROM raw.daily_sales").fetchone()[0],
        }
        print(f"[load] DuckDB {duckdb_path} -> {counts}")
        return counts
    finally:
        con.close()

if __name__ == "__main__":
    load_to_duckdb()
