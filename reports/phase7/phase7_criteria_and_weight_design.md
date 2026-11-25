# Phase 7 — Criteria and Weight Design Report
## Multi-Dimensional Decision Hierarchy and Weighting Framework

**Project:** `AI_RouteRanker — AI-Powered Public Transit Route Optimization`  
**Root Path:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** Milestone 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Phase:** 7 — Requirements Discovery and Architecture Planning  
**Status:** COMPLETE / CRITERIA DESIGN BASELINE  

---

## 1. Executive Summary & Design Principles

The credibility, explainability, and policy utility of the Multi-Criteria Decision-Making (MCDM) ranking engine depend fundamentally on the design of its evaluation criteria and weight parameters.

This report establishes the **Hierarchical Multi-Pillar Transit Evaluation Framework** for AI_RouteRanker. The framework organizes transit performance into **four distinct planning pillars** that comprehensively capture demand volume, operational capacity utilization, schedule commitment, spatial hub connectivity, and structural corridor duplication.

### Core Design Principles:
1. **Mathematical Orthogonality:** Exclude redundant, collinear feature pairs ($r \ge 0.70$) to prevent unintentional double-counting of the same physical transit signal.
2. **Directional Consistency:** Ensure all criteria are oriented such that higher normalized values consistently indicate higher planning or intervention priority. Cost criteria (such as headway intervals) are mathematically inverted into benefit metrics.
3. **Information Integrity:** Strictly exclude constant features with zero empirical variance (e.g., `spatial_equity_indicator` and `hub_weighted_importance`) from receiving active weights.
4. **Policy Persona Flexibility:** Provide a default balanced planning profile alongside transparent stakeholder personas (Overcrowding Relief, Corridor Restructuring, and Network Essentiality).
5. **Subgroup Equity:** Enforce distinct, defensible evaluation tracks for bus and heavy rail routes to accommodate fundamental differences in farebox telemetry availability.

---

## 2. Four-Pillar Evaluation Framework

The 133 CTA routes are evaluated across four primary functional dimensions totaling $100\%$ weight:

```
                            [ Total Route Evaluation Score (100%) ]
                                               |
         +--------------------+----------------+--------------------+--------------------+
         |                    |                                     |                    |
   [ Pillar 1: 35% ]    [ Pillar 2: 25% ]                     [ Pillar 3: 20% ]    [ Pillar 4: 20% ]
  Demand & Passenger   Operational Service                    Network & Hub        Corridor Structure
   Capacity Pressure  Provision & Frequency                    Connectivity         & Duplication
         |                    |                                     |                    |
   -- Forecasted (15%)  -- Scheduled Trips (10%)              -- Hub Stop          -- Corridor
   -- Load Factor (20%) -- Service Span (5%)                     Ratio (20%)          Duplication (20%)
                        -- Headway Inverted (10%)
```

---

## 3. Detailed Criteria Specifications

### 3.1 Pillar 1: Demand & Passenger Capacity Pressure (Total Weight: 35%)

#### Criterion 1.1: Forecasted Passenger Volume
- **Physical Column:** `forecasted_daily_demand_norm`
- **Underlying Source:** Milestone 5 Tuned Tier 1 Random Forest model predictions for `2026-06-10`.
- **Preference Direction:** **Benefit** ($\uparrow$) — higher volume indicates greater public mobility reliance.
- **Formula:** Direct 1st–99th percentile normalized value ($x \in [0, 1]$).
- **Proposed Weight:** **$0.15$ (15%)**
- **Missing-Data Policy:** Strictly `NaN` on rail routes (evaluated only in Bus Priority and Combined tracks).
- **Interpretation:** Reflects total passenger throughput served by the route.
- **Potential Bias / Limitation:** Favors long, high-capacity trunk routes operating on major arterial grids over neighborhood circulators.

#### Criterion 1.2: Load Intensity Factor (Demand Pressure)
- **Physical Column:** `load_intensity_factor_norm`
- **Underlying Source:** Demand divided by scheduled trips and centerline route length:
  $$L_r = \frac{\text{forecasted\_daily\_demand}}{\text{scheduled\_trips} \times \text{route\_length\_km}} = \frac{\text{rides\_per\_trip}}{\text{route\_length\_km}}$$
- **Preference Direction:** **Benefit** ($\uparrow$) — higher load intensity indicates acute crowding risk, intense seat turnover, and high productivity per vehicle-kilometer.
- **Formula:** Direct 1st–99th percentile normalized value ($x \in [0, 1]$).
- **Proposed Weight:** **$0.20$ (20%)**
- **Missing-Data Policy:** Strictly `NaN` on rail routes.
- **Interpretation:** Distinguishes routes where vehicles operate consistently near or above capacity relative to corridor length from routes with high gross ridership that operate with excess capacity.
- **Potential Bias / Limitation:** Extremely short routes with modest demand can occasionally exhibit elevated ratios; protected by 99th-percentile clipping ($7.24 \text{ rides/trip/km}$).

---

### 3.2 Pillar 2: Operational Service Provision & Frequency (Total Weight: 25%)

#### Criterion 2.1: Scheduled Daily Trips
- **Physical Column:** `scheduled_trips_norm`
- **Underlying Source:** Phase 6.2 / GTFS `trips.txt` total scheduled runs on `2026-06-10`.
- **Preference Direction:** **Benefit** ($\uparrow$) — higher trip frequency indicates core transit service provision.
- **Formula:** Direct 1st–99th percentile normalized value ($x \in [0, 1]$).
- **Proposed Weight:** **$0.10$ (10%)**
- **Missing-Data Policy:** Non-null across all 133 routes ($100\%$ available).
- **Interpretation:** Measures transit supply commitment allocated by CTA schedule planners.
- **Potential Bias / Limitation:** High trips correlate with high demand ($r = 0.8900$); keeping weight moderate ($10\%$) avoids over-weighting raw fleet allocation.

#### Criterion 2.2: Daily Service Span
- **Physical Column:** `service_span_hours_norm`
- **Underlying Source:** Phase 6.2 difference between latest arrival and earliest departure in hours.
- **Preference Direction:** **Benefit** ($\uparrow$) — longer operating span ensures temporal accessibility across off-peak, evening, and night shifts.
- **Formula:** Direct 1st–99th percentile normalized value ($x \in [0, 1]$).
- **Proposed Weight:** **$0.05$ (5%)**
- **Missing-Data Policy:** Non-null across all 133 routes ($100\%$ available).
- **Interpretation:** Rewards routes offering 24-hour owl or extended 20+ hour daily operations.
- **Potential Bias / Limitation:** Most trunk lines offer 18–24 hour spans, so variance is concentrated in specialized or commuter express routes ($9.25\text{ to }25.22\text{ hours}$).

#### Criterion 2.3: Peak AM Service Frequency (Inverted Headway)
- **Physical Column:** `am_headway_min_norm`
- **Underlying Source:** Phase 6.2 mean consecutive departure interval between 07:00 and 09:00 AM.
- **Preference Direction:** **Cost** ($\downarrow$) $\rightarrow$ Inverted to **Benefit** ($\uparrow$):
  $$x_{\text{headway\_inv}} = 1.0 - \text{am\_headway\_min\_norm}$$
- **Proposed Weight:** **$0.10$ (10%)**
- **Missing-Data Policy:** Strictly `NaN` on Routes 10, 130, and N5. Handled via dynamic criterion weight masking (weight reallocated proportionally across remaining valid criteria).
- **Interpretation:** Shorter headway (e.g., 4–8 minutes) yields a transformed score near $1.0$, rewarding high-frequency rapid transit lines. Infrequent routes (headways $\ge 20$ minutes) yield scores near $0.0$.
- **Potential Bias / Limitation:** Captures AM peak only; does not reflect midday or weekend headways.

---

### 3.3 Pillar 3: Network & Transit Hub Connectivity (Total Weight: 20%)

#### Criterion 3.1: Transit Hub Stop Ratio
- **Physical Column:** `hub_stop_ratio_norm`
- **Underlying Source:** Phase 6.1 Top-100 spatial cluster transit hubs intersecting route stops:
  $$\text{hub\_stop\_ratio} = \frac{|\text{stops}_r \cap \text{Top100\_Hubs}|}{|\text{stops}_r|}$$
- **Preference Direction:** **Benefit** ($\uparrow$) — higher hub intersection indicates pivotal network connectivity and intermodal transfer utility.
- **Formula:** Direct 1st–99th percentile normalized value ($x \in [0, 1]$).
- **Proposed Weight:** **$0.20$ (20%)**
- **Missing-Data Policy:** Non-null across all 133 routes ($100\%$ available).
- **Interpretation:** Measures the degree to which a route feeds and circulates passengers through major CTA rail-bus transfer terminals and central transfer nodes.
- **Potential Bias / Limitation:** Rail routes exhibit $0.0$ in the current stop-level intersection table because rail station IDs were cataloged independently of street-level bus stops. Accounted for in subgroup handling.

#### Features Excluded from Pillar 3:
- `spatial_equity_indicator`: Constant value of $1.000$ across all 133 routes (zero variance). Assigned **$0.00$ weight**.
- `hub_weighted_importance`: Constant value of $0.000$ across all 133 routes (zero variance). Assigned **$0.00$ weight**.

---

### 3.4 Pillar 4: Corridor Co-Routing & Infrastructure Duplication (Total Weight: 20%)

#### Criterion 4.1: Corridor Duplication Index
- **Physical Column:** `corridor_duplication_index_norm`
- **Underlying Source:** Phase 6.3 composite synthesis of Phase 6.2 Frechet alignment similarity and shared consecutive stop sequences:
  $$D_r = 0.40 \cdot \text{max\_corridor\_overlap} + 0.30 \cdot \text{mean\_corridor\_overlap} + 0.30 \cdot \text{corridor\_duplication\_ratio}$$
- **Preference Direction:**
  - In **Operational Intervention Priority Mode (Default):** **Benefit** ($\uparrow$) — routes with high duplication represent primary targets for corridor rationalization, branching consolidation, or schedule synchronization to eliminate bus bunching.
  - In **Standalone Network Health Mode:** **Cost** ($\downarrow$, inverted to $1 - D_r$) — routes providing unique, un-duplicated transit coverage are rewarded.
- **Formula:** Direct 1st–99th percentile normalized value ($x \in [0, 1]$).
- **Proposed Weight:** **$0.20$ (20%)**
- **Missing-Data Policy:** Non-null across all 133 routes ($100\%$ available).
- **Interpretation:** Identifies routes heavily co-routed along shared transit boulevards (e.g., Michigan Avenue, State Street, Western Avenue) versus isolated grid corridors.
- **Potential Bias / Limitation:** Co-routing along high-density downtown trunks is often deliberate transit planning (trunk-and-branch); high duplication must be interpreted in conjunction with demand.

---

## 4. Multicollinearity & Redundancy Audit

To prevent artificial signal amplification, the table below documents the resolution of all correlated feature pairs:

| Candidate Feature Pair | Pearson $r$ | Chosen Feature | Excluded Feature | Methodological Justification |
| :--- | :---: | :---: | :---: | :--- |
| `forecasted_daily_demand` vs `historical_mean_daily_rides` | **0.9954** | `forecasted_daily_demand_norm` | `historical_mean_daily_rides_norm` | Retains the forward-looking ML model prediction for `2026-06-10`; prevents double-counting identical ridership signal. |
| `corridor_duplication_index` vs `max_corridor_overlap` | **0.9284** | `corridor_duplication_index_norm` | `max_corridor_overlap_norm` | Composite index already incorporates maximum overlap with audited weight ($0.40$); including both would inflate overlap. |
| `corridor_duplication_index` vs `mean_corridor_overlap` | **0.9332** | `corridor_duplication_index_norm` | `mean_corridor_overlap_norm` | Composite index already incorporates mean overlap ($0.30$); including both would double-count alignment similarity. |
| `corridor_duplication_index` vs `corridor_duplication_ratio` | **0.8935** | `corridor_duplication_index_norm` | `corridor_duplication_ratio_norm` | Composite index already incorporates shared stop ratio ($0.30$). |
| `scheduled_trips` vs `log_scheduled_trips` | **0.9107** | `scheduled_trips_norm` | `log_scheduled_trips` | Direct percentile normalization already stabilizes extreme values; raw linear scale provides superior intuitive explainability. |
| `rides_per_trip` vs `load_intensity_factor` | **0.5206** | `load_intensity_factor_norm` | `rides_per_trip_norm` | Load intensity factor normalizes rides per trip by route length ($\text{rides/trip/km}$), providing true capacity pressure rather than trip-length artifact. |
| `hub_stop_ratio` vs `hub_connectivity_index` | **1.0000** | `hub_stop_ratio_norm` | `hub_connectivity_index` | Because `hub_weighted_importance` was constant $0.0$, the composite index $H_r = 0.40 \cdot \text{hub\_stop\_ratio}$ is collinear with the ratio. Using `hub_stop_ratio_norm` directly is simpler and more transparent. |

---

## 5. Stakeholder Weight Profiles (Personas)

To provide actionable flexibility for different transit agency stakeholders, AI_RouteRanker supports four pre-configured weight profiles:

| Criterion Code | Feature Name | Profile A: Balanced Priority (Default) | Profile B: Overcrowding Relief | Profile C: Corridor Restructuring | Profile D: Network Essentiality |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **C1** | `forecasted_daily_demand_norm` | **15%** | **25%** | **15%** | **20%** |
| **C2** | `load_intensity_factor_norm` | **20%** | **30%** | **15%** | **15%** |
| **C3** | `scheduled_trips_norm` | **10%** | **10%** | **5%** | **15%** |
| **C4** | `service_span_hours_norm` | **5%** | **5%** | **5%** | **10%** |
| **C5** | `am_headway_min_norm` (inv) | **10%** | **10%** | **5%** | **15%** |
| **C6** | `hub_stop_ratio_norm` | **20%** | **10%** | **15%** | **20%** |
| **C7** | `corridor_duplication_index_norm` | **20%** | **10%** | **40%** | **5%** (inv) |
| | **Total Weight Sum** | **100%** | **100%** | **100%** | **100%** |

### Persona Descriptions:
- **Profile A (Balanced Operational Priority - Default):** Balances demand pressure, operational supply, hub connectivity, and structural duplication. Identifies major workhorse corridors requiring holistic operational oversight.
- **Profile B (Overcrowding & Capacity Relief):** Heavily weights passenger demand and load intensity factor ($55\%$ combined). Highlights overcrowded corridors where added articulated buses or short-turn runs are needed.
- **Profile C (Corridor Restructuring & Efficiency):** Prioritizes corridor duplication ($40\%$). Identifies overlapping routes with redundant alignments for potential route consolidation, stop spacing rationalization, or express/local splitting.
- **Profile D (Core Network Essentiality):** Focuses on vital transit connectivity and standalone service span. Inverts duplication to reward unique coverage lifelines.

---

## 6. Bus and Rail Subgroup Strategy

To prevent unfair distortion caused by the absence of route-level rail ridership in GTFS telemetry, the ranking engine supports three distinct evaluation tracks:

### Track 1: Bus Network Comprehensive Priority (125 Routes)
- Evaluates all 125 canonical bus routes using the full 7-criterion framework across all 4 pillars.
- Provides the authoritative ranking for CTA bus operations, fleet allocation, and corridor planning.

### Track 2: Heavy Rail Operational Priority (8 Routes)
- Evaluates the 8 heavy rail lines (`Red`, `Blue`, `Brn`, `G`, `Org`, `P`, `Pink`, `Y`) using operational supply and corridor infrastructure metrics:
  - `scheduled_trips_norm` ($30\%$)
  - `service_span_hours_norm` ($20\%$)
  - `am_headway_min_norm` (inv, $30\%$)
  - `corridor_duplication_index_norm` ($20\%$)
- Highlights operational intensity and frequency ranking among 'L' lines.

### Track 3: Unified Network-Wide Operational Supply (133 Routes)
- Evaluates all 133 transit routes on a level playing field using mode-agnostic operational supply metrics:
  - `scheduled_trips_norm` ($35\%$)
  - `service_span_hours_norm` ($20\%$)
  - `am_headway_min_norm` (inv, $25\%$)
  - `corridor_duplication_index_norm` ($20\%$)
- Enables agency-wide comparison of service frequency and operational commitment across both rail and bus networks.

---

## 7. Dynamic Weight Masking for Missing Criteria

For any route $r$ with missing values in criterion subset $M_{\text{missing}}(r)$, the engine executes dynamic weight renormalization:

1. Identify active valid criteria:
   $$V(r) = \{i \in \{1, \dots, 7\} \mid x_{r, i} \text{ is not NaN}\}$$
2. Compute the sum of valid base weights:
   $$W_{\text{valid}}(r) = \sum_{i \in V(r)} w_i$$
3. Re-scale valid weights:
   $$w_i'(r) = \frac{w_i}{W_{\text{valid}}(r)}, \quad \forall i \in V(r)$$
4. Compute final route score:
   $$S(r) = \sum_{i \in V(r)} w_i'(r) \cdot x_{r, i}$$

**Example on Specialized Route 130 (Missing Headway, Base $w_{\text{headway}} = 0.10$):**
- Valid base weights sum to $0.90$.
- Each remaining criterion weight is scaled by $1.0 / 0.90 \approx 1.1111$.
- Demand weight adjusts from $0.150 \rightarrow 0.167$; Load intensity adjusts from $0.200 \rightarrow 0.222$.
- The route is scored fairly based on its verified attributes without synthetic imputation penalties.

---

## 8. Conclusion

The criteria and weight framework provides an orthogonal, defensible, and fully explainable foundation for Milestone 7. We proceed to design the software architecture and module interfaces in `reports/phase7/phase7_architecture_plan.md`.
