# Phase 6.3 — Risk Register and Mitigation Strategy
## Analytical, Architectural, and Environmental Risk Governance for Route Ranker Feature Synthesis

**Project:** AI_RouteRanker — AI-Powered Public Transit Route Optimization  
**Project Directory:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Date:** 2026-11-25 13:40:00 +05:30  
**Phase:** Phase 6.3 (Milestone 6 Module 4 / Module 5 Integration Bridge)  
**Mode:** **READ-ONLY INSPECTION AND PLANNING ONLY**  
**Status:** **RISK REGISTER FORMALIZED**

---

## 1. Overview & Risk Governance Framework

Phase 6.3 brings together disparate data streams from stop clustering (Phase 6.1), corridor and operational clustering (Phase 6.2), and machine learning passenger demand forecasting (Milestone 5). 

To ensure the resulting `route_ranker_feature_master.parquet` is analytically sound, mathematically robust, and safe for downstream ranking in Module 5, this risk register identifies potential hazards, assesses their severity, and establishes concrete mitigation strategies.

### Risk Matrix Categories
- **Severity:** High / Medium / Low
- **Likelihood:** High / Medium / Low
- **Domain:** Data Integrity, Machine Learning / Methodology, Spatial Interpretation, Hardware & Environment, Software Regression

---

## 2. Detailed Risk Assessment and Mitigation Strategies

### Risk R-01: Data Asymmetry Between Bus and Rail Modes
- **Domain:** Data Integrity & Downstream Ranking
- **Severity:** High
- **Likelihood:** High (Confirmed in Phase 6.2)
- **Description:** CTA daily boarding data in `analytical.cta_ridership_daily` originates exclusively from bus fareboxes. Heavy rail lines ($N=8$: Red, Blue, Brown, Green, Orange, Purple, Pink, Yellow) record ridership via turnstiles at rail stations, which were not partitioned by route in the historical daily dataset. Consequently, historical ridership and ML forecasted boardings for rail are `NaN`.
- **Potential Impact:** Naive ranking algorithms in Module 5 could penalize rail routes as having "zero" demand, severely distorting network optimization priorities.
- **Mitigation Strategy:**
  1. **Strict `NaN` Preservation:** Do **not** impute rail ridership with `0.0`. Preserve `np.nan` explicitly in `route_ranker_feature_master.parquet`.
  2. **Multi-Modal Flagging:** Maintain `is_rail` boolean and `route_type` integer columns in the feature master.
  3. **Tiered Ranking Architecture:** Downstream Module 5 ranking algorithms must support evaluation masks: evaluating bus routes ($N=125$) on demand and load factors, while evaluating rail routes ($N=8$) on capacity, headway frequency, and transit hub connectivity.

---

### Risk R-02: Missing Operational Headways on Specialized Route Profiles
- **Domain:** Data Integrity & Feature Completeness
- **Severity:** Medium
- **Likelihood:** High (Verified in Phase 6.2 Stage 2 Audit)
- **Description:** Three specialized routes lack scheduled departures during the canonical AM peak window (06:00 to 09:00 AM) on Wednesday `2026-06-10`:
  - `Route 10` (Museum of Science & Industry): Only 1 AM departure; zero consecutive departure intervals.
  - `Route 130` (Museum Campus): First scheduled trip departs at 09:27 AM.
  - `Route N5` (South Shore Night Bus): Overnight service operating 23:00 to 05:00.
- **Potential Impact:** Missing `am_headway_min` values cause these 3 routes to be excluded from $K$-Means operational clustering ($N=130$ clustered routes out of 133). If unhandled, this could cause downstream ranking pipelines to drop these routes.
- **Mitigation Strategy:**
  1. **Documented Missingness:** Preserve `am_headway_min` as `NaN` for Routes 10, 130, and N5.
  2. **Cluster Imputation Flag:** Assign `operational_cluster_k3` as `NaN` (or dedicated specialized cluster category `-1` / `'Specialized'`) with an explicit boolean column `is_specialized_schedule=True`.
  3. **Network Completeness Guarantee:** Guarantee that the final `route_ranker_feature_master.parquet` contains **all 133 routes**, regardless of whether headway is missing.

---

### Risk R-03: Temporal Leakage and Holdout Data Contamination
- **Domain:** Machine Learning & Analytical Validity
- **Severity:** High
- **Likelihood:** Low
- **Description:** Milestone 5 trained Random Forest demand models on historical dates with strict temporal train/validation/test splits. Synthesizing demand predictions into Phase 6.3 could risk data leakage if out-of-sample holdout target values or future weather/calendar data were used.
- **Potential Impact:** Artificially optimistic ranking metrics or circular dependencies violating machine learning best practices.
- **Mitigation Strategy:**
  1. **Frozen Canonical Date:** Demand predictions must be strictly aligned to the approved canonical service date (`2026-06-10`).
  2. **Pre-Trained Model Inference Only:** Phase 6.3 loads the tuned joblib models (`tier1_random_forest_tuned.joblib`) in strict inference mode. No model re-training or hyperparameter adjustments occur.
  3. **Zero Ground-Truth Mixing:** Predicted boardings (`forecasted_daily_demand`) are recorded separately from historical mean daily rides (`historical_mean_daily_rides`).

---

### Risk R-04: Spatial Interpretation Bias (Co-Routing vs Service Redundancy)
- **Domain:** Spatial Methodology & Urban Transit Interpretation
- **Severity:** Medium
- **Likelihood:** High
- **Description:** High corridor buffer overlap ($D_r \ge 0.50$) or shared consecutive stop sequences can easily be misinterpreted as "wasteful duplication." In Chicago's radial grid network, multiple distinct routes necessarily share high-capacity trunk arterials (e.g., Michigan Avenue, State Street, Western Avenue) before branching out into suburban or residential sectors.
- **Potential Impact:** Erroneous route restructuring recommendations that propose cutting critical arterial feeder branches.
- **Mitigation Strategy:**
  1. **Semantic Clarity:** Label the metric `corridor_duplication_ratio` and `co_routing_index` with explicit documentation that co-routing represents arterial infrastructure sharing, not operational waste.
  2. **Branching Ratio Indicator:** Incorporate the proportion of non-shared stops ($1 - D_r$) to highlight unique service coverage provided beyond shared arterial corridors.
  3. **Regional Stratification:** Incorporate the Fréchet $K=2$ regional divider (`North Chicago` vs `South Chicago`) so routes are benchmarked against geographically relevant peers.

---

### Risk R-05: Hardware Memory Exhaustion (8 GB Physical RAM Ceiling)
- **Domain:** Environment & Infrastructure
- **Severity:** High
- **Likelihood:** Low (Mitigated by Design)
- **Description:** The host environment is a Windows machine with 8 GB physical RAM and CPU-only execution. If Phase 6.3 were to recompute pairwise buffer overlaps or Cartesian joins across 1.2 million stop times, memory exhaustion would crash the process.
- **Potential Impact:** Process termination, memory thrashing, corrupt intermediate files.
- **Mitigation Strategy:**
  1. **Precomputed Asset Reuse:** Strictly read already computed matrices (`buffer_overlap_similarity_matrix.parquet`, `shared_consecutive_stop_sequences.parquet`, `transit_hub_rankings.parquet`). Zero polygon buffering or Fréchet calculations in Phase 6.3.
  2. **Memory Footprint Ceiling:** Keep total working memory $<150\text{ MB}$.
  3. **Active Memory Guard:** Enforce automatic abort if available RAM $<600\text{ MB}$ or system memory load $>95\%$.

---

### Risk R-06: Regression Drift and Mutation of Protected Assets
- **Domain:** Software Engineering & Reproducibility
- **Severity:** High
- **Likelihood:** Very Low
- **Description:** Accidental modification of existing tables in `ai_routeranker.duckdb`, models in `artifacts/random_forest/`, or Parquet outputs from Phase 6.1 / Phase 6.2.
- **Potential Impact:** Invalidation of previous milestone sign-offs and reproducibility loss.
- **Mitigation Strategy:**
  1. **Read-Only Database Connection:** Connect to DuckDB strictly with `duckdb.connect(..., read_only=True)`.
  2. **Pre- and Post-Flight Integrity Hashing:** Verify all 22 protected asset baseline hashes before and after execution.
  3. **Distinct Output Directory:** Write all Phase 6.3 outputs exclusively to `artifacts/ranking_features/` and `reports/phase6_3/`.

---

### Risk R-07: Multicollinearity in Downstream Ranking Optimization
- **Domain:** Multi-Criteria Decision Making (MCDM)
- **Severity:** Medium
- **Likelihood:** Medium
- **Description:** Metrics like `scheduled_trips`, `unique_stops_count`, and `route_length_km` exhibit natural positive correlation. In MCDM techniques like TOPSIS or SAW, highly correlated criteria can inadvertently overweight certain physical dimensions.
- **Potential Impact:** Distorted route rankings skewed toward long, high-frequency routes at the expense of efficient local shuttles.
- **Mitigation Strategy:**
  1. **Correlation Matrix Documentation:** In `phase6_3_synthesis_report.md`, output the Pearson and Spearman correlation matrix across all 24 synthesized features.
  2. **Intensive vs Extensive Metrics:** Provide both extensive totals (`scheduled_trips`, `route_length_km`) and intensive ratios (`rides_per_trip`, `hub_stop_ratio`, `corridor_duplication_ratio`).
  3. **Normalized Feature Variants:** Provide min-max scaled columns ($\in [0, 1]$) with percentile clipping to standardize criteria ranges.

---

## 3. Risk Summary and Readiness Matrix

| Risk ID | Title | Severity | Likelihood | Residual Risk | Status |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **R-01** | Rail Ridership Asymmetry (`NaN`) | **High** | **High** | **Low** | Managed via explicit `NaN` preservation & tiered ranking |
| **R-02** | Missing AM Headways (Routes 10, 130, N5)| **Medium** | **High** | **Low** | Managed via nullable fields & complete 133-route accounting |
| **R-03** | Temporal & Target Data Leakage | **High** | **Low** | **Zero** | Eliminated via canonical date freeze (`2026-06-10`) |
| **R-04** | Spatial Co-Routing Interpretation Bias | **Medium** | **High** | **Low** | Managed via arterial definitions & regional stratification |
| **R-05** | Memory Exhaustion on 8 GB RAM | **High** | **Low** | **Zero** | Eliminated via matrix reuse & MemoryGuard ceiling |
| **R-06** | Protected Baseline Asset Mutation | **High** | **Low** | **Zero** | Eliminated via read-only connections & SHA-256 verification |
| **R-07** | Multicollinearity in Downstream MCDM | **Medium** | **Medium** | **Low** | Managed via intensive ratios & correlation matrix audit |