from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class KPIData(BaseModel):
    total_days: int
    total_quantity: int
    total_revenue: float
    avg_daily_revenue: float
    top_category_by_revenue: Optional[str]
    top_category_revenue: Optional[float]

class TrendPoint(BaseModel):
    date: str
    total_quantity: int
    total_revenue: float
    category: Optional[str] = None

class ForecastPoint(BaseModel):
    date: str
    forecast: float
    lower: float
    upper: float
    product_id: Optional[int] = None
    category: Optional[str] = None

class AnomalyPoint(BaseModel):
    date: str
    product_id: int
    product_name: Optional[str]
    category: Optional[str]
    quantity: int
    rolling_mean: float
    rolling_std: float
    z_score: float
    severity: str
    revenue: Optional[float] = None

class ProductInfo(BaseModel):
    product_id: int
    product_name: str
    category: str
    price: float
    rating_rate: Optional[float]
