# PHASE 6.1 STAGE 2 — CANONICAL SPATIAL STOP CLUSTERING & TRANSIT HUB IDENTIFICATION REPORT
**Project:** AI_RouteRanker – AI-Powered Public Transit Route Optimization  
**Repository Directory:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Execution Environment:** Windows 11, Python 3.11.9, CPU-only, 8 GB Physical RAM  
**Execution Date:** 2026-11-24  
**Status:** Canonical Stage 2 Execution Complete  

---

## 1. Executive Summary

Phase 6.1 Stage 2 executed the approved spatial and functional clustering methodology on the canonical Chicago Transit Authority (CTA) General Transit Feed Specification (GTFS) dataset using read-only database connections and memory-safe processing.

The pipeline generated four independent analytical outputs:
1. **Geographic Stop Clusters (DBSCAN):** 117 dense spatial clusters and 18 unclustered/noise stops across the 11,020 physical boarding stops. Chaining diagnostics identified 7 chained clusters, including the primary contiguous Chicago street grid cluster (Cluster 0, comprising 10,192 stops).
2. **Functional Stop Typologies (K-Means):** Evaluated $K \in [3, 8]$ across the 10,583 eligible boarding stops using five standardized operational attributes. Approximate represented-population-weighted silhouette scoring across 5 fixed seeds identified $K=3$ as the mathematical silhouette peak ($0.4222 \pm 0.0023$), with $K=7$ ($0.4073 \pm 0.0024$) providing a secondary granular operational typology.
3. **Individual Transit Hub Rankings:** Evaluated eligible stops across Configurations A (Balanced), B (Connectivity), and C (Demand Intensity). Identified candidate transit hubs meeting the $\text{HubScore} \ge 0.90$ and $\text{routes\_served} \ge 5$ threshold (Stop `1106` [Michigan & Washington] ranked #1 across all three configurations). Sensitivity analysis revealed strong concordance between Configs A and B ($r_s = 0.9891$, Top-100 Jaccard $0.9048$), with moderate divergence when demand intensity is weighted in Config C ($r_s = 0.7589$, Top-100 Jaccard $0.5152$).
4. **Peripheral and Low-Density Coverage Analysis:** Analyzed 18 spatial noise stops ($0.16\%$), 53 zero-visit stops ($0.48\%$), and network periphery distances (P95 distance to network center of gravity: $19.61\text{ km}$).

---

## 2. Canonical Dataset Verification

- **GTFS Snapshot Identifier:** `mdb-389-202605300003` (VERIFIED DATASET FACT).
- **Representative Service Date:** `2026-06-10` (Wednesday, VERIFIED DATASET FACT).
- **Demand Attribution Period:** `2025-11-23` through `2026-04-23` (152 calendar days, VERIFIED DATASET FACT).
- **Active Service Calendars on 2026-06-10:** 49 active service IDs.
- **Active Scheduled Trips on 2026-06-10:** 20,689 scheduled trips.
- **Scheduled Stop Visits at Boarding Stops:** 1,207,277 scheduled arrival/departure events.
- **Route Mapping Matches:** 125 exact-match mapped routes in snapshot `mdb-389-202605300003`. 124 routes had active ridership records in the Tier 2 period (Route 10 had zero scheduled service in Tier 2).

---

## 3. Boarding-Stop Population Reconciliation

The canonical GTFS stop hierarchy in snapshot `mdb-389-202605300003` was partitioned strictly by `location_type`:

| Stop Type (`location_type`) | Count | Status in Phase 6.1 |
| :--- | :--- | :--- |
| **Physical Boarding Stops (`location_type=0`)** | **11,020** | **Primary Analytical Population (100.00%)** |
| Parent Stations (`location_type=1`) | 143 | Excluded from stop clustering (Station level) |
| Entrances / Exits (`location_type=2`) | 14 | Excluded from stop clustering (Access points) |
| **Total GTFS Stops in Snapshot** | **11,177** | **100.00% Fully Reconciled** |

Every single one of the 11,020 boarding stops was mapped, projected, and clustered without loss or duplication.

---

## 4. Demand Attribution Coverage and Conservation

Demand attribution follows the approved proportional formula:
$$D_s = \sum_{r \in \mathcal{R}_{\text{mapped}}} \bar{Y}_r \times \frac{v_{sr}}{V_r}$$

- **Network-Wide Attributable Daily Demand ($\sum \bar{Y}_r$):** 535,580.32 estimated boardings / day across 124 mapped routes.
- **Total Demand Attributed to Stops ($\sum D_s$):** 535,580.32 estimated boardings / day.
- **Conservation Delta:** Exactly $0.0000$ passengers ($\Delta < 10^{-6}$, perfect numerical conservation).
- **Demand Coverage Classification:**
  - `COMPLETE` Coverage (all served routes mapped): 10,583 stops ($96.03\%$).
  - `PARTIAL` Coverage (served by at least 1 mapped and 1 unmapped route): 139 stops ($1.26\%$).
  - `UNAVAILABLE` Coverage (zero mapped routes served or zero visits): 298 stops ($2.70\%$).

---

## 5. Scheduled Headway Window Results

Headways were calculated independently per `(stop_id, route_id, direction_id, service_date)` within half-open $[start, end)$ operational windows. Trips beyond 24:00 were preserved as continuous integer seconds.

| Window Name | Clock Interval | Start (s) | End (s) | Active Stops | Median (min) | Mean (min) | Min (min) | Max (min) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **AM Peak** | 07:00:00 – 08:59:59 | 25,200 | 32,400 | 10,881 | 10.82 | 12.02 | 3.76 | 30.00 |
| **Midday** | 09:00:00 – 15:59:59 | 32,400 | 57,600 | 10,938 | 13.45 | 16.05 | 5.00 | 393.50 |
| **PM Peak** | 16:00:00 – 17:59:59 | 57,600 | 64,800 | 10,885 | 11.28 | 12.20 | 3.85 | 31.82 |
| **Evening** | 18:00:00 – 21:59:59 | 64,800 | 79,200 | 10,780 | 14.90 | 15.04 | 5.90 | 45.00 |
| **Overnight** | 22:00:00 – 28:59:59 | 79,200 | 104,400 | 8,781 | 19.30 | 18.83 | 6.27 | 38.76 |

*(Note: Scheduled headway reflects scheduled timetable vehicle spacing, not actual passenger waiting times).*

---

## 6. Stop Eligibility Waterfall

The stop eligibility waterfall evaluated the 11,020 boarding stops under strict priority rules:

| Priority | Category | Stop Count | Percentage | Definition & Rule |
| :---: | :--- | :---: | :---: | :--- |
| 1 | `EXCLUDED_ZERO_VISITS` | 53 | 0.48% | Total scheduled visits $v_s = 0$ on 2026-06-10 |
| 2 | `EXCLUDED_UNAVAILABLE_DEMAND` | 298 | 2.70% | Demand $D_s$ is NULL (no mapped routes) |
| 3 | `EXCLUDED_NO_AM_HEADWAY` | 86 | 0.78% | $< 2$ visits in AM Peak window ($[25,200, 32,400)$) |
| 4 | `EXCLUDED_NON_FINITE_FEATURE` | 0 | 0.00% | Any non-finite feature (NaN/Inf) |
| 5 | **`ELIGIBLE`** | **10,583** | **96.03%** | Complete, finite 5-feature vector |
| **TOTAL** | **Reconciled Total** | **11,020** | **100.00%** | **Mutually exclusive & 100% reconciled** |

Secondary diagnostic flags recorded:
- `flag_zero_visits`: 53 stops ($0.48\%$)
- `flag_unavailable_demand`: 298 stops ($2.70\%$)
- `flag_no_am_headway`: 139 stops ($1.26\%$) (86 primary + 53 co-occurring with zero visits)
- `flag_partial_demand`: 139 stops ($1.26\%$)

---

## 7. Geographic Stop Clustering (DBSCAN) & Chaining Diagnostics

- **Configuration:** $\text{eps} = 300\text{ meters}$, $\text{min\_samples} = 2$, Metric: Projected Euclidean $(x, y)$.
- **Total Valid Clusters Formed:** 117 clusters.
- **Clustered Stops:** 11,002 stops ($99.84\%$).
- **Unclustered Noise Stops (`label = -1`):** 18 stops ($0.16\%$).
- **Chaining Diagnostics:** A cluster is flagged with a chaining warning if $\text{Diameter} > 1,500\text{ m}$ OR $\text{Stop Count} > 50$.
  - **Chained Clusters Flagged:** 7 clusters ($5.98\%$ of clusters).
  - **Macro-Cluster 0:** Contains 10,192 stops, spanning a diameter of $47.78\text{ km}$ across the contiguous Chicago street grid. This confirms that DBSCAN operates as a spatial proximity detector, not a transit network partitioner.
  - **Other Chained Clusters:** Cluster 9 ($N=96$, $\text{diam}=5.5\text{ km}$), Cluster 13 ($N=78$, $\text{diam}=5.4\text{ km}$), Cluster 17 ($N=59$, $\text{diam}=2.7\text{ km}$), Cluster 21 ($N=50$, $\text{diam}=4.4\text{ km}$), Cluster 7 ($N=33$, $\text{diam}=2.8\text{ km}$), Cluster 19 ($N=19$, $\text{diam}=1.9\text{ km}$).

---

## 8. Functional Stop Typology (K-Means) Candidate Evaluation

Evaluated across the 10,583 eligible stops using 5 standardized operational features: $[\ln(v_s + 1), \text{routes\_served}, \bar{H}_{s, \text{AM}}, D_s, \text{service\_span\_hours}]$ with `StandardScaler`, `random_state=42`, and `n_init=10`.

Sampled silhouette scores were computed across 5 seeds (`[42, 101, 2024, 777, 9999]`) with sample size 3,000 using the Hamilton–Hare Largest Remainder Method:

| Candidate $K$ | Inertia | Sampled Silhouette ($\mu \pm \sigma$) | Score Min | Score Max | Unweighted Reference $\mu$ | Evaluated Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **$K = 3$** | **22,881.46** | **0.4222 ± 0.0023** | **0.4192** | **0.4251** | **0.3952** | **VALID EVALUATION** |
| $K = 4$ | 17,770.20 | 0.3753 ± 0.0045 | 0.3697 | 0.3801 | 0.3601 | VALID EVALUATION |
| $K = 5$ | 14,453.92 | 0.3874 ± 0.0082 | 0.3755 | 0.3945 | 0.3541 | VALID EVALUATION |
| $K = 6$ | 12,796.34 | 0.3846 ± 0.0043 | 0.3789 | 0.3907 | 0.3421 | VALID EVALUATION |
| **$K = 7$** | **11,296.07** | **0.4073 ± 0.0024** | **0.4042** | **0.4116** | **0.3475** | **VALID EVALUATION** |
| $K = 8$ | 10,231.15 | 0.4053 ± 0.0032 | 0.4005 | 0.4097 | 0.3424 | VALID EVALUATION |

### Typology Selection Analysis
- **Global Silhouette Peak:** $K=3$ achieves the highest sampled silhouette score ($0.4222 \pm 0.0023$). It partitions the transit network into three coarse operational tiers: High-Frequency Core Arterials, Standard Local Service, and Low-Frequency Outliers.
- **Granular Typology Peak:** $K=7$ achieves the second-highest silhouette score ($0.4073 \pm 0.0024$) while reducing inertia by $50.6\%$ relative to $K=3$. It resolves nuanced operational stop roles (e.g., Downtown Multi-Route Spines, Express Corridors, Feeder Loops).
- All candidates $K=3$ through $K=8$ are preserved in [`kmeans_cluster_assignments.parquet`](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/artifacts/clustering/kmeans_cluster_assignments.parquet).

---

## 9. Transit Hub Rankings across Locked Configurations

Evaluated across the 10,583 eligible stops using the three approved configurations:
- **Config A (Balanced):** $\text{Score}_A = 0.40 \cdot \tilde{v} + 0.35 \cdot \tilde{R} + 0.25 \cdot \tilde{D}$
- **Config B (Connectivity):** $\text{Score}_B = 0.25 \cdot \tilde{v} + 0.55 \cdot \tilde{R} + 0.20 \cdot \tilde{D}$
- **Config C (Demand Intensity):** $\text{Score}_C = 0.30 \cdot \tilde{v} + 0.30 \cdot \tilde{R} + 0.40 \cdot \tilde{I}$, where $\tilde{I}$ is the robust min-max normalized demand intensity $I_s = D_s / v_{s, \text{mapped}}$.

### Top 10 Candidate Transit Hubs (Ranked by Config A)

| Rank (A) | Stop ID | Stop Name | Score (A) | Rank (B) | Score (B) | Rank (C) | Score (C) | Visits ($v_s$) | Routes ($R_s$) | Demand ($D_s$) | Intensity ($I_s$) |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | **1106** | **Michigan & Washington** | **1.0000** | **1** | **1.0000** | **1** | **0.8665** | 854 | 12 | 543.1 | 0.636 |
| **2** | **73** | Michigan & Van Buren/Ida B. Wells | 0.8720 | 2 | 0.8827 | 4 | 0.7867 | 737 | 11 | 453.8 | 0.616 |
| **3** | **1103** | Michigan & Hubbard (Wrigley Bldg.) | 0.8220 | 3 | 0.8512 | 2 | 0.8043 | 633 | 11 | 451.3 | 0.713 |
| **4** | **1122** | Michigan & Hubbard (Tribune Bldg.) | 0.8200 | 4 | 0.8497 | 3 | 0.8017 | 632 | 11 | 448.0 | 0.709 |
| **5** | **1102** | Michigan & Illinois | 0.7844 | 5 | 0.7972 | 5 | 0.7754 | 625 | 10 | 447.0 | 0.715 |
| **5** | **1101** | Michigan & Ohio | 0.7844 | 5 | 0.7972 | 5 | 0.7754 | 625 | 10 | 447.0 | 0.715 |
| **7** | **1123** | Michigan & Grand | 0.7824 | 7 | 0.7957 | 7 | 0.7728 | 624 | 10 | 443.7 | 0.711 |
| **8** | **2816** | 95th Street & Michigan | 0.7639 | 8 | 0.7744 | 14 | 0.6095 | 748 | 11 | 208.5 | 0.279 |
| **9** | **448** | Washington & State | 0.7429 | 9 | 0.6713 | 13 | 0.6231 | 721 | 7 | 466.2 | 0.647 |
| **10** | **1120** | Michigan & South Water | 0.7330 | 10 | 0.7371 | 9 | 0.7303 | 626 | 9 | 403.6 | 0.645 |

### Tier 1 Candidate Hub Identification ($\text{Score} \ge 0.90$ and $\text{Routes} \ge 5$)
- **Configuration A:** 1 candidate hub (Stop `1106` [Michigan & Washington], Score 1.0000, 12 routes).
- **Configuration B:** 1 candidate hub (Stop `1106` [Michigan & Washington], Score 1.0000, 12 routes).
- **Configuration C:** 0 candidate hubs meet $\text{Score} \ge 0.90$ (Stop `1106` score is 0.8665 due to robust min-max scaling of demand intensity).
- **Interpretation:** These stops represent candidate transit hubs identified by the project's multi-criteria weighting methodology, not officially designated transit hubs.

---

## 10. Ranking Sensitivity Analysis

Evaluating ranking consistency across the 10,583 eligible stops:

- **Spearman Rank Correlations ($r_s$):**
  - $r_s(\text{Config A}, \text{Config B}) = \mathbf{0.9891}$ (Very strong alignment between balanced and connectivity emphasis).
  - $r_s(\text{Config A}, \text{Config C}) = \mathbf{0.7589}$ (Moderate-strong alignment; demand intensity shifts ranks of high-volume transfer stops).
  - $r_s(\text{Config B}, \text{Config C}) = \mathbf{0.7310}$.
- **Top 100 Jaccard Overlaps ($J$):**
  - $J(\text{Config A}, \text{Config B}) = \mathbf{0.9048}$ (95 overlapping stops in Top 100).
  - $J(\text{Config A}, \text{Config C}) = \mathbf{0.5152}$ (68 overlapping stops in Top 100).
  - $J(\text{Config B}, \text{Config C}) = \mathbf{0.5267}$ (69 overlapping stops in Top 100).
- **Interpretation:** Rankings are highly stable between Balanced and Connectivity weightings, but sensitive to whether demand is evaluated in raw volume ($D_s$) versus intensity per vehicle visit ($I_s$).

---

## 11. Peripheral and Low-Density Coverage Findings

Continuous spatial and operational coverage metrics:
- **Unclustered DBSCAN Noise Stops:** 18 stops ($0.16\%$). Located at extreme outer terminal branches (e.g., O'Hare remote gates, Hegewisch/South Chicago industrial borders).
- **Zero-Visit Stops:** 53 stops ($0.48\%$). Physical boarding stops with zero scheduled arrivals on Wednesday 2026-06-10 (weekend-only or seasonal service stops).
- **Unavailable Demand Stops:** 298 stops ($2.70\%$). Stops served exclusively by unmapped routes.
- **Missing AM Headway Stops:** 86 active stops ($0.78\%$) had only 1 scheduled trip during the 2-hour AM Peak window.
- **Distance to Network Center of Gravity ($41.8587^\circ\text{N}, -87.7150^\circ\text{W}$):**
  - Mean Distance: $11.23\text{ km}$
  - 90th Percentile: $17.65\text{ km}$
  - 95th Percentile: $19.61\text{ km}$
  - Maximum Distance: $27.91\text{ km}$
- *(Note: These metrics report continuous geometric distance and service availability. They do not classify demographic transit deserts without external socio-economic data).*

---

## 12. Memory and Runtime Performance

- **Environment Memory:** 7.74 GB Total RAM; Available RAM throughout execution remained between $758.1\text{ MB}$ and $2,503.2\text{ MB}$.
- **Memory Guard:** The 600 MB abort threshold was never breached. System load peaked at $90\%$ and normalized to $70\%$ post-clustering.
- **Total Pipeline Execution Time:** **61.27 seconds**.

---

## 13. Output File Inventory & Record Counts

All Stage 2 analytical outputs were saved in dedicated directories without overwriting any pre-existing files:

| File Path | Format | Record Count | Description |
| :--- | :--- | :--- | :--- |
| `artifacts/clustering/spatial_dbscan_assignments.parquet` | Parquet | 11,020 rows | Projected $(x, y)$ coordinates and DBSCAN cluster labels for all stops. |
| `artifacts/clustering/dbscan_chaining_diagnostics.parquet` | Parquet | 117 rows | Cluster diameter, bounding box, radius of gyration, and chaining warnings. |
| `artifacts/clustering/stop_level_feature_master.parquet` | Parquet | 11,020 rows | Complete master dataset: demand, 5 headway windows, eligibility, and scores. |
| `artifacts/clustering/kmeans_cluster_assignments.parquet` | Parquet | 10,583 rows | Cluster assignments for all candidate $K \in [3, 8]$ on eligible stops. |
| `artifacts/clustering/kmeans_candidate_evaluation.csv` | CSV | 6 rows | Inertia, silhouette mean/std, and validation status for $K=3$ through $8$. |
| `artifacts/clustering/transit_hub_rankings.parquet` | Parquet | 10,583 rows | Scores and ranks for Configs A, B, and C across eligible stops. |
| `artifacts/clustering/top100_hubs_config_a.csv` | CSV | 100 rows | Human-readable Top 100 candidate hubs under Config A (Balanced). |
| `artifacts/clustering/top100_hubs_config_b.csv` | CSV | 100 rows | Human-readable Top 100 candidate hubs under Config B (Connectivity). |
| `artifacts/clustering/top100_hubs_config_c.csv` | CSV | 100 rows | Human-readable Top 100 candidate hubs under Config C (Demand Intensity). |
| `artifacts/clustering/peripheral_and_noise_stops.parquet` | Parquet | 18 rows | Spatial noise stops and peripheral distance metrics. |
| `artifacts/clustering/phase6_1_stage2_metadata.json` | JSON | 1 file | Comprehensive run metadata, parameter records, and memory checkpoints. |

---

## 14. Testing and Post-Execution Integrity

- **Unit Test Suite:** Ran full project test discovery (`python -m unittest discover tests -v`).
  - **Results:** **123 / 123 tests passed** in $6.879\text{s}$ with zero failures, zero errors, and zero warnings.
- **Protected Artifact Immutability:** SHA-256 hashes matched pre-change baselines exactly:
  - `model_ready_features.parquet`: `30980434303f7d8a96b55338572a245c479bacd3abb581cd9d7bf2b417e8b95f` (**PASS**)
  - `tier1_random_forest.joblib`: `559936f8e200d67f29d56f6c40ad1748b15d012b25ca44ed6d1ce0d1120db3c9` (**PASS**)
  - `tier2_random_forest.joblib`: `d688a9e10b120f4998e8bff6dfd8ffca94c771db5db1947b0f71cd6360af9b2e` (**PASS**)
  - `tier1_random_forest_tuned.joblib`: `d73b79016012496809f9bc2dc3e05db686d5894f02a55d859a42f91052af1508` (**PASS**)
  - `tier2_random_forest_tuned.joblib`: `dafa999d181502d35098944c97009458f7f79bbefa3be0542e39b41b07ab40b5` (**PASS**)
  - `ai_routeranker.duckdb`: Size 1,007,169,536 bytes, mtime `1795175665.555737` (**PASS**, untouched).

---

## 15. Limitations & Methodological Constraints

1. **Proxy Nature of Demand:** Demand $D_s$ represents route-level ridership proportionally attributed via vehicle visit frequency. It does not measure actual boardings or alighting counts per physical stop.
2. **Headway vs. Waiting Time:** Headway measures scheduled timetable spacing between trips. It does not reflect vehicle punctuality, delays, or actual passenger waiting times.
3. **Proximity vs. Connectivity:** DBSCAN groups stops by Euclidean distance ($300\text{ m}$), not actual transit network routing or walking connectivity.
4. **Candidate Hubs vs. Official Hubs:** Hub scores reflect analytical multi-attribute criteria and are intended for transit planning review, not as official agency designations.

---

## 16. Confirmation of Phase Boundary

Phase 6.1 Stage 2 is complete. **Phase 6.2 has NOT been started.** No route-level clustering, network optimization, or dashboard integration has been executed.

---

```
================================================================================
PHASE 6.1 STAGE 2 — EXECUTION COMPLETE
PHASE 6.2 — NOT STARTED
AWAITING USER APPROVAL
================================================================================
```
