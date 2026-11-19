import json
import os
import pickle
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

OUT_DIR = "data/processed/v1"
ARTIFACT_DIR = "artifacts/v1"

DEMAND_FEATURES = [
    "route", "day_of_week", "month", "is_weekend", "is_sunday_holiday_daytype",
    "rides_1_day_before", "rides_7_days_before", "rides_14_days_before",
    "rides_21_days_before", "rides_28_days_before",
    "available_same_weekday_observations", "past_four_same_weekdays_mean",
    "rides_28_days_before_available",
]
SERVICE_FEATURES = DEMAND_FEATURES + ["scheduled_trips", "scheduled_service_hours"]

def apply_option_2_policy(df: pd.DataFrame, require_schedule: bool = True) -> pd.DataFrame:
    out = df.copy()
    out["rides_28_days_before_available"] = out["rides_28_days_before"].notna().astype(int)

    donor_cols = ["rides_7_days_before", "rides_14_days_before", "rides_21_days_before"]
    donor_mean = out[donor_cols].mean(axis=1)
    out["rides_28_days_before"] = out["rides_28_days_before"].fillna(donor_mean)

    req_cols = [
        "rides_1_day_before", "rides_7_days_before", "rides_14_days_before",
        "rides_21_days_before", "rides_28_days_before", "past_four_same_weekdays_mean"
    ]
    if require_schedule:
        req_cols += ["scheduled_trips", "scheduled_service_hours"]

    out["is_eligible"] = out[req_cols].notna().all(axis=1)
    return out

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_pred = np.maximum(0.0, y_pred)
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    denom = float(np.sum(y_true))
    wape = float(np.sum(np.abs(y_true - y_pred)) / denom) if denom > 0 else None
    return {"mae": round(mae, 2), "rmse": round(rmse, 2), "wape": round(wape, 4) if wape is not None else None}

def build_pipeline(feature_cols: list[str], model_type: str = "rf") -> Pipeline:
    cat_cols = ["route"]
    num_cols = [c for c in feature_cols if c not in cat_cols]

    pre = ColumnTransformer(
        transformers=[
            ("route_ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
            ("num", StandardScaler(), num_cols),
        ]
    )
    regressor = (
        RandomForestRegressor(n_estimators=150, max_depth=14, min_samples_leaf=5, random_state=42, n_jobs=-1)
        if model_type == "rf"
        else Ridge(alpha=1.0)
    )
    return Pipeline([("preprocessor", pre), ("regressor", regressor)])

def run():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    df = pd.read_csv(os.path.join(OUT_DIR, "expanded_demand_service_features.csv"))
    df = apply_option_2_policy(df, require_schedule=True)

    train_df = df[(df["split"] == "train") & (df["is_eligible"])].copy()
    val_df = df[(df["split"] == "validation") & (df["is_eligible"])].copy()
    test_df = df[(df["split"] == "test") & (df["is_eligible"])].copy()

    # Fit Service-Aware Random Forest (Primary) and Demand-Only Fallback
    service_pipe = build_pipeline(SERVICE_FEATURES, model_type="rf")
    service_pipe.fit(train_df[SERVICE_FEATURES], train_df["rides"])

    # Also train a demand-only fallback on the longer 2024-2026 dataset
    demand_df = pd.read_csv(os.path.join(OUT_DIR, "daily_forecasting_features.csv"))
    demand_df = apply_option_2_policy(demand_df, require_schedule=False)
    d_train = demand_df[(demand_df["split"] == "train") & (demand_df["is_eligible"])]
    demand_pipe = build_pipeline(DEMAND_FEATURES, model_type="rf")
    demand_pipe.fit(d_train[DEMAND_FEATURES], d_train["rides"])

    # Evaluate on Test Split (Frozen)
    eval_report = {
        "service_rf_test": compute_metrics(test_df["rides"].values, service_pipe.predict(test_df[SERVICE_FEATURES])),
        "seasonal_baseline_test": compute_metrics(test_df["rides"].values, test_df["past_four_same_weekdays_mean"].values),
        "last_week_baseline_test": compute_metrics(test_df["rides"].values, test_df["rides_7_days_before"].values),
        "coverage": {
            "test_total_rows": int((df["split"] == "test").sum()),
            "test_eligible_rows": int(len(test_df)),
            "test_withheld_rows": int((df["split"] == "test").sum() - len(test_df)),
        }
    }

    with open(os.path.join(ARTIFACT_DIR, "service_forecaster.pkl"), "wb") as f:
        pickle.dump({"pipeline": service_pipe, "features": SERVICE_FEATURES, "version": "rf-service-v1"}, f)
    with open(os.path.join(ARTIFACT_DIR, "demand_fallback_forecaster.pkl"), "wb") as f:
        pickle.dump({"pipeline": demand_pipe, "features": DEMAND_FEATURES, "version": "rf-demand-v1"}, f)
    with open(os.path.join(ARTIFACT_DIR, "forecast_eval_report.json"), "w") as f:
        json.dump(eval_report, f, indent=2)

    print("Evaluation Report:\n", json.dumps(eval_report, indent=2))

if __name__ == "__main__":
    run()