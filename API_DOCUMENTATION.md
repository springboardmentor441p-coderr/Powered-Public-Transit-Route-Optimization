# MetroFlow REST API Reference Documentation
*Project: MetroFlow AI Platform for Metro Crowd Management & Scheduling*
*Document Reference: API-REF-01*

---

## Base URL & Authentication
- **Base URL:** `http://127.0.0.1:8000`
- **Interactive Documentation:** `http://127.0.0.1:8000/docs`
- **ReDoc Documentation:** `http://127.0.0.1:8000/redoc`
- **Authentication Scheme:** OAuth2 Bearer Token (JWT).
- **Header Format:** `Authorization: Bearer <access_token>`

---

## 1. Authentication Endpoints

### `POST /auth/login`
Obtain a JWT access token using form-urlencoded credentials.
- **Request Body:** `username=<email>&password=<password>`
- **Response `200 OK`:**
  ```json
  {
    "access_token": "eyJhbGci...",
    "token_type": "bearer"
  }
  ```

### `GET /auth/me`
Retrieve currently authenticated user profile and assigned role.
- **Security:** Bearer token required.
- **Response `200 OK`:**
  ```json
  {
    "id": 1,
    "email": "admin@example.com",
    "full_name": "Admin User",
    "role": "admin"
  }
  ```

### `POST /auth/admin/users`
Create a new operator or admin user (Admin privileges required).
- **Security:** Bearer token (Admin only).
- **Request Body:**
  ```json
  {
    "email": "operator@example.com",
    "password": "secure_password",
    "full_name": "Shift Operator",
    "role": "operator"
  }
  ```

---

## 2. Dashboard & Scale Endpoints

### `GET /dashboard/summary`
Returns total counts across the transit network.
- **Response `200 OK`:**
  ```json
  {
    "routes": 315,
    "stops": 6745,
    "trips": 10128,
    "stop_times": 429302,
    "monitored_stations": 30,
    "active_trains": 21
  }
  ```

---

## 3. Crowd Monitoring Endpoints

### `GET /crowd/live`
Retrieve real-time station passenger density, inflow/outflow, and crowd tiers.
- **Query Params:** `limit=50`, `level=CRITICAL` (optional).
- **Response `200 OK`:** Array of station crowd records.

### `GET /crowd/congestion`
Network-wide congestion index, average passenger density, and top bottleneck stations.

### `GET /crowd/heatmap`
Returns station coordinates (`lat`, `lon`), density %, and congestion index for map visualizations.

### `GET /crowd/station/{stop_id}`
Detailed metrics for an individual station.

---

## 4. Train Scheduling Endpoints

### `GET /schedule/routes`
List all transit routes and line descriptors.

### `GET /schedule/trips`
List trips filtered by `route_id` and `direction_id`.

### `GET /schedule/timetable/{trip_id}`
Returns the chronological station-by-station timetable for a specific trip.

### `GET /schedule/delays`
List of all active network delays across monitored trains.

### `POST /schedule/delays`
Report or update a live train delay.
- **Request Body:**
  ```json
  {
    "trip_id": "TRIP_101",
    "delay_minutes": 8,
    "current_station_id": "STOP_450"
  }
  ```

---

## 5. Frequency Optimization Endpoints

### `GET /scheduling/frequency/recommendations`
Algorithmic headway recommendations comparing current headway vs. peak targets (3.5m) and off-peak targets (10m).

### `POST /scheduling/scenarios`
Create and persist a new frequency adjustment scenario.

### `GET /scheduling/scenarios`
List all proposed schedule scenarios.

---

## 6. Operational Monitoring Endpoints

### `GET /monitor/live-status`
Returns fleet health, On-Time Performance (OTP %), and delay averages.

### `GET /monitor/trains`
List individual train positions, occupancy %, and status (`ON_TIME`, `DELAYED`, `CRITICAL_DELAY`).

### `GET /monitor/station/{stop_id}/departures`
Upcoming train departures from a station with live delay calculations.

---

## 7. AI Machine Learning Forecasting Endpoints

### `POST /predict/crowd`
Predicts crowd density and congestion risk for a specific hour and day of week.
- **Request Body:**
  ```json
  {
    "hour": 8,
    "day_of_week": 1,
    "stop_sequence": 12,
    "route_type": 3,
    "scheduled_frequency": 6
  }
  ```

### `GET /predict/demand`
Returns a 24-hour diurnal passenger demand and crowd density curve for operational scheduling.

### `GET /predict/recommendations`
AI-generated operational actions (e.g., dispatch relief trains, dynamic platform metering).

---

## 8. Analytics & Reporting Endpoints

### `GET /analytics/traffic-report`
Compiled transit analysis metrics in structured JSON.

### `GET /analytics/traffic-report/markdown`
Formatted Markdown traffic analysis report.

