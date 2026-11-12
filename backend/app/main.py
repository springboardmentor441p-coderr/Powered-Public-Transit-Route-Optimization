"""
RouteRanker: FastAPI Application Main Entry Point
AI-Powered Public Transit Monitoring, Crowd Forecasting, and Route Optimization
Target System: Chicago Transit Authority (CTA), Chicago, USA
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.app.api.transit_routes import router as transit_router
from backend.app.api.analytics_routes import router as analytics_router
from backend.app.api.planning_routes import router as planning_router

load_dotenv()

app = FastAPI(
    title="RouteRanker CTA Transit API",
    description="Official Chicago Transit Authority (CTA) Analytics, Real-Time Monitoring & Optimization API",
    version="1.0.0"
)

# Configure CORS for local React/Vite development
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(transit_router)
app.include_router(analytics_router)
app.include_router(planning_router)

@app.get("/")
def root_status():
    return {
        "application": "RouteRanker",
        "description": "Chicago Transit Authority Real-Time Monitoring & Demand Forecasting Platform",
        "status": "Operational",
        "system": "Chicago Transit Authority (CTA), Chicago, USA",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "RouteRanker Backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)

