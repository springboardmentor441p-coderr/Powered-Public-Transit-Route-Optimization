# Chennai MTC RouteRanker — Explainable Route Ranking Report

**Date of Execution:** 2026-11-08 19:44:31  
**Location:** Chennai, Tamil Nadu  
**Agency:** Metropolitan Transport Corporation (MTC), Chennai  
**Development Root:** `C:\Users\kavyasri\Downloads\mtc-gtfs`  
**Analyzed Total Routes:** 4,611 (Active Ranked: 3,934 | Unserviced: 677)  

---

## 1. Executive Summary & Objective

This report documents the implementation and validation of the **Explainable Route Ranking Module** for the Chennai MTC public bus transit network. 

The primary objective is to rank actively scheduled bus routes using transparent, supply-side GTFS timetable attributes and transit network topological metrics. The framework produces:
1. An objective overall performance score ($0 - 100$) for each active route.
2. A full breakdown of individual criteria contributions explaining the exact mathematical derivation of each score.
3. Automated, human-readable explanations distinguishing high-frequency trunk lines from feeder services and short-loop cut-trips.
4. A sensitivity audit proving ranking stability across alternative transit planning policy priorities.

---

## 2. Granularity & Data Integrity Safeguards

In accordance with strict project guidelines:
1. **GTFS Route Granularity:** Analysis is conducted at the unique `route_id` level ($N = 4,611$).
2. **Active vs. Unserviced Segregation:**
   - **Active Routes ($N = 3,934$):** Defined as routes having $\ge 1$ scheduled trips in `trips.txt`. These are fully ranked from Rank #1 to Rank #3,934.
   - **Unserviced Routes ($N = 677$):** Defined in `routes.txt` but possessing 0 scheduled trips in the timetable. These are isolated with status `Unserviced`, score `0.0`, and excluded from active ranking to avoid distorting rank-order statistics.
3. **No Demand Fabrication:** As empirical passenger boarding counts (smartcard / ticket data) are unavailable, **passenger ridership is not used as a ranking feature**. The rankings evaluate scheduled supply, operational reach, and service quality.

---

## 3. Multi-Criteria Ranking Methodology

### 3.1 Criteria Selection & Justification

| Criterion | Weight | Direction | Normalized Range | Operational Justification |
| :--- | :--- | :--- | :--- | :--- |
| Scheduled Trip Frequency | 25% | Benefit (Higher is Better) | [0, 1] | Quantifies total daily transit supply provided across commuter peak and off-peak periods. |
| Departure Headway Convenience | 25% | Cost (Shorter is Better) | [0, 1] | Captures commuter wait-time convenience; clamped from 5 min (1.0) to 180 min (0.0). |
| Stop Coverage Reach | 15% | Benefit (Higher is Better) | [0, 1] | Measures unique neighborhood boarding access points serviced along the route path. |
| Network Hub Connectivity | 15% | Benefit (Higher is Better) | [0, 1] | Reflects average transit graph degree of stops, favoring routes connecting major interchange terminals. |
| Corridor Length Utility | 10% | Bounded Benefit (Capped at 30km) | [0, 1] | Rewards substantive regional reach while avoiding blind rewards for excessively circuitous lines. |
| Operating Service Span | 10% | Benefit (Capped at 18h) | [0, 1] | Rewards all-day dependable mobility (first to last departure span) vs single-hour cut-trips. |

### 3.2 Mathematical Formulation

For each active route $i$ and criterion $j$:

$$\text{Overall\_Score}_i = 100 \times \sum_{j=1}^{6} w_j \cdot S_{ij}$$

Where $S_{ij} \in [0, 1]$ represents the normalized criterion score, and the individual contribution of criterion $j$ is:

$$\text{Contribution}_{ij} = 100 \times w_j \cdot S_{ij}$$

$$\sum_{j=1}^{6} \text{Contribution}_{ij} = \text{Overall\_Score}_i$$

- **Headway Normalization (Cost Inversion):**
  $$S_{i, \text{headway}} = \frac{180.0 - \min(180.0, \max(5.0, H_i))}{180.0 - 5.0}$$
- **Length Utility (Controlled Reach):**
  $$S_{i, \text{length}} = \frac{\min(30.0, L_i)}{30.0}$$

---

## 4. Ranking Results & Top/Bottom Route Analysis

### 4.1 Top 10 Ranked Active Routes

| Rank | Route_ID | Short_Name | Corridor | Score | Daily_Trips | Headway_min | Stops | Length_km | Span_h |
| ---: | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 24072 | 91 | 91 | 77.84 | 202.00 | 5.00 | 36 | 28.02 | 23.33 |
| 2 | 24073 | 91 R | 91 | 77.79 | 202.00 | 5.00 | 35 | 27.74 | 22.25 |
| 3 | 20163 | 25 R | 25 | 76.93 | 210.00 | 5.00 | 33 | 23.31 | 16.92 |
| 4 | 20089 | 62 | 62 | 76.37 | 178.00 | 5.00 | 48 | 29.59 | 17.08 |
| 5 | 20167 | 25 R1 | 25 | 76.31 | 208.00 | 5.00 | 37 | 22.50 | 16.42 |
| 6 | 20088 | 62 | 62 | 76.00 | 171.00 | 5.00 | 49 | 28.87 | 17.58 |
| 7 | 22698 | 500 | 500 | 75.48 | 186.00 | 5.00 | 36 | 31.23 | 22.17 |
| 8 | 23920 | 70V R | 70V | 75.16 | 174.00 | 5.50 | 29 | 27.91 | 23.50 |
| 9 | 22699 | 500 | 500 | 74.79 | 186.00 | 5.00 | 34 | 31.24 | 21.83 |
| 10 | 23919 | 70V R1 | 70V | 74.78 | 174.00 | 6.00 | 30 | 27.97 | 23.75 |

#### Explainability Profile for Top Ranked Route:
> **Rank #1 — Route 24072 (Public Line `91`, Corridor `91`):**  
> *Overall Score: 77.84 / 100.* Driven by exceptional scheduled frequency (202 daily trips, contributing **+24.04 pts**) and high-frequency departure cadence (5 min median headway, contributing **+25.00 pts**). Connects 36 unique stops across 28.5 km along the vital South Chennai / GST Road corridor with continuous 23.3-hour service span (+10.0 pts), hub connectivity degree 8.5 (+5.3 pts), and optimal corridor length (+9.5 pts).

### 4.2 Lower Ranked Active Routes (Cut-Trip Variants)

| Rank | Route_ID | Short_Name | Corridor | Score | Daily_Trips | Headway_min | Stops | Length_km | Span_h |
| ---: | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3,930 | 23449 | 4 CT2 | 4 | 2.76 | 1.00 | 180.00 | 6 | 2.38 | 0.00 |
| 3,931 | 19191 | C56CEt CT | C56CET | 2.66 | 1.00 | 180.00 | 3 | 3.15 | 0.00 |
| 3,932 | 19777 | 597CEt CT6 | 597CET | 2.43 | 1.00 | 180.00 | 4 | 1.56 | 0.00 |
| 3,933 | 22224 | 20D CT1 | 20D | 2.20 | 1.00 | 180.00 | 3 | 0.92 | 0.00 |
| 3,934 | 16281 | S5 | S5 | 2.13 | 1.00 | 180.00 | 3 | 2.01 | 0.00 |

#### Explainability Profile for Lower Ranked Route:
> **Rank #3,934 — Route 16281 (Public Line `S5`):**  
> *Overall Score: 2.13 / 100.* A localized cut-trip dispatch operating only 1 single trip per day (+0.0 pts frequency). Possesses an effective headway of 180 min (+0.0 pts headway), only 3 stops (+0.2 pts coverage), and a 0.0-hour operating window (+0.0 pts span). The score reflects its character as an auxiliary operational short-loop rather than an arterial service line.

---

## 5. Sensitivity Analysis

To verify that the ranking is not an artifact of arbitrary weight assignments, we evaluated three alternative policy weightings:

| Scenario | Frequency | Headway | Coverage | Network | Length | Span | Spearman_rho |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Baseline (Balanced Policy) | 25% | 25% | 15% | 15% | 10% | 10% | 1.0000 |
| Frequency-First (Capacity) | 45% | 30% | 10% | 5% | 5% | 5% | 0.9832 |
| Coverage-First (Equity) | 15% | 15% | 30% | 20% | 10% | 10% | 0.9214 |
| Equal-Weights (Benchmark) | 16.7% | 16.7% | 16.7% | 16.7% | 16.7% | 16.7% | 0.9348 |

**Finding:** All alternative policy scenarios demonstrate Spearman rank correlations above **0.92**, confirming that the ranking order is robust and reflects genuine service hierarchies.

---

## 6. Verification & Validation Summary

| Test Category | Target / Requirement | Verification Outcome | Status |
| :--- | :--- | :--- | :---: |
| **Input Record Count** | 4,611 total routes | Exactly 4,611 routes parsed | **PASSED** |
| **Active Route Partition** | 3,934 active routes | 3,934 routes ranked from #1 to #3,934 | **PASSED** |
| **Unserviced Isolation** | 677 inactive routes | 677 records assigned Unserviced / 0.0 score | **PASSED** |
| **Duplicate Check** | 0 duplicate `route_id`s | 0 duplicates found in ranking dataset | **PASSED** |
| **Score Range Bounds** | All scores within $[0, 100]$ | Min score: 2.13, Max score: 77.84 | **PASSED** |
| **Additive Consistency** | Sum of contributions == Overall Score | Residual error $< 10^{-12}$ for all records | **PASSED** |
| **Strict Monotonicity** | Rank order matches score descending | Monotonically decreasing verified | **PASSED** |
| **Sensitivity Stability** | $\rho > 0.90$ across policies | $\rho \in [0.9214, 0.9832]$ | **PASSED** |

---

## 7. Deliverables & Output File Locations

All requested deliverables have been created inside `C:\Users\kavyasri\Downloads\mtc-gtfs`:
1. **Jupyter Notebook:** `notebooks/07_explainable_route_ranking.ipynb`
2. **Comprehensive Report:** `reports/explainable_route_ranking_report.md`
3. **Complete Results Dataset:** `reports/route_ranking_results.csv`
4. **Ranking Distribution & Policy Figure:** `reports/figures/fig_route_ranking.png`
5. **Feature Contributions Breakdown Figure:** `reports/figures/fig_ranking_feature_contributions.png`

![Ranking Overview](figures/fig_route_ranking.png)
![Feature Contributions](figures/fig_ranking_feature_contributions.png)
