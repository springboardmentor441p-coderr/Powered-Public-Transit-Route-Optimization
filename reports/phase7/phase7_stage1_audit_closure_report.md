# Phase 7 Stage 1 — Audit Closure Report
## Narrow Read-Only Verification and Pre-Execution Alignment

**Project:** `AI_RouteRanker — AI-Powered Public Transit Route Optimization`  
**Root Path:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** Milestone 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Phase:** 7 — Multi-Criteria Route Ranking Engine  
**Stage:** 1 — Implementation, Synthetic Testing, and Audit Closure  
**Audit Closure Type:** STRICT READ-ONLY VERIFICATION  
**Closure Timestamp:** 2026-11-25T16:50:00+05:30  
**Final Stage 2 Readiness Verdict:** **READY FOR CANONICAL REAL-DATA EXECUTION**

---

## 1. Executive Summary

This Audit Closure Report concludes Phase 7 Stage 1 by resolving four specific methodological items raised during the independent audit:
1. **Bus Missing-Criterion Verification:** Verified exact handling of Routes 10, 130, and N5 under Track 1, confirming dynamic weight redistribution, coverage rule enforcement, and reporting transparency.
2. **Rail and Unified Profile Verification:** Documented exact criteria, weights, directions, and 100% weight totals for Track 2 (Rail Priority) and Track 3 (Unified Supply), verifying zero demand criterion leakage.
3. **TOPSIS Comparability Decision:** Formally classified TOPSIS as an exploratory secondary benchmark and defined the restricted complete-case population ($N = 122$ for bus) for meaningful distance metric comparisons.
4. **Sensitivity Track Isolation:** Confirmed that sensitivity analysis executes strictly within each isolated track and profile, preserving valid weight sums across perturbations.

---

## 2. Item 1: Bus Missing-Criterion Verification (Routes 10, 130, N5)

### 2.1 Route Population & Status
- **Total Bus Population (Track 1):** Exactly **125 canonical bus routes** (`is_rail == False`).
- **Complete 7-Criteria Routes:** Exactly **122 bus routes** possess complete empirical data across all 7 criteria.
- **Specialized 6-Criteria Routes:** Exactly **3 bus routes** (`10`, `130`, `N5`) possess valid empirical data for 6 criteria, with `am_headway_min_norm` strictly `NaN`.
  - *Route 10 (Obama Presidential Center / Museum of Science & Industry Express):* Operates exactly 1 AM trip (departure interval undefined).
  - *Route 130 (Museum Campus):* Operates exclusively after 09:27 AM (outside 07:00–09:00 AM peak).
  - *Route N5 (South Shore Night Bus):* Overnight owl service terminating prior to 07:00 AM peak.
- **Reporting Clarity Rule:** All Stage 1 and Stage 2 reports must transparently document that **122 bus routes are evaluated across 7 criteria** and **3 bus routes are evaluated across 6 criteria with AM headway dynamically masked**.

### 2.2 Effective Weight Recalculation for Routes 10, 130, N5
Under Profile A (Balanced Priority), the base weight of `am_headway_min_norm` is $0.10$ ($10.0\%$).
When headway is `NaN`:
1. **Valid Weight Sum:**
   $$W_{\text{valid}} = \sum_{j \in \text{Valid}(r)} w_j = 1.00 - 0.10 = 0.90\ (90.0\%)$$
2. **Coverage Threshold Check:**
   $$\text{Coverage Ratio} = \frac{0.90}{1.00} = 90.0\% \ge \text{MIN\_VALID\_WEIGHT\_THRESHOLD}\ (50.0\%)$$
   The coverage check passes unconditionally. The routes are confirmed valid and eligible for ranking.
3. **Effective Weight Scaling ($w_i' = w_i / 0.90$):**
   - `forecasted_daily_demand_norm`: $0.1500 \rightarrow \mathbf{0.1667}$ ($16.67\%$)
   - `load_intensity_factor_norm`: $0.2000 \rightarrow \mathbf{0.2222}$ ($22.22\%$)
   - `scheduled_trips_norm`: $0.1000 \rightarrow \mathbf{0.1111}$ ($11.11\%$)
   - `service_span_hours_norm`: $0.0500 \rightarrow \mathbf{0.0556}$ ($5.56\%$)
   - `am_headway_min_norm`: $0.1000 \rightarrow \mathbf{0.0000}$ (masked out)
   - `hub_stop_ratio_norm`: $0.2000 \rightarrow \mathbf{0.2222}$ ($22.22\%$)
   - `corridor_duplication_index_norm`: $0.2000 \rightarrow \mathbf{0.2222}$ ($22.22\%$)
   - **Effective Weight Sum:** $0.1667 + 0.2222 + 0.1111 + 0.0556 + 0.0 + 0.2222 + 0.2222 = \mathbf{1.000000}$ ($100.0\%$).

### 2.3 Route-Level Synthetic Demonstration
To prove that scores and ranks are calculated deterministically without synthetic imputation, a synthetic demonstration was executed on the three specialized routes alongside a reference trunk route (Route 79):

| Route ID | Route Name | Valid Criteria Count | Coverage Valid ($\ge 50\%$) | Effective Weight Sum | WSM Score | WSM Rank | TOPSIS Score |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `79_ref` | 79th (Reference Trunk) | 7 / 7 | True ($100\%$) | $1.000000$ | **0.6270** | **#1** | $0.8149$ |
| `10` | Museum of Science Express | 6 / 7 | True ($90\%$) | $1.000000$ | **0.2350** | **#2** | $0.1780$ |
| `130` | Museum Campus | 6 / 7 | True ($90\%$) | $1.000000$ | **0.2167** | **#3** | $0.1591$ |
| `N5` | South Shore Night Bus | 6 / 7 | True ($90\%$) | $1.000000$ | **0.1989** | **#4** | $0.0971$ |

**Conclusion:** All three routes receive fully valid, bounded, and explainable scores without zero-imputation or arbitrary penalties.

---

## 3. Item 2: Rail and Unified Profile Verification

The exact criteria, weights, directions, and total weight sums for Tracks 2 and 3 were audited in `RankerConfig`:

### 3.1 Track 2: Heavy Rail Operational Priority (8 Rail Routes)
- **Target Population:** Exactly 8 heavy rail routes (`Red`, `Blue`, `Brn`, `G`, `Org`, `P`, `Pink`, `Y`).
- **Pillars Evaluated:** Service Provision (80%) and Corridor Structure (20%).

| Criterion Feature Name | Operational Meaning | Direction | Weight |
| :--- | :--- | :---: | :---: |
| `scheduled_trips_norm` | Daily train run frequency | Benefit ($\uparrow$) | **30.0%** |
| `service_span_hours_norm` | 24-hour / extended operating span | Benefit ($\uparrow$) | **20.0%** |
| `am_headway_min_norm` | Peak AM headway ($1.0 - x$) | Cost $\rightarrow$ Benefit ($\uparrow$) | **30.0%** |
| `corridor_duplication_index_norm` | Alignment sharing across 'L' lines | Benefit ($\uparrow$) | **20.0%** |
| **Total Weight Sum** | | | **100.0%** |

- **Passenger Demand Verification:** Exactly **0.0%** demand criteria. No farebox ridership or bus-derived demand values enter rail scoring.

### 3.2 Track 3: Unified Operational Supply (133 Routes)
- **Target Population:** All 133 CTA routes (125 bus + 8 rail).
- **Evaluation Purpose:** Level-playing-field comparison of operational service provision and corridor geometry across both modes.

| Criterion Feature Name | Operational Meaning | Direction | Weight |
| :--- | :--- | :---: | :---: |
| `scheduled_trips_norm` | Total daily trips provided | Benefit ($\uparrow$) | **35.0%** |
| `service_span_hours_norm` | Daily operating span in hours | Benefit ($\uparrow$) | **20.0%** |
| `am_headway_min_norm` | Peak AM frequency ($1.0 - x$) | Cost $\rightarrow$ Benefit ($\uparrow$) | **25.0%** |
| `corridor_duplication_index_norm` | Co-routing duplication index | Benefit ($\uparrow$) | **20.0%** |
| **Total Weight Sum** | | | **100.0%** |

- **Demand Exclusion Verification:** Exactly **0.0%** demand criteria. Bus demand values are strictly prevented from entering the unified model, guaranteeing that rail lines are not penalized for the structural absence of bus farebox telemetry.

---

## 4. Item 3: TOPSIS Comparability Decision

### 4.1 Methodological Analysis
In `MCDMEngine.compute_topsis()`, Euclidean separation distance $D_r^+$ is evaluated over the active valid criteria subset $V(r)$:
$$D_r^+ = \sqrt{\sum_{j \in V(r)} (w_{r, j}' X_{r, j} - w_{r, j}' v_j^+)^2}$$
When routes have different dimensionality (e.g. 7 criteria for standard buses vs 6 criteria for specialized routes), the summation operates across different Euclidean dimensions. While the relative closeness ratio $C_r = \frac{D^-}{D^+ + D^-}$ normalizes scale, metric comparisons across varying dimensional spaces are non-isometric.

### 4.2 Formal Project Methodology Decision
1. **Authoritative Role:** **Hierarchical WSM is confirmed as the sole primary production engine.** WSM scores and ranks are authoritative across all 125 bus routes because linear dynamic weight masking is mathematically exact.
2. **Exploratory Role:** **TOPSIS is formally classified as an exploratory secondary benchmark.** TOPSIS scores will be generated as secondary reference columns (`topsis_score`, `topsis_rank`) but will never override WSM ranks.
3. **Restricted Comparison Population for Validation Metrics:**
   - In Track 1 (Bus Priority), automated validation metrics (Spearman rank correlation $\rho$, Top-10 overlap, Top-20 overlap between WSM and TOPSIS) will be evaluated on the **comparable common-criteria population** ($N = 122$ bus routes with complete 7 criteria), ensuring mathematically defensible metric benchmarking.
   - Routes 10, 130, and N5 will receive exploratory TOPSIS scores, but will be noted as dimensionally adjusted in run metadata.
   - In Track 2 (Rail Priority), all 8 rail lines possess complete 4-criteria data, making rail TOPSIS 100% comparable across all 8 lines.

---

## 5. Item 4: Sensitivity Track & Profile Isolation

The sensitivity analysis implementation in `analytics/ranking/ranker_service.py` was inspected:

```python
# Population is filtered FIRST before sensitivity is invoked:
track_df = self.select_track_population(df, track)
weights = self.get_track_weights(track, profile_name, custom_weights)
matrix, valid_mask, criteria_list, coverage_mask = self.transformer.transform(track_df, weights)
# Sensitivity runs strictly within that track's isolated matrix:
sens_scenarios, sens_shifts, stability = RankingSensitivityAnalyzer.evaluate_sensitivity(...)
```

### Verification Findings:
1. **Track Isolation:** Sensitivity analysis is executed **strictly within the active track and profile**. Bus Priority evaluates 28 scenarios across 7 bus criteria; Rail Priority evaluates 16 scenarios across 4 rail criteria. There is zero cross-track contamination.
2. **Weight Sum Preservation:** Under every perturbation delta ($\pm 10\%, \pm 20\%$), the target criterion weight is shifted and remaining weights are proportionally rescaled, verifying that $\sum w_{\text{perturbed}} = 1.000000$ across all scenarios.
3. **Missing-Criterion Consistency:** During sensitivity perturbations, routes missing criteria (e.g. 10, 130, N5) continue to have missing criteria masked and valid weights dynamically normalized to $1.0$.

---

## 6. Pre-Execution Data Contract Alignment Note

### Finding: Feature Master Column Naming Alignment
- In `RankerConfig.PROFILE_A_WEIGHTS`, the corridor criterion was defined with the key `"corridor_duplication_index_norm"`.
- Inspection of the canonical Phase 6.3 feature master (`artifacts/ranking_features/route_ranker_feature_master.parquet`) confirmed that the physical column is named `corridor_duplication_index` (Column 28, values $\in [0.0264, 0.8658]$, which was already synthesized as a normalized index in $[0, 1]$ in Phase 6.3).
- **Remediation for Stage 2:** In Stage 2 canonical orchestration, `CriteriaTransformer.transform()` should seamlessly resolve `corridor_duplication_index_norm` to read from `corridor_duplication_index` if the `_norm` alias is not physically present in the DataFrame. This ensures 100% data contract compatibility without mutating the accepted 44-column feature master.

---

## 7. Final Stage 2 Readiness Verdict

| Audit Closure Item | Verification Standard | Finding | Status |
| :---: | :--- | :--- | :---: |
| **Item 1** | Bus Missing-Criterion Handling | 125 total bus; 122 with 7 crits, 3 with 6 crits; $90\% \ge 50\%$ coverage; valid scores. | **VERIFIED** |
| **Item 2** | Rail & Unified Profile Weights | Rail profile sums to 100%; Unified profile sums to 100%; zero demand leakage. | **VERIFIED** |
| **Item 3** | TOPSIS Comparability Decision | TOPSIS classified as exploratory; validation metrics restricted to complete cases ($N=122$). | **VERIFIED** |
| **Item 4** | Sensitivity Track Isolation | Runs strictly within active track/profile; perturbations sum to 1.000000. | **VERIFIED** |
| **Integrity** | Baseline Cryptographic Assets | 23 / 23 protected baseline assets verified 100% bit-for-bit identical. | **VERIFIED** |

### Final Verdict: **READY FOR CANONICAL REAL-DATA EXECUTION**

All four audit closure items are verified. The implementation is mathematically sound, policy-compliant, and fully documented.

Awaiting explicit user authorization before initiating **Phase 7 Stage 2: Canonical Real-Data Ranking and Verification**.
