# Phase 7 — Requirements Discovery Report
## Multi-Criteria Decision-Making (MCDM) Route Ranking Engine

**Project:** `AI_RouteRanker — AI-Powered Public Transit Route Optimization`  
**Root Path:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** Milestone 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Phase:** 7 — Requirements Discovery and Architecture Planning  
**Status:** COMPLETE / ARCHITECTURE PLANNING BASELINE  
**Authoritative Input:** `artifacts/ranking_features/route_ranker_feature_master.parquet` (133 routes $\times$ 44 columns)

---

## 1. Executive Summary & Project Purpose

Milestone 7 represents the culminating analytical engine of the **AI_RouteRanker** platform. Preceding milestones successfully ingested GTFS network feeds, established historical demand and headway distributions, trained high-accuracy Random Forest ridership forecasting models (Milestone 5), clustered stops into spatial transit hubs (Phase 6.1), quantified Frechet-based corridor co-routing alignments (Phase 6.2), and synthesized these multidimensional attributes into a unified, 44-column canonical feature master across all 133 CTA routes (Phase 6.3).

The primary objective of Milestone 7 is to design and implement an **explainable, transparent, multi-criteria decision-making (MCDM) ranking engine** that evaluates and ranks all 133 transit routes across operational, spatial, demand, and structural dimensions.

### Core Mission & Ethical Governance:
- **Decision-Support Tool:** The ranking engine is designed exclusively as an advanced **decision-support system** for transit planners, schedule coordinators, and mobility analysts.
- **Strict Non-Automation Principle:** The ranking engine **does not** and **must not** constitute an automated trigger to reduce, eliminate, or arbitrarily expand transit service. Real-world transit operations involve complex Title VI civil rights mandates, community equity obligations, contract work rules, and network connectivity guarantees that exceed pure algorithmic scoring. Algorithmic rankings serve to identify routes deserving **planning attention, operational review, schedule recalibration, or corridor restructuring investigation**.

---

## 2. Authoritative Input & Verified Feature Baseline

The ranking engine operates strictly upon the verified canonical outputs produced by Phase 6.3 Stage 2:

1. **Primary Feature Master:** `artifacts/ranking_features/route_ranker_feature_master.parquet`  
   - Dimensions: Exactly **133 rows $\times$ 44 columns**.  
   - SHA-256: `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85`.  
   - Population: Exactly **125 bus routes** and **8 heavy rail lines** (`Red`, `Blue`, `Brn`, `G`, `Org`, `P`, `Pink`, `Y`).
2. **Directional Pattern Link Matrix:** `artifacts/ranking_features/route_direction_connectivity_matrix.parquet`  
   - Dimensions: Exactly **261 active patterns $\times$ 7 columns** on the representative date `2026-06-10`.
3. **Execution Metadata:** `artifacts/ranking_features/phase6_3_metadata.json`  
   - Validates snapshot `mdb-389-202605300003`, service date `2026-06-10`, and normalization parameters.

---

## 3. Physical Feature Inventory & Classification

The 44 columns of the canonical feature master were systematically categorized into functional roles:

### 3.1 Identifiers & Descriptive Metadata (Non-Scored)
These columns provide identity, display labels, GTFS categorization, and regional grouping. They must not enter numerical scoring equations directly:
- `route_id` (string): Primary route identifier.
- `route_short_name` (string): Public route number or abbreviation.
- `route_long_name` (string): Full descriptive route corridor name.
- `route_type` (integer): GTFS mode code ($1 = \text{Rail}, 3 = \text{Bus}$).
- `is_rail` (boolean): Mode segmentation flag.
- `regional_partition` (string): Geographic grouping based on Frechet trajectory clustering (`North Chicago`, `South Chicago`).
- `operational_cluster_k3` (float): K-Means operational typology cluster index ($0, 1, 2$).
- `operational_cluster_label` (string): Semantic operational label (`Trunk`, `Feeder`, `Regional`).

### 3.2 Raw Physical Counts & Operational Metrics (Candidate Criteria)
Physical metrics reflecting physical supply, service frequency, and geometry:
- `scheduled_trips` (int): Total trips scheduled across the 24-hour service date.
- `log_scheduled_trips` (float): Natural logarithm of scheduled trips (variance-stabilized).
- `service_span_hours` (float): Operating span from first scheduled departure to last arrival.
- `am_headway_min` (float): Mean scheduled interval between departures during AM peak (07:00–09:00).
- `route_length_km` (float): Total round-trip or bidirectional centerline corridor length.
- `unique_stops_count` (int): Number of distinct physical stop locations served by the route.

### 3.3 Demand & Passenger Pressure Metrics (Candidate Criteria)
Passenger boarding volume and vehicle loading intensity:
- `historical_mean_daily_rides` (float): Empirical mean weekday boardings from Phase 6.2 baseline telemetry.
- `forecasted_daily_demand` (float): Milestone 5 Tuned Tier 1 Random Forest ridership forecast for `2026-06-10`.
- `rides_per_trip` (float): Average passenger volume per scheduled trip ($\text{Demand} / \text{Trips}$).
- `load_intensity_factor` (float): Demand pressure per vehicle-kilometer ($\text{Rides per Trip} / \text{Length}$).

### 3.4 Spatial & Corridor Connectivity Metrics (Candidate Criteria)
Network connectivity, hub transfer access, and infrastructure overlap:
- `hub_stop_count` (int): Absolute count of stops intersecting Phase 6.1 Top-100 transit hubs.
- `hub_stop_ratio` (float): Proportion of route stops intersecting Top-100 transit hubs ($\in [0, 1]$).
- `hub_weighted_importance` (float): Cumulative importance-weighted hub score.
- `max_corridor_overlap` (float): Maximum pairwise Frechet alignment similarity with any other route ($\in [0, 1]$).
- `mean_corridor_overlap` (float): Mean alignment similarity with top-5 overlapping routes ($\in [0, 1]$).
- `shared_consecutive_stop_count` (int): Total shared consecutive stops ($\ge 2$ contiguous stops) with other routes.
- `corridor_duplication_ratio` (float): Ratio of shared stops to total unique route stops ($\in [0, 1]$).

### 3.5 Composite Domain Indicators (Pre-Engineered Criteria)
Formulas synthesized in Phase 6.3:
- `hub_connectivity_index` ($H_r$): Weighted combination of hub stop ratio and normalized importance ($H_r = 0.40 \cdot \text{hub\_stop\_ratio}$).
- `corridor_duplication_index` ($D_r$): Multi-criteria structural overlap index ($D_r = 0.40 \cdot \text{max\_overlap} + 0.30 \cdot \text{mean\_overlap} + 0.30 \cdot \text{dup\_ratio}$).
- `spatial_equity_indicator` ($E_r$): Fraction of route stops serving peripheral / unclustered transit zones.

### 3.6 Percentile-Normalized Variants (`_norm`)
The 16 continuous numerical features have pre-computed 1st-to-99th percentile min-max scaled columns strictly bounded in $[0.0, 1.0]$. These normalized columns provide the verified numerical inputs for MCDM algorithms.

---

## 4. Empirical Feature Distributions & Data Limitations

Empirical inspection of the 44-column master revealed critical characteristics that dictate criterion selection:

1. **Constant Features (Zero Information Variance):**
   - `spatial_equity_indicator`: Exhibits a mean of $1.000$, standard deviation of $0.000$, minimum of $1.000$, and maximum of $1.000$ across all 133 routes.
   - `hub_weighted_importance`: Value is $0.000$ across all 133 routes (because stop IDs in the spatial clustering table were typed as integers while GTFS stop IDs were alphanumeric strings, yielding an empty join on scores while stop-ID geometry intersections succeeded for `hub_stop_count`). Consequently, `hub_weighted_importance_norm` was mapped to $0.500$ via the zero-variance guard.
   - *Design Implication:* Features with zero variance **must not** be assigned active criteria weights in the ranking engine, as a constant feature acts only as an uninformative scalar offset.

2. **Multicollinearity & Double-Counting Audit:**
   Pearson correlation analysis across the 133 routes revealed severe redundancy among certain pairs:
   - $\text{historical\_mean\_daily\_rides} \leftrightarrow \text{forecasted\_daily\_demand}$: $r = 0.9954$.
     *Rule:* Using both would double-count passenger volume. The engine must use `forecasted_daily_demand_norm` as the primary forward-looking demand criterion.
   - $\text{mean\_corridor\_overlap} \leftrightarrow \text{corridor\_duplication\_index}$: $r = 0.9332$.
   - $\text{max\_corridor\_overlap} \leftrightarrow \text{corridor\_duplication\_index}$: $r = 0.9284$.
   - $\text{corridor\_duplication\_ratio} \leftrightarrow \text{corridor\_duplication\_index}$: $r = 0.8935$.
     *Rule:* Because `corridor_duplication_index` already integrates maximum overlap, mean overlap, and shared stop ratios with verified weights ($0.4/0.3/0.3$), the engine must use `corridor_duplication_index_norm` as a single composite criterion rather than including the raw sub-components simultaneously.
   - $\text{scheduled\_trips} \leftrightarrow \text{log\_scheduled\_trips}$: $r = 0.9107$.
     *Rule:* Use linear `scheduled_trips_norm` (or log variant), but never both.
   - $\text{scheduled_trips} \leftrightarrow \text{forecasted_daily_demand}$: $r = 0.8900$.
     *Rule:* Transit agencies schedule service in proportion to demand. To isolate service efficiency from raw scale, `load_intensity_factor_norm` (demand divided by trips and length) provides distinct operational signal ($r = 0.3278$ with demand).

---

## 5. Candidate Criteria & Preference Direction

Depending on the planning objective, criteria are classified as **Benefit** (higher is prioritized) or **Cost** (lower is prioritized):

| Criterion Code | Feature Name | Description | Preference Direction | Planning Rationale |
| :---: | :--- | :--- | :---: | :--- |
| **C1** | `forecasted_daily_demand_norm` | Total forecasted passenger trips | **Benefit** ($\uparrow$) | Routes serving large passenger volumes represent core public mobility lifelines. |
| **C2** | `load_intensity_factor_norm` | Passenger demand per vehicle-km | **Benefit** ($\uparrow$) | High passenger load intensity indicates overcrowding risk and intense capacity utilization. |
| **C3** | `scheduled_trips_norm` | Total daily scheduled trips | **Benefit** ($\uparrow$) | Reflects operational service commitment and transit provision. |
| **C4** | `service_span_hours_norm` | Operating hours per day | **Benefit** ($\uparrow$) | Longer service spans provide vital all-day and shift-worker accessibility. |
| **C5** | `am_headway_min_norm` | Peak AM headway in minutes | **Cost** ($\downarrow$) | Shorter headways signify higher frequency and superior service quality. For benefit formulation, inverted as $(1 - \text{headway\_norm})$. |
| **C6** | `hub_stop_ratio_norm` | Ratio of stops at major transit hubs | **Benefit** ($\uparrow$) | High hub connectivity indicates vital network transfer functionality. |
| **C7** | `corridor_duplication_index_norm` | Structural co-routing duplication | **Context-Dependent** | In *Intervention Priority* mode, high duplication indicates prime candidates for corridor consolidation or branch streamlining ($\uparrow$). In *Autonomous Network Health* mode, low duplication is preferred ($\downarrow$). |

---

## 6. Missing-Data Policy & Subgroup Handling

The ranking methodology must rigorously enforce the approved missing-data rules:

### 6.1 Heavy Rail Subgroup (8 Routes)
- **Data Status:** Rail routes (`Red`, `Blue`, `Brn`, `G`, `Org`, `P`, `Pink`, `Y`) have turnstile-based ridership that is not disaggregated by route in the GTFS farebox telemetry. Consequently, `historical_mean_daily_rides`, `forecasted_daily_demand`, `rides_per_trip`, and `load_intensity_factor` are strictly `NaN`.
- **Methodology Policy:**
  1. Imputing zeros or mean values is strictly forbidden (would unfairly penalize rail as having zero ridership, which is factually false).
  2. Imputing synthetic ridership is forbidden.
  3. **Dual-Track Ranking Architecture:**
     - **Track 1: Bus Network Priority Ranking (125 Routes):** Evaluates all 125 bus routes using the full multi-criteria framework (Demand, Operations, Hub Connectivity, and Duplication).
     - **Track 2: Rail Network Operational Ranking (8 Routes):** Evaluates all 8 rail lines using mode-appropriate operational criteria (`scheduled_trips`, `service_span_hours`, `am_headway_min`, `route_length_km`, `unique_stops_count`, `corridor_duplication_index`).
     - **Track 3: Unified Network-Wide Operational Supply Ranking (133 Routes):** A unified ranking across all 133 routes based on shared, mode-agnostic operational supply and corridor geometry metrics.

### 6.2 Specialized Bus Routes (3 Routes: 10, 130, N5)
- **Data Status:**
  - Route 130 (Museum Campus): Starts after 09:00 AM (no AM peak service).
  - Route N5 (South Shore Night Bus): Overnight owl service ending before AM peak.
  - Route 10 (Museum of Science & Industry): Operates exactly 1 trip in AM peak (no interval).
  - `am_headway_min` and `am_headway_min_norm` are strictly `NaN`.
- **Methodology Policy:**
  1. Do not replace `am_headway_min` with zero (which would falsely imply instantaneous, infinite frequency).
  2. Do not replace with arbitrary penalty values (e.g., 999 min).
  3. **Dynamic Criterion Weight Masking & Renormalization:** When scoring a route missing criterion $k$, criterion $k$ is masked out and the remaining valid criteria weights are dynamically normalized to sum to $1.0$:
     $$w_i' = \frac{w_i}{\sum_{j \in \text{Valid}(r)} w_j}$$
     This evaluates the route objectively based exclusively on the dimensions where valid empirical data exists, without distortion or penalty.

---

## 7. Explainability & Sensitivity Requirements

### 7.1 Explainability Architecture
To support transparent transit decision-making and seamless integration with the React/TypeScript frontend, the ranking engine must provide:
1. **Decomposed Criterion Contributions:** For every route $r$ and criterion $i$, output the exact additive contribution:
   $$\text{Contribution}_{r, i} = w_i \cdot x_{r, i}$$
2. **Pillar Sub-Scores:** Aggregate scores into 4 high-level planning pillars:
   - *Demand & Capacity Pressure Pillar*
   - *Service Frequency & Availability Pillar*
   - *Network & Hub Connectivity Pillar*
   - *Corridor Structure & Duplication Pillar*
3. **Waterfall Score Attribution:** Identify the top 2 positive drivers (strengths elevating the score) and top 2 negative drivers (factors pulling the score down).
4. **Natural Language Synthesis:** Automated, plain-English summary paragraphs explaining the route's performance profile and operational context.

### 7.2 Sensitivity & Stability Testing
The engine must incorporate automated sensitivity analysis:
1. **Weight Perturbation:** Evaluate rank shifts when individual criteria weights are varied by $\pm 10\%$ and $\pm 20\%$.
2. **Statistical Correlation:** Compute Spearman's rank correlation ($\rho$) and Kendall's tau ($\tau$) between alternative weighting profiles.
3. **Top-K Volatility:** Measure stability of the top-10 and top-20 priority routes under weight perturbations.

---

## 8. Requirements Traceability Matrix

| Requirement ID | Description | Source / Mandate | Proposed Design Implementation |
| :---: | :--- | :--- | :--- |
| **REQ-01** | Support planning decision-making without automated service cut triggers | Project Charter & User Mandate | Define ranking as "Operational & Planning Review Priority"; provide balanced positive/negative explanations. |
| **REQ-02** | Ingest canonical 44-column feature master without modifications | Phase 6.3 Final Verification | Load `artifacts/ranking_features/route_ranker_feature_master.parquet` directly in read-only mode. |
| **REQ-03** | Prevent multicollinear double-counting | Statistical Correlation Audit | Exclude `historical_mean_daily_rides` ($r=0.9954$ with forecast); use composite `corridor_duplication_index`. |
| **REQ-04** | Exclude zero-variance constant features | Empirical Feature Audit | Exclude `spatial_equity_indicator` and `hub_weighted_importance` from weighted scoring equations. |
| **REQ-05** | Respect rail ridership missingness policy | Phase 6.2/6.3 Governance | Implement dual-track ranking: Bus Network Priority (125 routes) and Unified Operational Supply (133 routes). |
| **REQ-06** | Handle specialized route headway missingness | Phase 6.2 W-03 Resolution | Implement dynamic weight renormalization over valid criteria ($w_i' = w_i / \sum w_j$). |
| **REQ-07** | Maintain strict $[0, 1]$ criterion normalization | Phase 6.3 Normalization | Ingest pre-verified `_norm` columns; invert cost criteria via $(1 - x_{\text{norm}})$. |
| **REQ-08** | Provide additive explainability for UI | Frontend Architecture | Implement additive linear decomposition and pillar sub-score rollups. |
| **REQ-09** | Provide sensitivity analysis | Robustness Mandate | Implement weight perturbation matrix and Spearman rank correlation tracking. |
| **REQ-10** | Memory & resource safety | Windows 11 8 GB RAM Guard | Vectorized NumPy/Pandas operations; memory consumption strictly $< 600\text{ MB}$. |

---

## 9. Conclusion & Planning Authorization

Requirements discovery is complete. The operational, mathematical, and data constraints of the 133-route network have been mapped to robust methodological principles. We proceed to evaluate candidate Multi-Criteria Decision-Making (MCDM) algorithms in `reports/phase7/phase7_mcdm_methodology_comparison.md`.
