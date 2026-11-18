# Stage 4b quality report: neural network models (an additional modelling experiment)

Generated 2026-11-18T16:14:28+00:00 by `analytics/models/train_stage4b.py`. An additional modelling experiment on top of the mentor's reference work (Stage 4a): four small neural networks (MLP, LSTM, GRU, 1D CNN) that read the route's last 28 days, compared with the two baselines and the four Stage 4a models on identical rows.

- Data version: `cta_ref__r20261113__gtfs8__to20260731/features__delay1d`; feature rows sha256 `2c3e0eeeccf947d5`; raw ridership `CTA_-_Ridership_-_Bus_Routes_-_Daily_Totals_by_Route_20261113` (sha256 `d9675570e50a1b3d`)
- Code version: git `8bb77e9+uncommitted`; artifact version `stage4b-1.0.0`; Stage 4a artifacts `stage4a-1.0.0` (frozen files checked by sha256, nothing refitted)
- Settings fixed in `analytics/config/neural.json` before any network was trained: seed 42, Adam lr 0.001, batch 128, MSE on the scaled target, at most 200 epochs, early-stopping patience 20, CPU, deterministic algorithms, one thread
- Scoring: the unchanged Stage 4a module (`analytics/models/scoring.py`)

## Summary

- Lowest validation MAE of all ten methods: **`rf_demand`** (345.47).
- Best network on validation: **`gru`** (364.86).
- Serving: the Stage 4a serving bundle (`rf_demand`) is **unchanged**. No network beat it on validation.

Each network against the Random Forest and the best baseline (a loss is stated, not hidden):

- validation: `gru` **loses to** the Random Forest `rf_demand` on MAE (364.86 vs 345.47; WAPE 6.75% vs 6.40%).
- validation: `gru` **loses to** the best baseline `seasonal_mean` on MAE (364.86 vs 360.36; WAPE 6.75% vs 6.67%).
- validation: `lstm` **loses to** the Random Forest `rf_demand` on MAE (385.66 vs 345.47; WAPE 7.14% vs 6.40%).
- validation: `lstm` **loses to** the best baseline `seasonal_mean` on MAE (385.66 vs 360.36; WAPE 7.14% vs 6.67%).
- validation: `mlp` **loses to** the Random Forest `rf_demand` on MAE (416.82 vs 345.47; WAPE 7.72% vs 6.40%).
- validation: `mlp` **loses to** the best baseline `seasonal_mean` on MAE (416.82 vs 360.36; WAPE 7.72% vs 6.67%).
- validation: `cnn` **loses to** the Random Forest `rf_demand` on MAE (559.85 vs 345.47; WAPE 10.36% vs 6.40%).
- validation: `cnn` **loses to** the best baseline `seasonal_mean` on MAE (559.85 vs 360.36; WAPE 10.36% vs 6.67%).
- test (reused holdout): `gru` **loses to** the Random Forest `rf_demand` on MAE (461.98 vs 398.01; WAPE 8.90% vs 7.67%).
- test (reused holdout): `gru` **loses to** the best baseline `seasonal_mean` on MAE (461.98 vs 421.15; WAPE 8.90% vs 8.12%).
- test (reused holdout): `mlp` **loses to** the Random Forest `rf_demand` on MAE (467.36 vs 398.01; WAPE 9.01% vs 7.67%).
- test (reused holdout): `mlp` **loses to** the best baseline `seasonal_mean` on MAE (467.36 vs 421.15; WAPE 9.01% vs 8.12%).
- test (reused holdout): `lstm` **loses to** the Random Forest `rf_demand` on MAE (484.97 vs 398.01; WAPE 9.35% vs 7.67%).
- test (reused holdout): `lstm` **loses to** the best baseline `seasonal_mean` on MAE (484.97 vs 421.15; WAPE 9.35% vs 8.12%).
- test (reused holdout): `cnn` **loses to** the Random Forest `rf_demand` on MAE (557.57 vs 398.01; WAPE 10.74% vs 7.67%).
- test (reused holdout): `cnn` **loses to** the best baseline `seasonal_mean` on MAE (557.57 vs 421.15; WAPE 10.74% vs 8.12%).

## 1. Rows: identical to Stage 4a, with the training period split in time

| part | dates | eligible rows |
|---|---|---|
| fit (networks, encoder, scalers) | 2025-11-24..2026-03-09 | 10,988 |
| early stopping | 2026-03-10..2026-03-31 | 2,391 |
| validation (selection only) | 2026-04-01..2026-05-31 | 6,560 |
| test (reused holdout, scored once) | 2026-06-01..2026-07-31 | 6,542 |

- **The networks learn from fewer rows than the Stage 4a models:** 10,988 instead of 13,379 (82.1%). The last three weeks of training are held back to decide when to stop. This is an honest trade for a fair comparison: validation is never used for training or stopping and serves only for selection, exactly as for the Random Forest.
- The route encoder, calendar scaler and boardings scaler are fitted on the fit part only (10,988 rows, 123 routes; boardings mean 4699.1, std 4279.8).
- Eligibility and splits are read from `feature_rows.csv` unchanged; all ten methods are scored on the same rows, which Stage 4a's `score_methods` checks.

28-day windows (exact calendar dates D-28..D-1). Guard: the window's D-1/7/14/21/28 positions equal the Stage 3 lag columns: `boardings_1d_ago` equal, `boardings_7d_ago` equal, `boardings_14d_ago` equal, `boardings_21d_ago` equal, `boardings_28d_ago` equal.

Missing days inside eligible windows (value = scaled placeholder, `observed` = 0; never 0 boardings):

| split | eligible rows | window days | missing days | missing share % | rows with any missing day |
|---|---|---|---|---|---|
| train | 13,379 | 374,612 | 18,239 | 4.870 | 2,371 |
| validation | 6,560 | 183,680 | 9,500 | 5.170 | 1,314 |
| test | 6,542 | 183,176 | 10,044 | 5.480 | 1,267 |

## 2. Networks

All four use one recipe: same seed (reset before each), optimiser, batch size, loss, epoch limit and patience. The best early-stopping epoch's weights are restored.

| network | parameters | epochs run | best epoch | best early-stopping loss (scaled MSE) | training seconds |
|---|---|---|---|---|---|
| mlp | 13,889 | 47 | 27 | 0.024 | 5.500 |
| lstm | 9,761 | 66 | 46 | 0.025 | 30.300 |
| gru | 8,609 | 66 | 46 | 0.025 | 42.600 |
| cnn | 6,689 | 32 | 12 | 0.031 | 6.300 |

## 3. Validation: all ten methods on the identical rows (selection)

| method | kind | target_rows | scored_rows | withheld_rows | coverage | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|---|---|---|
| rf_demand | rf | 6,864 | 6,560 | 304 | 95.6% | 345.473 | 582.069 | 6.396 |
| rf_service | rf | 6,864 | 6,560 | 304 | 95.6% | 354.084 | 593.616 | 6.555 |
| seasonal_mean | baseline | 6,864 | 6,560 | 304 | 95.6% | 360.359 | 605.828 | 6.671 |
| gru | neural | 6,864 | 6,560 | 304 | 95.6% | 364.862 | 630.298 | 6.755 |
| last_week | baseline | 6,864 | 6,560 | 304 | 95.6% | 375.182 | 632.038 | 6.946 |
| lstm | neural | 6,864 | 6,560 | 304 | 95.6% | 385.656 | 649.913 | 7.140 |
| ridge_demand | ridge | 6,864 | 6,560 | 304 | 95.6% | 400.560 | 599.791 | 7.416 |
| mlp | neural | 6,864 | 6,560 | 304 | 95.6% | 416.824 | 616.865 | 7.717 |
| ridge_service | ridge | 6,864 | 6,560 | 304 | 95.6% | 437.136 | 645.998 | 8.093 |
| cnn | neural | 6,864 | 6,560 | 304 | 95.6% | 559.851 | 847.327 | 10.364 |

- The Stage 4a methods reproduce their stored validation predictions exactly: `last_week` True, `seasonal_mean` True, `ridge_demand` True, `rf_demand` True, `ridge_service` True, `rf_service` True.
- Selection rule: lowest validation MAE. Lowest overall: `rf_demand`; best network: `gru`.

## 4. Test period (reused holdout, scored once)

**Reused holdout.** June-July 2026 was already examined while the method was developed (mentor notebook), so these are reused-holdout results, not an untouched test. The serving method and every setting were fixed on validation before this scoring ran; nothing was tuned on these numbers.

| method | kind | target_rows | scored_rows | withheld_rows | coverage | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|---|---|---|
| rf_demand | rf | 7,018 | 6,542 | 476 | 93.2% | 398.012 | 659.402 | 7.670 |
| rf_service | rf | 7,018 | 6,542 | 476 | 93.2% | 407.619 | 681.622 | 7.855 |
| seasonal_mean | baseline | 7,018 | 6,542 | 476 | 93.2% | 421.155 | 718.515 | 8.115 |
| ridge_demand | ridge | 7,018 | 6,542 | 476 | 93.2% | 450.558 | 694.665 | 8.682 |
| gru | neural | 7,018 | 6,542 | 476 | 93.2% | 461.980 | 746.641 | 8.902 |
| ridge_service | ridge | 7,018 | 6,542 | 476 | 93.2% | 466.629 | 692.094 | 8.992 |
| mlp | neural | 7,018 | 6,542 | 476 | 93.2% | 467.360 | 711.748 | 9.006 |
| lstm | neural | 7,018 | 6,542 | 476 | 93.2% | 484.971 | 776.672 | 9.345 |
| last_week | baseline | 7,018 | 6,542 | 476 | 93.2% | 517.100 | 877.193 | 9.964 |
| cnn | neural | 7,018 | 6,542 | 476 | 93.2% | 557.573 | 882.719 | 10.744 |

### By reported day type

| daytype | method | scored_rows | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|
| (no record) | rf_demand | 0 | unavailable | unavailable | unavailable |
| (no record) | last_week | 0 | unavailable | unavailable | unavailable |
| (no record) | seasonal_mean | 0 | unavailable | unavailable | unavailable |
| (no record) | ridge_demand | 0 | unavailable | unavailable | unavailable |
| (no record) | ridge_service | 0 | unavailable | unavailable | unavailable |
| (no record) | rf_service | 0 | unavailable | unavailable | unavailable |
| (no record) | mlp | 0 | unavailable | unavailable | unavailable |
| (no record) | lstm | 0 | unavailable | unavailable | unavailable |
| (no record) | gru | 0 | unavailable | unavailable | unavailable |
| (no record) | cnn | 0 | unavailable | unavailable | unavailable |
| A | rf_demand | 731 | 455.379 | 768.700 | 8.671 |
| A | last_week | 731 | 661.412 | 1,105.106 | 12.595 |
| A | seasonal_mean | 731 | 515.082 | 921.945 | 9.808 |
| A | ridge_demand | 731 | 476.707 | 803.456 | 9.077 |
| A | ridge_service | 731 | 572.770 | 900.075 | 10.907 |
| A | rf_service | 731 | 510.611 | 919.498 | 9.723 |
| A | mlp | 731 | 636.880 | 995.922 | 12.127 |
| A | lstm | 731 | 900.275 | 1,339.507 | 17.143 |
| A | gru | 731 | 870.134 | 1,296.790 | 16.569 |
| A | cnn | 731 | 1,041.293 | 1,526.042 | 19.828 |
| U | rf_demand | 782 | 519.637 | 881.742 | 11.748 |
| U | last_week | 782 | 645.527 | 1,019.856 | 14.594 |
| U | seasonal_mean | 782 | 549.859 | 931.020 | 12.431 |
| U | ridge_demand | 782 | 665.369 | 876.416 | 15.042 |
| U | ridge_service | 782 | 655.131 | 810.340 | 14.811 |
| U | rf_service | 782 | 501.828 | 824.527 | 11.345 |
| U | mlp | 782 | 474.413 | 760.972 | 10.725 |
| U | lstm | 782 | 653.666 | 1,008.069 | 14.778 |
| U | gru | 782 | 594.515 | 968.786 | 13.440 |
| U | cnn | 782 | 856.642 | 1,305.255 | 19.366 |
| W | rf_demand | 5,029 | 370.760 | 599.032 | 6.996 |
| W | last_week | 5,029 | 476.153 | 813.457 | 8.985 |
| W | seasonal_mean | 5,029 | 387.488 | 642.844 | 7.312 |
| W | ridge_demand | 5,029 | 413.355 | 643.791 | 7.800 |
| W | ridge_service | 5,029 | 421.889 | 635.008 | 7.961 |
| W | rf_service | 5,029 | 377.999 | 613.007 | 7.133 |
| W | mlp | 5,029 | 441.622 | 651.748 | 8.333 |
| W | lstm | 5,029 | 398.372 | 604.874 | 7.517 |
| W | gru | 5,029 | 382.044 | 578.626 | 7.209 |
| W | cnn | 5,029 | 440.756 | 640.460 | 8.317 |

### Routes seen vs unseen in training

| route_group | method | scored_rows | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|
| route seen in training | rf_demand | 6,443 | 400.627 | 663.110 | 7.625 |
| route seen in training | last_week | 6,443 | 521.406 | 882.984 | 9.924 |
| route seen in training | seasonal_mean | 6,443 | 422.827 | 722.133 | 8.048 |
| route seen in training | ridge_demand | 6,443 | 451.892 | 697.226 | 8.601 |
| route seen in training | ridge_service | 6,443 | 467.027 | 693.772 | 8.889 |
| route seen in training | rf_service | 6,443 | 410.270 | 685.500 | 7.809 |
| route seen in training | mlp | 6,443 | 469.541 | 715.354 | 8.937 |
| route seen in training | lstm | 6,443 | 475.263 | 767.292 | 9.046 |
| route seen in training | gru | 6,443 | 461.660 | 749.226 | 8.787 |
| route seen in training | cnn | 6,443 | 557.513 | 886.027 | 10.612 |
| route unseen in training | rf_demand | 99 | 227.772 | 340.026 | 22.637 |
| route unseen in training | last_week | 99 | 236.879 | 325.714 | 23.542 |
| route unseen in training | seasonal_mean | 99 | 312.283 | 420.829 | 31.036 |
| route unseen in training | ridge_demand | 99 | 363.734 | 500.540 | 36.150 |
| route unseen in training | ridge_service | 99 | 440.781 | 572.397 | 43.807 |
| route unseen in training | rf_service | 99 | 235.109 | 345.723 | 23.366 |
| route unseen in training | mlp | 99 | 325.430 | 414.420 | 32.343 |
| route unseen in training | lstm | 99 | 1,116.786 | 1,243.255 | 110.991 |
| route unseen in training | gru | 99 | 482.801 | 553.016 | 47.983 |
| route unseen in training | cnn | 99 | 561.475 | 631.242 | 55.802 |

Unseen routes in the test period: 10, 130.

### Routes 10 and 130, separately

Route 10:

| method | target_rows | scored_rows | withheld_rows | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|---|
| last_week | 55 | 50 | 5 | 250.540 | 340.994 | 25.845 |
| seasonal_mean | 55 | 50 | 5 | 334.575 | 461.000 | 34.514 |
| ridge_demand | 55 | 50 | 5 | 384.132 | 533.372 | 39.627 |
| rf_demand | 55 | 50 | 5 | 258.144 | 379.228 | 26.630 |
| ridge_service | 55 | 50 | 5 | 476.417 | 624.639 | 49.147 |
| rf_service | 55 | 50 | 5 | 269.100 | 386.549 | 27.760 |
| mlp | 55 | 50 | 5 | 359.965 | 457.731 | 37.134 |
| lstm | 55 | 50 | 5 | 1,149.131 | 1,291.424 | 118.543 |
| gru | 55 | 50 | 5 | 531.047 | 599.797 | 54.782 |
| cnn | 55 | 50 | 5 | 627.959 | 699.335 | 64.779 |

Route 130:

| method | target_rows | scored_rows | withheld_rows | MAE | RMSE | WAPE_percent |
|---|---|---|---|---|---|---|
| last_week | 55 | 49 | 6 | 222.939 | 309.345 | 21.359 |
| seasonal_mean | 55 | 49 | 6 | 289.536 | 375.433 | 27.740 |
| ridge_demand | 55 | 49 | 6 | 342.920 | 464.653 | 32.854 |
| rf_demand | 55 | 49 | 6 | 196.779 | 294.698 | 18.853 |
| ridge_service | 55 | 49 | 6 | 404.417 | 513.641 | 38.746 |
| rf_service | 55 | 49 | 6 | 200.425 | 298.360 | 19.202 |
| mlp | 55 | 49 | 6 | 290.189 | 364.965 | 27.802 |
| lstm | 55 | 49 | 6 | 1,083.782 | 1,192.098 | 103.835 |
| gru | 55 | 49 | 6 | 433.570 | 500.794 | 41.539 |
| cnn | 55 | 49 | 6 | 493.635 | 553.186 | 47.294 |

## 5. Saved files

Each file holds the weights as numpy arrays, the fitted preprocessor and the architecture settings (joblib, compress=3). They were frozen before the test period was scored.

| file | uncompressed bytes | saved bytes | compress | under 20 MB | reload reproduces validation exactly | sha256 |
|---|---|---|---|---|---|---|
| models/mlp.joblib | 58,893 | 53,697 | 3 | True | True | 6fb9bac2eaf7ae7c |
| models/lstm.joblib | 42,525 | 38,478 | 3 | True | True | 7095bfe6879ef7d3 |
| models/gru.joblib | 37,917 | 34,130 | 3 | True | True | 63a0c0300fead4a0 |
| models/cnn.joblib | 30,269 | 27,037 | 3 | True | True | 6baccfb983df06a5 |

## 6. Why the networks win or lose

Every network loses to `rf_demand` on validation and to the best baseline as well.

Likely reasons (not proven; each would need its own experiment):

- **Little data for a network.** The networks learn from 10,988 rows, fewer than the Random Forest's 13,379, because three weeks are held back for early stopping. That is only about 89 days per route for 123 routes.
- **Very different route sizes.** In the fit part, route averages range from 133 boardings a day (route 169) to 15,267 (route 9), median 2,740. One shared scale makes small routes' errors tiny in the loss, so the network attends mostly to the big routes.
- **The Random Forest's inputs are already the useful summaries.** Same-weekday lags and the seasonal mean carry most of the signal; a tree splits on them directly, while a network must learn them from 28 raw days.
- **Loss vs metric.** The networks minimise squared error (MSE) but are ranked by MAE.
- **Settings fixed in advance.** Architectures and learning settings were chosen once, before any result, and not tuned. That is deliberate (so validation stays a fair selection set), but it means these are untuned networks.

Observed in the test period (reused holdout; reported, not used for any choice):

- **Unseen routes are the networks' weakest case.** On routes never seen in training (10, 130; 99 rows) the WAPE is `mlp` 32.3%, `lstm` 111.0%, `gru` 48.0%, `cnn` 55.8%, against `rf_demand` 22.6% (route 10: `lstm` 118.5% vs `rf_demand` 26.6%; route 130: `lstm` 103.8% vs `rf_demand` 18.9%). An unseen route gets an all-zero route code; the networks appear to rely on that code more than on the route's own 28 days, while the Random Forest leans on the lags.
- **Best network by day type (WAPE):** W: `gru` 7.21% vs `rf_demand` 7.00%; A: `gru` 16.57% vs `rf_demand` 8.67%; U: `gru` 13.44% vs `rf_demand` 11.75%. A likely contributor on weekends: `month` in June-July lies outside the November-March range the networks learned from; a network extrapolates, a tree caps.
- **One slice where a network is lowest:** on day type U, `mlp` has the lowest WAPE of all ten methods (10.73%). One test slice; it changes nothing.

## 7. Reproducibility

- Fixed seed reset before each network; seeded shuffling; `torch.use_deterministic_algorithms(True)`; one intra-op and one inter-op thread (the equivalent of Stage 4a's `n_jobs=1`); CPU; float32.
- Predictions run one row at a time, so a row's forecast does not depend on which other rows are predicted with it (float32 results otherwise depend on the batch size).
- Validation predictions sha256 `0a245ee5e7643aa0`; training history sha256 `3b4c28eed53c3aff`. A rerun must give the same values.
- Runtime: python 3.12.10, torch 2.15.0, pandas 3.1.1, numpy 2.5.4, scikit-learn 1.9.1, joblib 1.6.0
