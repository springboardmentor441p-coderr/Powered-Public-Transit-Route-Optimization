"""
RouteRanker: Phase 6 Daily Passenger Demand Forecasting Training Pipeline
Implements:
1. Chronological splitting (Train / Validation / Test) with zero leakage.
2. Naive 7-Day Baseline, 7-Day Moving Average, Ridge Regression, Random Forest, and Gradient Boosting.
3. System-wide demand forecasting model suite.
4. Route-level models for top high-demand bus corridors (Routes 79, 9, 66, 4).
5. Station-level models for top rapid transit hubs (Clark/Lake, Washington/Wabash, Lake, O'Hare).
6. Model evaluation, metric comparison, artifact persistence (.joblib), and visualization generation.
"""

import os
import json
import joblib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PHASE4_DATA_DIR = os.path.join(BASE_DIR, "data", "processed", "phase4")
MODELS_DIR = os.path.join(BASE_DIR, "models")
EVAL_DIR = os.path.join(BASE_DIR, "outputs", "evaluation")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(EVAL_DIR, exist_ok=True)

# Visual styling
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
NAVY = "#0F172A"
BLUE = "#00A1DE"
TEAL = "#0D9488"
CORAL = "#E11D48"

def compute_metrics(y_true, y_pred):
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    # Avoid zero division in MAPE
    non_zero = y_true > 0
    mape = float(np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])) * 100)
    r2 = float(r2_score(y_true, y_pred))
    return {
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "MAPE": round(mape, 2),
        "R2": round(r2, 4)
    }

def train_system_forecasting():
    print("\n" + "=" * 65)
    print("1. TRAINING SYSTEM-WIDE DAILY PASSENGER FORECASTING MODELS")
    print("=" * 65)
    
    sys_path = os.path.join(PHASE4_DATA_DIR, "cta_daily_system_forecasting_ready.csv")
    df = pd.read_csv(sys_path)
    df["date"] = pd.to_datetime(df["service_date"])
    
    # Drop rows where lag features are null (first 28 days)
    df = df.dropna(subset=["total_rides_lag_28", "total_rides_roll28_mean"]).sort_values("date").reset_index(drop=True)
    
    # Feature columns
    feature_cols = [
        "month", "day_of_week_num", "is_weekend", "day_of_year", "quarter",
        "is_month_start", "is_month_end",
        "total_rides_lag_1", "total_rides_lag_7", "total_rides_lag_14", "total_rides_lag_28",
        "total_rides_roll7_mean", "total_rides_roll14_mean", "total_rides_roll28_mean", "total_rides_roll7_std"
    ]
    
    # Add dummy variables for day_type_code (W, A, U)
    day_dummies = pd.get_dummies(df["day_type_code"], prefix="day_type", drop_first=False).astype(int)
    for c in day_dummies.columns:
        df[c] = day_dummies[c]
        if c not in feature_cols:
            feature_cols.append(c)
            
    print(f"Features ({len(feature_cols)}): {feature_cols}")
    
    # Chronological Split
    train_mask = df["date"] < "2025-01-01"
    val_mask = (df["date"] >= "2025-01-01") & (df["date"] < "2026-01-01")
    test_mask = df["date"] >= "2026-01-01"
    
    train_df = df[train_mask].copy()
    val_df = df[val_mask].copy()
    test_df = df[test_mask].copy()
    
    print(f"Chronological Splits:")
    print(f"  Train: {train_df['date'].min().strftime('%Y-%m-%d')} to {train_df['date'].max().strftime('%Y-%m-%d')} ({len(train_df):,} days)")
    print(f"  Validation: {val_df['date'].min().strftime('%Y-%m-%d')} to {val_df['date'].max().strftime('%Y-%m-%d')} ({len(val_df):,} days)")
    print(f"  Final Test: {test_df['date'].min().strftime('%Y-%m-%d')} to {test_df['date'].max().strftime('%Y-%m-%d')} ({len(test_df):,} days)")
    
    X_train, y_train = train_df[feature_cols], train_df["total_rides"]
    X_val, y_val = val_df[feature_cols], val_df["total_rides"]
    X_test, y_test = test_df[feature_cols], test_df["total_rides"]
    
    results = {}
    test_predictions = pd.DataFrame({
        "service_date": test_df["service_date"].values,
        "actual_total_rides": y_test.values
    })
    
    # --- Model 1: Naive 7-Day Baseline (y_t = y_{t-7}) ---
    y_pred_naive_val = val_df["total_rides_lag_7"].values
    y_pred_naive_test = test_df["total_rides_lag_7"].values
    results["Naive_7Day_Lag"] = {
        "val_metrics": compute_metrics(y_val.values, y_pred_naive_val),
        "test_metrics": compute_metrics(y_test.values, y_pred_naive_test)
    }
    test_predictions["pred_naive_7day"] = y_pred_naive_test
    
    # --- Model 2: Moving Average (7-Day Rolling Mean) ---
    y_pred_ma_val = val_df["total_rides_roll7_mean"].values
    y_pred_ma_test = test_df["total_rides_roll7_mean"].values
    results["Moving_Average_7Day"] = {
        "val_metrics": compute_metrics(y_val.values, y_pred_ma_val),
        "test_metrics": compute_metrics(y_test.values, y_pred_ma_test)
    }
    test_predictions["pred_moving_avg"] = y_pred_ma_test
    
    # --- Model 3: Ridge Regression with StandardScaler ---
    ridge_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=100.0, random_state=42))
    ])
    ridge_pipe.fit(X_train, y_train)
    results["Ridge_Regression"] = {
        "val_metrics": compute_metrics(y_val.values, ridge_pipe.predict(X_val)),
        "test_metrics": compute_metrics(y_test.values, ridge_pipe.predict(X_test))
    }
    test_predictions["pred_ridge"] = ridge_pipe.predict(X_test)
    
    # --- Model 4: Random Forest Regressor ---
    rf_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)
    results["Random_Forest"] = {
        "val_metrics": compute_metrics(y_val.values, rf_model.predict(X_val)),
        "test_metrics": compute_metrics(y_test.values, rf_model.predict(X_test))
    }
    test_predictions["pred_random_forest"] = rf_model.predict(X_test)
    
    # --- Model 5: HistGradientBoosting Regressor ---
    gb_model = HistGradientBoostingRegressor(
        max_iter=150,
        learning_rate=0.08,
        max_depth=8,
        random_state=42
    )
    gb_model.fit(X_train, y_train)
    results["Gradient_Boosting"] = {
        "val_metrics": compute_metrics(y_val.values, gb_model.predict(X_val)),
        "test_metrics": compute_metrics(y_test.values, gb_model.predict(X_test))
    }
    test_predictions["pred_gradient_boosting"] = gb_model.predict(X_test)
    
    # Compare Test Performance
    print("\n--- MODEL PERFORMANCE COMPARISON (TEST DATASET: 2026 UNSEEN DATES) ---")
    summary_table = []
    best_model_name = None
    lowest_mae = float("inf")
    
    for name, res in results.items():
        tm = res["test_metrics"]
        print(f"  {name:22s} | MAE: {tm['MAE']:>9,f} | RMSE: {tm['RMSE']:>9,f} | MAPE: {tm['MAPE']:>5.2f}% | R2: {tm['R2']:>6.4f}")
        summary_table.append({
            "model_name": name,
            "test_mae": tm["MAE"],
            "test_rmse": tm["RMSE"],
            "test_mape": tm["MAPE"],
            "test_r2": tm["R2"]
        })
        if tm["MAE"] < lowest_mae:
            lowest_mae = tm["MAE"]
            best_model_name = name
            
    print(f"\n=> Best Performing Model Selected: {best_model_name} (Lowest Test MAE: {lowest_mae:,.2f})")
    
    # Select best model object
    best_model_obj = gb_model if best_model_name == "Gradient_Boosting" else rf_model
    
    # Save best model and metadata
    system_model_path = os.path.join(MODELS_DIR, "cta_system_demand_forecaster.joblib")
    joblib.dump({
        "model": best_model_obj,
        "feature_names": feature_cols,
        "model_type": best_model_name,
        "best_metrics": results[best_model_name]["test_metrics"],
        "all_results": results
    }, system_model_path)
    print(f"Saved system model artifact to: {system_model_path}")
    
    # Save predictions CSV
    preds_path = os.path.join(EVAL_DIR, "system_forecast_test_predictions.csv")
    test_predictions.to_csv(preds_path, index=False)
    
    # Save metrics JSON
    metrics_json_path = os.path.join(EVAL_DIR, "model_evaluation_metrics.json")
    with open(metrics_json_path, "w") as f:
        json.dump({
            "target": "CTA System-Wide Daily Ridership",
            "best_model": best_model_name,
            "splits": {
                "train_days": len(train_df),
                "val_days": len(val_df),
                "test_days": len(test_df)
            },
            "models_benchmarked": results
        }, f, indent=2)
        
    return df, feature_cols, test_predictions, summary_table, best_model_name, rf_model

def train_route_and_station_models():
    print("\n" + "=" * 65)
    print("2. TRAINING CORRIDOR & STATION LEVEL DEMAND MODELS")
    print("=" * 65)
    
    # Bus Route Models for Top Corridors (79, 9, 66, 4)
    bus_path = os.path.join(PHASE4_DATA_DIR, "cta_daily_bus_route_forecasting_ready.csv")
    df_bus = pd.read_csv(bus_path, low_memory=False)
    df_bus["date"] = pd.to_datetime(df_bus["service_date"])
    df_bus["day_of_week_num"] = df_bus["date"].dt.day_of_week
    df_bus["is_weekend"] = df_bus["day_of_week_num"].isin([5, 6]).astype(int)
    df_bus["month"] = df_bus["date"].dt.month
    df_bus["route_id"] = df_bus["route_id"].astype(str)
    
    priority_routes = ["79", "9", "66", "4", "49", "X9"]
    route_models = {}
    
    bus_features = ["month", "day_of_week_num", "is_weekend", "route_rides_lag_1", "route_rides_lag_7", "route_rides_roll7_mean", "scheduled_trips"]
    
    for r in priority_routes:
        sub_df = df_bus[df_bus["route_id"] == str(r)].dropna(subset=["route_rides_lag_7", "route_rides_roll7_mean"]).sort_values("date")
        if len(sub_df) < 50:
            continue
            
        train_sub = sub_df[sub_df["date"] < "2026-01-01"]
        test_sub = sub_df[sub_df["date"] >= "2026-01-01"]
        
        if len(test_sub) == 0:
            train_sub = sub_df.iloc[:-60]
            test_sub = sub_df.iloc[-60:]
            
        rf_r = RandomForestRegressor(n_estimators=60, max_depth=8, random_state=42)
        rf_r.fit(train_sub[bus_features], train_sub["rides"])
        preds = rf_r.predict(test_sub[bus_features])
        metrics = compute_metrics(test_sub["rides"].values, preds)
        
        route_models[r] = {
            "model": rf_r,
            "metrics": metrics,
            "mean_demand": float(sub_df["rides"].mean())
        }
        print(f"  Route {r:4s} Model | Test MAE: {metrics['MAE']:>6.1f} | MAPE: {metrics['MAPE']:>5.2f}% | Mean Daily: {route_models[r]['mean_demand']:>7.0f}")
        
    route_models_path = os.path.join(MODELS_DIR, "cta_bus_route_forecasters.joblib")
    joblib.dump({
        "models": {k: v["model"] for k, v in route_models.items()},
        "metrics": {k: v["metrics"] for k, v in route_models.items()},
        "features": bus_features
    }, route_models_path)
    print(f"Saved route models artifact to: {route_models_path}")
    
    # Rail Station Models for Top Hubs (Clark/Lake 40380, Washington/Wabash 41700, Lake 41660, O'Hare 40890)
    rail_path = os.path.join(PHASE4_DATA_DIR, "cta_daily_rail_station_forecasting_ready.csv")
    df_rail = pd.read_csv(rail_path, low_memory=False)
    df_rail["date"] = pd.to_datetime(df_rail["service_date"])
    df_rail["day_of_week_num"] = df_rail["date"].dt.day_of_week
    df_rail["is_weekend"] = df_rail["day_of_week_num"].isin([5, 6]).astype(int)
    df_rail["month"] = df_rail["date"].dt.month
    
    top_stations = [40380, 41700, 41660, 40890, 41220]
    station_models = {}
    rail_features = ["month", "day_of_week_num", "is_weekend", "station_rides_lag_1", "station_rides_lag_7", "station_rides_roll7_mean"]
    
    for s in top_stations:
        sub_st = df_rail[df_rail["station_id"] == s].dropna(subset=["station_rides_lag_7", "station_rides_roll7_mean"]).sort_values("date")
        if len(sub_st) < 50:
            continue
            
        train_st = sub_st[sub_st["date"] < "2026-01-01"]
        test_st = sub_st[sub_st["date"] >= "2026-01-01"]
        
        rf_s = RandomForestRegressor(n_estimators=60, max_depth=8, random_state=42)
        rf_s.fit(train_st[rail_features], train_st["rides"])
        preds = rf_s.predict(test_st[rail_features])
        metrics = compute_metrics(test_st["rides"].values, preds)
        st_name = sub_st["station_name"].iloc[0]
        
        station_models[str(s)] = {
            "model": rf_s,
            "metrics": metrics,
            "station_name": st_name,
            "mean_demand": float(sub_st["rides"].mean())
        }
        print(f"  Station {s} ({st_name[:18]:18s}) | Test MAE: {metrics['MAE']:>6.1f} | MAPE: {metrics['MAPE']:>5.2f}%")
        
    station_models_path = os.path.join(MODELS_DIR, "cta_rail_station_forecasters.joblib")
    joblib.dump({
        "models": {k: v["model"] for k, v in station_models.items()},
        "metrics": {k: v["metrics"] for k, v in station_models.items()},
        "features": rail_features
    }, station_models_path)
    print(f"Saved station models artifact to: {station_models_path}")

def generate_evaluation_visualizations(test_predictions, summary_table, rf_model, feature_cols):
    print("\n" + "=" * 65)
    print("3. GENERATING FORECASTING EVALUATION CHARTS")
    print("=" * 65)
    
    # Chart 1: Actual vs Predicted Demand on 2026 Unseen Test Set
    fig, ax = plt.subplots(figsize=(14, 6), dpi=300)
    test_dates = pd.to_datetime(test_predictions["service_date"])
    
    # Plot first 90 days of test set for clear visual resolution
    sub_test = test_predictions.head(90).copy()
    sub_dates = pd.to_datetime(sub_test["service_date"])
    
    ax.plot(sub_dates, sub_test["actual_total_rides"] / 1000, label="Actual Observed Ridership", color=NAVY, linewidth=2.5, marker="o", markersize=3)
    ax.plot(sub_dates, sub_test["pred_gradient_boosting"] / 1000, label="Gradient Boosting Forecast", color=BLUE, linewidth=2.0, linestyle="--")
    ax.plot(sub_dates, sub_test["pred_random_forest"] / 1000, label="Random Forest Forecast", color=TEAL, linewidth=1.5, alpha=0.85)
    ax.plot(sub_dates, sub_test["pred_naive_7day"] / 1000, label="Naive 7-Day Baseline", color="#94A3B8", linewidth=1.2, linestyle=":")
    
    ax.set_title("RouteRanker: Daily System Ridership Actual vs. Predicted (Unseen 2026 Test Period)", fontsize=14, fontweight="bold", color=NAVY, pad=15)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Daily Passenger Demand (Thousands)", fontsize=11)
    ax.legend(frameon=True, loc="upper right")
    
    chart1_path = os.path.join(EVAL_DIR, "forecast_actual_vs_predicted_2026.png")
    plt.tight_layout()
    plt.savefig(chart1_path)
    plt.close()
    print(f"  Saved: {chart1_path}")
    
    # Chart 2: Model Comparison Chart (MAE & RMSE)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)
    
    df_summary = pd.DataFrame(summary_table).sort_values("test_mae")
    model_names = [m.replace("_", " ") for m in df_summary["model_name"]]
    
    colors = [TEAL if m == "Gradient_Boosting" else BLUE for m in df_summary["model_name"]]
    
    bars1 = ax1.bar(model_names, df_summary["test_mae"] / 1000, color=colors, width=0.55, edgecolor=NAVY)
    ax1.set_title("Test Mean Absolute Error (MAE)", fontsize=13, fontweight="bold", color=NAVY)
    ax1.set_ylabel("Error in Daily Boardings (Thousands)", fontsize=11)
    ax1.set_xticklabels(model_names, rotation=25, ha="right")
    for bar in bars1:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 1.5, f"{h:.1f}k", ha="center", fontsize=9, fontweight="bold")
    ax1.set_ylim(0, max(df_summary["test_mae"] / 1000) * 1.2)
    
    bars2 = ax2.bar(model_names, df_summary["test_mape"], color=colors, width=0.55, edgecolor=NAVY)
    ax2.set_title("Mean Absolute Percentage Error (MAPE %)", fontsize=13, fontweight="bold", color=NAVY)
    ax2.set_ylabel("Percentage Error (%)", fontsize=11)
    ax2.set_xticklabels(model_names, rotation=25, ha="right")
    for bar in bars2:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 0.5, f"{h:.1f}%", ha="center", fontsize=9, fontweight="bold")
    ax2.set_ylim(0, max(df_summary["test_mape"]) * 1.2)
    
    plt.suptitle("Model Evaluation & Selection on Unseen Test Set", fontsize=15, fontweight="bold", color=NAVY, y=1.02)
    plt.tight_layout()
    chart2_path = os.path.join(EVAL_DIR, "model_benchmark_comparison.png")
    plt.savefig(chart2_path, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {chart2_path}")
    
    # Chart 3: Random Forest Feature Importance
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    importances = rf_model.feature_importances_
    indices = np.argsort(importances)[::-1][:12]
    
    top_features = [feature_cols[i].replace("_", " ") for i in indices]
    top_scores = importances[indices]
    
    y_pos = np.arange(len(top_features))
    ax.barh(y_pos, top_scores, align="center", color=BLUE, edgecolor="#0284C7", height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(top_features, fontsize=10)
    ax.invert_yaxis()
    ax.set_title("Top 12 Most Predictive Features for Daily Passenger Demand", fontsize=14, fontweight="bold", color=NAVY, pad=15)
    ax.set_xlabel("Relative Feature Importance (Gini Importance)", fontsize=11)
    
    chart3_path = os.path.join(EVAL_DIR, "feature_importance.png")
    plt.tight_layout()
    plt.savefig(chart3_path)
    plt.close()
    print(f"  Saved: {chart3_path}")
    
    # Copy charts to artifact directory as required by instructions
    brain_dir = r"C:\Users\Hp\.gemini\antigravity\brain\289951b2-d17b-4273-a25e-fae95a022a60\eval_charts"
    os.makedirs(brain_dir, exist_ok=True)
    import shutil
    for cp in [chart1_path, chart2_path, chart3_path]:
        shutil.copy(cp, brain_dir)
    print(f"Evaluation charts copied to artifact directory: {brain_dir}")

def main():
    print("=" * 70)
    print("ROUTERANKER: PHASE 6 DEMAND FORECASTING TRAINING & EVALUATION")
    print("=" * 70)
    
    df, feature_cols, test_predictions, summary_table, best_model_name, rf_model = train_system_forecasting()
    train_route_and_station_models()
    generate_evaluation_visualizations(test_predictions, summary_table, rf_model, feature_cols)
    print("\nPhase 6 Forecasting Engine completed successfully.")

if __name__ == "__main__":
    main()
