"""Prefect flow: scrape -> load -> dbt -> forecast. Schedule daily 02:00 UTC, manual triggerable."""
from prefect import flow, task, get_run_logger
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

@task(retries=1, retry_delay_seconds=10, log_prints=True)
def extract():
    logger = get_run_logger()
    logger.info("Extract: Fake Store API + synthesize")
    from ingestion.fetch_fakestore import run_fetch_and_synthesize
    return run_fetch_and_synthesize(days=180)

@task(log_prints=True)
def load():
    logger = get_run_logger()
    logger.info("Load: raw -> DuckDB")
    from ingestion.load_duckdb import load_to_duckdb
    return load_to_duckdb()

@task(log_prints=True)
def dbt_run():
    logger = get_run_logger()
    logger.info("dbt build")
    import shutil
    dbt_bin = shutil.which("dbt")
    # On Windows, Scripts folder may not be on PATH
    if not dbt_bin:
        # Try common locations
        candidates = [
            Path(sys.executable).parent / "Scripts" / "dbt.exe",
            Path(sys.executable).parent / "dbt.exe",
            Path.home() / "AppData" / "Roaming" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Scripts" / "dbt.exe",
        ]
        for c in candidates:
            if c.exists():
                dbt_bin = str(c)
                break
    if not dbt_bin:
        dbt_bin = "dbt"
    logger.info(f"Using dbt binary: {dbt_bin}")
    result = subprocess.run(
        [dbt_bin, "build", "--profiles-dir", "warehouse", "--project-dir", "warehouse"],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        raise RuntimeError(f"dbt build failed with {result.returncode}")
    logger.info("dbt build succeeded")

@task(log_prints=True)
def train_forecast():
    logger = get_run_logger()
    logger.info("Train: forecast + anomalies")
    from ml.train import train_and_save
    train_and_save()
    logger.info("Train done")

@flow(name="ecommerce_pipeline", log_prints=True)
def ecommerce_pipeline():
    logger = get_run_logger()
    logger.info("Starting ecommerce_pipeline")
    extract()
    load()
    dbt_run()
    train_forecast()
    logger.info("Pipeline complete")

if __name__ == "__main__":
    ecommerce_pipeline()
