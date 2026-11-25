# Phase 6.3 — Requirements Discovery Report
## Cross-Phase Spatial Synthesis and Multi-Criteria Route Ranker Feature Integration

**Project:** AI_RouteRanker — AI-Powered Public Transit Route Optimization  
**Project Directory:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Date:** 2026-11-25 13:20:00 +05:30  
**Phase:** Phase 6.3 (Milestone 6 Module 4 / Module 5 Integration Bridge)  
**Mode:** **READ-ONLY INSPECTION AND PLANNING ONLY**  
**Status:** **REQUIREMENTS DISCOVERED & FORMALIZED**  

---

## 1. Authoritative Documentation Review & Hierarchy

To establish the exact, unambiguous scope of Phase 6.3, all authoritative project documentation, repository history, schemas, and completed milestone reports were inspected:

### 1.1 Documentation Hierarchy
1. **[`README.md`](file:///D:/B.TECH_PROJECTS/AI_RouteRanker/README.md) (Root Architectural Blueprint):**
   - **Section 1 (Project Objective):** Establishes the three core capabilities: (1) Passenger Demand Forecasting, (2) Transit Hub & Bottleneck Identification, and (3) Multi-Criteria Route Ranking & Optimization.
   - **Section 3 (Directory Structure):** Defines `analytics/clustering/` for stop & corridor clustering and `analytics/ranking/` for multi-criteria route optimization & scoring algorithms.
   - **Section 7 (Future Development Modules):** Establishes the sequential progression from Module 1 (Ingestion) through Module 4 (Spatial Stop & Route Clustering) to Module 5 (Multi-Criteria Route Ranking Engine).
2. **[`reports/clustering/phase6_1_stage2_report.md`](file:///D:/B.TECH_PROJECTS/AI_RouteRanker/reports/clustering/phase6_1_stage2_report.md) (Phase 6.1 Canonical Baseline):**
   - Locked stop-level clustering methodology: 11,020 physical boarding stops, equirectangular projection, DBSCAN spatial proximity clusters, 5-headway window profiles, stop-level demand attribution, functional $K$-Means typology ($K=3$), and Top-100 Transit Hub rankings (Configs A, B, C).
3. **[`reports/clustering/phase6_2_stage2_report.md`](file:///D:/B.TECH_PROJECTS/AI_RouteRanker/reports/clustering/phase6_2_stage2_report.md) and [`reports/clustering/phase6_2_documentation_correction_report.md`](file:///D:/B.TECH_PROJECTS/AI_RouteRanker/reports/clustering/phase6_2_documentation_correction_report.md):**
   - Locked route-level clustering methodology: 133 canonical GTFS routes, 261 active route-direction patterns on `2026-06-10`, 100m buffer overlap ratios, exact Discrete Fréchet distances ($K=2$ North vs South Chicago regional divider), 950 contiguous shared consecutive stop sequences, and route operational typology ($K=3$ champion model).
   - Explicitly records: *"Phase 6.3 (Route Ranker Integration) is strictly contingent upon formal user sign-off on Phase 6.2 Stage 2 outputs and report."*
4. **[`reports/modeling/random_forest/final_model_evaluation_report.md`](file:///D:/B.TECH_PROJECTS/AI_RouteRanker/reports/modeling/random_forest/final_model_evaluation_report.md):**
   - Locked demand forecasting baselines: Tier 1 (route-level) and Tier 2 (route-daytype) Random Forest models, feature importances, and validated prediction artifacts.

### 1.2 Documentation Conflict Assessment
- **Finding:** There is **zero contradiction** between existing reports and the root `README.md`.
- **Authoritative Status:** The high-level objective is explicitly codified in `README.md` and previous milestone audit reports. However, detailed sub-stage technical specifications for Phase 6.3 were not pre-authored in `docs/`. Consequently, the technical architecture, indicator schemas, and implementation sequence designed in this report represent the authoritative technical proposal for user approval.

---

## 2. Phase 6.3 Objective & Role in AI_RouteRanker

Phase 6.3 serves as the **critical analytical synthesis bridge** between:
- **Module 4 (Spatial Stop & Route Clustering — Milestone 6):** Stop hubs, DBSCAN spatial clusters, corridor buffer overlaps, shared stop sequences, and operational typologies.
- **Module 5 (Multi-Criteria Route Ranking Engine — Milestone 7):** Composite transit scoring balancing load factors, demand density, headway compliance, and operational efficiency.

### Core Mission
Phase 6.3 synthesizes the granular stop-level, route-corridor, network-connectivity, and machine learning demand forecast outputs into a unified, clean, route-level evaluation dataset:
```
route_ranker_feature_master.parquet
```
This dataset arms the downstream ranking engine (Module 5) and the interactive dashboard (Module 6) with multidimensional, verified transit performance indicators across all 133 CTA routes.

---

## 3. Explicitly Documented vs Recommended / Inferred Requirements

To ensure complete transparency, requirements are strictly divided into approved project mandates versus recommended design choices:

### 3.1 Explicitly Documented Requirements (Mandatory)
1. **Target Population:** All 133 canonical GTFS routes (125 bus, 8 rail) must be represented.
2. **Canonical Data Snapshot & Service Date:** GTFS snapshot `mdb-389-202605300003` and representative service date `2026-06-10` (Wednesday).
3. **Database Security:** Strict read-only connection to `data/processed/ai_routeranker.duckdb`. Zero database writes.
4. **Hardware & Resource Limits:** Strict compliance with the 8 GB physical RAM CPU-only environment. Abort immediately if available RAM $<600\text{ MB}$ or memory load $>95\%$.
5. **Asset Immutability:** Absolute protection of all 22 protected baseline assets (Random Forest models, Phase 6.1 outputs, Phase 6.2 outputs, and DuckDB).
6. **Ridership Data Preservation:** Rail ridership must remain `NaN` without synthetic zero-filling.
7. **Exclusion Transparency:** Specialized routes with missing features (e.g. Routes 10, 130, N5 lacking AM peak headways) must be documented and handled transparently.

### 3.2 Recommended & Inferred Requirements (Subject to User Approval)
1. **Indicator Construction (Recommended):** Formulate 4 composite multi-criteria indicators synthesizing prior milestone outputs:
   - *Transit Hub Connectivity Index ($H_r$):* Proportion and volume of a route's scheduled stops that intersect Phase 6.1 Top-100 Transit Hubs.
   - *Corridor Duplication & Infrastructure Sharing Index ($D_r$):* Degree of physical co-routing and shared consecutive stops derived from Phase 6.2 buffer overlap matrices and 950 shared stop sequences.
   - *Demand Pressure & Fleet Allocation Factor ($L_r$):* Ratio of predicted ridership (from Tier 1/Tier 2 Random Forest models) to scheduled service capacity (scheduled trips and vehicle service span).
   - *Regional Spatial Equity Indicator ($E_r$):* Route spatial alignment with the verified North vs South metropolitan partition (Fréchet $K=2$) and coverage of DBSCAN peripheral/noise stops.
2. **Feature Master Granularity (Recommended):** Produce route-level aggregates ($N=133$) while preserving route-direction breakdowns ($N=261$) in a secondary link table for interactive mapping.
3. **Normalization Standards (Recommended):** Use robust percentile MinMax scaling ($\text{clip}[p_{01}, p_{99}]$) to protect against transit outlier skewing (e.g. high-capacity rail lines vs local shuttles).

---

## 4. Input Data Dependencies & Reusable Artifacts

Phase 6.3 reuses existing, validated outputs across multiple milestones without recalculating raw features:

| Milestone / Source | Artifact Name | Format / Location | Reusable Information in Phase 6.3 |
| :--- | :--- | :--- | :--- |
| **Phase 6.1** | `transit_hub_rankings.parquet` | `artifacts/clustering/` | Hub scores (Configs A, B, C) for all 11,020 physical stops |
| **Phase 6.1** | `top100_hubs_config_a.csv` | `artifacts/clustering/` | Explicit Top-100 transit hub stop IDs and coordinates |
| **Phase 6.1** | `spatial_dbscan_assignments.parquet` | `artifacts/clustering/` | DBSCAN stop clusters, core stops, and peripheral/noise stops |
| **Phase 6.1** | `stop_level_feature_master.parquet` | `artifacts/clustering/` | Stop-level service frequency and demand coverage status |
| **Phase 6.2** | `route_level_operational_features.parquet` | `artifacts/route_clustering/` | 133 routes: trips, span, AM headway, length, unique stops, ridership |
| **Phase 6.2** | `kmeans_operational_assignments.parquet` | `artifacts/route_clustering/` | 130 clustered routes: champion $K=3$ typology (Trunk, Feeder, Regional) |
| **Phase 6.2** | `buffer_overlap_similarity_matrix.parquet` | `artifacts/route_clustering/` | $261 \times 261$ spatial corridor overlap matrix |
| **Phase 6.2** | `shared_consecutive_stop_sequences.parquet` | `artifacts/route_clustering/` | 950 contiguous shared physical stop sequences ($\ge 2$ stops) |
| **Phase 6.2** | `corridor_cluster_assignments.parquet` | `artifacts/route_clustering/` | 261 patterns assigned to corridor clusters (Fréchet $K=2$ regional) |
| **Milestone 5** | `tier1_random_forest_tuned.joblib` | `artifacts/random_forest/` | Trained model for route-level passenger demand forecasting |
| **Milestone 5** | `model_ready_features.parquet` | `data/processed/features/` | Validated feature records for historical demand predictions |
| **DuckDB** | `ai_routeranker.duckdb` | `data/processed/` | Read-only GTFS schedule tables (`gtfs_stop_times`, `gtfs_trips`, `gtfs_routes`) |

---

## 5. Expected Outputs & Deliverables

Phase 6.3 will produce the following primary artifacts under `artifacts/ranking_features/` (or `artifacts/route_ranking/`):

1. **`route_ranker_feature_master.parquet`:**
   The unified multi-criteria feature dataset containing all 133 canonical routes with:
   - Core route identity (`route_id`, `route_short_name`, `route_type`, `is_rail`).
   - Operational features (`scheduled_trips`, `service_span_hours`, `am_headway_min`, `route_length_km`, `unique_stops_count`).
   - Operational typology cluster (`operational_cluster_k3`, label: Trunk/Feeder/Regional).
   - Demand indicators (`historical_mean_daily_rides`, `forecasted_daily_demand`, `rides_per_trip`).
   - Hub connectivity metrics (`hub_stop_count`, `hub_stop_ratio`, `hub_weighted_importance`).
   - Corridor sharing metrics (`max_corridor_overlap`, `mean_corridor_overlap`, `shared_consecutive_stop_count`).
   - Regional orientation (`regional_partition`: North vs South Chicago).
2. **`route_direction_connectivity_matrix.parquet`:**
   Route-to-hub and route-to-corridor graph connectivity table.
3. **`phase6_3_metadata.json`:**
   Execution metadata, timestamps, input artifact hashes, and summary distributions.
4. **`reports/phase6_3/phase6_3_synthesis_report.md`:**
   Full analytical report documenting synthesized indicators, distributions, and readiness for Module 5 ranking algorithms.

---

## 6. Acceptance Criteria

Phase 6.3 will be evaluated against strict, measurable acceptance criteria:
1. **Network Completeness:** Exactly 133 canonical routes must be accounted for (125 bus, 8 rail).
2. **Zero Leakage:** Historical forecasting models must only be evaluated on approved feature dates; no future or holdout targets leaked into ranking inputs.
3. **Zero Imputation Corruption:** Missing ridership for rail lines ($N=8$) must be preserved as `NaN`; missing AM headways for Routes 10, 130, N5 must be documented and handled safely.
4. **Mathematical Consistency:** All synthesized indices must be bounded ($\in [0, 1]$ or normalized $[0, 100]$) with documented mathematical formulas.
5. **Memory Safety:** Peak RAM utilization must remain under 95% load and $>600\text{ MB}$ available at all times.
6. **Regression Preservation:** All 34 Phase 6.2 tests, 105 Phase 6.1/ML tests, and full test discovery suite must pass ($100\%$).
7. **Protected Asset Immutability:** All 22 protected asset SHA-256 hashes must remain identical.
