# Milestone 5.2 – Phase 3.1: Random Forest Regression Methodology

**Project:** `AI_RouteRanker – AI-Powered Public Transit Route Optimization`  
**Location:** [analytics/modeling/random_forest/](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/analytics/modeling/random_forest/)  
**Phase:** 3.1 Controlled Initial Training (Single Fixed Hyperparameter Set).

---

## 1. Controlled Initial Configuration

In accordance with Phase 3.1 specifications, exactly one controlled configuration of `sklearn.ensemble.RandomForestRegressor` was evaluated across both Tier 1 and Tier 2. Zero hyperparameter tuning or grid searches were performed.

```json
{
  "n_estimators": 100,
  "max_depth": 12,
  "min_samples_leaf": 5,
  "random_state": 42,
  "n_jobs": 2,
  "max_features": 1.0,
  "bootstrap": true,
  "criterion": "squared_error"
}
```

### Justification of Fixed Parameters:
- **`n_estimators = 100`:** Sufficient ensemble size to stabilize variance without exceeding 8 GB RAM memory bounds.
- **`max_depth = 12`:** Controlled tree depth prevents deep overfitting to idiosyncrasies of specific historical calendar periods.
- **`min_samples_leaf = 5`:** Regularization preventing leaf-level memorization of rare service anomalies.
- **`n_jobs = 2`:** Strictly capped to prevent CPU starvation on the Core i5-1334U workstation.
- **`max_features = 1.0`:** Full feature consideration per split for initial baseline benchmarking.
- **`random_state = 42`:** Guarantees absolute deterministic reproducibility.

---

## 2. Temporal Partitioning & Leakage Safeguards

1. **Non-Overlapping Partitions:**
   - **Tier 1 Train:** `2022-01-01` to `2024-12-31` (125,447 rows).
   - **Tier 1 Validation:** `2025-01-01` to `2025-11-22` (37,786 rows).
   - **Tier 2 Train:** `2025-11-23` to `2026-04-23` (17,388 rows).
   - **Tier 2 Validation:** `2026-04-24` to `2026-05-29` (4,117 rows).
2. **Strict Test Isolation:** Test partitions (`2025-11-23` to `2026-07-31` for Tier 1; `2026-05-30` to `2026-07-31` for Tier 2) and the August 2026 Holdout partition were **never accessed, loaded, or evaluated**.
3. **Encoder Fitting:** All categorical encoders (`RouteEncoder`, `DaytypeEncoder`) were fitted exclusively on training data.
4. **Target Leakage Prohibition:** `target_rides` and contemporaneous `rides_per_scheduled_trip` were strictly excluded from feature matrices.
