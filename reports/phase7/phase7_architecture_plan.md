# Phase 7 — Architecture Plan
## Modular Software Architecture for Multi-Criteria Route Ranking Engine

**Project:** `AI_RouteRanker — AI-Powered Public Transit Route Optimization`  
**Root Path:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** Milestone 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Phase:** 7 — Requirements Discovery and Architecture Planning  
**Status:** COMPLETE / ARCHITECTURE BASELINE  

---

## 1. Executive Summary & Architectural Goals

The **Phase 7 Architecture** establishes a modular, extensible, and mathematically rigorous Python package to evaluate and rank all 133 canonical CTA routes.

### Architectural Goals:
1. **Single Source of Truth:** Direct, read-only ingestion of the verified Phase 6.3 feature master (`artifacts/ranking_features/route_ranker_feature_master.parquet`).
2. **Strict Separation of Concerns:** Decouple criteria configuration, data transformation, mathematical scoring, explainability generation, and sensitivity analysis into distinct, independently testable modules.
3. **Dual MCDM Engine:** Primary production ranking via **Hierarchical Weighted Sum Model (WSM)** with secondary benchmark cross-validation via **TOPSIS**.
4. **Seamless Full-Stack Integration:** Produce structured Parquet and JSON deliverables directly consumable by the FastAPI backend and React 19 + TypeScript frontend.
5. **Deterministic Performance & Resource Safety:** Execute fully vectorized NumPy/Pandas pipelines consuming $< 250\text{ MB}$ RAM with execution time $< 5\text{ seconds}$ on standard CPU hardware.

---

## 2. Component Architecture & Module Structure

All ranking engine modules reside under `analytics/ranking/`, cleanly extending the existing package structure established in Phase 6.3:

```
analytics/ranking/
├── __init__.py                     # Package initialization and exports
├── config.py                       # Configuration, criteria definitions, weight profiles, paths
├── criteria_transformer.py         # Criteria extraction, directional inversion, missing-value masking
├── mcdm_engine.py                  # Core WSM and TOPSIS scoring algorithms
├── explainer.py                    # Additive contribution decomposition & natural language explanations
├── sensitivity.py                  # Weight perturbation analysis & Spearman rank correlation
└── ranker_service.py               # Orchestration service, file I/O, API integration facade
```

```
                                  [ route_ranker_feature_master.parquet ]
                                                     |
                                                     v
                                       [ criteria_transformer.py ]
                                    (Invert Headway, Mask Missing)
                                                     |
                         +---------------------------+---------------------------+
                         |                                                       |
                         v                                                       v
                 [ mcdm_engine.py ]                                      [ mcdm_engine.py ]
              Primary: WSM Engine (SAW)                               Secondary: TOPSIS Engine
                         |                                                       |
                         v                                                       v
                 [ explainer.py ]                                        [ sensitivity.py ]
        (Waterfall & Pillar Decomposition)                           (Spearman Rho & Perturbations)
                         |                                                       |
                         +---------------------------+---------------------------+
                                                     |
                                                     v
                                         [ ranker_service.py ]
                                                     |
                   +---------------------------------+---------------------------------+
                   |                                 |                                 |
                   v                                 v                                 v
   [ route_rankings_master.parquet ]    [ route_ranking_explanations.json ]  [ phase7_metadata.json ]
```

---

## 3. Module Responsibilities & Interface Specifications

### 3.1 `analytics/ranking/config.py` (Configuration)
- **Role:** Centralizes all ranking constants, criteria metadata, weight profile dictionaries, pillar mappings, and deliverable paths.
- **Key Classes / Structures:**
  - `RankingProfile` (Enum): `BALANCED_DEFAULT`, `OVERCROWDING_RELIEF`, `CORRIDOR_RESTRUCTURING`, `NETWORK_ESSENTIALITY`.
  - `RankingMode` (Enum): `BUS_PRIORITY` (125 routes), `RAIL_PRIORITY` (8 routes), `UNIFIED_SUPPLY` (133 routes).
  - `RankerConfig`: Extended with `MCDM_CRITERIA`, `WEIGHT_PROFILES`, `PILLAR_DEFINITIONS`, `DELIVERABLES_DIR`.

### 3.2 `analytics/ranking/criteria_transformer.py` (Data Preparation)
- **Role:** Ingests the 44-column feature master, validates required columns, inverts cost criteria into benefit metrics, and generates route-level valid criteria masks.
- **Key Functions:**
  - `load_feature_master(path: Path) -> pd.DataFrame`
  - `transform_criteria(df: pd.DataFrame, criteria: List[str]) -> Tuple[pd.DataFrame, Dict[str, np.ndarray]]`
    - Inverts `am_headway_min_norm` to $(1.0 - \text{am\_headway\_min\_norm})$.
    - Produces a clean $[N \times M]$ numerical matrix with boolean validity masks.

### 3.3 `analytics/ranking/mcdm_engine.py` (Core Mathematical Scoring)
- **Role:** Implements the core mathematical ranking algorithms.
- **Key Functions:**
  - `compute_wsm_scores(matrix: np.ndarray, weights: np.ndarray, valid_mask: np.ndarray) -> np.ndarray`
    - Computes dynamically normalized weighted sum scores for every route:
      $$S(r) = \sum_{i \in \text{Valid}(r)} \left( \frac{w_i}{\sum_{j \in \text{Valid}(r)} w_j} \right) X_{r, i}$$
  - `compute_topsis_scores(matrix: np.ndarray, weights: np.ndarray, valid_mask: np.ndarray) -> np.ndarray`
    - Implements Euclidean distance to positive and negative ideal solutions.
  - `generate_rankings(scores: np.ndarray, ascending: bool = False) -> Tuple[np.ndarray, np.ndarray]`
    - Generates 1-based ranks with standard competitive tie-breaking (`min` method).

### 3.4 `analytics/ranking/explainer.py` (Explainability Engine)
- **Role:** Translates raw numerical scores into transparent, additive contributions, high-level pillar scores, and natural language explanations.
- **Key Functions:**
  - `compute_contributions(matrix: np.ndarray, weights: np.ndarray, valid_mask: np.ndarray, feature_names: List[str]) -> pd.DataFrame`
    - Generates additive contribution columns ($C_{r, i} = w_i'(r) \cdot x_{r, i}$).
  - `compute_pillar_scores(contributions_df: pd.DataFrame, pillar_map: Dict[str, List[str]]) -> pd.DataFrame`
    - Aggregates contributions into 4 pillar scores: Demand, Service, Hubs, Duplication.
  - `generate_route_explanation(route_row: pd.Series, contributions: Dict[str, float], rank: int, total: int) -> Dict[str, Any]`
    - Generates top 2 positive drivers, top 2 negative drivers, missing criteria notices, and an automated narrative summary.

### 3.5 `analytics/ranking/sensitivity.py` (Stability & Sensitivity Analysis)
- **Role:** Performs robustness analysis under weight perturbations and cross-methodological validation.
- **Key Functions:**
  - `perturb_weights(base_weights: Dict[str, float], delta: float = 0.20) -> List[Dict[str, float]]`
    - Generates systematic single-criterion $\pm 10\%$ and $\pm 20\%$ perturbation vectors.
  - `evaluate_rank_sensitivity(df: pd.DataFrame, base_ranks: np.ndarray, perturbation_ranks: List[np.ndarray]) -> Dict[str, Any]`
    - Calculates Spearman's $\rho$, Kendall's $\tau$, mean absolute rank shift, and Top-10 / Top-20 stability index.
  - `compare_wsm_vs_topsis(wsm_scores: np.ndarray, topsis_scores: np.ndarray) -> Dict[str, float]`
    - Computes rank correlation between WSM and TOPSIS to validate methodological robustness.

### 3.6 `analytics/ranking/ranker_service.py` (Pipeline Orchestrator)
- **Role:** Master orchestration service that executes the end-to-end ranking workflow, saves canonical Parquet/JSON artifacts, and exposes a clean programmatic API for the FastAPI backend.
- **Key Methods:**
  - `run_ranking_pipeline(profile: str = "BALANCED_DEFAULT", mode: str = "BUS_PRIORITY") -> Dict[str, Any]`
  - `save_ranking_deliverables(results: Dict[str, Any], output_dir: Path) -> None`
  - `get_route_ranking(route_id: str) -> Optional[Dict[str, Any]]`

---

## 4. Input & Output Deliverable Specifications

### 4.1 Input Specification
- **Path:** `artifacts/ranking_features/route_ranker_feature_master.parquet`
- **Schema:** 133 rows $\times$ 44 columns, primary key `route_id`. Read-only access enforced.

### 4.2 Output Deliverables (Directory: `artifacts/ranking_results/`)

#### 1. `route_rankings_master.parquet`
Primary tabular deliverable containing all route rankings, composite scores, pillar rollups, and individual criterion contributions:
- Columns:
  - Identifiers: `route_id`, `route_short_name`, `route_long_name`, `is_rail`, `regional_partition`, `operational_cluster_label`
  - Ranking Metrics: `overall_score`, `rank`, `percentile_rank`
  - Pillar Rollups: `pillar_demand_score`, `pillar_service_score`, `pillar_hub_score`, `pillar_corridor_score`
  - Criterion Contributions: `contrib_demand`, `contrib_load_intensity`, `contrib_trips`, `contrib_span`, `contrib_headway`, `contrib_hub_ratio`, `contrib_corridor_dup`
  - TOPSIS Benchmark: `topsis_score`, `topsis_rank`
- Row Count: 133 (or segmented by mode).

#### 2. `route_ranking_explanations.json`
Complete structured explanation payload optimized for frontend rendering:
```json
{
  "route_id": "79",
  "route_short_name": "79",
  "route_long_name": "79th",
  "rank": 1,
  "total_routes": 125,
  "overall_score": 0.8425,
  "pillars": {
    "demand_pressure": 0.3250,
    "service_availability": 0.2310,
    "hub_connectivity": 0.0820,
    "corridor_duplication": 0.2045
  },
  "top_positive_drivers": [
    {"criterion": "Load Intensity Factor", "contribution": 0.1985, "percentile": 98.4},
    {"criterion": "Corridor Duplication Index", "contribution": 0.1742, "percentile": 95.2}
  ],
  "top_negative_drivers": [
    {"criterion": "Hub Stop Ratio", "contribution": 0.0046, "percentile": 12.0}
  ],
  "missing_criteria": [],
  "narrative": "Route 79 ranks #1 of 125 bus routes with an overall priority score of 0.842. Its ranking is primarily driven by exceptionally high passenger load intensity and significant corridor duplication along 79th Street."
}
```

#### 3. `ranking_sensitivity_analysis.parquet`
Records stability metrics, Spearman rank correlations, and rank volatility across all weight perturbation scenarios.

#### 4. `phase7_metadata.json`
Detailed run metadata recording execution timestamp, input hashes, deliverable hashes, active weight profile, and host execution metrics.

---

## 5. Full-Stack Integration Contracts

### 5.1 FastAPI Backend Contract
The backend exposes REST endpoints consuming the generated ranking artifacts:
- `GET /api/v1/rankings`: Returns paginated list of ranked routes with filtering options (`profile`, `mode`, `regional_partition`).
- `GET /api/v1/rankings/{route_id}`: Returns detailed ranking data and pillar breakdown for a single route.
- `GET /api/v1/rankings/{route_id}/explanation`: Returns the structured explanation JSON payload for frontend modal display.

### 5.2 React 19 + TypeScript Frontend Contract
Frontend dashboard components consume the API responses:
- **Rankings Table Component:** Displays sortable ranks, badges (`Trunk`, `Feeder`, `Regional`), pillar mini-bars, and overall score pills.
- **Pillar Radar Chart (`Recharts`):** Renders the 4 pillar scores ($[0, 1]$) against network averages.
- **Waterfall Contribution Chart (`Recharts`):** Displays horizontal stacked bar charts showing exact additive positive and negative criterion contributions.
- **Route Explanation Modal:** Presents the natural language summary and top drivers.

---

## 6. Resource Governance & Performance Constraints

- **Platform:** Windows 11, Python 3.11, CPU-only.
- **Memory Guard:** Total execution memory consumption will remain $< 250\text{ MB}$, well within the project's strict 600 MB abort threshold.
- **Runtime Performance:** Entire scoring, explainability generation, and sensitivity analysis pipeline completes in $< 5\text{ seconds}$ for all 133 routes.
- **Zero Protected Asset Modification:** Milestone 5 models, Phase 6.1/6.2 clustering artifacts, and Phase 6.3 feature master are strictly accessed in read-only mode.

---

## 7. Conclusion

The Phase 7 architecture delivers an end-to-end, modular, and fully explainable ranking engine. We proceed to lay out the staged development roadmap in `reports/phase7/phase7_implementation_roadmap.md`.
