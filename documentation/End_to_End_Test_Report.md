# RouteRanker – End-to-End Audit & Bug-Fixing Test Report

**Execution Date:** November 5, 2026  
**Target Transit Agency:** Chicago Transit Authority (CTA), Chicago, Illinois, USA  
**Test Suite Status:** **100% PASSED (28/28 Endpoints Verified HTTP 200 OK)**

---

## 1. Audit Summary Across Core System Modules

| Section | Issue Audited | Resolution Status | Technical Implementation & Verification |
| :--- | :--- | :--- | :--- |
| **1. Route Optimization** | Invalid Belmont-to-Jackson routing & station-line assignment ambiguities | **Fixed** | Extracted exact official GTFS parent station sequences for all 8 rail lines (`Red`, `Blue`, `Brn`, `G`, `Org`, `P`, `Pink`, `Y`). Built line-aware candidate disambiguation in `route_planner.py`. Belmont Red (`RAIL_41320`) to Jackson Red (`RAIL_40560`) now correctly computes a direct 17.1-min, 0-transfer journey on the Red Line. Belmont Blue (`RAIL_40060`) to Jackson Blue (`RAIL_40070`) computes a direct 22.6-min, 0-transfer journey on the Blue Line. Step-by-step turn-by-turn directions now output valid `from_stop`, `to_stop`, `line`, `mode`, and `duration_minutes`. |
| **2. Live Monitoring** | CARTO map tile `API KEY REQUIRED` watermark & simulated vs live telemetry labeling | **Fixed** | Replaced tile provider in `LiveMonitoringView.jsx` with official OpenStreetMap tiles (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`). Added strict geographic coordinate validation (`41.5 <= lat <= 42.2` and `-87.95 <= lon <= -87.5`). Added clear badges and banners explicitly labeling GTFS schedule trajectory simulation versus live CTA GPS telemetry. |
| **3. Demand Forecasting** | Outdated September 2026 dates, day-of-week / day-type errors, and 95% confidence intervals | **Fixed** | Updated `demand_forecast_service.py` to forecast dynamically starting from the current date (November 5, 2026). Standardized day-type codes according to CTA standards (`W` for Weekday, `A` for Saturday, `U` for Sunday/Holiday). Formulated mathematically rigorous 95% confidence intervals combining ensemble tree variance with test residual standard error (`RMSE = 94,630`). Enabled 7, 14, and 28-day horizons. |
| **4. Smart Scenarios** | Missing / zero values in baseline trips, headway, passenger capacity, and peak-loading | **Fixed** | Harmonized data contracts between backend `smart_recommendations.py` and frontend `RecommendationsView.jsx`. Populated actual GTFS baseline weekday trips (e.g. Route 79: 148 trips, 7.3m headway, 8,880 capacity; Route 9: 144 trips). Added explicit disclosure labeling nominal 40ft bus capacity (60 passengers) versus unavailable live APC sensor counts. |
| **5. Alerts & Dashboard** | Conflicting alert counts across header, dashboard, and live monitoring page | **Fixed** | Unified the CTA Alerts response schema in `transit_routes.py` with `total_alerts` and `count` fields. Updated `Navbar.jsx`, `DashboardView.jsx`, and `LiveMonitoringView.jsx` to consume the identical data source, eliminating discrepancies (all displaying 44 active CTA alerts). |
| **6. Backend Integration** | Startup verification, proxy 502/ECONNREFUSED errors, and 500 error on historical-trend | **Fixed** | Resolved `day_type` column naming in `get_historical_trend()`. Configured Vite reverse proxy (`/api` -> `http://127.0.0.1:8000`). Verified 28 direct and proxied endpoints. |

---

## 2. Automated Test Evidence

### A. Real-Time API Test Suite (`tests/test_realtime_apis.py`)
```text
[Test 1] Testing Official Live CTA Customer Alerts API...
  Retrieved 44 live alerts. Sample headline: 'Temporary Bus Stop Change'
[Test 2] Testing Bus Vehicle Positions Client & Metadata...
  Bus 79 positions: 4 vehicles. Data source: GTFS_SCHEDULE_DERIVED
[Test 3] Testing Train Tracker Client & Line Telemetry...
  Red Line trains: 4 active trains. Data source: GTFS_SCHEDULE_DERIVED
[Test 4] Testing Station Platform Arrival Predictions...
  Arrival prediction for Washington/Wabash: Brown Line train in 2 mins
[Test 5] Testing Transit Cache Hit & TTL Freshness...
  Cache validated. Timestamp: 2026-11-05T04:52:03Z
[Test 6] Testing FastAPI REST Endpoints...
  System Status: GTFS_SCHEDULE_SIMULATION_WITH_LIVE_ALERTS, Alerts: 44
----------------------------------------------------------------------
Ran 6 tests in 0.870s -> OK (6/6 PASSING)
```

### B. Full Backend REST & ML Test Suite (`tests/test_backend_full.py`)
```text
  System Forecast 7-Day: Day 1=1,021,224 (High Demand)
  Route 79 Forecast: Day 1=17,989 rides
  Model Benchmarks: Best Model=Random_Forest
  Simulation Route 79: Rec='Alleviate Severe Peak Passenger Loading', Headway=6.8m
  Route Plan Belmont -> Jackson: 17.1 mins, 0 transfers
  Location Search 'Clark': Found 2 matches
  Top Route: Rt 66 (Chicago) - 15,069 avg daily rides
  Top Network Hub: Clark/Lake (Centrality=0.0663)
----------------------------------------------------------------------
Ran 9 tests in 1.628s -> OK (9/9 PASSING)
```

### C. Comprehensive Endpoint Health & Proxy Verification (`test_all_endpoints.py`)
```text
[PASS 200] Backend Health
[PASS 200] FastAPI Docs
[PASS 200] Transit Status
[PASS 200] CTA Alerts (All)
[PASS 200] CTA Alerts (Filter Rt 79)
[PASS 200] CTA Alerts (Filter Red Line)
[PASS 200] Bus Vehicles (Rt 79)
[PASS 200] Train Positions (Red)
[PASS 200] Route Plan Belmont->Jackson
[PASS 200] Route Plan O'Hare->Clark/Lake
[PASS 200] Route Plan Midway->Jackson
[PASS 200] Locations Search 'Belmont'
[PASS 200] System Forecast (7 days)
[PASS 200] System Forecast (14 days)
[PASS 200] System Forecast (28 days)
[PASS 200] Route Forecast (Rt 79, 7d)
[PASS 200] Route Forecast (Rt 9, 28d)
[PASS 200] Model Benchmark Metrics
[PASS 200] Scenario Simulate Rt 79
[PASS 200] Scenario Simulate Rt 66
[PASS 200] Corridor Rankings
[PASS 200] Station Rankings
[PASS 200] Historical Trend (30 days)
[PASS 200] Network Centrality
[PASS 200] Vite Proxy -> /api/route/plan
[PASS 200] Vite Proxy -> /api/transit/alerts
[PASS 200] Vite Proxy -> /api/forecast/system
[PASS 200] Vite Proxy -> /api/recommendations/simulate

>>> ALL 28 ENDPOINTS VERIFIED & PASSING WITH 200 OK! <<<
```

### D. Frontend Production Build
```text
vite v8.3.5 building client environment for production...
transforming...
✓ 2437 modules transformed.
rendering chunks...
dist/index.html                   0.94 kB
dist/assets/index-CQpBmfeW.css   39.98 kB
dist/assets/index-KXkitCbT.js   852.27 kB
✓ built in 386ms -> 0 errors
```

