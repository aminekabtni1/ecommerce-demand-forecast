from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import pandas as pd
from pathlib import Path

from api.db import query_df, resolve_mart_table
from ingestion.config import DUCKDB_PATH, FORECAST_DIR

# Vercel: ensure data exists on cold start ( /tmp is writable, repo is read-only )
try:
    from pathlib import Path as _P
    if str(DUCKDB_PATH).startswith("/tmp") and not _P(DUCKDB_PATH).exists():
        from api.vercel_init import ensure_data
        ensure_data()
except Exception as _e:
    print(f"[startup] vercel init skipped: {_e}")

app = FastAPI(
    title="E-Commerce Demand Forecasting API",
    version="0.1.0",
    description="KPIs, trends, forecasts, anomalies from DuckDB marts",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    p = Path(DUCKDB_PATH)
    exists = p.exists()
    info = {"status": "ok", "duckdb_exists": exists, "duckdb_path": str(DUCKDB_PATH)}
    if exists:
        try:
            for tbl in ["mart_daily_sales", "mart_category_daily", "forecast_product", "anomalies"]:
                t = resolve_mart_table(tbl)
                try:
                    cnt = query_df(f"SELECT COUNT(*) as c FROM {t}").iloc[0]["c"]
                    info[t] = int(cnt)
                except Exception:
                    info[t] = "missing"
        except Exception as e:
            info["error"] = str(e)
    return info

@app.get("/api/kpis")
def kpis(days: int = Query(30, ge=1, le=365)):
    tbl = resolve_mart_table("mart_daily_sales")
    kpi_tbl = resolve_mart_table("mart_kpi_summary")
    # recent kpis computed on the fly for dynamic days param
    sql = f"""
        SELECT
            COUNT(DISTINCT date) as total_days,
            SUM(quantity) as total_quantity,
            SUM(revenue) as total_revenue,
            AVG(revenue) as avg_daily_revenue
        FROM {tbl}
        WHERE date >= (SELECT MAX(date) - INTERVAL {days} DAY FROM {tbl})
    """
    try:
        df = query_df(sql)
        row = df.iloc[0]
        # top category
        cat_sql = f"""
            SELECT category, SUM(revenue) as rev FROM {tbl}
            WHERE date >= (SELECT MAX(date) - INTERVAL {days} DAY FROM {tbl})
            GROUP BY category ORDER BY rev DESC LIMIT 1
        """
        cat_df = query_df(cat_sql)
        top_cat = cat_df.iloc[0]["category"] if not cat_df.empty else None
        top_rev = float(cat_df.iloc[0]["rev"]) if not cat_df.empty else None
        return {
            "total_days": int(row["total_days"] or 0),
            "total_quantity": int(row["total_quantity"] or 0),
            "total_revenue": float(row["total_revenue"] or 0),
            "avg_daily_revenue": float(row["avg_daily_revenue"] or 0),
            "top_category_by_revenue": top_cat,
            "top_category_revenue": top_rev,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
def products():
    tbl = resolve_mart_table("mart_daily_sales")
    # distinct products with latest name/category/price
    sql = f"""
        SELECT DISTINCT product_id, product_name, category, price
        FROM {tbl}
        ORDER BY product_id
    """
    try:
        df = query_df(sql)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
def categories():
    tbl = resolve_mart_table("mart_daily_sales")
    df = query_df(f"SELECT DISTINCT category FROM {tbl} ORDER BY category")
    return df["category"].tolist()

@app.get("/api/sales/trends")
def sales_trends(
    days: int = Query(90, ge=7, le=365),
    category: Optional[str] = None,
    product_id: Optional[int] = None,
    group_by: str = Query("day", pattern="^(day|category)$"),
):
    tbl = resolve_mart_table("mart_daily_sales")
    tbl_cat = resolve_mart_table("mart_category_daily")
    if group_by == "category" or category:
        # daily totals, optionally filtered
        where = []
        if category:
            where.append(f"category = '{category}'")
        if product_id:
            where.append(f"product_id = {int(product_id)}")
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        # date filter
        date_where = f"date >= (SELECT MAX(date) - INTERVAL {days} DAY FROM {tbl})"
        if where_sql:
            where_sql += f" AND {date_where}"
        else:
            where_sql = f"WHERE {date_where}"
        sql = f"""
            SELECT date::VARCHAR as date, SUM(quantity) as total_quantity, SUM(revenue) as total_revenue
            FROM {tbl}
            {where_sql}
            GROUP BY date ORDER BY date
        """
    else:
        sql = f"""
            SELECT date::VARCHAR as date, SUM(quantity) as total_quantity, SUM(revenue) as total_revenue
            FROM {tbl}
            WHERE date >= (SELECT MAX(date) - INTERVAL {days} DAY FROM {tbl})
            GROUP BY date ORDER BY date
        """
    try:
        df = query_df(sql)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/forecast")
def forecast(
    product_id: Optional[int] = None,
    category: Optional[str] = None,
    horizon: int = Query(30, ge=7, le=60),
):
    """
    If product_id given -> product forecast with history.
    Else if category given -> category forecast.
    Else -> all category forecasts aggregated.
    """
    try:
        if product_id is not None:
            tbl_fc = resolve_mart_table("forecast_product")
            tbl_hist = resolve_mart_table("mart_daily_sales")
            # forecast
            df_fc = query_df(f"SELECT date::VARCHAR as date, forecast, lower, upper, product_id, category FROM {tbl_fc} WHERE product_id={int(product_id)} ORDER BY date")
            # history last 90 days
            df_hist = query_df(f"""
                SELECT date::VARCHAR as date, quantity, revenue, rolling_7d_avg_qty
                FROM {tbl_hist} WHERE product_id={int(product_id)} ORDER BY date DESC LIMIT 90
            """)
            df_hist = df_hist.sort_values("date")
            return {"forecast": df_fc.to_dict(orient="records"), "history": df_hist.to_dict(orient="records")}
        elif category is not None:
            tbl_fc = resolve_mart_table("forecast_category")
            tbl_hist = resolve_mart_table("mart_category_daily")
            safe_cat = category.replace("'", "''")
            df_fc = query_df(f"SELECT date::VARCHAR as date, forecast, lower, upper, category FROM {tbl_fc} WHERE category='{safe_cat}' ORDER BY date")
            df_hist = query_df(f"SELECT date::VARCHAR as date, total_quantity as quantity, total_revenue as revenue FROM {tbl_hist} WHERE category='{safe_cat}' ORDER BY date DESC LIMIT 90")
            df_hist = df_hist.sort_values("date")
            return {"forecast": df_fc.to_dict(orient="records"), "history": df_hist.to_dict(orient="records")}
        else:
            # all categories forecast
            tbl_fc = resolve_mart_table("forecast_category")
            df_fc = query_df(f"SELECT date::VARCHAR as date, forecast, lower, upper, category FROM {tbl_fc} ORDER BY category, date")
            return {"forecast": df_fc.to_dict(orient="records"), "history": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/forecast/category")
def forecast_category(category: str, horizon: int = 30):
    return forecast(category=category, horizon=horizon)

@app.get("/api/anomalies")
def anomalies(
    days: int = Query(30, ge=7, le=180),
    z_threshold: float = Query(2.5, ge=1.0, le=5.0),
    category: Optional[str] = None,
    product_id: Optional[int] = None,
):
    tbl = resolve_mart_table("anomalies")
    where = [f"date >= (SELECT MAX(date) - INTERVAL {days} DAY FROM {resolve_mart_table('mart_daily_sales')})"]
    if z_threshold:
        where.append(f"ABS(z_score) >= {float(z_threshold)}")
    if category:
        safe = category.replace("'", "''")
        where.append(f"category = '{safe}'")
    if product_id:
        where.append(f"product_id = {int(product_id)}")
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    sql = f"""
        SELECT date::VARCHAR as date, product_id, product_name, category, quantity, revenue, rolling_mean, rolling_std, z_score, severity
        FROM {tbl}
        {where_sql}
        ORDER BY ABS(z_score) DESC LIMIT 100
    """
    try:
        df = query_df(sql)
        return df.to_dict(orient="records")
    except Exception as e:
        # if table empty, return []
        if "does not exist" in str(e) or "not found" in str(e).lower():
            return []
        raise HTTPException(status_code=500, detail=str(e))

# Root for convenience
@app.get("/")
def root():
    return {"message": "E-Commerce Demand Forecast API", "docs": "/docs", "health": "/api/health"}

# Vercel handler (Mangum) — allows FastAPI on serverless
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None
