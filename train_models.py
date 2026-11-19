# pyright: reportMissingImports=false
# type: ignore
"""
Step 8: Train and evaluate Demand-Only & Service-Aware forecasters + KMeans route clusters.
Saves versioned model artifacts, metrics JSON, and audit reports.
"""
import os
import sys
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Optional XGBoost import with type ignore for static checkers
try:
    from xgboost import XGBRegressor  # type: ignore
except ImportError:
    XGBRegressor = None

# Ensure script directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Feature schemas and targets
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

PROCESSED_DIR = os.getenv("ROUTERANKER_PROCESSED_DIR", str(BASE_DIR / "data" / "processed"))
ARTIFACTS_DIR = os.getenv("ROUTERANKER_ARTIFACTS_DIR", str(BASE_DIR / "artifacts"))
REPORTS_DIR = os.getenv("ROUTERANKER_REPORTS_DIR", str(BASE_DIR / "reports"))

def train_forecast_family(df: pd.DataFrame, feature_cols: list[str], prefix: str) -> dict:
    eligible = df.dropna(subset=feature_cols + [TARGET]).copy()
    train_df = eligible[eligible["split"] == "train"]
    val_df = eligible[eligible["split"] == "validation"]
    test_df = eligible[eligible["split"] == "test"]

    results = {
        "counts": {
            "total_eligible": len(eligible),
            "withheld_incomplete_history": len(df) - len(eligible),
            "train": len(train_df),
            "validation": len(val_df),
            "test": len(test_df),
        },
        "baselines": {
            "last_week_d7": {
                "validation": compute_regression_metrics(val_df[TARGET], val_df["rides_7_days_before"]),
                "test": compute_regression_metrics(test_df[TARGET], test_df["rides_7_days_before"]),
            },
            "seasonal_4w_mean": {
                "validation": compute_regression_metrics(val_df[TARGET], val_df["past_four_same_weekdays_mean"]),
                "test": compute_regression_metrics(test_df[TARGET], test_df["past_four_same_weekdays_mean"]),
            },
        },
        "models": {},
    }

    best_model_name = "ridge"
    best_val_mae = float("inf")

    candidate_models = ["ridge", "random_forest"]
    if XGBRegressor is not None:
        candidate_models.append("xgboost")

    for m_name in candidate_models:
        pipe = build_regressor_pipeline(feature_cols, m_name)
        pipe.fit(train_df[feature_cols], train_df[TARGET])

        val_preds = np.maximum(0.0, pipe.predict(val_df[feature_cols]))
        test_preds = np.maximum(0.0, pipe.predict(test_df[feature_cols]))

        val_metrics = compute_regression_metrics(val_df[TARGET], val_preds)
        test_metrics = compute_regression_metrics(test_df[TARGET], test_preds)

        artifact_path = os.path.join(ARTIFACTS_DIR, f"{prefix}_{m_name}.joblib")
        joblib.dump(pipe, artifact_path)

        results["models"][m_name] = {
            "artifact_path": artifact_path,
            "validation": val_metrics,
            "test": test_metrics,
        }
        if val_metrics["mae"] < best_val_mae:
            best_val_mae = val_metrics["mae"]
            best_model_name = m_name

    results["selected_serving_model"] = best_model_name
    return results

def train_route_clusters():
    matched = pd.read_parquet(os.path.join(PROCESSED_DIR, "matched_utilization.parquet"))
    dev = matched[pd.to_datetime(matched["date"]) < pd.to_datetime("2026-06-01")].copy()

    w_df = dev[dev["daytype"] == "W"].groupby("route", as_index=False).agg(
        weekday_observed_days=("date", "nunique"),
        mean_weekday_rides=("rides", "mean"),
        std_weekday_rides=("rides", "std"),
        mean_weekday_trips=("scheduled_trips", "mean"),
        sum_w_rides=("rides", "sum"),
        sum_w_hours=("scheduled_service_hours", "sum"),
    )
    w_df["weekday_rides_cv"] = (w_df["std_weekday_rides"] / w_df["mean_weekday_rides"]).fillna(0.0)
    w_df["weekday_rides_per_hour"] = w_df["sum_w_rides"] / w_df["sum_w_hours"]

    a_df = dev[dev["daytype"] == "A"].groupby("route", as_index=False).agg(
        sat_days=("date", "nunique"), mean_sat_rides=("rides", "mean")
    )
    u_df = dev[dev["daytype"] == "U"].groupby("route", as_index=False).agg(
        sun_days=("date", "nunique"), mean_sun_rides=("rides", "mean")
    )

    prof = w_df.merge(a_df, on="route", how="left").merge(u_df, on="route", how="left")
    prof["sat_to_weekday_ratio"] = (prof["mean_sat_rides"] / prof["mean_weekday_rides"]).fillna(0.65)
    prof["sun_to_weekday_ratio"] = (prof["mean_sun_rides"] / prof["mean_weekday_rides"]).fillna(0.50)

    cluster_features = [
        "mean_weekday_rides",
        "weekday_rides_cv",
        "sat_to_weekday_ratio",
        "sun_to_weekday_ratio",
        "mean_weekday_trips",
        "weekday_rides_per_hour",
    ]
    eligible = prof[prof["weekday_observed_days"] >= 20].dropna(subset=cluster_features).copy()

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(eligible[cluster_features])

    k = min(3, len(eligible))
    km = KMeans(n_clusters=k, n_init=20, random_state=42)
    eligible["cluster_id"] = km.fit_predict(X_scaled)
    unique_clusters = int(eligible["cluster_id"].nunique())
    sil = round(float(silhouette_score(X_scaled, eligible["cluster_id"])), 4) if k > 1 and unique_clusters > 1 and len(eligible) > k else None

    cluster_means = eligible.groupby("cluster_id")["mean_weekday_rides"].mean().sort_values()
    rank_labels = ["Moderate-Demand Coverage Tier", "Core Corridor Tier", "High-Volume Trunk Tier"]
    name_map = {cid: rank_labels[idx % len(rank_labels)] for idx, cid in enumerate(cluster_means.index)}
    eligible["cluster_label"] = eligible["cluster_id"].map(name_map)

    joblib.dump(scaler, os.path.join(ARTIFACTS_DIR, "kmeans_scaler.joblib"))
    joblib.dump(km, os.path.join(ARTIFACTS_DIR, "kmeans_model.joblib"))
    eligible.to_parquet(os.path.join(PROCESSED_DIR, "route_clusters.parquet"), index=False)

    return {"k": k, "clustered_routes": len(eligible), "silhouette_score": sil, "features": cluster_features}

def run():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    demand_df = pd.read_parquet(os.path.join(PROCESSED_DIR, "daily_forecasting_features.parquet"))
    service_df = pd.read_parquet(os.path.join(PROCESSED_DIR, "matched_service_features.parquet"))

    demand_res = train_forecast_family(demand_df, DEMAND_FEATURES, "demand_only")
    service_res = train_forecast_family(service_df, SERVICE_FEATURES, "matched_service")
    cluster_res = train_route_clusters()

    metrics_payload = {
        "model_version": "v3.8-prototype",
        "missing_history_policy": "Option 2 (Impute missing 28d lag from 7/14/21d mean + availability indicator)",
        "demand_only": demand_res,
        "matched_service": service_res,
        "clustering": cluster_res,
    }

    with open(os.path.join(ARTIFACTS_DIR, "training_metrics.json"), "w") as f:
        json.dump(metrics_payload, f, indent=2)

    with open(os.path.join(ARTIFACTS_DIR, "feature_schema.json"), "w") as f:
        json.dump({"demand_features": DEMAND_FEATURES, "service_features": SERVICE_FEATURES, "target": TARGET}, f, indent=2)

    sel_m = str(service_res.get("selected_serving_model") or "ridge")
    test_m = service_res["models"][sel_m]["test"]
    base_m = service_res["baselines"]["seasonal_4w_mean"]["test"]
    report_md = f"""# RouteRanker Model Evaluation Report

- **Model Version**: `{metrics_payload['model_version']}`
- **Missing History Policy**: {metrics_payload['missing_history_policy']}
- **Selected Service-Aware Regressor**: `{sel_m}`

## Held-Out Test Comparison (Matched Service Experiment)
| Method | Test Rows | MAE (rides/day) | RMSE (rides/day) | WAPE (%) |
|---|---:|---:|---:|---:|
| Last-Week Baseline (D-7) | {service_res['baselines']['last_week_d7']['test']['rows']} | {service_res['baselines']['last_week_d7']['test']['mae']} | {service_res['baselines']['last_week_d7']['test']['rmse']} | {service_res['baselines']['last_week_d7']['test']['wape_pct']}% |
| Seasonal 4-Week Mean Baseline | {base_m['rows']} | {base_m['mae']} | {base_m['rmse']} | {base_m['wape_pct']}% |
| **{sel_m} (Selected)** | **{test_m['rows']}** | **{test_m['mae']}** | **{test_m['rmse']}** | **{test_m['wape_pct']}%** |

## Route Clustering Summary
- **Clusters (K)**: {cluster_res['k']}
- **Clustered Routes**: {cluster_res['clustered_routes']}
- **Silhouette Score**: {cluster_res['silhouette_score']}
"""
    with open(os.path.join(REPORTS_DIR, "model_evaluation.md"), "w") as f:
        f.write(report_md)

    print(f"[train_models] Training complete. Selected model: {sel_m} (Test MAE: {test_m['mae']}, WAPE: {test_m['wape_pct']}%)")

if __name__ == "__main__":
    run()
