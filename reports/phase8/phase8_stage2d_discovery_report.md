# AI_RouteRanker — Milestone 8 Stage 2D: Historical Prediction Artifact Discovery Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Stage:** 2D — Historical Forecasting API  
**Date:** 2026-11-25T19:19:00+05:30  
**Status:** DISCOVERY COMPLETE  

---

## 1. Executive Summary

Inspection of `artifacts/random_forest/` and `reports/modeling/random_forest/` verified five canonical historical prediction Parquet artifacts produced by the approved tuned Random Forest models (**Candidate 3 Champion** for both Tier 1 and Tier 2), along with authoritative aggregate evaluation metrics (`final_model_evaluation_metrics.csv`, `random_forest_champion_config.json`).

**Critical Limitation:** Both tuned Random Forest models rely on observed autoregressive lag features (`rides_lag_1/7/14/28`, `rolling_mean_7/14/28`) and no verified future-inference pipeline exists. Therefore, the API exposes **historical evaluation results only** (`forecast_scope: "historical_evaluation_only"`, `future_forecasting_supported: false`).

---

## 2. Verified Historical Prediction Artifacts Inventory

| Tier | Period | File Path | Size (B) | Shape | Date Coverage | Routes | Nulls / Dups | SHA-256 |
| :---: | :--- | :--- | :---: | :---: | :--- | :---: | :---: | :--- |
| **Tier 1** | `validation` | `artifacts/random_forest/tier1_val_predictions_tuned.parquet` | 560,317 | `37,786 x 6` | `2025-01-01` .. `2025-11-22` | 129 | `0` / `0` | `4214b9140711c2f1901acb2252b0d90ee25fe095bd240acc65ab4af2a5879f3e` |
| **Tier 1** | `test` | `artifacts/random_forest/tier1_test_predictions_tuned.parquet` | 492,573 | `28,798 x 7` | `2025-11-23` .. `2026-07-31` | 128 | `0` / `0` | `3d1a70b6d447544eb4d3f862a1fd9bcb490f28b2a8725e93ab1e76187402c9a2` |
| **Tier 1** | `august_holdout` | `artifacts/random_forest/tier1_august_predictions_tuned.parquet` | 75,841 | `3,566 x 7` | `2026-08-01` .. `2026-08-31` | 128 | `0` / `0` | `33c59e2e4438475dea175fbd39ede81e930eb953451fa35683a7c1fad5281e06` |
| **Tier 2** | `validation` | `artifacts/random_forest/tier2_val_predictions_tuned.parquet` | 64,124 | `4,117 x 6` | `2026-04-24` .. `2026-05-29` | 127 | `0` / `0` | `f0f0bb8f4c86892b998e5cf30f9bb3feeaaaf7dd4873800133e3fd3cd5c2981e` |
| **Tier 2** | `test` | `artifacts/random_forest/tier2_test_predictions_tuned.parquet` | 144,215 | `7,293 x 7` | `2026-05-30` .. `2026-07-31` | 127 | `0` / `0` | `4b6825dedc8d601c831e4483e64ee896dc952fca71ff798dd007bc31427e72fb` |

### Schema Differences Identified
- **Validation files (`*_val_predictions_tuned.parquet`)**: `['route', 'date', 'daytype', 'target_rides', 'pred_random_forest', 'residual']`.
- **Test & Holdout files (`*_test_predictions_tuned.parquet`, `tier1_august_predictions_tuned.parquet`)**: `['route', 'date', 'daytype', 'target_rides', 'rf_tuned_prediction', 'pred_baseline_b_seasonal_naive', 'fallback_baseline_b']`.

---

## 3. Provenance & Leakage Separation

- All 5 prediction files correspond to the tuned Candidate 3 champion models (`tier1_random_forest_tuned.joblib`, SHA-256 `d73b7901...`; `tier2_random_forest_tuned.joblib`, SHA-256 `dafa999d...`).
- Hyperparameter selection (`random_forest_champion_config.json`) used strictly the validation partitions (`tier1` WAPE `7.2430%`, $R^2=0.9822$; `tier2` WAPE `5.6173%`, $R^2=0.9904$). Test and August holdout partitions were evaluated strictly post-selection (`final_model_evaluation_metrics.csv`).
- **Unsupported Combinations:** `tier2` + `august_holdout` does **not** exist in the approved evaluation design and must be rejected with HTTP 400.
- **Rail Exclusion:** CTA heavy rail lines are not included in the Random Forest demand models (`127–129` bus routes only).
