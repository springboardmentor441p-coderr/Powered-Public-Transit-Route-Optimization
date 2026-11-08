# MetroFlow System Architecture & Design Specification
*Project: MetroFlow AI Platform for Metro Crowd Management & Scheduling*
*Document Reference: ARCH-01*

---

## 1. System Overview & Architecture Diagram

MetroFlow is designed as a modular, scalable public transit intelligence platform. It ingests static transit topology from standard GTFS feeds, integrates real-time station crowd telemetry and train operations, applies machine learning models for passenger demand forecasting, and exposes operational decision support tools.

```
+-----------------------------------------------------------------------------------+
|                        USER INTERFACE LAYER (Web / Mobile)                        |
|   Dashboard  |  Crowd Heatmap  |  Timetables  |  Frequency Optimizer  |  AI Lab   |
|   - React.js / Next.js + TypeScript + Tailwind CSS                                |
|   - Leaflet interactive transit map + Chart.js analytics                          |
+-----------------------------------------+-----------------------------------------+
                                          | REST / JSON (OAuth2 JWT)
                                          v
+-----------------------------------------------------------------------------------+
|                           API GATEWAY LAYER (FastAPI)                             |
|   Routing  |  JWT Authentication  |  Request Validation  |  CORS & Rate Limiting  |
+-----------------------------------------+-----------------------------------------+
                                          |
          +-------------------------------+-------------------------------+
          |                               |                               |
          v                               v                               v
+-------------------+           +-------------------+           +-------------------+
| CROWD MONITORING  |           | SCHEDULING SYSTEM |           | OPERATIONAL       |
| SERVICE           |           | SERVICE           |           | MONITORING        |
| - Station density |           | - Route catalog   |           | - Active fleet    |
| - Inflow / outflow|           | - Timetables      |           | - OTP tracking    |
| - Heatmaps        |           | - Delays handling |           | - Live departures |
| - Bottlenecks     |           | - Headways        |           | - Delay cascades  |
+---------+---------+           +---------+---------+           +---------+---------+
          |                               |                               |
          +-------------------------------+-------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                     TRANSPORTATION ANALYTICS & AI ENGINE                          |
|   - Scikit-Learn GradientBoostingRegressor (Crowd Density %)                      |
|   - Scikit-Learn RandomForestRegressor (Passenger Footfall Demand)                |
|   - Diurnal 24-Hour Peak Surge Predictor                                          |
|   - Algorithmic Headway Optimization & Overcrowding Relief Scenarios              |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                          DATA & PERSISTENCE LAYER                                 |
|   PostgreSQL / SQLite Storage:                                                    |
|   - GTFS Static: routes, stops, trips, stop_times, calendar, shapes, agency       |
|   - Operational: station_crowd, train_status, schedule_scenarios                  |
|   - Authentication: users, roles                                                  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Functional Modules

### 2.1 User Management & Security Module
- **JWT Authentication:** Cryptographically signed tokens (`HS256`, 30-minute expiry).
- **Role-Based Access Control (RBAC):**
  - `admin`: User provisioning, scenario approval, network configuration.
  - `operator`: Real-time monitoring, delay logging, frequency scenario testing.
- **Password Protection:** Secure hashing via `passlib` with salt verification.

### 2.2 Crowd Monitoring Module
- **Station Passenger Density Tracking:** Continuous estimation of platform density (`0% - 100%`).
- **Severity Classification:**
  - `LOW`: < 45% (Comfortable passenger flow)
  - `MODERATE`: 45% - 69% (Normal transit volumes)
  - `HIGH`: 70% - 84% (Approaching platform capacity)
  - `CRITICAL`: >= 85% (Immediate crowd safety intervention required)
- **Spatial Heatmaps:** Lat/lon intensity mapping for operational dispatchers.

### 2.3 Scheduling & Frequency Optimization Module
- **Timetable Management:** Chronological station arrival and departure sequencing across 10,128 trips.
- **Headway Optimization Engine:**
  - Detects peak morning (`07:30 - 09:30`) and evening (`17:30 - 19:30`) congestion windows.
  - Dynamically calculates target dispatch intervals (e.g. reducing 10 min headway down to 3.5 min).
  - Computes additional rolling stock sets needed and projected crowd relief percentage.
- **Scenario Storage:** Persists proposed schedule adjustments for operator review and validation.

### 2.4 Real-Time Operational Monitoring Module
- **Fleet Telemetry:** Live train position, occupancy percentage, and delay minutes.
- **On-Time Performance (OTP):** Continuously computed network punctuality indicator.
- **Live Departures:** Estimates dynamic station departures with live delay propagation.

### 2.5 AI Machine Learning Prediction Module
- **Feature Set:** Temporal indices (`hour`, `day_of_week`, `is_peak`), network topology (`stop_sequence`, `route_type`), and baseline service frequency.
- **Dual Ensembles:**
  - `GradientBoostingRegressor`: High-precision density percentage prediction.
  - `RandomForestRegressor`: Station-level passenger footfall forecasting.
- **Smart Recommendations:** Context-aware automated advice (e.g., turnstile metering, holding intervals, train injections).

