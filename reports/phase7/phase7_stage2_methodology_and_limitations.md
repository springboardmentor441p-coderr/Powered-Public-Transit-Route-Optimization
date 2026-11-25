# AI_RouteRanker — Phase 7 Stage 2: Methodology & Limitations Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 7 — Module 5 Multi-Criteria Route Ranking Engine  
**Stage:** 2 — Canonical Execution & Empirical Verification  
**Document Type:** Methodological Rationale, Interpretation Standard & Operational Boundaries

---

## 1. Methodological Framework: Hierarchical Weighted Sum Model (WSM)

### 1.1 Mathematical Formulation
The primary production ranking engine utilizes the Hierarchical Weighted Sum Model (WSM). For any given transit route $r$, the composite priority score $S(r)$ is defined as the weighted linear combination of normalized criterion performances:

$$S(r) = \sum_{i=1}^{m} w_i^{\text{eff}} \cdot v_i(r)$$

where:
- $v_i(r) \in [0.0, 1.0]$ is the normalized criterion value for feature $i$.
- $w_i^{\text{eff}} \ge 0$ is the effective criterion weight, satisfying $\sum_{i=1}^{m} w_i^{\text{eff}} = 1.0$.

For hierarchical decomposition, criteria are grouped into four operational pillars ($P_k$):
$$S(r) = \sum_{k=1}^{4} P_k(r) = P_{\text{Demand}}(r) + P_{\text{Service}}(r) + P_{\text{Hub}}(r) + P_{\text{Corridor}}(r)$$

Each pillar score $P_k(r)$ represents the sum of criterion contributions $C_i(r) = w_i^{\text{eff}} \cdot v_i(r)$ assigned to that pillar.

### 1.2 Justification for WSM Selection
WSM was chosen over non-linear multi-criteria approaches (such as Outranking/ELECTRE or Analytic Hierarchy Process) due to:
1. **Mathematical Additivity & Explainability:** The exact contribution of each transit factor can be isolated and explained directly to transit planners in both absolute score units and percentages.
2. **Computational Determinism:** WSM executes in linear time $O(N \cdot m)$ without matrix inversions or iterative solvers, guaranteeing zero memory overflow risks on resource-constrained systems.
3. **Weight Transparency:** Planner-defined policy weights are preserved directly without subjective pairwise distortion.

---

## 2. Weight Design and Directional Alignment

### 2.1 Profile A (Balanced Network Default)
Profile A represents the default strategic evaluation profile approved for Module 5:

| Criterion Key | Pillar | Base Weight | Direction | Analytical Rationale |
| :--- | :--- | :---: | :---: | :--- |
| `forecasted_daily_demand_norm` | Demand Pressure | $0.20$ ($20\%$) | Benefit | Higher passenger volume warrants greater monitoring |
| `load_intensity_factor_norm` | Demand Pressure | $0.15$ ($15\%$) | Benefit | Higher passenger load per scheduled trip indicates capacity pressure |
| `scheduled_trips_norm` | Service Provision | $0.10$ ($10\%$) | Benefit | Higher trip frequency reflects operational trunk commitment |
| `service_span_hours_norm` | Service Provision | $0.05$ ($5\%$) | Benefit | Longer daily operating span represents core backbone service |
| `am_headway_min_norm` | Service Provision | $0.10$ ($10\%$) | Cost (Inverted) | Shorter peak headway represents intense high-frequency service |
| `hub_stop_ratio_norm` | Network Hubs | $0.20$ ($20\%$) | Benefit | Higher concentration of stops in designated transit hubs |
| `corridor_duplication_index` | Corridor Structure | $0.20$ ($20\%$) | Benefit | Higher corridor co-routing requires coordination scrutiny |

### 2.2 Crucial Interpretation Standard: High Corridor Duplication
> [!IMPORTANT]
> In Profile A, corridor duplication is formally classified as a **BENEFIT** indicator because the multi-criteria engine is designed to surface routes requiring operational review, coordination scrutiny, and bottleneck mitigation.
>
> A high duplication score **must never be interpreted as an automated finding or recommendation that a route should be reduced, eliminated, or consolidated**. In high-density transit systems like Chicago, high co-routing along radial arterial corridors (e.g., Michigan Avenue, Lake Shore Drive, Western Avenue) is often an intentional planning choice designed to concentrate high-capacity trunk capacity.

---

## 3. Modal Asymmetry & Multi-Track Separation

Bus and Heavy Rail systems exhibit fundamentally asymmetric operational dynamics:
- **Heavy Rail:** Grade-separated rights-of-way, fixed block signaling, 24/7 continuous operations on key lines (Red/Blue), multi-car trainsets, and station-based turnstile faregates.
- **Bus Network:** Surface street mixed-traffic operations, extensive curb stop networks, peak-only express routing, and high susceptibility to traffic congestion.

To prevent apples-to-oranges comparisons, the system strictly isolates evaluation across three independent tracks:
1. **Track 1 (Bus Network Priority):** Evaluates all 125 bus routes exclusively against one another.
2. **Track 2 (Heavy Rail Operational Priority):** Evaluates all 8 rail lines exclusively against rail operational standards with $0.0\%$ demand criteria weight.
3. **Track 3 (Unified Operational Supply):** Compares all 133 transit routes purely on operational supply characteristics (`scheduled_trips`, `service_span_hours`, `am_headway_min`, `corridor_duplication_index`), providing mode-agnostic supply benchmarking without demand model distortion.

---

## 4. Secondary Benchmarking Constraints (TOPSIS)

Technique for Order Preference by Similarity to Ideal Solution (TOPSIS) was implemented as an exploratory secondary benchmark. 

### 4.1 Methodological Considerations
TOPSIS calculates geometric Euclidean distances to synthetic Ideal ($A^+$) and Anti-Ideal ($A^-$) solutions:
$$C^*(r) = \frac{d^-(r)}{d^+(r) + d^-(r)}$$

In Euclidean space, missing features (such as missing AM headways for Routes 10, 130, N5) alter the dimensionality of the vector space, creating geometric distortions if evaluated alongside complete cases.

### 4.2 Benchmark Population Protocol
To maintain mathematical rigor:
- Comparative rank correlation statistics (Spearman $\rho$, Top-$k$ overlap) are computed strictly across **common complete-case populations** ($N=122$ for bus routes, $N=130$ for unified routes).
- TOPSIS is designated as an **exploratory secondary benchmark** and is not used to override or dictate canonical operational rankings.

---

## 5. Known Limitations & Operational Boundaries

1. **Temporal Horizon:** All metrics are based on a canonical static snapshot service date (`2026-06-10`) representing a standard summer weekday schedule. Seasonal and weekend variations are not reflected in this snapshot.
2. **Demand Uncertainty:** Demand metrics rely on Milestone 5 Random Forest predictive models. Model prediction intervals and residual uncertainties propagate into the demand pillar.
3. **Absence of Title VI / Equity Analysis:** The ranking engine evaluates operational and demand performance only. It does not perform federal Title VI disparate impact assessments or socio-economic demographic analyses.
4. **Non-Prescriptive Operational Status:** The engine is an investigative prioritization tool for human transit planners. Output ranks must not be used to trigger automated route cancellations, service cuts, or driver reassignment.
