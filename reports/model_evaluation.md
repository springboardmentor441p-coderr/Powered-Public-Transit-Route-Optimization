# RouteRanker Model Evaluation Report

- **Model Version**: `v3.8-prototype`
- **Missing History Policy**: Option 2 (Impute missing 28d lag from 7/14/21d mean + availability indicator)
- **Selected Service-Aware Regressor**: `ridge`

## Held-Out Test Comparison (Matched Service Experiment)
| Method | Test Rows | MAE (rides/day) | RMSE (rides/day) | WAPE (%) |
|---|---:|---:|---:|---:|
| Last-Week Baseline (D-7) | 610 | 1038.33 | 1349.98 | 7.74% |
| Seasonal 4-Week Mean Baseline | 610 | 865.36 | 1120.23 | 6.45% |
| **ridge (Selected)** | **610** | **820.59** | **1055.52** | **6.11%** |

## Route Clustering Summary
- **Clusters (K)**: 3
- **Clustered Routes**: 10
- **Silhouette Score**: 0.2935
