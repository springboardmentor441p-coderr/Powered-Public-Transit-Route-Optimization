"""
Milestone 3 — Step 3: High-Demand-per-Trip Classification Models (src/train_classification.py)

Trains, tunes, and evaluates classification models for `high_demand_per_trip`
(`riders_per_trip > threshold_p75`, defined on active-service hours where `trips_running > 0`):
1. Baseline Rule A: `lag_7d / trips_running > threshold_p75` (F1 = 0.6276, PR-AUC = 0.6295)
2. Baseline Rule B (Target to Beat): `lag_mean_available / trips_running > threshold_p75`
   (Precision = 0.6641, Recall = 0.6689, F1 = 0.6665, PR-AUC = 0.6904 on 53,406 common active hours)
3. Logistic Regression with class weights (10 validation settings + probability cutoff tuning)
4. Random Forest Classifier with class weights (10 validation settings + probability cutoff tuning)
5. Gradient Boosting Classifier (`HistGradientBoostingClassifier`) with class weights
   (12 validation settings + probability cutoff tuning)
6. Forecast ÷ Trips (`HistGradientBoosting` ridership forecast ÷ `trips_running` vs `threshold_p75`):
   - Evaluates the unadjusted 1.00x threshold (`pred_hgb / trips_running > threshold_p75`) to check how
     Step 2's +8.83 riders/hr (+3.5%) seasonal overprediction inflates flagged hours and lowers precision.
   - Tunes the threshold multiplier `m` across 10 validation settings (`pred_hgb / trips_running > m * threshold_p75`),
     reporting both the F1-maximising cutoff (`m = 0.96`) and the bias-corrected cutoff (`m = 1.03`) that
     restores precision above Rule B while preserving higher recall.

Cutoff Selection Rule & Final Test Protocol:
- Cutoff rule written down explicitly: Our primary selection rule on validation is **maximising F1 score**
  (balancing false-positive extra-bus dispatches against missed crowding hours), while also reporting the
  default 0.50 (1.00x) cutoff and the bias-adjusted / precision-matched cutoff (`m = 1.03` for Forecast ÷ Trips).
- Final Test Run Rule (Step 5): Just like Step 2 forecasting, after locking hyperparameters and probability/ratio
  cutoffs on validation, every compared classifier (and the underlying forecaster for Forecast ÷ Trips) will be
  retrained on `train + val` combined (January to July 2026) before scoring the test set once in Step 5.
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
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluate import (
    compute_classification_metrics,
    evaluate_classification,
    load_dataset,
    print_classification_summary,
)
from src.train_forecasting import ALL_FEATURES

MODELS_DIR = ROOT / "models"
TAB_DIR = ROOT / "reports" / "tables"
FIG_DIR = ROOT / "reports" / "figures"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)


def find_best_f1_cutoff(
    y_true: np.ndarray,
    y_score: np.ndarray,
    grid: np.ndarray,
) -> Tuple[float, Dict]:
    """Sweep cutoff grid on validation and return (best_cutoff, metrics_at_best_cutoff) maximising F1."""
    best_t = float(grid[0])
    best_m = None
    best_f1 = -1.0
    for t in grid:
        pred = (y_score >= t).astype(int)
        m = compute_classification_metrics(y_true, pred, y_score)
        if m["f1"] > best_f1:
            best_f1 = m["f1"]
            best_t = float(round(t, 3))
            best_m = m
    return best_t, best_m


def run_step3_classification() -> None:
    print("=" * 88, flush=True)
    print("MILESTONE 3 — STEP 3: HIGH-DEMAND-PER-TRIP CLASSIFICATION MODELS", flush=True)
    print("=" * 88, flush=True)

    train_df = load_dataset("train")
    val_df = load_dataset("val")
    preprocessor = joblib.load(MODELS_DIR / "preprocessor.joblib")
    forecaster_bundle = joblib.load(MODELS_DIR / "best_forecaster.joblib")

    # Active-service filter: classification target is defined strictly when trips_running > 0
    tr_active_mask = (train_df["trips_running"] > 0) & train_df["threshold_p75"].notnull()
    va_active_mask = (val_df["trips_running"] > 0) & val_df["threshold_p75"].notnull()

    tr_clf = train_df[tr_active_mask].copy()
    va_clf = val_df[va_active_mask].copy()

    # Common 53,406 active-service validation rows where both lag_7d and lag_mean_available exist
    common_in_va_clf = (
        va_clf["lag_7d"].notnull() & va_clf["lag_mean_available"].notnull()
    ).values

    print(
        f"Active-service training rows   : {len(tr_clf):,} (positive rate = {tr_clf['high_demand_per_trip'].mean()*100:.2f}%)",
        flush=True,
    )
    print(
        f"Active-service validation rows : {len(va_clf):,} total | {common_in_va_clf.sum():,} common baseline rows "
        f"(positive rate = {va_clf.loc[common_in_va_clf, 'high_demand_per_trip'].mean()*100:.2f}%)",
        flush=True,
    )

    X_train = preprocessor.transform(tr_clf[ALL_FEATURES])
    y_train = tr_clf["high_demand_per_trip"].values.astype(int)

    X_val_all = preprocessor.transform(va_clf[ALL_FEATURES])
    y_val_all = va_clf["high_demand_per_trip"].values.astype(int)
    y_val_common = y_val_all[common_in_va_clf]

    prob_grid = np.round(np.linspace(0.30, 0.85, 56), 2)
    tuning_rows: List[Dict] = []
    best_family_info: Dict[str, Dict] = {}

    def record_clf_setting(
        family: str,
        setting_id: int,
        setting_desc: str,
        probs_all: np.ndarray,
        default_cutoff: float,
        cutoff_grid: np.ndarray,
        fit_sec: float,
        extra_obj: object = None,
    ) -> Dict:
        probs_common = probs_all[common_in_va_clf]
        # Metrics at default cutoff (0.50 for probability classifiers, 1.00 for ratio)
        m_def = compute_classification_metrics(
            y_val_common, (probs_common >= default_cutoff).astype(int), probs_common
        )
        # Metrics at F1-maximising validation cutoff
        best_t, m_best_c = find_best_f1_cutoff(y_val_common, probs_common, cutoff_grid)
        # Metrics on all 53,495 active-service validation rows at best_t
        m_best_all = compute_classification_metrics(
            y_val_all, (probs_all >= best_t).astype(int), probs_all
        )

        row = {
            "model_family": family,
            "setting_id": setting_id,
            "setting_description": setting_desc,
            "default_cutoff": default_cutoff,
            "precision_at_default_53406": m_def["precision"],
            "recall_at_default_53406": m_def["recall"],
            "f1_at_default_53406": m_def["f1"],
            "pred_pos_at_default_53406": m_def["pred_positive"],
            "opt_cutoff_max_f1": best_t,
            "n_eval_common": m_best_c["n_eval"],
            "pred_pos_53406": m_best_c["pred_positive"],
            "precision_53406": m_best_c["precision"],
            "recall_53406": m_best_c["recall"],
            "f1_53406": m_best_c["f1"],
            "pr_auc_53406": m_best_c["pr_auc"],
            "roc_auc_53406": m_best_c["roc_auc"],
            "n_eval_all_active": m_best_all["n_eval"],
            "precision_53495": m_best_all["precision"],
            "recall_53495": m_best_all["recall"],
            "f1_53495": m_best_all["f1"],
            "pr_auc_53495": m_best_all["pr_auc"],
            "fit_seconds": round(fit_sec, 2),
        }
        tuning_rows.append(row)

        if (
            family not in best_family_info
            or m_best_c["f1"] > best_family_info[family]["f1_53406"]
        ):
            best_family_info[family] = {
                **row,
                "probs_all": probs_all,
                "probs_common": probs_common,
                "estimator": extra_obj,
            }
        return row

    # ==========================================================================
    # FAMILY 1: Logistic Regression with Class Weights (10 settings)
    # ==========================================================================
    print("\n[1/4] Tuning Logistic Regression with class weights (10 settings)...", flush=True)
    lr_settings = [
        (0.01, "balanced", "balanced"),
        (0.1, "balanced", "balanced"),
        (1.0, "balanced", "balanced"),
        (10.0, "balanced", "balanced"),
        (100.0, "balanced", "balanced"),
        (0.01, {0: 1.0, 1: 2.0}, "weight_1:2"),
        (0.1, {0: 1.0, 1: 2.0}, "weight_1:2"),
        (1.0, {0: 1.0, 1: 2.0}, "weight_1:2"),
        (10.0, {0: 1.0, 1: 2.0}, "weight_1:2"),
        (1.0, {0: 1.0, 1: 1.5}, "weight_1:1.5"),
    ]
    for sid, (c_val, cw, cw_label) in enumerate(lr_settings, start=1):
        t0 = time.time()
        clf = LogisticRegression(C=c_val, class_weight=cw, max_iter=500, random_state=42)
        clf.fit(X_train, y_train)
        probs = clf.predict_proba(X_val_all)[:, 1]
        dt = time.time() - t0
        desc = f"C={c_val}, class_weight={cw_label}"
        r = record_clf_setting("Logistic Regression", sid, desc, probs, 0.50, prob_grid, dt, clf)
        print(
            f"  #{sid:02d} {desc:<36} -> @0.50 F1={r['f1_at_default_53406']:.4f} | "
            f"@t={r['opt_cutoff_max_f1']:.2f} P={r['precision_53406']:.4f}, R={r['recall_53406']:.4f}, "
            f"F1={r['f1_53406']:.4f}, PR-AUC={r['pr_auc_53406']:.4f}",
            flush=True,
        )

    # ==========================================================================
    # FAMILY 2: Random Forest Classifier with Class Weights (10 settings)
    # ==========================================================================
    print("\n[2/4] Tuning Random Forest Classifier with class weights (10 settings)...", flush=True)
    rf_settings = [
        (10, 20, 0.6, "balanced"),
        (12, 15, 0.6, "balanced"),
        (14, 10, 0.6, "balanced"),
        (14, 10, 0.8, "balanced"),
        (16, 10, 0.6, "balanced"),
        (16, 10, 0.8, "balanced"),
        (18, 10, 0.7, "balanced"),
        (18, 5, 0.8, "balanced"),
        (20, 5, 0.8, "balanced"),
        (20, 5, 0.8, "balanced_subsample"),
    ]
    for sid, (depth, leaf, feat, cw) in enumerate(rf_settings, start=1):
        t0 = time.time()
        rf = RandomForestClassifier(
            n_estimators=80,
            max_depth=depth,
            min_samples_leaf=leaf,
            max_features=feat,
            class_weight=cw,
            n_jobs=-1,
            random_state=42,
        )
        rf.fit(X_train, y_train)
        probs = rf.predict_proba(X_val_all)[:, 1]
        dt = time.time() - t0
        desc = f"depth={depth}, leaf={leaf}, feat={feat}, cw={cw}"
        r = record_clf_setting("Random Forest Classifier", sid, desc, probs, 0.50, prob_grid, dt, rf)
        print(
            f"  #{sid:02d} {desc:<48} -> @0.50 F1={r['f1_at_default_53406']:.4f} | "
            f"@t={r['opt_cutoff_max_f1']:.2f} P={r['precision_53406']:.4f}, R={r['recall_53406']:.4f}, "
            f"F1={r['f1_53406']:.4f}, PR-AUC={r['pr_auc_53406']:.4f} ({dt:.1f}s)",
            flush=True,
        )

    # ==========================================================================
    # FAMILY 3: HistGradientBoostingClassifier with Class Weights (12 settings)
    # ==========================================================================
    print("\n[3/4] Tuning HistGradientBoostingClassifier with class weights (12 settings)...", flush=True)
    hgb_settings = [
        (0.03, 31, 20, 1.0, "balanced", "balanced"),
        (0.05, 31, 20, 1.0, "balanced", "balanced"),
        (0.05, 63, 20, 1.0, "balanced", "balanced"),
        (0.05, 63, 25, 1.0, "balanced", "balanced"),
        (0.05, 63, 30, 5.0, "balanced", "balanced"),
        (0.08, 63, 25, 1.0, "balanced", "balanced"),
        (0.05, 127, 25, 1.0, "balanced", "balanced"),
        (0.05, 127, 30, 5.0, "balanced", "balanced"),
        (0.08, 127, 30, 5.0, "balanced", "balanced"),
        (0.05, 63, 25, 1.0, {0: 1.0, 1: 2.0}, "weight_1:2"),
        (0.05, 127, 25, 1.0, {0: 1.0, 1: 2.0}, "weight_1:2"),
        (0.05, 63, 25, 1.0, {0: 1.0, 1: 1.5}, "weight_1:1.5"),
    ]
    for sid, (lr_val, leaf, min_l, l2, cw, cw_label) in enumerate(hgb_settings, start=1):
        t0 = time.time()
        hgb_c = HistGradientBoostingClassifier(
            learning_rate=lr_val,
            max_leaf_nodes=leaf,
            min_samples_leaf=min_l,
            l2_regularization=l2,
            class_weight=cw,
            max_iter=300,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=15,
            random_state=42,
        )
        hgb_c.fit(X_train, y_train)
        probs = hgb_c.predict_proba(X_val_all)[:, 1]
        dt = time.time() - t0
        desc = f"lr={lr_val}, leaf={leaf}, min={min_l}, l2={l2}, cw={cw_label}"
        r = record_clf_setting("HistGradientBoosting Classifier", sid, desc, probs, 0.50, prob_grid, dt, hgb_c)
        print(
            f"  #{sid:02d} {desc:<54} -> @0.50 F1={r['f1_at_default_53406']:.4f} | "
            f"@t={r['opt_cutoff_max_f1']:.2f} P={r['precision_53406']:.4f}, R={r['recall_53406']:.4f}, "
            f"F1={r['f1_53406']:.4f}, PR-AUC={r['pr_auc_53406']:.4f} ({dt:.1f}s)",
            flush=True,
        )

    # ==========================================================================
    # FAMILY 4: Forecast ÷ Trips (HistGradientBoosting Forecast / trips_running vs threshold_p75)
    # ==========================================================================
    print("\n[4/4] Evaluating Forecast ÷ Trips across 10 threshold multiplier settings...", flush=True)
    pred_riders_all = np.clip(
        forecaster_bundle["pipeline"].predict(va_clf[ALL_FEATURES]), 0.0, None
    )
    pred_rpt_all = pred_riders_all / va_clf["trips_running"].values
    ratio_all = pred_rpt_all / va_clf["threshold_p75"].values
    ratio_common = ratio_all[common_in_va_clf]

    # Normalized continuous score in [0, 1] for PR-AUC / ROC-AUC (monotonic with ratio_all)
    score_div_all = np.clip(ratio_all / 2.0, 0.0, 1.0)
    score_div_common = score_div_all[common_in_va_clf]

    multipliers = [0.92, 0.94, 0.96, 0.98, 1.00, 1.02, 1.03, 1.05, 1.08, 1.10]
    m_at_100 = compute_classification_metrics(
        y_val_common, (ratio_common > 1.00).astype(int), score_div_common
    )
    for sid, mult in enumerate(multipliers, start=1):
        m_c = compute_classification_metrics(
            y_val_common, (ratio_common > mult).astype(int), score_div_common
        )
        m_a = compute_classification_metrics(
            y_val_all, (ratio_all > mult).astype(int), score_div_all
        )
        desc = f"pred_hgb / trips_running > {mult:.2f} * threshold_p75"
        row = {
            "model_family": "Forecast ÷ Trips (HGB)",
            "setting_id": sid,
            "setting_description": desc,
            "default_cutoff": 1.00,
            "precision_at_default_53406": m_at_100["precision"],
            "recall_at_default_53406": m_at_100["recall"],
            "f1_at_default_53406": m_at_100["f1"],
            "pred_pos_at_default_53406": m_at_100["pred_positive"],
            "opt_cutoff_max_f1": mult,
            "n_eval_common": m_c["n_eval"],
            "pred_pos_53406": m_c["pred_positive"],
            "precision_53406": m_c["precision"],
            "recall_53406": m_c["recall"],
            "f1_53406": m_c["f1"],
            "pr_auc_53406": m_c["pr_auc"],
            "roc_auc_53406": m_c["roc_auc"],
            "n_eval_all_active": m_a["n_eval"],
            "precision_53495": m_a["precision"],
            "recall_53495": m_a["recall"],
            "f1_53495": m_a["f1"],
            "pr_auc_53495": m_a["pr_auc"],
            "fit_seconds": 0.0,
        }
        tuning_rows.append(row)
        print(
            f"  #{sid:02d} multiplier={mult:.2f}x -> pred_pos={m_c['pred_positive']:>5} "
            f"(actual={m_c['actual_positive']}), P={m_c['precision']:.4f}, R={m_c['recall']:.4f}, "
            f"F1={m_c['f1']:.4f}, PR-AUC={m_c['pr_auc']:.4f}",
            flush=True,
        )

    tuning_df = pd.DataFrame(tuning_rows)
    tuning_path = TAB_DIR / "m3_classification_tuning_results.csv"
    tuning_df.to_csv(tuning_path, index=False)
    print(f"\nSaved {len(tuning_df)} classification tuning runs to {tuning_path.relative_to(ROOT)}", flush=True)

    # ==========================================================================
    # BUILD HEAD-TO-HEAD COMPARISON TABLE (53,406 COMMON ROWS & ALL 53,495 ROWS)
    # ==========================================================================
    comp_rows = []

    # Baselines: Rule A (7-day lag) and Rule B (4-week average — Target to Beat)
    for rule_name, col, role in [
        ("Baseline Rule A: 7-Day Lag ÷ Trips > Threshold", "lag_7d", "Baseline (Weak)"),
        ("Baseline Rule B: 4-Week Avg ÷ Trips > Threshold (Target to Beat)", "lag_mean_available", "Baseline Hurdle"),
    ]:
        sub_c = va_clf[common_in_va_clf]
        rpt_c = sub_c[col] / sub_c["trips_running"]
        pred_c = (rpt_c > sub_c["threshold_p75"]).astype(int)
        score_c = np.clip(rpt_c / (2.0 * sub_c["threshold_p75"]), 0.0, 1.0)
        mc = compute_classification_metrics(y_val_common, pred_c, score_c)

        valid_col = va_clf[col].notnull().values
        sub_a = va_clf[valid_col]
        rpt_a = sub_a[col] / sub_a["trips_running"]
        pred_a = (rpt_a > sub_a["threshold_p75"]).astype(int)
        score_a = np.clip(rpt_a / (2.0 * sub_a["threshold_p75"]), 0.0, 1.0)
        ma = compute_classification_metrics(y_val_all[valid_col], pred_a, score_a)

        comp_rows.append({
            "model_name": rule_name,
            "model_category": role,
            "cutoff_rule": "ratio > 1.00 * threshold_p75 (Fixed)",
            "settings_tested": 1,
            "n_eval_53406": mc["n_eval"],
            "actual_pos_53406": mc["actual_positive"],
            "pred_pos_53406": mc["pred_positive"],
            "precision_53406": mc["precision"],
            "recall_53406": mc["recall"],
            "f1_53406": mc["f1"],
            "pr_auc_53406": mc["pr_auc"],
            "roc_auc_53406": mc["roc_auc"],
            "n_eval_all_active": ma["n_eval"],
            "precision_all_active": ma["precision"],
            "recall_all_active": ma["recall"],
            "f1_all_active": ma["f1"],
            "pr_auc_all_active": ma["pr_auc"],
            "f1_gain_vs_rule_b": round(mc["f1"] - 0.6665, 4),
        })

    # Direct classifiers (Logistic Regression, Random Forest, HistGradientBoosting)
    for fam in ["Logistic Regression", "Random Forest Classifier", "HistGradientBoosting Classifier"]:
        b = best_family_info[fam]
        n_tested = int((tuning_df["model_family"] == fam).sum())
        comp_rows.append({
            "model_name": f"{fam} ({b['setting_description']})",
            "model_category": "Direct Classifier (Class Weights)",
            "cutoff_rule": f"prob >= {b['opt_cutoff_max_f1']:.2f} (Max F1 on Val; @0.50 F1={b['f1_at_default_53406']:.4f})",
            "settings_tested": n_tested,
            "n_eval_53406": b["n_eval_common"],
            "actual_pos_53406": 12987,
            "pred_pos_53406": b["pred_pos_53406"],
            "precision_53406": b["precision_53406"],
            "recall_53406": b["recall_53406"],
            "f1_53406": b["f1_53406"],
            "pr_auc_53406": b["pr_auc_53406"],
            "roc_auc_53406": b["roc_auc_53406"],
            "n_eval_all_active": b["n_eval_all_active"],
            "precision_all_active": b["precision_53495"],
            "recall_all_active": b["recall_53495"],
            "f1_all_active": b["f1_53495"],
            "pr_auc_all_active": b["pr_auc_53495"],
            "f1_gain_vs_rule_b": round(b["f1_53406"] - 0.6665, 4),
        })

    # Forecast ÷ Trips: report all 3 key operational cutoffs (1.00x unadjusted, 1.03x bias-corrected, 0.96x max-F1)
    for mult, label, rule_desc in [
        (1.00, "Forecast ÷ Trips: Unadjusted (1.00x Threshold)", "ratio > 1.00 * threshold_p75 (Unadjusted; +8.83 bias flags 14,748 hrs)"),
        (1.03, "Forecast ÷ Trips: Bias-Corrected (1.03x Threshold)", "ratio > 1.03 * threshold_p75 (Offsets +3.5% seasonal bias; beats Rule B on P & R)"),
        (0.96, "Forecast ÷ Trips: Max-F1 Tuned (0.96x Threshold)", "ratio > 0.96 * threshold_p75 (Maximises Validation F1)"),
    ]:
        mc = compute_classification_metrics(
            y_val_common, (ratio_common > mult).astype(int), score_div_common
        )
        ma = compute_classification_metrics(
            y_val_all, (ratio_all > mult).astype(int), score_div_all
        )
        comp_rows.append({
            "model_name": label,
            "model_category": "Forecast ÷ Trips (HGB)",
            "cutoff_rule": rule_desc,
            "settings_tested": 10,
            "n_eval_53406": mc["n_eval"],
            "actual_pos_53406": mc["actual_positive"],
            "pred_pos_53406": mc["pred_positive"],
            "precision_53406": mc["precision"],
            "recall_53406": mc["recall"],
            "f1_53406": mc["f1"],
            "pr_auc_53406": mc["pr_auc"],
            "roc_auc_53406": mc["roc_auc"],
            "n_eval_all_active": ma["n_eval"],
            "precision_all_active": ma["precision"],
            "recall_all_active": ma["recall"],
            "f1_all_active": ma["f1"],
            "pr_auc_all_active": ma["pr_auc"],
            "f1_gain_vs_rule_b": round(mc["f1"] - 0.6665, 4),
        })

    comp_df = pd.DataFrame(comp_rows)
    comp_path = TAB_DIR / "m3_classification_model_comparison.csv"
    comp_df.to_csv(comp_path, index=False)
    print("\n" + "=" * 88, flush=True)
    print("STEP 3 CLASSIFICATION COMPARISON: COMMON 53,406 ROWS vs ALL 53,495 ACTIVE ROWS", flush=True)
    print("=" * 88, flush=True)
    print(comp_df.to_string(index=False), flush=True)

    # ==========================================================================
    # EVALUATE BEST DIRECT CLASSIFIER (HistGradientBoostingClassifier) & FORECAST ÷ TRIPS
    # ==========================================================================
    best_hgb_info = best_family_info["HistGradientBoosting Classifier"]
    best_t_hgb = best_hgb_info["opt_cutoff_max_f1"]

    va_common_eval = va_clf[common_in_va_clf].copy()
    va_common_eval["pred_hgb_clf"] = (best_hgb_info["probs_common"] >= best_t_hgb).astype(int)
    va_common_eval["prob_hgb_clf"] = best_hgb_info["probs_common"]

    res_hgb_clf = evaluate_classification(
        df=va_common_eval,
        y_true_col="high_demand_per_trip",
        y_pred_col="pred_hgb_clf",
        y_prob_col="prob_hgb_clf",
        model_name=f"HistGradientBoosting Classifier (Best Direct Classifier, cutoff={best_t_hgb:.2f})",
        save_prefix="m3_eval_best_direct_clf",
        out_dir=TAB_DIR,
    )
    print_classification_summary(res_hgb_clf)

    # Also save breakdowns for Forecast ÷ Trips (Max-F1 0.96x and Bias-Corrected 1.03x)
    va_common_eval["pred_div_maxf1"] = (ratio_common > 0.96).astype(int)
    va_common_eval["score_div"] = score_div_common
    evaluate_classification(
        df=va_common_eval,
        y_true_col="high_demand_per_trip",
        y_pred_col="pred_div_maxf1",
        y_prob_col="score_div",
        model_name="Forecast ÷ Trips (HGB Forecast / trips_running > 0.96 * threshold_p75, Max F1)",
        save_prefix="m3_eval_forecast_div_trips_maxf1",
        out_dir=TAB_DIR,
    )

    va_common_eval["pred_div_biascorr"] = (ratio_common > 1.03).astype(int)
    evaluate_classification(
        df=va_common_eval,
        y_true_col="high_demand_per_trip",
        y_pred_col="pred_div_biascorr",
        y_prob_col="score_div",
        model_name="Forecast ÷ Trips (HGB Forecast / trips_running > 1.03 * threshold_p75, Bias-Corrected)",
        save_prefix="m3_eval_forecast_div_trips_biascorr",
        out_dir=TAB_DIR,
    )

    # Save best direct classifier bundle
    best_clf_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", best_hgb_info["estimator"]),
    ])
    joblib.dump(
        {
            "pipeline": best_clf_pipeline,
            "model_family": "HistGradientBoosting Classifier",
            "best_setting": best_hgb_info["setting_description"],
            "opt_cutoff_max_f1": best_t_hgb,
            "features": ALL_FEATURES,
            "val_f1_53406": best_hgb_info["f1_53406"],
            "val_pr_auc_53406": best_hgb_info["pr_auc_53406"],
            "forecast_div_trips_cutoffs": {"unadjusted": 1.00, "bias_corrected": 1.03, "max_f1": 0.96},
        },
        MODELS_DIR / "best_classifier.joblib",
        compress=3,
    )
    print(f"Saved best classifier bundle to {MODELS_DIR / 'best_classifier.joblib'}", flush=True)

    # ==========================================================================
    # GENERATE STEP 3 FIGURE: MODEL COMPARISON & PRECISION-RECALL CURVES
    # ==========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), dpi=150)

    # Panel A: Grouped bar chart of Precision, Recall, F1, PR-AUC on 53,406 common rows
    plot_models = [
        ("Rule A\n(7-Day Lag)", 0.6211, 0.6342, 0.6276, 0.6295),
        ("Rule B Hurdle\n(4-Wk Avg)", 0.6641, 0.6689, 0.6665, 0.6904),
        ("Logistic Reg\n(Max F1)", best_family_info["Logistic Regression"]["precision_53406"], best_family_info["Logistic Regression"]["recall_53406"], best_family_info["Logistic Regression"]["f1_53406"], best_family_info["Logistic Regression"]["pr_auc_53406"]),
        ("Random Forest\n(Max F1)", best_family_info["Random Forest Classifier"]["precision_53406"], best_family_info["Random Forest Classifier"]["recall_53406"], best_family_info["Random Forest Classifier"]["f1_53406"], best_family_info["Random Forest Classifier"]["pr_auc_53406"]),
        ("HGB Classifier\n(Max F1)", best_hgb_info["precision_53406"], best_hgb_info["recall_53406"], best_hgb_info["f1_53406"], best_hgb_info["pr_auc_53406"]),
        ("Forecast÷Trips\n(1.00x Raw)", m_at_100["precision"], m_at_100["recall"], m_at_100["f1"], m_at_100["pr_auc"]),
        ("Forecast÷Trips\n(1.03x Bias-Adj)", comp_df.iloc[-2]["precision_53406"], comp_df.iloc[-2]["recall_53406"], comp_df.iloc[-2]["f1_53406"], comp_df.iloc[-2]["pr_auc_53406"]),
        ("Forecast÷Trips\n(0.96x Max F1)", comp_df.iloc[-1]["precision_53406"], comp_df.iloc[-1]["recall_53406"], comp_df.iloc[-1]["f1_53406"], comp_df.iloc[-1]["pr_auc_53406"]),
    ]
    x = np.arange(len(plot_models))
    w = 0.25
    p_vals = [m[1] for m in plot_models]
    r_vals = [m[2] for m in plot_models]
    f1_vals = [m[3] for m in plot_models]

    ax1.bar(x - w, p_vals, w, label="Precision", color="#93c5fd", edgecolor="#1d4ed8")
    ax1.bar(x, r_vals, w, label="Recall", color="#60a5fa", edgecolor="#1e40af")
    bars_f1 = ax1.bar(x + w, f1_vals, w, label="F1 Score", color="#1e3a8a", edgecolor="#0f172a")
    ax1.axhline(0.6665, color="#dc2626", linestyle="--", linewidth=1.2, label="Rule B F1 Hurdle (0.6665)")
    for b in bars_f1:
        h = b.get_height()
        ax1.text(b.get_x() + b.get_width() / 2.0, h + 0.01, f"{h:.3f}", ha="center", va="bottom", fontsize=7, fontweight="bold")
    ax1.set_title("A. Classification Precision, Recall & F1 (53,406 Common Rows)", fontsize=10.5, fontweight="bold", pad=8)
    ax1.set_ylabel("Score", fontsize=9.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels([m[0] for m in plot_models], fontsize=7.5)
    ax1.set_ylim(0.40, 0.94)
    ax1.grid(axis="y", alpha=0.3)
    ax1.legend(loc="upper left", fontsize=8, ncol=2)

    # Panel B: Precision-Recall Curves & Operating Points
    for name, scores, color, ls in [
        ("HGB Direct Classifier (PR-AUC = 0.727)", best_hgb_info["probs_common"], "#1d4ed8", "-"),
        ("Forecast ÷ Trips (HGB, PR-AUC = 0.721)", score_div_common, "#059669", "-."),
        ("Random Forest Classifier (PR-AUC = 0.716)", best_family_info["Random Forest Classifier"]["probs_common"], "#7c3aed", "--"),
        ("Logistic Regression (PR-AUC = 0.617)", best_family_info["Logistic Regression"]["probs_common"], "#94a3b8", ":"),
    ]:
        prec_c, rec_c, _ = precision_recall_curve(y_val_common, scores)
        ax2.plot(rec_c, prec_c, color=color, linestyle=ls, linewidth=1.8, label=name)

    # Plot operating points for Rule B, Forecast÷Trips 1.00x, Forecast÷Trips 1.03x, Forecast÷Trips 0.96x, and HGB Clf
    ax2.scatter([0.6689], [0.6641], color="#dc2626", s=65, zorder=5, marker="D", label="Rule B Baseline (P=0.664, R=0.669)")
    ax2.scatter([m_at_100["recall"]], [m_at_100["precision"]], color="#f59e0b", s=65, zorder=5, marker="o", label="Forecast÷Trips 1.00x (P=0.651, R=0.739)")
    ax2.scatter([comp_df.iloc[-2]["recall_53406"]], [comp_df.iloc[-2]["precision_53406"]], color="#059669", s=70, zorder=5, marker="^", label="Forecast÷Trips 1.03x Bias-Adj (P=0.688, R=0.671)")
    ax2.scatter([comp_df.iloc[-1]["recall_53406"]], [comp_df.iloc[-1]["precision_53406"]], color="#047857", s=70, zorder=5, marker="s", label="Forecast÷Trips 0.96x Max-F1 (P=0.605, R=0.826)")

    ax2.set_title("B. Validation Precision–Recall Curves & Cutoff Operating Points", fontsize=10.5, fontweight="bold", pad=8)
    ax2.set_xlabel("Recall (Share of True High-Demand Hours Flagged)", fontsize=9.5)
    ax2.set_ylabel("Precision (Share of Flagged Hours Truly High-Demand)", fontsize=9.5)
    ax2.set_xlim(0.20, 1.00)
    ax2.set_ylim(0.35, 0.95)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="lower left", fontsize=7.5)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "m3_classification_model_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved Step 3 classification figure to reports/figures/m3_classification_model_comparison.png", flush=True)


if __name__ == "__main__":
    run_step3_classification()

