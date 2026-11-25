# Milestone 5.2 – Phase 2: Naive Baselines Methodology Specification

**Project:** `AI_RouteRanker – AI-Powered Public Transit Route Optimization`  
**Location:** [analytics/modeling/baselines/](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/analytics/modeling/baselines/)  
**Status:** Strictly Phase 2 Implementation (Zero Machine-Learning Models Trained).

---

## 1. Executive Summary

This document specifies the mathematical formulations, prioritized fallback hierarchies, causal guardrails, and rolling evaluation policies for the two reference naive baselines developed in Phase 2 of Milestone 5.2:
1. **Baseline A:** Route/Daytype Expanding Historical Mean.
2. **Baseline B:** Seasonal Naive (Calendar $t - 7$ Days with Hierarchical Fallbacks).

These baselines serve as rigorous, leak-free empirical benchmarks against which subsequent machine-learning models (such as Random Forest Regression in Phase 3) must be compared.

---

## 2. Baseline A: Route/Daytype Expanding Historical Mean

### A. Mathematical Formulation
For each target observation on route $r$, daytype $d \in \{W, A, U\}$, and prediction date $t$:

$$\hat{y}^{\text{BaseA}}_{r, d, t} = \frac{1}{|S_{r, d, <t}|} \sum_{\tau \in S_{r, d, <t}} y_{r, d, \tau}$$

Where:
- $S_{r, d, <t} = \{ \tau \in \mathcal{D}_{\text{history}} \mid \text{route}(\tau) = r, \text{daytype}(\tau) = d, \text{date}(\tau) < t \}$.
- $\mathcal{D}_{\text{history}}$ is the eligible historical observation pool starting at the partition train boundary:
  - **Tier 1:** Starts on `2022-01-01` (post-pandemic structural regime).
  - **Tier 2:** Starts on `2025-11-23` (contemporary GTFS era).

### B. Hierarchical Fallbacks
1. **Primary Prediction:** Expanding mean for exact `(route, daytype)` pair strictly prior to date $t$.
2. **Secondary Fallback:** If $|S_{r, d, <t}| = 0$ (e.g., a route has run on weekdays but has its first weekend run), fall back to the expanding mean across all daytypes for route $r$ strictly prior to date $t$.
3. **Tertiary Fallback:** If route $r$ has zero prior history in the eligible pool (e.g. debut day of newly introduced route `N5` on `2025-01-01`), mark prediction as **`unavailable` (`NaN`)**.
4. **Zero Substitution Prohibition:** The baseline **never silently substitutes zero** for missing history.

### C. Causal & Leakage Guardrails
- **Strictly Historical:** Only observations with $\text{date} < t$ are included in the expanding summation.
- **Zero Target-Date Leakage:** Target-date ridership $y_{r, d, t}$ is strictly excluded from its own prediction.
- **Zero Future Leakage:** Future observations ($\tau > t$) are never accessible.

---

## 3. Baseline B: Seasonal Naive (Calendar $t - 7$ Days)

### A. Distinction from Feature `rides_lag_7`
- In Milestone 4, `rides_lag_7` was generated via:
  $$\text{LAG}(\text{rides}, 7) \text{ OVER (PARTITION BY route ORDER BY date ASC)}$$
  This shifts by **seven operational observation rows**, which spans 9 to 14 calendar days for non-daily routes (e.g., weekday-only routes, express shuttles).
- **Baseline B strictly uses calendar date arithmetic:**
  $$\text{Target Lookup Date} = t - 7\text{ calendar days}$$
  It looks for the exact same route's ground-truth ridership exactly 7 calendar days earlier.

### B. Prioritized Fallback Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│               BASELINE B PREDICTION PRIORITY HIERARCHY                 │
├───────────────────┬──────────────────────────────────┬─────────────────┤
│ Level             │ Condition                        │ Fallback Action │
├───────────────────┼──────────────────────────────────┼─────────────────┤
│ Priority 1 (99.3%)│ Exact match on (r, t - 7 days)   │ Use y(r, t-7d)  │
├───────────────────┼──────────────────────────────────┼─────────────────┤
│ Priority 2 (0.6%) │ Date (t - 7d) missing/suspended  │ Use most recent │
│                   │                                  │ obs for (r, d)  │
│                   │                                  │ in [t-28d, t-1d]│
├───────────────────┼──────────────────────────────────┼─────────────────┤
│ Priority 3 (0.1%) │ No obs in preceding 28 days      │ Expanding mean  │
│                   │                                  │ for (r, d) < t  │
├───────────────────┼──────────────────────────────────┼─────────────────┤
│ Priority 4 (0.01%)│ Zero prior history for route r   │ Mark UNAVAILABLE│
│                   │                                  │ (NaN)           │
└───────────────────┴──────────────────────────────────┴─────────────────┘
```

1. **Priority 1 (`calendar_t7`):** Look for ground-truth ridership of route $r$ on exact calendar date $t - 7\text{ days}$.
2. **Priority 2 (`recent_28d_daytype`):** If $t - 7\text{ days}$ is absent (e.g., route suspended or service altered), find the most recent observation for the same route and daytype strictly within the preceding 28 calendar days ($[t - 28\text{ days}, t - 1\text{ day}]$).
3. **Priority 3 (`historical_mean`):** If no observation exists in the trailing 28 days, fall back to the expanding historical mean for $(r, d)$ strictly before date $t$.
4. **Priority 4 (`unavailable`):** If no eligible historical record exists, mark as unavailable (`NaN`). Do not substitute zero.

---

## 4. Evaluation Protocol & Chronological Slices

Partitions are strictly chronological and mutually exclusive. Tier 1 and Tier 2 are evaluated independently:

### Tier 1 Partitions (Post-Pandemic Macro)
- **Train Window (History Inception):** `2022-01-01` to `2024-12-31` ($125,447$ rows).
- **Validation Partition:** `2025-01-01` to `2025-11-22` ($37,786$ rows).
- **Test Partition (GTFS Era):** `2025-11-23` to `2026-07-31` ($28,798$ rows).
- **August 2026 Holdout:** `2026-08-01` to `2026-08-31` ($3,566$ rows).

### Tier 2 Partitions (Contemporary GTFS Era)
- **Train Window (History Inception):** `2025-11-23` to `2026-04-23` (Snapshots 1–5, $17,388$ rows).
- **Validation Partition:** `2026-04-24` to `2026-05-29` (Snapshot 6, $4,117$ rows).
- **Test Partition:** `2026-05-30` to `2026-07-31` (Snapshots 7–8, $7,293$ rows).

---

## 5. Rolling One-Day-Ahead Policy & Operational Latency

### A. Rolling Dynamic Updates
Evaluation simulates daily operational transit forecasting:
- When predicting for date $t$, all ground-truth ridership values for dates $\tau < t$ (including realized validation/test actuals from date $t - 1$) become eligible for the expanding historical pool.
- At date $t$, actual ridership $y_{r, d, t}$ is strictly unknown and withheld.

### B. Operational Telemetry Latency Assumption
- **Idealized Benchmark Assumption:** At 04:00 AM on operational date $t$, finalized ridership from date $t - 1$ is assumed to be fully validated and present in the database.
- **Real-World Caveat:** In actual transit operations, Automated Fare Collection (AFC) and Automated Passenger Counter (APC) data require batch validation and reconciliation. This phase evaluates an idealized upper-bound operational baseline; production systems with a $k$-day reporting delay would operate with a minimum lag of $k$ days.

---

## 6. Mathematical Metric Definitions

1. **Mean Absolute Error (MAE):**
   $$\text{MAE} = \frac{1}{N} \sum_{i=1}^N |y_i - \hat{y}_i|$$
2. **Root Mean Squared Error (RMSE):**
   $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^N (y_i - \hat{y}_i)^2}$$
3. **Coefficient of Determination ($R^2$):**
   $$R^2 = 1 - \frac{\sum_{i=1}^N (y_i - \hat{y}_i)^2}{\sum_{i=1}^N (y_i - \bar{y})^2}$$
4. **Weighted Absolute Percentage Error (WAPE):**
   $$\text{WAPE} = \frac{\sum_{i=1}^N |y_i - \hat{y}_i|}{\sum_{i=1}^N y_i} \times 100$$
   *Zero Denominator Guard:* If $\sum y_i = 0$, WAPE returns `NaN` rather than raising a division-by-zero exception.
5. **Prediction Coverage:**
   $$\text{Coverage (\%)} = \frac{\text{Predictions Generated}}{\text{Expected Partition Rows}} \times 100$$
