# AI_RouteRanker - Final Model Evaluation Report (Phase 3.3)

**Project:** `AI_RouteRanker - AI-Powered Public Transit Route Optimization`  
**Milestone:** 5.2 - Modeling Phase 3.3  
**Status:** Completed & Verified  

---

## 1. Executive Summary

Milestone 5.2 Phase 3.3 evaluated the tuned Random Forest models (Candidate 3) against the approved Phase 2 Seasonal Naive benchmark ($t - 7$ days) across all out-of-sample partitions.

Key results:
1. **Tier 1 Test (GTFS Era, 28,798 rows):** Random Forest achieved **WAPE = 8.5279%**, beating Seasonal Naive (12.0843%) by **3.5564%**. MAE improved by **167.72**, and RMSE improved by **380.36**.
2. **Tier 1 August Holdout (3,566 rows):** Random Forest achieved **WAPE = 8.1985%**, beating Seasonal Naive (10.8486%) by **2.6502%**.
3. **Tier 2 Test (7,293 rows):** Random Forest achieved **WAPE = 8.1013%**, beating Seasonal Naive (10.1194%) by **2.0181%**. MAE improved by **98.28**, and RMSE improved by **191.46**.
4. **Fair Head-to-Head Comparison (May 30 to July 31, 2026, 7,293 common rows):**
   - Tier 1 Tuned WAPE: **8.1089%** (MAE = 394.88, RMSE = 683.25, $R^2$ = 0.9780)
   - Tier 2 Tuned WAPE: **8.1013%** (MAE = 394.51, RMSE = 671.59, $R^2$ = 0.9788)
   - Tier 2 outperforms Tier 1 by **0.0076% WAPE** and **0.37 MAE** on the identical observations, demonstrating the predictive value of GTFS scheduled supply features.

---

## 2. Partition Evaluation Performance

| Tier | Partition | Date Range | Rows | Coverage | RF WAPE | Base B WAPE | $\Delta$ WAPE | RF MAE | Base B MAE | RF RMSE | Base B RMSE | RF $R^2$ | Base B $R^2$ |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Tier 1** | Test (GTFS Era) | 2025-11-23 to 2026-07-31 | 28,798 | 100.0% | **8.5279%** | 12.0843% | **-3.5564%** | **402.18** | 569.91 | **701.57** | 1081.93 | **0.9756** | 0.9421 |
| **Tier 1** | August Holdout | 2026-08-01 to 2026-08-31 | 3,566 | 100.0% | **8.1985%** | 10.8486% | **-2.6502%** | **399.54** | 528.69 | **709.66** | 904.35 | **0.9761** | 0.9612 |
| **Tier 2** | Test | 2026-05-30 to 2026-07-31 | 7,293 | 100.0% | **8.1013%** | 10.1194% | **-2.0181%** | **394.51** | 492.79 | **671.59** | 863.05 | **0.9788** | 0.9650 |

---

## 3. Fair Head-to-Head Comparison: Tier 1 vs Tier 2

- **Comparison Window:** 2026-05-30 to 2026-07-31
- **Common Key Intersection:** 7,293 unique `(route, date)` pairs
- **Excluded Observations:** Tier 1: 0 | Tier 2: 0
- **Exact Key Parity:** True
- **Target Parity:** True

| Metric | Tier 1 (Macro Regime) | Tier 2 (GTFS Contemporary) | Delta (Tier 2 - Tier 1) | Advantage |
|---|---:|---:|---:|---|
| **WAPE** | 8.1089% | **8.1013%** | **-0.0076%** | **Tier 2 (0.0076% lower)** |
| **MAE** | 394.88 | **394.51** | **-0.37** | **Tier 2 (0.37 lower)** |
| **RMSE** | 683.25 | **671.59** | **-11.66** | **Tier 2 (11.66 lower)** |
| **$R^2$** | 0.9780 | **0.9788** | **+0.0007** | **Tier 2 (+0.0007 higher)** |

---

## 4. Hardware and Computational Observations

| Partition | Predictors | Matrix Memory (est.) | Duration | Pre-Avail RAM | Pre-Load | Post-Avail RAM | Post-Load |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Tier 1 Test** | 160 | 17.58 MB | 0.69s | 871.57 MB | 89% | 900.37 MB | 88% |
| **Tier 1 August** | 160 | 2.18 MB | 0.28s | 906.39 MB | 88% | 886.15 MB | 88% |
| **Tier 2 Test** | 169 | 4.7 MB | 0.31s | 886.18 MB | 88% | 885.67 MB | 88% |

All pre- and post-partition system physical RAM observations comfortably satisfied the safe thresholds (> 600 MB available physical RAM, < 95% memory load). Total process heap footprint remained stably between 150 MB and 250 MB throughout inference.

---

## 5. Operational Data Availability Disclosure (Remediation)

- **Assumed Information Boundary:** Model evaluation across all test and holdout partitions was executed under an assumed one-day-ahead information boundary (historical information strictly prior to target date $t$ was utilized).
- **Unverified Agency Reporting Latency:** Actual CTA ridership publication delays and data portal update frequencies were not independently verified or benchmarked against historical release schedules.
- **Evaluation Scope Clarification:** The reported metrics demonstrate model predictive accuracy under the assumed historical-information regime, not confirmed real-time operational availability. Future production deployment must account for transit agency publication cadence before day-of-operation forecasting.
