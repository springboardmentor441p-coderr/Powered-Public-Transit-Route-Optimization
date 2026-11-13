"""
Unit tests for Milestone 3 evaluation framework (src/evaluate.py).
Tests core metrics calculation, zero-demand WAPE edge cases, test-set access enforcement,
canonical time-band breakdown labeling, and baseline hurdles.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.evaluate import (
    compute_forecast_metrics,
    compute_forecast_breakdown,
    evaluate_forecasting,
    compute_classification_metrics,
    compute_classification_breakdown,
    evaluate_classification,
    format_confusion_matrix,
    load_dataset,
    TEST_LOG_PATH,
)
from src.eda_utils import TIME_BANDS, get_time_band_label

ROOT = Path(__file__).resolve().parents[1]
VAL_PATH = ROOT / "data" / "processed" / "val_features.parquet"


# ==============================================================================
# 1. FORECASTING METRICS TESTS
# ==============================================================================

def test_compute_forecast_metrics_exact():
    y_true = np.array([100.0, 200.0, 300.0])
    y_pred = np.array([110.0, 190.0, 330.0])  # errors: 10, 10, 30 -> sum = 50
    # sum_y = 600
    # MAE = 50 / 3 = 16.67
    # RMSE = sqrt((100 + 100 + 900)/3) = sqrt(1100/3) = sqrt(366.67) = 19.15
    # WAPE = 50 / 600 * 100 = 8.33%
    # Bias = (10 - 10 + 30)/3 = +10.0
    m = compute_forecast_metrics(y_true, y_pred)
    assert m["n_eval"] == 3
    assert m["total_actual"] == 600.0
    assert m["total_pred"] == 630.0
    assert m["mae"] == 16.67
    assert m["rmse"] == 19.15
    assert m["wape_pct"] == 8.33
    assert m["bias_pred_minus_actual"] == 10.0


def test_compute_forecast_metrics_handles_nans_and_empty():
    y_true = np.array([10.0, np.nan, 20.0])
    y_pred = np.array([np.nan, 15.0, 25.0])
    m = compute_forecast_metrics(y_true, y_pred)
    assert m["n_eval"] == 1
    assert m["mae"] == 5.0
    assert m["wape_pct"] == 25.0

    empty_m = compute_forecast_metrics(np.array([]), np.array([]))
    assert empty_m["n_eval"] == 0
    assert np.isnan(empty_m["mae"])


def test_wape_zero_riders_is_nan():
    """Verify that when actual ridership total is 0, WAPE is reported as NaN, never 0.0 or inf."""
    y_true = np.array([0.0, 0.0, 0.0])
    y_pred = np.array([5.0, 2.0, 1.0])
    m = compute_forecast_metrics(y_true, y_pred)
    assert m["n_eval"] == 3
    assert m["total_actual"] == 0.0
    assert np.isnan(m["wape_pct"]), "WAPE with 0 actual riders must be NaN"


def test_evaluate_forecasting_with_breakdowns_and_storms():
    df = pd.DataFrame({
        "route": ["M1", "M1", "M2", "M2"],
        "day_type": ["Typical Weekday", "Typical Weekday", "Typical Sunday", "Typical Sunday"],
        "time_band": ["morning_peak", "evening_peak", "morning_peak", "evening_peak"],
        "is_storm": [False, True, False, False],
        "ridership": [100, 50, 200, 150],
        "pred": [90, 40, 210, 160],
    })
    res = evaluate_forecasting(df, y_true_col="ridership", y_pred_col="pred", model_name="TestModel")
    assert "overall" in res
    assert "by_route" in res
    assert "by_day_type" in res
    assert "by_time_band" in res

    # Because df contains storm days, overall must contain All Hours, Without Storm Days, and Storm Days Only
    subsets = set(res["overall"]["subset"])
    assert "All Hours" in subsets
    assert "Without Storm Days" in subsets
    assert "Storm Days Only" in subsets


def test_time_band_breakdown_uses_canonical_labels():
    """Verify that time_band breakdown reads existing column and attaches Milestone 1 hour labels."""
    df = pd.DataFrame({
        "route": ["M1", "M1", "M2", "M2"],
        "day_type": ["Typical Weekday"] * 4,
        "time_band": ["early_morning", "morning_peak", "midday", "night"],
        "is_storm": [False] * 4,
        "ridership": [20, 80, 120, 30],
        "pred": [22, 75, 130, 28],
    })
    bd = compute_forecast_breakdown(df, group_col="time_band", y_true_col="ridership", y_pred_col="pred")
    assert "time_band_label" in bd.columns
    early_row = bd[bd["time_band"] == "early_morning"].iloc[0]
    assert "04:00–06:59" in early_row["time_band_label"]
    assert "Early Morning" in early_row["time_band_label"]


# ==============================================================================
# 2. CLASSIFICATION METRICS TESTS
# ==============================================================================

def test_compute_classification_metrics_exact():
    # 2 TP, 1 FP, 1 FN, 2 TN -> total 6
    # y_true = [1, 1, 1, 0, 0, 0]
    # y_pred = [1, 1, 0, 1, 0, 0]
    y_true = np.array([1, 1, 1, 0, 0, 0])
    y_pred = np.array([1, 1, 0, 1, 0, 0])
    y_prob = np.array([0.9, 0.8, 0.4, 0.7, 0.2, 0.1])

    m = compute_classification_metrics(y_true, y_pred, y_prob)
    assert m["n_eval"] == 6
    assert m["tp"] == 2
    assert m["fp"] == 1
    assert m["fn"] == 1
    assert m["tn"] == 2
    assert m["precision"] == 0.6667
    assert m["recall"] == 0.6667
    assert m["f1"] == 0.6667
    assert not np.isnan(m["pr_auc"])
    assert m["pr_auc"] > 0.5


def test_format_confusion_matrix():
    cm_dict = {"tn": 100, "fp": 10, "fn": 5, "tp": 50}
    df_cm = format_confusion_matrix(cm_dict, model_name="TestClf")
    assert df_cm.shape == (3, 5)
    assert df_cm.loc[df_cm["Actual Class"] == "Actual High Demand (1)", "Pred High (1)"].iloc[0] == 50
    assert df_cm.loc[df_cm["Actual Class"] == "Total Predicted", "Total Actual"].iloc[0] == 165


# ==============================================================================
# 3. TEST SET ACCESS ENFORCEMENT & AUDIT TRAIL
# ==============================================================================

def test_load_dataset_test_isolation_enforcement():
    """Verify that load_dataset('test') raises PermissionError without final=True,
    and succeeds with an audit log when final=True.
    """
    with pytest.raises(PermissionError) as exc_info:
        load_dataset("test")
    assert "Access to test_features.parquet is restricted" in str(exc_info.value)

    with pytest.raises(PermissionError) as exc_info_flag:
        load_dataset("test", final=False)
    assert "Access to test_features.parquet is restricted" in str(exc_info_flag.value)

    # Calling with final=True must succeed and append to test_runs.log
    existed_before = TEST_LOG_PATH.exists()
    prior_content = TEST_LOG_PATH.read_text(encoding="utf-8") if existed_before else ""
    try:
        test_df = load_dataset("test", final=True, caller="test_load_dataset_test_isolation_enforcement")
        assert isinstance(test_df, pd.DataFrame)
        assert len(test_df) == 53736
        assert TEST_LOG_PATH.exists()

        with open(TEST_LOG_PATH, "r", encoding="utf-8") as f:
            log_content = f.read()
        assert "AUDIT TEST ACCESS" in log_content
        assert "test_load_dataset_test_isolation_enforcement" in log_content
    finally:
        if existed_before:
            TEST_LOG_PATH.write_text(prior_content, encoding="utf-8")
        elif TEST_LOG_PATH.exists():
            TEST_LOG_PATH.unlink()


def test_validation_no_storm_days_note():
    """Verify that when a split has 0 storm days (like validation), the duplicate
    'Without Storm Days' row is omitted and replaced with a storm_note annotation.
    """
    val_df = load_dataset("val")
    common_mask = (
        val_df["ridership"].notnull()
        & val_df["lag_7d"].notnull()
        & val_df["lag_mean_available"].notnull()
    )
    val_eval = val_df[common_mask].copy()
    res = evaluate_forecasting(
        val_eval,
        y_true_col="ridership",
        y_pred_col="lag_mean_available",
        model_name="4WkCheck",
    )
    overall = res["overall"]
    assert "Without Storm Days" not in set(overall["subset"])
    assert "storm_note" in overall.columns
    assert "0 storm days in window" in str(overall["storm_note"].iloc[0])


# ==============================================================================
# 4. VALIDATION SET REPRODUCTION & BASELINE HURDLES
# ==============================================================================

def test_validation_4wk_baseline_hurdle():
    """Verify that 4-week average baseline evaluated on validation matches 14.08% WAPE."""
    val_df = load_dataset("val")
    common_mask = (
        val_df["ridership"].notnull()
        & val_df["lag_7d"].notnull()
        & val_df["lag_mean_available"].notnull()
    )
    val_eval = val_df[common_mask].copy()
    assert len(val_eval) == 53585

    m_4wk = compute_forecast_metrics(val_eval["ridership"], val_eval["lag_mean_available"])
    assert m_4wk["wape_pct"] == 14.08, f"Expected 14.08% WAPE, got {m_4wk['wape_pct']}"

    m_lag7 = compute_forecast_metrics(val_eval["ridership"], val_eval["lag_7d"])
    assert m_lag7["wape_pct"] == 17.48, f"Expected 17.48% WAPE, got {m_lag7['wape_pct']}"
    assert m_4wk["wape_pct"] < m_lag7["wape_pct"]


def test_stronger_classification_baseline_hurdle():
    """Verify that the 4-week average heuristic classification rule outperforms lag_7d."""
    val_df = load_dataset("val")
    valid_mask = (
        (val_df["trips_running"] > 0)
        & val_df["threshold_p75"].notnull()
        & val_df["lag_7d"].notnull()
        & val_df["lag_mean_available"].notnull()
    )
    val_eval = val_df[valid_mask].copy()
    assert len(val_eval) == 53406

    y = val_eval["high_demand_per_trip"].values

    rpt_7d = val_eval["lag_7d"] / val_eval["trips_running"]
    pred_7d = (rpt_7d > val_eval["threshold_p75"]).astype(int)
    prob_7d = np.clip(rpt_7d / (2.0 * val_eval["threshold_p75"]), 0.0, 1.0)
    m_7d = compute_classification_metrics(y, pred_7d, prob_7d)

    rpt_4wk = val_eval["lag_mean_available"] / val_eval["trips_running"]
    pred_4wk = (rpt_4wk > val_eval["threshold_p75"]).astype(int)
    prob_4wk = np.clip(rpt_4wk / (2.0 * val_eval["threshold_p75"]), 0.0, 1.0)
    m_4wk = compute_classification_metrics(y, pred_4wk, prob_4wk)

    # 4-week rule must be strictly superior to 7-day rule on F1, Precision, and PR-AUC
    assert m_4wk["f1"] > m_7d["f1"], f"4wk F1 {m_4wk['f1']} should exceed 7d F1 {m_7d['f1']}"
    assert m_4wk["precision"] > m_7d["precision"]
    assert m_4wk["pr_auc"] > m_7d["pr_auc"]


# ==============================================================================
# 5. MILESTONE 3 STEP 2: FORECASTING MODELS, TUNING & DIAGNOSTICS
# ==============================================================================

def test_step2_forecasting_outputs_and_hurdle():
    """Verify Step 2 forecasting tuning grid (10-20 settings per family),
    53,585 vs 54,046 row reporting, permutation importance, and worst misses table.
    """
    tab_dir = ROOT / "reports" / "tables"
    fig_dir = ROOT / "reports" / "figures"

    tuning_df = pd.read_csv(tab_dir / "m3_forecast_tuning_results.csv")
    comp_df = pd.read_csv(tab_dir / "m3_forecast_model_comparison.csv")
    perm_df = pd.read_csv(tab_dir / "m3_forecast_permutation_importance.csv")
    misses_df = pd.read_csv(tab_dir / "m3_forecast_worst_misses.csv")

    expected_families = {
        "Ridge (riders)",
        "Ridge (log(1 + riders))",
        "Random Forest",
        "HistGradientBoosting",
    }
    assert set(tuning_df["model_family"].unique()) == expected_families

    # Each model family must have 10 to 20 validation settings tested
    for fam in expected_families:
        n_settings = int((tuning_df["model_family"] == fam).sum())
        assert 10 <= n_settings <= 20, f"{fam} has {n_settings} settings; expected 10..20"

    # Comparison table must report both 53,585 common rows and 54,046 all validation rows
    ml_rows = comp_df[comp_df["model_type"] == "ML Model"]
    assert len(ml_rows) == 4
    assert (ml_rows["n_eval_53585"] == 53585).all()
    assert (ml_rows["n_eval_all_val"] == 54046).all()

    # Best model must beat the 14.08% WAPE 4-week average baseline on the 53,585 rows
    best_wape = ml_rows["wape_53585_pct"].min()
    assert best_wape < 14.08, f"Best model WAPE {best_wape}% did not beat 14.08% baseline"

    # Permutation importance must rank all 22 input features
    assert len(perm_df) == 22
    assert perm_df.iloc[0]["mae_increase_riders"] > 0

    # Worst misses table must list top 25 route-hours sorted by abs_error descending
    assert len(misses_df) == 25
    assert misses_df["abs_error"].is_monotonic_decreasing
    miss_cats = " ".join(misses_df["miss_category"].astype(str).tolist())
    assert "cause not confirmed" in miss_cats
    assert "Juneteenth" in miss_cats
    assert "weather" not in miss_cats.lower()

    # Weekly bias & WAPE check (9 validation weeks: wins 8 of 9 weeks, ties 1) and 41-route gain check
    weekly_df = pd.read_csv(tab_dir / "m3_forecast_weekly_check.csv")
    assert len(weekly_df) == 9
    assert int((weekly_df["weekly_outcome"] == "Win").sum()) == 8
    assert int((weekly_df["weekly_outcome"] == "Tie").sum()) == 1
    assert int((weekly_df["weekly_outcome"] == "Loss").sum()) == 0

    route_gain_df = pd.read_csv(tab_dir / "m3_forecast_route_gain_check.csv")
    assert len(route_gain_df) == 41
    assert int(route_gain_df["hgb_improves_wape"].sum()) == 37

    # Figures must exist and be non-empty
    for fig_name in [
        "m3_forecast_model_comparison.png",
        "m3_forecast_permutation_importance.png",
        "m3_forecast_weekly_bias_wape.png",
    ]:
        p = fig_dir / fig_name
        assert p.exists() and p.stat().st_size > 10_000


# ==============================================================================
# 6. MILESTONE 3 STEP 3: CLASSIFICATION MODELS & FORECAST ÷ TRIPS CHECK
# ==============================================================================

def test_step3_classification_outputs_and_hurdle():
    """Verify Step 3 classification tuning grid, 53,406 vs 53,495 active-row comparison,
    Rule B hurdle (F1 > 0.6665, PR-AUC > 0.6904), PR-AUC & equal-workload (13,081 hours)
    ranking, and Forecast ÷ Trips official 0.96x rule vs 1.03x side check.
    """
    tab_dir = ROOT / "reports" / "tables"
    fig_dir = ROOT / "reports" / "figures"

    tuning_df = pd.read_csv(tab_dir / "m3_classification_tuning_results.csv")
    comp_df = pd.read_csv(tab_dir / "m3_classification_model_comparison.csv")
    fair_df = pd.read_csv(tab_dir / "m3_classification_fair_ranking.csv")

    expected_families = {
        "Logistic Regression",
        "Random Forest Classifier",
        "HistGradientBoosting Classifier",
        "Forecast ÷ Trips (HGB)",
    }
    assert set(tuning_df["model_family"].unique()) == expected_families
    for fam in expected_families:
        n_settings = int((tuning_df["model_family"] == fam).sum())
        assert 10 <= n_settings <= 20, f"{fam} has {n_settings} settings; expected 10..20"

    # Verify common active-service row count (53,406) and all active-service rows (53,495) for ALL rows
    assert (comp_df["n_eval_53406"] == 53406).all()
    assert (comp_df["n_eval_all_active"] == 53495).all()
    assert "precision_at_13081_53406" in comp_df.columns

    ml_comp = comp_df[~comp_df["model_category"].str.startswith("Baseline")]
    # Best direct classifier and Forecast ÷ Trips must beat Rule B (F1 = 0.6665, PR-AUC = 0.6904)
    assert ml_comp["f1_53406"].max() > 0.6665
    assert ml_comp["pr_auc_53406"].max() > 0.6904

    # Fair ranking table must be sorted by PR-AUC descending with 6 models (excluding side checks)
    assert len(fair_df) == 6
    assert fair_df["pr_auc_53406"].is_monotonic_decreasing
    # Forecast ÷ Trips at equal workload (13,081 hours) must beat Rule B's 0.6641 precision
    div_fair = fair_df[fair_df["model_name"].str.contains("0.96x")].iloc[0]
    assert div_fair["precision_at_13081_hours"] > 0.6641
    assert "Recommended Main Approach" in div_fair["test_set_role"]

    # Verify Forecast ÷ Trips side checks (1.00x and 1.03x)
    raw_div = comp_df[comp_df["model_name"].str.contains("1.00x")].iloc[0]
    adj_div = comp_df[comp_df["model_name"].str.contains("1.03x")].iloc[0]
    assert raw_div["precision_53406"] < 0.6641
    assert adj_div["precision_53406"] > 0.6641
    assert adj_div["recall_53406"] > 0.6689
    assert adj_div["f1_53406"] > 0.6665
    assert "Side Check" in raw_div["test_set_role"]
    assert "Side Check" in adj_div["test_set_role"]

    p = fig_dir / "m3_classification_model_comparison.png"
    assert p.exists() and p.stat().st_size > 10_000


# ==============================================================================
# 7. MILESTONE 3 STEP 4: ROUTE CLUSTERING (KMEANS, STABILITY, DBSCAN, PROFILES)
# ==============================================================================

def test_step4_clustering_outputs_and_stability():
    """Verify Step 4 KMeans evaluation across k=2..6 on the 40 routes (excluding M35 outlier),
    10-start, LOO, and 1-start ARI stability checks, DBSCAN k-distance and sensitivity tables,
    41-route assignments (3 KMeans groups + M35 outlier), unscaled median profiles with
    measured-feature group names and non-fitting members, and figures/maps.
    """
    tab_dir = ROOT / "reports" / "tables"
    fig_dir = ROOT / "reports" / "figures"

    ksel_df = pd.read_csv(tab_dir / "m3_clustering_k_selection.csv")
    dbscan_df = pd.read_csv(tab_dir / "m3_clustering_dbscan_summary.csv")
    kdist_df = pd.read_csv(tab_dir / "m3_clustering_k_distance.csv")
    assigned_df = pd.read_csv(tab_dir / "m3_route_clusters_assigned.csv")
    profile_df = pd.read_csv(tab_dir / "m3_cluster_group_profiles_unscaled.csv")

    # KMeans tested for k = 2..6 on the 40 routes excluding M35
    ksel_40 = ksel_df[ksel_df["n_routes_clustered"] == 40]
    assert list(ksel_40["k"]) == [2, 3, 4, 5, 6]
    assert ksel_40["silhouette_score"].notnull().all()
    assert ksel_40["ari_10starts_mean"].notnull().all()
    assert ksel_40["ari_loo_mean"].notnull().all()
    assert ksel_40["ari_1start_mean"].notnull().all()

    # k = 3 must be selected on the 40 routes (no singletons, 0.9831 10-start ARI, 0.9126 LOO ARI)
    sel_row = ksel_40[ksel_40["is_selected_k"]].iloc[0]
    assert int(sel_row["k"]) == 3
    assert pd.isna(sel_row["singletons"]) or str(sel_row["singletons"]).lower() == "none"
    assert sel_row["ari_10starts_mean"] > 0.98
    assert sel_row["ari_loo_mean"] > 0.91

    # DBSCAN k-distance and sensitivity tables
    assert len(kdist_df) == 41
    assert kdist_df["knn_3_distance"].is_monotonic_increasing
    assert (dbscan_df["min_samples"] == 3).all()
    elbow_row = dbscan_df[dbscan_df["is_elbow_setting"]].iloc[0]
    assert float(elbow_row["eps"]) == 1.80
    assert int(elbow_row["n_clusters"]) == 3
    assert int(elbow_row["n_noise_routes"]) == 12

    # 41 routes: 40 clustered across 3 KMeans groups (18, 15, 7) + 1 pre-clustering outlier (M35 = group 0)
    assert len(assigned_df) == 41
    assert set(assigned_df["group_id"].unique()) == {0, 1, 2, 3}
    group_counts = assigned_df["group_id"].value_counts().to_dict()
    assert group_counts == {1: 18, 2: 15, 3: 7, 0: 1}
    m35_row = assigned_df[assigned_df["route_id"] == "M35"].iloc[0]
    assert int(m35_row["group_id"]) == 0
    assert "Unlike every other route" in str(m35_row["group_label"])

    # Unscaled median profiles table (3 KMeans groups + 1 M35 outlier + 1 40-route median row = 5 rows)
    assert len(profile_df) == 5
    assert set(profile_df["group_id"]) == {-1, 0, 1, 2, 3}
    assert "non_fitting_members" in profile_df.columns
    non_fit_text = " ".join(profile_df["non_fitting_members"].astype(str).tolist())
    assert "M15+" in non_fit_text
    assert "M98" in non_fit_text

    for fname in [
        "m3_clustering_evaluation.png",
        "m3_clustering_pca_and_map.png",
        "m3_route_clusters.html",
    ]:
        p = fig_dir / fname
        assert p.exists() and p.stat().st_size > 10_000


# ==============================================================================
# 8. MILESTONE 3 STEP 5: SINGLE FINAL TEST RUN & MODEL CARDS
# ==============================================================================

def test_step5_final_test_outputs_and_model_cards():
    """Verify Step 5 single official test run outputs, audit log count (1 official run),
    forecasting and classification test tables (with and without M35 surge hours, 0 storm days),
    saved model artifacts, and model cards.
    """
    import json
    import joblib

    tab_dir = ROOT / "reports" / "tables"
    fig_dir = ROOT / "reports" / "figures"
    models_dir = ROOT / "models"

    # 1. Verify reports/test_runs.log has exactly 1 official test run recorded
    log_path = ROOT / "reports" / "test_runs.log"
    assert log_path.exists()
    log_lines = [ln.strip() for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(log_lines) == 1, f"Expected exactly 1 official test run in test_runs.log, found {len(log_lines)}"
    assert "run_step5_final_test" in log_lines[0]

    # 2. Verify forecasting test tables (overall, by week, by route)
    f_ov = pd.read_csv(tab_dir / "m3_test_forecast_overall.csv")
    f_wk = pd.read_csv(tab_dir / "m3_test_forecast_by_week.csv")
    f_rt = pd.read_csv(tab_dir / "m3_test_forecast_by_route.csv")

    assert any(f_ov["evaluation_subset"].str.startswith("With M35 Surge Hours"))
    assert any(f_ov["evaluation_subset"].str.startswith("Without M35 Surge Hours"))
    assert (f_ov["storm_days_note"].str.contains("0 storm days")).all()

    hgb_with = f_ov[(f_ov["evaluation_subset"].str.startswith("With M35")) & (f_ov["model_name"].str.startswith("HistGradientBoosting"))].iloc[0]
    base_with = f_ov[(f_ov["evaluation_subset"].str.startswith("With M35")) & (f_ov["model_name"].str.startswith("4-Week"))].iloc[0]
    assert hgb_with["wape_common_pct"] < base_with["wape_common_pct"]
    assert abs(hgb_with["bias_common_pred_minus_actual"]) < abs(base_with["bias_common_pred_minus_actual"])

    assert len(f_wk) == 18  # 9 test weeks x 2 subsets (With and Without M35 Surge Hours)
    assert len(f_rt) == 82  # 41 routes x 2 subsets (With and Without M35 Surge Hours)
    rt_with = f_rt[f_rt["evaluation_subset"] == "With M35 Surge Hours"]
    rt_no = f_rt[f_rt["evaluation_subset"] == "Without M35 Surge Hours"]
    assert int(rt_with["hgb_improves_wape"].sum()) == 41
    assert int(rt_no["hgb_improves_wape"].sum()) == 41

    # 3. Verify classification test table (With and Without M35 Surge Hours)
    c_ov = pd.read_csv(tab_dir / "m3_test_classification_overall.csv")
    assert any(c_ov["evaluation_subset"].str.startswith("With M35 Surge Hours"))
    assert any(c_ov["evaluation_subset"].str.startswith("Without M35 Surge Hours"))
    assert (c_ov["storm_days_note"].str.contains("0 storm days")).all()

    div_with = c_ov[(c_ov["evaluation_subset"].str.startswith("With M35")) & (c_ov["model_name"].str.startswith("Forecast ÷ Trips"))].iloc[0]
    rb_with = c_ov[(c_ov["evaluation_subset"].str.startswith("With M35")) & (c_ov["model_name"].str.startswith("Baseline Rule B"))].iloc[0]
    assert div_with["pr_auc_common"] > rb_with["pr_auc_common"]
    assert div_with["precision_at_rule_b_workload"] > rb_with["precision_at_rule_b_workload"]
    assert div_with["f1_at_fixed_cutoff"] > rb_with["f1_at_fixed_cutoff"]

    # 4. Verify saved models and model cards
    for mfile in ["final_forecaster.joblib", "final_classifier.joblib", "route_clustering.joblib"]:
        mp = models_dir / mfile
        assert mp.exists() and mp.stat().st_size > 1_000

    cards_json = json.loads((models_dir / "model_cards.json").read_text(encoding="utf-8"))
    assert "final_forecaster" in cards_json
    assert "final_classifier" in cards_json
    for key in ["final_forecaster", "final_classifier"]:
        card = cards_json[key]
        assert "training_date_window" in card
        assert "input_features" in card and len(card["input_features"]) == 22
        assert "hyperparameters" in card
        assert "validation_scores_jan_may_fit" in card
        assert "test_scores_aug_sep_2026" in card

    md_card_path = ROOT / "reports" / "model_cards.md"
    assert md_card_path.exists() and md_card_path.stat().st_size > 1_000

    for fig_name in ["m3_test_forecast_results.png", "m3_test_classification_results.png"]:
        fp = fig_dir / fig_name
        assert fp.exists() and fp.stat().st_size > 10_000


# ==============================================================================
# 5. WEEK 5 FINAL METADATA & WEEK 6 OPERATIONAL / REALLOCATION TESTS (STEPS 6-9)
# ==============================================================================

def test_week5_final_metadata_and_single_test_log():
    import json

    assert TEST_LOG_PATH.exists()
    log_lines = [ln.strip() for ln in TEST_LOG_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(log_lines) == 1
    assert "2026-11-13" in log_lines[0]

    cards_text = (ROOT / "models" / "model_cards.json").read_text(encoding="utf-8")
    assert "2026-11-13" in cards_text
    assert "2026-11-13" in (ROOT / "reports" / "model_cards.md").read_text(encoding="utf-8")

    k_cmp_path = ROOT / "reports" / "tables" / "m3_clustering_k2_vs_k3_comparison.csv"
    assert k_cmp_path.exists()
    k_cmp = pd.read_csv(k_cmp_path)
    assert len(k_cmp) >= 5  # 2 groups for k=2 + 3 groups for k=3


def test_classify_overlap_pair_family_vs_corridor():
    from src.build_review_list import classify_overlap_pair

    assert classify_overlap_pair("M15", "M15+") == "same_family"
    assert classify_overlap_pair("M34+", "M34A+") == "same_family"
    assert classify_overlap_pair("M14A+", "M14D+") == "same_family"
    assert classify_overlap_pair("M101", "M103") == "shared_corridor"
    assert classify_overlap_pair("M1", "M2") == "shared_corridor"


def test_week6_config_and_outputs():
    import json

    cfg_path = ROOT / "configs" / "optimization_thresholds.json"
    assert cfg_path.exists()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    rw = cfg["step7_9_review_window"]
    assert rw["start_date"] == "2026-08-01"
    assert rw["end_date"] == "2026-10-31"
    assert rw["high_demand_multiplier"] == pytest.approx(1.0)

    s7 = cfg["step7_review_thresholds"]
    assert "fewer_trips_screening" in s7
    assert "more_trips_screening" in s7
    assert s7["fewer_trips_screening"]["category_name"] == "fewer_trips_candidate"
    assert s7["fewer_trips_screening"]["min_days_count"] == 20
    assert s7["fewer_trips_screening"]["min_avg_trips_per_day"] == pytest.approx(2.0)
    assert s7["more_trips_screening"]["category_name"] == "more_trips_candidate"
    assert s7["more_trips_screening"]["min_days_count"] == 20
    assert s7["more_trips_screening"]["min_avg_trips_per_day"] == pytest.approx(2.0)
    assert s7["coverage_guardrails"]["high_exclusive_stop_share"] == pytest.approx(0.60)
    assert s7["shared_corridor_overlap"]["allowed_overlap_category"] == "shared_corridor"
    assert s7["shared_corridor_overlap"]["min_overlap_share_for_merge_check"] == pytest.approx(0.40)

    s8 = cfg["step8_9_adjustment_rules"]
    assert s8["assumed_ridership_elasticity"] == pytest.approx(0.0)
    assert s8["budget_neutral_net_service_hours_max"] == pytest.approx(0.0)

    tab_dir = ROOT / "reports" / "tables"
    fig_dir = ROOT / "reports" / "figures"

    # Step 6 outputs + post-test production artifact + diagnostic checks
    assert (ROOT / "models" / "production_forecaster_jan_sep.joblib").exists()
    oct_pred = pd.read_csv(tab_dir / "m3_october_predictions.csv")
    assert len(oct_pred) == 12_270
    assert oct_pred["route"].nunique() == 41
    assert oct_pred["date"].min() == "2026-10-18"
    assert oct_pred["date"].max() == "2026-10-31"
    assert set(oct_pred["day_group"].unique()) == {"weekday", "weekend"}
    assert (oct_pred["trips_running"] >= 1).all()
    assert set(oct_pred["pred_high_demand_per_trip"].unique()).issubset({0, 1})

    oct_fc = pd.read_csv(tab_dir / "m3_october_forecast_summary.csv")
    assert len(oct_fc) == 6
    assert (oct_fc["n_active_eval"] == 12_270).all()
    assert int(oct_fc["is_production_retrain"].sum()) == 2

    oct_cls = pd.read_csv(tab_dir / "m3_october_classification_summary.csv")
    assert len(oct_cls) == 3
    assert oct_cls["actual_positive_pct"].iloc[0] == pytest.approx(37.23)

    oct_diag = pd.read_csv(tab_dir / "m3_october_diagnostic_checks.csv")
    assert len(oct_diag) >= 5
    month_row = oct_diag[oct_diag["check_name"] == "month_feature_in_model"]
    assert len(month_row) == 1 and "False" in month_row["result"].iloc[0]

    # Step 7 review list (weekday & weekend day_group split over Aug-Oct typical days)
    review_df = pd.read_csv(tab_dir / "m3_step7_review_list.csv")
    assert len(review_df) == 400
    assert review_df.duplicated(subset=["route", "day_group", "time_band"]).sum() == 0
    assert (review_df["day_group"] == "weekday").sum() == 205
    assert (review_df["day_group"] == "weekend").sum() == 195
    assert (review_df["days_count"] < 20).sum() == 2
    adj_candidates = review_df[
        review_df["review_category"].isin(["fewer_trips_candidate", "more_trips_candidate"])
    ]
    assert (adj_candidates["days_count"] >= 20).all()
    assert (adj_candidates["avg_trips_per_day"] >= 2.0).all()
    assert review_df["reason"].notna().all()
    assert review_df["reason"].str.len().min() > 20
    assert set(review_df["review_category"].unique()) == {
        "fewer_trips_candidate",
        "more_trips_candidate",
        "shared_corridor_overlap_watch",
        "no_change_watch",
    }
    for old_word in ["underused", "congested", "crowding", "crowded", "reliev"]:
        assert not review_df["reason"].str.lower().str.contains(old_word).any()

    # Step 8 scenarios + strictly shared_corridor merge checks
    scen_df = pd.read_csv(tab_dir / "m3_step8_candidate_scenarios.csv")
    assert len(scen_df) == 432
    assert set(scen_df["scenario_trip_change_pct"].unique()) == {-20, -10, 10, 20}
    assert set(scen_df["review_category"].unique()) == {
        "fewer_trips_candidate",
        "more_trips_candidate",
    }
    deep_excl = scen_df[
        (scen_df["scenario_trip_change_pct"] == -20)
        & (scen_df["exclusive_stop_share"] >= 0.60)
    ]
    assert (deep_excl["guardrail_status"] == "exceeds_10pct_exclusivity_guardrail").all()

    merge_df = pd.read_csv(tab_dir / "m3_step8_shared_corridor_merge_checks.csv")
    assert len(merge_df) == 18
    assert set(merge_df["overlap_category"].unique()) == {"shared_corridor"}
    assert int(merge_df["meets_40pct_config_rule"].sum()) == 11

    # Step 9 budget-neutral reallocation plan (within weekday and within weekend)
    realloc_df = pd.read_csv(tab_dir / "m3_step9_budget_neutral_reallocation.csv")
    assert len(realloc_df) == 39
    assert float(realloc_df["delta_service_hours"].sum()) <= 0.0
    for dg in ["weekday", "weekend"]:
        sub = realloc_df[realloc_df["day_group"] == dg]
        assert not sub.empty
        assert float(sub["delta_service_hours"].sum()) <= 0.0
    donors = realloc_df[realloc_df["delta_service_hours"] < 0]
    recips = realloc_df[realloc_df["delta_service_hours"] > 0]
    assert len(donors) == 32 and len(recips) == 7
    assert "M35" not in set(donors["route"])
    assert (donors["high_demand_hours_delta"] <= 0).all()
    assert int(realloc_df["high_demand_hours_delta"].sum()) == -219
    for old_word in ["underused", "congested", "crowding", "crowded", "reliev"]:
        assert not realloc_df["rationale"].str.lower().str.contains(old_word).any()

    for fig_name in ["m3_october_unseen_evaluation.png", "m3_step9_reallocation_summary.png"]:
        fp = fig_dir / fig_name
        assert fp.exists() and fp.stat().st_size > 10_000

    report_path = ROOT / "reports" / "milestone3_report.md"
    assert report_path.exists() and report_path.stat().st_size > 5_000
    report_txt = report_path.read_text(encoding="utf-8")
    assert "2026-11-13" in report_txt
    assert "2026-10-18" in report_txt
    assert "shared_corridor" in report_txt
    assert "constant" in report_txt.lower()
    assert "fewer_trips_candidate" in report_txt
    assert "more_trips_candidate" in report_txt
    assert "fall below the high-demand threshold" in report_txt
    assert "route-hours" in report_txt.lower()
    assert "2026-09-03" in report_txt
    assert "consistent with" in report_txt.lower()
    oct_diag_section = report_txt.split("### 7.1")[1].split("### 7.2")[0]
    assert "confirmed" not in oct_diag_section.split("Checked Diagnostic Possibilities")[1].lower()
    assert "relative to the 4-week average" in report_txt.lower()
    for old_word in ["underused", "congested", "crowding", "crowded", "relieving"]:
        assert old_word not in report_txt.lower()



