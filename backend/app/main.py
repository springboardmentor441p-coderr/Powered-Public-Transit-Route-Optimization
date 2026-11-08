from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .dashboard_ui import get_dashboard_html
from .api import (
    auth,
    dashboard,
    crowd,
    schedule,
    scheduling_optimization,
    monitor,
    prediction,
    analytics,
    alerts,
    notifications,
    announcements,
    schedule_updates,
    ensemble
)

app = FastAPI(
    title="MetroFlow: AI Platform for Metro Crowd Management and Scheduling",
    description=(
        "Comprehensive transit intelligence backend powering GTFS ingestion, "
        "crowd monitoring, frequency optimization, real-time train tracking, "
        "and machine learning passenger demand forecasting."
    ),
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication & User Management"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(crowd.router, prefix="/crowd", tags=["Crowd Monitoring"])
app.include_router(schedule.router, prefix="/schedule", tags=["Train Scheduling & Timetables"])
app.include_router(scheduling_optimization.router, prefix="/scheduling", tags=["Frequency Optimization"])
app.include_router(monitor.router, prefix="/monitor", tags=["Operational Monitoring"])
app.include_router(prediction.router, prefix="/predict", tags=["AI Demand & Crowd Prediction"])
app.include_router(analytics.router, prefix="/analytics", tags=["Traffic Analysis Reports"])
app.include_router(alerts.router, prefix="/alerts", tags=["Alerts Management"])
app.include_router(notifications.router, prefix="/notifications", tags=["In-App Notifications"])
app.include_router(announcements.router, prefix="/announcements", tags=["Emergency Announcements"])
app.include_router(schedule_updates.router, prefix="/schedule-updates", tags=["Operational Schedule Updates"])
app.include_router(ensemble.router, prefix="/ensemble", tags=["Ensemble Prediction"])

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "MetroFlow Transit Platform",
        "database": settings.POSTGRES_DB
    }

# Serve React.js / TypeScript production build at root URL
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse, tags=["Dashboard Web UI"])
    def serve_dashboard():
        return get_dashboard_html()
