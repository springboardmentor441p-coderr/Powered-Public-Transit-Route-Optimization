# Phase 6.2 Stage 2 — Canonical Real-Data Execution Report
## Spatial Route Corridor Clustering, Shared-Stop Connectivity, and Operational Typology

**Project:** AI_RouteRanker — AI-Powered Public Transit Route Optimization  
**Project Directory:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Execution Timestamp:** 2026-11-25 12:23:18 +05:30  
**Status:** **COMPLETE — ALL CHECKS PASSED**  
**Execution Environment:** Windows 11, Python 3.11.9, Scikit-learn 1.9.1, NumPy 2.4.6, Pandas 3.1.0, Shapely 2.2.0, DuckDB 2.0.0  

---

## 1. Executive Summary & Authorization Boundary

Phase 6.2 Stage 2 executed the canonical real-data experiment for spatial route clustering and route-level analysis across the Chicago Transit Authority (CTA) network under strict read-only database connections and absolute protection of Phase 6.1 and prior milestones.

### Key Analytical Achievements
1. **Pillar A — Spatial Corridor Similarity:**
   - Evaluated all **261 active route-direction patterns** with 100-meter buffered corridor overlap ratios and exact Discrete Fréchet distances.
   - Evaluated independent Hierarchical Agglomerative Clustering across $K \in [2, 12]$ using average linkage for both metrics. Max silhouette for Discrete Fréchet distance achieved at $K=2$ ($0.3204$).
2. **Pillar B — Shared-Stop & Network Connectivity:**
   - Extracted physical boarding-stop sets (`location_type = 0`) across 261 patterns.
   - Identified **950 contiguous shared consecutive stop sequences** of length $\ge 2$ (mean length: 5.23 stops, max length: 37 stops) using dynamic programming.
3. **Pillar C — Operational Route Typology:**
   - Evaluated operational $K$-Means clustering across $K \in [3, 7]$ across 5 canonical operational predictors.
   - Selected champion model at **$K=3$** with highest silhouette score of **$0.3814$** and inertia of $303.49$.
4. **Data Integrity & Quality Safeguards:**
   - Critical **W-01 safeguard** verified single-date homogeneity (`2026-06-10`) across 20,689 active trips.
   - Zero shape exclusions across all 261 active route-directions.
   - Unmapped rail routes (8 lines) preserved strictly as `NaN` without synthetic imputation.
5. **System Verification & Immutability:**
   - 34/34 focused Phase 6.2 tests passed in $0.657\text{s}$.
   - 157/157 full discovery tests passed in $15.196\text{s}$.
   - **All 22 protected baseline assets verified 100% bit-for-bit identical** against approved cryptographic SHA-256 baselines.

---

## 2. Canonical Data Sources & Experiment Configuration

| Parameter | Configuration Value | Canonical Source / Justification |
| :--- | :--- | :--- |
| **GTFS Snapshot ID** | `mdb-389-202605300003` | Approved canonical CTA transit snapshot |
| **Representative Service Date** | `2026-06-10` | Canonical Wednesday service date (W-01 compliant) |
| **Active Trip Filter** | GTFS calendar & calendar_dates | Trips with active Wednesday schedule and exception handling |
| **Spatial Projection** | EPSG:3435 (NAD83 / Illinois East) | Metric cartesian projection for Chicago transit |
| **Buffer Radius** | $100.0\text{ meters}$ | Approved transit corridor catchment radius |
| **Trajectory Downsampling** | $50.0\text{ meters}$ | Equidistant polyline downsampling for shape comparison |
| **Corridor Cluster Range** | $K \in [2, 12]$ | Hierarchical agglomerative clustering evaluation range |
| **Operational Cluster Range** | $K \in [3, 7]$ | $K$-Means operational typology candidate range |
| **AM Peak Window** | `07:00:00` to `09:00:00` ($[25200, 32400)$ sec) | Scheduled departures for peak headway extraction |
| **DuckDB Connection Mode** | `read_only = True` | Strict database write prohibition |

---

## 3. Route Population & Route-Direction Selection

The canonical transit network comprises 133 routes, all of which had active scheduled service on `2026-06-10`:

| Mode | Canonical GTFS Routes | Active Trips on 2026-06-10 | Active Route-Direction Patterns | Scheduled Boarding Visits |
| :--- | :---: | :---: | :---: | :---: |
| **Bus (`route_type = 3`)** | 125 | 18,728 | 245 | 1,105,745 |
| **Rail (`route_type = 1`)** | 8 | 1,961 | 16 | 101,532 |
| **Total CTA Network** | **133** | **20,689** | **261** | **1,207,277** |

*Note:* Directional patterns represent active `(route_id, direction_id)` pairs. 128 routes operate 2 directions ($128 \times 2 = 256$), and 5 routes operate a single circular or uni-directional service pattern ($5 \times 1 = 5$), totaling exactly 261 active patterns.

---

## 4. Shape Selection & Polyline Validation

Representative shapes were selected by identifying the shape ID with the highest scheduled trip count for each active route-direction pattern:

- **Total Active Route-Directions:** 261
- **Representative Shapes Selected:** 261
- **Shape Exclusions Count:** 0
- **Total Raw Polyline Vertices Fetched:** 279,449
- **Coordinate Validation:** All vertices bounded within Canonical Chicago bounding box ($[41.50, 42.25]^\circ\text{N}$, $[-88.10, -87.40]^\circ\text{W}$). Zero NaNs, zero duplicate sequence indices.
- **Downsampling Statistics ($50\text{m}$ spacing):**
  - Minimum vertices per polyline: 56
  - Mean vertices per polyline: 303.3
  - Maximum vertices per polyline: 896
  - Total downsampled trajectory vertices: 79,161

---

## 5. Pillar A — Spatial Corridor Similarity Results

Pairwise geometric similarity was evaluated across all $\frac{261 \times 260}{2} = 33,930$ unique pattern pairs under two independent formulations:

### 5.1 Metric Formulations
1. **100m Buffer Overlap Similarity:**
   $$\text{Overlap}(A, B) = \frac{\text{Area}(\text{Buffer}_{100\text{m}}(A) \cap \text{Buffer}_{100\text{m}}(B))}{\min(\text{Area}(\text{Buffer}_{100\text{m}}(A)), \text{Area}(\text{Buffer}_{100\text{m}}(B)))}$$
   Distance: $D_{\text{buffer}}(A, B) = 1.0 - \text{Overlap}(A, B)$.
2. **Discrete Fréchet Distance:**
   Exact coupling distance in meters computed via dynamic programming with $O(M)$ auxiliary memory and vectorized metric pairwise coordinate distances.

### 5.2 Hierarchical Agglomerative Clustering Evaluation ($K=2..12$, Average Linkage)

| $K$ | Buffer Overlap Silhouette | Buffer Min Cluster Size | Buffer Max Cluster Size | Discrete Fréchet Silhouette | Fréchet Min Cluster Size | Fréchet Max Cluster Size | Evaluation Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2** | 0.027800 | 66 | 195 | **0.320391 (Peak)** | 115 | 146 | VALID |
| **3** | 0.033717 | 14 | 195 | 0.251324 | 27 | 119 | VALID |
| **4** | 0.039663 | 14 | 195 | 0.193618 | 2 | 119 | VALID |
| **5** | 0.050200 | 14 | 149 | 0.201451 | 2 | 113 | VALID |
| **6** | 0.056021 | 14 | 149 | 0.218528 | 2 | 113 | VALID |
| **7** | 0.060872 | 8 | 141 | 0.229023 | 2 | 81 | VALID |
| **8** | 0.073796 | 8 | 95 | 0.240988 | 2 | 81 | VALID |
| **9** | 0.081104 | 8 | 95 | 0.267566 | 2 | 43 | VALID |
| **10** | 0.087371 | 8 | 95 | 0.296195 | 2 | 43 | VALID |
| **11** | 0.095348 | 8 | 95 | 0.282006 | 1 | 43 | VALID |
| **12** | 0.103447 | 2 | 95 | 0.280946 | 1 | 43 | VALID |

*Methodological Insight:* Discrete Fréchet distance cleanly partitions the network into a broad **North Chicago versus South Chicago geographic regional partition** at $K=2$ (Silhouette $= 0.3204$), governed by the spatial coordinate separation across the Chicago metropolitan area rather than trajectory grid orientation. Buffer overlap distances exhibit gradual sub-corridor partitioning up to $K=12$. Both distance structures are preserved independently in output matrices.

---

## 6. Pillar B — Shared-Stop & Network Route Connectivity Results

Network connectivity was analyzed exclusively across physical boarding stops (`location_type = 0`):

1. **Pairwise Jaccard Similarity Matrix:**
   $$J(A, B) = \frac{|S_A \cap S_B|}{|S_A \cup S_B|}$$
   Computed across all 261 patterns. High Jaccard values identify co-routed corridors (e.g., Michigan Avenue, Western Avenue, Halsted Street).
2. **Shared Consecutive Stop Sequences:**
   - Contiguous shared sub-sequences of length $\ge 2$ physical stops were identified using dynamic programming.
   - **Total Shared Consecutive Segments Found:** **950**
   - **Summary Distribution of Sequence Lengths:**
     - Minimum length: $2.0\text{ stops}$
     - 25th percentile: $2.0\text{ stops}$
     - Median length: $4.0\text{ stops}$
     - Mean length: $5.23\text{ stops}$
     - 75th percentile: $6.0\text{ stops}$
     - Maximum length: $37.0\text{ stops}$

---

## 7. Pillar C — Operational Route Typology & KMeans Evaluation

### 7.1 Operational Features Summary ($N=133$ Routes)
Features were extracted from scheduled GTFS operations on `2026-06-10`:

| Feature Name | Count | Mean | Std Dev | Min | Median | Max | Missing Count |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `log_scheduled_trips` | 133 | 4.847 | 0.711 | 2.398 | 4.963 | 6.127 | 0 |
| `service_span_hours` | 133 | 19.604 | 4.575 | 9.258 | 19.283 | 25.217 | 0 |
| `am_peak_mean_headway_min` | 130 | 12.587 | 5.281 | 4.773 | 10.987 | 30.000 | 3* |
| `route_length_km` | 133 | 15.543 | 7.609 | 3.128 | 14.921 | 44.741 | 0 |
| `unique_stops_count` | 133 | 107.429 | 55.118 | 6.000 | 111.000 | 254.000 | 0 |

*\*Data Quality Note:* All 133 canonical routes are represented in the route-level feature master (`route_level_operational_features.parquet`). Exactly 3 routes have missing AM peak mean headway values and were excluded from KMeans clustering without synthetic imputation, yielding $N=130$ clustered routes in `kmeans_operational_assignments.parquet`:
- **Route `10` (Museum of Science & Industry):** First service begins at 08:45 AM with only one scheduled trip in the AM peak window; consequently, 0 consecutive departure intervals exist at any stop-direction group to calculate headway.
- **Route `130` (Museum Campus):** First scheduled service commences at 09:27 AM; exactly 0 departures exist during the 07:00–09:00 AM peak window.
- **Route `N5` (South Shore Night Bus):** Dedicated overnight "owl" service operating 00:16–06:40 AM and after 19:00; exactly 0 departures exist during the 07:00–09:00 AM peak window.

### 7.2 KMeans Candidate Model Evaluation ($K \in [3, 7]$, StandardScaler, `n_init=10`, `random_state=42`)

| $K$ | Inertia | Silhouette Score | Evaluation Status | Recommendation |
| :---: | :---: | :---: | :---: | :--- |
| **3** | **303.4886** | **0.381425** | **VALID** | **CHAMPION MODEL (Highest Silhouette)** |
| 4 | 252.7438 | 0.278426 | VALID | Candidate |
| 5 | 209.2233 | 0.310025 | VALID | Candidate |
| 6 | 181.6986 | 0.310588 | VALID | Candidate |
| 7 | 156.1503 | 0.310186 | VALID | Candidate |

### 7.3 Champion Model ($K=3$) Cluster Profiles ($N=130$ Routes)

```
====================================================================================================
CHAMPION CLUSTER 0: High-Frequency Arterial Trunk Routes (N = 67: 66 Bus, 1 Rail)
====================================================================================================
Characteristics: High daily trip volume, comprehensive 24-hour service spans, frequent headways (~10 min).
  - log_scheduled_trips:       Mean = 5.32 (equiv. ~204 trips), Median = 5.30
  - service_span_hours:        Mean = 22.80 h, Median = 24.27 h
  - am_peak_mean_headway_min:  Mean = 10.30 min, Median = 9.89 min
  - route_length_km:           Mean = 17.01 km, Median = 16.42 km
  - unique_stops_count:        Mean = 144.2 stops, Median = 139.0 stops

====================================================================================================
CHAMPION CLUSTER 1: Community & Feeder Secondary Routes (N = 52: 51 Bus, 1 Rail)
====================================================================================================
Characteristics: Moderate trip counts, daytime-focused service span (~15.5 h), wider headways (~17.5 min).
  - log_scheduled_trips:       Mean = 4.30 (equiv. ~74 trips), Median = 4.41
  - service_span_hours:        Mean = 15.32 h, Median = 15.55 h
  - am_peak_mean_headway_min:  Mean = 16.63 min, Median = 17.52 min
  - route_length_km:           Mean = 10.25 km, Median = 9.05 km
  - unique_stops_count:        Mean = 70.3 stops, Median = 66.0 stops

====================================================================================================
CHAMPION CLUSTER 2: Long-Distance Regional & Heavy Rapid Transit (N = 11: 5 Bus, 6 Rail)
====================================================================================================
Characteristics: Long route corridors (>30 km), high service spans, ultra-frequent peak headways (~7.4 min).
  - log_scheduled_trips:       Mean = 4.92 (equiv. ~137 trips), Median = 4.98
  - service_span_hours:        Mean = 21.71 h, Median = 24.72 h
  - am_peak_mean_headway_min:  Mean = 7.43 min, Median = 7.67 min
  - route_length_km:           Mean = 31.91 km, Median = 30.66 km
  - unique_stops_count:        Mean = 62.2 stops, Median = 66.0 stops
====================================================================================================
```

### 7.4 Supplementary Ridership Preservation
- 125 bus routes mapped with historical average daily ridership.
- Exactly 8 rail routes ("Blue", "Brn", "G", "Org", "P", "Pink", "Red", "Y") have `mean_daily_rides = NaN`.
- Zero synthetic imputation or zero-filling was applied.

---

## 8. Data Quality & Exclusion Audits

| Metric / Check | Value | Status |
| :--- | :---: | :---: |
| Canonical GTFS Routes in Database | 133 | Complete |
| Active GTFS Routes on 2026-06-10 | 133 | Complete |
| Active Route-Direction Trajectories | 261 | Complete |
| Shape Exclusions Count | 0 | **PASS** |
| AM Headway Exclusions (Missing peak headway) | 3 ("10", "130", "N5") | Documented & Excluded |
| Routes Clustered in Operational KMeans | 130 | Complete |
| Unmapped Ridership Routes (Rail lines) | 8 | Documented as `NaN` |
| Bounding Box Latitude Violations | 0 | **PASS** |
| Bounding Box Longitude Violations | 0 | **PASS** |
| Duplicate Shape Sequence Records | 0 | **PASS** |

---

## 9. System Resources & Memory Guard Audits

The memory guard operated continuously throughout the 218-second execution session:

| Resource Metric | Baseline Threshold | Measured Initial | Measured Final | Guard Status |
| :--- | :---: | :---: | :---: | :---: |
| **Available Physical Memory** | $\ge 600.0\text{ MB}$ | $1,382.0\text{ MB}$ | $1,301.8\text{ MB}$ | **SAFE (Not Triggered)** |
| **Physical Memory Load** | $\le 95\%$ | $82\%$ | $83\%$ | **SAFE (Not Triggered)** |
| **Total Pipeline Wall Time** | $< 1800\text{ s}$ | — | $218.23\text{ s}$ | **EFFICIENT** |
| **DuckDB Connection Mode** | Read-Only | Read-Only | Closed | **SECURE (0 Writes)** |

---

## 10. Output Artifact Inventory

All 14 output artifacts were generated under `D:\B.TECH_PROJECTS\AI_RouteRanker\artifacts\route_clustering\` and verified present and non-empty:

| # | Artifact Filename | File Size | Description / Schema |
| :---: | :--- | :---: | :--- |
| 1 | `route_direction_geometries_metadata.parquet` | $19,105\text{ bytes}$ | Route-direction metadata, shape IDs, raw & downsampled point counts, trajectory length |
| 2 | `buffer_overlap_similarity_matrix.parquet` | $239,392\text{ bytes}$ | $261 \times 261$ pairwise 100m corridor buffer overlap ratio matrix ($\in [0, 1]$) |
| 3 | `buffer_distance_matrix.parquet` | $250,560\text{ bytes}$ | $261 \times 261$ pairwise buffer distance matrix ($1.0 - \text{overlap}$) |
| 4 | `frechet_distance_matrix.parquet` | $721,289\text{ bytes}$ | $261 \times 261$ pairwise exact Discrete Fréchet distance matrix (in meters) |
| 5 | `corridor_clustering_evaluation.csv` | $959\text{ bytes}$ | Evaluation metrics for hierarchical clustering on both distance matrices ($K=2..12$) |
| 6 | `corridor_cluster_assignments.parquet` | $28,995\text{ bytes}$ | Cluster assignments for all 261 route-directions across $K=2..12$ for both matrices |
| 7 | `route_direction_jaccard_matrix.parquet` | $191,412\text{ bytes}$ | $261 \times 261$ pairwise Jaccard shared-stop similarity matrix |
| 8 | `route_direction_shared_stops_matrix.parquet` | $171,148\text{ bytes}$ | $261 \times 261$ pairwise raw shared physical boarding stop count matrix |
| 9 | `shared_consecutive_stop_sequences.parquet` | $41,983\text{ bytes}$ | 950 identified contiguous shared physical stop sequence records ($\ge 2$ stops) |
| 10 | `route_level_operational_features.parquet` | $14,801\text{ bytes}$ | 133 route-level operational feature records with descriptive ridership metrics |
| 11 | `kmeans_operational_evaluation.csv` | $261\text{ bytes}$ | $K$-Means inertia, silhouette score, and validity status for $K \in [3, 7]$ |
| 12 | `kmeans_operational_assignments.parquet` | $18,347\text{ bytes}$ | 130 clustered routes with assignments across $K=3..7$ and champion cluster labels |
| 13 | `exclusion_and_quality_records.json` | $430\text{ bytes}$ | Audit manifest recording 0 shape exclusions and 8 unmapped rail lines |
| 14 | `phase6_2_stage2_metadata.json` | $3,601\text{ bytes}$ | Full reproducibility manifest with timestamps, configuration, and cluster profiles |

---

## 11. Comprehensive Unit Test & Regression Suite Verification

The complete project test suite was executed immediately following canonical artifact generation:

### Focused Suite (`tests/test_route_clustering.py`)
- **Total Tests:** 34
- **Passed:** 34
- **Failed:** 0
- **Execution Time:** $0.657\text{s}$
- **Coverage:** Complete coverage of geometry downsampling, buffer overlaps, discrete Fréchet distance symmetry, Jaccard stop connectivity, consecutive stop sequence dynamic programming, operational feature extraction, AM peak departures grouping, $K$-Means evaluations, degenerate cluster safeguards, and ridership `NaN` preservation.

### Full Discovery Suite (`tests/`)
- **Total Tests:** 157
- **Passed:** 157
- **Failed:** 0
- **Execution Time:** $15.196\text{s}$
- **Coverage:** Full project regression across all milestones (data ingestion, preprocessing, baselines, random forest modeling, hyperparameter tuning, Phase 6.1 stop clustering, Phase 6.2 route clustering).

---

## 12. Complete 22 Protected Baseline Asset Integrity Verification

All 22 protected assets across earlier milestones and Phase 6.1 were cryptographically audited via SHA-256 immediately post-execution:

| # | Protected File Path | Baseline SHA-256 Hash | Post-Run SHA-256 Hash | Status |
| :---: | :--- | :--- | :--- | :---: |
| 1 | `data/processed/features/model_ready_features.parquet` | `30980434303f7d8a...` | `30980434303f7d8a...` | **100% MATCH** |
| 2 | `artifacts/random_forest/tier1_random_forest.joblib` | `559936f8e200d67f...` | `559936f8e200d67f...` | **100% MATCH** |
| 3 | `artifacts/random_forest/tier2_random_forest.joblib` | `d688a9e10b120f49...` | `d688a9e10b120f49...` | **100% MATCH** |
| 4 | `artifacts/random_forest/tier1_random_forest_tuned.joblib` | `d73b790160124968...` | `d73b790160124968...` | **100% MATCH** |
| 5 | `artifacts/random_forest/tier2_random_forest_tuned.joblib` | `dafa999d181502d3...` | `dafa999d181502d3...` | **100% MATCH** |
| 6 | `data/processed/ai_routeranker.duckdb` | `ec0fd3626c6734fa...` | `ec0fd3626c6734fa...` | **100% MATCH** |
| 7 | `analytics/clustering/spatial_projection.py` | `64db44fec6ae647b...` | `64db44fec6ae647b...` | **100% MATCH** |
| 8 | `analytics/clustering/demand_aggregator.py` | `a05ccc2bcb66ede5...` | `a05ccc2bcb66ede5...` | **100% MATCH** |
| 9 | `analytics/clustering/stop_clustering.py` | `e9d3c025b0ecb0cc...` | `e9d3c025b0ecb0cc...` | **100% MATCH** |
| 10 | `analytics/clustering/evaluator.py` | `ec0d5cbe9010f077...` | `ec0d5cbe9010f077...` | **100% MATCH** |
| 11 | `tests/test_clustering.py` | `a778f66db6c5035d...` | `a778f66db6c5035d...` | **100% MATCH** |
| 12 | `artifacts/clustering/stop_level_feature_master.parquet` | `1c78779eaa99a9d7...` | `1c78779eaa99a9d7...` | **100% MATCH** |
| 13 | `artifacts/clustering/spatial_dbscan_assignments.parquet` | `3c7d40bcca545e14...` | `3c7d40bcca545e14...` | **100% MATCH** |
| 14 | `artifacts/clustering/peripheral_and_noise_stops.parquet` | `1b9ec0cbac8bbbe8...` | `1b9ec0cbac8bbbe8...` | **100% MATCH** |
| 15 | `artifacts/clustering/dbscan_chaining_diagnostics.parquet` | `2bae53207ae61139...` | `2bae53207ae61139...` | **100% MATCH** |
| 16 | `artifacts/clustering/kmeans_cluster_assignments.parquet` | `fca9a563bac59275...` | `fca9a563bac59275...` | **100% MATCH** |
| 17 | `artifacts/clustering/kmeans_candidate_evaluation.csv` | `e0cd587319b68bfe...` | `e0cd587319b68bfe...` | **100% MATCH** |
| 18 | `artifacts/clustering/transit_hub_rankings.parquet` | `20e1168913766963...` | `20e1168913766963...` | **100% MATCH** |
| 19 | `artifacts/clustering/top100_hubs_config_a.csv` | `201682c6587678e2...` | `201682c6587678e2...` | **100% MATCH** |
| 20 | `artifacts/clustering/top100_hubs_config_b.csv` | `beb0e6ca53c141ed...` | `beb0e6ca53c141ed...` | **100% MATCH** |
| 21 | `artifacts/clustering/top100_hubs_config_c.csv` | `7bf212ca1725f398...` | `7bf212ca1725f398...` | **100% MATCH** |
| 22 | `artifacts/clustering/phase6_1_stage2_metadata.json` | `4b4cd002a309538c...` | `4b4cd002a309538c...` | **100% MATCH** |

**Zero baseline contamination:** All 22 protected files maintain bit-for-bit identity ($100\%$ verification).

---

## 13. Operational Interpretations & Boundary Limitations

1. **Physical Stop Sharing vs Service Redundancy:**
   Shared stops and high Jaccard indices reflect shared roadway/track infrastructure, multi-modal transfer corridors, or trunk-feeder confluence. They do not imply redundant service without headway, demand, and transfer synchronization analysis.
2. **Buffer Overlap vs Route Competition:**
   $100\text{m}$ buffer overlap measures spatial proximity of trajectories in the Chicago grid. Parallel routes (e.g., adjacent grid streets 0.5 miles apart) do not overlap at $100\text{m}$, while routes merging onto shared boulevards exhibit localized overlap.
3. **KMeans Typology vs Performance Ranking:**
   KMeans clusters represent descriptive operational profiles (trunk, community feeder, regional express). They are not evaluative ratings or efficiency rankings.
4. **Transition to Phase 6.3:**
   Phase 6.3 (Route Ranker Integration) is strictly contingent upon formal user sign-off on the Phase 6.2 Stage 2 outputs and report. Phase 6.3 has not been started.
