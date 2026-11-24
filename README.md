# MetroFlow: AI Platform for Metro Crowd Management and Scheduling

**MetroFlow** is an end-to-end AI-powered transit crowd management, predictive demand forecasting, route clustering, and real-time scheduling optimization platform. It features **JWT authentication & RBAC**, **overcrowding alerts**, **emergency disruption broadcasts**, **multi-channel notifications (Email, SMS, Mobile Push, Public Address)**, **corridor congestion heatmaps**, **service delay handling**, **Kubernetes orchestration**, and **containerized Docker deployment**.

---

## 🌟 Key Architecture Modules (100% Implemented)

1. **User Management Module**: Zero-dependency HMAC-SHA256 JWT authentication supporting `Admin`, `Operator`, and `Viewer` roles.
2. **Crowd Monitoring Module**: Real-time passenger density tracking, corridor congestion heatmaps, and station inflow/outflow analysis.
3. **Scheduling Management Module**: Live train/bus schedule management, delay impact prediction, frequency adjustments, and peak-hour optimization.
4. **AI Prediction Module**: Chronologically validated Ridge, Random Forest, and XGBoost models delivering a **6.11% WAPE** on held-out test data, plus unsupervised KMeans route clustering ($K=3$).
5. **Alert & Notification Module**: Real-time overcrowding alerts (>300 rides/hr), emergency broadcast banners, and multi-channel external dispatchers (Email, SMS, Push, PA System).
6. **Analytics Dashboard Module**: Interactive React/Recharts dashboard with 7-day projected demand curves, historical replay engine with $D-1$ cutoff rules, and continuous drift monitoring.
7. **Cloud & DevOps Ready**: Multi-stage `Dockerfile`, `docker-compose.yml`, Kubernetes manifests (`k8s/`), AWS ECS task definitions, and GitHub Actions CI/CD.

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
