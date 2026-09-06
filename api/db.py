import duckdb
import pandas as pd
from pathlib import Path
from ingestion.config import DUCKDB_PATH

def get_con(read_only: bool = True):
    return duckdb.connect(str(DUCKDB_PATH), read_only=read_only)

def query_df(sql: str, params=None) -> pd.DataFrame:
    con = get_con()
    try:
        return con.execute(sql, params or []).df()
    finally:
        con.close()

def table_exists(schema: str, table: str) -> bool:
    con = get_con()
    try:
        res = con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=? AND table_name=?",
            [schema, table]
        ).fetchone()[0]
        return res > 0
    finally:
        con.close()

def resolve_mart_table(name: str) -> str:
    """dbt with schema: marts may be in main or marts depending on DuckDB version."""
    for schema in ["marts", "main"]:
        if table_exists(schema, name):
            return f"{schema}.{name}"
    return f"marts.{name}"  # fallback
