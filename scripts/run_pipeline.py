"""One-shot pipeline runner without Prefect (for local dev / Docker startup)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ingestion.fetch_fakestore import run_fetch_and_synthesize
from ingestion.load_duckdb import load_to_duckdb
import subprocess

def main():
    print("== Step 1: Extract + Synthesize ==")
    run_fetch_and_synthesize(days=180)
    print("== Step 2: Load DuckDB ==")
    load_to_duckdb()
    print("== Step 3: dbt build ==")
    import shutil
    dbt_bin = shutil.which("dbt")
    if not dbt_bin:
        for c in [
            Path(sys.executable).parent / "Scripts" / "dbt.exe",
            Path.home() / "AppData" / "Roaming" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Scripts" / "dbt.exe",
        ]:
            if c.exists():
                dbt_bin = str(c)
                break
        else:
            dbt_bin = "dbt"
    print(f"Using dbt: {dbt_bin}")
    res = subprocess.run([dbt_bin, "build", "--profiles-dir", "warehouse", "--project-dir", "warehouse"], cwd=str(ROOT))
    if res.returncode != 0:
        print("dbt build failed")
        sys.exit(1)
    print("== Step 4: Train forecast + anomalies ==")
    from ml.train import train_and_save
    train_and_save()
    print("== Pipeline complete ==")

if __name__ == "__main__":
    main()
