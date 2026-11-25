# 04 — Machine Learning Verification Audit (Phase D)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Audit Date:** 2026-11-25  

---

## 1. Model Bundle Inspection (Read-Only, No Retraining)
- **`artifacts/random_forest/tier1_random_forest_tuned.joblib`:** Dict bundle containing `RandomForestRegressor` (`n_features_in_ = 160`).
- **`artifacts/random_forest/tier2_random_forest_tuned.joblib`:** Dict bundle containing `RandomForestRegressor` (`n_features_in_ = 169`).

## 2. Independent Metric Reproduction from Saved Predictions
Metrics recalculated directly from `target_rides` and `rf_tuned_prediction` in the saved Parquet files:

| Tier & Period | Rows | Recalc WAPE (%) | Recalc MAE | Recalc RMSE | Recalc R² | Matches Canonical Report |
| --- | ---: | ---: | ---: | ---: | ---: | :---: |
| Tier 1 Test | 28,798 | 8.5279 | 402.1843 | 701.5721 | 0.9756 | **YES** |
| Tier 1 August Holdout | 3,566 | 8.1985 | 399.5392 | 709.6592 | 0.9761 | **YES** |
| Tier 2 Test | 7,293 | 8.1013 | 394.5119 | 671.5884 | 0.9788 | **YES** |

## 3. Serving Scope & Guardrails
- `GET /api/v1/forecasting/historical` and `/summary` explicitly report `forecast_scope: "historical_evaluation_only"` and `future_forecasting_supported: false`.
- `("tier2", "august_holdout")` is rejected with HTTP `400` on the backend and excluded from the Period selector when Tier 2 is selected in the frontend.
- Baseline B strategy provenance (`calendar_t7` -> `false`, `recent_28d_daytype`/`historical_mean` -> `true`, validation -> `null`) is preserved accurately.
