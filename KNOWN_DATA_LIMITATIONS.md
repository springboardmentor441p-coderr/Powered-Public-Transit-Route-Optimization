# Known Data Limitations & Transportation Data Integration Architecture
*Project: MetroFlow AI Public Transportation Intelligence Platform*
*Document Reference: DATA-LIMITATIONS-01*

---

## 1. Primary Dataset Overview
The primary dataset ingested into MetroFlow consists of the full static General Transit Feed Specification (GTFS) package provided in `data/`:
- **Routes:** 315 transit routes (`routes.txt`)
- **Stops & Stations:** 6,745 stops (`stops.txt`)
- **Scheduled Trips:** 10,128 trips (`trips.txt`)
- **Timetable Events:** 429,302 arrival and departure events (`stop_times.txt`)
- **Path Geometries:** 256,823 coordinate points (`shapes.txt`)
- **Agencies & Calendar:** `agency.txt`, `calendar.txt`, `feed_info.txt`

---

## 2. Transit Mode Classification & GTFS Route Types
Inspection of the ingested `routes.txt` confirms that all 315 lines carry `route_type = 3`, which corresponds to **Bus Transit / Surface Public Transit** in the GTFS specification.

### Transparency & Integrity Policy:
- **No Misrepresentation:** The platform explicitly reports these 315 routes as regional transit and surface bus lines.
- **Universal Architecture:** GTFS is the worldwide standard for public transit, used interchangeably for subway, light rail, metro, bus rapid transit (BRT), and regional rail. MetroFlow's scheduling algorithms, headway optimization formulas, and spatial congestion heatmaps operate seamlessly across both surface bus lines and grade-separated metro systems.

---

## 3. Static Timetable Data vs. Real-Time Passenger Observations

### What Static GTFS Provides:
- Exact stop sequences, route alignments, and station coordinates (`stop_lat`, `stop_lon`).
- Scheduled arrival and departure times for 10,128 trips.
- Network topological connections, service intervals, and baseline headway spacing.

### What Static GTFS Does NOT Provide:
- Live turnstile smart-card tap-ins/tap-outs (Automated Fare Collection - AFC).
- Real-time automated passenger counters (APC) or onboard optical sensors.
- Real-time automated vehicle location (AVL / GTFS-RT GPS feeds).

---

## 4. Integration Architecture for Live Observations
To fulfill the operational monitoring and crowd prediction requirements without fabricating false historical claims, MetroFlow implements a decoupled two-tier architecture:

```
+-------------------------------------------------------------------+
|               GTFS Static Core (Ground Truth)                     |
|  routes | stops | trips | stop_times | calendar | shapes          |
|  - 315 lines, 6,745 stops, 429,302 scheduled timetable records    |
+---------------------------------+---------------------------------+
                                  |
               Spatial & Topological Reference (stop_id, route_id)
                                  v
+---------------------------------+---------------------------------+
|          Real-time Observational & Operational Layer              |
|  station_crowd | train_status | schedule_scenarios                |
|  - Real-time passenger density (%) & congestion index             |
|  - Inflow & outflow rates (pax/min) and platform headcount        |
|  - Train telemetry, delays, occupancy rates & dynamic headways    |
+---------------------------------+---------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|          AI & Machine Learning Forecasting Engine                 |
|  - Gradient Boosting & Random Forest Regressors                   |
|  - Inputs: Hour, day-of-week, peak flag, GTFS headway, stop seq  |
|  - Outputs: Predicted crowd density, demand footfall, risk tier   |
+-------------------------------------------------------------------+
```

### Future Data Connectors:
1. **GTFS-Realtime (GTFS-RT):** TripUpdates, VehiclePositions, and Alert feeds can be directly ingested into `train_status`.
2. **AFC / Smart Card Ingestion:** Turnstile tap records stream into `station_crowd.inflow_rate` and `outflow_rate`.
3. **CCTV / Sensor Streams:** Optical passenger counter readings feed directly into platform headcount without requiring video processing inside the core backend.

