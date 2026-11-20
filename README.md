# RouteRanker: AI-Powered Public Transit Intelligence Platform

RouteRanker is an end-to-end transit analytics, machine learning forecasting, route clustering, and scenario simulation platform with **JWT authentication & RBAC**, **overcrowding alerts**, **emergency broadcast announcements**, **congestion heatmaps**, and **containerized Docker deployment**.

---

## 🌟 Key Features

1. **AI Demand Forecasting**: Chronologically validated Ridge, Random Forest, and XGBoost models delivering a **6.11% WAPE** on held-out test data.
2. **KMeans Route Clustering**: Unsupervised grouping into High-Volume Trunk, Core Corridor, and Coverage tiers.
3. **Productivity Rankings**: Routes ranked by passenger productivity (*Rides per Scheduled Service Hour* and *Rides per Scheduled Trip*).
4. **Historical Replay Engine**: Virtual clock with strict `D-1` cutoff policies to prevent future data leakage during backtesting.
5. **Conditional Service Scenarios**: What-if calculator for planners to test frequency adjustments and demand multipliers.
6. **Authentication & RBAC (Milestone 1)**: Zero-dependency HMAC-SHA256 JWT authentication supporting `Admin`, `Operator`, and `Viewer` roles.
7. **Overcrowding & Capacity Alerts (Milestone 3)**: Automated real-time alerts when routes exceed density thresholds (>300 rides/hr).
8. **Emergency Broadcast System (Milestone 3)**: System-wide transit disruption announcements and live banner ticker.
9. **Corridor Congestion Heatmap (Milestone 2 & 3)**: Visual route density indicators categorized as Critical, High, or Moderate load.
10. **Live Schedule Updates (Milestone 2 & 3)**: Authorized operator workflow to submit and log operational schedule adjustments.
11. **Automated Verification Suite (Milestone 4)**: 16 automated tests covering data integrity, lag features, scenario math, auth, and API workflows.
12. **Docker Containerization (Milestone 4)**: Multi-stage Dockerfile and `docker-compose.yml` for unified deployment.

---

## 🚀 Quickstart

### Option 1: Local Development

```bash
# 1. Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate sample data & run analytics pipeline
python analytics/00_generate_sample_data.py
python analytics/run_pipeline.py

# 4. Train ML models
python train_models.py

# 5. Start the FastAPI backend (Port 8000)
uvicorn backend.main:app --reload --port 8000

# 6. Start the React frontend (Port 5173 - In a separate terminal)
cd frontend
npm install
npm run dev
```

### Option 2: Docker Container Deployment

```bash
docker-compose up --build
```
The application will be accessible at `http://localhost:8000`.

---

## 🔑 Default User Accounts

| Username | Password | Role | Permissions |
| :--- | :--- | :--- | :--- |
| **`admin`** | `admin123` | **Admin** | Full system access, alert config, schedule management |
| **`operator`** | `operator123` | **Operator** | Manage schedules, broadcast emergency alerts, view analytics |
| **`viewer`** | `viewer123` | **Viewer** | Read-only access to analytics, forecasts, and rankings |

---

## 📡 API Endpoints Reference

### Authentication
* `POST /api/auth/login`: Authenticate with username and password, returns JWT token.
* `GET /api/auth/me`: Get profile of the currently signed-in user (requires Bearer token).

### Alerts & Notifications
* `GET /api/alerts`: List active overcrowding alerts.
* `POST /api/alerts/configs`: Create custom threshold configuration (Operator/Admin).
* `POST /api/alerts/{alert_id}/acknowledge`: Mark an alert as reviewed.
* `GET /api/notifications`: Retrieve full system notification audit trail.

### Emergency Broadcasts
* `GET /api/broadcasts`: List all emergency disruption notices.
* `POST /api/broadcasts`: Publish a new public announcement (Operator/Admin).
* `POST /api/broadcasts/{id}/deactivate`: Deactivate an announcement banner.

### Congestion & Scheduling
* `GET /api/heatmap`: Get corridor congestion heatmap intensities.
* `GET /api/schedule-updates`: Retrieve log of applied schedule modifications.
* `POST /api/schedule-updates`: Submit an authorized schedule change (Operator/Admin).

### Core Transit Analytics
* `GET /api/data/coverage`: Dataset provenance, GTFS snapshots, and model evaluation metrics.
* `GET /api/routes`: Route catalog with KMeans cluster labels and stop counts.
* `GET /api/routes/{route}/history`: Cutoff-aware historical boardings and route coordinates.
* `GET /api/rankings`: Productivity leaderboard sorted by rides/hour.
* `GET /api/routes/compare`: Side-by-side comparison with corridor stop overlap.
* `POST /api/forecasts`: Live ML daily ridership inference.
* `POST /api/replays`: Initialize a stateful historical replay session.
* `POST /api/replays/{id}/control`: Play, Pause, Advance, or Reset replay clock.
* `POST /api/scenarios`: Run conditional service scenario simulation.

---

## 🧪 Testing

Run the automated verification suite with pytest:
```bash
pytest tests/ -v
```
All **16 tests** validate GTFS calendar exceptions, directional reconciliation, lag engineering, scenario arithmetic, JWT authentication, RBAC authorization, alerts lifecycle, emergency broadcasts, and congestion heatmap generation.
