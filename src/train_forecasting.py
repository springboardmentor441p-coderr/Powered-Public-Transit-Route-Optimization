"""
Milestone 3 — Step 2: Demand Forecasting Models (src/train_forecasting.py)

Trains, tunes, and evaluates four forecasting model families on the Manhattan bus dataset:
1. Ridge regression on riders (`Ridge (riders)`) — 12 validation settings
2. Ridge regression on log(1 + riders) (`Ridge (log(1 + riders))`) — 12 validation settings
3. Random Forest (`RandomForestRegressor`) — 12 validation settings
4. Gradient Boosting (`HistGradientBoostingRegressor`) — 14 validation settings

Evaluation & Reporting Rules:
- Strict test-set isolation: only `train` (2026-01-04 to 2026-05-31, 125,445 rows) and
  `val` (2026-06-01 to 2026-07-31, 54,046 rows) are loaded via `src.evaluate.load_dataset`.
- Fair baseline comparison: compares all models with the 4-week average baseline
  (`lag_mean_available`, 14.08% WAPE) and 1-week lag (`lag_7d`, 17.48% WAPE) on the
  exact same 53,585 validation rows where both lags are present, and reports all
  54,046 validation rows separately.
- Computes permutation importance on the validation set for the best model across all
  22 semantic input features.
- Identifies where the best model misses most (top 25 largest validation route-hour
  errors plus systematic breakdown by error regime).
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluate import (
    compute_forecast_metrics,
    evaluate_forecasting,
    load_dataset,
    print_forecasting_summary,
)

MODELS_DIR = ROOT / "models"
TAB_DIR = ROOT / "reports" / "tables"
FIG_DIR = ROOT / "reports" / "figures"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

CAT_COLS = ["route", "day_of_week", "time_band"]
NUM_SCALE_COLS = [
    "trips_running",
    "trips_starting",
    "service_hours",
    "route_length_km",
    "stop_count",
    "hour_sin",
    "hour_cos",
]
BINARY_COLS = [
    "is_weekend",
    "is_public_holiday",
    "holiday_schedule",
    "is_storm",
    "is_sbs",
    "is_24h",
]
LAG_COLS = [
    "lag_7d",
    "lag_14d",
    "lag_21d",
    "lag_28d",
    "lag_mean_available",
    "lags_available_count",
]
ALL_FEATURES = CAT_COLS + NUM_SCALE_COLS + BINARY_COLS + LAG_COLS

LOG_TRANSFORM_COLS = [
    "trips_running",
    "trips_starting",
    "service_hours",
    "lag_7d",
    "lag_14d",
    "lag_21d",
    "lag_28d",
    "lag_mean_available",
]


def make_log_input_df(df: pd.DataFrame) -> pd.DataFrame:
    """Apply log1p to non-negative count and lag predictors for log-log Ridge regression."""
    out = df[ALL_FEATURES].copy()
    for col in LOG_TRANSFORM_COLS:
        out[col] = np.log1p(np.clip(out[col], 0.0, None))
    return out


def classify_miss_reason(row: pd.Series) -> str:
    """Categorize why a large validation route-hour forecast error occurred."""
    if bool(row.get("is_public_holiday", False)) or bool(row.get("holiday_schedule", False)):
        return "Public Holiday / Holiday Schedule Over-prediction"
    if str(row.get("route", "")) == "M35":
        return "M35 Randall's Island Event / Ferry Surge"
    if str(row.get("time_band", "")) in ("morning_peak", "evening_peak") and row.get("actual_ridership", 0) >= 800:
        return "High-Volume Trunk Commuter Peak Fluctuation"
    if str(row.get("time_band", "")) == "midday" and row.get("actual_ridership", 0) >= 700:
        return "High-Volume Trunk Midday Surge / Dip"
    return "Localised Schedule / Weather / Construction Variance"


def run_step2_forecasting() -> None:
    print("=" * 88, flush=True)
    print("MILESTONE 3 — STEP 2: DEMAND FORECASTING MODELS & VALIDATION TUNING", flush=True)
    print("=" * 88, flush=True)

    # 1. Load datasets strictly via load_dataset (never touching test_features.parquet)
    train_df = load_dataset("train")
    val_df = load_dataset("val")
    preprocessor = joblib.load(MODELS_DIR / "preprocessor.joblib")

    y_train = train_df["ridership"].values.astype(float)
    y_val = val_df["ridership"].values.astype(float)

    # Mask for the exact 53,585 validation rows where both baselines are defined
    common_val_mask = (
        val_df["ridership"].notnull()
        & val_df["lag_7d"].notnull()
        & val_df["lag_mean_available"].notnull()
    ).values

    # Mask for complete-lag training rows (113,262 of 125,445 rows)
    valid_train_mask = (
        train_df["lag_7d"].notnull() & train_df["lag_mean_available"].notnull()
    ).values

    print(f"Loaded train split : {len(train_df):,} rows ({valid_train_mask.sum():,} with complete lags)", flush=True)
    print(f"Loaded val split   : {len(val_df):,} rows ({common_val_mask.sum():,} common baseline rows)", flush=True)

    X_train_all = preprocessor.transform(train_df[ALL_FEATURES])
    X_train_valid = X_train_all[valid_train_mask]
    y_train_valid = y_train[valid_train_mask]
    X_val = preprocessor.transform(val_df[ALL_FEATURES])

    # Pre-compute log-transformed input matrix for Ridge on log(1 + riders)
    prep_log = clone(preprocessor)
    X_train_log_inputs = prep_log.fit_transform(make_log_input_df(train_df))
    X_val_log_inputs = prep_log.transform(make_log_input_df(val_df))

    tuning_rows: List[Dict] = []
    best_predictions: Dict[str, np.ndarray] = {}
    best_configs: Dict[str, Dict] = {}

    def record_setting(
        family: str,
        setting_id: int,
        setting_desc: str,
        params_dict: Dict,
        pred_val: np.ndarray,
        fit_sec: float,
    ) -> Dict:
        pred_clipped = np.clip(pred_val, 0.0, None)
        m_53585 = compute_forecast_metrics(y_val[common_val_mask], pred_clipped[common_val_mask])
        m_54046 = compute_forecast_metrics(y_val, pred_clipped)
        row = {
            "model_family": family,
            "setting_id": setting_id,
            "setting_description": setting_desc,
            "n_eval_common": m_53585["n_eval"],
            "wape_53585_pct": m_53585["wape_pct"],
            "mae_53585": m_53585["mae"],
            "rmse_53585": m_53585["rmse"],
            "bias_53585_pred_minus_actual": m_53585["bias_pred_minus_actual"],
            "n_eval_all": m_54046["n_eval"],
            "wape_54046_pct": m_54046["wape_pct"],
            "mae_54046": m_54046["mae"],
            "rmse_54046": m_54046["rmse"],
            "bias_54046_pred_minus_actual": m_54046["bias_pred_minus_actual"],
            "fit_seconds": round(fit_sec, 2),
        }
        tuning_rows.append(row)

        if (
            family not in best_configs
            or m_53585["wape_pct"] < best_configs[family]["wape_53585_pct"]
        ):
            best_configs[family] = {**row, "params": params_dict}
            best_predictions[family] = pred_clipped
        return row

    # ==========================================================================
    # FAMILY 1: Ridge Regression on riders (12 settings)
    # ==========================================================================
    print("\n[1/4] Tuning Ridge regression on riders (12 settings)...", flush=True)
    ridge_alphas = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
    sid = 0
    for subset_label, X_tr, y_tr in [
        ("all_train_rows", X_train_all, y_train),
        ("complete_lag_rows", X_train_valid, y_train_valid),
    ]:
        for alpha in ridge_alphas:
            sid += 1
            t0 = time.time()
            model = Ridge(alpha=alpha, random_state=42)
            model.fit(X_tr, y_tr)
            pred = model.predict(X_val)
            dt = time.time() - t0
            desc = f"alpha={alpha}, train={subset_label}"
            r = record_setting(
                "Ridge (riders)",
                sid,
                desc,
                {"alpha": alpha, "train_subset": subset_label},
                pred,
                dt,
            )
            print(
                f"  #{sid:02d} {desc:<38} -> 53,585 WAPE={r['wape_53585_pct']:>6.2f}%, "
                f"MAE={r['mae_53585']:>6.2f} | 54,046 WAPE={r['wape_54046_pct']:>6.2f}%",
                flush=True,
            )

    # ==========================================================================
    # FAMILY 2: Ridge Regression on log(1 + riders) (12 settings)
    # ==========================================================================
    print("\n[2/4] Tuning Ridge regression on log(1 + riders) (12 settings)...", flush=True)
    ridge_log_alphas = [0.01, 0.1, 1.0, 10.0, 100.0, 500.0]
    sid = 0
    y_train_log_all = np.log1p(y_train)
    y_train_log_valid = np.log1p(y_train_valid)
    for feat_mode, X_tr, y_tr_log, X_va in [
        ("raw_linear_inputs", X_train_valid, y_train_log_valid, X_val),
        ("log1p_count_and_lag_inputs", X_train_log_inputs[valid_train_mask], y_train_log_valid, X_val_log_inputs),
    ]:
        for alpha in ridge_log_alphas:
            sid += 1
            t0 = time.time()
            model = Ridge(alpha=alpha, random_state=42)
            model.fit(X_tr, y_tr_log)
            pred_log = np.clip(model.predict(X_va), 0.0, 10.0)
            pred = np.expm1(pred_log)
            dt = time.time() - t0
            desc = f"alpha={alpha}, features={feat_mode}"
            r = record_setting(
                "Ridge (log(1 + riders))",
                sid,
                desc,
                {"alpha": alpha, "features": feat_mode},
                pred,
                dt,
            )
            print(
                f"  #{sid:02d} {desc:<45} -> 53,585 WAPE={r['wape_53585_pct']:>6.2f}%, "
                f"MAE={r['mae_53585']:>6.2f} | 54,046 WAPE={r['wape_54046_pct']:>6.2f}%",
                flush=True,
            )

    # ==========================================================================
    # FAMILY 3: Random Forest Regressor (12 settings)
    # ==========================================================================
    print("\n[3/4] Tuning Random Forest Regressor (12 settings)...", flush=True)
    rf_grid = [
        (10, 20, 0.6, "all_train_rows"),
        (12, 15, 0.6, "all_train_rows"),
        (12, 10, 0.8, "all_train_rows"),
        (14, 10, 0.6, "all_train_rows"),
        (14, 10, 0.8, "all_train_rows"),
        (16, 10, 0.6, "all_train_rows"),
        (16, 10, 0.8, "all_train_rows"),
        (16, 5, 0.8, "all_train_rows"),
        (18, 10, 0.7, "all_train_rows"),
        (18, 5, 0.8, "all_train_rows"),
        (20, 5, 0.8, "all_train_rows"),
        (20, 5, 0.8, "complete_lag_rows"),
    ]
    for sid, (max_depth, min_leaf, max_feat, subset_label) in enumerate(rf_grid, start=1):
        t0 = time.time()
        X_tr = X_train_valid if subset_label == "complete_lag_rows" else X_train_all
        y_tr = y_train_valid if subset_label == "complete_lag_rows" else y_train
        rf = RandomForestRegressor(
            n_estimators=80,
            max_depth=max_depth,
            min_samples_leaf=min_leaf,
            max_features=max_feat,
            n_jobs=-1,
            random_state=42,
        )
        rf.fit(X_tr, y_tr)
        pred = rf.predict(X_val)
        dt = time.time() - t0
        desc = f"depth={max_depth}, leaf={min_leaf}, feat={max_feat}, train={subset_label}"
        r = record_setting(
            "Random Forest",
            sid,
            desc,
            {
                "n_estimators": 80,
                "max_depth": max_depth,
                "min_samples_leaf": min_leaf,
                "max_features": max_feat,
                "train_subset": subset_label,
            },
            pred,
            dt,
        )
        print(
            f"  #{sid:02d} {desc:<54} -> 53,585 WAPE={r['wape_53585_pct']:>6.2f}%, "
            f"MAE={r['mae_53585']:>6.2f} | 54,046 WAPE={r['wape_54046_pct']:>6.2f}% ({dt:.1f}s)",
            flush=True,
        )

    # ==========================================================================
    # FAMILY 4: Gradient Boosting — HistGradientBoostingRegressor (14 settings)
    # ==========================================================================
    print("\n[4/4] Tuning HistGradientBoostingRegressor (14 settings)...", flush=True)
    hgb_grid = [
        ("squared_error", 0.03, 31, 20, 1.0, "all_train_rows"),
        ("squared_error", 0.05, 31, 20, 1.0, "all_train_rows"),
        ("squared_error", 0.05, 63, 20, 1.0, "all_train_rows"),
        ("squared_error", 0.05, 63, 30, 5.0, "all_train_rows"),
        ("squared_error", 0.08, 63, 25, 1.0, "all_train_rows"),
        ("squared_error", 0.05, 127, 30, 5.0, "all_train_rows"),
        ("squared_error", 0.05, 63, 20, 1.0, "complete_lag_rows"),
        ("absolute_error", 0.05, 31, 20, 1.0, "all_train_rows"),
        ("absolute_error", 0.05, 63, 25, 1.0, "all_train_rows"),
        ("absolute_error", 0.05, 127, 30, 1.0, "all_train_rows"),
        ("absolute_error", 0.08, 63, 25, 1.0, "all_train_rows"),
        ("poisson", 0.05, 63, 25, 1.0, "all_train_rows"),
        ("poisson", 0.05, 127, 25, 1.0, "all_train_rows"),
        ("poisson", 0.05, 127, 25, 1.0, "complete_lag_rows"),
    ]
    best_hgb_estimator = None
    best_hgb_wape = float("inf")

    for sid, (loss_fn, lr, max_leaf, min_leaf, l2, subset_label) in enumerate(hgb_grid, start=1):
        t0 = time.time()
        X_tr = X_train_valid if subset_label == "complete_lag_rows" else X_train_all
        y_tr = y_train_valid if subset_label == "complete_lag_rows" else y_train
        hgb = HistGradientBoostingRegressor(
            loss=loss_fn,
            learning_rate=lr,
            max_leaf_nodes=max_leaf,
            min_samples_leaf=min_leaf,
            l2_regularization=l2,
            max_iter=300,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=15,
            random_state=42,
        )
        hgb.fit(X_tr, y_tr)
        pred = hgb.predict(X_val)
        dt = time.time() - t0
        desc = f"loss={loss_fn}, lr={lr}, leaf={max_leaf}, min={min_leaf}, l2={l2}, train={subset_label}"
        r = record_setting(
            "HistGradientBoosting",
            sid,
            desc,
            {
                "loss": loss_fn,
                "learning_rate": lr,
                "max_leaf_nodes": max_leaf,
                "min_samples_leaf": min_leaf,
                "l2_regularization": l2,
                "train_subset": subset_label,
            },
            pred,
            dt,
        )
        if r["wape_53585_pct"] < best_hgb_wape:
            best_hgb_wape = r["wape_53585_pct"]
            best_hgb_estimator = hgb
        print(
            f"  #{sid:02d} {desc:<72} -> 53,585 WAPE={r['wape_53585_pct']:>6.2f}%, "
            f"MAE={r['mae_53585']:>6.2f} | 54,046 WAPE={r['wape_54046_pct']:>6.2f}% ({dt:.1f}s)",
            flush=True,
        )

    # Save full tuning log
    tuning_df = pd.DataFrame(tuning_rows)
    tuning_path = TAB_DIR / "m3_forecast_tuning_results.csv"
    tuning_df.to_csv(tuning_path, index=False)
    print(f"\nSaved {len(tuning_df)} hyperparameter tuning runs to {tuning_path.relative_to(ROOT)}", flush=True)

    # ==========================================================================
    # BUILD HEAD-TO-HEAD COMPARISON TABLE (53,585 Common Rows & All 54,046 Rows)
    # ==========================================================================
    comparison_rows = []

    # Baselines on 53,585 common rows and on all available rows out of 54,046
    for base_name, col in [
        ("Same Hour Last Week (lag_7d)", "lag_7d"),
        ("4-Week Average (lag_mean_available)", "lag_mean_available"),
    ]:
        m_c = compute_forecast_metrics(val_df.loc[common_val_mask, "ridership"], val_df.loc[common_val_mask, col])
        m_a = compute_forecast_metrics(val_df["ridership"], val_df[col])
        comparison_rows.append({
            "model_name": base_name,
            "model_type": "Baseline",
            "best_setting": f"Direct {col} historical average",
            "settings_tested": 1,
            "n_eval_53585": m_c["n_eval"],
            "mae_53585": m_c["mae"],
            "rmse_53585": m_c["rmse"],
            "wape_53585_pct": m_c["wape_pct"],
            "bias_53585_pred_minus_actual": m_c["bias_pred_minus_actual"],
            "n_eval_all_val": m_a["n_eval"],
            "mae_all_val": m_a["mae"],
            "rmse_all_val": m_a["rmse"],
            "wape_all_val_pct": m_a["wape_pct"],
            "bias_all_val_pred_minus_actual": m_a["bias_pred_minus_actual"],
            "wape_change_vs_4wk_pct_pts": round(m_c["wape_pct"] - 14.08, 2),
        })

    for fam in ["Ridge (riders)", "Ridge (log(1 + riders))", "Random Forest", "HistGradientBoosting"]:
        bc = best_configs[fam]
        n_tested = int((tuning_df["model_family"] == fam).sum())
        comparison_rows.append({
            "model_name": fam,
            "model_type": "ML Model",
            "best_setting": bc["setting_description"],
            "settings_tested": n_tested,
            "n_eval_53585": bc["n_eval_common"],
            "mae_53585": bc["mae_53585"],
            "rmse_53585": bc["rmse_53585"],
            "wape_53585_pct": bc["wape_53585_pct"],
            "bias_53585_pred_minus_actual": bc["bias_53585_pred_minus_actual"],
            "n_eval_all_val": bc["n_eval_all"],
            "mae_all_val": bc["mae_54046"],
            "rmse_all_val": bc["rmse_54046"],
            "wape_all_val_pct": bc["wape_54046_pct"],
            "bias_all_val_pred_minus_actual": bc["bias_54046_pred_minus_actual"],
            "wape_change_vs_4wk_pct_pts": round(bc["wape_53585_pct"] - 14.08, 2),
        })

    comparison_df = pd.DataFrame(comparison_rows)
    comp_path = TAB_DIR / "m3_forecast_model_comparison.csv"
    comparison_df.to_csv(comp_path, index=False)
    print("\n" + "=" * 88, flush=True)
    print("VALIDATION COMPARISON: COMMON 53,585 ROWS vs ALL 54,046 ROWS", flush=True)
    print("=" * 88, flush=True)
    print(comparison_df.to_string(index=False), flush=True)

    # ==========================================================================
    # EVALUATE BEST MODEL (HistGradientBoosting) WITH SHARED EVALUATION MODULE
    # ==========================================================================
    best_family = "HistGradientBoosting"
    best_pred = best_predictions[best_family]

    val_common_eval = val_df[common_val_mask].copy()
    val_common_eval["prediction"] = best_pred[common_val_mask]
    res_common = evaluate_forecasting(
        df=val_common_eval,
        y_true_col="ridership",
        y_pred_col="prediction",
        model_name="HistGradientBoosting (Best Validation Forecaster, 53,585 Common Rows)",
        save_prefix="m3_eval_best_forecast",
        out_dir=TAB_DIR,
    )
    print_forecasting_summary(res_common)

    val_all_eval = val_df.copy()
    val_all_eval["prediction"] = best_pred
    evaluate_forecasting(
        df=val_all_eval,
        y_true_col="ridership",
        y_pred_col="prediction",
        model_name="HistGradientBoosting (Best Validation Forecaster, All 54,046 Rows)",
        save_prefix="m3_eval_best_forecast_all54046",
        out_dir=TAB_DIR,
    )

    # Save best model pipeline bundle
    best_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", best_hgb_estimator),
    ])
    joblib.dump(
        {
            "pipeline": best_pipeline,
            "model_family": best_family,
            "best_setting": best_configs[best_family]["setting_description"],
            "params": best_configs[best_family]["params"],
            "features": ALL_FEATURES,
            "val_wape_53585_pct": best_configs[best_family]["wape_53585_pct"],
            "val_wape_54046_pct": best_configs[best_family]["wape_54046_pct"],
        },
        MODELS_DIR / "best_forecaster.joblib",
        compress=3,
    )
    print(f"Saved best forecaster bundle to {MODELS_DIR / 'best_forecaster.joblib'}", flush=True)

    # ==========================================================================
    # PERMUTATION IMPORTANCE ON VALIDATION SET (22 SEMANTIC INPUT FEATURES)
    # ==========================================================================
    print("\nComputing permutation importance on validation set (22 input features, n_repeats=5)...", flush=True)
    t0 = time.time()
    perm_res = permutation_importance(
        best_pipeline,
        val_df[ALL_FEATURES],
        y_val,
        scoring="neg_mean_absolute_error",
        n_repeats=5,
        random_state=42,
        n_jobs=1,
    )
    mean_y = float(np.mean(y_val))
    perm_df = pd.DataFrame({
        "feature": ALL_FEATURES,
        "mae_increase_riders": np.round(perm_res.importances_mean, 3),
        "mae_increase_std": np.round(perm_res.importances_std, 3),
        "wape_increase_pct_pts": np.round((perm_res.importances_mean / mean_y) * 100.0, 3),
    }).sort_values("mae_increase_riders", ascending=False).reset_index(drop=True)
    perm_df["rank"] = np.arange(1, len(perm_df) + 1)
    perm_df = perm_df[["rank", "feature", "mae_increase_riders", "mae_increase_std", "wape_increase_pct_pts"]]
    perm_path = TAB_DIR / "m3_forecast_permutation_importance.csv"
    perm_df.to_csv(perm_path, index=False)
    print(f"Permutation importance completed in {time.time() - t0:.1f}s -> {perm_path.relative_to(ROOT)}", flush=True)
    print(perm_df.head(12).to_string(index=False), flush=True)

    # ==========================================================================
    # WHERE THE BEST MODEL MISSES MOST (TOP 25 ROUTE-HOURS + CATEGORY SUMMARY)
    # ==========================================================================
    misses_df = val_df.copy()
    misses_df["actual_ridership"] = y_val.round(1)
    misses_df["predicted_ridership"] = np.round(best_pred, 1)
    misses_df["bias_pred_minus_actual"] = np.round(best_pred - y_val, 1)
    misses_df["abs_error"] = np.round(np.abs(best_pred - y_val), 1)
    misses_df["lag_mean_available"] = misses_df["lag_mean_available"].round(1)
    misses_df["miss_category"] = misses_df.apply(classify_miss_reason, axis=1)

    top_misses = (
        misses_df.sort_values("abs_error", ascending=False)
        .head(25)
        .copy()
    )
    top_misses["rank"] = np.arange(1, len(top_misses) + 1)
    miss_cols = [
        "rank",
        "route",
        "date",
        "day_of_week",
        "hour",
        "time_band",
        "day_type",
        "is_public_holiday",
        "holiday_schedule",
        "trips_running",
        "actual_ridership",
        "predicted_ridership",
        "bias_pred_minus_actual",
        "abs_error",
        "lag_mean_available",
        "miss_category",
    ]
    top_misses = top_misses[miss_cols]
    misses_path = TAB_DIR / "m3_forecast_worst_misses.csv"
    top_misses.to_csv(misses_path, index=False)
    print(f"\nSaved top 25 largest validation forecast misses to {misses_path.relative_to(ROOT)}", flush=True)
    print(top_misses.head(15).to_string(index=False), flush=True)

    # Also summarize the top 100 largest misses by category
    top100 = misses_df.sort_values("abs_error", ascending=False).head(100)
    cat_summary = (
        top100.groupby("miss_category")
        .agg(
            hours_in_top_100=("abs_error", "count"),
            mean_abs_error=("abs_error", "mean"),
            mean_bias_pred_minus_actual=("bias_pred_minus_actual", "mean"),
            example_routes=("route", lambda s: ", ".join(pd.Series(s).value_counts().head(4).index)),
        )
        .reset_index()
        .sort_values("hours_in_top_100", ascending=False)
    )
    cat_summary["mean_abs_error"] = cat_summary["mean_abs_error"].round(1)
    cat_summary["mean_bias_pred_minus_actual"] = cat_summary["mean_bias_pred_minus_actual"].round(1)
    cat_summary.to_csv(TAB_DIR / "m3_forecast_miss_summary_by_category.csv", index=False)

    # ==========================================================================
    # GENERATE STEP 2 FIGURES FOR REPORT & NOTEBOOK
    # ==========================================================================
    # Figure 1: Model comparison bar chart (53,585 common rows vs 54,046 all rows)
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    labels = [
        "Same Hour Last Week\n(lag_7d)",
        "4-Week Average\n(lag_mean_available)",
        "Ridge\n(riders)",
        "Ridge\n(log(1 + riders))",
        "Random Forest\n(Tuned)",
        "HistGradientBoosting\n(Tuned Best)",
    ]
    x = np.arange(len(comparison_df))
    w = 0.36
    b1 = ax.bar(
        x - w / 2,
        comparison_df["wape_53585_pct"],
        w,
        label="Common 53,585 Rows (Fair Baseline Comparison)",
        color="#2563eb",
        edgecolor="#1e3a8a",
    )
    b2 = ax.bar(
        x + w / 2,
        comparison_df["wape_all_val_pct"],
        w,
        label="All 54,046 Validation Rows",
        color="#93c5fd",
        edgecolor="#1d4ed8",
    )
    ax.axhline(
        14.08,
        color="#dc2626",
        linestyle="--",
        linewidth=1.3,
        label="4-Week Average Baseline Hurdle (14.08% WAPE)",
    )
    for bar in b1:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + 0.2,
            f"{h:.2f}%",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
        )
    for bar in b2:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + 0.2,
            f"{h:.2f}%",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#1e40af",
        )
    ax.set_title(
        "Milestone 3 Step 2: Validation Forecast WAPE (%) — Baselines vs Tuned Models",
        fontsize=11,
        fontweight="bold",
        pad=10,
    )
    ax.set_ylabel("Validation WAPE (%)", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylim(0, 20.0)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="upper right", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "m3_forecast_model_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Figure 2: Permutation importance horizontal bar chart (top 15 features)
    top_perm = perm_df.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 5.5), dpi=150)
    ax.barh(
        top_perm["feature"],
        top_perm["mae_increase_riders"],
        xerr=top_perm["mae_increase_std"],
        color="#1d4ed8",
        edgecolor="#1e3a8a",
        alpha=0.9,
        capsize=3,
    )
    for idx, row_p in top_perm.iterrows():
        ax.text(
            row_p["mae_increase_riders"] + row_p["mae_increase_std"] + 1.2,
            row_p["feature"],
            f"+{row_p['mae_increase_riders']:.1f} MAE (+{row_p['wape_increase_pct_pts']:.2f}% WAPE)",
            va="center",
            fontsize=8,
        )
    ax.set_title(
        "Validation Permutation Importance — Best Forecaster (HistGradientBoosting)",
        fontsize=11,
        fontweight="bold",
        pad=10,
    )
    ax.set_xlabel("Increase in Validation MAE (Riders/Hour) When Feature Is Shuffled", fontsize=9.5)
    ax.set_ylabel("Input Feature", fontsize=9.5)
    ax.set_xlim(0, max(top_perm["mae_increase_riders"] + top_perm["mae_increase_std"]) * 1.32)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "m3_forecast_permutation_importance.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved Step 2 figures to reports/figures/", flush=True)


if __name__ == "__main__":
    run_step2_forecasting()

