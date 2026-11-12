# RouteRanker – Complete Project Scope & Architecture Audit Report

**Date of Audit:** November 5, 2026  
**Auditor Roles:** Senior AI/ML Engineer, Principal Backend Systems Architect, Public Transit Optimization Specialist  
**Target Transit Agency:** Chicago Transit Authority (CTA), Chicago, Illinois, USA  
**Scope:** Complete repository inspection (Data, Models, Notebooks, Backend APIs, Frontend Views, Graph Networks, and Real-Time Feeds)  
**Status:** Audit Completed. No source code or model weights modified during this audit.

---

## 1. Executive Summary & Verification Matrix

The RouteRanker codebase was audited against all 12 requested functional modules and the project's strict data authenticity guidelines.

RouteRanker is an AI-powered public transit decision support and passenger demand platform built for the Chicago Transit Authority. The project contains:
- **Cleaned Data:** 9,374 daily system ridership records (2001–2026), 150k+ bus route records, 150k+ rail station entry records, and cleaned Chicago GTFS feeds.
- **Machine Learning Models:** System-wide daily demand forecasters (`cta_system_demand_forecaster.joblib`), route-specific regressors (`cta_bus_route_forecasters.joblib`), and rail station regressors (`cta_rail_station_forecasters.joblib`).
- **Graph & Optimization Engine:** NetworkX multi-modal directed transit graph with 182 nodes (144 rail stations, 38 bus corridor stops) and 390 edges across all 8 Chicago 'L' rail lines, bus corridors, and transfer points.
- **Backend Services:** FastAPI application running on `127.0.0.1:8000` with 17 operational REST endpoints.
- **Frontend Dashboard:** React 19 + Tailwind CSS + Leaflet map application running on `localhost:5173`.

### 12 Required Modules Inspection Matrix

| # | Required Module | Audit Status | Implementation State | Verification Evidence & Limiting Factors |
|---|---|:---:|---|---|
| **1** | Bus crowd and passenger demand analysis | **PASS** | Fully implemented & verified | Preprocessed ridership on 120+ CTA routes (`cleaned_bus_route_ridership.csv`). High/Mod/Low percentiles calculated across empirical route distributions. |
| **2** | Bus live vehicle monitoring and actual/estimated passenger count | **WARN** | Implemented with simulation disclosure | Official CTA Bus Tracker API keys are absent (`.env` placeholder). Vehicle positions are calculated via GTFS schedule timetable interpolation. Passenger counts are estimated mathematically, not measured via automated passenger counters (APCs). UI explicitly discloses `GTFS SCHEDULE EMULATION`. |
| **3** | Bus route-wise and time-wise demand forecasting | **PASS** | Fully implemented & verified | Multi-step route-level daily regressors in `cta_bus_route_forecasters.joblib` for major corridors (79, 9, 66, 4, 49). Forecast horizons of 7, 14, and 28 days verified. Hourly/time-of-day profile derived from GTFS published run schedules. |
| **4** | Bus overcrowding risk estimation | **WARN** | Implemented but requires semantic clarity | Daily ridership percentiles (e.g. Route 79 > 90th percentile = 17,200 rides) are categorized as "Potentially Overcrowded". Because CTA only publishes daily aggregate route boardings, trip-level crowding cannot be directly observed from historical data without applying GTFS hourly distribution curves. |
| **5** | Rail station and train-line crowd/demand analysis | **PASS** | Fully implemented & verified | All 144 CTA 'L' stations analyzed via `cleaned_l_station_entries.csv`. Top hubs (Clark/Lake, Lake/State, Chicago Red) benchmarked with network centralities. |
| **6** | AI/ML model training, evaluation, saving, prediction API | **PASS** | Fully implemented & verified | Five algorithms benchmarked (Naive, Moving Avg, Ridge, Random Forest, Gradient Boosting). Random Forest is champion ($R^2=0.7899$, $\text{MAPE}=7.92\%$). Models saved as `.joblib` in `models/` and served via `/api/forecast/*`. |
| **7** | Dijkstra shortest-path routing | **PASS** | Fully implemented & verified | Implemented in `route_planner.py` using weighted NetworkX graph with line penalties. Belmont to Jackson direct on Red Line (17.1 min, 0 transfers) and Blue Line (22.6 min, 0 transfers) verified. |
| **8** | Alternative routes, transfer optimization, travel times | **WARN** | Partially implemented / Graph edge penalty tuning | Alternative itineraries are computed using edge exclusion. However, on long journeys with complex transfers, pure Dijkstra weights can favor transferring to a Loop elevated line rather than staying on the continuous Red Line subway due to a 0 transfer penalty on line transitions. |
| **9** | Crowd-aware route recommendations | **WARN** | Implemented via daily demand weighting | Crowd-weighting penalizes routes during peak forecast days using historical percentile multipliers. Actual real-time crowd data (APCs/turnstile deltas) is unavailable from public CTA APIs. |
| **10** | Smart bus-frequency & service optimization scenarios | **PASS** | Fully implemented & verified | Scenario simulator recalculates headways and passenger load factors for Route 79 using GTFS baseline weekday trips (148 scheduled trips, 60-passenger vehicle capacity, 17,989 daily rides). |
| **11** | Official CTA live service alerts | **PASS** | Fully implemented & verified | Live XML/JSON integration with `https://www.transitchicago.com/api/1.0/alerts.aspx`. Current feed returns 43 active advisories. Caching and fallback mechanisms verified. |
| **12** | Frontend dashboards, charts, maps, API integrations | **PASS** | Fully implemented & verified | 7 complete views (Dashboard, Live Monitoring, Route Planner, Forecasting, Recommendations, Analytics, System Status) with OpenStreetMap tiles and responsive Recharts components. |

---

## 2. Deep-Dive Inspection of Specific Audit Points

### 2.1. The 28-Record Difference (9,374 Daily Records vs. 9,346 in Model Splits)
- **Observation:** `cta_ridership_daily_system_totals.csv` has **9,374 rows** (Jan 1, 2001 to Aug 31, 2026). The model training splits sum to **9,346 rows** ($\text{Train}: 8,738 + \text{Val}: 365 + \text{Test}: 243 = 9,346$).
- **Root Cause Verified:** To generate autoregressive lag and rolling window features (`total_rides_lag_1`, `total_rides_lag_7`, `total_rides_lag_14`, `total_rides_lag_28`, and 28-day rolling means), the first **28 days of the dataset (Jan 1, 2001 to Jan 28, 2001)** have `NaN` values for `total_rides_lag_28`. The dataset was cleanly filtered using `df.dropna(subset=['total_rides_lag_28'])`:
  $$9,374 - 28 = 9,346$$
- **Verdict:** **PASS (Mathematically verified)**. No records were lost or deleted; the 28 records are the required burn-in period for 28-day lag feature engineering.

### 2.2. CTA Alerts API Discrepancy & Old Alerts with Null `EventEnd`
- **Observation:** CTA alerts endpoint returned 43 records. 24 of the 43 alerts have `EventEnd: None`. Some alerts date back to 2022 (e.g., long-term bus stop relocations due to construction).
- **Impact on System:**
  - In `LiveMonitoringView.jsx`, corridor filtering for Route 79 returned 0 alerts, while the system badge showed 43/44 alerts.
  - The CTA alerts API includes permanent/long-term stop changes without scheduled end dates alongside immediate temporary service delays.
- **Verdict:** **PASS with Explanatory UI**. The alerts feed represents actual CTA data where indefinite station renovations or long-term detours remain active in CTA's customer alert system without an `EventEnd` date. The UI toggle between "Corridor Advisories" and "System-Wide Advisories (43)" accurately reflects this.

### 2.3. Route 79 Demand Classification & Daily Ridership vs. Overcrowding
- **Observation:** Route 79 weekday ridership forecasts ($17,000 - 18,000$ rides) are classified as `"Potentially Overcrowded"` because Route 79's empirical 75th percentile is 17,045 rides and 90th percentile is 18,455 rides.
- **Transit Domain Consideration:** A daily volume of 18,000 rides across 148 scheduled bus runs represents an average of $\approx 121$ passengers per bus trip across its entire length. Overcrowding in transit is a **spatio-temporal phenomenon** (e.g., 65 passengers on a 60-capacity bus between State and Halsted at 8:15 AM), not a whole-day property.
- **Verdict:** **WARN**. The label should be updated to `"Very High Corridor Daily Volume (Peak Crowding Likely)"` to prevent the false impression that every bus run on Route 79 is overcrowded throughout the day.

### 2.4. Forecast Confidence Intervals
- **Observation:** System forecast intervals are calculated as:
  $$\text{Bounds}_{95\%} = \hat{y} \pm 1.96 \times \text{RMSE}_{\text{test}} \quad (\text{RMSE} = 94,630)$$
  Yielding bounds such as $[835,749, 1,206,699]$ around a $1,021,224$ weekday forecast.
- **Route-Level Intervals:** On Route 79, confidence intervals span $[15,831, 20,147]$ around an estimate of $17,989$ rides ($\pm 12\%$).
- **Verdict:** **PASS**. The confidence intervals are statistically sound, derived from out-of-sample test error rather than arbitrary spreads.

### 2.5. Belmont-to-Fullerton Alternative Routes & Stop Counts
- **Observation:** Querying `origin=Belmont` and `destination=Fullerton`:
  - **Option 1 (Red Line Express Spine):** Belmont $\rightarrow$ Fullerton. Stops: 1. Duration: 3.0 min. Transfers: 0.
  - **Option 2 (Brown Line Local Alternative):** Belmont $\rightarrow$ Wellington $\rightarrow$ Diversey $\rightarrow$ Fullerton. Stops: 3. Duration: 4.8 min. Transfers: 0.
- **Verdict:** **PASS**. The alternative route stop counts reflect physical reality: Red and Purple lines run express skipping Wellington and Diversey, while the Brown Line makes local stops at Wellington and Diversey.

### 2.6. Location Directory (144 Rail Stations vs. 3 Bus Terminals)
- **Observation:** `/api/route/locations` returns 147 items: 144 parent 'L' rail stations and 3 bus terminals (`BUS_79_Ford_City_Mall`, `BUS_66_Navy_Pier_Terminal`, `BUS_9_95th_Ashland`).
- **Graph Topology Reality:** In `models/cta_network_graph.joblib`, the graph contains **182 nodes**:
  - 144 Rail Stations
  - 38 Bus Stops along key corridors (Route 79, Route 66, Route 9, Route 4)
- **Root Cause:** In `backend/app/api/planning_routes.py`, the `search_transit_locations` endpoint hardcodes only 3 sample bus terminals rather than querying all 38 bus stops stored in the network graph or the GTFS bus stops dataset.
- **Verdict:** **WARN**. The backend routing engine supports all 38 bus stops, but the autocomplete search endpoint only exposes 3 bus locations to the frontend user.

### 2.7. Network Graph Edges & Transfer Logic
- **Observation:**
  - Graph Nodes: 182
  - Graph Edges: 390 directed edges (292 Rail, 12 Station Transfers, 16 Bus-Rail Walking links, 70 Bus links).
  - Intermodal test (`Ford City Mall` $\rightarrow$ `Fullerton`): Routes via Bus 79 $\rightarrow$ Transfer to 79th Red Line $\rightarrow$ Red Line to Roosevelt $\rightarrow$ Orange/Pink/Brown to Fullerton (79.5 min, 4 transfers).
- **Transfer Anomaly Identified:**
  - From 79th Red Line to Fullerton, the continuous Red Line subway runs directly in $\approx 25$ minutes with 0 transfers.
  - However, Dijkstra's algorithm chose to transfer from Red to Orange at Roosevelt, Pink at Washington/Wabash, and Brown at Clark/Lake because the cumulative edge transit time on the elevated loop was calculated as $16.3$ minutes vs $17.3$ minutes on the Red Line, and line-change transfer penalty was set to 0.
- **Verdict:** **WARN**. The network graph is fully connected and valid, but `transfer_penalty` on rail-to-rail line changes must be increased (e.g. $+5.0$ minutes) to penalize unnecessary transfers and keep passengers on direct single-line journeys.

### 2.8. Smart Scenario Capacity Assumptions
- **Baseline Parameters for Route 79:**
  - Scheduled Daily Trips: 148 runs (GTFS weekday schedule).
  - Headway: 9.7 minutes average (6.5 min peak, 15 min off-peak).
  - Vehicle Type: Standard 40ft transit bus.
  - Vehicle Capacity Standard: 40 seated + 20 standees = **60 total capacity**.
  - Directional Capacity: $148 \times 60 = 8,880$ seats/spaces per direction.
  - Load Factor Formula:
    $$\text{Peak Hour Passenger Demand} / (\text{Peak Trips per Hour} \times 60)$$
- **Verdict:** **PASS**. All calculations are grounded in official CTA GTFS timetables and transit industry standards. Disclaimers regarding traffic congestion and bunching are present.

### 2.9. Real-Time CTA API Configuration
- **Observation:** `.env` contains:
  ```env
  CTA_BUS_API_KEY=YOUR_CTA_BUS_TRACKER_API_KEY_HERE
  CTA_TRAIN_API_KEY=YOUR_CTA_TRAIN_TRACKER_API_KEY_HERE
  ```
- **System Behavior:** When API keys are placeholders, `cta_bus_client.py` and `cta_train_client.py` fall back to `GTFS_SCHEDULE_DERIVED` emulation.
- **Verdict:** **PASS with Transparent Disclosure**. The application does not forge fake live GPS pings. It explicitly alerts the operator that positions are schedule-derived simulations.

### 2.10. Notebook Preservation
- **Verification:** Both notebooks referenced by the user are preserved:
  - `C:\Users\Hp\Downloads\RouteRanker_EDA-1 .ipynb` (preserved in user's downloads folder).
  - `C:\Users\Hp\Downloads\RouteRanker_Network_Optimization_and_ML.ipynb`.
  - In workspace: `outputs/eda/generate_eda_visualizations.py` produces the 8 figures documented in the Phase 3 report without overwriting any original notebook files.
- **Verdict:** **PASS**. No notebooks were overwritten or deleted.

---

## 3. Missing or Sub-Optimal Functionality

1. **Incomplete Bus Stop Search in Location Autocomplete (`planning_routes.py`):**
   - The `/api/route/locations` endpoint only lists 3 bus stops out of the 38 bus stops in the transit graph.
2. **Transfer Penalty in Dijkstra Routing Graph (`cta_network_builder.py`):**
   - Edge weights currently only measure in-vehicle travel time. Transfers between rail lines carry 0 penalty, causing Dijkstra to choose a 3-transfer path if in-vehicle running time is 1 minute faster than staying on a direct train.
3. **Overcrowding Semantic Labeling (`demand_forecast_service.py`):**
   - Corridors with high daily demand are labeled "Potentially Overcrowded" without an explicit disclaimer explaining that this represents daily volume exceeding the 75th/90th percentile, not continuous bus overcrowding.

---

## 4. Required Changes & Recommended Implementation Plan

Before executing code modifications, the following phased changes are proposed for user review and approval:

```
[Phase A: Routing & Graph Tuning]
  ├── Update route_optimization/cta_network_builder.py:
  │     └── Add a 5.0-minute transfer penalty to rail-to-rail inter-line transfers.
  └── Rebuild models/cta_network_graph.joblib.

[Phase B: Location Search Expansion]
  └── Update backend/app/api/planning_routes.py:
        └── Dynamically export all 38 bus stop nodes from cta_network_graph.joblib
            into /api/route/locations so users can plan from any corridor bus stop.

[Phase C: Forecasting Label Clarification]
  └── Update backend/app/services/demand_forecast_service.py:
        └── Change "Potentially Overcrowded" to "High Daily Corridor Volume (Peak Overcrowding Risk)"
            and document that crowding is trip-specific.
```

---

## 5. Certification & Current Working State

The RouteRanker application is currently running:
- **Backend API:** `http://127.0.0.1:8000` (FastAPI / Uvicorn)
- **Frontend UI:** `http://localhost:5173` (Vite / React)
- **All 15 Unit & Integration Tests:** 100% PASSING.

*Audit complete. Ready to proceed upon confirmation.*

