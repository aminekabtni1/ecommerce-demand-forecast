import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FORECAST_DIR = DATA_DIR / "forecasts"

FAKESTORE_API_BASE = os.getenv("FAKESTORE_API_BASE", "https://fakestoreapi.com")
DUCKDB_PATH = os.getenv("DUCKDB_PATH", str(DATA_DIR / "warehouse.duckdb"))
FORECAST_HORIZON_DAYS = int(os.getenv("FORECAST_HORIZON_DAYS", "30"))
ANOMALY_Z_THRESHOLD = float(os.getenv("ANOMALY_Z_THRESHOLD", "2.5"))

# Ensure dirs exist
for d in [RAW_DIR, PROCESSED_DIR, FORECAST_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)
