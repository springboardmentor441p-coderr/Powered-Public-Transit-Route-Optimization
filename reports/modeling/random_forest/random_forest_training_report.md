# Milestone 5.2 – Phase 3.1: Random Forest Initial Training Report

**Project:** `AI_RouteRanker – AI-Powered Public Transit Route Optimization`  
**Execution Timestamp:** 2026-11-21T19:53:40.718147  
**Artifacts Directory:** [artifacts/random_forest/](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/artifacts/random_forest/)  
**Reports Directory:** [reports/modeling/random_forest/](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/reports/modeling/random_forest/)  

---

## 1. Executive Summary

Milestone 5.2 Phase 3.1 successfully implemented and trained two independent Random Forest models under controlled, leak-free conditions:
1. **Tier 1 Model (Post-Pandemic Macro Regime):** Trained on 125,447 rows (160 predictors) in 215.72s.
2. **Tier 2 Model (Contemporary Supply-Informed Regime):** Trained on 17,388 rows (169 predictors) in 23.39s.

Both models were evaluated strictly on their corresponding validation partitions. No test or holdout data was touched.

---

## 2. Validation Performance Summary

| Tier | Model | Expected Rows | Evaluated Rows | Coverage | MAE | RMSE | $R^2$ | WAPE (%) |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | Random Forest (Phase 3.1) | 37786 | 37786 | 100.0% | **359.02** | **636.03** | **0.9800** | **7.51%** |
| **2** | Random Forest (Phase 3.1) | 4117 | 4117 | 100.0% | **304.50** | **503.73** | **0.9891** | **5.87%** |

---

## 3. Comparison with Phase 2 Baselines

### Tier 1 Validation Partition (37,786 rows)
- **Baseline A (Historical Mean):** MAE = 977.5079, WAPE = 20.4461%
- **Baseline B (Seasonal Naive $t-7$):** MAE = 447.4613, WAPE = 9.3594%
- **Random Forest (Initial):** MAE = 359.0223, WAPE = 7.5097%
  - *Diff vs Baseline A:* -12.94% WAPE (Beats Baseline A: **True**)
  - *Diff vs Baseline B:* -1.85% WAPE (Beats Baseline B: **True**)

### Tier 2 Validation Partition (4,117 rows)
- **Baseline A (Historical Mean):** MAE = 664.8767, WAPE = 12.8074%
- **Baseline B (Seasonal Naive $t-7$):** MAE = 346.78, WAPE = 6.68%
- **Random Forest (Initial):** MAE = 304.499, WAPE = 5.8669%
  - *Diff vs Baseline A:* -6.94% WAPE (Beats Baseline A: **True**)
  - *Diff vs Baseline B:* -0.81% WAPE (Beats Baseline B: **True**)

---

## 4. Hardware & Resource Consumption
- Sequential execution preserved system memory below safe laptop operating limits.
- Tier 1 training completed in 215.7s.
- Tier 2 training completed in 23.4s.
- Zero memory exhaustion or system instability encountered.
