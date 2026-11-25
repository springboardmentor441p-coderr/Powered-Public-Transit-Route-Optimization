# Phase 7 — Risk Register
## Comprehensive Risk Assessment and Mitigation Architecture

**Project:** `AI_RouteRanker — AI-Powered Public Transit Route Optimization`  
**Root Path:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** Milestone 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Phase:** 7 — Requirements Discovery and Architecture Planning  
**Status:** COMPLETE / RISK MANAGEMENT BASELINE  

---

## 1. Executive Summary

The Multi-Criteria Route Ranking Engine (Milestone 7) integrates complex geospatial, temporal, operational, and machine learning signals to produce actionable transit evaluations.

This Risk Register identifies **10 critical technical, mathematical, data integrity, operational, and policy risks** associated with Phase 7. For each risk, concrete prevention strategies, architectural safeguards, and monitoring mechanisms are established.

---

## 2. Risk Matrix & Severity Summary

| Risk ID | Category | Risk Description | Pre-Likelihood | Pre-Impact | Pre-Risk | Post-Risk |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| **R-01** | Data / Method | Rail demand absence causing scoring bias or crash | High | High | **HIGH** | **LOW** |
| **R-02** | Data / Method | Missing AM headways on specialized routes (10, 130, N5) | Medium | High | **HIGH** | **LOW** |
| **R-03** | Mathematical | Multicollinear redundancy inflating demand signals | High | High | **HIGH** | **LOW** |
| **R-04** | Data / Feature | Zero-variance constant features acting as dead weights | High | Medium | **MEDIUM** | **LOW** |
| **R-05** | Policy / Ethics| Misinterpreting ranking as automated service cut triggers | Medium | Critical | **HIGH** | **LOW** |
| **R-06** | Policy / Weight| Subjectivity in criteria weights and stakeholder bias | High | Medium | **MEDIUM** | **LOW** |
| **R-07** | Mathematical | Rank reversal or instability across alternative MCDM methods| Medium | Medium | **MEDIUM** | **LOW** |
| **R-08** | Environment | Host memory spikes during sensitivity perturbation grids | Low | High | **MEDIUM** | **LOW** |
| **R-09** | Asset Integrity| Accidental mutation of protected baseline assets | Low | Critical | **MEDIUM** | **NEGLIGIBLE** |
| **R-10** | Integration | Schema mismatch between Python outputs and React UI | Medium | Medium | **MEDIUM** | **LOW** |

---

## 3. Detailed Risk Analysis & Mitigation Strategies

### R-01: Rail Demand Absence Causing Scoring Bias or Pipeline Failure
- **Description:** All 8 heavy rail routes (`Red`, `Blue`, `Brn`, `G`, `Org`, `P`, `Pink`, `Y`) have `NaN` for all 4 demand columns (`historical_mean_daily_rides`, `forecasted_daily_demand`, `rides_per_trip`, `load_intensity_factor`) because rail ridership is collected at station turnstiles rather than onboard fareboxes. If evaluated in a single unsegmented table with demand criteria, rail routes would either cause mathematical exceptions or be unfairly penalized as having zero ridership.
- **Mitigation Strategy:**
  1. Implement **Dual-Track Ranking Architecture**:
     - *Track 1 (Bus Priority):* Evaluates the 125 bus routes with full demand and operational criteria.
     - *Track 2 (Unified Supply):* Evaluates all 133 routes using mode-agnostic operational supply criteria (`scheduled_trips`, `service_span_hours`, `am_headway_min`, `corridor_duplication_index`).
     - *Track 3 (Rail Priority):* Evaluates the 8 rail lines independently.
  2. Implement strict validity masks in `criteria_transformer.py` to prevent `NaN` propagation.
- **Monitoring & Verification:** Unit test `test_rail_isolation()` confirms rail routes never receive imputed zero ridership scores.

---

### R-02: Missing AM Headways on Specialized Routes (10, 130, N5)
- **Description:** Routes 10, 130, and N5 lack standard AM peak intervals (Route 130 starts after 09:00 AM, Route N5 ends before 07:00 AM, Route 10 has only 1 trip). Imputing zero headway would falsely reward them with infinite frequency; imputing large numbers (e.g., 999 min) would artificially penalize them.
- **Mitigation Strategy:**
  1. Implement **Dynamic Criterion Weight Masking**:
     $$w_i'(r) = \frac{w_i}{\sum_{j \in \text{Valid}(r)} w_j}$$
  2. For routes missing AM headway, the headway weight is redistributed proportionally across the remaining valid criteria (Demand, Trips, Span, Hubs, Duplication).
- **Monitoring & Verification:** Unit test `test_dynamic_weight_renormalization()` verifies weights re-scale to exactly $1.000000$ and specialized routes are scored fairly without `NaN` scores.

---

### R-03: Multicollinear Redundancy Inflating Demand Signals
- **Description:** Statistical correlation analysis revealed extreme correlation between `historical_mean_daily_rides` and `forecasted_daily_demand` ($r = 0.9954$), as well as high correlation between corridor overlap metrics and `corridor_duplication_index` ($r > 0.90$). Including all of these features simultaneously would artificially double-count demand and corridor overlap.
- **Mitigation Strategy:**
  1. Strictly enforce **Feature Orthogonality**:
     - Select `forecasted_daily_demand_norm` as the sole passenger volume criterion (excluding historical demand).
     - Select `corridor_duplication_index_norm` as the sole corridor co-routing criterion (excluding raw overlap columns).
     - Select `load_intensity_factor_norm` to capture capacity pressure per kilometer ($r = 0.3278$ with demand).
- **Monitoring & Verification:** Automated check confirms no pair of active criteria in the ranking model has $|r| \ge 0.70$.

---

### R-04: Zero-Variance Constant Features Acting as Dead Weights
- **Description:** Canonical feature master inspection revealed that `spatial_equity_indicator` is identically $1.000$ (std $= 0.000$) and `hub_weighted_importance` is identically $0.000$ (std $= 0.000$) across all 133 routes. Assigning active criteria weights to these features would add a constant scalar offset to every route, reducing the discriminatory power of the remaining valid criteria.
- **Mitigation Strategy:**
  1. Explicitly assign **$0.00$ weight** to `spatial_equity_indicator` and `hub_weighted_importance`.
  2. Use `hub_stop_ratio_norm` (which has healthy empirical variance, range $0.0$ to $0.6888$) as the sole hub connectivity criterion.
- **Monitoring & Verification:** Weight validation test asserts weights for constant features are strictly $0.0$.

---

### R-05: Misinterpreting Ranking as Automated Service Cut Triggers
- **Description:** Stakeholders or external reviewers could misinterpret route rankings as algorithmic recommendations to cancel or eliminate low-ranked routes. In reality, low-volume routes often serve vulnerable transit-dependent populations under civil rights (Title VI) mandates.
- **Mitigation Strategy:**
  1. Strictly define the engine's purpose as **"Operational Review & Planning Priority"**, not service reduction.
  2. In the explainability engine (`explainer.py`), generate balanced narratives highlighting both strengths and operational context.
  3. Provide a dedicated **"Core Network Essentiality"** persona that rewards standalone coverage lifelines.
  4. Include clear disclaimers in all reports, API responses, and frontend UI cards.
- **Monitoring & Verification:** Review of generated narratives in `route_ranking_explanations.json` to ensure zero pejorative or service-cutting language.

---

### R-06: Subjectivity in Criteria Weights and Stakeholder Bias
- **Description:** Any single fixed weighting scheme represents a subjective trade-off that may not satisfy all planning perspectives (e.g., operations vs finance vs equity).
- **Mitigation Strategy:**
  1. Establish **Four Transparent Personas**:
     - *Profile A: Balanced Operational Priority (Default)*
     - *Profile B: Overcrowding & Capacity Relief*
     - *Profile C: Corridor Restructuring & Efficiency*
     - *Profile D: Network Essentiality & Coverage*
  2. Implement an automated **Sensitivity Analysis Engine** (`sensitivity.py`) that executes systematic $\pm 10\%$ and $\pm 20\%$ perturbations across all criteria and calculates rank volatility.
- **Monitoring & Verification:** Sensitivity analysis table recorded in `artifacts/ranking_results/ranking_sensitivity_analysis.parquet`.

---

### R-07: Rank Reversal or Instability Across Alternative MCDM Methods
- **Description:** Linear WSM and distance-based TOPSIS can yield divergent rankings, causing stakeholder confusion if rankings fluctuate dramatically between formulations.
- **Mitigation Strategy:**
  1. Designate **Hierarchical WSM as the Authoritative Production Engine** due to its mathematical immunity to rank reversal and 100% additive explainability.
  2. Use **TOPSIS strictly as a Secondary Benchmark**.
  3. Compute Spearman's rank correlation ($\rho$) between WSM and TOPSIS; require $\rho \ge 0.85$ to validate structural consistency.
- **Monitoring & Verification:** Cross-method correlation metric logged in run metadata.

---

### R-08: Host Memory Spikes During Sensitivity Perturbation Grids
- **Description:** Running multidimensional weight perturbation grids across 133 routes could cause memory spikes on memory-constrained systems (8 GB RAM Windows 11 host).
- **Mitigation Strategy:**
  1. Utilize purely vectorized NumPy 2D array operations instead of iterative Pandas object loops.
  2. Pre-allocate rank arrays and run sensitivity sequentially per criterion.
  3. Enforce the strict $600\text{ MB}$ memory abort threshold.
- **Monitoring & Verification:** Memory tracking during preflight and post-execution.

---

### R-09: Accidental Mutation of Protected Baseline Assets
- **Description:** Milestone 5 Random Forest models, Phase 6.1/6.2 clustering tables, and Phase 6.3 feature master must remain strictly untouched.
- **Mitigation Strategy:**
  1. Enforce strict read-only access flags on all input files.
  2. Route all output files exclusively to a new dedicated directory: `artifacts/ranking_results/`.
  3. Run automated SHA-256 baseline verification before Stage 2 execution and during final verification.
- **Monitoring & Verification:** 100% cryptographic match required across all 22 protected assets.

---

### R-10: Schema Mismatch Between Python Outputs and React UI
- **Description:** If the Parquet columns or JSON explanation structure drift from the frontend TypeScript interfaces, the React dashboard will encounter rendering errors.
- **Mitigation Strategy:**
  1. Document explicit TypeScript interface contracts in the architecture plan.
  2. Include schema validation assertions in the unit test suite (`test_explanation_json_schema`).
  3. Produce both flat tabular Parquet (for tabular filtering) and nested JSON (for component drilldown).
- **Monitoring & Verification:** Automated JSON schema validation in `tests/test_route_ranking.py`.

---

## 4. Conclusion & Governance Sign-Off

All 10 identified risks have been addressed with concrete architectural safeguards. Milestone 7 architecture planning is fully insulated against data corruption, mathematical bias, and operational instability. We are fully prepared to begin Stage 1 implementation upon user authorization.
