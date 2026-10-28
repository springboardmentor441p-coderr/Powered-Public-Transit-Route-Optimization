"""
analytics/06_train_evaluate_models.py
RouteRanker Data Pipeline - Step 6: Machine Learning Training & Evaluation

Implements strict chronological train/validation/test evaluation:
- Train Split: 2018-01-01 to 2024-12-31
- Validation Split: 2025-01-01 to 2025-12-31
- Test Split: 2026-01-01 to 2026-07-31

Models Evaluated:
1. Historical Daytype Mean Baseline
2. Persistent Lag-7 Baseline
3. Ridge Regression (L2 regularized linear model)
4. Random Forest Regressor
5. XGBoost Regressor

Evaluation Metrics: MAE, RMSE, and WAPE (Weighted Absolute Percentage Error).
Saves model artifacts to models/ and performance report to reports/model_metrics.json.
"""

import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = WORKSPACE_ROOT / "models"
REPORTS_DIR = WORKSPACE_ROOT / "reports"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def calculate_metrics(y_true, y_pred):
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    wape = float((np.sum(np.abs(y_true - y_pred)) / np.sum(y_true)) * 100.0)
    return {
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "WAPE_pct": round(wape, 2)
    }

def train_and_evaluate():
    print("=" * 60)
    print("ROUTERANKER PIPELINE: STEP 6 - MODEL TRAINING & EVALUATION")
    print("=" * 60)

    features_path = PROCESSED_DIR / "model_features.parquet"
    if not features_path.exists():
        raise FileNotFoundError(f"Feature file not found at {features_path}. Run step 05 first.")

    df = pd.read_parquet(features_path)
    df["date"] = pd.to_datetime(df["date"])
    print(f"[INPUT] Loaded {len(df):,} feature rows.")

    # 1. Chronological Train / Val / Test Splits
    train_mask = (df["date"] >= "2018-01-01") & (df["date"] <= "2024-12-31")
    val_mask = (df["date"] >= "2025-01-01") & (df["date"] <= "2025-12-31")
    test_mask = (df["date"] >= "2026-01-01") & (df["date"] <= "2026-07-31")

    train_df = df[train_mask].copy()
    val_df = df[val_mask].copy()
    test_df = df[test_mask].copy()

    print(f"[SPLIT] Chronological partitioning:")
    print(f"  Train:      {train_df['date'].min().date()} to {train_df['date'].max().date()} ({len(train_df):,} rows)")
    print(f"  Validation: {val_df['date'].min().date()} to {val_df['date'].max().date()} ({len(val_df):,} rows)")
    print(f"  Test:       {test_df['date'].min().date()} to {test_df['date'].max().date()} ({len(test_df):,} rows)")

    # 2. Baselines
    # Baseline 1: Route-specific historical daytype mean calculated strictly on train_df
    route_dt_means = train_df.groupby(["route", "daytype"])["rides"].mean().to_dict()
    global_mean = float(train_df["rides"].mean())

    val_pred_b1 = val_df.apply(lambda r: route_dt_means.get((r["route"], r["daytype"]), global_mean), axis=1).values
    test_pred_b1 = test_df.apply(lambda r: route_dt_means.get((r["route"], r["daytype"]), global_mean), axis=1).values

    b1_val_metrics = calculate_metrics(val_df["rides"].values, val_pred_b1)
    b1_test_metrics = calculate_metrics(test_df["rides"].values, test_pred_b1)
    print(f"\n[BASELINE 1 - Historical Route Daytype Mean]:")
    print(f"  Val  -> MAE: {b1_val_metrics['MAE']} | RMSE: {b1_val_metrics['RMSE']} | WAPE: {b1_val_metrics['WAPE_pct']}%")
    print(f"  Test -> MAE: {b1_test_metrics['MAE']} | RMSE: {b1_test_metrics['RMSE']} | WAPE: {b1_test_metrics['WAPE_pct']}%")

    # Baseline 2: Lag-7 persistent baseline (same day last week)
    val_pred_b2 = val_df["lag_7"].fillna(val_df["rolling_mean_7"]).fillna(global_mean).values
    test_pred_b2 = test_df["lag_7"].fillna(test_df["rolling_mean_7"]).fillna(global_mean).values

    b2_val_metrics = calculate_metrics(val_df["rides"].values, val_pred_b2)
    b2_test_metrics = calculate_metrics(test_df["rides"].values, test_pred_b2)
    print(f"\n[BASELINE 2 - Persistent Lag-7 Baseline]:")
    print(f"  Val  -> MAE: {b2_val_metrics['MAE']} | RMSE: {b2_val_metrics['RMSE']} | WAPE: {b2_val_metrics['WAPE_pct']}%")
    print(f"  Test -> MAE: {b2_test_metrics['MAE']} | RMSE: {b2_test_metrics['RMSE']} | WAPE: {b2_test_metrics['WAPE_pct']}%")

    # 3. Feature Selection
    feature_cols = [
        "lag_1", "lag_7", "lag_14", "lag_28",
        "rolling_mean_7", "rolling_std_7", "rolling_mean_28",
        "day_of_week", "is_weekend", "month", "day_of_month", "day_of_year",
        "sin_dow", "cos_dow", "sin_month", "cos_month",
        "stops_count", "weekday_scheduled_trips", "saturday_scheduled_trips", "sunday_scheduled_trips",
        "exclusivity_pct"
    ]
    print(f"\n[FEATURES] {len(feature_cols)} predictor features selected: {feature_cols}")

    X_train = train_df[feature_cols].copy().fillna(0)
    y_train = train_df["rides"].values

    X_val = val_df[feature_cols].copy().fillna(0)
    y_val = val_df["rides"].values

    X_test = test_df[feature_cols].copy().fillna(0)
    y_test = test_df["rides"].values

    # Scaler for linear models
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)

    metrics_summary = {
        "evaluation_protocol": "Chronological Out-of-Time Validation",
        "splits": {
            "train": {"start": "2018-01-01", "end": "2024-12-31", "rows": len(train_df)},
            "validation": {"start": "2025-01-01", "end": "2025-12-31", "rows": len(val_df)},
            "test": {"start": "2026-01-01", "end": "2026-07-31", "rows": len(test_df)}
        },
        "features": feature_cols,
        "models": {
            "Baseline_Historical_Daytype_Mean": {"validation": b1_val_metrics, "test": b1_test_metrics},
            "Baseline_Lag_7_Persistent": {"validation": b2_val_metrics, "test": b2_test_metrics}
        }
    }

    # 4. Model 1: Ridge Regression
    print("\n[TRAINING] 1. Ridge Regression (alpha=100.0)...")
    ridge = Ridge(alpha=100.0, random_state=42)
    ridge.fit(X_train_scaled, y_train)

    val_pred_ridge = np.clip(ridge.predict(X_val_scaled), 0, None)
    test_pred_ridge = np.clip(ridge.predict(X_test_scaled), 0, None)

    ridge_val_m = calculate_metrics(y_val, val_pred_ridge)
    ridge_test_m = calculate_metrics(y_test, test_pred_ridge)
    metrics_summary["models"]["Ridge_Regression"] = {"validation": ridge_val_m, "test": ridge_test_m}
    print(f"  Val  -> MAE: {ridge_val_m['MAE']} | RMSE: {ridge_val_m['RMSE']} | WAPE: {ridge_val_m['WAPE_pct']}%")
    print(f"  Test -> MAE: {ridge_test_m['MAE']} | RMSE: {ridge_test_m['RMSE']} | WAPE: {ridge_test_m['WAPE_pct']}%")

    # 5. Model 2: Random Forest Regressor
    print("\n[TRAINING] 2. Random Forest Regressor (n_estimators=100, max_depth=12)...")
    rf = RandomForestRegressor(n_estimators=100, max_depth=12, min_samples_leaf=5, n_jobs=-1, random_state=42)
    rf.fit(X_train, y_train)

    val_pred_rf = np.clip(rf.predict(X_val), 0, None)
    test_pred_rf = np.clip(rf.predict(X_test), 0, None)

    rf_val_m = calculate_metrics(y_val, val_pred_rf)
    rf_test_m = calculate_metrics(y_test, test_pred_rf)
    metrics_summary["models"]["Random_Forest"] = {"validation": rf_val_m, "test": rf_test_m}
    print(f"  Val  -> MAE: {rf_val_m['MAE']} | RMSE: {rf_val_m['RMSE']} | WAPE: {rf_val_m['WAPE_pct']}%")
    print(f"  Test -> MAE: {rf_test_m['MAE']} | RMSE: {rf_test_m['RMSE']} | WAPE: {rf_test_m['WAPE_pct']}%")

    # 6. Model 3: XGBoost Regressor
    print("\n[TRAINING] 3. XGBoost Regressor (n_estimators=150, max_depth=6, lr=0.05)...")
    xgb = XGBRegressor(n_estimators=150, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)
    xgb.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    val_pred_xgb = np.clip(xgb.predict(X_val), 0, None)
    test_pred_xgb = np.clip(xgb.predict(X_test), 0, None)

    xgb_val_m = calculate_metrics(y_val, val_pred_xgb)
    xgb_test_m = calculate_metrics(y_test, test_pred_xgb)
    metrics_summary["models"]["XGBoost"] = {"validation": xgb_val_m, "test": xgb_test_m}
    print(f"  Val  -> MAE: {xgb_val_m['MAE']} | RMSE: {xgb_val_m['RMSE']} | WAPE: {xgb_val_m['WAPE_pct']}%")
    print(f"  Test -> MAE: {xgb_test_m['MAE']} | RMSE: {xgb_test_m['RMSE']} | WAPE: {xgb_test_m['WAPE_pct']}%")

    # 7. Save Model Artifacts
    print("\n[SAVING] Serializing models & scaler...")
    joblib.dump(scaler, MODELS_DIR / "scaler.joblib")
    joblib.dump(ridge, MODELS_DIR / "ridge_model.joblib")
    joblib.dump(rf, MODELS_DIR / "random_forest_model.joblib")
    joblib.dump(xgb, MODELS_DIR / "xgboost_model.joblib")

    with open(REPORTS_DIR / "model_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2)

    # Save predictions dataframe on test set for UI and evaluation
    test_df_export = test_df[["route", "date", "daytype", "rides"]].copy()
    test_df_export["pred_baseline_daytype"] = np.round(test_pred_b1, 1)
    test_df_export["pred_baseline_lag7"] = np.round(test_pred_b2, 1)
    test_df_export["pred_ridge"] = np.round(test_pred_ridge, 1)
    test_df_export["pred_random_forest"] = np.round(test_pred_rf, 1)
    test_df_export["pred_xgboost"] = np.round(test_pred_xgb, 1)

    out_preds = PROCESSED_DIR / "model_predictions_test.parquet"
    test_df_export.to_parquet(out_preds, engine="pyarrow", index=False)
    print(f"[EXPORTED] Test predictions saved to {out_preds.relative_to(WORKSPACE_ROOT)} ({len(test_df_export):,} rows)")

    return metrics_summary

if __name__ == "__main__":
    train_and_evaluate()
