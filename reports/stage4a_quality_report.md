# Stage 4a quality report: baselines, Ridge and Random Forest

Generated 2026-11-18T14:43:21+00:00 by `analytics/models/train_stage4a.py`. Conventions follow the mentor's reference notebook where it differs from spec v3.8. No neural networks in this stage.

- Data version: `cta_ref__r20261113__gtfs8__to20260731/features__delay1d`; feature rows sha256 `2c3e0eeeccf947d5`
- Code version: git `3a89127+uncommitted`; artifact version `stage4a-1.0.0`
- Periods: train 2025-11-24..2026-03-31, validation 2026-04-01..2026-05-31, test 2026-06-01..2026-07-31 (reused holdout: June-July 2026 was examined while the method was developed (notebook); not an untouched final test)
- Settings (fixed in `analytics/config/models.json` before the run): Ridge alpha 100; Random Forest 100 trees, max_depth 16, min_samples_leaf 10, seed 42; route one-hot (unknown routes ignored); numeric inputs standardized on training rows only; predictions floored at 0
- Row counts vs the notebook: **6 MATCH, 0 MISMATCH**

## Selected serving method: `rf_demand` (rf)

`rf_demand` has the lowest validation MAE (345.47) of the six methods; the best baseline is `seasonal_mean` (360.36).

Model vs best baseline (honest comparison; a loss is reported, not hidden):

- validation: `rf_demand` beats the best baseline `seasonal_mean` on MAE (345.47 vs 360.36; WAPE 6.40% vs 6.67%).
- validation: `rf_service` beats the best baseline `seasonal_mean` on MAE (354.08 vs 360.36; WAPE 6.56% vs 6.67%).
- validation: `ridge_demand` **loses to** the best baseline `seasonal_mean` on MAE (400.56 vs 360.36; WAPE 7.42% vs 6.67%).
- validation: `ridge_service` **loses to** the best baseline `seasonal_mean` on MAE (437.14 vs 360.36; WAPE 8.09% vs 6.67%).
- test (reused holdout): `ridge_demand` **loses to** the best baseline `seasonal_mean` on MAE (450.56 vs 421.15; WAPE 8.68% vs 8.12%).
- test (reused holdout): `rf_demand` beats the best baseline `seasonal_mean` on MAE (398.01 vs 421.15; WAPE 7.67% vs 8.12%).
- test (reused holdout): `ridge_service` **loses to** the best baseline `seasonal_mean` on MAE (466.63 vs 421.15; WAPE 8.99% vs 8.12%).
- test (reused holdout): `rf_service` beats the best baseline `seasonal_mean` on MAE (407.62 vs 421.15; WAPE 7.85% vs 8.12%).

## 1. Row counts vs the notebook

| check | notebook | ours | result | difference |
|---|---:|---:|---|---:|
| train target rows | 14,430 | 14,430 | **MATCH** | +0 |
| train eligible rows | 13,379 | 13,379 | **MATCH** | +0 |
| validation target rows | 6,864 | 6,864 | **MATCH** | +0 |
| validation eligible rows | 6,560 | 6,560 | **MATCH** | +0 |
| test target rows | 7,018 | 7,018 | **MATCH** | +0 |
| test eligible rows | 6,542 | 6,542 | **MATCH** | +0 |

Why our earlier Stage 3 matched counts (spec 9.10.3: 14,501 / 6,859 / 7,014) differ from these: the notebook's target rows are the route/days in the **forecast-time** schedule. The 86 matched rows on 2025-11-23 have no archive saved before that day, so they cannot be forecast; scheduled days with no recorded boardings are kept as targets and withheld.

| split | spec matched rows | minus: no archive saved before the date | plus: scheduled, no recorded boardings | = target rows (ours) | notebook target | eligible (ours) | notebook eligible | withheld (ours) |
|---|---|---|---|---|---|---|---|---|
| train | 14,501 | -86 | 15 | 14,430 | 14,430 | 13,379 | 13,379 | 1,051 |
| validation | 6,859 | 0 | 5 | 6,864 | 6,864 | 6,560 | 6,560 | 304 |
| test | 7,014 | 0 | 4 | 7,018 | 7,018 | 6,542 | 6,542 | 476 |

- Identity holds in every split: **True**; the rows with recorded boardings are exactly the spec matched rows minus the dropped rows (compared as key sets): **True**.
- Eligibility uses one required-field list for all six methods, so every method is scored on the **same** rows: the common-row population and each method's own population coincide (spec 9.10.3 asks for both).

Withheld reasons:

| split | excluded_reason | rows |
|---|---|---|
| test | boardings_1d_ago | 237 |
| test | boardings_21d_ago | 49 |
| test | boardings_14d_ago | 39 |
| test | boardings_7d_ago | 38 |
| test | boardings_1d_ago, boardings_21d_ago | 37 |
| test | boardings_1d_ago, boardings_14d_ago | 36 |
| test | boardings_1d_ago, boardings_7d_ago | 36 |
| test | boardings_7d_ago, boardings_21d_ago | 2 |
| test | boardings_14d_ago, boardings_21d_ago | 1 |
| test | boardings_7d_ago, boardings_14d_ago | 1 |
| train | boardings_1d_ago | 813 |
| train | boardings_21d_ago | 74 |
| train | boardings_7d_ago | 39 |
| train | boardings_7d_ago, boardings_14d_ago | 39 |
| train | boardings_14d_ago, boardings_21d_ago | 38 |
| train | boardings_14d_ago | 37 |
| train | boardings_7d_ago, boardings_14d_ago, boardings_21d_ago, boardings_28d_filled | 5 |
| train | no recorded boardings | 3 |
| train | boardings_7d_ago, boardings_14d_ago, boardings_21d_ago | 2 |
| train | boardings_7d_ago, boardings_21d_ago | 1 |
| validation | boardings_1d_ago | 293 |
| validation | boardings_14d_ago, boardings_21d_ago | 2 |
| validation | boardings_14d_ago | 1 |
| validation | boardings_1d_ago, boardings_14d_ago | 1 |
| validation | boardings_1d_ago, boardings_7d_ago | 1 |
| validation | boardings_21d_ago | 1 |
| validation | boardings_7d_ago | 1 |
| validation | boardings_7d_ago, boardings_14d_ago | 1 |
| validation | boardings_7d_ago, boardings_14d_ago, boardings_21d_ago, boardings_28d_filled | 1 |
| validation | boardings_7d_ago, boardings_21d_ago | 1 |
| validation | no recorded boardings | 1 |

## 2. Our Stage 3 features vs the notebook's `build_features` (aligned in Step 29)

| # | item | our Stage 3 (before) | notebook (now used) | effect |
|---|---|---|---|---|
| 1 | Target rows | matched rides on the descriptive schedule (28,374) | every route/day in the forecast-time schedule (28,312); rides left-joined | different population (section 1) |
| 2 | Scheduled days without rides | not in the table | kept, withheld as `no recorded boardings` | +24 withheld rows |
| 3 | 2025-11-23 | 86 rows; only the schedule model withheld them | not a target (no archive saved before it) | -86 rows |
| 4 | Sunday-like flag | `is_sunday_holiday_service_day`: Sunday or observed federal holiday (fixed list) | `is_sunday_like_day`: more than half of the date's scheduled bus trips are Sunday-only services | different rule; both known at issue time; both disagree with daytype U on 0 rows (Stage 3 report, section 6) |
| 5 | Required fields | demand: 1/7/14/21-day lags + 28-day donor; schedule model adds valid trips/hours (trips > 0) | one list for every method: 1/7/14/21-day lags, `boardings_28d_filled`, `scheduled_trips`, `scheduled_hours` | demand-only model also needs the schedule, so all methods share identical rows |
| 6 | Withheld-reason format | `missing_rides_7_days_before;...` | comma-joined field names, or `no recorded boardings` | format only |
| 7 | 28-day lag | overwritten with the filled value | raw `boardings_28d_ago` kept; fill in `boardings_28d_filled` | raw value stays auditable |
| 8 | Names | `rides_<k>_days_before`, `available_same_weekday_observations`, `past_four_same_weekdays_mean`, `rides_28_days_before_available`, `scheduled_service_hours` | `boardings_<k>d_ago`, `seasonal_count`, `seasonal_mean`, `boardings_28d_available`, `scheduled_hours` | rename only |
| 9 | Feature order | 28-day flag appended last | notebook order (route, calendar, flag, lags, 28d filled/available, seasonal count/mean, then schedule) | order affects Random Forest tie-breaking |
| 10 | Split edges | train 2025-11-23..2026-03-31, validation Apr-May, test Jun-Jul | train <= 2026-03-31 < validation <= 2026-05-31 < test | identical once the 2025-11-23 row rule applies |
| 11 | Route key | trimmed, case kept | trimmed and upper-cased | 0 effect (no lower-case route ids) |
| 12 | Trip-hours validity | endpoint/sequence rules; hours rounded to 1e-6 | also rejects times going backwards and departure < arrival; unrounded | 0 trips affected in these feeds (eligible counts match exactly); rounding difference below 1e-6 hours |
| 13 | Rides dtype | nullable integer | float | none |

## 3. Validation (identical eligible rows; selection uses MAE)

| method | kind | target_rows | scored_rows | withheld_rows | coverage | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|---|---|---|
| rf_demand | rf | 6,864 | 6,560 | 304 | 95.6% | 345.473 | 582.069 | 6.396 |
| rf_service | rf | 6,864 | 6,560 | 304 | 95.6% | 354.084 | 593.616 | 6.555 |
| seasonal_mean | baseline | 6,864 | 6,560 | 304 | 95.6% | 360.359 | 605.828 | 6.671 |
| last_week | baseline | 6,864 | 6,560 | 304 | 95.6% | 375.182 | 632.038 | 6.946 |
| ridge_demand | ridge | 6,864 | 6,560 | 304 | 95.6% | 400.560 | 599.791 | 7.416 |
| ridge_service | ridge | 6,864 | 6,560 | 304 | 95.6% | 437.136 | 645.998 | 8.093 |

Training: 13,379 eligible rows, 123 routes.

## 4. Saved artifacts (frozen before the test scoring)

Every `.joblib` file is saved with `joblib.dump(..., compress=3)`; compression changes the file encoding, not the model. The 20 MB limit (20,000,000 bytes) is checked on the saved file. The uncompressed size is a dump of the same object into memory.

| file | uncompressed bytes | saved bytes (compress=3) | saved MB | under 20 MB | sha256 of saved file (first 16) |
|---|---|---|---|---|---|
| models/ridge_demand.joblib | 5,377 | 3,234 | 0.003 | True | 2b79935078235d68 |
| models/rf_demand.joblib | 9,558,154 | 3,175,906 | 3.176 | True | 7ca6be08810472a2 |
| models/ridge_service.joblib | 5,553 | 3,315 | 0.003 | True | 2eba581a75390da1 |
| models/rf_service.joblib | 9,537,146 | 3,182,790 | 3.183 | True | 39fd6ec8f26a18cb |
| models/serving_bundle.joblib | 1,056 | 657 | 0.001 | True | 90c795ccb861d0ba |

Reloaded compressed pipelines reproduce the in-memory validation predictions exactly: `ridge_demand` True, `rf_demand` True, `ridge_service` True, `rf_service` True.

`feature_contract.json` sha256 `f010f5dd0e479fca`; frozen at 2026-11-18T14:43:19+00:00.

## 5. Test period (scored once)

**Reused holdout.** June-July 2026 was already examined while the method was developed (mentor notebook), so these are reused-holdout results, not an untouched test. The serving method and every setting were fixed on validation before this scoring ran; nothing was tuned on these numbers.

Scored at 2026-11-18T14:43:19+00:00, after freezing at 2026-11-18T14:43:19+00:00.

| method | kind | target_rows | scored_rows | withheld_rows | coverage | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|---|---|---|
| last_week | baseline | 7,018 | 6,542 | 476 | 93.2% | 517.100 | 877.193 | 9.964 |
| seasonal_mean | baseline | 7,018 | 6,542 | 476 | 93.2% | 421.155 | 718.515 | 8.115 |
| ridge_demand | ridge | 7,018 | 6,542 | 476 | 93.2% | 450.558 | 694.665 | 8.682 |
| rf_demand | rf | 7,018 | 6,542 | 476 | 93.2% | 398.012 | 659.402 | 7.670 |
| ridge_service | ridge | 7,018 | 6,542 | 476 | 93.2% | 466.629 | 692.094 | 8.992 |
| rf_service | rf | 7,018 | 6,542 | 476 | 93.2% | 407.619 | 681.622 | 7.855 |

### By reported day type (the daytype is used for reporting only, never as an input)

| daytype | method | target_rows | scored_rows | withheld_rows | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|---|---|
| (no record) | rf_demand | 4 | 0 | 4 | unavailable | unavailable | unavailable |
| (no record) | last_week | 4 | 0 | 4 | unavailable | unavailable | unavailable |
| (no record) | seasonal_mean | 4 | 0 | 4 | unavailable | unavailable | unavailable |
| (no record) | ridge_demand | 4 | 0 | 4 | unavailable | unavailable | unavailable |
| (no record) | ridge_service | 4 | 0 | 4 | unavailable | unavailable | unavailable |
| (no record) | rf_service | 4 | 0 | 4 | unavailable | unavailable | unavailable |
| A | rf_demand | 740 | 731 | 9 | 455.379 | 768.700 | 8.671 |
| A | last_week | 740 | 731 | 9 | 661.412 | 1,105.106 | 12.595 |
| A | seasonal_mean | 740 | 731 | 9 | 515.082 | 921.945 | 9.808 |
| A | ridge_demand | 740 | 731 | 9 | 476.707 | 803.456 | 9.077 |
| A | ridge_service | 740 | 731 | 9 | 572.770 | 900.075 | 10.907 |
| A | rf_service | 740 | 731 | 9 | 510.611 | 919.498 | 9.723 |
| U | rf_demand | 784 | 782 | 2 | 519.637 | 881.742 | 11.748 |
| U | last_week | 784 | 782 | 2 | 645.527 | 1,019.856 | 14.594 |
| U | seasonal_mean | 784 | 782 | 2 | 549.859 | 931.020 | 12.431 |
| U | ridge_demand | 784 | 782 | 2 | 665.369 | 876.416 | 15.042 |
| U | ridge_service | 784 | 782 | 2 | 655.131 | 810.340 | 14.811 |
| U | rf_service | 784 | 782 | 2 | 501.828 | 824.527 | 11.345 |
| W | rf_demand | 5,490 | 5,029 | 461 | 370.760 | 599.032 | 6.996 |
| W | last_week | 5,490 | 5,029 | 461 | 476.153 | 813.457 | 8.985 |
| W | seasonal_mean | 5,490 | 5,029 | 461 | 387.488 | 642.844 | 7.312 |
| W | ridge_demand | 5,490 | 5,029 | 461 | 413.355 | 643.791 | 7.800 |
| W | ridge_service | 5,490 | 5,029 | 461 | 421.889 | 635.008 | 7.961 |
| W | rf_service | 5,490 | 5,029 | 461 | 377.999 | 613.007 | 7.133 |

### Routes 10 and 130 (unseen in training; few rows, so percentages are noisy)

Zero scored rows would mean unavailable metrics, not zero error.

| route | method | target_rows | scored_rows | withheld_rows | withheld_by_reason | MAE | WAPE_percent |
|---|---|---|---|---|---|---|---|
| 10 | last_week | 55 | 50 | 5 | boardings_21d_ago: 5 | 250.540 | 25.845 |
| 10 | seasonal_mean | 55 | 50 | 5 | boardings_21d_ago: 5 | 334.575 | 34.514 |
| 10 | ridge_demand | 55 | 50 | 5 | boardings_21d_ago: 5 | 384.132 | 39.627 |
| 10 | rf_demand | 55 | 50 | 5 | boardings_21d_ago: 5 | 258.144 | 26.630 |
| 10 | ridge_service | 55 | 50 | 5 | boardings_21d_ago: 5 | 476.417 | 49.147 |
| 10 | rf_service | 55 | 50 | 5 | boardings_21d_ago: 5 | 269.100 | 27.760 |
| 130 | last_week | 55 | 49 | 6 | boardings_21d_ago: 6 | 222.939 | 21.359 |
| 130 | seasonal_mean | 55 | 49 | 6 | boardings_21d_ago: 6 | 289.536 | 27.740 |
| 130 | ridge_demand | 55 | 49 | 6 | boardings_21d_ago: 6 | 342.920 | 32.854 |
| 130 | rf_demand | 55 | 49 | 6 | boardings_21d_ago: 6 | 196.779 | 18.853 |
| 130 | ridge_service | 55 | 49 | 6 | boardings_21d_ago: 6 | 404.417 | 38.746 |
| 130 | rf_service | 55 | 49 | 6 | boardings_21d_ago: 6 | 200.425 | 19.202 |

### Known vs unseen routes (unseen in test: 10, 130)

| route_group | method | target_rows | scored_rows | withheld_rows | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|---|---|
| route seen in training | rf_demand | 6,908 | 6,443 | 465 | 400.627 | 663.110 | 7.625 |
| route seen in training | last_week | 6,908 | 6,443 | 465 | 521.406 | 882.984 | 9.924 |
| route seen in training | seasonal_mean | 6,908 | 6,443 | 465 | 422.827 | 722.133 | 8.048 |
| route seen in training | ridge_demand | 6,908 | 6,443 | 465 | 451.892 | 697.226 | 8.601 |
| route seen in training | ridge_service | 6,908 | 6,443 | 465 | 467.027 | 693.772 | 8.889 |
| route seen in training | rf_service | 6,908 | 6,443 | 465 | 410.270 | 685.500 | 7.809 |
| route unseen in training | rf_demand | 110 | 99 | 11 | 227.772 | 340.026 | 22.637 |
| route unseen in training | last_week | 110 | 99 | 11 | 236.879 | 325.714 | 23.542 |
| route unseen in training | seasonal_mean | 110 | 99 | 11 | 312.283 | 420.829 | 31.036 |
| route unseen in training | ridge_demand | 110 | 99 | 11 | 363.734 | 500.540 | 36.150 |
| route unseen in training | ridge_service | 110 | 99 | 11 | 440.781 | 572.397 | 43.807 |
| route unseen in training | rf_service | 110 | 99 | 11 | 235.109 | 345.723 | 23.366 |

## 6. Notes and limits

- Settings and the selection rule were fixed before any result was read; the test period was scored once, after the artifacts were frozen and hashed.
- The test period is a reused holdout (see section 5); no claim is made from it without that label.
- Library versions differ from the notebook's run (see the model manifest). Baselines and Ridge are deterministic arithmetic; Random Forest tree-building can differ slightly between scikit-learn versions.
- Boardings are daily counts: they say nothing about crowding. Scheduled service is not operated service.
- Per-route results: `reports/stage4a_per_route_evaluation.csv`; withheld rows by route and reason: `reports/stage4a_withheld_by_route.csv`.
