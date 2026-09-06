"""
Anomaly detection: z-score on rolling stats and forecast residuals.
Flags |z| > threshold (default 2.5).
"""

from __future__ import annotations
import pandas as pd
import numpy as np

def detect_anomalies_rolling(
    df: pd.DataFrame,
    z_threshold: float = 2.5,
    window: int = 14,
) -> pd.DataFrame:
    """
    df: columns [date, product_id, quantity, category?]
    Returns df with anomaly flag and z_score.
    """
    out_frames = []
    for pid, grp in df.groupby("product_id"):
        grp = grp.sort_values("date").copy()
        # rolling stats (shift 1 to avoid leakage)
        grp["rolling_mean"] = grp["quantity"].shift(1).rolling(window, min_periods=7).mean()
        grp["rolling_std"] = grp["quantity"].shift(1).rolling(window, min_periods=7).std()
        # fill std NaN with expanding std or global
        global_std = grp["quantity"].std()
        if not np.isfinite(global_std) or global_std == 0:
            global_std = 1.0
        grp["rolling_std"] = grp["rolling_std"].fillna(global_std)
        grp["rolling_std"] = grp["rolling_std"].clip(lower=0.8)
        grp["z_score"] = (grp["quantity"] - grp["rolling_mean"]) / grp["rolling_std"]
        grp["z_score"] = grp["z_score"].fillna(0)
        grp["is_anomaly"] = grp["z_score"].abs() > z_threshold
        grp["severity"] = pd.cut(
            grp["z_score"].abs(),
            bins=[0, z_threshold, 3.5, float("inf")],
            labels=["none", "medium", "high"],
            include_lowest=True,
        ).astype(str)
        # map none to not anomaly
        grp.loc[~grp["is_anomaly"], "severity"] = "none"
        out_frames.append(grp)
    if not out_frames:
        return pd.DataFrame()
    result = pd.concat(out_frames, ignore_index=True)
    return result

def detect_anomalies_forecast_residual(
    df_history: pd.DataFrame,
    df_forecast: pd.DataFrame,
    z_threshold: float = 2.5,
) -> pd.DataFrame:
    """
    Alternative: join history to forecast for overlapping period and flag residuals.
    For now we use rolling method; this is placeholder for forecast-residual method.
    """
    # Not needed for MVP: rolling already covers it. Kept for interview explanation.
    return detect_anomalies_rolling(df_history, z_threshold=z_threshold)
