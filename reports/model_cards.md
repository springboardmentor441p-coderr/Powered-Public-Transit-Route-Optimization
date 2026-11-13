# Final Model Cards (Milestone 3 — Step 5)
*Official Single Final Test Run Date: **2026-11-13** (Audit Log: `[2026-11-13T11:30:59.750143] AUDIT TEST ACCESS: test_features.parquet loaded with final=True. Caller: src/run_final_test.py::run_step5_final_test (Single Official Test Run)`)*
*Models locked after Step 5 test run; no model weights or settings changed afterwards.*

## 1. Ridership Forecaster & Main Alerting Model (`models/final_forecaster.joblib`)
- **Model:** `HistGradientBoostingRegressor (Final Retrained Ridership Forecaster)`
- **Official Test Run Date:** `2026-11-13`
- **Training Window:** `2026-01-04 to 2026-07-31 (Train + Validation combined)` (`179,491` route-hours across `41` routes)
- **Input Features (22 columns -> 77 transformed):** `route, day_of_week, time_band, trips_running, trips_starting, service_hours, route_length_km, stop_count, hour_sin, hour_cos, is_weekend, is_public_holiday, holiday_schedule, is_storm, is_sbs, is_24h, lag_7d, lag_14d, lag_21d, lag_28d, lag_mean_available, lags_available_count`
- **Chosen Settings (Locked on Validation):** `{'loss': 'poisson', 'learning_rate': 0.05, 'max_leaf_nodes': 127, 'min_samples_leaf': 25, 'l2_regularization': 1.0, 'max_iter': 300, 'early_stopping': True, 'validation_fraction': 0.1, 'n_iter_no_change': 15, 'random_state': 42}` (`n_iter_ = 300`)
- **Validation Scores (Jun–Jul 2026, 53,585 common rows):**
  - Forecaster: `WAPE = 13.03%`, `MAE = 33.00`, `RMSE = 56.05`, `Bias = +8.83` (vs 4-week average baseline `14.08% WAPE`)
  - `Forecast ÷ Trips` (`0.96 × threshold_p75`): `PR-AUC = 0.7205`, `Precision @ 13,081 hrs = 0.6801`, `Max-F1 = 0.6998`
- **Test Scores (Aug–Sep 2026, 0 storm days — evaluated once on 2026-11-13):**
  - **Forecasting (With M35 Surge, `53,501` common rows):** `WAPE = 14.06%`, `MAE = 35.77`, `RMSE = 63.94`, `Bias = -1.89` (vs 4-week average `15.41% WAPE`, `~9%` relative error reduction; better on `41/41` routes and `7/9` weeks). Note that both the model and baseline do worse on test than validation (`14.06%` vs `13.03%`, and `15.41%` vs `14.08%`).
  - **`Forecast ÷ Trips` Classification (With M35 Surge):** `PR-AUC = 0.7165` (`0.717`), `Precision @ Rule B Workload (11,654 hrs) = 0.7166` (`0.717`, vs Rule B `0.6952` and HGB Classifier `0.7128`), `Fixed 0.96× Cutoff F1 = 0.7010` (`P = 0.6537`, `R = 0.7557`, `15,555` flagged hrs).
  - **Without M35 Surge (`6` hours on 19 Sep):** Removing those 6 hours changes forecasting and classification metrics by `0.02` points or less (`WAPE = 14.04%`, `PR-AUC = 0.7161`, `Precision @ 11,648 hrs = 0.7164`, `F1 = 0.7009`).
  - **Why Main Approach:** Kept as main alerting approach because one model does both jobs (hourly forecasting and high-demand-per-trip alerting), not because it outperforms the dedicated classifier.
- **Known Limits:**
  1. Cut-offs (0.96x for Forecast ÷ Trips and 0.63 for HistGradientBoostingClassifier) were chosen on models trained on January to May 2026, before retraining on January to July 2026.
  2. January to May training contains no public holiday operating a normal timetable (Juneteenth on 19 June 2026 had is_public_holiday=True with holiday_schedule=False, appearing only once in validation / Jan–Jul retraining).
  3. Only the 6-hour M35 surge on Saturday 19 September 2026 (14:00–19:00) was flagged as an outlier (is_outlier == True); other single-day surges or drops remain unflagged.
  4. Boardings do not measure how full a bus is (riders_per_trip divides hourly boardings by trips_running without alightings, through-passengers, or vehicle capacity).

## 2. Dedicated High-Demand Classifier Comparison (`models/final_classifier.joblib`)
- **Model:** `HistGradientBoostingClassifier (Final Retrained High-Demand-per-Trip Classifier)`
- **Official Test Run Date:** `2026-11-13`
- **Training Window:** `2026-01-04 to 2026-07-31 (Train + Validation active-service hours)` (`177,654` active route-hours across `41` routes)
- **Input Features (22 columns -> 77 transformed):** `route, day_of_week, time_band, trips_running, trips_starting, service_hours, route_length_km, stop_count, hour_sin, hour_cos, is_weekend, is_public_holiday, holiday_schedule, is_storm, is_sbs, is_24h, lag_7d, lag_14d, lag_21d, lag_28d, lag_mean_available, lags_available_count`
- **Chosen Settings & Fixed Cutoff:** `{'learning_rate': 0.08, 'max_leaf_nodes': 127, 'min_samples_leaf': 30, 'l2_regularization': 5.0, 'class_weight': 'balanced', 'max_iter': 300, 'early_stopping': True, 'validation_fraction': 0.1, 'n_iter_no_change': 15, 'random_state': 42}`, `cutoff = 0.63` (`n_iter_ = 221`)
- **Label Definition:** `Per-route × day_type 75th percentile thresholds (threshold_p75) kept fixed from Jan–May 2026`
- **Validation Scores (Jun–Jul 2026, 53,406 common active rows):**
  - `PR-AUC = 0.7290`, `Precision @ 13,081 hrs = 0.6610`, `Fixed 0.63 Cutoff F1 = 0.6862` (`P = 0.5854`, `R = 0.8290`)
- **Test Scores (Aug–Sep 2026, 0 storm days — evaluated once on 2026-11-13):**
  - **With M35 Surge (`53,316` common active rows):** `PR-AUC = 0.7495` (`0.750`, leading `Forecast ÷ Trips`'s `0.717`), `Precision @ Rule B Workload (11,654 hrs) = 0.7128` (`0.713`, effectively tied with `Forecast ÷ Trips`'s `0.717`), `Fixed 0.63 Cutoff F1 = 0.7021` (`P = 0.6296`, `R = 0.7934`, `16,954` flagged hrs).
  - **Without M35 Surge (`53,310` common active rows):** Removing those 6 hours changes results by `0.01` points or less (`PR-AUC = 0.7494`, `Precision @ 11,648 hrs = 0.7127`, `F1 = 0.7020`).
- **Known Limits:**
  1. Cut-offs (0.96x for Forecast ÷ Trips and 0.63 for HistGradientBoostingClassifier) were chosen on models trained on January to May 2026, before retraining on January to July 2026.
  2. January to May training contains no public holiday operating a normal timetable (Juneteenth on 19 June 2026 had is_public_holiday=True with holiday_schedule=False, appearing only once in validation / Jan–Jul retraining).
  3. Only the 6-hour M35 surge on Saturday 19 September 2026 (14:00–19:00) was flagged as an outlier (is_outlier == True); other single-day surges or drops remain unflagged.
  4. Boardings do not measure how full a bus is (riders_per_trip divides hourly boardings by trips_running without alightings, through-passengers, or vehicle capacity).
