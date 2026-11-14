# Milestone 3: Modeling, Evaluation & Service Optimization Report
**AI-Powered Public Transit Route Optimization — Manhattan Bus Network**  
*Training Window: 4 January – 31 May 2026 | Validation Window: 1 June – 31 July 2026 | Official Test Window: 1 August – 30 September 2026 | Operational Unseen Window: 18–31 October 2026*  
*Official Single Final Test Run Date: **2026-11-13** (`reports/test_runs.log` — 1 run logged)*

---

## 1. Executive Summary & Evaluation Protocol (Step 1)

Milestone 3 builds and evaluates hourly ridership forecasting, high-demand-per-trip alerting, route clustering, and downstream schedule reallocation across the **41 Manhattan bus routes**.

### Chronological Split & Test-Set Safeguards
- **Training (`2026-01-04` to `2026-05-31`):** `125,445` total route-hours (`124,248` active hours with `trips_running >= 1`). Used for model selection and computing fixed `threshold_p75` per-route × day-type thresholds.
- **Validation (`2026-06-01` to `2026-07-31`):** `54,046` total route-hours (`53,585` common non-null-lag rows; `53,406` active hours). **0 storm days** occurred during validation.
- **Official Test (`2026-08-01` to `2026-09-30`):** `53,736` total route-hours (`53,501` common non-null-lag rows; `53,316` active common hours). **0 storm days** occurred during the test window; one 6-hour outlier (`M35`, Saturday 19 September 2026, `14:00–19:00`) is reported both with and without inclusion.
- **Single-Use Test Lock:** [`src/evaluate.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/src/evaluate.py) blocks access to `test_features.parquet` unless `final=True` is explicitly passed and logs every test load to [`reports/test_runs.log`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/test_runs.log). The single official test run was recorded on **`2026-11-13`**:
  `[2026-11-13T11:30:59.750143] AUDIT TEST ACCESS: test_features.parquet loaded with final=True. Caller: src/run_final_test.py::run_step5_final_test (Single Official Test Run)`.
  *(Note: prior to the follow-up test-suite isolation fix, `test_load_dataset_test_isolation_enforcement` in `tests/test_evaluate.py` opened the real `test_features.parquet` to verify the unlock check and restored `reports/test_runs.log` afterwards without scoring or tuning any model; that test now uses a temporary synthetic `.parquet` file and log via `monkeypatch` and `tmp_path`.)*
- **Bias Sign Convention:** All reported biases use **`Predicted - Actual`** (`+` means model overpredicts; `-` means model underpredicts). Groups or time bands with `0` actual riders report `NaN` for WAPE instead of dividing by zero.

---

## 2. Hourly Ridership Forecasting — Validation Results (Step 2)

Four model families were tuned on Jan–May training data and compared on the common `53,585`-row June–July validation set against two historical lag baselines ([`m3_forecast_model_comparison.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_forecast_model_comparison.csv)).

| Model / Baseline | Type | Chosen Setting | MAE (53,585) | RMSE (53,585) | WAPE (53,585) | Bias (Pred − Actual) | WAPE vs 4-Wk Avg (pp) |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| **Same Hour Last Week (`lag_7d`)** | Baseline | Direct `lag_7d` | 44.27 | 81.45 | 17.48% | -0.26 | +3.40 |
| **4-Week Average (`lag_mean_available`)** | Baseline Hurdle | Direct 4-week lag average | 35.66 | 63.24 | 14.08% | +3.11 | 0.00 |
| **Ridge (`riders`)** | Linear ML | `alpha=1000.0`, complete-lag rows | 36.97 | 61.74 | 14.60% | +9.30 | +0.52 |
| **Ridge (`log(1 + riders)`)** | Linear ML | `alpha=0.01`, log1p inputs | 36.24 | 62.84 | 14.31% | +8.74 | +0.23 |
| **Random Forest** | Tree Ensemble | `depth=18, leaf=5, feat=0.8` | 34.06 | 58.48 | 13.45% | +9.27 | -0.63 |
| **HistGradientBoosting** | Boosted Trees | `loss=poisson, lr=0.05, leaf=127, min=25, l2=1.0` | **33.00** | **56.05** | **13.03%** | +8.83 | **-1.05** |

![Validation Forecast Model Comparison](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_forecast_model_comparison.png)

### Key Validation Findings
1. **Selected Model vs Baselines:** **HistGradientBoosting** achieves **`13.03%` WAPE** vs **`14.08%`** for the 4-week average (`-1.05 percentage points`, roughly **`7%` fewer errors** relative to baseline). **Ridge regressions do not beat the 4-week average baseline** (`14.60%` and `14.31%` WAPE) and are kept transparently in the comparison.
2. **Gain Holds Across Weeks and Routes:** Across the 9 June–July validation weeks ([`m3_forecast_weekly_check.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_forecast_weekly_check.csv)), HistGradientBoosting **wins 8 of 9 weeks and ties 1** (Week 7, `13–19 Jul`: `13.39%` vs `13.40%`, diff `-0.01 pp`). Across individual routes ([`m3_forecast_route_gain_check.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_forecast_route_gain_check.csv)), it improves WAPE on **37 of 41 routes** (with minor increases <= `0.40 pp` on `M102` `+0.09`, `M125` `+0.19`, `M98` `+0.23`, and `M104` `+0.40`).
3. **Seasonal Bias Confirmed & Retraining Rule Set:** All four trained models overpredict by **`+8.7` to `+9.3` riders/hour** (about `3.5%` on a ~253 rider/hour mean) against `+3.11` for the 4-week average. As observed in Milestone 2, average boardings in validation fall from **`268.1` riders/hour in Week 1 (`1–7 Jun`) to ~`245` riders/hour by mid-July** (`245.1` in Week 6 and `245.8` in Week 7; trough `228.4` in Week 5 including Independence Day). HistGradientBoosting's bias rises alongside that summer decline (`+1.54` in Week 1 vs `+13.39` and `+9.66` in Weeks 6–7) because it was fitted only on Jan–May spring levels, whereas the 4-week average self-adjusts over a rolling lookback. Accordingly, the final test protocol locked hyperparameters on validation and **retrained all chosen models on Jan–Jul (`2026-01-04` to `2026-07-31`, `179,491` rows)** before scoring Aug–Sep test data.

![Validation Weekly Bias and WAPE Check](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_forecast_weekly_bias_wape.png)

---

## 3. High-Demand-Per-Trip Classification — Validation Results (Step 3)

Active route-hours (`trips_running >= 1`) are labeled positive (`high_demand_per_trip = 1`) when actual `riders_per_trip` exceeds the fixed Jan–May per-route × day-type 75th percentile threshold (`threshold_p75`). Two modeling strategies were compared on `53,406` common validation hours (`12,987` actual positive hours; [`m3_classification_model_comparison.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_classification_model_comparison.csv), [`m3_classification_fair_ranking.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_classification_fair_ranking.csv)).

| PR-AUC Rank | Model / Baseline | PR-AUC | Precision @ Rule B Workload (13,081 hrs) | F1 @ 13,081 hrs | Max-F1 Cutoff Rule | Pred Pos @ Max-F1 | Precision @ Max-F1 | Recall @ Max-F1 | F1 @ Max-F1 |
| :---: | :--- | ---: | ---: | ---: | :--- | ---: | ---: | ---: | ---: |
| **1** | **HistGradientBoosting Classifier** (`lr=0.08, leaf=127, min=30, l2=5.0, cw=balanced`) | **0.7290** | 0.6610 | 0.6634 | `prob >= 0.63` | 18,390 | 0.5854 | 0.8290 | 0.6862 |
| **2** | **Forecast ÷ Trips** (`HistGradientBoostingRegressor` ÷ `trips_running`) | **0.7205** | **0.6801** | **0.6825** | `ratio > 0.96 × p75` | 17,789 | 0.6054 | 0.8292 | **0.6998** |
| **3** | **Random Forest Classifier** (`depth=18, leaf=5, feat=0.8, cw=balanced`) | 0.6992 | 0.6417 | 0.6440 | `prob >= 0.55` | 19,820 | 0.5623 | 0.8582 | 0.6794 |
| **4** | **Baseline Rule B** (4-Wk Avg ÷ Trips > `1.00 × p75`) | 0.6904 | 0.6641 | 0.6665 | `ratio > 1.00 × p75` | 13,081 | 0.6641 | 0.6689 | 0.6665 |
| **5** | **Baseline Rule A** (7-Day Lag ÷ Trips > `1.00 × p75`) | 0.6295 | 0.6235 | 0.6257 | `ratio > 1.00 × p75` | 13,263 | 0.6211 | 0.6342 | 0.6276 |
| **6** | **Logistic Regression** (`C=1.0, cw={1: 1.5}`) | 0.6271 | 0.5944 | 0.5966 | `prob >= 0.48` | 18,769 | 0.5351 | 0.7733 | 0.6325 |

### Why PR-AUC and Equal-Workload Precision Matter Here
- Maximizing F1 alone flags **`17,789` to `19,820` hours** (well above the `12,987` actual positive hours), trading precision down to **`0.56–0.61`**.
- **HistGradientBoosting Classifier** leads in threshold-free **PR-AUC (`0.729` vs `0.721`)**, yet at Baseline Rule B's exact alert volume (`13,081` flagged hours), the dedicated classifier scores **`0.661` precision** — slightly below Rule B's **`0.664`** — whereas **`Forecast ÷ Trips` reaches `0.680` precision** (`+0.016` over Rule B).
- Both **`Forecast ÷ Trips`** (`0.96 × threshold_p75`, main approach) and **`HistGradientBoostingClassifier`** (`cutoff >= 0.63`, comparison benchmark) were advanced to Step 5 test evaluation after Jan–Jul retraining with frozen settings and cutoffs.

---

## 4. Official Final Test Results — August & September 2026 (Step 5)

The single official test evaluation was executed on **`2026-11-13`** after retraining both models on **January–July 2026 (`179,491` total rows / `177,654` active rows)** with frozen settings and cutoffs.

### 4.1 Forecasting Performance on Test (`m3_test_forecast_overall.csv`, `m3_test_forecast_by_week.csv`, `m3_test_forecast_by_route.csv`)

| Evaluation Subset | Model / Baseline | Common Rows (`n`) | MAE | RMSE | WAPE | Bias (Pred − Actual) | WAPE vs 4-Wk Avg (pp) |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **With M35 Surge (All Test Hours)** | 4-Week Average Baseline | 53,501 | 39.21 | 73.02 | 15.41% | -6.36 | 0.00 |
| **With M35 Surge (All Test Hours)** | **HistGradientBoosting (Jan–Jul Retrained)** | 53,501 | **35.77** | **63.94** | **14.06%** | **-1.89** | **-1.35** |
| **Without M35 Surge (Excl. 6 hrs on 19 Sep)** | 4-Week Average Baseline | 53,495 | 39.16 | 72.77 | 15.39% | -6.30 | 0.00 |
| **Without M35 Surge (Excl. 6 hrs on 19 Sep)** | **HistGradientBoosting (Jan–Jul Retrained)** | 53,495 | **35.72** | **63.67** | **14.04%** | **-1.84** | **-1.35** |

![Official Test Forecasting Results](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_test_forecast_results.png)

- **Main Test Takeaway:** On the `53,501` common test hours (`53,736` total including rows with all lags missing), HistGradientBoosting achieves **`14.06%` vs `15.41%` WAPE** — roughly **`9%` fewer errors relative to the 4-week average baseline** (`-1.35 percentage points`).
- **Route & Weekly Consistency:** HistGradientBoosting outperforms the baseline on **all 41 of 41 routes** and in **7 of 9 weeks** (trailing slightly only in Aug Weeks 3–4 by `0.39 pp` and `0.09 pp` before beating the baseline in every September week, where mean ridership jumps to `262.7–294.6` riders/hour in Weeks 6–7 and the 4-week lag average underpredicts by `-20.5` to `-49.7` riders/hour).
- **Seasonal Bias Improvement & Harder Test Period:** Retraining on January–July reduced overall forecast bias from **`+8.8` (`+8.83`) in validation to `-1.9` (`-1.89`) in test**. At the same time, **both the model and the baseline do worse on the August–September test period than on June–July validation (`14.06%` vs `13.03%` for HGB, and `15.41%` vs `14.08%` for the 4-week average)**: August and September are harder to predict than June and July, and the model's advantage over the baseline held up anyway.
- **M35 Surge Sensitivity:** Removing the 6-hour `M35` surge (`19 Sep 14:00–19:00`) changes forecasting error by **`0.02` points** (`14.04%` vs `14.06%` WAPE; baseline `15.39%` vs `15.41%`).

### 4.2 High-Demand-per-Trip Classification on Test (`m3_test_classification_overall.csv`)

Evaluated on **`53,316` common active hours** (`13,455` actual positive hours; `53,319` total active hours):

| Evaluation Subset | Model / Baseline | Fixed Cutoff Rule | PR-AUC | Precision @ Rule B Workload (11,654 hrs) | F1 @ 11,654 hrs | Pred Pos @ Fixed Cutoff | Precision @ Fixed Cutoff | Recall @ Fixed Cutoff | F1 @ Fixed Cutoff |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **With M35 Surge** | Baseline Rule B (4-Wk Avg ÷ Trips) | `ratio > 1.00 × p75` | 0.6869 | 0.6952 | 0.6453 | 11,654 | 0.6952 | 0.6022 | 0.6453 |
| **With M35 Surge** | **`Forecast ÷ Trips` (Main Approach)** | `ratio > 0.96 × p75` | **0.7165** (`0.717`) | **0.7166** (`0.717`) | **0.6652** | 15,555 | 0.6537 | 0.7557 | **0.7010** |
| **With M35 Surge** | **HistGradientBoosting Classifier** | `prob >= 0.63` | **0.7495** (`0.750`) | **0.7128** (`0.713`) | **0.6617** | 16,954 | 0.6296 | 0.7934 | **0.7021** |
| **Without M35 Surge** | Baseline Rule B | `ratio > 1.00 × p75` | 0.6865 | — | — | 11,648 | 0.6951 | 0.6020 | 0.6452 |
| **Without M35 Surge** | `Forecast ÷ Trips` | `ratio > 0.96 × p75` | 0.7161 | — | — | 15,549 | 0.6535 | 0.7556 | 0.7009 |
| **Without M35 Surge** | HistGradientBoosting Classifier | `prob >= 0.63` | 0.7494 | — | — | 16,949 | 0.6295 | 0.7934 | 0.7020 |

![Official Test Classification Results](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_test_classification_results.png)

- **Main Classification Takeaway:** Both ML models clearly beat Baseline Rule B (`0.6869` PR-AUC, `0.6952` Precision @ Rule B workload, `0.6453` F1). Between the two ML models, the comparison is close: **`HistGradientBoostingClassifier` leads in PR-AUC (`0.750` vs `0.717`, wider than validation's `0.729` vs `0.721`)**, while **precision at Rule B's workload (`11,654` flagged hours) is effectively a tie (`Forecast ÷ Trips` `0.717` vs classifier `0.713`)** and fixed-cutoff F1 is also nearly identical (`0.7010` vs `0.7021`). **`Forecast ÷ Trips` is kept as the main operational approach because one model does both jobs** (forecasting hourly boardings and flagging high-demand hours), not because it outperforms the dedicated classifier.
- **M35 Surge Sensitivity:** Excluding the 6-hour `M35` surge changes classification metrics by **`0.01` points or less** (`Forecast ÷ Trips` PR-AUC `0.7161`, F1 `0.7009`; Classifier PR-AUC `0.7494`, F1 `0.7020`).

---

## 5. Manhattan Route Clustering — 40 Routes + M35 Outlier (Step 4)

Clustering uses the 9 non-redundant scaled Jan–May route features established in Milestone 2 (`max |r| = 0.840 < 0.85`). **M35 (`4.95 km`, RFK Bridge to Randall's Island)** is removed prior to clustering and reported separately because it forms a single-route singleton at every $k$ on the 41-route set (inflating $k=2$ silhouette to `0.6179` purely by separating `M35` from the other 40 routes). Wait/standout metrics confirm `M35` is **unlike every other route**: `~146` weekday riders/day, **`1.666` weekend-to-weekday ratio** (only route above `1.0`), **`21.7 km/h` scheduled speed** (vs `9.8 km/h` 40-route median), **`4.42` peak riders/service-hour**, **`0.847` demand variability**, **`100%` exclusive stops**, and `7.97` 3-nearest-neighbor distance.

### 5.1 Pre-Set Selection Rule (`k = 2`) vs Chosen Solution (`k = 3`) Side-by-Side (`m3_clustering_k_selection.csv`, `m3_clustering_k2_vs_k3_comparison.csv`)

On the remaining **40 routes**, candidate $k \in \{2, 3, 4, 5, 6\}$ were evaluated:

| $k$ (40 routes) | Silhouette | 10-Start ARI Mean | Leave-One-Route-Out ARI Mean | 1-Start ARI Mean | Cluster Sizes | Singletons | Rule / Selection Status |
| :---: | ---: | ---: | ---: | ---: | :--- | :--- | :--- |
| **2** | **0.2551** | **1.0000** | **0.9873** | 0.4416 | `23, 17` | None | **Chosen by pre-set rule** |
| **3** | **0.2682** | **0.9831** | **0.9126** | 0.7522 | `18, 15, 7` | None | **Retained (explicit departure from rule)** |
| **4** | 0.2844 | 0.9084 | 0.9085 | 0.6331 | `15, 13, 7, 5` | None | Rejected (10-start stability drop) |
| **5** | 0.2817 | 0.8307 | 0.8654 | 0.5657 | `15, 13, 6, 5, 1` | `M98` | Rejected (`M98` singleton) |
| **6** | 0.2972 | 0.7497 | 0.8444 | 0.5771 | `15, 10, 6, 5, 3, 1` | `M98` | Rejected (`M98` singleton + lower ARI) |

![Clustering K Selection & DBSCAN Evaluation](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_clustering_evaluation.png)

- **Honest Accounting of the Selection Rule:** Our pre-set rule — *"pick the number of groups that is most stable with 10 starts (`ari_10starts_mean`) and when leaving one route out (`ari_loo_mean`), unless its silhouette is clearly lower"* — **picks `k = 2` (`1.000` 10-start ARI, `0.987` leave-one-out ARI, `0.255` silhouette)** because `0.255` vs `0.268` is not clearly lower (and 1-start agreement `0.442` vs `0.752` was not part of the written rule).
- **Why We Departed from the Rule to Keep `k = 3`:** We keep **`k = 3`** and present **`k = 2` vs `k = 3` side by side** because `k = 2` merges **`1,431`-weekday-rider lower-volume/high-variability routes** (`M106, M21, M22, M50, M8, M9, M98`) together with **`6,871`-weekday-rider short high-density crosstown/SBS routes** (`M15+, M86+, M96, M42, M34+, M23+`, etc.) plus `M125` inside one 23-route cluster (`k2_2`), hiding an operationally distinct low-volume group (`k = 3` maintains strong stability at `0.983` 10-start ARI and `0.913` LOO ARI with zero singletons).
- **Weak Overall Structure:** Silhouette scores across all $k \in \{2..6\}$ sit in a narrow, weak band (**`0.255–0.297`**). Manhattan bus routes form a continuous spectrum rather than crisp, separated clusters.

#### Side-by-Side Group Profiles (`k = 2` Rule Winner vs `k = 3` Retained Groups)

| Partition | Group | $n$ | Median Weekday Riders | Median Length (km) | Median Peak Riders/Svc-Hr | Median Variability | Median Wknd Ratio | Median Excl. Stop Share | Routes / Composition |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| **`k = 2` (Pre-set rule winner)** | `k2_1` | 17 | ~7,193 | 12.70 | 32.48 | 0.175 | 0.762 | 41.8% | 17 of 18 `k=3` Group 1 routes (excl. `M125`) |
| **`k = 2` (Pre-set rule winner)** | `k2_2` | 23 | ~4,807 | 4.24 | 58.55 | 0.176 | 0.513 | 60.7% | Merges all 15 `k=3` Group 2 + all 7 `k=3` Group 3 + `M125` |
| **`k = 3` (Chosen departure)** | **Group 1:** Longer routes | 18 | **~7,018** | **12.58** | **32.45** | **0.175** | **0.755** | **44.7%** | `M1, M10, M101–M104, M11, M12, M125, M15, M2, M20, M3, M4, M5, M55, M60+, M7` |
| **`k = 3` (Chosen departure)** | **Group 2:** Short routes with the most riders per service-hour | 15 | **~6,871** | **4.24** | **65.76** | **0.163** | **0.539** | **50.0%** | `M116, M14A+, M14D+, M15+, M23+, M31, M34+, M34A+, M42, M57, M66, M72, M79+, M86+, M96` |
| **`k = 3` (Chosen departure)** | **Group 3:** Short routes with fewer riders and less steady demand | 7 | **~1,431** | **4.06** | **36.08** | **0.276** | **0.470** | **69.1%** | `M106, M21, M22, M50, M8, M9, M98` |
| **Separate Outlier** | `M35` (excluded before KMeans) | 1 | **~146** | **4.95** | **4.42** | **0.847** | **1.666** | **100.0%** | `M35` (RFK Bridge to Randall's Island; speed `21.7 km/h`) |

![PCA Projection & Route Map of K=3 Groups + M35](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_clustering_pca_and_map.png)

- **40-Route PCA Variance Explained ([`m3_clustering_pca_variance.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_clustering_pca_variance.csv)):** Fitted on the **40 clustered routes (`M35` excluded)**, the first two principal components explain **`36.1%` (`PC1`, `0.3606`)** and **`23.1%` (`PC2`, `0.2306`)** — **`59.1%` (`0.5913`) cumulative variance** — with `M35` projected afterwards onto those 40-route axes (`PC1 = -0.2, PC2 = -3.1`).

### 5.2 Non-Fitting Exceptions & DBSCAN Cross-Check (`m3_cluster_group_profiles_unscaled.csv`, `m3_clustering_dbscan_summary.csv`)
Because cluster boundaries are soft, several routes fall into a group due to secondary features despite differing on length or ridership:
- **In Group 1 (Longer routes):** `M12` (`5.55 km`, `~1,097/day`), `M55` (`7.02 km`, `~1,306/day`), and `M20` (`10.13 km`, `~1,187/day`) carry far fewer riders than the `~7,018`-rider median (`M10` at `8.36 km` / `~2,899/day` and `M125` at `5.38 km` / `~4,294/day` are also shorter), placed in Group 1 due to high weekend retention (`0.616–1.007`) and night share (`11.2%–14.4%`).
- **In Group 2 (Short high-density):** `M15+` (`13.89 km`, `~22,500/day`) is over 3x the `4.24 km` median length, grouped here by `72.16` peak riders/service-hour and low demand variability (`0.136`).
- **In Group 3 (Short lower-volume, less steady):** `M98` (`11.78 km`, `~1,115/day`, `0.001` weekend ratio, `0.378` variability) becomes a singleton at $k=5,6$; `M9` (`7.71 km`, `~3,834/day`, variability `0.175`) sits between Groups 1 and 3.
- **DBSCAN Cross-Check (`eps=1.80, min_samples=3`):** At the 3-NN k-distance elbow, DBSCAN identifies **3 density cores covering 29 routes** (`Cluster 0`: 10 Group 1 avenue routes; `Cluster 1`: 16 routes mixing 14 Group 2 + `M125` + `M9`; `Cluster 2`: `M12, M20, M55`) while marking **12 routes (`29.3%`) as noise** (`M35`, `M15+`, `M15`, `M60+`, `M10`, `M104`, plus 6 Group 3 routes). On the 29 non-noise routes, `ARI vs KMeans = 0.6389` (`silhouette = 0.3821`).

---

## 6. Known Limits (Model Cards & Scope Caveats)

All model cards ([`models/model_cards.json`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/models/model_cards.json), [`reports/model_cards.md`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/model_cards.md)) record four explicit limitations:
1. **Cut-offs selected before retraining:** Both classification cut-offs (`0.96 × threshold_p75` for `Forecast ÷ Trips` and `0.63` probability for `HistGradientBoostingClassifier`) were selected on validation predictions from models trained only on January–May 2026, before retraining on January–July 2026.
2. **Holiday × normal-timetable rarity:** January–May training contains **no public holiday operating a normal timetable** (`Juneteenth` on 19 June 2026 had `is_public_holiday=True` and `holiday_schedule=False`, appearing only once across validation / Jan–Jul retraining).
3. **Single flagged outlier event:** Only the 6-hour `M35` surge on Saturday 19 September 2026 (`14:00–19:00`) was flagged as an outlier (`is_outlier == True`); other isolated single-day spikes or drops remain unflagged in training and evaluation.
4. **Boardings vs bus occupancy:** Hourly MTA ridership counts **boardings**, not how full a bus is — `riders_per_trip` divides hourly boardings by `trips_running` without alightings, through-passengers, or vehicle capacity (articulated vs standard buses).

---

## 7. Week 6 — Operational Forecaster, Unseen October Evaluation, Review List & Service Reallocation (Steps 6–9)

### 7.1 Step 6 — Reusable Operational Predictor & Unseen October Evaluation ([`src/predict.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/src/predict.py))
- **Unseen October Inputs & Validation Checks ([`m3_october_diagnostic_checks.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_october_diagnostic_checks.csv)):** Scored the `2026-10-18..2026-10-31` window (`10` weekdays `Oct 19–23, 26–30`; `4` weekend days `Oct 18, 24, 25, 31`) using the **17 October 2026 GTFS** (`data/raw/gtfs/manhattan/2026-10-17/original.zip`, `feed_version = 20261009`) and **October 2026 MTA ridership** (`data/raw/ridership/2026-10.csv`). Confirmed all 6 `clean_ridership.validate` checks pass (`0` issues across nulls, non-integer counts, negative ridership, negative transfers, `transfers > ridership`, duplicate route-hours), `find_outage_hours_relative(..., threshold=0.20)` flags **`0` outage hours** across October (excl. Columbus Day `2026-10-12`), and the `-BM` bridge-trip (`2–3/day`) and `6,229–8,573/day` regular `trips_running` definitions match [`src/build_schedule.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/src/build_schedule.py).
- **Row Count Reconciliation (`12,270` active vs `12,335` matched grid):** Across `41 × 14 × 24 = 13,776` potential route-hours, `1,441` have `trips_running == 0 & ridership == 0` (`neither`), **`12,270` active route-hours (`trips_running >= 1`) are both scored and evaluated** ([`m3_october_predictions.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_october_predictions.csv)), and `65` unscheduled cells have `trips_running == 0 & ridership > 0` (`113` total riders, accounting for `12,335` matched-grid rows).
- **Frozen Step 5 Evaluation + Separate Post-Test Production Retrain:** Official Step 5 test evaluation (`2026-11-13`, `reports/test_runs.log` untouched at `1` line) remains frozen on `models/final_forecaster.joblib` (`Jan–Jul 2026`). Because test evaluation is finished, `src/predict.py` also trains a separate post-test **production model (`models/production_forecaster_jan_sep.joblib`, Jan–Sep 2026, `233,221` rows excl. 6 `M35` outlier hours)** with identical validation-chosen settings and reports it on a **separate, labeled row after the frozen Step 5 result**.

> **Plain Forecasting Result:** **On unseen October data, neither the frozen Step 5 model nor the Jan–Sep production retrain beat the 4-week average overall.**

| Operational Lag Mode | Active Hours (`Matched`) | Model / Baseline | Training Window | MAE | RMSE | WAPE (%) | Bias (Pred − Actual) | Routes Beating 4-Wk Avg |
| :--- | ---: | :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| **Publish Cutoff (`<= 2026-10-17`, realistic)** | 12,270 (`12,335`) | **4-Week Average Baseline** | 4-week rolling | 34.35 | 59.63 | **11.69%** (`11.70%`) | -11.85 | — |
| **Publish Cutoff (`<= 2026-10-17`, realistic)** | 12,270 (`12,335`) | **Frozen Step 5 HGB Forecaster** | Jan–Jul 2026 | 36.06 | 63.28 | **12.28%** (`12.28%`) | -10.36 | **20 / 41** |
| **Publish Cutoff (`<= 2026-10-17`, realistic)** | 12,270 (`12,335`) | *Production HGB (post-test retrain)* | *Jan–Sep 2026* | *36.85* | *64.22* | ***12.54%*** (`12.55%`) | *-6.87* | *18 / 41* |
| **Rolling Lags (`7d–28d`, diagnostic)** | 12,270 (`12,335`) | **4-Week Average Baseline** | 4-week rolling | 32.91 | 56.81 | **11.20%** (`11.20%`) | -11.01 | — |
| **Rolling Lags (`7d–28d`, diagnostic)** | 12,270 (`12,335`) | **Frozen Step 5 HGB Forecaster** | Jan–Jul 2026 | 33.21 | 59.43 | **11.30%** (`11.31%`) | -16.41 | **26 / 41** |
| **Rolling Lags (`7d–28d`, diagnostic)** | 12,270 (`12,335`) | *Production HGB (post-test retrain)* | *Jan–Sep 2026* | *33.24* | *59.59* | ***11.32%*** (`11.32%`) | *-16.41* | *28 / 41* |

- **Why the Model Missed — Checked Diagnostic Possibilities ([`m3_october_forecast_by_day.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_october_forecast_by_day.csv), [`m3_october_diagnostic_checks.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_october_diagnostic_checks.csv)):**
  1. *Higher autumn ridership level / negative bias (consistent, not causal proof):* Unseen `Oct 18–31` averages **`293.75` riders/active hr**, **`+17.1%`** above Jan–Jul (`250.89/hr`) and above Aug–Sep (`255.30/hr`; Sep = `270.99/hr`); that level shift is **consistent with** the model's negative bias (`-10.36` cutoff to `-16.41` rolling), though a single 2-week sample cannot prove causation alone.
  2. *Calendar `month` as a feature (ruled out):* Inspecting `preprocessor.feature_names_in_` verifies **`month` is NOT a model feature (`in_model = False`, `0.00` prediction effect)**; all `22` inputs are domain, schedule, and lag features.
  3. *Retraining on Jan–Sep made October slightly worse & 2-week variance:* Under the publish cutoff, **retraining through September (`Jan–Sep`) slightly worsened October WAPE from `12.28%` (frozen) to `12.54%`** (and from `11.30%` to `11.32%` under rolling lags), even though cutoff bias narrowed from `-10.36` to `-6.87`. Adding two more training months did not help—when demand shifts to an unseen level, the model's edge disappears while the 4-week average adjusts automatically. Within this small 14-day sample, Frozen HGB beats the baseline on weekends and Mondays (`10-18`, `10-19`, `10-24`, `10-25`, `10-26`, `10-31`) but trails during Week 2 weekdays (`10-27..10-30`: `11.11%–13.74%` vs `8.24%–9.60%` baseline).
- **Future Work (Untested):** Predict ridership **relative to the 4-week average** (training the model on deviations from the moving baseline rather than raw hourly levels) so seasonal or autumn level shifts are absorbed by the baseline automatically.
- **High-Demand Classification (`12,270` active hours, actual positive rate = `37.23%` [`4,568 / 12,270`], [`m3_october_classification_summary.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_october_classification_summary.csv)):** Because October ridership sits `+17.1%` above Jan–Jul, **`37.23%` of active hours exceed the fixed `p75` cutoff** (up from `~25%` in training and `25.2%` in Aug–Sep test), which raises `PR-AUC` across every rule and model. Alongside that **`37.23%` actual positive share**, **`Forecast ÷ Trips (> 0.96 × p75)`** scores:
  - **Baseline Rule B (`> 1.00 × p75`):** `PR-AUC = 0.8878`, `ROC-AUC = 0.9418`, `F1 = 0.8143` (`Precision = 0.8572`, `Recall = 0.7754`, `4,132` flagged = `33.68%`).
  - **Frozen Step 5 (`Jan–Jul`):** **`PR-AUC = 0.8967`**, **`ROC-AUC = 0.9492`**, **`F1 = 0.8456`** (`Precision = 0.8353`, `Recall = 0.8562`, `4,682` flagged = `38.16%`), and **`0.8688`** precision at Rule B's `4,132`-flag workload.
  - *Post-test Production (`Jan–Sep`, separate row):* *`PR-AUC = 0.8990`, `ROC-AUC = 0.9498`, `F1 = 0.8447` (`Precision = 0.8354`, `Recall = 0.8542`, `4,671` flagged = `38.07%`), **`0.8698`** precision at Rule B workload.*

![Unseen October 2026 Evaluation — Daily Cutoff WAPE & Overall Comparison](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_october_unseen_evaluation.png)

---

### 7.2 Step 7 — Config-Driven `(route, day_group, time_band)` Review List ([`configs/optimization_thresholds.json`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/configs/optimization_thresholds.json), [`src/build_review_list.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/src/build_review_list.py))
All Step 7–9 screening rules live in [`configs/optimization_thresholds.json`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/configs/optimization_thresholds.json). To satisfy Milestone 2's sample-size floor (`min_days_count = 20`) instead of basing service recommendations on a 14-day window (`4` weekend days), Step 7–9 screen the **3-month observed typical-day window (`2026-08-01..2026-10-31`)** — `92` calendar days reduced to **`90` typical days** (`weekday` = `63` typical days; `weekend` = `27` typical days, excluding Labor Day `2026-09-07`, Columbus Day `2026-10-12`, the `Aug 16 21:00–22:00` outage [`2` hrs], and the `M35 Sep 19 14:00–19:00` outlier [`6` hrs], spanning `78,756` active route-hours) against the fixed **`1.00 × threshold_p75`** Jan–May cutoff. **Using August and September here is valid without leaking test data:** the single official test run is already finished and logged ([`reports/test_runs.log`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/test_runs.log)), and the review list only summarizes observed ridership (`matched_hourly.parquet` directly, without reading `test_features.parquet`, tuning settings, or updating any model).

- **`1–17 October` Full Pipeline Check:** Extending Step 7–9 from `18–31 Oct` to the full `90`-day typical window incorporates `1–17 October` (`11` typical weekdays + `5` typical weekend days = `16` typical days, `14,019` active route-hours, `4,078,270` riders) from the same `2026-10.csv` file, passed through full `load_clean_ridership_history` (`validate`) checks, matched to the **3 September GTFS (`2026-09-03`)** for `1–16 Oct` (switching to `2026-10-17` GTFS on `17 Oct` with `0` boundary spillover differences), and screened under the same holiday-schedule (`-Weekday-SDon`) and `20%` outage rules (`Columbus Day 2026-10-12` excluded; `find_outage_hours_relative(..., threshold=0.20)` flags **`0` outage hours** across all of `1–31 Oct`, and `M35` max is `95` riders with `0` outlier hours).
- **`fewer_trips_screening` (`fewer_trips_candidate`):** `obs_riders_per_service_hour <= 22.0`, `high_demand_freq_pct <= 15.0%`, `min_days_count >= 20`, and `min_avg_trips_per_day >= 2.0`.
- **`more_trips_screening` (`more_trips_candidate`):** `high_demand_freq_pct >= 65.0%`, `obs_riders_per_service_hour >= 40.0`, `min_days_count >= 20`, and `min_avg_trips_per_day >= 2.0` (excluding low-trip outliers like `M35`).
- **Coverage & overlap guardrails:** `high_exclusive_stop_share >= 0.60` caps trims at `-10%` (`moderate_exclusive_stop_share = 0.40`); `shared_corridor_overlap.allowed_overlap_category = "shared_corridor"` with `min_overlap_share_for_merge_check = 0.40` (excluding `same_family` pairs); `demand_trend_bands` `±3.0%` vs non-overlapping `Jan–Jul` typical service (`hist_jan_jul_riders_per_service_hour`).

Running `python -m src.build_review_list` produces [`m3_step7_review_list.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_step7_review_list.csv) (**`400` rows** across `weekday` [`205` cells, `41` routes, all `63` days] and `weekend` [`195` cells, `40` routes, `193` cells at `27` days; `M98` has no weekend trips]):

| Day Type (`Aug–Oct` Typical Days) | Total Cells | Observed Service-Hours | `fewer_trips_candidate` | `more_trips_candidate` | `shared_corridor_overlap_watch` | `no_change_watch` |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Weekday (`63` days)** | 205 | 423,430.1 | **32** (`55,427.6` hrs, `13.09%`) | **20** (`39,743.2` hrs, `9.39%`) | **42** (`157,895.5` hrs, `37.29%`) | **111** (`170,363.8` hrs, `40.23%`) |
| **Weekend (`27` days)** | 195 | 126,799.9 | **42** (`22,775.6` hrs, `17.96%`) | **14** (`11,914.8` hrs, `9.40%`) | **41** (`41,757.8` hrs, `32.93%`) | **98** (`50,351.7` hrs, `39.71%`) |
| **90-Day Typical Total** | **400** | **550,230.0** | **74** (`78,203.2` hrs) | **34** (`51,658.0` hrs) | **83** (`199,653.3` hrs) | **209** (`220,715.4` hrs) |

Five low-sample weekend cells (`22.35` hrs) are explicitly held out as `no_change_watch` (`hold_or_monitor_low_sample`): **`2` spillover cells below `20` days** (`M15+ weekend early_morning` at `14` days, `1.0` trip/day; `M20 weekend early_morning` at `13` days, `1.0` trip/day) plus `3` `27`-day minimal-service cells averaging `1.0` trip/day (`M106 night`, `M12 early_morning`, `M50 early_morning`).

---

### 7.3 Steps 8–9 — Service Scenarios, `shared_corridor` Merge Checks & Budget-Neutral Reallocation ([`src/recommend_adjustments.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/src/recommend_adjustments.py))

> **Explicit Demand Assumption:** All Step 8–9 scenarios and reallocation calculations assume **ridership stays constant (`assumed_ridership_elasticity = 0.0`) when scheduled trips change (`±10%` or `±20%`)**, subject to a minimum floor of `1` trip per active hour.

1. **Candidate Trip Scenarios ([`m3_step8_candidate_scenarios.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_step8_candidate_scenarios.csv)):** `432` rows evaluating `[-20%, -10%, +10%, +20%]` trip changes across all `108` candidate `(route, day_group, time_band)` cells (`74` `fewer_trips_candidate` + `34` `more_trips_candidate`).
2. **`shared_corridor` Merge Feasibility Checks ([`m3_step8_shared_corridor_merge_checks.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_step8_shared_corridor_merge_checks.csv)):** Evaluated **`18` strictly `shared_corridor` route pairs (`>= 30%` stop overlap; `0` `same_family` pairs)** using daily observed demand normalized by each route's actual typical active days in `Aug–Oct`. **`11` pairs meet the `>= 40%` rule** (`M101/M103 77.4%`, `M102/M103 72.6%`, `M101/M102 66.7%`, `M1/M2 57.5%`, `M2/M3 54.9%`, `M31/M57 54.8%`, `M106/M96 50.0%`, `M1/M3 47.8%`, `M101/M125 43.9%`, `M116/M7 42.9%`, `M3/M4 40.8%`), where every pair shows the smaller route also serving `12` to `98` stops that the larger route doesn't, so a full merger would take service away from those stops.
3. **Budget-Neutral Reallocation Plan ([`m3_step9_budget_neutral_reallocation.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_step9_budget_neutral_reallocation.csv), `39` rows):** Balanced **independently within `weekday` (`63` typical days) and `weekend` (`27` typical days)** after filtering out `fewer_trips_candidate` trims that move shoulder hours above `1.00 × threshold_p75` and capping `exclusive_stop_share >= 0.60` trims at `-10%`:
   - **Weekday Plan (`63` typical days `2026-08-03..2026-10-30`):** **`12` donor cells** (`early_morning -451.09`, `night -643.62`) shift **`1,094.71` service-hours** (`-17.38 hrs/day`, **`0.26%`** of `423,430.1` weekday service-hours; `0` donor route-hours moving above `p75`) to **`4` recipient cells with high riders per trip** (`M42`, `M15+`, `M11`, `M72` evening peak), adding **`+1,094.06` service-hours** (`+17.37 hrs/day`; net **`-0.65` hrs**). **With riders held constant, `135` route-hours over `63` weekdays (about `2` per day) fall below the high-demand threshold.**
   - **Weekend Plan (`27` typical days `2026-08-01..2026-10-31`):** **`20` donor cells** (`early_morning -383.16`, `night -88.95`) shift **`472.11` service-hours** (`-17.49 hrs/day`, **`0.37%`** of `126,799.9` weekend service-hours; `0` donor route-hours moving above `p75`) to **`3` recipient cells with high riders per trip** (`M14D+` midday & evening peak, `M12` midday), adding **`+465.35` service-hours** (`+17.24 hrs/day`; net **`-6.76` hrs**). **With riders held constant, `84` route-hours over `27` weekend days (about `3` per day) fall below the high-demand threshold.**
   - **90-Day Typical-Day Total (`Aug 1–Oct 31`):** **`32` donor cells** shift **`1,566.82` service-hours (`0.28%` of `550,230.0` network service-hours)** to **`7` recipient cells** (`+1,559.41` service-hours; net **`-7.41` hrs**). **With riders held constant, `219` route-hours over `90` typical days (about `2.4` per day) fall below the high-demand threshold** (`0` donor route-hours moving above `p75`).

![Step 9 Budget-Neutral Reallocation Summary](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_step9_reallocation_summary.png)
