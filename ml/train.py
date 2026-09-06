"""
Train/refresh forecasts + anomalies and persist to DuckDB + parquet.
Executed by Prefect and on-demand.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import duckdb
import pandas as pd

from ingestion.config import DUCKDB_PATH, FORECAST_DIR, FORECAST_HORIZON_DAYS, ANOMALY_Z_THRESHOLD
from ml.forecast import forecast_for_all
from ml.anomaly import detect_anomalies_rolling

def load_marts(duckdb_path: str | Path = DUCKDB_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect(str(duckdb_path))
    try:
        # Use marts schema (dbt creates marts.mart_daily_sales etc. but also main.mart_daily_sales via profiles.yml schema=main)
        # Try both locations
        def _read(table: str) -> pd.DataFrame:
            for schema in ["marts", "main"]:
                try:
                    return con.execute(f"SELECT * FROM {schema}.{table}").df()
                except Exception:
                    continue
            raise RuntimeError(f"Table {table} not found in marts/main")
        df_daily = _read("mart_daily_sales")
        df_category = _read("mart_category_daily")
        return df_daily, df_category
    finally:
        con.close()

def train_and_save(
    horizon: int = FORECAST_HORIZON_DAYS,
    z_threshold: float = ANOMALY_Z_THRESHOLD,
    duckdb_path: str | Path = DUCKDB_PATH,
):
    df_daily, df_category = load_marts(duckdb_path)
    if df_daily.empty:
        print("[train] mart_daily_sales empty - run dbt first")
        return

    # Ensure date is datetime
    df_daily["date"] = pd.to_datetime(df_daily["date"])
    df_category["date"] = pd.to_datetime(df_category["date"])

    print(f"[train] loaded {len(df_daily)} daily rows, {df_daily['product_id'].nunique()} products")

    # Product forecasts
    df_fc_prod = forecast_for_all(df_daily, horizon=horizon, group_col="product_id")
    # Category forecasts: aggregate first
    df_cat_daily = df_daily.groupby(["date","category"], as_index=False).agg(quantity=("quantity","sum"))
    df_fc_cat = forecast_for_all(df_cat_daily, horizon=horizon, group_col="category")

    # Anomalies (rolling)
    df_anom = detect_anomalies_rolling(df_daily, z_threshold=z_threshold, window=14)
    df_anom_flags = df_anom[df_anom["is_anomaly"]].copy()

    # Persist to parquet for API fast load
    FORECAST_DIR.mkdir(parents=True, exist_ok=True)
    prod_path = FORECAST_DIR / "forecast_product.parquet"
    cat_path = FORECAST_DIR / "forecast_category.parquet"
    anom_path = FORECAST_DIR / "anomalies.parquet"
    # fallback to csv if parquet engine missing
    try:
        df_fc_prod.to_parquet(prod_path, index=False)
        df_fc_cat.to_parquet(cat_path, index=False)
        df_anom_flags.to_parquet(anom_path, index=False)
        print(f"[train] wrote parquet: {prod_path} ({len(df_fc_prod)}), {cat_path} ({len(df_fc_cat)}), {anom_path} ({len(df_anom_flags)})")
    except Exception as e:
        print(f"[train] parquet failed {e}, writing csv fallback")
        df_fc_prod.to_csv(str(prod_path).replace(".parquet",".csv"), index=False)
        df_fc_cat.to_csv(str(cat_path).replace(".parquet",".csv"), index=False)
        df_anom_flags.to_csv(str(anom_path).replace(".parquet",".csv"), index=False)

    # Also persist to DuckDB marts for SQL access
    con = duckdb.connect(str(duckdb_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS marts")
        # forecasts
        con.execute("DROP TABLE IF EXISTS marts.forecast_product")
        con.execute("CREATE TABLE marts.forecast_product AS SELECT * FROM df_fc_prod")
        con.execute("DROP TABLE IF EXISTS marts.forecast_category")
        con.execute("CREATE TABLE marts.forecast_category AS SELECT * FROM df_fc_cat")
        con.execute("DROP TABLE IF EXISTS marts.anomalies")
        if not df_anom_flags.empty:
            con.execute("CREATE TABLE marts.anomalies AS SELECT * FROM df_anom_flags")
        else:
            # create empty with schema
            con.execute("CREATE TABLE marts.anomalies (date DATE, product_id INTEGER, quantity INTEGER, category VARCHAR, rolling_mean DOUBLE, rolling_std DOUBLE, z_score DOUBLE, is_anomaly BOOLEAN, severity VARCHAR)")
        print(f"[train] DuckDB marts updated: forecast_product={len(df_fc_prod)}, anomalies={len(df_anom_flags)}")
    finally:
        con.close()

    # Print sample
    if not df_fc_prod.empty:
        print(df_fc_prod.head(3).to_string())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, default=FORECAST_HORIZON_DAYS)
    parser.add_argument("--z-threshold", type=float, default=ANOMALY_Z_THRESHOLD)
    args = parser.parse_args()
    train_and_save(horizon=args.horizon, z_threshold=args.z_threshold)
