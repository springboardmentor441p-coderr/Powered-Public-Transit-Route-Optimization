# RouteRanker: AI-Powered Public Transit Route Optimization & Demand Platform

---

## 🛠️ Complete Technical Skills & Tech Stack Summary

### 1. Frontend Development
* **Framework**: React 18 (TypeScript 5.6)
* **Build Tool & Bundler**: Vite 5.4 (Hot Module Replacement)
* **Styling & Design System**: Tailwind CSS 3.4 (Custom dark mode transit theme)
* **Iconography**: Lucide React (feather-style vector icons)
* **Data Visualization & Charting**: Recharts 2.13 (Interactive responsive line charts, multi-metric bar charts, tooltip aggregators)
* **State & Network Management**: React Hooks (`useState`, `useEffect`, `useCallback`), Browser `localStorage` token storage, Async Fetch API

### 2. Backend Engineering
* **Web Framework**: FastAPI (High-performance asynchronous Python REST API)
* **ASGI Server**: Uvicorn (Fast ASGI runtime with auto-reload)
* **Data Validation & Schemas**: Pydantic v2 (Strict type checking, request/response models)
* **Security & Authentication**: 
  * Role-Based Access Control (RBAC): `admin`, `operator`, `viewer`
  * Cryptographic Password Hashing: Salted SHA-256
  * Token Format: Stateless HMAC-SHA256 JSON Web Tokens (JWT)
* **CORS & Middleware**: CORSMiddleware configured for strict local origin routing

### 3. Machine Learning & Data Science
* **Core Libraries**: `scikit-learn`, `numpy`, `pandas`, `scipy`
* **Route Clustering**:
  * Unsupervised **KMeans Clustering** (Dynamic $K=2, 3, 4, 5$)
  * Dimensionality & Spatial Validation: Silhouette Score evaluation ($0.2935$)
  * Tier segmentation: High-Volume Trunk Corridors, Core Corridors, Moderate-Demand Coverage
* **Demand Forecasting & Predictive Modeling**:
  * Regularized **Ridge Regression (L2)**, **Random Forest**, Gradient Boosting, Day-of-Week historical baselines
  * Multi-horizon forward forecasting (7-day horizon with $\pm5\%$ statistical confidence intervals)
  * Error metrics: Weighted Absolute Percentage Error (**WAPE: 18.2%**), Mean Absolute Error (MAE), Root Mean Squared Error (RMSE)
* **Optimization Algorithms**:
  * Goal-driven fleet reallocation engine across 4 operational objectives:
    1. *Maximize Ridership*
    2. *Minimize Overcrowding*
    3. *Cost Reduction*
    4. *Balanced Headways*

### 4. Data Engineering & Integrity
* **Transit Standards**: General Transit Feed Specification (GTFS) ingestion (`routes.txt`, `trips.txt`, `stop_times.txt`, `stops.txt`, `calendar.txt`)
* **Data Provenance**: Cryptographic SHA-256 checksums per dataset snapshot with audit trail (`provenance.json`)
* **Spatial & Network Metrics**: Stop exclusivity ratio, route stop counts, headway variance, hourly passenger density

### 5. DevOps, Testing & Containerization
* **Containerization**: Multi-stage `Dockerfile` and `docker-compose.yml`
* **Automated Testing**: `pytest` comprehensive test suite covering schema validation, RBAC security, optimization math, and ML endpoints
* **Version Control**: Git & GitHub branch management (`origin/Priyanka-Jambagi`)

---

# 📑 Slide-by-Slide Presentation Content

---

### Slide 1: Outline
* **Project Title**: RouteRanker – AI-Powered Public Transit Route Optimization & Demand Intelligence
* **Presentation Agenda**:
  1. Problem Statement & Urban Mobility Challenges
  2. Core Project Objectives
  3. Novelty of the Proposed System
  4. Base Paper & Literature Review
  5. End-to-End System Architecture
  6. Dataset Description & Provenance
  7. Proposed Methodology & Mathematical Formulation
  8. Live Output Screenshots & Feature Demonstrations
  9. Conclusion & Future Enhancements
  10. Step-by-Step Application Usage Manual

---

### Slide 2: Problem Statement
* **The Transit Dilemma**: Rapid urbanization across Indian metropolitan cities has created severe imbalances in bus transit networks.
* **Key Challenges**:
  * **Severe Peak Overcrowding**: Major arterial trunk routes suffer from dangerous crush loads during morning (06:00–09:00) and evening (15:00–19:00) rush hours.
  * **Empty Off-Peak Runs**: Peripheral coverage routes operate large buses with low load factors, leading to massive fuel and driver wage waste.
  * **Static, Inflexible Timetables**: Existing transit schedules are updated annually or seasonally, failing to react to real-time surges, events, or weather disruptions.
  * **Data Silos**: Planners lack unified digital platforms that connect raw GTFS timetable feeds with machine learning demand forecasts and actionable dispatch tools.

---

### Slide 3: Objectives
1. **Automate GTFS Ingestion & Cleaning**: Reconcile scheduled trips with real-world passenger ridership logs across 1.39M+ transaction records.
2. **Accurate Demand Forecasting**: Predict daily and hourly route ridership with low error using machine learning models (outperforming static baselines).
3. **Dynamic Route Clustering**: Automatically segment transit networks into distinct operational tiers using unsupervised learning ($K$-Means with Silhouette validation).
4. **AI-Driven Fleet Optimization**: Provide an automated solver to shift bus trips from underutilized routes to overcrowded corridors without expanding fleet budget.
5. **Interactive Operations Dashboard**: Deliver a production-ready Web UI with Role-Based Access Control, live emergency broadcasts, and scenario stress calculators.

---

### Slide 4: Novelty of Proposed System
* **Closed-Loop "Prediction to Execution" Pipeline**: Unlike traditional academic projects that stop at static graphs, RouteRanker couples ML predictions directly with a one-click schedule deployment engine.
* **Causal Service Scenario Simulator**: Allows dispatchers to stress-test hypothetical "what-if" conditions (e.g., +30% festival surge or -20% fuel rationing) before dispatching a single bus.
* **Dynamic On-the-Fly Reclustering**: Planners can adjust cluster counts ($K=2$ to $5$) directly from the UI and watch the algorithm re-segment routes in real time.
* **Enterprise Security & Auditability**: Incorporates role-based permissions (Admin, Operator, Viewer), JWT authentication, and SHA-256 data integrity proofs.

---

### Slide 5: Base Paper & Literature Review
* **Base Reference**: 
  * *Title*: "Short-Term Public Transit Passenger Demand Forecasting and Dynamic Route Scheduling Using Machine Learning"
  * *Domain*: IEEE Transactions on Intelligent Transportation Systems / Elsevier Transportation Research Part C.
* **Key Insights from Prior Art**:
  * Static linear models fail to capture non-linear ridership shifts between weekdays, weekends, and holidays.
  * Clustering routes by passenger density and stop exclusivity significantly reduces forecasting error compared to global network models.
* **RouteRanker Enhancements over Base Paper**:
  * Integrates real-time optimization directly onto ML forecasts.
  * Adds multi-horizon 7-day predictive confidence bounds.
  * Replaces slow batch jobs with sub-second FastAPI endpoints and an interactive React dashboard.

---

### Slide 6: System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PRESENTATION LAYER (Frontend)                         │
│  React 18  •  TypeScript  •  Tailwind CSS  •  Recharts  •  Lucide Icons     │
│  [Network Overview] [Route Optimization] [Demand Forecasting] [Clustering]  │
│  [Review Priorities] [Service Scenarios] [Congestion Heatmap] [Alerts/RBAC] │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / JSON REST APIs (JWT Auth)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                        API & BUSINESS LOGIC (Backend)                       │
│  FastAPI Runtime  •  Uvicorn  •  Pydantic v2  •  HMAC-SHA256 Token Engine   │
│  ├── /api/auth               ── Login & Role Permission Gatekeeper         │
│  ├── /api/optimization/run   ── Multi-Objective Reallocation Solver        │
│  ├── /api/demand/routes      ── 7-Day Forecasting & Hourly Profiles         │
│  ├── /api/clustering         ── Dynamic K-Means & Silhouette Evaluation    │
│  ├── /api/alerts             ── Overcrowding Detection & Emergency Banner   │
│  └── /api/scenarios/run      ── Elasticity & Sensitivity Engine             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                     ANALYTICS & MACHINE LEARNING LAYER                      │
│  scikit-learn  •  NumPy  •  Pandas  •  Pre-trained Model Artifacts          │
│  ├── Clustering: KMeans (k=2..5), Silhouette Score (0.2935)                │
│  ├── Forecaster: Ridge Regression (WAPE 18.2%), Random Forest, Baselines    │
│  └── Feature Store: Daytype, Peak Windows, Headway Ratios, Exclusivity      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                         DATA INGESTION & STORAGE                            │
│  GTFS Tables (routes, trips, stops, stop_times, calendar)                   │
│  1,399,737 Clean Ridership Records  •  SHA-256 Provenance Ledger           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Slide 7: Dataset Description
* **Primary Source**: General Transit Feed Specification (GTFS) public transit feeds & Lepton Software Indian Transit Benchmarks.
* **Core Dataset Files**:
  1. `routes.txt`: Route IDs, short/long names, corridor classifications.
  2. `trips.txt`: Trip identifier mappings linked to active route schedules.
  3. `stop_times.txt`: Arrival/departure timestamps, sequences, and stop identifiers.
  4. `stops.txt`: Geographical stop locations (latitudes, longitudes).
  5. `calendar.txt`: Operational service schedules (Weekday `W`, Saturday `A`, Sunday/Holiday `U`).
* **Ridership Data Profile**:
  * **Clean Transaction Rows**: 1,399,737 records
  * **Matched Route-Date Pairs**: 100,578 historical points
  * **Reconciled Indian Corridors**: 10 high-density bus routes
  * **Data Integrity**: Every file version-controlled with SHA-256 cryptographic hashes in `provenance.json`.

---

### Slide 8: Proposed Methodology

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Raw Data      │ ──> │   Feature Eng.   │ ──> │   AI Modeling    │
│ • GTFS Feeds    │     │ • Peak Windows   │     │ • KMeans Tiers   │
│ • Ridership Logs│     │ • Daytype Flags  │     │ • Ridge L2 WAPE  │
│ • Stop Records  │     │ • Headway Spread │     │ • Demand Curves  │
└─────────────────┘     └──────────────────┘     └──────────────────┘
                                                           │
                                                           ▼
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Live Schedule  │ <── │ Optimization Run │ <── │  Decision Logic  │
│  Deployment     │     │ • Trip Deltas    │     │ • Overcrowding   │
│ • New Dispatch  │     │ • Fleet Shifting │     │ • Cost Reduction │
│ • Push to GTFS  │     │ • Headway Smooth │     │ • Balanced Loads │
└─────────────────┘     └──────────────────┘     └──────────────────┘
```

#### Step-by-Step Methodology:
1. **Data Ingestion & Cleaning**: Reconcile timestamps, remove missing entries, and match GTFS scheduled departures with observed passenger boardings.
2. **Feature Engineering**: Extract time-of-day buckets (Morning Peak, Mid-Day, Evening Peak, Night), weekend indicators, and stop exclusivity percentages.
3. **Unsupervised Route Stratification**: Cluster corridors using $K$-Means based on daily passenger load and frequency, validated with Silhouette analysis.
4. **Supervised Demand Forecasting**: Train predictive models (Ridge Regression, Random Forest) on matched historical data to forecast future daily ridership.
5. **Optimization Engine**: Given forecasted passenger demand and a fixed fleet size, reallocate scheduled trips to minimize overcrowding while respecting operational headway constraints.
6. **Execution & Feedback Loop**: Dispatchers review proposed trip additions/reductions and deploy the schedule update directly into the production database.

---

### Slide 9: Output Screenshots & Feature Showcase

* **Screenshot 1: Network Overview**
  * Displays global network health cards: 1.39M clean rows, 100K matched pairs, 18.2% forecaster WAPE, and 10 route grouping cards.
* **Screenshot 2: AI Route Optimization Engine**
  * Displays the objective picker (*Maximize Ridership*, *Minimize Overcrowding*, *Cost Reduction*, *Balanced Headways*), fleet shift slider, and route-by-route trip delta recommendations (+18 trips for Route 79, -15 trips for Route 20).
* **Screenshot 3: Route Demand Analytics**
  * Displays 7-day multi-horizon forward forecast graphs with shaded confidence intervals, peak window distributions, and elasticity ratings.
* **Screenshot 4: AI Route Clustering Explorer**
  * Displays interactive $K$-means clustering ($K=3$, Silhouette Score: 0.2935) with tier breakdowns for High-Volume Trunk, Core Corridor, and Coverage.
* **Screenshot 5: Service Scenario Simulator**
  * Displays the "what-if" calculator showing baseline vs simulated output when testing 130 trips (+38.3%) with a 10% demand surge (`1.1` multiplier).
* **Screenshot 6: Alerts & Emergency Broadcasts**
  * Real-time banner ticker broadcasting route delays and overcrowding alerts across the network.

---

### Slide 10: Conclusion & Future Enhancements

#### Key Achievements:
* Successfully engineered a full-stack, AI-powered public transit intelligence system meeting 100% of the project specification.
* Reduced forecasting error down to **18.2% WAPE**, outperforming standard moving-average heuristics.
* Automated trip reallocation to relieve dangerous peak hour overcrowding without increasing total fleet operational budget.
* Integrated enterprise-grade Role-Based Access Control and modern containerized architecture.

#### Future Enhancements:
1. **GPS Telematics Stream**: Integrate live GTFS-Realtime (GTFS-RT) protobuf streams for sub-minute live bus tracking.
2. **Electric Vehicle (EV) Battery State-of-Charge (SoC) Constraints**: Add battery charging depot schedule constraints into the optimization algorithm.
3. **Multi-Modal Metro & Bus Feeder Sync**: Align feeder bus arrival times directly with metro train arrival schedules at major intermodal transit hubs.

---

### Slide 11: End-to-End Application Usage Guide (From Sign-In to End)

```
[ Step 1: Sign In ] ──> [ Step 2: Overview ] ──> [ Step 3: Run AI Optimizer ]
                                                              │
                                                              ▼
[ Step 6: Deploy Plan ] <── [ Step 5: Test Scenario ] <── [ Step 4: Demand & Clusters ]
```

1. **Step 1: Sign In with Role-Based Access**
   * Navigate to `http://localhost:5173`.
   * Click **"Sign In"** in the top navigation bar.
   * Choose your role:
     * **Admin** (`admin` / `admin123`): Full access to optimize, deploy schedules, and broadcast emergency alerts.
     * **Operator** (`operator` / `operator123`): Operational schedule updates and alerts.
     * **Viewer** (`viewer` / `viewer123`): View-only analytics.
2. **Step 2: Monitor Network Health (Tab 1: Network Overview)**
   * View network-wide metrics (1.39M rows, 18.2% WAPE model performance).
   * Check route cards to identify route tiers and stop exclusivity.
3. **Step 3: Run Route Optimization (Tab 2: Route Optimization)**
   * Select your goal (e.g., **"Minimize Overcrowding"**).
   * Set your **Fleet Reallocation Budget** (e.g., 15%).
   * Click **"Run AI Optimization"**.
   * Review the generated recommendations (e.g. Route 79 adds +18 trips; Route 20 reduces 15 trips).
   * Click **"Apply Optimized Plan"** to automatically publish updates to active dispatch!
4. **Step 4: Analyze Demand Patterns (Tab 3: Route Demand)**
   * Select a route (e.g., Route 79).
   * Review the **7-Day Forward Forecast** chart with upper and lower confidence intervals.
   * Check the hourly breakdown: see morning peak vs mid-day vs evening rush hour loads.
5. **Step 5: Explore Route Tiers (Tab 4: AI Clustering)**
   * View the KMeans grouping and Silhouette score.
   * Move the cluster slider ($K = 2, 3, 4, 5$) and click **"Recluster Transit Network"** to re-segment the routes dynamically.
6. **Step 6: Stress Test Scenarios (Tab 8: Service Scenarios)**
   * Enter proposed daily trips (e.g., `130`) and an assumed demand multiplier (e.g., `1.1` for a 10% surge).
   * Click **"Calculate Scenario"** to evaluate passenger load per bus and driver operating hours before committing.
7. **Step 7: Manage Alerts & Broadcast Emergency Notices (Tab 10: Active Alerts)**
   * Review active overcrowding alerts.
   * Acknowledge alerts as an Operator/Admin.
   * Create an Emergency Notice (e.g. *"Heavy rain along Route 79 corridor, express shuttles added"*) to broadcast a network-wide live ticker across all user dashboards.
