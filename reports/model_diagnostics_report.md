git add reports/model_diagnostics_report.md# NYC Bus Passenger Demand Forecasting — Model Diagnostics Report

**Project:** Powered Public Transit Route Optimization
**Scope:** NYC Bus Routes
**Evaluation version:** V2
**Date:** 17 November 2026

---

## 1. Objective

This report documents the performance and diagnostic analysis of the passenger demand forecasting models developed for eight selected NYC bus routes.

The objectives were to:

- Compare forecasting models using chronological validation and testing.
- Evaluate performance against a previous-week baseline.
- Identify route-specific prediction errors.
- Investigate unusual passenger-count observations.
- Examine forecasting performance during evening peak hours.

## 2. Dataset and Features

The forecasting dataset contains hourly passenger-count observations for eight bus routes:

B6, BX12+, M101, M15, M15+, Q27, Q44+ and Q58.

The feature dataset contains 113,088 records and covers:

**8 January 2025 – 1 September 2026**

Features include:

- Bus route
- Hour
- Day of week
- Day of month
- Month
- Weekend indicator
- Previous-hour passenger count
- Previous-day passenger count
- Previous-week passenger count

The first 168 hours per route were excluded when preparing the lag-based forecasting dataset because complete historical lag values were unavailable.

## 3. Model Training and Evaluation Methodology

Two ensemble regression models were evaluated:

- Random Forest Regressor
- Extra Trees Regressor

The V2 experiment used chronological splitting:

| Dataset | Proportion |
|---|---:|
| Training | 70% |
| Validation | 15% |
| Testing | 15% |

The validation set was used to select the model. Extra Trees achieved the lower validation MAE and was selected for final evaluation.

The selected model was retrained using the combined training and validation data and evaluated on the untouched test set.

The previous-week passenger count was used as a baseline prediction.

## 4. Overall Model Performance

### Validation results

| Model | MAE | RMSE | WAPE | R² |
|---|---:|---:|---:|---:|
| Extra Trees | 43.76 | 65.27 | 7.71% | 0.9801 |
| Random Forest | 44.95 | 68.25 | 7.92% | 0.9782 |

Extra Trees was selected based on its better validation performance.

### Final test results

| Model | MAE | RMSE | WAPE | R² |
|---|---:|---:|---:|---:|
| Extra Trees | 43.12 | 65.23 | 8.08% | 0.9771 |
| Previous-week baseline | 66.57 | 111.45 | 12.47% | 0.9331 |

Extra Trees reduced MAE by approximately **35.23%** compared with the baseline.

These results indicate that the selected model performed better than the previous-week baseline on the evaluated test period.

## 5. Route-wise Performance

| Route | Extra Trees MAE | Baseline MAE | MAE Improvement |
|---|---:|---:|---:|
| Q27 | 32.34 | 47.26 | 31.57% |
| B6 | 35.89 | 55.14 | 34.91% |
| BX12+ | 37.28 | 61.09 | 38.99% |
| Q58 | 41.65 | 58.54 | 28.85% |
| Q44+ | 42.01 | 62.17 | 32.43% |
| M101 | 45.33 | 64.32 | 29.53% |
| M15 | 50.87 | 75.54 | 32.65% |
| M15+ | 59.62 | 108.48 | 45.04% |

Each route contributed 2,121 test records.

All eight routes showed lower MAE with Extra Trees than with the previous-week baseline.

M15+ had the highest absolute MAE, while Q27 had the lowest. M15+ also showed the largest percentage improvement over the baseline.

## 6. Prediction Error Analysis

The test set contained 16,968 records.

| Measure | Result |
|---|---:|
| MAE | 43.12 |
| RMSE | 65.23 |
| Mean signed error | +3.85 |
| Overpredictions | 9,241 |
| Underpredictions | 7,727 |

Signed error is calculated as predicted passengers minus actual passengers. The positive mean signed error indicates a small overall tendency to overpredict.

The largest absolute prediction errors were concentrated on M15+. This route should receive further investigation during future model improvement.

### Hourly MAE

| Hour | MAE |
|---|---:|
| 00:00 | 17.42 |
| 01:00 | 9.63 |
| 02:00 | 5.20 |
| 03:00 | 5.28 |
| 04:00 | 11.22 |
| 05:00 | 21.10 |
| 06:00 | 48.62 |
| 07:00 | 61.44 |
| 08:00 | 63.87 |
| 09:00 | 58.92 |
| 10:00 | 54.36 |
| 11:00 | 51.99 |
| 12:00 | 51.94 |
| 13:00 | 56.21 |
| 14:00 | 59.21 |
| 15:00 | 60.58 |
| 16:00 | 64.39 |
| 17:00 | 69.93 |
| 18:00 | 70.67 |
| 19:00 | 56.68 |
| 20:00 | 43.73 |
| 21:00 | 37.63 |
| 22:00 | 31.30 |
| 23:00 | 22.88 |

The highest hourly MAE occurred at 18:00, followed by 17:00 and 16:00.

These findings identify evening hours as an important area for further model diagnostics.

## 7. Cross-Route Data Anomaly Investigation

During prediction error analysis, an unusual observation was identified at:

**16 August 2026, 21:00**

All eight selected routes had exceptionally low passenger counts at the same timestamp.

| Route | Passenger count |
|---|---:|
| B6 | 2 |
| BX12+ | 0 |
| M101 | 2 |
| M15 | 1 |
| M15+ | 2 |
| Q27 | 2 |
| Q44+ | 0 |
| Q58 | 2 |
| **Total** | **11** |

The combined passenger count at 20:00 was 2,253, while at 21:00 it was only 11.

The original training CSV was inspected and confirmed to contain these values. Therefore, the cleaning script did not introduce this anomaly.

The eight observations were recorded in a separate audit file:

`data/cross_route_anomaly_audit.csv`

**Interpretation:** The simultaneous near-zero values across all eight routes suggest a shared data-quality or reporting anomaly. Its underlying cause has not been established.

The records were not automatically deleted.

## 8. Sensitivity Evaluation

A separate evaluation compared the original test results with results excluding only the eight flagged observations.

| Metric | All records | Excluding flagged observations |
|---|---:|---:|
| Test records | 16,968 | 16,960 |
| MAE | 43.124 | 43.030 |
| RMSE | 65.226 | 65.001 |
| WAPE | 8.080% | 8.059% |
| R² | 0.977089 | 0.977241 |

The aggregate performance metrics changed only slightly.

This indicates that the eight flagged observations have a limited effect on overall test performance.

However, this does not establish that the observations are valid or that similar anomalies do not exist elsewhere.

The sensitivity results were saved separately in:

`data/anomaly_impact_evaluation_v2.csv`

## 9. Evening-Hour Model Diagnostics

A detailed analysis was conducted for 16:00, 17:00 and 18:00.

### Overall comparison

| Method | Evening MAE |
|---|---:|
| Extra Trees | 68.33 |
| Previous-week baseline | 107.75 |

Extra Trees achieved a **36.58% reduction in MAE** compared with the baseline across 2,136 evening test records.

### Route-level observations

M15+ showed the highest evening prediction errors:

| Hour | M15+ MAE |
|---|---:|
| 16:00 | 94.23 |
| 17:00 | 101.93 |
| 18:00 | 114.67 |

Despite its higher absolute errors, Extra Trees outperformed the baseline for M15+ during all three evening hours.

Across all eight routes and three evening hours, Extra Trees achieved lower MAE than the previous-week baseline in all 24 route-hour combinations.

The comparison was saved in:

`data/evening_model_vs_baseline.csv`

## 10. Key Findings

1. Extra Trees was selected over Random Forest using validation performance.
2. Extra Trees achieved a test MAE of 43.12 and WAPE of 8.08%.
3. The selected model outperformed the previous-week baseline overall and on all eight routes.
4. M15+ had the highest absolute prediction errors and deserves further investigation.
5. Evening hours, especially 17:00 and 18:00, showed higher MAE.
6. Extra Trees still outperformed the baseline across all evaluated evening route-hour combinations.
7. A simultaneous near-zero passenger-count anomaly was identified across all eight routes and documented separately.
8. Excluding the eight flagged observations had only a small effect on aggregate test metrics.

## 11. Limitations and Further Work

The results should be interpreted with the following limitations:

- The evaluation is retrospective and does not establish real-time forecasting capability.
- The availability of historical lag features at the actual forecast issue time must be verified against the data publication schedule.
- The identified anomaly's underlying cause remains unknown.
- Passenger counts do not represent unique passengers, onboard occupancy or vehicle capacity.
- Higher MAE during peak hours does not by itself establish why the errors occur.
- The model has not yet been validated in a live operational environment.

Recommended next steps:

1. Investigate high-error routes, particularly M15+.
2. Examine weekday, weekend and seasonal error patterns.
3. Verify data publication delays and forecast feature availability.
4. Review GTFS route and schedule integration.
5. Explore model improvements using additional validated features.
6. Preserve chronological evaluation and baseline comparisons when testing future models.

## 12. Output Files

| File | Purpose |
|---|---|
| `data/demand_forecasting_predictions_v2.csv` | Final V2 test predictions |
| `data/model_comparison_results_v2.csv` | Final model comparison |
| `data/model_validation_results_v2.csv` | Validation metrics |
| `data/model_performance_by_route_v2.csv` | Route-wise test performance |
| `data/prediction_error_summary_v2.csv` | Overall prediction error summary |
| `data/prediction_errors_by_route_v2.csv` | Route-wise error analysis |
| `data/largest_prediction_errors_v2.csv` | Largest individual errors |
| `data/prediction_errors_by_hour_v2.csv` | Hourly prediction errors |
| `data/cross_route_anomaly_audit.csv` | Flagged anomaly observations |
| `data/anomaly_impact_evaluation_v2.csv` | Sensitivity evaluation |
| `data/evening_prediction_errors_by_route.csv` | Evening errors by route and hour |
| `data/evening_model_vs_baseline.csv` | Evening model comparison |

---

**Conclusion**

The V2 Extra Trees forecasting model demonstrated better predictive performance than the previous-week baseline on the evaluated NYC bus-route test data. The diagnostic analyses identified evening peak hours and M15+ as important areas for further investigation. The discovered cross-route anomaly was documented and evaluated separately without modifying the original dataset or model outputs.
