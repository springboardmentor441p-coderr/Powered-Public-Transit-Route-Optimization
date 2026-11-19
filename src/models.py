"""
Shared feature schemas, metric helpers (MAE, RMSE, WAPE), and preprocessing pipeline builder.
Ensures identical preprocessing across training, evaluation, and FastAPI inference.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None

DEMAND_FEATURES = [
    "route",
    "day_of_week",
    "month",
    "is_weekend",
    "is_sunday_holiday_daytype",
    "rides_1_day_before",
    "rides_7_days_before",
    "rides_14_days_before",
    "rides_21_days_before",
    "rides_28_days_before",
    "rides_28_days_before_available",
    "available_same_weekday_observations",
    "past_four_same_weekdays_mean",
]

SERVICE_FEATURES = DEMAND_FEATURES + [
    "scheduled_trips",
    "scheduled_service_hours",
]

TARGET = "rides"

def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.maximum(0.0, np.asarray(y_pred, dtype=float))
    abs_err = np.abs(y_true - y_pred)
    mae = float(np.mean(abs_err))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    denom = float(np.sum(y_true))
    wape = round((float(np.sum(abs_err)) / denom) * 100.0, 2) if denom > 0 else None
    return {
        "rows": int(len(y_true)),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "wape_pct": wape,
    }

def build_regressor_pipeline(feature_cols: list[str], model_type: str) -> Pipeline:
    cat_cols = ["route"]
    num_cols = [c for c in feature_cols if c != "route"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
            ("num", StandardScaler(), num_cols),
        ]
    )

    if model_type == "ridge":
        est = Ridge(alpha=1.0, random_state=42)
    elif model_type == "random_forest":
        est = RandomForestRegressor(n_estimators=120, max_depth=14, random_state=42, n_jobs=-1)
    elif model_type == "xgboost":
        if XGBRegressor is None:
            raise ImportError("xgboost is not installed. Run `pip install xgboost` to enable the XGBoost regressor.")
        est = XGBRegressor(
            n_estimators=160,
            max_depth=6,
            learning_rate=0.06,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    return Pipeline([("prep", preprocessor), ("model", est)])
