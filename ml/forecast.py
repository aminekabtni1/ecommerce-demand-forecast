"""
Forecasting: Holt-Winters Exponential Smoothing per product/category.
Explainable, interview-friendly. Falls back to naive if short history.
Outputs forecast + 95% CI.
"""
from __future__ import annotations
import warnings
from typing import Tuple
import pandas as pd
import numpy as np

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
except ImportError:
    ExponentialSmoothing = None  # fallback handled

def _fit_holt_winters(series: pd.Series, horizon: int = 30) -> Tuple[np.ndarray, float]:
    """Fit HW and return (forecast array, residual_std)."""
    if ExponentialSmoothing is None:
        raise ImportError("statsmodels not available")
    n = len(series)
    # heuristics
    if n < 14:
        raise ValueError("too short for HW")
    # Seasonal period 7 (weekly). Use additive trend+seasonal.
    # For small n, damped_trend helps stability.
    model = ExponentialSmoothing(
        series,
        trend="add",
        seasonal="add",
        seasonal_periods=7,
        initialization_method="estimated",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = model.fit(optimized=True, use_brute=True)
    fc = fit.forecast(horizon)
    resid = fit.resid.dropna()
    resid_std = float(resid.std()) if len(resid) > 2 else float(series.std() * 0.5 + 1.0)
    if not np.isfinite(resid_std) or resid_std < 0.5:
        resid_std = max(0.8, float(series.std() * 0.4))
    return fc.values, resid_std

def _naive_forecast(series: pd.Series, horizon: int) -> Tuple[np.ndarray, float]:
    """Seasonal naive (repeat last 7) or rolling mean fallback."""
    n = len(series)
    if n >= 7:
        last_week = series.iloc[-7:].values
        reps = int(np.ceil(horizon / 7))
        fc = np.tile(last_week, reps)[:horizon]
    elif n >= 1:
        fc = np.full(horizon, series.mean())
    else:
        fc = np.zeros(horizon)
    # residual std approx
    resid_std = float(series.std()) if n > 2 else 1.5
    if not np.isfinite(resid_std) or resid_std < 0.5:
        resid_std = 1.0
    return fc.astype(float), resid_std

def forecast_series(series: pd.Series, horizon: int = 30, alpha: float = 1.96) -> pd.DataFrame:
    """
    Forecast a single time series (indexed by date, values = quantity).
    Returns DataFrame with columns: forecast, lower, upper
    """
    series = series.sort_index().astype(float)
    # ensure non-negative
    series = series.clip(lower=0)

    try:
        if len(series) >= 14 and ExponentialSmoothing is not None:
            fc_vals, resid_std = _fit_holt_winters(series, horizon)
        else:
            raise ValueError("fallback")
    except Exception:
        fc_vals, resid_std = _naive_forecast(series, horizon)

    # Clip negatives, smooth
    fc_vals = np.maximum(fc_vals, 0)
    # confidence interval
    lower = np.maximum(fc_vals - alpha * resid_std, 0)
    upper = fc_vals + alpha * resid_std
    # future dates
    last_date = pd.to_datetime(series.index.max())
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
    df = pd.DataFrame({
        "date": future_dates,
        "forecast": fc_vals,
        "lower": lower,
        "upper": upper,
        "residual_std": resid_std,
    })
    return df

def forecast_for_all(
    df_daily: pd.DataFrame,
    horizon: int = 30,
    group_col: str = "product_id",
) -> pd.DataFrame:
    """
    df_daily: must have columns [date, group_col, quantity]
    Returns long forecast DataFrame with group_col + date + forecast/lower/upper
    """
    forecasts = []
    for key, grp in df_daily.groupby(group_col):
        grp = grp.sort_values("date")
        s = grp.set_index("date")["quantity"]
        # ensure daily frequency fill missing 0
        idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
        s = s.reindex(idx, fill_value=0)
        s.index.name = "date"
        df_fc = forecast_series(s, horizon=horizon)
        df_fc[group_col] = key
        # add category if available
        if "category" in grp.columns:
            df_fc["category"] = grp["category"].iloc[0]
        if "product_name" in grp.columns:
            df_fc["product_name"] = grp["product_name"].iloc[0]
        forecasts.append(df_fc)
    if not forecasts:
        return pd.DataFrame(columns=["date","forecast","lower","upper",group_col])
    out = pd.concat(forecasts, ignore_index=True)
    return out
