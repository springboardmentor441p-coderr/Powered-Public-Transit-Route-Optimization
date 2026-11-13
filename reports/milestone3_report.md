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
- **Unseen October Inputs:** Downloaded October 2026 MTA ridership (`data/raw/ridership/2026-10.csv`: `34,224` rows across `46` routes; `0` nulls, `0` negative values, lowest network hourly total `94` riders at `02:00` AM — no outages) and the **17 October 2026 GTFS** (`data/raw/gtfs/manhattan/2026-10-17/original.zip`, `feed_version = 20261009`, regular service `2026-10-09..2026-10-31`, `41` matching routes).
- **Predictions Generated Without Retraining:** Using the frozen Step 5 model (`models/final_forecaster.joblib`, trained on Jan–Jul 2026; `reports/test_runs.log` untouched at `1` line), `python -m src.predict --start-date 2026-10-18 --end-date 2026-10-31 --timetable-version 2026-10-17 --evaluate` scored **`12,270` active route-hours** across `41` routes ([`m3_october_predictions.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_october_predictions.csv)), flagging **`4,682` high-demand hours** (`Forecast ÷ Trips > 0.96 × threshold_p75`).

| Operational Lag Mode | Matched Hours | Model / Baseline | MAE | RMSE | WAPE (%) | Bias (Pred − Actual) | Routes Beating Baseline |
| :--- | ---: | :--- | ---: | ---: | ---: | ---: | :--- |
| **Rolling Lags (`7d–28d`)** | 12,335 | **4-Week Average Baseline** | 32.74 | 56.66 | **11.20%** | -10.96 | — |
| **Rolling Lags (`7d–28d`)** | 12,335 | **Frozen Step 5 HGB Forecaster** | 33.04 | 59.27 | **11.31%** | -16.33 | **26 / 41** |
| **Publish-Date Cutoff (`<= 2026-10-17`)** | 12,335 | **4-Week Average Baseline** | 34.17 | 59.47 | **11.70%** | -11.80 | — |
| **Publish-Date Cutoff (`<= 2026-10-17`)** | 12,335 | **Frozen Step 5 HGB Forecaster** | 35.88 | 63.11 | **12.28%** | -10.31 | **20 / 41** |

- **Forecasting Interpretation ([`m3_october_forecast_summary.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_october_forecast_summary.csv), [`m3_october_forecast_by_day.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_october_forecast_by_day.csv)):** Across `12,335` matched hours under Rolling Lags, the frozen Jan–Jul HGB model finishes just **`+0.11` pp** behind the 4-week rolling baseline (`11.31%` vs `11.20%`) because late-October peak volume (`~295k–302k/day` on major trunks such as `M15+`) exceeds Jan–Jul leaf expectations (`-16.33` bias). Nevertheless, HGB **beats the 4-week average on `26 of 41` individual routes** and outperforms it on Sundays and Mondays (`10-18`, `10-19`, `10-25`, `10-26`) after Columbus Day (`10-12`).
- **High-Demand Classification (`12,270` active hours, `4,568` actual positive = `37.2%`, [`m3_october_classification_summary.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_october_classification_summary.csv)):** Frozen **`Forecast ÷ Trips (> 0.96 × p75)` beats Rule B on every metric**:
  - **PR-AUC:** **`0.8967`** vs **`0.8878`**
  - **ROC-AUC:** **`0.9492`** vs **`0.9418`**
  - **Precision at Rule B workload (`4,132` flagged hours):** **`0.8688`** vs **`0.8572`**
  - **Max-F1 Cut-Off Comparison:** **`F1 = 0.8456`** (`Precision = 0.8353`, `Recall = 0.8562`, `4,682` flagged hours) vs Rule B **`F1 = 0.8143`**

![Unseen October 2026 Evaluation — Daily WAPE & Window Progression](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_october_unseen_evaluation.png)

---

### 7.2 Step 7 — Config-Driven `(route, time_band)` Review List ([`configs/optimization_thresholds.json`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/configs/optimization_thresholds.json), [`src/build_review_list.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/src/build_review_list.py))
All Step 7–9 screening rules live in [`configs/optimization_thresholds.json`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/configs/optimization_thresholds.json):
- **Underused screening:** `pred_riders_per_service_hour <= 22.0`, `high_demand_freq_pct <= 15.0%`, `active_hours >= 10`, `trips >= 20`.
- **High-demand screening:** `high_demand_freq_pct >= 65.0%`, `pred_riders_per_service_hour >= 40.0`, `active_hours >= 15`.
- **Coverage & overlap guardrails:** `high_exclusive_stop_share >= 0.60` caps trip trims at `-10%` (`moderate_exclusive_stop_share = 0.40`); `shared_corridor_overlap.allowed_overlap_category = "shared_corridor"` with `min_overlap_share_for_merge_check = 0.40` (strictly excluding `same_family` pairs); forecast trend bands `±3.0%`.

Running `python -m src.build_review_list` produces [`m3_step7_review_list.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_step7_review_list.csv) (`205` rows = `41 routes × 5 time bands`), joining riders per service-hour, high-demand frequency, forecast trend vs 4-week baseline, stop exclusivity, top overlap & top `shared_corridor` partner, route group, and a metric-backed written `reason`:
- **`no_change_watch` (`99` rows):** Balanced load or moderate demand below high-demand / underused cutoffs.
- **`shared_corridor_overlap_watch` (`37` rows):** Daytime/evening cells with top `shared_corridor` overlap `>= 40%`; held for headway spacing rather than unilateral cuts.
- **`high_demand_candidate` (`36` rows):** Frequently crowded high-load corridors (`M23+`, `M42`, `M14A+/D+`, `M60+`, `M72`, `M79+`, `M66`, `M86+`).
- **`underused_candidate` (`33` rows, totaling `12,178.7` scheduled service-hours):** Low-load windows concentrated in `early_morning` and `night` bands.

---

### 7.3 Steps 8–9 — Service Scenarios, `shared_corridor` Merge Checks & Budget-Neutral Reallocation ([`src/recommend_adjustments.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/src/recommend_adjustments.py))

> **Explicit Demand Assumption:** All Step 8–9 scenarios and reallocation calculations assume **ridership stays constant (`assumed_ridership_elasticity = 0.0`) when scheduled trips change (`±10%` or `±20%`)**, subject to a minimum floor of `1` trip per active hour.

1. **Candidate Trip Scenarios ([`m3_step8_candidate_scenarios.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_step8_candidate_scenarios.csv)):** `276` rows evaluating `[-20%, -10%, +10%, +20%]` trip changes across all `69` Step 7 adjustment candidates (`33` underused + `36` high-demand).
2. **`shared_corridor` Merge Feasibility Checks ([`m3_step8_shared_corridor_merge_checks.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_step8_shared_corridor_merge_checks.csv)):** Evaluated **`18` strictly `shared_corridor` route pairs (`>= 30%` stop overlap; `0` `same_family` pairs)**. **`11` pairs meet the `>= 40%` rule** (`M101/M103 77.4%`, `M102/M103 72.6%`, `M101/M102 66.7%`, `M1/M2 57.5%`, `M2/M3 54.9%`, `M31/M57 54.8%`, `M106/M96 50.0%`, `M1/M3 47.8%`, `M101/M125 43.9%`, `M116/M7 42.9%`, `M3/M4 40.8%`), supporting timed headway spacing on shared trunk segments rather than deleting distinct northern/crosstown branches.
3. **Budget-Neutral Reallocation Plan ([`m3_step9_budget_neutral_reallocation.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m3_step9_budget_neutral_reallocation.csv)):**
   - **Crowding-safe donor filter:** Rejects underused candidates whose `-10%` trim triggers new shoulder-hour alerts (`M101 night`, `M2 night`, `M4 night`, `M5 night`, `M7 night`) and caps trims at `-10%` when `exclusive_stop_share >= 0.60`.
   - **Donors (`16` cells in `early_morning` `-135` service-hours and `night` `-433` service-hours across `M20, M55, M125, M10, M104, M7, M3, M103, M21, M5, M102, M1, M11`):** frees **`568.62` service-hours** across the 14-day window while creating **`0` new high-demand hours**.
   - **Recipients (`8` congested cells: `M23+ eve +20%`, `M42 eve +20%`, `M14D+ eve +20%`, `M14A+ eve +20%`, `M60+ mor +20%`, `M60+ eve +20%`, `M72 eve +20%`, `M79+ eve +10%`):** adds **`+561.54` service-hours**.
   - **Net Plan Balance:** **`-7.08` service-hours (`<= 0.0` budget-neutral)**, relieving **`91` high-demand hours** under the explicit **riders-stay-constant** assumption.

![Step 9 Budget-Neutral Reallocation Summary](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m3_step9_reallocation_summary.png)
