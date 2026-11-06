# Module 4: Route Planning and Optimization Report
**Project:** RouteRanker for Chennai MTC Buses  
**Date:** 2026-11-06  
**Dataset Path:** `C:\Users\kavyasri\Downloads\mtc-gtfs`  
**Algorithm:** Timetable-Aware RAPTOR (Round-Based Public Transit Routing)

---

## 1. Executive Summary

This report establishes **Module 4: Route Planning and Optimization** for RouteRanker.
Addressing the critical routing limitations identified in the Module 3 verification audit, we replaced naive graph shortest paths with the industry-standard **RAPTOR algorithm** (Delling et al., 2012).

### Key Architectural Highlights
- **Guaranteed Route Continuity**: Solves the "Stop-Graph" transfer fallacy. Bus route changes are explicitly constrained to transfer points.
- **Multi-Criteria Optimization**: Generates Pareto-optimal itineraries balancing total journey duration against number of transfers ($k = 0, 1, 2$).
- **Calendar-Aware Scheduling**: Dynamically filters active trips for Monday–Saturday vs. Sunday operations.
- **GTFS Timetable Precision**: Computes real-world boarding, alighting, in-vehicle travel, and transfer waiting times down to the minute.
- **Post-Midnight Handling**: Successfully routes late-night trips continuing into hours 24 and 25 without modulo errors.

---

## 2. RAPTOR Algorithm Design & Implementation

### 2.1 Theoretical Overview
Unlike Dijkstra on a Stop-Graph, RAPTOR operates directly on the timetable:
1. **Route Pattern Indexing**: The 47,047 trips in the Chennai MTC dataset are indexed into **3,491 unique route patterns** (unique stop sequences).
2. **Round-Based Progression**:
   - Round 1 ($k=1$): Finds all stops reachable with **0 transfers** (direct bus).
   - Round 2 ($k=2$): Finds all stops reachable with **1 transfer** (2 bus legs).
   - Round 3 ($k=3$): Finds all stops reachable with **2 transfers** (3 bus legs).
3. **Transfer Modeling**: Enforces a minimum pedestrian buffer of **180 seconds (3 minutes)** between connecting legs.
4. **Earliest Arrival Tracking**: A trip is boarded at stop $p$ only if its departure is >= arrival time from the previous round + transfer buffer.

---

## 3. Empirical Scenario Test Results

### Scenario 1: Direct Trunk Journey (0 Transfers)
- **Route Corridor:** Anna Square (`495`) to Poonamallee (`9440`)
- **Query Departure:** `08:00:00` (Monday morning peak)
- **Itinerary Result:**
  - Board Line **`25R`** at Anna Square at **08:00:00**
  - Alight at Poonamallee at **09:04:00**
  - **Total Duration:** 64.0 minutes (In-vehicle: 64.0 min, Initial Wait: 0.0 min, Transfers: 0)

### Scenario 2: Multi-Leg Journey with Transfer Optimization
- **Route Corridor:** Thiruvanmiyur Bus Stand (`5908`) to Redhills Bus Terminus (`5578`)
- **Query Departure:** `08:00:00` (Monday morning peak)
- **Pareto-Optimal Journey Options Generated:**
  1. **Option 1 (Fastest Duration, 2 Transfers):**
     - Leg 1: Line `1C CT2` from Thiruvanmiyur (08:05:00) to Simpson (08:35:00)
     - Transfer: 4 min wait at Simpson
     - Leg 2: Line `2A R` from Simpson (08:39:00) to Padmanaba Theatre (08:47:00)
     - Transfer: 8 min wait at Padmanaba Theatre
     - Leg 3: Line `57` from Padmanaba Theatre (08:55:00) to Redhills (09:23:00)
     - **Total Duration:** **83.0 minutes** (Transfers: 2)
  2. **Option 2 (Fewer Transfers, 1 Transfer via Koyambedu Hub):**
     - Leg 1: Line `78` from Thiruvanmiyur (08:15:00) to M.G.R.Koyambedu Bus Terminus (08:50:00)
     - Transfer: 5 min transfer buffer at Koyambedu
     - Leg 2: Line `114` from Koyambedu (08:55:00) to Redhills Bus Terminus (09:32:00)
     - **Total Duration:** **92.0 minutes** (Transfers: 1)
- **Key Insight:** Option 2 takes 9 minutes longer (92 min vs 83 min) but requires only **1 single transfer** at Chennai's largest bus terminal (Koyambedu), making it the preferred passenger choice.

### Scenario 3: Missed-Bus / Later Departure Sensitivity
- **Query Departure:** `08:30:00` (30 minutes after Scenario 2)
- **Itinerary Result:**
  - **Leg 1:** Line `78` departs Thiruvanmiyur Bus Stand at **08:35:00** → alights M.G.R. Koyambedu Bus Terminus at **09:10:00** (ride: 35 min)
  - *Transfer 1:* Koyambedu wait **15 min** (09:10:00 to 09:25:00, transfer buffer $\ge 180\text{ s}$)
  - **Leg 2:** Line `113 CT` departs Koyambedu at **09:25:00** → alights Puzhal Camp at **09:45:00** (ride: 20 min)
  - *Transfer 2:* Puzhal Camp wait **3 min** (09:45:00 to 09:48:00, transfer buffer $= 180\text{ s}$)
  - **Leg 3:** Line `242 CT10` departs Puzhal Camp at **09:48:00** → arrives Redhills Bus Terminus at **09:55:00** (ride: 7 min)
  - **Total Duration:** **85.0 minutes** (62 min in-vehicle + 5 min initial wait + 18 min transfer wait) | **Transfers: 2**
- **Validation:** RAPTOR dynamically re-evaluates the optimal connection tree following the later departure, maintaining journey continuity and the 180-second minimum transfer buffer across all stages.

### Scenario 4: Sunday vs. Monday Schedule Differentiation (HSC Service)
- **Route Corridor:** Route `45A` (Stop `8940` to Stop `5791` towards Madipakkam)
- **Query Departure:** `05:50:00` (Early Morning)
- **Monday Result:**
  - Board Trip `89823` (Service: **`HSC`**) at **05:55:00**
  - Initial Wait: **5.0 minutes**
- **Sunday Result:**
  - Service `HSC` is suspended on Sundays per `calendar.txt`.
  - Next available dispatch is Trip `89824` (Service: **`Regular`**) at **06:35:00**
  - Initial Wait: **45.0 minutes**
- **Empirical Impact:** Passenger experiences **+40 minutes of additional wait time** on Sundays, directly demonstrating calendar-aware routing fidelity.

### Scenario 5: Disconnected / Isolated Stop Handling (No-Route Test)
- **Query:** Unserviced depot stop `11` (`Alandur Depot`, degree 0) to `5822` (`Koyambedu`)
- **Result:** Returns **0 journeys** cleanly without exceptions, infinite recursion, or time-out.

### Scenario 6: Late Night Service & GTFS Post-Midnight Support
- **Query:** `5908` (`Thiruvanmiyur`) to `9991` (`Kilambakkam`) at **`23:45:00`**
- **Result:** Boards overnight trip at **23:50:00**, arriving at Kilambakkam at **`24:35:00`** (00:35 AM next day).
- **Duration:** 50.0 minutes. Proves native second-based post-midnight arithmetic.

---

## 4. Visualizations Generated

The following figures were generated and saved into `reports/figures/`:
1. `fig11_raptor_journey_comparison.png`: Stacked bar chart comparing in-vehicle ride time, initial wait time, and transfer wait time across scenarios.
2. `fig12_sunday_service_impact.png`: Bar chart demonstrating the +40 min wait penalty on Sundays on Route 45A due to `HSC` service exclusion.
3. `fig13_transfer_journey_map.png`: Geographic path visualization of the 1-transfer journey across Chennai via M.G.R. Koyambedu Bus Terminus.

---

## 5. Methodological Validation & Integrity Checks

| Validation Requirement | Benchmark | Empirical Test Result | Status |
| :--- | :--- | :--- | :--- |
| **Route Pattern Preprocessing** | 47,047 trips indexed | **3,491 unique route patterns** | **PASS** |
| **Route Continuity** | No phantom route switching | **100% verified on all legs** | **PASS** |
| **Direct Journey (0 Transfers)** | Discovers 0-transfer trip | **Scenario 1 (Line 25R, 64 min)** | **PASS** |
| **Transfer Optimization (1-2 Transfers)** | Discovers connecting trips | **Scenario 2 (Line 78 -> Line 114)** | **PASS** |
| **Transfer Walking Buffer** | >= 180 sec between legs | **Enforced strictly on all transfers** | **PASS** |
| **Calendar Awareness** | Excludes HSC on Sunday | **+40 min wait verified on Route 45A** | **PASS** |
| **Late Night Post-Midnight** | Handled beyond 24:00:00 | **23:50:00 -> 24:35:00 verified** | **PASS** |
| **No-Route Handling** | Isolated stop degree 0 | **0 journeys returned cleanly** | **PASS** |

---

## 6. Dataset Limitations & Scope Disclaimers

1. **Static Scheduled Timetable**: RAPTOR produces optimal itineraries based on the published MTC timetable. Actual on-road journey times are subject to real-time traffic congestion, bus bunching, and dispatch delays.
2. **Pedestrian Transfers**: Transfer walking between connecting platforms is modeled using a standard 3-minute buffer (180 seconds). Fine-grained walking routing across specific bus bays is unrepresented due to missing `pathways.txt` and `transfers.txt`.
3. **No Real-Time Vehicle Tracking**: Headways and transfers represent timetable potential, not GPS live vehicle positions.

---
**Report generated automatically by Module 4 analysis notebook.**
