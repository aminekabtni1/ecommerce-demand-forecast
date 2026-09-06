"""Init DuckDB file alone (useful for testing)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.load_duckdb import load_to_duckdb
if __name__ == "__main__":
    print(load_to_duckdb())
