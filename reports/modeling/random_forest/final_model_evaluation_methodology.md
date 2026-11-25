# AI_RouteRanker - Final Model Evaluation Methodology (Phase 3.3)

**Project:** `AI_RouteRanker - AI-Powered Public Transit Route Optimization`  
**Milestone:** 5.2 - Modeling Phase 3.3  
**Status:** Approved & Implemented  

---

## 1. Scope and Objective
Milestone 5.2 Phase 3.3 evaluates the finalized tuned Random Forest models (Candidate 3) on previously untouched, chronological evaluation partitions. The primary objective is to evaluate generalization performance out-of-sample and quantify performance differentials against the Phase 2 Seasonal Naive benchmark ($t - 7$ days).

---

## 2. Evaluation Partitions

| Tier | Regime | Partition | Date Range | Predictor Count | Expected Rows |
|---|---|---|---|---:|---:|
| **Tier 1** | Post-Pandemic Macro | Test (GTFS Era) | 2025-11-23 to 2026-07-31 | 160 | 28,798 |
| **Tier 1** | Post-Pandemic Macro | August Holdout | 2026-08-01 to 2026-08-31 | 160 | 3,566 |
| **Tier 2** | Contemporary GTFS-Informed | Test | 2026-05-30 to 2026-07-31 | 169 | 7,293 |

The August 2026 holdout remains strictly isolated from Tier 1 test evaluation. Tier 2 contains no separate August holdout.

---

## 3. Evaluated Model Configurations

Only Candidate 3 tuned Random Forest models selected during Phase 3.2 are evaluated:
- **Tier 1:** `artifacts/random_forest/tier1_random_forest_tuned.joblib`
- **Tier 2:** `artifacts/random_forest/tier2_random_forest_tuned.joblib`

Both models share the approved Candidate 3 hyperparameter architecture:
- `n_estimators`: 100
- `max_depth`: 14
- `min_samples_split`: 4
- `min_samples_leaf`: 5
- `max_features`: 0.70
- `bootstrap`: True
- `random_state`: 42
- `n_jobs`: 2

No retraining, refitting, or post-hoc threshold tuning was performed. Models operate strictly in inference mode.

---

## 4. Chronological Feature Availability & Leakage Safeguards

1. **One-Day-Ahead Boundary:** For route $r$ and date $t$, features use information strictly prior to date $t$.
2. **Milestone 4 Observation-Row Semantics:** Lag features (`rides_lag_1`, `rides_lag_7`, `rides_lag_14`, `rides_lag_28`) and rolling statistics (`rolling_mean_*`, `rolling_std_*`) represent preceding observation rows for route $r$ in chronological sequence. For routes with weekday-only schedules, observation lags span multiple calendar days without assuming continuous daily operations.
3. **Target & Leakage Exclusions:** `target_rides` and `rides_per_scheduled_trip` are strictly excluded from all predictor matrices.
4. **Encoder Transformation Isolation:** `RouteEncoder` and `DaytypeEncoder` instances fitted strictly on training partitions are applied via `transform()` only.

---

## 5. Fair Head-to-Head Comparison Methodology

To compare Tier 1 and Tier 2 objectively:
1. **Shared Window:** The evaluation window is restricted to the exact overlap: `2026-05-30` to `2026-07-31`.
2. **Common Composite Keys:** Predictions are joined on composite keys `(route, date)`.
3. **Exact Key and Target Parity:** Identical ordered composite keys and bit-for-bit target equality ($\max |\Delta y| < 10^{-4}$) are verified prior to calculating comparative metrics.

---

## 6. Memory Safeguards and Metric Categorization

To guarantee physical system stability on 8 GB RAM hardware:
1. **Predictor Matrix Memory:** Calculated as $N 	imes P 	imes 4	ext{ bytes}$ float32:
   - Tier 1 Test (28,798 × 160): ~18.43 MB
   - Tier 1 August Holdout (3,566 × 160): ~2.28 MB
   - Tier 2 Test (7,293 × 169): ~4.93 MB
2. **Python Process Footprint:** Estimated at ~150–250 MB total process heap.
3. **Physical System Memory:** Verified before and after every partition via Win32 `GlobalMemoryStatusEx`. Hard abort thresholds: `< 600 MB` available physical RAM or `> 95%` memory load.

---

## 7. Data Availability Disclosure & Operational Regimes (Remediation)

- **Assumed Information Boundary:** The evaluation methodology strictly operates under an assumed one-day-ahead information boundary (observations prior to target date $t$ are assumed available to predict demand on date $t$).
- **Unverified Agency Reporting Latency:** Actual CTA ridership data publication schedules, reporting delays, and data-portal release latencies were not independently verified or benchmarked against production ingestion logs.
- **Evaluation vs. Production Reality:** Consequently, these evaluation metrics demonstrate out-of-sample predictive performance under the assumed historical-information regime ($t - 1$ availability), rather than confirmed real-time or day-of-service operational deployment availability. No specific publication latency duration is asserted or assumed beyond this defined boundary.
