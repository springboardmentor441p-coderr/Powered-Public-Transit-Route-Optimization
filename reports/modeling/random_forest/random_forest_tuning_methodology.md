# Milestone 5.2 – Phase 3.2: Random Forest Hyperparameter Optimization Methodology

**Project:** `AI_RouteRanker – AI-Powered Public Transit Route Optimization`  
**Location:** [analytics/modeling/random_forest/](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/analytics/modeling/random_forest/)  
**Phase:** 3.2 Bounded Hyperparameter Optimization (7 New Candidates + Reused Candidate 0).

---

## 1. Executive Summary & Design Principles

Phase 3.2 implements a strictly bounded hyperparameter search designed to explore key variance-reduction, depth-expansion, and feature-subsampling dimensions without compromising data causality or computational safety on an 8 GB RAM laptop.

### Core Safeguards Implemented:
1. **Candidate 0 Reused Without Retraining:** The existing Phase 3.1 models (`tier1_random_forest.joblib` and `tier2_random_forest.joblib`) are loaded directly as the benchmark (Candidate 0), expending zero unnecessary training compute.
2. **Exact Key Alignment on Common Validation Rows:** Metric evaluations and comparative selections are computed strictly on unique composite keys `(route, date)` matching the exact rows evaluated by Phase 2 Seasonal Naive (37,785 common keys for Tier 1; 4,116 common keys for Tier 2).
3. **Upstream SQL Partition Isolation:** `DataLoader.load_slice()` loads only approved training and validation dates via SQL predicate pushdown. Test and August holdout partitions are never queried, loaded, or present in memory.
4. **Conservative Selection Policy for Secondary Deteriorations:** If a tuned candidate achieves lower common-row WAPE than Candidate 0 but exhibits secondary metric deterioration (higher RMSE, higher MAE, or lower R²), Candidate 0 is retained as the default champion pending explicit user review.
5. **Win32 Memory Monitoring:** `GlobalMemoryStatusEx` checks available physical RAM and memory load before every candidate with a conservative abort threshold (< 600 MB available RAM or > 95% memory load).

---

## 2. The 8-Candidate Search Space

```
Candidate 0 (Benchmark Anchor — Loaded from Phase 3.1):
  n_estimators=100, max_depth=12, min_samples_split=2,  min_samples_leaf=5, max_features=1.00

Candidate 1 (Feature Decorrelation via 70% Subsampling):
  n_estimators=100, max_depth=12, min_samples_split=2,  min_samples_leaf=5, max_features=0.70

Candidate 2 (Moderate Subsampling & Split Regularization):
  n_estimators=100, max_depth=12, min_samples_split=4,  min_samples_leaf=5, max_features=0.85

Candidate 3 (Deeper Trees with Feature Subsampling):
  n_estimators=100, max_depth=14, min_samples_split=4,  min_samples_leaf=5, max_features=0.70

Candidate 4 (Deeper Trees with Leaf Regularization):
  n_estimators=100, max_depth=14, min_samples_split=10, min_samples_leaf=8, max_features=0.85

Candidate 5 (Conservative Tree Depth & Split Smoothing):
  n_estimators=100, max_depth=10, min_samples_split=10, min_samples_leaf=8, max_features=0.70

Candidate 6 (Ensemble Expansion - 150 Trees):
  n_estimators=150, max_depth=12, min_samples_split=4,  min_samples_leaf=5, max_features=0.70

Candidate 7 (Granular Tail Fitting with Feature Subsampling):
  n_estimators=100, max_depth=12, min_samples_split=4,  min_samples_leaf=3, max_features=0.85
```

---

## 3. Validation-Selection Bias & Overfitting Controls

Evaluating multiple candidate models on a single validation period creates the mathematical risk of validation-selection bias (choosing a model that overfits idiosyncratic fluctuations of that period).

To mitigate this risk:
- **The candidate budget is strictly fixed at 7 new models.** No iterative parameter expansion is permitted.
- **Structural regularization** (`min_samples_leaf >= 3`, `max_depth <= 14`) prevents leaf-level memorization of noise.
- **Zero Test Snooping:** Test partitions are never accessed to resolve candidate selection uncertainty.
