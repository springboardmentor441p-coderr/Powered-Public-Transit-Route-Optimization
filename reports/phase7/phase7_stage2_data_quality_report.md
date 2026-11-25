# AI_RouteRanker — Phase 7 Stage 2: Data Quality & Integrity Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Stage:** 2 — Canonical Execution & Empirical Verification  
**Evaluation Date:** 2026-11-25T16:56:55+05:30  
**Quality Status:** EXCELLENT (100% INVARIANTS & INTEGRITY VERIFIED)

---

## 1. Scope and Objective

This report provides the canonical data quality audit for the Multi-Criteria Decision-Making (MCDM) route ranking results generated in Phase 7 Stage 2. It evaluates input data integrity, missing-value management, mathematical invariants, score bounding, and baseline asset preservation.

---

## 2. Input Feature Master Integrity

The input artifact `artifacts/ranking_features/route_ranker_feature_master.parquet` was evaluated prior to ranking execution:

- **Row Count:** Exactly 133 rows (representing 100% of canonical CTA transit routes).
- **Column Count:** Exactly 44 columns (24 base features + 3 composite indicators + 16 normalized criteria + 1 cluster label).
- **Primary Key:** `route_id` has 133 distinct values; zero duplicate IDs, zero null IDs.
- **Route Type Distribution:** 125 bus routes (`route_type = 3`, `is_rail = False`) and 8 rail routes (`route_type = 1`, `is_rail = True`).
- **Cryptographic Hash:** SHA-256 is verified as `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85`, confirming complete bitwise preservation from the Phase 6.3 acceptance gate.

---

## 3. Missing Value Analysis & Audit Reconciliation

### 3.1 Rail Demand Column Isolation
By project policy established in Phase 6.3, rail demand predictions were not trained due to historical GTFS/ridership source aggregation at station turnstiles rather than line IDs.
- **Observed Nulls:** All 8 rail rows contain `NaN` across the 4 demand-related fields (`historical_mean_daily_rides`, `forecasted_daily_demand`, `rides_per_trip`, `load_intensity_factor`) and their normalized equivalents.
- **Quality Handling:** In Track 2 (Heavy Rail Operational Priority) and Track 3 (Unified Operational Supply), the demand pillar is assigned an exact weight of $0.0\%$. Demand criteria are omitted from criteria transformation for these tracks. Consequently, no artificial imputations or distortions were introduced.

### 3.2 Bus Headway Sparsity Management
- **Observed Nulls:** Exactly three bus routes (Routes 10, 130, and N5) have `NaN` for `am_headway_min` and `am_headway_min_norm`.
  - Route 10 (Museum of Science & Industry) operates as a seasonal/special-event express.
  - Route 130 (Museum Campus) operates midday/weekend museum service with no AM peak schedule.
  - Route N5 (South Shore Night Bus) operates overnight owl service exclusively outside the AM peak window ($06:00 - 09:00$).
- **Dynamic Re-weighting Verification:**
  - Base Profile A assigns $10.0\%$ weight to `am_headway_min_norm`.
  - For these three routes, the missing criterion was dynamically masked, leaving 6 valid criteria with a cumulative weight of $0.9000$ ($90.0\%$), well above the mandatory $50.0\%$ minimum valid-weight coverage threshold.
  - Effective weights were dynamically normalized by dividing by $0.9000$, ensuring $\sum w_i^{\text{eff}} = 1.0000$.
  - All three routes generated mathematically sound, valid WSM scores and ranks.

---

## 4. Mathematical Invariant Verification

All ranking outputs in `artifacts/ranking_results/route_rankings_master.parquet` were audited against core mathematical invariants across all 266 route-track evaluations:

### Invariant 1: Criterion Contribution Additivity
The sum of individual criterion contributions must equal the overall composite score:
$$\sum_{i=1}^{m} C_i = S$$

- **Observed Discrepancy:**
  - Maximum absolute difference: $\max |\sum C_i - S| = 2.00 \times 10^{-6}$.
  - Tolerated epsilon: $\epsilon = 1.0 \times 10^{-5}$.
  - **Verdict: PASS (100% compliant across 266 records)**.

### Invariant 2: Pillar Score Additivity
The sum of the four thematic pillar scores must equal the overall composite score:
$$\sum_{k=1}^{4} P_k = S$$

- **Observed Discrepancy:**
  - Maximum absolute difference: $\max |\sum P_k - S| = 2.00 \times 10^{-6}$.
  - Tolerated epsilon: $\epsilon = 1.0 \times 10^{-5}$.
  - **Verdict: PASS (100% compliant across 266 records)**.

### Invariant 3: Score Range Bounds
Every composite score must remain bounded in the unit interval $[0.0, 1.0]$:
$$0.0 \le S \le 1.0$$

- **Track 1 (Bus Priority):** Min = $0.0824$, Max = $0.6363$ — **PASS**.
- **Track 2 (Rail Priority):** Min = $0.4588$, Max = $0.8458$ — **PASS**.
- **Track 3 (Unified Supply):** Min = $0.1117$, Max = $0.8458$ — **PASS**.
- **Verdict: PASS (100% within valid range)**.

### Invariant 4: Monotonic Dense Ranking
Within each track, ranks must span strictly from $1$ to $N$ with zero gaps:
- **Track 1:** Ranks $1 \dots 125$ present, unique, and strictly monotonically ordered by score.
- **Track 2:** Ranks $1 \dots 8$ present, unique, and strictly monotonically ordered by score.
- **Track 3:** Ranks $1 \dots 133$ present, unique, and strictly monotonically ordered by score.
- **Verdict: PASS (100% compliant)**.

---

## 5. Protected Baseline Assets Verification

All 23 authoritative baseline assets established in Phase 7 Stage 1 across previous project milestones, clustering modules, trained Random Forest models, and the canonical Phase 6.3 feature master were verified via independent SHA-256 computation before and after execution:

| # | Protected Baseline Asset Path | Baseline SHA-256 Digest | Post-Execution SHA-256 Digest | Verification Status |
| :-: | :--- | :--- | :--- | :---: |
| 1 | `data/processed/features/model_ready_features.parquet` | `30980434303f7d8a96b55338572a245c479bacd3abb581cd9d7bf2b417e8b95f` | `30980434303f7d8a96b55338572a245c479bacd3abb581cd9d7bf2b417e8b95f` | **MATCH (100%)** |
| 2 | `artifacts/random_forest/tier1_random_forest.joblib` | `559936f8e200d67f29d56f6c40ad1748b15d012b25ca44ed6d1ce0d1120db3c9` | `559936f8e200d67f29d56f6c40ad1748b15d012b25ca44ed6d1ce0d1120db3c9` | **MATCH (100%)** |
| 3 | `artifacts/random_forest/tier2_random_forest.joblib` | `d688a9e10b120f4998e8bff6dfd8ffca94c771db5db1947b0f71cd6360af9b2e` | `d688a9e10b120f4998e8bff6dfd8ffca94c771db5db1947b0f71cd6360af9b2e` | **MATCH (100%)** |
| 4 | `artifacts/random_forest/tier1_random_forest_tuned.joblib` | `d73b79016012496809f9bc2dc3e05db686d5894f02a55d859a42f91052af1508` | `d73b79016012496809f9bc2dc3e05db686d5894f02a55d859a42f91052af1508` | **MATCH (100%)** |
| 5 | `artifacts/random_forest/tier2_random_forest_tuned.joblib` | `dafa999d181502d35098944c97009458f7f79bbefa3be0542e39b41b07ab40b5` | `dafa999d181502d35098944c97009458f7f79bbefa3be0542e39b41b07ab40b5` | **MATCH (100%)** |
| 6 | `data/processed/ai_routeranker.duckdb` | `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209` | `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209` | **MATCH (100%)** |
| 7 | `analytics/clustering/spatial_projection.py` | `64db44fec6ae647b3acbfa0049cab09281a5048a540e2087fbbb3c95b7ac16a1` | `64db44fec6ae647b3acbfa0049cab09281a5048a540e2087fbbb3c95b7ac16a1` | **MATCH (100%)** |
| 8 | `analytics/clustering/demand_aggregator.py` | `a05ccc2bcb66ede50c99b15d522c2a21f6a49424c5cd0afc3a737a895fbde261` | `a05ccc2bcb66ede50c99b15d522c2a21f6a49424c5cd0afc3a737a895fbde261` | **MATCH (100%)** |
| 9 | `analytics/clustering/stop_clustering.py` | `e9d3c025b0ecb0cc27286aeff2936e1857259bba759173cd7a402eec76656456` | `e9d3c025b0ecb0cc27286aeff2936e1857259bba759173cd7a402eec76656456` | **MATCH (100%)** |
| 10 | `analytics/clustering/evaluator.py` | `ec0d5cbe9010f07753de74e4ff5350462a3e9b3881ba44a8e77b6d6b5c82d60e` | `ec0d5cbe9010f07753de74e4ff5350462a3e9b3881ba44a8e77b6d6b5c82d60e` | **MATCH (100%)** |
| 11 | `tests/test_clustering.py` | `a778f66db6c5035d56f67b52794183968e1576a224d9b1d53ba8a63761327bc9` | `a778f66db6c5035d56f67b52794183968e1576a224d9b1d53ba8a63761327bc9` | **MATCH (100%)** |
| 12 | `artifacts/clustering/stop_level_feature_master.parquet` | `1c78779eaa99a9d72e729efd1a6127670df2336d663065056cabbfdf1dbd32b5` | `1c78779eaa99a9d72e729efd1a6127670df2336d663065056cabbfdf1dbd32b5` | **MATCH (100%)** |
| 13 | `artifacts/clustering/spatial_dbscan_assignments.parquet` | `3c7d40bcca545e142a69afd8b084166a372069a3f645360f76812fcdf9bab674` | `3c7d40bcca545e142a69afd8b084166a372069a3f645360f76812fcdf9bab674` | **MATCH (100%)** |
| 14 | `artifacts/clustering/peripheral_and_noise_stops.parquet` | `1b9ec0cbac8bbbe88dccac368c439e10aef9c443f1321d2605ea345473f3e751` | `1b9ec0cbac8bbbe88dccac368c439e10aef9c443f1321d2605ea345473f3e751` | **MATCH (100%)** |
| 15 | `artifacts/clustering/dbscan_chaining_diagnostics.parquet` | `2bae53207ae611395f30618505e8e00644b8c48e1f77768f2531bec20cd6c481` | `2bae53207ae611395f30618505e8e00644b8c48e1f77768f2531bec20cd6c481` | **MATCH (100%)** |
| 16 | `artifacts/clustering/kmeans_cluster_assignments.parquet` | `fca9a563bac59275e9dcbdc82aa97ba69f18963afc7089a6f99a3d1ff7e91b80` | `fca9a563bac59275e9dcbdc82aa97ba69f18963afc7089a6f99a3d1ff7e91b80` | **MATCH (100%)** |
| 17 | `artifacts/clustering/kmeans_candidate_evaluation.csv` | `e0cd587319b68bfe8be1f0321f438cd22d5e0bdc0209081ae7ceecfbf73aa253` | `e0cd587319b68bfe8be1f0321f438cd22d5e0bdc0209081ae7ceecfbf73aa253` | **MATCH (100%)** |
| 18 | `artifacts/clustering/transit_hub_rankings.parquet` | `20e116891376696370c38c2dd919d8d59c95b981fb493270b29763adb2260aa7` | `20e116891376696370c38c2dd919d8d59c95b981fb493270b29763adb2260aa7` | **MATCH (100%)** |
| 19 | `artifacts/clustering/top100_hubs_config_a.csv` | `201682c6587678e2ef05fb6635e7ac7f16c1a2ed8c0f7d08aaf17671a9d1bc03` | `201682c6587678e2ef05fb6635e7ac7f16c1a2ed8c0f7d08aaf17671a9d1bc03` | **MATCH (100%)** |
| 20 | `artifacts/clustering/top100_hubs_config_b.csv` | `beb0e6ca53c141ed4050cffb2fa02ecd253e8b7aca2038daa1598562bd0570e0` | `beb0e6ca53c141ed4050cffb2fa02ecd253e8b7aca2038daa1598562bd0570e0` | **MATCH (100%)** |
| 21 | `artifacts/clustering/top100_hubs_config_c.csv` | `7bf212ca1725f398c8a2f06ffaf725e3cd12cd8a528860a585e106f62d692ca9` | `7bf212ca1725f398c8a2f06ffaf725e3cd12cd8a528860a585e106f62d692ca9` | **MATCH (100%)** |
| 22 | `artifacts/clustering/phase6_1_stage2_metadata.json` | `4b4cd002a309538c0fe03eb7bd5e924cba5f00632198b57f15878085eb42f67f` | `4b4cd002a309538c0fe03eb7bd5e924cba5f00632198b57f15878085eb42f67f` | **MATCH (100%)** |
| 23 | `artifacts/ranking_features/route_ranker_feature_master.parquet` | `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85` | `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85` | **MATCH (100%)** |

**Zero baseline assets were modified or corrupted (100% bit-for-bit cryptographic match across all 23 protected files).**
