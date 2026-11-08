# MetroFlow Scheduling & Headway Optimization Documentation

## Overview

MetroFlow includes an algorithmic train timetable and frequency adjustment engine designed to optimize dispatch headways, handle operational delays, and evaluate what-if schedule scenarios before dispatching changes into production.

---

## 1. Algorithmic Principles & Formulation

### 1.1 Headway Calculation
For any given transit line (route $r \in R$), the current baseline average headway $H_{\text{current}}(r)$ across a 16-hour operational span ($T_{\text{span}} = 960$ minutes) is derived from the scheduled trip count $N_{\text{trips}}(r)$:

$$H_{\text{current}}(r) = \max\left(5, \left\lfloor \frac{T_{\text{span}}}{N_{\text{trips}}(r)} \right\rceil\right)$$

### 1.2 Peak vs. Off-Peak Recommendations
During peak morning ($07:30 - 09:30$) and evening ($17:30 - 19:30$) congestion windows, passenger density increases significantly. The system algorithmically recommends:
- **Peak Headway Target:** $H_{\text{peak}}^*(r) = \min(4, \max(3, \lfloor 0.4 \times H_{\text{current}}(r) \rfloor))$ minutes.
- **Off-Peak Headway Target:** $H_{\text{offpeak}}^*(r) = \min(10, \max(6, \lfloor 0.8 \times H_{\text{current}}(r) \rfloor))$ minutes.

### 1.3 Supplemental Fleet Requirement
The number of supplemental rolling stock units / bus sets $\Delta K(r)$ required to achieve the recommended peak headway is computed as:

$$\Delta K(r) = \max\left(1, \left\lfloor \frac{H_{\text{current}}(r) - H_{\text{peak}}^*(r)}{3.0} \right\rceil\right)$$

### 1.4 Projected Overcrowding Relief
Platform and in-vehicle crowd density reduction is estimated by:

$$\Delta C_{\text{relief}}(r) = \min\left(45.0, 18.0 + \Delta K(r) \times 8.5\right) \quad [\%]$$

---

## 2. API Reference

| Endpoint | Method | Role | Description |
| :--- | :---: | :---: | :--- |
| `/schedule/routes` | GET | Operator/Admin | List active GTFS routes with metadata and colors |
| `/schedule/trips` | GET | Operator/Admin | Filter trips by route ID and direction ID |
| `/schedule/timetable/{trip_id}` | GET | Operator/Admin | Retrieve stop sequence, arrival, and departure times |
| `/schedule/delays` | GET | Operator/Admin | Retrieve all logged trip delay deviations |
| `/schedule/delays` | POST | Operator/Admin | Broadcast a new train/vehicle delay |
| `/scheduling/frequency/recommendations` | GET | Operator/Admin | Route-wise headway reduction recommendations |
| `/scheduling/scenarios` | GET | Operator/Admin | List saved what-if frequency adjustment scenarios |
| `/scheduling/scenarios` | POST | Operator/Admin | Simulate and persist a new frequency scenario |

---

## 3. Operational Delay Handling Workflow

1. Station master or telemetry sensor detects vehicle delay at a station.
2. Operator submits delay report via `POST /schedule/delays` with `trip_id`, `delay_minutes`, `current_station_id`, and `notes`.
3. Database `train_statuses` and `operational_delays` records are updated in real time.
4. Downstream telemetry dashboard and interactive Leaflet map reflect the updated train position and color code (green for on-time, amber/red for delayed).
5. If delay exceeds configured threshold (e.g. 10 minutes), an automated notification is broadcast via WebSocket to all connected stations.

