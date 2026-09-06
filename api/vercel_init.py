# Vercel cold-start initializer: ensure DuckDB + marts exist in /tmp
# Called from api/main.py startup if DUCKDB_PATH is /tmp
import os
from pathlib import Path

def ensure_data():
    from ingestion.config import DUCKDB_PATH
    p = Path(DUCKDB_PATH)
    if p.exists() and p.stat().st_size > 1000:
        # check tables exist
        try:
            import duckdb
            con = duckdb.connect(str(p), read_only=True)
            has = con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='marts' AND table_name='mart_daily_sales'").fetchone()[0]
            con.close()
            if has:
                return
        except Exception:
            pass
    print("[vercel] initializing data in", p)
    try:
        from ingestion.fetch_fakestore import run_fetch_and_synthesize
        from ingestion.load_duckdb import load_to_duckdb
        run_fetch_and_synthesize(days=180)
        load_to_duckdb(duckdb_path=str(p))
        # Try dbt, fallback to pure-python marts if dbt not available on Vercel
        try:
            import subprocess, sys
            from pathlib import Path as _P
            root = _P(__file__).resolve().parents[1]
            # dbt may not be installed on Vercel build env; try anyway
            import shutil
            dbt_bin = shutil.which("dbt") or "dbt"
            res = subprocess.run([dbt_bin, "build", "--profiles-dir", "warehouse", "--project-dir", "warehouse"], cwd=str(root), capture_output=True, text=True, timeout=120)
            print("[vercel] dbt build", res.returncode)
            if res.returncode != 0:
                raise RuntimeError(res.stdout[-500:] + res.stderr[-500:])
        except Exception as e:
            print(f"[vercel] dbt failed, falling back to python marts: {e}")
            # Fallback: create marts via python (minimal)
            import duckdb, pandas as pd
            con = duckdb.connect(str(p))
            con.execute("CREATE SCHEMA IF NOT EXISTS staging")
            con.execute("CREATE SCHEMA IF NOT EXISTS intermediate")
            con.execute("CREATE SCHEMA IF NOT EXISTS marts")
            # Re-use mart logic from dbt but via SQL directly
            con.execute("""
                CREATE OR REPLACE VIEW staging.stg_products AS
                SELECT CAST(product_id AS INTEGER) as product_id, TRIM(title) as product_name, CAST(price AS DOUBLE) as price,
                       REPLACE(TRIM(category), '''', '') as category FROM warehouse.raw.products WHERE product_id IS NOT NULL;
            """)
            con.execute("""
                CREATE OR REPLACE VIEW staging.stg_sales AS
                SELECT CAST(date AS DATE) as sale_date, CAST(product_id AS INTEGER) as product_id,
                       REPLACE(TRIM(category), '''', '') as category, TRIM(title) as product_name,
                       CAST(price AS DOUBLE) as price, CAST(quantity AS INTEGER) as quantity, CAST(revenue AS DOUBLE) as revenue
                FROM warehouse.raw.daily_sales WHERE product_id IS NOT NULL;
            """)
            con.execute("CREATE OR REPLACE VIEW intermediate.int_daily_sales AS SELECT s.sale_date, s.product_id, s.category, s.product_name, s.price, s.quantity, s.revenue FROM staging.stg_sales s LEFT JOIN staging.stg_products p USING (product_id);")
            con.execute("""
                CREATE OR REPLACE TABLE marts.mart_daily_sales AS
                SELECT sale_date as date, product_id, category, product_name, price, quantity, revenue,
                       AVG(quantity) OVER (PARTITION BY product_id ORDER BY sale_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as rolling_7d_avg_qty,
                       AVG(quantity) OVER (PARTITION BY product_id ORDER BY sale_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as rolling_14d_avg_qty,
                       STDDEV_POP(quantity) OVER (PARTITION BY product_id ORDER BY sale_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as rolling_14d_std_qty
                FROM intermediate.int_daily_sales ORDER BY date, product_id;
            """)
            con.execute("CREATE OR REPLACE TABLE marts.mart_category_daily AS SELECT date, category, SUM(quantity) as total_quantity, SUM(revenue) as total_revenue FROM marts.mart_daily_sales GROUP BY date, category;")
            con.execute("CREATE OR REPLACE TABLE marts.mart_kpi_summary AS SELECT COUNT(DISTINCT date) as total_days, SUM(quantity) as total_quantity, SUM(revenue) as total_revenue, AVG(revenue) as avg_daily_revenue FROM marts.mart_daily_sales;")
            con.close()
        # Train forecasts
        from ml.train import train_and_save
        train_and_save()
        print("[vercel] init done")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"[vercel] init error: {e}")
