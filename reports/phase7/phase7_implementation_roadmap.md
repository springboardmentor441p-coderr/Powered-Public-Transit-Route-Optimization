# Phase 7 — Implementation Roadmap
## Staged Implementation, Testing Strategy, and Verification Gates

**Project:** `AI_RouteRanker — AI-Powered Public Transit Route Optimization`  
**Root Path:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** Milestone 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Phase:** 7 — Requirements Discovery and Architecture Planning  
**Status:** COMPLETE / IMPLEMENTATION ROADMAP BASELINE  

---

## 1. Executive Summary & Staged Development Philosophy

Milestone 7 transitions the verified, 44-column analytical feature master into a production-grade, explainable Multi-Criteria Decision-Making (MCDM) ranking engine.

To ensure strict safety, zero data corruption, mathematical fidelity, and seamless regression compliance, Phase 7 adheres to a **three-stage development lifecycle**:
1. **Stage 1:** Modular Implementation, Synthetic Test Fixtures, and Unit Testing.
2. **Stage 2:** Canonical Real-Data Execution, Subgroup Scoring, and Sensitivity Evaluation.
3. **Stage 3:** Independent Read-Only Verification, Cryptographic Audit, and Milestone Closure.

```
+---------------------------------------------------------------------------------------+
|  STAGE 1: Code Implementation & Synthetic Testing                                     |
|  - Implement 6 ranking modules under analytics/ranking/                                |
|  - Implement comprehensive unit test suite (tests/test_route_ranking.py)              |
|  - Test with isolated synthetic fixtures only (0 real-data mutations)                 |
|  - Stage 1 Independent Audit Gate                                                     |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|  STAGE 2: Canonical Real-Data Execution & Artifact Generation                         |
|  - Preflight checks: Verify 22 baseline hashes + 3 Phase 6.3 hashes                   |
|  - Execute canonical ranking pipeline on 133-route feature master                     |
|  - Generate artifacts/ranking_results deliverables (Parquet, JSON)                    |
|  - Full project regression test pass (Milestones 1-6)                                 |
|  - Author Stage 2 Execution Report                                                    |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|  STAGE 3: Final Independent Read-Only Verification                                    |
|  - Audit deliverables, schema, missing-data policies, and rank distributions          |
|  - Re-verify 100% cryptographic integrity of all 22 protected assets                  |
|  - Formal Milestone 7 acceptance and readiness for Module 6 (Frontend Dashboard)     |
+---------------------------------------------------------------------------------------+
```

---

## 2. Stage 1: Modular Implementation & Synthetic Testing

### 2.1 Scope & Boundaries
- **Strict Guardrail:** Stage 1 must utilize **exclusively synthetic in-memory fixtures**. It must not execute canonical real-data scoring, touch the physical databases, or overwrite production artifacts.
- **Deliverables:**
  1. Six Python modules under `analytics/ranking/`:
     - `config.py`: Extended with Phase 7 MCDM criteria, weight profiles, and deliverable paths.
     - `criteria_transformer.py`: Directional inversion, missing-value masking, validation.
     - `mcdm_engine.py`: Vectorized WSM and TOPSIS algorithms.
     - `explainer.py`: Additive contribution decomposition, waterfall attribution, natural language synthesis.
     - `sensitivity.py`: Weight perturbation analysis, Spearman correlation, rank shift tracking.
     - `ranker_service.py`: Pipeline orchestration and artifact management.
  2. Comprehensive test suite: `tests/test_route_ranking.py`.
  3. Implementation Report: `reports/phase7/phase7_stage1_implementation_report.md`.
  4. Independent Audit Report: `reports/phase7/phase7_stage1_final_audit_report.md`.

### 2.2 Synthetic Test Suite Specification (`tests/test_route_ranking.py`)
The unit test suite will implement at least **20 discrete test scenarios** covering:
- **Test Group A: Configuration & Weight Profiles**
  - All weight profiles sum to exactly $1.000000$.
  - Criteria mappings align with physical normalized columns.
- **Test Group B: Criteria Transformation & Inversion**
  - AM headway is correctly inverted ($(1.0 - x)$).
  - Normalization bounds ($[0, 1]$) are validated.
  - Zero-variance features are safely handled without exception.
- **Test Group C: WSM Mathematical Scoring**
  - Standard multi-criteria weighted sum calculation matches hand-calculated reference values.
  - Dynamic weight masking on missing criteria re-scales remaining weights to sum to $1.0$.
  - Routes with identical scores receive identical competitive ranks (`min` method).
  - Monotonicity: Increasing a benefit criterion strictly increases (or maintains) the score.
- **Test Group D: TOPSIS Scoring & Benchmark**
  - Euclidean distances $D^+, D^-$ and closeness coefficient $C \in [0, 1]$ are strictly bounded.
  - TOPSIS ranks correlate strongly with WSM on synthetic data.
- **Test Group E: Explainability & Contribution Decomposition**
  - Sum of individual criterion contributions equals the overall WSM score exactly ($\sum C_i = S$).
  - Sum of pillar scores equals the overall WSM score exactly ($\sum P_k = S$).
  - Top positive and negative drivers correctly identify max and min relative contributions.
  - Generated natural language narrative contains valid route identifiers, ranks, and driver names.
- **Test Group F: Sensitivity & Stability Analysis**
  - Weight perturbation vectors sum to $1.0$.
  - Spearman rank correlation ($\rho$) and Kendall tau ($\tau$) correctly compute rank shifts.
- **Test Group G: Subgroup & Mode Isolation**
  - Bus Priority mode evaluates exactly the bus subset.
  - Unified Supply mode evaluates all routes.
  - Heavy rail missing demand values produce clean `NaN` without pipeline termination.

---

## 3. Stage 2: Canonical Real-Data Execution & Artifact Generation

### 3.1 Preflight Verification
Before executing canonical ranking on real data:
1. Verify SHA-256 hashes of all 22 protected baseline assets against approved references.
2. Verify SHA-256 hashes of all 3 Phase 6.3 canonical artifacts.
3. Verify host memory ($> 600\text{ MB}$ available).
4. Verify output directory structure (`artifacts/ranking_results/`).

### 3.2 Canonical Pipeline Execution
Execute master orchestration via `ranker_service.py` on the verified feature master:
1. **Primary Run (Bus Comprehensive Priority):**
   - Population: 125 bus routes.
   - Profile: Balanced Operational Priority (Profile A).
   - Generates primary scores, ranks, pillar breakdowns, and explanations.
2. **Secondary Run (Unified Operational Supply):**
   - Population: 133 routes (125 bus + 8 rail).
   - Evaluates shared mode-agnostic operational supply.
3. **Tertiary Run (Rail Operational Priority):**
   - Population: 8 rail routes.
4. **Benchmark Run (TOPSIS Cross-Validation):**
   - Generates TOPSIS scores and Spearman rank correlation with WSM.
5. **Sensitivity Perturbation Run:**
   - Evaluates $\pm 10\%$ and $\pm 20\%$ weight perturbations across all criteria.

### 3.3 Deliverable Generation Inventory
Write canonical deliverables to `artifacts/ranking_results/`:
1. `route_rankings_master.parquet` (~$85\text{ KB}$): Primary master table with scores, ranks, pillars, contributions, and TOPSIS benchmarks.
2. `route_ranking_explanations.json` (~$150\text{ KB}$): Complete nested JSON explanation dictionary for all 133 routes.
3. `ranking_sensitivity_analysis.parquet` (~$30\text{ KB}$): Perturbation stability metrics and rank shift tables.
4. `phase7_metadata.json` (~$4\text{ KB}$): Execution metadata, parameter logs, input/output cryptographic hashes.

### 3.4 Full Project Regression Test Run
Run complete project test discovery across all milestones:
- `tests/test_clustering.py` (Phase 6.1)
- `tests/test_route_clustering.py` (Phase 6.2)
- `tests/test_route_ranker_features.py` (Phase 6.3)
- `tests/test_route_ranking.py` (Phase 7)
- Target: **100% pass rate with zero regressions**.

---

## 4. Stage 3: Final Independent Read-Only Verification

### 4.1 Verification Mandates
1. **Physical Parquet Inspection:** Confirm row counts, column counts, data types, primary key uniqueness, and absence of null scores.
2. **Explanation JSON Schema Audit:** Validate JSON syntax, key existence, top driver formatting, and narrative readability.
3. **Mathematical Invariant Verification:**
   - Verify $\sum_{i} C_{r, i} = S(r)$ for all routes.
   - Verify all scores $S(r) \in [0.0, 1.0]$.
   - Verify rank ordering ($S(r_{(k)}) \ge S(r_{(k+1)})$).
4. **Protected Baseline Cryptographic Audit:** Confirm all 22 protected baseline assets remain 100% bit-for-bit identical.
5. **Deliverable Reporting:** Author `reports/phase7/phase7_stage2_final_verification_report.md`.

---

## 5. Summary of Verification Gates

| Gate ID | Stage | Criteria for Passing Gate | Enforcement Mechanism |
| :---: | :---: | :--- | :--- |
| **GATE-7.1** | Stage 1 | All 6 modules implemented; unit test suite passes 100% ($> 20$ tests); zero real-data touched. | Automated `pytest` on synthetic fixtures; Independent Audit Report. |
| **GATE-7.2** | Stage 2 Preflight | All 22 baseline hashes match; Phase 6.3 hashes match; RAM $> 600\text{ MB}$. | Cryptographic SHA-256 preflight script. |
| **GATE-7.3** | Stage 2 Execution | Canonical Parquet and JSON deliverables generated; all 133 routes accounted for; full regression passes. | Automated pipeline run + full `pytest` regression suite. |
| **GATE-7.4** | Stage 3 Audit | Additive contribution invariants hold; TOPSIS correlation verified; 22 baseline hashes remain identical. | Independent read-only verification script and audit report. |

---

## 6. Conclusion

This staged roadmap enforces rigorous quality control, reproducibility, and protection of baseline assets. We proceed to identify and mitigate risks in `reports/phase7/phase7_risk_register.md`.
