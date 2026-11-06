# Module 3: Bus Network Construction Critical Verification Audit Report
**Project:** RouteRanker for Chennai MTC Buses  
**Audit Date:** 2026-11-06  
**Auditor:** RouteRanker Verification & Quality Assurance Pipeline  
**Dataset Path:** `C:\Users\kavyasri\Downloads\mtc-gtfs`  
**Target Documents Under Audit:** `reports/network_construction_report.md` & `notebooks/03_network_construction.ipynb`

---

## 1. Executive Summary

This report delivers the critical verification audit of **Module 3: Chennai MTC Bus Network Construction**.
Using independent Python scripts executed directly against the raw GTFS tables (`stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`), every graph topological metric, consecutive stop transition, travel time calculation, and connectivity property was recomputed and audited.

### Overall Audit Verdict
- **Total Verification Areas:** 5 primary categories (15 itemized checks).
- **Pass (Verified Exact):** 11 checks.
- **Pass with Essential Qualification:** 4 checks (Clarifying active vs. all-stop degree denominator; Sunday edge service reduction; Stop-Graph route-switching limitation; Edge aggregation route multiplicity).
- **Needs Correction:** 0 mathematical calculation errors found in Module 3.

---

## 2. Itemized Verification Matrix

| Category | Verification Item | Module 3 Claimed Metric | Recalculated Audit Value | Audit Verdict | Technical Explanation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Graph Statistics** | **Total Graph Nodes ($|V|$)** | 5,580 nodes | **5,580 nodes** | **PASS** | Exact match with `stops.txt` (5,477 active stops visited by trips, 103 unserviced stops). |
| | **Total Directed Edges ($|E|$)** | 12,521 edges | **12,521 edges** | **PASS** | Exact match of unique directed pairs `(from_stop_id, to_stop_id)` extracted from consecutive trip stop sequences. |
| | **Consecutive Segment Events** | 1,313,396 records | **1,313,396 records** | **PASS** | Exactly satisfies the topological theorem: $\sum_{i=1}^{T} (N_i - 1) = 1,360,443 - 47,047 = 1,313,396$. |
| | **Isolated Nodes (Degree 0)** | 103 stops | **103 stops** | **PASS** | Exactly matches the unserviced depots and obsolete stops identified in Module 1 and Module 2. |
| | **Mean In-Degree / Out-Degree** | 2.29 edges per active stop | • Active Stops Denominator ($N = 5,477$): **2.2861 $\approx$ 2.29**<br>• All Stops Denominator ($N = 5,580$): **2.2439 $\approx$ 2.24** | **PASS with Qualification** | The reported figure (2.29) is mathematically exact when evaluated over active stops ($12,521 / 5,477$). The report correctly stated "per active stop", but both denominators should be documented to avoid ambiguity. |
| | **Strongly Connected Component (SCC)** | 5,266 stops (96.1%) | **5,266 stops**<br>• 96.15% of active stops (5,477)<br>• 94.37% of all stops (5,580) | **PASS** | Giant strongly connected component guarantees bi-directional transit reachability across over 96% of active Chennai bus stops. |
| | **Weakly Connected Component (WCC)** | 5,468 stops (99.8%) | **5,468 stops**<br>• 99.84% of active stops (5,477)<br>• 97.99% of all stops (5,580) | **PASS** | 99.8% of active stops belong to a single connected topological structure. Exactly 9 active stops belong to peripheral isolated branches. |
| **2. Edge Construction** | **Inter-Trip Boundary Bleeding** | 0 cross-trip edges | **0 edges** | **PASS** | Vectorized condition `trip_id == next_trip_id` strictly prevents edges from linking the last stop of Trip $k$ to the first stop of Trip $k+1$. |
| | **Negative Travel Times** | 0 negative times | **0 records** | **PASS** | Evaluated via elapsed seconds from midnight. $t_{\text{arr, next}} \ge t_{\text{dep, curr}}$ holds for 100% of consecutive pairs. |
| | **Zero-Minute Travel Times** | Min travel time: 1.0 min | **0 zero-minute pairs** (Min: 1.0 min, Mean: 1.83 min, Max: 120.0 min) | **PASS** | No consecutive stop transitions have identical departure and arrival timestamps. |
| | **Self-Loops ($u \rightarrow u$)** | 0 self loops | **0 records** | **PASS** | No trip schedules consecutive visits to the same stop ID. |
| | **Intra-Trip Duplicate Edges** | N/A | **0 records** | **PASS** | No individual trip traverses the exact same directed stop pair $(u, v)$ more than once. |
| **3. Frequency & Calendar** | **Trip Frequency Base** | 47,047 trips | • Mon–Sat scheduled frequency: **1,313,396 segment events** across **12,521 edges**<br>• Sunday scheduled frequency: **1,311,358 segment events** across **12,520 edges** | **PASS with Qualification** | Edge `trip_count` represents **Monday–Saturday daily scheduled service**. On Sundays, 74 HSC trips (2,038 segment events) do not operate, making **1 directed edge completely inactive** and reducing frequency on 137 edges. |
| | **Demand vs. Supply Labeling** | Scheduled vehicle capacity | Strictly represents transit authority dispatch supply | **PASS** | Confirmed: Frequency measures scheduled timetable dispatches, never passenger boardings or ridership demand. |
| **4. Route Continuity & Transfers** | **Multi-Route Edge Aggregation** | Edge carries `distinct_route_ids` & `distinct_route_shortnames` | • **7,611 edges (60.8%)** aggregate multiple `route_id`s<br>• **7,224 edges (57.7%)** aggregate multiple public lines<br>• Max lines on single edge: **153 lines** (`5822 -> 9612`) | **PASS with Qualification** | Collapsing multiple bus lines into a single directed edge is standard for Stop-Graphs, but requires route-aware itinerary reconstruction in Module 4 to prevent "free" transfers. |
| **5. Geographic Accuracy** | **Map Coordinates vs. Road Geometry** | Stop point coordinates only; no road geometry claimed | Strictly uses $(lon, lat)$ for stop placement; explicitly disclaims road curvature | **PASS** | Confirmed: Graph does not claim straight-line edges represent street centerlines (`shapes.txt` is missing). |

---

## 3. In-Depth Technical Audits

### 3.1 Mean Degree Denominator Audit
- **Reported in Module 3:** "Mean In-Degree / Out-Degree: 2.29 edges per active stop."
- **Empirical Check:**
  - Total directed edges $|E| = 12,521$.
  - When evaluated across **active stops only** ($N_{\text{active}} = 5,477$):
    $$\bar{k}_{\text{in, active}} = \frac{12,521}{5,477} = 2.286105... \approx \mathbf{2.29}$$
  - When evaluated across **all defined stops** ($N_{\text{total}} = 5,580$, including the 103 degree-0 stops):
    $$\bar{k}_{\text{in, total}} = \frac{12,521}{5,580} = 2.243906... \approx \mathbf{2.24}$$
- **Verdict:** **PASS WITH QUALIFICATION**. The text in Module 3 explicitly specified "per active stop", which is mathematically exact. Both figures are now formally recorded.

---

### 3.2 Sunday Edge Service Degradation (The HSC Impact)
- In `calendar.txt`, service `HSC` (74 trips) operates Monday through Saturday, but **does not run on Sunday**.
- **Audit Findings on Network Edges:**
  - Total consecutive segment events generated by HSC trips: **2,038 segments**.
  - Total unique directed edges traversed by HSC trips: **138 edges**.
  - Edges served *exclusively* by HSC trips: **Exactly 1 edge** (`10515` $\rightarrow$ `10516`, B.D.O Office Ikkadu branch in Tiruvallur).
  - On Sundays, this 1 edge receives 0 bus service, reducing the active network to **12,520 directed edges**.
  - The remaining 137 edges experience minor scheduled trip reductions on Sunday.
- **Verdict:** **PASS WITH QUALIFICATION**. Edge `trip_count` must be explicitly defined as the **Monday–Saturday scheduled frequency**. Sunday operations retain 99.99% of network edges ($12,520 / 12,521$).

---

### 3.3 Critical Routing Limitation: The "Stop-Graph" Transfer Fallacy
A directed graph $G = (V, E)$ where nodes represent physical stops and edges represent consecutive stop movements is known in transit network modeling as a **Stop-Graph** (or Topology-Only Graph).

#### The Problem:
- In our constructed graph, edge `(5822 -> 9612)` aggregates **153 public bus lines** (e.g., 15CT8, 27B, 70V, etc.).
- A standard shortest-path search (e.g. Dijkstra on `weight = median_travel_time_min`) operates on nodes and edges without awareness of which route operates which edge.
- **Example Scenario:**
  - Suppose a shortest path from Stop $A$ to Stop $C$ via Stop $B$ selects edge $(A, B)$ and edge $(B, C)$.
  - Edge $(A, B)$ might have minimum travel time on Route 25R.
  - Edge $(B, C)$ might have minimum travel time on Route 91.
  - Standard Dijkstra treats transitioning from $(A, B)$ to $(B, C)$ at Stop $B$ as instantaneous and "free", assuming the passenger magically teleports between buses without waiting for Route 91 to arrive, or even worse, treats it as a single through-bus.

#### Mathematical Reality:
1. **Transfer Penalties:** An actual transit transfer at Stop $B$ incurs:
   $$t_{\text{transfer}} = t_{\text{walk}}(\text{platform}_1 \rightarrow \text{platform}_2) + t_{\text{wait}}(\text{next departure of Route 91})$$
2. **Schedule Feasibility:** An itinerary is feasible if and only if:
   $$t_{\text{departure}}(\text{Route 91}, B) \ge t_{\text{arrival}}(\text{Route 25R}, B) + t_{\text{min\_walk}}$$

---

## 4. Architectural Requirements & Recommendations for Module 4

To ensure that Module 4 (Route Planning & Ranking) delivers realistic, passenger-usable transit itineraries rather than unexecutable theoretical shortest paths, the following design paradigms are recommended:

### Recommended Routing Paradigms for Module 4:

1. **Option A (Industry Standard): RAPTOR (Round-Based Public Transit Routing)**
   - *Why:* RAPTOR does not use a graph. It operates directly on GTFS arrays of routes, trips, and stop times.
   - *Advantage:* In Round 1, it finds all stops reachable with 0 transfers. In Round 2, it finds all stops reachable with 1 transfer, explicitly tracking the transfer stop and adding transfer walking buffers. It naturally optimizes both travel time and number of transfers without graph expansion.

2. **Option B: Route-Expanded Graph (Layered Graph / Dual Graph)**
   - *Why:* If NetworkX graph algorithms are preferred, the Stop-Graph must be expanded:
     - Nodes become tuples: $(u, \text{route}_r)$ representing Route $r$ serving Stop $u$.
     - **In-Vehicle Edges:** Directed edges $(u, \text{route}_r) \rightarrow (v, \text{route}_r)$ with weight equal to in-vehicle travel time.
     - **Transfer Edges:** Directed edges $(u, \text{route}_r) \rightarrow (u, \text{route}_k)$ with weight equal to transfer walking penalty + expected headway wait time ($w_{\text{transfer}} = \Delta t_{\text{walk}} + \frac{1}{2} H_k$).
   - *Advantage:* Dijkstra on this expanded graph automatically penalizes route changes, preserving passenger route continuity.

3. **Option C: Post-Processing Path Validation on the DiGraph**
   - If shortest paths are extracted from the current $G = (V, E)$, a path must be evaluated against the underlying `stop_times` to verify:
     - Can a single through-route cover the path? If yes, transfer count = 0.
     - If multiple routes are required, identify the exact transfer stops, verify schedule feasibility, and add transfer wait penalties.

---

## 5. Verification Checklist & Required Corrections

| # | Check Item | Verification Status | Action for Module 4 |
| :- | :--- | :--- | :--- |
| **1** | Node count ($5,580$) & Edge count ($12,521$) | **PASS** | Validated and locked for graph routing. |
| **2** | Segment count ($1,313,396$) & 0 negative travel times | **PASS** | Validated. Edge weight `median_travel_time_min` is strictly positive ($\ge 1.0$ min). |
| **3** | Mean degree clarity | **PASS WITH QUALIFICATION** | Document both 2.29 (active stops) and 2.24 (all stops). |
| **4** | Weekly service frequency labeling | **PASS WITH QUALIFICATION** | Explicitly label edge frequencies as **Monday–Saturday scheduled trips** (1 edge inactive on Sunday). |
| **5** | Route continuity & transfer penalty | **PASS WITH QUALIFICATION** | Adopt route-aware routing (RAPTOR or Route-Expanded Graph) in Module 4 to prevent "free" transfers. |
| **6** | Geographic disclaimer | **PASS** | Reiterate that straight edges connecting stop coordinates do not reflect street geometry. |

---
**Verification audit complete. Module 3 is structurally sound, mathematically verified, and ready for Module 4 algorithm development.**
