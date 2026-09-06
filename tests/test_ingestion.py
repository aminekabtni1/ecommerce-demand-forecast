import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from ingestion.synthesize import synthesize_daily_sales
from ingestion.fetch_fakestore import FALLBACK_PRODUCTS

def test_synthesize_shape():
    products = FALLBACK_PRODUCTS[:3]
    rows = synthesize_daily_sales(products, days=10, seed=0)
    assert len(rows) == 30  # 10 * 3
    assert all("quantity" in r and "revenue" in r for r in rows)
    assert all(r["quantity"] >= 0 for r in rows)

def test_synthesize_deterministic():
    products = FALLBACK_PRODUCTS[:2]
    a = synthesize_daily_sales(products, days=5, seed=42)
    b = synthesize_daily_sales(products, days=5, seed=42)
    assert a == b

def test_fetch_fallback_on_failure(tmp_path, monkeypatch):
    # Simulate requests.get failure -> fallback used
    from ingestion import fetch_fakestore
    import ingestion.config as cfg
    import ingestion.fetch_fakestore as ff
    monkeypatch.setattr(cfg, "RAW_DIR", tmp_path)
    monkeypatch.setattr(ff, "RAW_DIR", tmp_path)
    with patch("ingestion.fetch_fakestore._get_with_retries", side_effect=Exception("offline")):
        products = fetch_fakestore.fetch_products()
        assert len(products) == len(FALLBACK_PRODUCTS)
        paths = fetch_fakestore.run_fetch_and_synthesize(days=5)
        assert Path(paths["products"]).exists()
        assert Path(paths["sales"]).exists()
        sales = json.loads(Path(paths["sales"]).read_text())
        assert len(sales) == 5 * len(products)

def test_load_duckdb(tmp_path, monkeypatch):
    import ingestion.config as cfg
    import ingestion.fetch_fakestore as ff
    from ingestion.load_duckdb import load_to_duckdb
    monkeypatch.setattr(cfg, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(ff, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    duck_path = tmp_path / "warehouse.duckdb"
    monkeypatch.setattr(cfg, "DUCKDB_PATH", str(duck_path))
    # need to also patch load_duckdb's RAW_DIR reference (imported)
    import ingestion.load_duckdb as ld
    monkeypatch.setattr(ld, "RAW_DIR", tmp_path / "raw")
    (tmp_path / "raw").mkdir(parents=True, exist_ok=True)
    # use ff.run_fetch_and_synthesize so it respects patched RAW_DIR
    ff.run_fetch_and_synthesize(days=7)
    counts = load_to_duckdb(duckdb_path=str(duck_path))
    assert counts["products"] > 0
    assert counts["daily_sales"] == 7 * counts["products"]
