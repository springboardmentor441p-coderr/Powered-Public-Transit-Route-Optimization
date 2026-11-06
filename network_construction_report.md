# Module 3: Chennai MTC Bus Network Construction Report
**Project:** RouteRanker for Chennai MTC Buses  
**Date:** 2026-11-06  
**Dataset Path:** `C:\Users\kavyasri\Downloads\mtc-gtfs`  
**Model Type:** Static GTFS Directed Weighted Network Graph (`networkx.DiGraph`)

---

## 1. Executive Summary

This report establishes **Module 3: Bus Network Construction** for RouteRanker.
Using NetworkX and Pandas, we modeled the entire scheduled transit operations of the Chennai Metropolitan Transport Corporation (MTC) as a directed, weighted graph $G = (V, E)$.

### Key Network Statistics
- **Total Network Nodes ($|V|$):** **5,580 bus stops** (5,477 active stops and 103 unserviced stops).
- **Total Directed Edges ($|E|$):** **12,521 unique directed stop-to-stop movements**.
- **Consecutive Trip Segments Aggregated:** **1,313,396 segment events** across all 47,047 scheduled trips.
- **Edge Weight Attribute:** **`median_travel_time_min`** (Mean: 2.94 min, Median: 2.0 min).
- **Strongly Connected Component (SCC):** **5,266 stops** (96.1% of active stops), indicating near-universal bi-directional reachability.
- **Data Validation:** 100% pass across all sequential, temporal, and topological integrity checks.

---

## 2. Graph Construction Methodology

### 2.1 Graph Definition
The transit network is modeled as a directed multi-attribute graph $G = (V, E)$:
1. **Nodes ($V$):** Every physical stop defined in `stops.txt` is ingested as a node with geographic coordinates (`stop_lat`, `stop_lon`) and `stop_name`.
2. **Edges ($E$):** A directed edge $e = (u, v)$ exists if and only if at least one scheduled trip moves directly from stop $u$ to stop $v$ in consecutive sequence along its timetable.

### 2.2 Segment Extraction & Travel Time Formulation
- All 1,360,443 rows in `stop_times.txt` were linked to `trips.txt` and `routes.txt`, sorted strictly by `(trip_id, stop_sequence)`.
- Consecutive stop pairs (u -> v) were extracted within trip boundaries:
  `delta_t = arrival_time(v) - departure_time(u)`
- Travel times were computed in elapsed seconds from midnight, natively supporting GTFS post-midnight trips (> 24:00:00).

### 2.3 Edge Attribute Aggregation
Multiple trips operating over the same directed pair $(u, v)$ were aggregated into edge attributes:
- `trip_count`: Total daily scheduled trips traversing the segment.
- `distinct_route_ids`: Number of distinct GTFS internal route variants.
- `distinct_route_shortnames`: Number of distinct public bus line numbers.
- `weight` / `median_travel_time_min`: Median scheduled travel time (used as the primary impedance weight for shortest-path algorithms).
- `min_travel_time_min`, `max_travel_time_min`, `mean_travel_time_min`: Operational travel time bounds.

---

## 3. Node Metrics & Connectivity Hierarchy

### 3.1 Node Degree Distribution
- **Mean In-Degree / Out-Degree:** 2.29 edges per active stop.
- **Median Degree:** 2 in-edges, 2 out-edges.
- **Maximum In-Degree:** 27 edges (Stop `5822`: M.G.R.Koyambedu Bus Terminus).
- **Maximum Out-Degree:** 20 edges (Stop `5822`: M.G.R.Koyambedu Bus Terminus).
- **Isolated Nodes (Degree 0):** Exactly **103 stops**, exactly matching the unserviced depot and obsolete stops identified in Module 1 and Module 2.

### 3.2 Top 15 Interchange Hubs by Public Bus Lines (`route_short_name`)

| Stop ID | Stop Name | Public Bus Lines | Internal Route IDs | In-Degree | Out-Degree | Daily Scheduled Visits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `5822` | M.G.R.Koyambedu Bus Terminus | **338** | 600 | 25 | 23 | 8,014 |
| `11159` | Island ground Terminus | **263** | 316 | 7 | 8 | 5,176 |
| `11158` | Royapuram terminus | **219** | 271 | 8 | 10 | 3,449 |
| `6693` | Tambaram West Bus Stand | **218** | 367 | 13 | 14 | 5,244 |
| `5785` | Chinnamalai Or Saidapet Court | **206** | 246 | 12 | 10 | 3,392 |
| `1048` | Concorde Or Chellammal College | **180** | 206 | 9 | 10 | 2,731 |
| `5788` | Little Mount | **178** | 199 | 8 | 10 | 2,250 |
| `5790` | Saidapet | **169** | 193 | 11 | 12 | 2,190 |
| `908` | Chellammal College | **167** | 191 | 9 | 9 | 2,575 |
| `9612` | Koyambedu Chathiram | **164** | 205 | 17 | 17 | 2,848 |
| `9991` | Kilambakkam Bus Terminus | **163** | 240 | 11 | 9 | 4,353 |
| `9805` | Parrys Corner | **150** | 153 | 9 | 8 | 2,556 |
| `9843` | Beach Station | **150** | 153 | 10 | 10 | 2,556 |
| `6553` | Perungalattur | **144** | 191 | 10 | 9 | 2,800 |
| `5650` | Panagal Maligai Or Saiadapet Bridge | **143** | 161 | 9 | 10 | 2,075 |

---

## 4. Top 15 Frequently Used Directed Segments

| From Stop | To Stop | Daily Trips | Public Lines | Route IDs | Median Travel Time |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `6435` Vandalur Zoo | `6490` Vandalur Gate | **2,739** | 119 | 156 | 2.0 min |
| `5822` M.G.R.Koyambedu Bus Terminus | `9612` Koyambedu Chathiram | **2,592** | 153 | 183 | 2.0 min |
| `9805` Parrys Corner | `9843` Beach Station | **2,556** | 150 | 153 | 1.0 min |
| `5547` Beach Station | `9793` Parrys Corner | **2,465** | 130 | 131 | 1.0 min |
| `6592` Irumbuliyur | `6693` Tambaram West Bus Stand | **2,188** | 93 | 122 | 4.0 min |
| `8421` Chromepet | `8464` Saravana Store Chromepet | **2,149** | 114 | 138 | 1.0 min |
| `8462` Saravana Store Chromepet | `8424` Chromepet | **2,107** | 115 | 143 | 1.0 min |
| `6565` Perungalatgur Lake View Stop | `6553` Perungalattur | **2,077** | 113 | 147 | 1.0 min |
| `6553` Perungalattur | `6528` Perungalathur Sriram Gate | **2,077** | 114 | 143 | 1.0 min |
| `5788` Little Mount | `5650` Panagal Maligai Or Saiadapet Bridge | **2,067** | 141 | 159 | 1.0 min |
| `5607` TN Open Univ / Panagal Maligai | `5785` Chinnamalai Or Saidapet Court | **2,067** | 134 | 155 | 2.0 min |
| `83` Mgr Central / RG Govt Gen Hosp | `100` Pallavan Salai | **2,036** | 110 | 112 | 2.0 min |
| `5650` Panagal Maligai Or Saiadapet Bridge | `5790` Saidapet | **2,013** | 137 | 156 | 1.0 min |
| `99` Pallavan Salai | `82` Mgr Central Railway Station | **2,004** | 116 | 120 | 2.0 min |
| `124` Simpson | `99` Pallavan Salai | **2,000** | 115 | 120 | 1.0 min |

---

## 5. Visualizations Generated

The following high-resolution figures were generated and saved into `reports/figures/`:
1. `fig7_network_overview.png`: 4-panel dashboard displaying In/Out-Degree distribution, degree symmetry, edge trip log-frequency, and segment travel times.
2. `fig8_top_stops_connectivity.png`: Grouped horizontal bar chart of top 15 stops comparing public bus lines (`route_short_name`) against internal route variants (`route_id`).
3. `fig9_top_directed_segments.png`: Horizontal bar chart of the top 15 most heavily trafficked directed segments.
4. `fig10_core_subnetwork_graph.png`: Geographic layout of Chennai's high-frequency arterial bus backbone (>= 750 trips/day, 312 directed edges) mapped onto actual $(lon, lat)$ coordinates.

---

## 6. Methodological Validation & Integrity Checks

| Validation Criterion | Expected Benchmark | Empirical Value | Verdict |
| :--- | :--- | :--- | :--- |
| **Consecutive Segment Event Records** | $1,360,443 - 47,047 = 1,313,396$ | **1,313,396** | **PASS (Exact)** |
| **Cross-Trip Edge Bleeding** | 0 edges cross trip boundaries | **0** | **PASS (Zero Bleed)** |
| **Negative Scheduled Travel Times** | 0 events with $\Delta t < 0$ | **0** | **PASS (Clean)** |
| **Self-Loop Segment Events** | 0 events where $u == v$ | **0** | **PASS (Clean)** |
| **Total Graph Nodes** | 5,580 nodes from `stops.txt` | **5,580** | **PASS (Complete)** |
| **Isolated Nodes (Degree 0)** | 103 unserviced stops | **103** | **PASS (Verified)** |
| **Unique Directed Graph Edges** | Derived from consecutive segments | **12,521** | **PASS** |
| **Strongly Connected Component Coverage** | Core giant component | **5,266 stops (96.1%)** | **PASS (Robust)** |

---

## 7. Dataset Limitations & Modeling Assumptions

1. **Static Scheduled Representation**:
   - The graph represents *scheduled timetable connectivity*, not live GPS tracking (AVL) or real-time traffic congestion.
2. **Missing `shapes.txt` Road Geometry**:
   - Directed edges connect stop coordinates via logical graph transitions. Straight lines in visualizations do not represent actual road curvature or turns.
3. **No Zero-Wait Transfer Assumption**:
   - Shared stops allow route interchange, but transfer wait times depend on connecting headway and pedestrian walking across curbs.
4. **No Real-Time Capacity / Demand Modeling**:
   - Trip frequencies reflect timetable supply authored by MTC, not passenger boarding demand or bus crowding.

---
**Report generated automatically by Module 3 analysis notebook.**
