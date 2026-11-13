"""
Milestone 3 — Step 5: Single Final Test Set Evaluation & Model Cards (src/run_final_test.py)

========================================================================================
PRE-SPECIFIED FINAL TEST RUN PROTOCOL (FIXED BEFORE RUNNING ON TEST SET)
========================================================================================
1. Forecasting Models Evaluated on Test Set (August–September 2026):
   - Main Model: `HistGradientBoostingRegressor` with the validation-selected settings
     (`loss='poisson', learning_rate=0.05, max_leaf_nodes=127, min_samples_leaf=25,
     l2_regularization=1.0, max_iter=300, early_stopping=True, validation_fraction=0.1,
     n_iter_no_change=15, random_state=42`), retrained on January to July 2026
     (`train + val` combined, 179,491 rows).
   - Baseline: 4-week historical average (`lag_mean_available`, no training needed).

2. Classification Models Evaluated on Active Test Hours (`trips_running > 0`):
   - Main Approach: `Forecast ÷ Trips` at the fixed `0.96 × threshold_p75` cutoff
     (`pred_hgb_retrained / trips_running > 0.96 * threshold_p75`).
   - Comparison Benchmark: `HistGradientBoostingClassifier` at the fixed `0.63` probability
     cutoff (`learning_rate=0.08, max_leaf_nodes=127, min_samples_leaf=30,
     l2_regularization=5.0, class_weight='balanced', max_iter=300, early_stopping=True,
     validation_fraction=0.1, n_iter_no_change=15, random_state=42`), retrained on
     January to July 2026 (`train + val` active-service rows, 177,502 rows).
   - Baseline: Rule B (`lag_mean_available / trips_running > 1.00 * threshold_p75`).
   - Labels: Keep the per-route `threshold_p75` thresholds fitted on January to May 2026
     (stored in `test_features.parquet`). Recomputing them would change what counts as
     "high" in the test set.

3. Required Test Set Reporting:
   - Forecasting: MAE, RMSE, WAPE, and Bias (`predicted minus actual`), reported overall,
     per week, and per route (plus day type and canonical time band).
   - Classification: PR-AUC (cutoff-free), Precision at Rule B's exact test-set workload,
     and F1 (plus Precision, Recall, and flagged hours) at the fixed cut-offs (`0.96×` and `0.63`).
   - Outlier & Storm Handling: Report everything both WITH and WITHOUT the `M35` surge hours
     (`is_outlier == True`, 6 hours on Saturday 19 September 2026). State explicitly that
     the test period (August–September 2026) has no storm days (0 storm days).

4. Strict Single-Run & Model Card Rules:
   - Load test data exactly once via `load_dataset('test', final=True)`, which logs the
     official test evaluation to `reports/test_runs.log`.
   - Save each final retrained model with its complete model card (training dates, features,
     settings, and validation and test scores) to `models/final_forecaster.joblib`,
     `models/final_classifier.joblib`, `models/model_cards.json`, and `reports/model_cards.md`.
========================================================================================
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import precision_recall_curve
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluate import (
    compute_classification_metrics,
    compute_forecast_metrics,
    evaluate_classification,
    evaluate_forecasting,
    load_dataset,
    print_classification_summary,
    print_forecasting_summary,
)
from src.train_classification import metrics_at_fixed_workload
from src.train_forecasting import ALL_FEATURES

MODELS_DIR = ROOT / "models"
TAB_DIR = ROOT / "reports" / "tables"
FIG_DIR = ROOT / "reports" / "figures"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)


def run_step5_final_test() -> None:
    print("=" * 88, flush=True)
    print("MILESTONE 3 — STEP 5: SINGLE OFFICIAL FINAL TEST EVALUATION (AUG–SEP 2026)", flush=True)
    print("=" * 88, flush=True)

    # 1. Load Train (Jan–May), Validation (Jun–Jul), and Official Test (Aug–Sep, final=True ONCE)
    train_df = load_dataset("train")
    val_df = load_dataset("val")
    test_df = load_dataset(
        "test",
        final=True,
        caller="src/run_final_test.py::run_step5_final_test (Single Official Test Run)",
    )

    train_val_df = pd.concat([train_df, val_df], ignore_index=True)
    n_test_storms = int(test_df["is_storm"].sum()) if "is_storm" in test_df.columns else 0
    n_test_outliers = int(test_df["is_outlier"].sum()) if "is_outlier" in test_df.columns else 0

    print(
        f"Combined Train + Val (Jan–Jul 2026): {len(train_val_df):,} rows "
        f"({train_val_df['date'].min()} to {train_val_df['date'].max()})",
        flush=True,
    )
    print(
        f"Official Test Set (Aug–Sep 2026)   : {len(test_df):,} rows "
        f"({test_df['date'].min()} to {test_df['date'].max()}) | "
        f"M35 surge hours (is_outlier=True): {n_test_outliers} | Storm days: {n_test_storms}",
        flush=True,
    )

    # ==========================================================================
    # PART 1: RETRAIN CHOSEN FORECASTER ON JANUARY TO JULY & SCORE TEST SET
    # ==========================================================================
    print("\n[1/4] Retraining HistGradientBoostingRegressor on Jan–Jul 2026 (179,491 rows)...", flush=True)
    t0 = time.time()
    base_preprocessor = joblib.load(MODELS_DIR / "preprocessor.joblib")
    prep_forecast_tv = clone(base_preprocessor)
    X_tv_forecast = prep_forecast_tv.fit_transform(train_val_df[ALL_FEATURES])
    y_tv_forecast = train_val_df["ridership"].values.astype(float)

    hgb_forecaster_settings = {
        "loss": "poisson",
        "learning_rate": 0.05,
        "max_leaf_nodes": 127,
        "min_samples_leaf": 25,
        "l2_regularization": 1.0,
        "max_iter": 300,
        "early_stopping": True,
        "validation_fraction": 0.1,
        "n_iter_no_change": 15,
        "random_state": 42,
    }
    final_hgb_reg = HistGradientBoostingRegressor(**hgb_forecaster_settings)
    final_hgb_reg.fit(X_tv_forecast, y_tv_forecast)
    fit_sec_reg = round(time.time() - t0, 2)
    print(f"Retrained HistGradientBoostingRegressor in {fit_sec_reg:.2f}s (n_iter_={final_hgb_reg.n_iter_})", flush=True)

    final_forecaster_pipe = Pipeline([
        ("preprocessor", prep_forecast_tv),
        ("regressor", final_hgb_reg),
    ])

    test_eval_df = test_df.copy()
    test_eval_df["pred_hgb"] = np.clip(final_forecaster_pipe.predict(test_eval_df[ALL_FEATURES]), 0.0, None)
    test_eval_df["pred_4wk"] = test_eval_df["lag_mean_available"]

    # Common test rows where 4-week average baseline is non-null
    common_test_mask = test_eval_df["lag_mean_available"].notnull().values
    no_outlier_mask = (~test_eval_df["is_outlier"].astype(bool)).values

    # Build Overall Forecasting Comparison Table (With & Without M35 Surge Hours; Common vs All Rows)
    forecast_overall_rows = []
    for subset_label, outlier_mask_arr in [
        ("With M35 Surge Hours (All Test Hours)", np.ones(len(test_eval_df), dtype=bool)),
        ("Without M35 Surge Hours (Excluding 6-hr 19 Sep M35 Surge)", no_outlier_mask),
    ]:
        sub_common = test_eval_df[common_test_mask & outlier_mask_arr]
        sub_all = test_eval_df[outlier_mask_arr]

        m_4wk_c = compute_forecast_metrics(sub_common["ridership"].values, sub_common["pred_4wk"].values)
        m_hgb_c = compute_forecast_metrics(sub_common["ridership"].values, sub_common["pred_hgb"].values)
        m_hgb_a = compute_forecast_metrics(sub_all["ridership"].values, sub_all["pred_hgb"].values)

        forecast_overall_rows.append({
            "evaluation_subset": subset_label,
            "model_name": "4-Week Average Baseline (lag_mean_available)",
            "training_window": "None (4-week rolling lookback)",
            "n_eval_common": m_4wk_c["n_eval"],
            "mae_common": m_4wk_c["mae"],
            "rmse_common": m_4wk_c["rmse"],
            "wape_common_pct": m_4wk_c["wape_pct"],
            "bias_common_pred_minus_actual": m_4wk_c["bias_pred_minus_actual"],
            "n_eval_all_test": m_4wk_c["n_eval"],
            "mae_all_test": m_4wk_c["mae"],
            "rmse_all_test": m_4wk_c["rmse"],
            "wape_all_test_pct": m_4wk_c["wape_pct"],
            "bias_all_test_pred_minus_actual": m_4wk_c["bias_pred_minus_actual"],
            "wape_diff_vs_4wk_pct_pts": 0.0,
            "storm_days_note": "0 storm days in Aug–Sep 2026 test window",
        })
        forecast_overall_rows.append({
            "evaluation_subset": subset_label,
            "model_name": "HistGradientBoosting (Retrained on Jan–Jul 2026)",
            "training_window": "2026-01-04 to 2026-07-31 (179,491 rows)",
            "n_eval_common": m_hgb_c["n_eval"],
            "mae_common": m_hgb_c["mae"],
            "rmse_common": m_hgb_c["rmse"],
            "wape_common_pct": m_hgb_c["wape_pct"],
            "bias_common_pred_minus_actual": m_hgb_c["bias_pred_minus_actual"],
            "n_eval_all_test": m_hgb_a["n_eval"],
            "mae_all_test": m_hgb_a["mae"],
            "rmse_all_test": m_hgb_a["rmse"],
            "wape_all_test_pct": m_hgb_a["wape_pct"],
            "bias_all_test_pred_minus_actual": m_hgb_a["bias_pred_minus_actual"],
            "wape_diff_vs_4wk_pct_pts": round(m_hgb_c["wape_pct"] - m_4wk_c["wape_pct"], 2),
            "storm_days_note": "0 storm days in Aug–Sep 2026 test window",
        })

    forecast_overall_df = pd.DataFrame(forecast_overall_rows)
    forecast_overall_df.to_csv(TAB_DIR / "m3_test_forecast_overall.csv", index=False)
    print("\n--- TEST SET FORECASTING OVERALL (WITH & WITHOUT M35 SURGE HOURS) ---", flush=True)
    print(forecast_overall_df.to_string(index=False), flush=True)

    # Run shared evaluate_forecasting on common test rows for day-type and time-band breakdowns
    test_common_df = test_eval_df[common_test_mask].copy()
    res_test_hgb = evaluate_forecasting(
        df=test_common_df,
        y_true_col="ridership",
        y_pred_col="pred_hgb",
        model_name="HistGradientBoosting (Retrained Jan–Jul, Test Set)",
        save_prefix="m3_test_eval_hgb_forecast",
        out_dir=TAB_DIR,
    )
    print_forecasting_summary(res_test_hgb)

    evaluate_forecasting(
        df=test_common_df,
        y_true_col="ridership",
        y_pred_col="pred_4wk",
        model_name="4-Week Average Baseline (Test Set)",
        save_prefix="m3_test_eval_4wk_forecast",
        out_dir=TAB_DIR,
    )

    # Weekly Test Forecasting Breakdown (With and Without M35 Surge Hours)
    test_common_df["dt"] = pd.to_datetime(test_common_df["date"])
    min_dt = pd.Timestamp("2026-08-01")
    test_common_df["week_num"] = ((test_common_df["dt"] - min_dt).dt.days // 7) + 1

    weekly_rows = []
    for subset_label, sub_df in [
        ("With M35 Surge Hours", test_common_df),
        ("Without M35 Surge Hours", test_common_df[~test_common_df["is_outlier"].astype(bool)]),
    ]:
        for wk, grp in sub_df.groupby("week_num"):
            m4 = compute_forecast_metrics(grp["ridership"].values, grp["pred_4wk"].values)
            mh = compute_forecast_metrics(grp["ridership"].values, grp["pred_hgb"].values)
            w_diff = round(mh["wape_pct"] - m4["wape_pct"], 2)
            outcome = "Win" if w_diff < -0.02 else ("Tie" if abs(w_diff) <= 0.02 else "Loss")
            weekly_rows.append({
                "evaluation_subset": subset_label,
                "week_num": int(wk),
                "week_start": str(grp["date"].min()),
                "week_end": str(grp["date"].max()),
                "n_hours": int(len(grp)),
                "mean_actual_riders": round(float(grp["ridership"].mean()), 2),
                "mae_4wk": m4["mae"],
                "rmse_4wk": m4["rmse"],
                "wape_4wk_pct": m4["wape_pct"],
                "bias_4wk_pred_minus_actual": m4["bias_pred_minus_actual"],
                "mae_hgb": mh["mae"],
                "rmse_hgb": mh["rmse"],
                "wape_hgb_pct": mh["wape_pct"],
                "bias_hgb_pred_minus_actual": mh["bias_pred_minus_actual"],
                "wape_diff_hgb_minus_4wk": w_diff,
                "weekly_outcome": outcome,
            })

    weekly_test_df = pd.DataFrame(weekly_rows)
    weekly_test_df.to_csv(TAB_DIR / "m3_test_forecast_by_week.csv", index=False)
    print("\n--- TEST SET FORECASTING BY WEEK (WITH & WITHOUT M35 SURGE HOURS) ---", flush=True)
    print(weekly_test_df.to_string(index=False), flush=True)

    # Route-Level Test Forecasting Breakdown (With and Without M35 Surge Hours)
    route_rows = []
    for subset_label, sub_df in [
        ("With M35 Surge Hours", test_common_df),
        ("Without M35 Surge Hours", test_common_df[~test_common_df["is_outlier"].astype(bool)]),
    ]:
        for r_id, grp in sub_df.groupby("route"):
            m4 = compute_forecast_metrics(grp["ridership"].values, grp["pred_4wk"].values)
            mh = compute_forecast_metrics(grp["ridership"].values, grp["pred_hgb"].values)
            w_diff = round(mh["wape_pct"] - m4["wape_pct"], 2)
            route_rows.append({
                "evaluation_subset": subset_label,
                "route": r_id,
                "n_eval": int(len(grp)),
                "total_actual": round(float(grp["ridership"].sum()), 0),
                "mae_4wk": m4["mae"],
                "rmse_4wk": m4["rmse"],
                "wape_4wk_pct": m4["wape_pct"],
                "bias_4wk_pred_minus_actual": m4["bias_pred_minus_actual"],
                "mae_hgb": mh["mae"],
                "rmse_hgb": mh["rmse"],
                "wape_hgb_pct": mh["wape_pct"],
                "bias_hgb_pred_minus_actual": mh["bias_pred_minus_actual"],
                "wape_diff_hgb_minus_4wk": w_diff,
                "hgb_improves_wape": bool(w_diff < 0),
            })

    route_test_df = pd.DataFrame(route_rows)
    route_test_df.to_csv(TAB_DIR / "m3_test_forecast_by_route.csv", index=False)
    sub_r_with = route_test_df[route_test_df["evaluation_subset"] == "With M35 Surge Hours"]
    sub_r_no = route_test_df[route_test_df["evaluation_subset"] == "Without M35 Surge Hours"]
    print(
        f"\nRoute-Level Test Summary: HGB improves WAPE on "
        f"{int(sub_r_with['hgb_improves_wape'].sum())}/41 routes (with M35 surge) and "
        f"{int(sub_r_no['hgb_improves_wape'].sum())}/41 routes (without M35 surge).",
        flush=True,
    )
    print("M35 Route Row With vs Without Surge Hours:", flush=True)
    print(route_test_df[route_test_df["route"] == "M35"].to_string(index=False), flush=True)

    # ==========================================================================
    # PART 2: RETRAIN CHOSEN CLASSIFIER ON JANUARY TO JULY & SCORE TEST SET
    # ==========================================================================
    print("\n[2/4] Retraining HistGradientBoostingClassifier on Jan–Jul 2026 active hours...", flush=True)
    t0 = time.time()
    tv_active_mask = (train_val_df["trips_running"] > 0) & train_val_df["threshold_p75"].notnull()
    tv_clf = train_val_df[tv_active_mask].copy()

    prep_clf_tv = clone(base_preprocessor)
    X_tv_clf = prep_clf_tv.fit_transform(tv_clf[ALL_FEATURES])
    y_tv_clf = tv_clf["high_demand_per_trip"].values.astype(int)

    hgb_clf_settings = {
        "learning_rate": 0.08,
        "max_leaf_nodes": 127,
        "min_samples_leaf": 30,
        "l2_regularization": 5.0,
        "class_weight": "balanced",
        "max_iter": 300,
        "early_stopping": True,
        "validation_fraction": 0.1,
        "n_iter_no_change": 15,
        "random_state": 42,
    }
    final_hgb_clf = HistGradientBoostingClassifier(**hgb_clf_settings)
    final_hgb_clf.fit(X_tv_clf, y_tv_clf)
    fit_sec_clf = round(time.time() - t0, 2)
    print(f"Retrained HistGradientBoostingClassifier in {fit_sec_clf:.2f}s (n_iter_={final_hgb_clf.n_iter_})", flush=True)

    final_classifier_pipe = Pipeline([
        ("preprocessor", prep_clf_tv),
        ("classifier", final_hgb_clf),
    ])

    # Active-service test hours (keeping the January–May per-route threshold_p75 fixed!)
    te_active_mask = (test_eval_df["trips_running"] > 0) & test_eval_df["threshold_p75"].notnull()
    te_clf = test_eval_df[te_active_mask].copy()

    # 1. Rule B Baseline: lag_mean_available / trips_running > 1.00 * threshold_p75
    te_clf["lag_mean_filled"] = te_clf["lag_mean_available"].fillna(te_clf["lag_7d"]).fillna(150.0)
    te_clf["ratio_rule_b"] = (te_clf["lag_mean_filled"] / te_clf["trips_running"]) / te_clf["threshold_p75"]
    te_clf["pred_rule_b"] = (te_clf["ratio_rule_b"] > 1.00).astype(int)
    te_clf["score_rule_b"] = np.clip(te_clf["ratio_rule_b"] / 2.0, 0.0, 1.0)

    # 2. Main Approach: Forecast ÷ Trips at fixed 0.96 * threshold_p75
    #    (Also compute 1.00x unadjusted reference to document how Jan-Jul retraining changed cutoff behavior)
    te_clf["ratio_forecast_div_trips"] = (te_clf["pred_hgb"] / te_clf["trips_running"]) / te_clf["threshold_p75"]
    te_clf["pred_div_096"] = (te_clf["ratio_forecast_div_trips"] > 0.96).astype(int)
    te_clf["pred_div_100_ref"] = (te_clf["ratio_forecast_div_trips"] > 1.00).astype(int)
    te_clf["score_div"] = np.clip(te_clf["ratio_forecast_div_trips"] / 2.0, 0.0, 1.0)

    # 3. Comparison Benchmark: HistGradientBoostingClassifier at fixed 0.63 probability cutoff
    te_clf["prob_hgb_clf"] = final_classifier_pipe.predict_proba(te_clf[ALL_FEATURES])[:, 1]
    te_clf["pred_hgb_clf_063"] = (te_clf["prob_hgb_clf"] >= 0.63).astype(int)

    # Common active test hours where lag_mean_available is non-null
    common_clf_mask = te_clf["lag_mean_available"].notnull().values
    no_outlier_clf_mask = (~te_clf["is_outlier"].astype(bool)).values

    clf_overall_rows = []
    for subset_label, out_mask in [
        ("With M35 Surge Hours (All Active Test Hours)", np.ones(len(te_clf), dtype=bool)),
        ("Without M35 Surge Hours (Excluding 6-hr 19 Sep M35 Surge)", no_outlier_clf_mask),
    ]:
        sub_c = te_clf[common_clf_mask & out_mask]
        sub_a = te_clf[out_mask]
        y_c = sub_c["high_demand_per_trip"].values.astype(int)
        y_a = sub_a["high_demand_per_trip"].values.astype(int)

        # Rule B's exact workload on this test subset
        k_rule_b_test = int(sub_c["pred_rule_b"].sum())

        for model_name, role, cutoff_str, pred_col, raw_score_col, score_col in [
            (
                "Baseline Rule B: 4-Week Avg ÷ Trips > Threshold",
                "Baseline Benchmark",
                "ratio > 1.00 * threshold_p75 (Jan–May thresholds fixed)",
                "pred_rule_b",
                "ratio_rule_b",
                "score_rule_b",
            ),
            (
                "Forecast ÷ Trips: Official Rule (0.96 × Threshold)",
                "Main Approach (Official Test Candidate)",
                "pred_hgb / trips_running > 0.96 * threshold_p75 (Fixed Cutoff)",
                "pred_div_096",
                "ratio_forecast_div_trips",
                "score_div",
            ),
            (
                "HistGradientBoosting Classifier (Cutoff = 0.63)",
                "Comparison Benchmark (Official Test Candidate)",
                "prob >= 0.63 (Fixed Cutoff, Retrained Jan–Jul)",
                "pred_hgb_clf_063",
                "prob_hgb_clf",
                "prob_hgb_clf",
            ),
            (
                "Diagnostic Post-Hoc Check: Forecast ÷ Trips at 1.00 × Threshold",
                "Post-Hoc Diagnostic Only (Showing Effect of Zero Bias After Jan–Jul Retraining)",
                "pred_hgb / trips_running > 1.00 * threshold_p75 (Not Official Rule)",
                "pred_div_100_ref",
                "ratio_forecast_div_trips",
                "score_div",
            ),
        ]:
            mc = compute_classification_metrics(y_c, sub_c[pred_col].values, sub_c[score_col].values)
            ma = compute_classification_metrics(y_a, sub_a[pred_col].values, sub_a[score_col].values)
            mw = metrics_at_fixed_workload(y_c, sub_c[raw_score_col].values, k_flagged=k_rule_b_test)

            clf_overall_rows.append({
                "evaluation_subset": subset_label,
                "model_name": model_name,
                "role": role,
                "fixed_cutoff_rule": cutoff_str,
                "n_eval_common": mc["n_eval"],
                "actual_pos_common": mc["actual_positive"],
                "pr_auc_common": mc["pr_auc"],
                "roc_auc_common": mc["roc_auc"],
                "rule_b_workload_hours": k_rule_b_test,
                "precision_at_rule_b_workload": mw["precision"] if "Rule B" not in model_name else mc["precision"],
                "f1_at_rule_b_workload": mw["f1"] if "Rule B" not in model_name else mc["f1"],
                "pred_pos_at_fixed_cutoff": mc["pred_positive"],
                "precision_at_fixed_cutoff": mc["precision"],
                "recall_at_fixed_cutoff": mc["recall"],
                "f1_at_fixed_cutoff": mc["f1"],
                "n_eval_all_active": ma["n_eval"],
                "pr_auc_all_active": ma["pr_auc"],
                "f1_all_active": ma["f1"],
                "storm_days_note": "0 storm days in Aug–Sep 2026 test window",
            })

    clf_overall_df = pd.DataFrame(clf_overall_rows)
    clf_overall_df.to_csv(TAB_DIR / "m3_test_classification_overall.csv", index=False)
    print("\n--- TEST SET CLASSIFICATION OVERALL (WITH & WITHOUT M35 SURGE HOURS) ---", flush=True)
    print(clf_overall_df.to_string(index=False), flush=True)

    # Run shared evaluate_classification on common active test rows (automatically splits All Hours vs Without M35 Surge)
    te_clf_common = te_clf[common_clf_mask].copy()
    res_test_div = evaluate_classification(
        df=te_clf_common,
        y_true_col="high_demand_per_trip",
        y_pred_col="pred_div_096",
        y_prob_col="score_div",
        model_name="Forecast ÷ Trips (Official 0.96x Rule, Retrained Jan–Jul, Test Set)",
        save_prefix="m3_test_eval_forecast_div_trips",
        out_dir=TAB_DIR,
    )
    print_classification_summary(res_test_div)

    res_test_hgb_clf = evaluate_classification(
        df=te_clf_common,
        y_true_col="high_demand_per_trip",
        y_pred_col="pred_hgb_clf_063",
        y_prob_col="prob_hgb_clf",
        model_name="HistGradientBoosting Classifier (Fixed 0.63 Cutoff, Retrained Jan–Jul, Test Set)",
        save_prefix="m3_test_eval_hgb_clf",
        out_dir=TAB_DIR,
    )
    print_classification_summary(res_test_hgb_clf)

    evaluate_classification(
        df=te_clf_common,
        y_true_col="high_demand_per_trip",
        y_pred_col="pred_rule_b",
        y_prob_col="score_rule_b",
        model_name="Baseline Rule B (4-Week Avg ÷ Trips > Threshold, Test Set)",
        save_prefix="m3_test_eval_rule_b",
        out_dir=TAB_DIR,
    )

    # ==========================================================================
    # PART 3: SAVE FINAL MODELS & MODEL CARDS
    # ==========================================================================
    print("\n[3/4] Saving final models and model cards...", flush=True)
    f_with = forecast_overall_df[
        (forecast_overall_df["evaluation_subset"].str.startswith("With M35"))
        & (forecast_overall_df["model_name"].str.startswith("HistGradientBoosting"))
    ].iloc[0]
    f_no = forecast_overall_df[
        (forecast_overall_df["evaluation_subset"].str.startswith("Without M35"))
        & (forecast_overall_df["model_name"].str.startswith("HistGradientBoosting"))
    ].iloc[0]
    f_4wk_with = forecast_overall_df[
        (forecast_overall_df["evaluation_subset"].str.startswith("With M35"))
        & (forecast_overall_df["model_name"].str.startswith("4-Week"))
    ].iloc[0]
    f_4wk_no = forecast_overall_df[
        (forecast_overall_df["evaluation_subset"].str.startswith("Without M35"))
        & (forecast_overall_df["model_name"].str.startswith("4-Week"))
    ].iloc[0]

    c_div_with = clf_overall_df[
        (clf_overall_df["evaluation_subset"].str.startswith("With M35"))
        & (clf_overall_df["model_name"].str.startswith("Forecast ÷ Trips"))
    ].iloc[0]
    c_div_no = clf_overall_df[
        (clf_overall_df["evaluation_subset"].str.startswith("Without M35"))
        & (clf_overall_df["model_name"].str.startswith("Forecast ÷ Trips"))
    ].iloc[0]
    c_hgb_with = clf_overall_df[
        (clf_overall_df["evaluation_subset"].str.startswith("With M35"))
        & (clf_overall_df["model_name"].str.startswith("HistGradientBoosting"))
    ].iloc[0]
    c_hgb_no = clf_overall_df[
        (clf_overall_df["evaluation_subset"].str.startswith("Without M35"))
        & (clf_overall_df["model_name"].str.startswith("HistGradientBoosting"))
    ].iloc[0]

    forecaster_card = {
        "model_name": "HistGradientBoostingRegressor (Final Retrained Ridership Forecaster)",
        "artifact_path": "models/final_forecaster.joblib",
        "task": "Route-hour ridership forecasting (boardings per hour) and Forecast ÷ Trips high-demand alerting",
        "training_date_window": "2026-01-04 to 2026-07-31 (Train + Validation combined)",
        "n_training_rows": int(len(train_val_df)),
        "n_routes": 41,
        "input_features_count": len(ALL_FEATURES),
        "input_features": ALL_FEATURES,
        "transformed_feature_dimension": int(X_tv_forecast.shape[1]),
        "hyperparameters": hgb_forecaster_settings,
        "actual_iterations_fitted": int(final_hgb_reg.n_iter_),
        "validation_scores_jan_may_fit": {
            "window": "2026-06-01 to 2026-07-31 (53,585 common rows / 54,046 all rows)",
            "mae_common": 33.00,
            "rmse_common": 56.05,
            "wape_common_pct": 13.03,
            "bias_common_pred_minus_actual": 8.83,
            "baseline_4wk_wape_pct": 14.08,
        },
        "test_scores_aug_sep_2026": {
            "window": "2026-08-01 to 2026-09-30 (0 storm days)",
            "with_m35_surge_hours": {
                "n_eval_common": int(f_with["n_eval_common"]),
                "mae_common": float(f_with["mae_common"]),
                "rmse_common": float(f_with["rmse_common"]),
                "wape_common_pct": float(f_with["wape_common_pct"]),
                "bias_common_pred_minus_actual": float(f_with["bias_common_pred_minus_actual"]),
                "baseline_4wk_wape_pct": float(f_4wk_with["wape_common_pct"]),
                "wape_diff_vs_4wk_pct_pts": float(f_with["wape_diff_vs_4wk_pct_pts"]),
            },
            "without_m35_surge_hours": {
                "n_eval_common": int(f_no["n_eval_common"]),
                "mae_common": float(f_no["mae_common"]),
                "rmse_common": float(f_no["rmse_common"]),
                "wape_common_pct": float(f_no["wape_common_pct"]),
                "bias_common_pred_minus_actual": float(f_no["bias_common_pred_minus_actual"]),
                "baseline_4wk_wape_pct": float(f_4wk_no["wape_common_pct"]),
                "wape_diff_vs_4wk_pct_pts": float(f_no["wape_diff_vs_4wk_pct_pts"]),
            },
        },
        "forecast_div_trips_classification": {
            "official_rule": "pred_hgb / trips_running > 0.96 * threshold_p75 (Jan–May thresholds kept fixed)",
            "validation_scores": {
                "pr_auc": 0.7205,
                "precision_at_rule_b_workload_13081": 0.6801,
                "f1_at_096x": 0.6998,
                "precision_at_096x": 0.6054,
                "recall_at_096x": 0.8292,
            },
            "test_scores_with_m35_surge": {
                "pr_auc": float(c_div_with["pr_auc_common"]),
                "precision_at_rule_b_workload": float(c_div_with["precision_at_rule_b_workload"]),
                "f1_at_rule_b_workload": float(c_div_with["f1_at_rule_b_workload"]),
                "pred_pos_at_096x": int(c_div_with["pred_pos_at_fixed_cutoff"]),
                "precision_at_096x": float(c_div_with["precision_at_fixed_cutoff"]),
                "recall_at_096x": float(c_div_with["recall_at_fixed_cutoff"]),
                "f1_at_096x": float(c_div_with["f1_at_fixed_cutoff"]),
            },
            "test_scores_without_m35_surge": {
                "pr_auc": float(c_div_no["pr_auc_common"]),
                "precision_at_rule_b_workload": float(c_div_no["precision_at_rule_b_workload"]),
                "f1_at_rule_b_workload": float(c_div_no["f1_at_rule_b_workload"]),
                "pred_pos_at_096x": int(c_div_no["pred_pos_at_fixed_cutoff"]),
                "precision_at_096x": float(c_div_no["precision_at_fixed_cutoff"]),
                "recall_at_096x": float(c_div_no["recall_at_fixed_cutoff"]),
                "f1_at_096x": float(c_div_no["f1_at_fixed_cutoff"]),
            },
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    classifier_card = {
        "model_name": "HistGradientBoostingClassifier (Final Retrained High-Demand-per-Trip Classifier)",
        "artifact_path": "models/final_classifier.joblib",
        "task": "Binary classification of high_demand_per_trip (riders_per_trip > Jan–May threshold_p75 on active hours)",
        "training_date_window": "2026-01-04 to 2026-07-31 (Train + Validation active-service hours)",
        "n_training_rows": int(len(tv_clf)),
        "n_routes": 41,
        "input_features_count": len(ALL_FEATURES),
        "input_features": ALL_FEATURES,
        "transformed_feature_dimension": int(X_tv_clf.shape[1]),
        "hyperparameters": hgb_clf_settings,
        "fixed_probability_cutoff": 0.63,
        "threshold_label_rule": "Per-route × day_type 75th percentile thresholds (threshold_p75) kept fixed from Jan–May 2026",
        "actual_iterations_fitted": int(final_hgb_clf.n_iter_),
        "validation_scores_jan_may_fit": {
            "window": "2026-06-01 to 2026-07-31 (53,406 common active rows)",
            "pr_auc": 0.7290,
            "precision_at_rule_b_workload_13081": 0.6610,
            "f1_at_063": 0.6862,
            "precision_at_063": 0.5854,
            "recall_at_063": 0.8290,
        },
        "test_scores_aug_sep_2026": {
            "window": "2026-08-01 to 2026-09-30 (0 storm days)",
            "with_m35_surge_hours": {
                "n_eval_common": int(c_hgb_with["n_eval_common"]),
                "pr_auc": float(c_hgb_with["pr_auc_common"]),
                "roc_auc": float(c_hgb_with["roc_auc_common"]),
                "precision_at_rule_b_workload": float(c_hgb_with["precision_at_rule_b_workload"]),
                "f1_at_rule_b_workload": float(c_hgb_with["f1_at_rule_b_workload"]),
                "pred_pos_at_063": int(c_hgb_with["pred_pos_at_fixed_cutoff"]),
                "precision_at_063": float(c_hgb_with["precision_at_fixed_cutoff"]),
                "recall_at_063": float(c_hgb_with["recall_at_fixed_cutoff"]),
                "f1_at_063": float(c_hgb_with["f1_at_fixed_cutoff"]),
            },
            "without_m35_surge_hours": {
                "n_eval_common": int(c_hgb_no["n_eval_common"]),
                "pr_auc": float(c_hgb_no["pr_auc_common"]),
                "roc_auc": float(c_hgb_no["roc_auc_common"]),
                "precision_at_rule_b_workload": float(c_hgb_no["precision_at_rule_b_workload"]),
                "f1_at_rule_b_workload": float(c_hgb_no["f1_at_rule_b_workload"]),
                "pred_pos_at_063": int(c_hgb_no["pred_pos_at_fixed_cutoff"]),
                "precision_at_063": float(c_hgb_no["precision_at_fixed_cutoff"]),
                "recall_at_063": float(c_hgb_no["recall_at_fixed_cutoff"]),
                "f1_at_063": float(c_hgb_no["f1_at_fixed_cutoff"]),
            },
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    joblib.dump(
        {"pipeline": final_forecaster_pipe, "model_card": forecaster_card},
        MODELS_DIR / "final_forecaster.joblib",
        compress=3,
    )
    joblib.dump(
        {"pipeline": final_classifier_pipe, "model_card": classifier_card},
        MODELS_DIR / "final_classifier.joblib",
        compress=3,
    )

    cards_bundle = {
        "final_forecaster": forecaster_card,
        "final_classifier": classifier_card,
    }
    with open(MODELS_DIR / "model_cards.json", "w", encoding="utf-8") as f_json:
        json.dump(cards_bundle, f_json, indent=2)

    # Also write human-readable reports/model_cards.md
    md_lines = [
        "# Final Model Cards (Milestone 3 — Step 5)",
        "",
        "## 1. Ridership Forecaster & Main Alerting Model (`models/final_forecaster.joblib`)",
        f"- **Model:** `{forecaster_card['model_name']}`",
        f"- **Training Window:** `{forecaster_card['training_date_window']}` (`{forecaster_card['n_training_rows']:,}` route-hours across `{forecaster_card['n_routes']}` routes)",
        f"- **Input Features ({forecaster_card['input_features_count']} columns -> {forecaster_card['transformed_feature_dimension']} transformed):** `{', '.join(ALL_FEATURES)}`",
        f"- **Chosen Settings (Locked on Validation):** `{forecaster_card['hyperparameters']}` (`n_iter_ = {forecaster_card['actual_iterations_fitted']}`)",
        "- **Validation Scores (Jun–Jul 2026, 53,585 common rows):**",
        f"  - Forecaster: `WAPE = 13.03%`, `MAE = 33.00`, `RMSE = 56.05`, `Bias = +8.83` (vs 4-week average baseline `14.08% WAPE`)",
        f"  - `Forecast ÷ Trips` (`0.96 × threshold_p75`): `PR-AUC = 0.7205`, `Precision @ 13,081 hrs = 0.6801`, `Max-F1 = 0.6998`",
        "- **Test Scores (Aug–Sep 2026, 0 storm days):**",
        f"  - **Forecasting (With M35 Surge, `{f_with['n_eval_common']:,}` common rows):** `WAPE = {f_with['wape_common_pct']:.2f}%`, `MAE = {f_with['mae_common']:.2f}`, `RMSE = {f_with['rmse_common']:.2f}`, `Bias = {f_with['bias_common_pred_minus_actual']:+.2f}` (vs 4-week average `{f_4wk_with['wape_common_pct']:.2f}% WAPE`, `{f_with['wape_diff_vs_4wk_pct_pts']:+.2f} pp`)",
        f"  - **Forecasting (Without M35 Surge, `{f_no['n_eval_common']:,}` common rows):** `WAPE = {f_no['wape_common_pct']:.2f}%`, `MAE = {f_no['mae_common']:.2f}`, `RMSE = {f_no['rmse_common']:.2f}`, `Bias = {f_no['bias_common_pred_minus_actual']:+.2f}` (vs 4-week average `{f_4wk_no['wape_common_pct']:.2f}% WAPE`, `{f_no['wape_diff_vs_4wk_pct_pts']:+.2f} pp`)",
        f"  - **`Forecast ÷ Trips` Classification (With M35 Surge):** `PR-AUC = {c_div_with['pr_auc_common']:.4f}`, `Precision @ Rule B Workload ({int(c_div_with['rule_b_workload_hours']):,} hrs) = {c_div_with['precision_at_rule_b_workload']:.4f}`, `Fixed 0.96× Cutoff F1 = {c_div_with['f1_at_fixed_cutoff']:.4f}` (`P = {c_div_with['precision_at_fixed_cutoff']:.4f}`, `R = {c_div_with['recall_at_fixed_cutoff']:.4f}`, `{int(c_div_with['pred_pos_at_fixed_cutoff']):,}` flagged hrs)",
        f"  - **`Forecast ÷ Trips` Classification (Without M35 Surge):** `PR-AUC = {c_div_no['pr_auc_common']:.4f}`, `Precision @ Rule B Workload ({int(c_div_no['rule_b_workload_hours']):,} hrs) = {c_div_no['precision_at_rule_b_workload']:.4f}`, `Fixed 0.96× Cutoff F1 = {c_div_no['f1_at_fixed_cutoff']:.4f}` (`P = {c_div_no['precision_at_fixed_cutoff']:.4f}`, `R = {c_div_no['recall_at_fixed_cutoff']:.4f}`, `{int(c_div_no['pred_pos_at_fixed_cutoff']):,}` flagged hrs)",
        "",
        "## 2. Dedicated High-Demand Classifier Comparison (`models/final_classifier.joblib`)",
        f"- **Model:** `{classifier_card['model_name']}`",
        f"- **Training Window:** `{classifier_card['training_date_window']}` (`{classifier_card['n_training_rows']:,}` active route-hours across `{classifier_card['n_routes']}` routes)",
        f"- **Input Features ({classifier_card['input_features_count']} columns -> {classifier_card['transformed_feature_dimension']} transformed):** `{', '.join(ALL_FEATURES)}`",
        f"- **Chosen Settings & Fixed Cutoff:** `{classifier_card['hyperparameters']}`, `cutoff = 0.63` (`n_iter_ = {classifier_card['actual_iterations_fitted']}`)",
        f"- **Label Definition:** `{classifier_card['threshold_label_rule']}`",
        "- **Validation Scores (Jun–Jul 2026, 53,406 common active rows):**",
        f"  - `PR-AUC = 0.7290`, `Precision @ 13,081 hrs = 0.6610`, `Fixed 0.63 Cutoff F1 = 0.6862` (`P = 0.5854`, `R = 0.8290`)",
        "- **Test Scores (Aug–Sep 2026, 0 storm days):**",
        f"  - **With M35 Surge (`{c_hgb_with['n_eval_common']:,}` common active rows):** `PR-AUC = {c_hgb_with['pr_auc_common']:.4f}`, `Precision @ Rule B Workload ({int(c_hgb_with['rule_b_workload_hours']):,} hrs) = {c_hgb_with['precision_at_rule_b_workload']:.4f}`, `Fixed 0.63 Cutoff F1 = {c_hgb_with['f1_at_fixed_cutoff']:.4f}` (`P = {c_hgb_with['precision_at_fixed_cutoff']:.4f}`, `R = {c_hgb_with['recall_at_fixed_cutoff']:.4f}`, `{int(c_hgb_with['pred_pos_at_fixed_cutoff']):,}` flagged hrs)",
        f"  - **Without M35 Surge (`{c_hgb_no['n_eval_common']:,}` common active rows):** `PR-AUC = {c_hgb_no['pr_auc_common']:.4f}`, `Precision @ Rule B Workload ({int(c_hgb_no['rule_b_workload_hours']):,} hrs) = {c_hgb_no['precision_at_rule_b_workload']:.4f}`, `Fixed 0.63 Cutoff F1 = {c_hgb_no['f1_at_fixed_cutoff']:.4f}` (`P = {c_hgb_no['precision_at_fixed_cutoff']:.4f}`, `R = {c_hgb_no['recall_at_fixed_cutoff']:.4f}`, `{int(c_hgb_no['pred_pos_at_fixed_cutoff']):,}` flagged hrs)",
        "",
    ]
    (ROOT / "reports" / "model_cards.md").write_text("\n".join(md_lines), encoding="utf-8")
    print("Saved final models and model cards to models/ and reports/model_cards.md", flush=True)

    # ==========================================================================
    # PART 4: GENERATE STEP 5 TEST EVALUATION FIGURES
    # ==========================================================================
    print("\n[4/4] Generating Step 5 test evaluation figures...", flush=True)

    # Figure 1: Forecasting Test Weekly WAPE & Bias (Without M35 Surge, plus With-Surge Annotation)
    plot_step5_forecast_figure(weekly_test_df, forecast_overall_df)

    # Figure 2: Test Set Classification Comparison & PR Curves (Without M35 Surge Hours)
    fig2, (ax_bar, ax_pr) = plt.subplots(1, 2, figsize=(13.6, 5.2), dpi=150)

    c_rb_no = clf_overall_df[
        (clf_overall_df["evaluation_subset"].str.startswith("Without M35"))
        & (clf_overall_df["model_name"].str.startswith("Baseline Rule B"))
    ].iloc[0]

    plot_clf = [
        ("Rule B Baseline\n(4-Wk Avg)", c_rb_no["pr_auc_common"], c_rb_no["precision_at_rule_b_workload"], c_rb_no["f1_at_fixed_cutoff"]),
        ("Forecast ÷ Trips\n(Main, 0.96× Fixed)", c_div_no["pr_auc_common"], c_div_no["precision_at_rule_b_workload"], c_div_no["f1_at_fixed_cutoff"]),
        ("HGB Classifier\n(Comp, 0.63 Fixed)", c_hgb_no["pr_auc_common"], c_hgb_no["precision_at_rule_b_workload"], c_hgb_no["f1_at_fixed_cutoff"]),
    ]
    x_c = np.arange(len(plot_clf))
    w_c = 0.25
    b_pr = ax_bar.bar(x_c - w_c, [m[1] for m in plot_clf], w_c, label="PR-AUC (Cutoff-Free)", color="#1e3a8a", edgecolor="#0f172a")
    b_peq = ax_bar.bar(x_c, [m[2] for m in plot_clf], w_c, label=f"Precision @ Rule B Workload ({int(c_rb_no['rule_b_workload_hours']):,} hrs)", color="#059669", edgecolor="#064e3b")
    b_f1 = ax_bar.bar(x_c + w_c, [m[3] for m in plot_clf], w_c, label="F1 @ Fixed Validation Cutoff", color="#93c5fd", edgecolor="#1d4ed8")

    for bars_grp, col_txt in [(b_pr, "#1e3a8a"), (b_peq, "#065f46"), (b_f1, "#1d4ed8")]:
        for b in bars_grp:
            h = b.get_height()
            ax_bar.text(b.get_x() + b.get_width() / 2.0, h + 0.008, f"{h:.3f}", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color=col_txt)

    ax_bar.set_title("A. Test Classification: PR-AUC, Equal-Workload Precision & Fixed-Cutoff F1", fontsize=10.0, fontweight="bold", pad=8)
    ax_bar.set_ylabel("Score (Test Active Hours Without M35 Surge)", fontsize=9.5)
    ax_bar.set_xticks(x_c)
    ax_bar.set_xticklabels([m[0] for m in plot_clf], fontsize=8.5)
    ax_bar.set_ylim(0.50, 0.85)
    ax_bar.grid(axis="y", alpha=0.3)
    ax_bar.legend(loc="upper left", fontsize=7.8)

    # Panel B: Test Set Precision-Recall Curves
    sub_c_no = te_clf[common_clf_mask & no_outlier_clf_mask]
    y_c_no = sub_c_no["high_demand_per_trip"].values.astype(int)
    for name, scores, color, ls in [
        (f"Forecast ÷ Trips (PR-AUC = {c_div_no['pr_auc_common']:.3f})", sub_c_no["score_div"].values, "#059669", "-"),
        (f"HGB Direct Classifier (PR-AUC = {c_hgb_no['pr_auc_common']:.3f})", sub_c_no["prob_hgb_clf"].values, "#1d4ed8", "--"),
        (f"Rule B Baseline Ratio (PR-AUC = {c_rb_no['pr_auc_common']:.3f})", sub_c_no["score_rule_b"].values, "#64748b", ":"),
    ]:
        prec_c, rec_c, _ = precision_recall_curve(y_c_no, scores)
        ax_pr.plot(rec_c, prec_c, color=color, linestyle=ls, linewidth=1.9, label=name)

    ax_pr.scatter([c_rb_no["recall_at_fixed_cutoff"]], [c_rb_no["precision_at_fixed_cutoff"]], color="#dc2626", s=70, zorder=5, marker="D", label=f"Rule B (P={c_rb_no['precision_at_fixed_cutoff']:.3f}, R={c_rb_no['recall_at_fixed_cutoff']:.3f})")
    ax_pr.scatter([c_div_no["recall_at_fixed_cutoff"]], [c_div_no["precision_at_fixed_cutoff"]], color="#059669", s=75, zorder=5, marker="s", label=f"Forecast÷Trips 0.96× Fixed (P={c_div_no['precision_at_fixed_cutoff']:.3f}, R={c_div_no['recall_at_fixed_cutoff']:.3f})")
    ax_pr.scatter([c_hgb_no["recall_at_fixed_cutoff"]], [c_hgb_no["precision_at_fixed_cutoff"]], color="#1d4ed8", s=70, zorder=5, marker="o", label=f"HGB Clf 0.63 Fixed (P={c_hgb_no['precision_at_fixed_cutoff']:.3f}, R={c_hgb_no['recall_at_fixed_cutoff']:.3f})")

    ax_pr.set_title("B. Test Set Precision–Recall Curves & Fixed-Cutoff Operating Points", fontsize=10.0, fontweight="bold", pad=8)
    ax_pr.set_xlabel("Recall (Share of True High-Demand Hours Flagged)", fontsize=9.5)
    ax_pr.set_ylabel("Precision (Share of Flagged Hours Truly High-Demand)", fontsize=9.5)
    ax_pr.set_xlim(0.20, 1.00)
    ax_pr.set_ylim(0.35, 0.95)
    ax_pr.grid(True, alpha=0.3)
    ax_pr.legend(loc="lower left", fontsize=7.6)

    fig2.tight_layout()
    fig2.savefig(FIG_DIR / "m3_test_classification_results.png", dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print("Saved Step 5 test figures to reports/figures/m3_test_forecast_results.png and m3_test_classification_results.png", flush=True)


def plot_step5_forecast_figure(weekly_test_df: pd.DataFrame, forecast_overall_df: pd.DataFrame) -> None:
    """Plot Panel A (Weekly Forecast Bias) and Panel B (Weekly WAPE %) from saved test tables."""
    f_with = forecast_overall_df[
        (forecast_overall_df["evaluation_subset"].str.startswith("With M35"))
        & (forecast_overall_df["model_name"].str.startswith("HistGradientBoosting"))
    ].iloc[0]
    f_no = forecast_overall_df[
        (forecast_overall_df["evaluation_subset"].str.startswith("Without M35"))
        & (forecast_overall_df["model_name"].str.startswith("HistGradientBoosting"))
    ].iloc[0]
    f_4wk_with = forecast_overall_df[
        (forecast_overall_df["evaluation_subset"].str.startswith("With M35"))
        & (forecast_overall_df["model_name"].str.startswith("4-Week"))
    ].iloc[0]
    f_4wk_no = forecast_overall_df[
        (forecast_overall_df["evaluation_subset"].str.startswith("Without M35"))
        & (forecast_overall_df["model_name"].str.startswith("4-Week"))
    ].iloc[0]

    wk_no = weekly_test_df[weekly_test_df["evaluation_subset"] == "Without M35 Surge Hours"].reset_index(drop=True)
    n_wk_wins_no = int((wk_no["weekly_outcome"] == "Win").sum())
    n_wk_ties_no = int((wk_no["weekly_outcome"] == "Tie").sum())

    fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.0), dpi=150)
    x_wk = np.arange(len(wk_no))
    wk_labels = [f"W{int(r.week_num)}\n({r.week_start[5:]})" for _, r in wk_no.iterrows()]

    ax1.axhline(0.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax1.plot(x_wk, wk_no["bias_4wk_pred_minus_actual"], marker="s", linestyle="--", color="#64748b", linewidth=1.8, label="4-Week Average Baseline")
    ax1.plot(x_wk, wk_no["bias_hgb_pred_minus_actual"], marker="o", color="#1d4ed8", linewidth=2.2, label="HistGradientBoosting (Retrained Jan–Jul)")
    for idx_pt, r in wk_no.iterrows():
        ax1.text(idx_pt, r["bias_hgb_pred_minus_actual"] + (1.8 if r["bias_hgb_pred_minus_actual"] >= 0 else -3.5), f"{r['bias_hgb_pred_minus_actual']:+.1f}", ha="center", fontsize=7.4, color="#1e3a8a", fontweight="bold")
    ax1.set_title("A. Test Set Weekly Forecast Bias (Predicted − Actual Riders/Hr)", fontsize=10.2, fontweight="bold", pad=8)
    ax1.set_ylabel("Bias: Mean(Predicted − Actual)", fontsize=9.5)
    ax1.set_xticks(x_wk)
    ax1.set_xticklabels(wk_labels, fontsize=8)
    ax1.set_ylim(-55, 42)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="lower left", fontsize=8)

    w = 0.36
    ax2.bar(x_wk - w / 2, wk_no["wape_4wk_pct"], w, color="#93c5fd", edgecolor="#1d4ed8", label=f"4-Week Avg ({f_4wk_no['wape_common_pct']:.2f}% WAPE; {f_4wk_with['wape_common_pct']:.2f}% w/ M35)")
    ax2.bar(x_wk + w / 2, wk_no["wape_hgb_pct"], w, color="#1d4ed8", edgecolor="#1e3a8a", label=f"HGB Retrained ({f_no['wape_common_pct']:.2f}% WAPE; {f_with['wape_common_pct']:.2f}% w/ M35; Wins {n_wk_wins_no}/{len(wk_no)})")
    ax2.set_title("B. Test Set Weekly WAPE (%) Across Aug–Sep 2026", fontsize=10.2, fontweight="bold", pad=8)
    ax2.set_ylabel("Weekly WAPE (%)", fontsize=9.5)
    ax2.set_xticks(x_wk)
    ax2.set_xticklabels(wk_labels, fontsize=8)
    ax2.set_ylim(0, 24.5)
    ax2.grid(axis="y", alpha=0.3)
    ax2.legend(loc="upper left", fontsize=7.8)

    fig1.tight_layout()
    fig1.savefig(FIG_DIR / "m3_test_forecast_results.png", dpi=150, bbox_inches="tight")
    plt.close(fig1)


if __name__ == "__main__":
    if "--plots-only" in sys.argv:
        wk_df_saved = pd.read_csv(TAB_DIR / "m3_test_forecast_by_week.csv")
        ov_df_saved = pd.read_csv(TAB_DIR / "m3_test_forecast_overall.csv")
        plot_step5_forecast_figure(wk_df_saved, ov_df_saved)
        print("Regenerated m3_test_forecast_results.png from saved CSVs (--plots-only).")
    else:
        run_step5_final_test()
