# MetroFlow: AI Platform for Public Transit Crowd Management and Scheduling

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19%20%7C%20TypeScript-61dafb.svg)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-Compose%20Ready-2496ed.svg)](https://docker.com)
[![Tests](https://img.shields.io/badge/Tests-28%2F28%20Passed%20(100%25)-success.svg)](#running-automated-tests)
[![GTFS](https://img.shields.io/badge/GTFS-Ingested%20(429k%2B%20rows)-purple.svg)](#data-ingestion)

**MetroFlow** is an enterprise-grade AI public transportation intelligence platform designed for transit authorities, dispatchers, and station operators. It unifies real-time crowd monitoring, predictive demand forecasting, algorithmic headway optimization, delay tracking, operational alert dispatch, and emergency notifications.

---

## 🌟 Platform Highlights Across All Milestones

### Milestone 1: Platform Foundation & Full GTFS Ingestion
- **Security & RBAC:** JWT OAuth2 Bearer authentication, salted password hashing, `admin` and `operator` role management.
- **Full GTFS Dataset Ingestion:** Complete pipeline ingesting **315 routes**, **6,745 stops**, **10,128 trips**, **429,302 stop times**, and **256,823 shapes** from the Pune PMPML dataset.
- **Live Crowd Monitoring:** Station passenger density tracking, platform crowd counts, inflow/outflow rates, and network congestion indexes.
- **Interactive Transit Map:** Geographic visualization with Leaflet, color-coded station congestion markers, and interactive popups.

### Milestone 2: Scheduling, Frequency Optimization & AI Predictions
- **Timetables & Delays:** Route explorers, trip timetable reconstruction, and operational train delay reporting.
- **Algorithmic Frequency Adjustment:** Peak vs. off-peak headway recommendations (`3-5 min` peak target) with supplemental vehicle sizing and overcrowding relief estimation.
- **Machine Learning Demand Lab:** Gradient Boosted Decision Tree models forecasting passenger footfall and density surges across 24-hour diurnal curves.
- **Traffic Analytics:** Network punctuality (OTP), bottleneck identification, and downloadable Markdown reports.

### Milestone 3: Alerts, Notifications & Emergency Workflows
- **Operational Alerts:** Centralized tracking across 7 categories (`SERVICE_ACTIVITY`, `CONGESTION_INDICATOR`, `SCHEDULE_CHANGE`, `DELAY`, `INCIDENT`, `EMERGENCY`, `SYSTEM_EVENT`) with acknowledge and resolve workflows.
- **In-App Notification Center:** Real-time notification feed, dynamic unread badge, and WebSocket live push stream (`/notifications/ws`).
- **Emergency Announcements:** Admin-only high-priority broadcast module with a real-time warning banner across the web UI.
- **Operational Schedule Updates:** Real-time dispatching of delays, cancellations, and extra service runs without corrupting the static GTFS baseline.

### Milestone 4: Integration, Testing, Packaging & Deployment
- **Complete Integration:** Seamless interoperability between React frontend, FastAPI backend, and ML models with zero hardcoded metrics.
- **Production Containerization:** Multi-stage `frontend/Dockerfile` (Nginx) and `backend/Dockerfile`, orchestrated via `docker-compose.yml`.
- **Comprehensive Quality Assurance:** 28/28 automated Pytest test suite covering all modules with a 100% pass rate.
- **Comprehensive Documentation Package:** 22 specialized documentation guides, schemas, and reports.

---

## 🛠️ Quickstart & Local Setup

### 1. Virtual Environment & Dependencies
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r backend/requirements.txt
```

### 2. Configuration (`.env`)
Create a `.env` file at project root (or use existing defaults):
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=transit
JWT_SECRET_KEY=super-secret-key-metroflow-ai
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin123
```
*Note: The platform automatically uses SQLite fallback (`sqlite.db`) when a PostgreSQL server is not locally running.*

### 3. Ingest GTFS & Seed Database
```bash
python -m backend.scripts.ingest_gtfs
```

### 4. Run Server
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
- **Web Interface:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **API Health:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 🐳 Docker Deployment

Run the complete multi-container stack (PostgreSQL, Backend, Frontend) with a single command:
```bash
docker-compose up -d --build
```
- **Frontend App:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8000](http://localhost:8000)

---

## 🧪 Automated Test Suite

Run all unit, operational, and integration tests across all 4 milestones:
```bash
python -m pytest backend/tests -v
```
**Result:** `28 passed in 24.84s (100% pass rate)`

---

## 📚 Technical Documentation Index

| Document | Purpose |
| :--- | :--- |
| [`PROJECT_OVERVIEW.md`](./PROJECT_OVERVIEW.md) | High-level system architecture and feature summary |
| [`PROJECT_ARCHITECTURE.md`](./PROJECT_ARCHITECTURE.md) | Component architecture, data flows, and subsystem diagram |
| [`DATABASE_SCHEMA.md`](./DATABASE_SCHEMA.md) | Table structures, column data types, and primary keys |
| [`DATABASE_RELATIONSHIPS.md`](./DATABASE_RELATIONSHIPS.md) | Entity-Relationship (ER) diagram and foreign key mapping |
| [`DATA_DICTIONARY.md`](./DATA_DICTIONARY.md) | Complete data dictionary for all GTFS and operational entities |
| [`DATASET_AUDIT_REPORT.md`](./DATASET_AUDIT_REPORT.md) | Exact ingested row count audit against original GTFS archive |
| [`KNOWN_DATA_LIMITATIONS.md`](./KNOWN_DATA_LIMITATIONS.md) | Bus vs. metro distinction and data transparency notes |
| [`AUTHENTICATION_DOCUMENTATION.md`](./AUTHENTICATION_DOCUMENTATION.md) | JWT auth specifications, RBAC matrix, and security flows |
| [`API_DOCUMENTATION.md`](./API_DOCUMENTATION.md) | Complete REST API endpoint reference and query parameters |
| [`AI_MODEL_DOCUMENTATION.md`](./AI_MODEL_DOCUMENTATION.md) | ML regression architectures, hyperparams, and features |
| [`SCHEDULING_DOCUMENTATION.md`](./SCHEDULING_DOCUMENTATION.md) | Algorithmic headway optimization formulas and workflows |
| [`ALERT_SYSTEM_DOCUMENTATION.md`](./ALERT_SYSTEM_DOCUMENTATION.md) | 7 alert categories, notifications, and WebSocket push stream |
| [`TRAFFIC_ANALYSIS_REPORT.md`](./TRAFFIC_ANALYSIS_REPORT.md) | Network traffic analysis, punctuality (OTP), and bottlenecks |
| [`TEST_REPORT.md`](./TEST_REPORT.md) | Verbose pytest test results across all 28 test cases |
| [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) | Production Docker, AWS ECS, GCP, and Kubernetes setup guide |
| [`MILESTONE_1_REPORT.md`](./MILESTONE_1_REPORT.md) | Milestone 1 verification and deliverable details |
| [`MILESTONE_2_REPORT.md`](./MILESTONE_2_REPORT.md) | Milestone 2 verification and deliverable details |
| [`MILESTONE_3_REPORT.md`](./MILESTONE_3_REPORT.md) | Milestone 3 verification and deliverable details |
| [`MILESTONE_4_REPORT.md`](./MILESTONE_4_REPORT.md) | Milestone 4 verification and deliverable details |
| [`FINAL_PROJECT_REPORT.md`](./FINAL_PROJECT_REPORT.md) | Executive project summary and completion certificate |
| [`MILESTONE_PROGRESS.md`](./MILESTONE_PROGRESS.md) | Live milestone tracking and verification checkpoint status |
