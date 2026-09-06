import pandas as pd
from ml.forecast import forecast_series, forecast_for_all
from ml.anomaly import detect_anomalies_rolling

def test_forecast_simple():
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    s = pd.Series([10 + i*0.1 + (i%7) for i in range(60)], index=idx)
    df = forecast_series(s, horizon=7)
    assert len(df) == 7
    assert all(df["forecast"] >= 0)
    assert all(df["lower"] <= df["forecast"])
    assert all(df["upper"] >= df["forecast"])

def test_forecast_fallback_short_series():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    s = pd.Series([5,6,5,7,6], index=idx)
    df = forecast_series(s, horizon=7)
    assert len(df) == 7

def test_forecast_for_all():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    rows = []
    for pid in [1,2]:
        for d in dates:
            rows.append({"date": d, "product_id": pid, "quantity": 10 + pid, "category": "electronics"})
    df = pd.DataFrame(rows)
    out = forecast_for_all(df, horizon=7, group_col="product_id")
    assert len(out) == 14  # 2*7
    assert set(out["product_id"].unique()) == {1,2}

def test_anomaly_detection():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    # normal around 10, one spike at day 15
    qty = [10]*30
    qty[15] = 50
    df = pd.DataFrame({"date": dates, "product_id": [1]*30, "quantity": qty, "category": ["electronics"]*30})
    out = detect_anomalies_rolling(df, z_threshold=2.5, window=14)
    assert "is_anomaly" in out.columns
    assert out["is_anomaly"].sum() >= 1  # spike flagged
    assert out.loc[15, "is_anomaly"] == True

def test_anomaly_no_false_on_stable():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    df = pd.DataFrame({"date": dates, "product_id": [1]*30, "quantity": [10]*30})
    out = detect_anomalies_rolling(df, z_threshold=2.5)
    # stable series should have 0 anomalies (std clipped)
    assert out["is_anomaly"].sum() == 0
