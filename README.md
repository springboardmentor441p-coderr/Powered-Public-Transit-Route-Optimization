# Powered Public Transit Route Optimization

Exploratory Data Analysis (EDA) and data pipeline for Delhi Transport Corporation (DTC) bus operations using static GTFS schedules (2018) and high-frequency GPS Automated Vehicle Location (AVL) telemetry (July 2019).

---

## 1. What We Found

### A. Feasibility & City Selection (Delhi vs. Chennai)
- **100% Route Overlap**: All **476** distinct GPS route IDs observed in the AVL feed exist in the 2018 GTFS timetable (`routes.txt`).
- **100% Ping Coverage**: 100% of the 1.97 million GPS telemetry records map directly to valid scheduled route IDs.
- **Decision**: **Stay with Delhi** — the GPS telemetry and timetable are fully compatible.

### B. Fleet & Service Characteristics
- **Active Bus Fleet**: **1,522** unique buses tracked daily.
- **Reporting Interval**: Nominal device transmission frequency is **10 seconds** (median interval = 10.0s, 75th percentile = 20.0s).
- **Daily Volume**: Buses average **1,240.7 readings/day** (median: 1,210.5; max: 3,758).
- **Reporting Gaps**: Only **1.52%** of reporting intervals exceed 5 minutes, primarily during terminal layovers or shift turnovers. Gaps over 20 hours correspond to single morning-shift buses.
- **Service Patterns**:
  - The static GTFS schedule defines uniform 7-day operation (`service_id = 1` active across all days) with no distinction between weekday and weekend trips.
  - **Twin Commuter Peaks**: Scheduled trip origin departures peak in the morning (07:00–09:59 at ~590 departures/hour) and late afternoon (15:00–17:59, peaking at 608 departures/hour).
  - **Route Lengths**: Average route length is **43.48 stops/trip** (ranging from 11 stops on route `504` up to 86 stops on route `452`).

### C. Speed Profiling & Corridor Performance
- **Hourly Speed Curve**:
  - Free-flow early morning speeds: **6.74 km/h** commercial (**8.21 km/h** moving).
  - Congestion trough: Speeds drop severely during evening rush hours (**17:00–20:59**), reaching a daily low of **2.91 km/h** commercial (**5.09–5.18 km/h** moving).
- **Fastest Routes** ($\ge 500$ pings):
  1. Route `380` (`480UP`): **9.31 km/h** commercial (9.95 km/h moving)
  2. Route `235` (`833LnkSTLDown`): **9.01 km/h** commercial (9.44 km/h moving)
  3. Route `177` (`623EXTDN`): **7.40 km/h** commercial (7.79 km/h moving)
- **Slowest Routes** ($\ge 500$ pings):
  1. Route `309` (`990E_CL_UP`): **0.38 km/h** commercial (5.53 km/h moving; >85% idle)
  2. Route `299` (`938ACLUp`): **0.91 km/h** commercial (4.86 km/h moving)
  3. Route `370` (`460UP`): **1.12 km/h** commercial (5.27 km/h moving)

---

## 2. What's Broken / Dirty in the Data

| Issue | Severity | Affected Component | Impact & Remediation |
| :--- | :---: | :--- | :--- |
| **Duplicate GPS Records** | 🟡 Medium | `vehicle_feed` (GPS AVL) | **82,426 rows (4.18%)** are repeated identical pings emitted in bursts of 2–11 duplicate rows. **Fix**: Deduplicate on `(vehicle_id, timestamp)` before downstream processing. |
| **Coordinate Errors in Stops** | 🟡 Medium | `stops.txt` (GTFS) | **3 corrupt coordinates**:<br>• Stop `2546` (*Libarty*): placed at `(0.0, 0.0)` (Null Island).<br>• Stops `6501` (*Hanuman Mandir*) and `6725` (*Jain Mandir*): longitude was duplicated from latitude (`lon == lat`).<br>**Fix**: Filter with geographic bounding box (`28.0–29.5° N`, `76.5–78.0° E`). |
| **Missing Stop Times Coverage** | 🟠 High | `stop_times.txt` (GTFS) | While `routes.txt` lists 543 routes and `trips.txt` lists 16,562 trips, `stop_times.txt` only contains stop schedules for **195 routes (8,658 trips)**. 348 routes have no stop sequences in the timetable release. |
| **100% Missing GTFS Fields** | ℹ️ Minor | `routes.txt`, `agency.txt` | `route_short_name` is 100% null (route names are under `route_long_name`). `agency_phone` and `agency_fare_url` are 100% null. |
| **High Stationary Proportion** | ℹ️ Expected | `vehicle_feed` (GPS AVL) | **35.36% of all pings** report `speed = 0.0 m/s`. Commercial speed is roughly half of moving speed due to extensive traffic signal queues and passenger boarding delays. |

---

## 3. Repository Structure

```
├── notebooks/
│   └── delhi_transit_eda.ipynb      # Complete Jupyter notebook with all analysis cells
├── src/
│   └── gps_analysis.py              # Modular Python pipeline for AVL feed analysis & charting
├── data/
│   ├── raw/                         # Raw GTFS schedule and AVL databases (git-ignored)
│   ├── stops_map.html               # Interactive Folium map of 8,371 bus stops
│   └── hourly_speed_profile.png     # Plot of commercial vs moving speed by hour
├── .gitignore                       # Configured to ignore data/
└── README.md                        # Project documentation & contributing guidelines
```

---

## 4. Contributing Guidelines (For Interns / Collaborators)

All interns added as collaborators to this repository must follow the branch workflow below. **Direct commits or pushes to the `main` branch are not allowed.**

> Note: `main` only contains the `LICENSE` and `README.md` — it is not used for active development. There is no need to pull the latest `main` into your branch at any point.

### Branch Naming
- Every intern must create their own branch off `main`, named after themselves.
- Suggested naming convention: `firstname-lastname` (all lowercase, hyphen-separated).
  - Example: `john-doe`, `aisha-khan`

### Workflow
```bash
# Clone the repository
git clone https://github.com/springboardmentor441p-coder/Powered-Public-Transit-Route-Optimization.git

# Move into project folder
cd Powered-Public-Transit-Route-Optimization

# Create/checkout your branch
git checkout -b your-name

# Stage and commit your changes
git add .
git commit -m "Add EDA notebook and findings to README"

# Push to YOUR branch only
git push origin your-name
```

### Rules
- ❌ Do **not** push or upload code directly to `main`.
- ❌ Do **not** push code to another intern's branch.
- ✅ Only push/upload code to the branch that carries your own name.
- Keep uploading/pushing your code to your branch regularly as you make progress.
