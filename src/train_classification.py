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


def metrics_at_fixed_workload(
    y_true: np.ndarray,
    y_score: np.ndarray,
    k_flagged: int = 13081,
) -> Dict:
    """Evaluate precision, recall, and F1 when a model flags the exact top k_flagged hours (matching Rule B's 13,081 hours)."""
    order = np.argsort(-y_score, kind="mergesort")
    pred = np.zeros_like(y_true, dtype=int)
    pred[order[:k_flagged]] = 1
    m = compute_classification_metrics(y_true, pred, y_score)
    m["Implicit_Cutoff"] = float(round(y_score[order[k_flagged - 1]], 4))
    return m


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
    build_step3_comparison_and_figures(
        va_clf=va_clf,
        common_in_va_clf=common_in_va_clf,
        y_val_common=y_val_common,
        y_val_all=y_val_all,
        ratio_common=ratio_common,
        ratio_all=ratio_all,
        score_div_common=score_div_common,
        score_div_all=score_div_all,
        m_at_100=m_at_100,
        best_family_info=best_family_info,
        tuning_df=tuning_df,
        preprocessor=preprocessor,
    )


def build_step3_comparison_and_figures(
    va_clf: pd.DataFrame,
    common_in_va_clf: np.ndarray,
    y_val_common: np.ndarray,
    y_val_all: np.ndarray,
    ratio_common: np.ndarray,
    ratio_all: np.ndarray,
    score_div_common: np.ndarray,
    score_div_all: np.ndarray,
    m_at_100: Dict,
    best_family_info: Dict[str, Dict],
    tuning_df: pd.DataFrame,
    preprocessor: object,
) -> None:
    comp_rows = []
    k_rule_b = 13081

    # Baselines: Rule A (7-day lag) and Rule B (4-week average — Target to Beat)
    # Note: In va_clf (53,495 active rows), lag_7d is non-null on 53,406 rows (89 missing after holidays/outages)
    # and lag_mean_available is non-null on 53,492 rows (3 missing). To score all 53,495 active rows consistently
    # in the "all active rows" columns without dropping rows, missing lags are median-imputed (or fallback to lag_mean_available)
    # while recording exact non-null lag counts in cutoff_rule.
    for rule_name, col, role in [
        ("Baseline Rule A: 7-Day Lag ÷ Trips > Threshold", "lag_7d", "Baseline (Weak)"),
        ("Baseline Rule B: 4-Week Avg ÷ Trips > Threshold (Target to Beat)", "lag_mean_available", "Baseline Hurdle"),
    ]:
        sub_c = va_clf[common_in_va_clf]
        rpt_c = (sub_c[col] / sub_c["trips_running"]).values
        ratio_c = rpt_c / sub_c["threshold_p75"].values
        pred_c = (ratio_c > 1.00).astype(int)
        score_c = np.clip(ratio_c / 2.0, 0.0, 1.0)
        mc = compute_classification_metrics(y_val_common, pred_c, score_c)
        mw = metrics_at_fixed_workload(y_val_common, ratio_c, k_flagged=k_rule_b)

        # Evaluate across all 53,495 active-service rows (filling missing lag with lag_mean_available / median 150.0)
        lag_filled = va_clf[col].fillna(va_clf["lag_mean_available"]).fillna(150.0)
        rpt_a = (lag_filled / va_clf["trips_running"]).values
        ratio_a = rpt_a / va_clf["threshold_p75"].values
        pred_a = (ratio_a > 1.00).astype(int)
        score_a = np.clip(ratio_a / 2.0, 0.0, 1.0)
        ma = compute_classification_metrics(y_val_all, pred_a, score_a)
        n_nonnull = int(va_clf[col].notnull().sum())

        comp_rows.append({
            "model_name": rule_name,
            "model_category": role,
            "test_set_role": "Baseline Benchmark" if "Rule B" in rule_name else "Baseline Reference",
            "cutoff_rule": f"ratio > 1.00 * threshold_p75 (Fixed; {n_nonnull:,}/53,495 non-null lags)",
            "settings_tested": 1,
            "n_eval_53406": mc["n_eval"],
            "actual_pos_53406": mc["actual_positive"],
            "pred_pos_53406": mc["pred_positive"],
            "precision_53406": mc["precision"],
            "recall_53406": mc["recall"],
            "f1_53406": mc["f1"],
            "pr_auc_53406": mc["pr_auc"],
            "roc_auc_53406": mc["roc_auc"],
            "precision_at_13081_53406": mw["precision"] if "Rule A" in rule_name else mc["precision"],
            "f1_at_13081_53406": mw["f1"] if "Rule A" in rule_name else mc["f1"],
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
        mw = metrics_at_fixed_workload(y_val_common, b["probs_common"], k_flagged=k_rule_b)
        test_role = (
            "Dedicated Classifier Comparison (Official Test Candidate)"
            if fam == "HistGradientBoosting Classifier"
            else "Validation Candidate"
        )
        comp_rows.append({
            "model_name": f"{fam} ({b['setting_description']})",
            "model_category": "Direct Classifier (Class Weights)",
            "test_set_role": test_role,
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
            "precision_at_13081_53406": mw["precision"],
            "f1_at_13081_53406": mw["f1"],
            "n_eval_all_active": b["n_eval_all_active"],
            "precision_all_active": b["precision_53495"],
            "recall_all_active": b["recall_53495"],
            "f1_all_active": b["f1_53495"],
            "pr_auc_all_active": b["pr_auc_53495"],
            "f1_gain_vs_rule_b": round(b["f1_53406"] - 0.6665, 4),
        })

    # Forecast ÷ Trips:
    # - Official Rule (0.96x Threshold): chosen because our stated validation rule is to maximise F1.
    # - Side Checks (1.00x Unadjusted and 1.03x Bias-Corrected): reported as validation diagnostic checks only.
    mw_div = metrics_at_fixed_workload(y_val_common, ratio_common, k_flagged=k_rule_b)
    for mult, label, test_role, rule_desc in [
        (
            0.96,
            "Forecast ÷ Trips: Official Max-F1 Rule (0.96x Threshold)",
            "Recommended Main Approach (Official Test Candidate)",
            "ratio > 0.96 * threshold_p75 (Official Max-F1 Rule Selected on Validation)",
        ),
        (
            1.00,
            "Forecast ÷ Trips: Unadjusted Side Check (1.00x Threshold)",
            "Validation Side Check Only (Not Taken to Test)",
            "ratio > 1.00 * threshold_p75 (Unadjusted check; +8.83 bias flags 14,748 hrs)",
        ),
        (
            1.03,
            "Forecast ÷ Trips: Bias-Corrected Side Check (1.03x Threshold)",
            "Validation Side Check Only (Not Taken to Test)",
            "ratio > 1.03 * threshold_p75 (Side check offsetting +3.5% seasonal bias)",
        ),
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
            "test_set_role": test_role,
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
            "precision_at_13081_53406": mw_div["precision"],
            "f1_at_13081_53406": mw_div["f1"],
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

    # Build dedicated fair ranking table sorted by PR-AUC (cutoff-free) and Equal-Workload Precision (13,081 hours)
    fair_rows = []
    for idx_r, r in comp_df.iterrows():
        if "Side Check" in str(r["test_set_role"]):
            continue
        fair_rows.append({
            "model_name": r["model_name"],
            "test_set_role": r["test_set_role"],
            "pr_auc_53406": r["pr_auc_53406"],
            "roc_auc_53406": r["roc_auc_53406"],
            "precision_at_13081_hours": r["precision_at_13081_53406"],
            "f1_at_13081_hours": r["f1_at_13081_53406"],
            "pred_pos_at_max_f1": r["pred_pos_53406"],
            "precision_at_max_f1": r["precision_53406"],
            "recall_at_max_f1": r["recall_53406"],
            "f1_at_max_f1": r["f1_53406"],
        })
    fair_df = pd.DataFrame(fair_rows).sort_values("pr_auc_53406", ascending=False).reset_index(drop=True)
    fair_df["pr_auc_rank"] = np.arange(1, len(fair_df) + 1)
    fair_df = fair_df[[
        "pr_auc_rank",
        "model_name",
        "test_set_role",
        "pr_auc_53406",
        "precision_at_13081_hours",
        "f1_at_13081_hours",
        "pred_pos_at_max_f1",
        "precision_at_max_f1",
        "recall_at_max_f1",
        "f1_at_max_f1",
    ]]
    fair_path = TAB_DIR / "m3_classification_fair_ranking.csv"
    fair_df.to_csv(fair_path, index=False)
    print("\nFair Cutoff-Free (PR-AUC) & Equal-Workload (13,081 Flagged Hours) Ranking:", flush=True)
    print(fair_df.to_string(index=False), flush=True)

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
    # GENERATE STEP 3 FIGURE: FAIR RANKING (PR-AUC & EQUAL WORKLOAD) + PR CURVES
    # ==========================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.4), dpi=150)

    # Panel A: Grouped bar chart of PR-AUC, Equal-Workload Precision (13,081 hrs), and Max-F1 on 53,406 common rows
    # Order matches fair_df ranking (plus Forecast÷Trips 1.03x side check for reference)
    row_rule_a = comp_df[comp_df["model_name"].str.contains("Rule A")].iloc[0]
    row_rule_b = comp_df[comp_df["model_name"].str.contains("Rule B")].iloc[0]
    row_lr = comp_df[comp_df["model_name"].str.contains("Logistic Regression")].iloc[0]
    row_rf = comp_df[comp_df["model_name"].str.contains("Random Forest Classifier")].iloc[0]
    row_hgb = comp_df[comp_df["model_name"].str.contains("HistGradientBoosting Classifier")].iloc[0]
    row_div_096 = comp_df[comp_df["model_name"].str.contains("0.96x")].iloc[0]
    row_div_103 = comp_df[comp_df["model_name"].str.contains("1.03x")].iloc[0]

    plot_models = [
        ("Rule A\n(7-Day Lag)", row_rule_a["pr_auc_53406"], row_rule_a["precision_at_13081_53406"], row_rule_a["f1_53406"]),
        ("Logistic Reg\n(Cut=0.48)", row_lr["pr_auc_53406"], row_lr["precision_at_13081_53406"], row_lr["f1_53406"]),
        ("Rule B Hurdle\n(4-Wk Avg)", row_rule_b["pr_auc_53406"], row_rule_b["precision_at_13081_53406"], row_rule_b["f1_53406"]),
        ("Random Forest\n(Cut=0.55)", row_rf["pr_auc_53406"], row_rf["precision_at_13081_53406"], row_rf["f1_53406"]),
        ("Forecast÷Trips\n(0.96x Official)", row_div_096["pr_auc_53406"], row_div_096["precision_at_13081_53406"], row_div_096["f1_53406"]),
        ("HGB Classifier\n(Cut=0.63)", row_hgb["pr_auc_53406"], row_hgb["precision_at_13081_53406"], row_hgb["f1_53406"]),
    ]
    x = np.arange(len(plot_models))
    w = 0.25
    pr_auc_vals = [m[1] for m in plot_models]
    p_eq_vals = [m[2] for m in plot_models]
    f1_vals = [m[3] for m in plot_models]

    bars_pr = ax1.bar(x - w, pr_auc_vals, w, label="PR-AUC (Cutoff-Free)", color="#1e3a8a", edgecolor="#0f172a")
    bars_peq = ax1.bar(x, p_eq_vals, w, label="Precision @ 13,081 Hrs (Rule B Workload)", color="#059669", edgecolor="#064e3b")
    bars_f1 = ax1.bar(x + w, f1_vals, w, label="Max F1 (Chosen Cutoff)", color="#93c5fd", edgecolor="#1d4ed8")
    ax1.axhline(row_rule_b["pr_auc_53406"], color="#1e3a8a", linestyle="--", linewidth=1.0, alpha=0.7, label="Rule B PR-AUC (0.690)")
    ax1.axhline(row_rule_b["precision_at_13081_53406"], color="#dc2626", linestyle=":", linewidth=1.2, label="Rule B Precision @ 13,081 Hrs (0.664)")
    for b in bars_pr:
        h = b.get_height()
        ax1.text(b.get_x() + b.get_width() / 2.0, h + 0.008, f"{h:.3f}", ha="center", va="bottom", fontsize=6.8, fontweight="bold", color="#1e3a8a")
    for b in bars_peq:
        h = b.get_height()
        ax1.text(b.get_x() + b.get_width() / 2.0, h + 0.008, f"{h:.3f}", ha="center", va="bottom", fontsize=6.8, fontweight="bold", color="#065f46")
    ax1.set_title("A. Fair Model Comparison: PR-AUC, Equal-Workload Precision & Max F1", fontsize=10, fontweight="bold", pad=8)
    ax1.set_ylabel("Score (53,406 Common Active Rows)", fontsize=9.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels([m[0] for m in plot_models], fontsize=7.8)
    ax1.set_ylim(0.50, 0.84)
    ax1.grid(axis="y", alpha=0.3)
    ax1.legend(loc="upper left", fontsize=7.5, ncol=2)

    # Panel B: Precision-Recall Curves & Operating Points
    for name, scores, color, ls in [
        (f"HGB Direct Classifier (PR-AUC = {row_hgb['pr_auc_53406']:.3f})", best_hgb_info["probs_common"], "#1d4ed8", "-"),
        (f"Forecast ÷ Trips (HGB, PR-AUC = {row_div_096['pr_auc_53406']:.3f})", score_div_common, "#059669", "-."),
        (f"Random Forest Classifier (PR-AUC = {row_rf['pr_auc_53406']:.3f})", best_family_info["Random Forest Classifier"]["probs_common"], "#7c3aed", "--"),
        (f"Logistic Regression (PR-AUC = {row_lr['pr_auc_53406']:.3f})", best_family_info["Logistic Regression"]["probs_common"], "#94a3b8", ":"),
    ]:
        prec_c, rec_c, _ = precision_recall_curve(y_val_common, scores)
        ax2.plot(rec_c, prec_c, color=color, linestyle=ls, linewidth=1.8, label=name)

    # Plot operating points for Rule B, Equal-Workload (13,081 hrs), Forecast÷Trips 0.96x (Official), 1.03x (Side Check), and HGB Clf
    ax2.scatter([row_rule_b["recall_53406"]], [row_rule_b["precision_53406"]], color="#dc2626", s=65, zorder=5, marker="D", label="Rule B (13,081 hrs: P=0.664, R=0.669)")
    ax2.scatter([row_div_096["recall_53406"]], [row_div_096["precision_53406"]], color="#047857", s=70, zorder=5, marker="s", label="Forecast÷Trips 0.96x Official (17,789 hrs: P=0.605, R=0.829)")
    ax2.scatter([row_div_103["recall_53406"]], [row_div_103["precision_53406"]], color="#10b981", s=65, zorder=5, marker="^", label="Forecast÷Trips 1.03x Side Check (12,660 hrs: P=0.688, R=0.671)")
    ax2.scatter([row_hgb["recall_53406"]], [row_hgb["precision_53406"]], color="#1d4ed8", s=65, zorder=5, marker="o", label="HGB Clf Cut=0.63 (18,390 hrs: P=0.585, R=0.829)")

    ax2.set_title("B. Validation Precision–Recall Curves & Cutoff Operating Points", fontsize=10, fontweight="bold", pad=8)
    ax2.set_xlabel("Recall (Share of True High-Demand Hours Flagged)", fontsize=9.5)
    ax2.set_ylabel("Precision (Share of Flagged Hours Truly High-Demand)", fontsize=9.5)
    ax2.set_xlim(0.20, 1.00)
    ax2.set_ylim(0.35, 0.95)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="lower left", fontsize=7.2)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "m3_classification_model_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved Step 3 classification figure to reports/figures/m3_classification_model_comparison.png", flush=True)


def refresh_step3_comparison() -> None:
    """Fast refresh of Step 3 comparison tables and figures using saved tuning results and models."""
    train_df = load_dataset("train")
    val_df = load_dataset("val")
    preprocessor = joblib.load(MODELS_DIR / "preprocessor.joblib")

    tr_active_mask = (train_df["trips_running"] > 0) & train_df["threshold_p75"].notnull()
    va_active_mask = (val_df["trips_running"] > 0) & val_df["threshold_p75"].notnull()
    tr_clf = train_df[tr_active_mask].copy()
    va_clf = val_df[va_active_mask].copy()

    common_in_va_clf = (
        va_clf["lag_7d"].notnull() & va_clf["lag_mean_available"].notnull()
    ).values

    y_train = tr_clf["high_demand_per_trip"].values.astype(int)
    y_val_all = va_clf["high_demand_per_trip"].values.astype(int)
    y_val_common = y_val_all[common_in_va_clf]

    X_train = preprocessor.transform(tr_clf[ALL_FEATURES])
    X_val_all = preprocessor.transform(va_clf[ALL_FEATURES])
    X_val_common = X_val_all[common_in_va_clf]

    tuning_df = pd.read_csv(TAB_DIR / "m3_classification_tuning_results.csv")
    clf_bundle = joblib.load(MODELS_DIR / "best_classifier.joblib")
    best_hgb_pipe = clf_bundle["pipeline"]

    # Fit only the single best LogisticRegression and RandomForestClassifier from tuning_df
    print("Fitting best Logistic Regression (C=1.0, class_weight=weight_1:1.5)...", flush=True)
    lr_est = LogisticRegression(C=1.0, class_weight={0: 1.0, 1: 1.5}, max_iter=1000, random_state=42)
    lr_est.fit(X_train, y_train)
    probs_lr_c = lr_est.predict_proba(X_val_common)[:, 1]
    probs_lr_a = lr_est.predict_proba(X_val_all)[:, 1]

    print("Fitting best Random Forest Classifier (depth=18, leaf=5, feat=0.8, cw=balanced)...", flush=True)
    rf_est = RandomForestClassifier(
        n_estimators=200, max_depth=18, min_samples_leaf=5, max_features=0.8,
        class_weight="balanced", n_jobs=-1, random_state=42,
    )
    rf_est.fit(X_train, y_train)
    probs_rf_c = rf_est.predict_proba(X_val_common)[:, 1]
    probs_rf_a = rf_est.predict_proba(X_val_all)[:, 1]

    probs_hgb_c = best_hgb_pipe.predict_proba(va_clf[ALL_FEATURES].iloc[np.where(common_in_va_clf)[0]])[:, 1]
    probs_hgb_a = best_hgb_pipe.predict_proba(va_clf[ALL_FEATURES])[:, 1]

    best_family_info = {}
    for fam, probs_c, probs_a, est in [
        ("Logistic Regression", probs_lr_c, probs_lr_a, lr_est),
        ("Random Forest Classifier", probs_rf_c, probs_rf_a, rf_est),
        ("HistGradientBoosting Classifier", probs_hgb_c, probs_hgb_a, best_hgb_pipe.named_steps["classifier"]),
    ]:
        sub_t = tuning_df[tuning_df["model_family"] == fam].sort_values("f1_53406", ascending=False).iloc[0]
        row_d = sub_t.to_dict()
        row_d["probs_common"] = probs_c
        row_d["probs_all"] = probs_a
        row_d["estimator"] = est
        best_family_info[fam] = row_d

    # Forecast ÷ Trips from best forecaster
    forecaster_bundle = joblib.load(MODELS_DIR / "best_forecaster.joblib")
    best_forecaster = forecaster_bundle["pipeline"]
    pred_riders_all = np.clip(best_forecaster.predict(va_clf[ALL_FEATURES]), 0.0, None)
    pred_rpt_all = pred_riders_all / va_clf["trips_running"].values
    thresh_all = va_clf["threshold_p75"].values
    ratio_all = pred_rpt_all / thresh_all
    ratio_common = ratio_all[common_in_va_clf]
    score_div_all = np.clip(ratio_all / 2.0, 0.0, 1.0)
    score_div_common = score_div_all[common_in_va_clf]
    m_at_100 = compute_classification_metrics(
        y_val_common, (ratio_common > 1.00).astype(int), score_div_common
    )

    build_step3_comparison_and_figures(
        va_clf=va_clf,
        common_in_va_clf=common_in_va_clf,
        y_val_common=y_val_common,
        y_val_all=y_val_all,
        ratio_common=ratio_common,
        ratio_all=ratio_all,
        score_div_common=score_div_common,
        score_div_all=score_div_all,
        m_at_100=m_at_100,
        best_family_info=best_family_info,
        tuning_df=tuning_df,
        preprocessor=preprocessor,
    )


if __name__ == "__main__":
    import sys
    if "--refresh-only" in sys.argv:
        refresh_step3_comparison()
    else:
        run_step3_classification()


