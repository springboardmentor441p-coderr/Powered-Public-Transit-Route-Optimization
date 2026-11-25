# Milestone 5.2 – Phase 3.2: Random Forest Hyperparameter Tuning Report

**Project:** `AI_RouteRanker – AI-Powered Public Transit Route Optimization`  
**Execution Timestamp:** 2026-11-21T20:49:31.351475  
**Artifacts Directory:** [artifacts/random_forest/](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/artifacts/random_forest/)  
**Reports Directory:** [reports/modeling/random_forest/](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/reports/modeling/random_forest/)  

---

## 1. Executive Summary

Milestone 5.2 Phase 3.2 executed a bounded hyperparameter search across 8 candidate configurations per tier:
- **Candidate 0 (Phase 3.1 Benchmark Anchor):** Loaded directly from disk with zero retraining.
- **Candidates 1 through 7:** Trained sequentially on approved training partitions under Win32 memory monitoring (< 600 MB / > 95% abort guards).
- **Exact Key Alignment:** All comparative metrics were calculated strictly on the identical common keys evaluated by Phase 2 Seasonal Naive (**37,785 keys for Tier 1; 4,116 keys for Tier 2**).
- **Test Partition Protection:** Test and August holdout partitions were never queried, loaded, or evaluated.

---

## 2. Tier 1 Tuning Results (Post-Pandemic Macro Regime)

**Common Validation Rows Evaluated:** 37,785 rows | **Benchmark:** Baseline B WAPE = **9.3594%**

| Candidate | Configuration | Time (s) | Common WAPE (%) | Delta WAPE | MAE | Delta MAE | RMSE | Delta RMSE | $R^2$ | Delta $R^2$ | Secondary Det.? |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **C0** | d=12, feat=1.0, split=2, leaf=5, n=100 | 215.7s | **7.5095%** | +0.0000% | 359.02 | +0.00 | 636.03 | +0.00 | 0.9800 | +0.0000 | None (Clean) |
| **C1** | d=12, feat=0.7, split=2, leaf=5, n=100 | 75.1s | **7.2967%** | -0.2128% | 348.85 | -10.18 | 601.46 | -34.57 | 0.9821 | +0.0021 | None (Clean) |
| **C2** | d=12, feat=0.85, split=4, leaf=5, n=100 | 171.7s | **7.3949%** | -0.1146% | 353.54 | -5.48 | 615.58 | -20.45 | 0.9812 | +0.0012 | None (Clean) |
| **C3** | d=14, feat=0.7, split=4, leaf=5, n=100 | 131.2s | **7.2430%** | -0.2665% | 346.28 | -12.74 | 598.76 | -37.27 | 0.9822 | +0.0022 | None (Clean) |
| **C4** | d=14, feat=0.85, split=10, leaf=8, n=100 | 188.5s | **7.3024%** | -0.2071% | 349.12 | -9.90 | 611.79 | -24.24 | 0.9815 | +0.0015 | None (Clean) |
| **C5** | d=10, feat=0.7, split=10, leaf=8, n=100 | 73.1s | **7.4624%** | -0.0471% | 356.77 | -2.25 | 612.00 | -24.03 | 0.9815 | +0.0015 | None (Clean) |
| **C6** | d=12, feat=0.7, split=4, leaf=5, n=150 | 119.9s | **7.2865%** | -0.2230% | 348.36 | -10.66 | 601.13 | -34.90 | 0.9821 | +0.0021 | None (Clean) |
| **C7** | d=12, feat=0.85, split=4, leaf=3, n=100 | 73.5s | **7.4501%** | -0.0594% | 356.18 | -2.84 | 619.77 | -16.26 | 0.9810 | +0.0010 | None (Clean) |

### Tier 1 Additional Observation (Route N5 on 2025-01-01)
- Actual target rides: **13.0**
- Candidate 0 prediction: **360.48** (Absolute Error: **347.48**)
- Champion prediction: **354.98** (Absolute Error: **341.98**)

### Tier 1 Champion Decision:
- **Selected Champion:** **Candidate 3**
- **Decision Rationale:** Candidate 3 selected as champion: Achieved lower WAPE (7.2430% vs 7.5095%) with zero secondary metric deterioration (dMAE=-12.74, dRMSE=-37.27, dR2=+0.0022).

---

## 3. Tier 2 Tuning Results (Contemporary Supply-Informed Regime)

**Common Validation Rows Evaluated:** 4,116 rows | **Benchmark:** Baseline B WAPE = **6.6800%**

| Candidate | Configuration | Time (s) | Common WAPE (%) | Delta WAPE | MAE | Delta MAE | RMSE | Delta RMSE | $R^2$ | Delta $R^2$ | Secondary Det.? |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **C0** | d=12, feat=1.0, split=2, leaf=5, n=100 | 23.4s | **5.8643%** | +0.0000% | 304.44 | +0.00 | 503.71 | +0.00 | 0.9891 | +0.0000 | None (Clean) |
| **C1** | d=12, feat=0.7, split=2, leaf=5, n=100 | 7.5s | **5.6359%** | -0.2284% | 292.58 | -11.85 | 474.04 | -29.68 | 0.9903 | +0.0012 | None (Clean) |
| **C2** | d=12, feat=0.85, split=4, leaf=5, n=100 | 9.0s | **5.7247%** | -0.1396% | 297.19 | -7.24 | 488.51 | -15.21 | 0.9897 | +0.0006 | None (Clean) |
| **C3** | d=14, feat=0.7, split=4, leaf=5, n=100 | 8.2s | **5.6173%** | -0.2470% | 291.61 | -12.82 | 472.94 | -30.77 | 0.9904 | +0.0013 | None (Clean) |
| **C4** | d=14, feat=0.85, split=10, leaf=8, n=100 | 8.9s | **5.7140%** | -0.1503% | 296.63 | -7.80 | 486.43 | -17.28 | 0.9898 | +0.0007 | None (Clean) |
| **C5** | d=10, feat=0.7, split=10, leaf=8, n=100 | 7.2s | **5.7889%** | -0.0754% | 300.52 | -3.91 | 481.11 | -22.61 | 0.9900 | +0.0009 | None (Clean) |
| **C6** | d=12, feat=0.7, split=4, leaf=5, n=150 | 18.5s | **5.6236%** | -0.2407% | 291.94 | -12.49 | 473.43 | -30.28 | 0.9904 | +0.0013 | None (Clean) |
| **C7** | d=12, feat=0.85, split=4, leaf=3, n=100 | 15.0s | **5.7614%** | -0.1029% | 299.10 | -5.34 | 487.82 | -15.89 | 0.9898 | +0.0007 | None (Clean) |

### Tier 2 Additional Observation (Route 10 on 2026-05-20)
- Actual target rides: **2.0**
- Candidate 0 prediction: **569.88** (Absolute Error: **567.88**)
- Champion prediction: **536.61** (Absolute Error: **534.61**)

### Tier 2 Champion Decision:
- **Selected Champion:** **Candidate 3**
- **Decision Rationale:** Candidate 3 selected as champion: Achieved lower WAPE (5.6173% vs 5.8643%) with zero secondary metric deterioration (dMAE=-12.82, dRMSE=-30.77, dR2=+0.0013).

---

## 4. Hardware Observations & Execution Safety
- **Win32 Memory Checks:** Executed before every candidate fit with zero API failures.
- **Abort Status:** Zero aborts triggered (available physical RAM remained safely above 600 MB threshold).
- **Sequential Cleanup:** Explicit garbage collection between candidates prevented memory buildup.
