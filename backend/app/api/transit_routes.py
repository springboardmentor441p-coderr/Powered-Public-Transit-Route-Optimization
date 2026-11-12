"""
RouteRanker: Transit Monitoring REST Endpoints
Exposes clean FastAPI endpoints for CTA live telemetry, vehicle positions,
estimated arrivals, active customer alerts, and system health status.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
import os
import pandas as pd
from datetime import datetime, timezone

from backend.app.schemas.transit_schemas import (
    BusVehiclePosition, BusArrivalPrediction, TrainPosition,
    TrainArrivalPrediction, TransitAlert, TransitStatusResponse, APIResponseMetadata
)
from backend.app.services.cta_bus_client import cta_bus_client
from backend.app.services.cta_train_client import cta_train_client
from backend.app.services.cta_alerts_client import cta_alerts_client
from backend.app.services.transit_cache import global_transit_cache

router = APIRouter(prefix="/api/transit", tags=["Real-Time Transit Telemetry"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

@router.get("/status", response_model=TransitStatusResponse)
def get_transit_system_status():
    """
    Returns API connectivity status, auth flags, cache freshness, and telemetry counts.
    """
    alerts = cta_alerts_client.get_live_alerts()
    buses, _ = cta_bus_client.get_vehicle_positions()
    trains, _ = cta_train_client.get_train_positions()
    
    mode = "HYBRID_LIVE_AND_SIMULATED"
    if cta_bus_client.is_configured and cta_train_client.is_configured:
        mode = "OFFICIAL_LIVE_CTA_APIS"
    elif not cta_bus_client.is_configured and not cta_train_client.is_configured:
        mode = "GTFS_SCHEDULE_SIMULATION_WITH_LIVE_ALERTS"

    return TransitStatusResponse(
        bus_api_configured=cta_bus_client.is_configured,
        train_api_configured=cta_train_client.is_configured,
        alerts_api_active=True,
        bus_vehicle_count=len(buses),
        train_count=len(trains),
        active_alerts_count=len(alerts),
        last_system_refresh=datetime.now(timezone.utc).isoformat(),
        cache_ttl_seconds=30,
        data_source_mode=mode
    )

@router.get("/bus/vehicles")
def get_bus_vehicle_positions(route: Optional[str] = Query(None, description="Optional bus route number (e.g. 79, 9, 66)")):
    """
    Returns current bus positions, headings, speeds, and delay flags.
    NOTE: Vehicle positions represent geographic locations, NOT passenger occupancy.
    """
    vehicles, meta = cta_bus_client.get_vehicle_positions(route_id=route)
    return {
        "metadata": meta.model_dump(),
        "count": len(vehicles),
        "vehicles": [v.model_dump() for v in vehicles]
    }

@router.get("/bus/predictions")
def get_bus_predictions(stop_id: str = Query(..., description="CTA Bus Stop ID")):
    """
    Returns estimated arrival countdowns for a specific bus stop.
    """
    predictions, meta = cta_bus_client.get_arrival_predictions(stop_id=stop_id)
    return {
        "metadata": meta.model_dump(),
        "count": len(predictions),
        "predictions": [p.model_dump() for p in predictions]
    }

@router.get("/train/positions")
def get_train_positions(line: Optional[str] = Query(None, description="Optional line: Red, Blue, Brown, Green, Orange, Purple, Pink, Yellow")):
    """
    Returns current CTA train coordinates, headings, and approaching indicators.
    """
    trains, meta = cta_train_client.get_train_positions(line_name=line)
    return {
        "metadata": meta.model_dump(),
        "count": len(trains),
        "trains": [t.model_dump() for t in trains]
    }

@router.get("/train/arrivals")
def get_train_arrivals(station_id: str = Query(..., description="CTA Station ID (MAP_ID, e.g. 41700, 40380)")):
    """
    Returns live platform arrival predictions for a CTA rapid transit station.
    """
    arrivals, meta = cta_train_client.get_station_arrivals(station_id=station_id)
    return {
        "metadata": meta.model_dump(),
        "count": len(arrivals),
        "arrivals": [a.model_dump() for a in arrivals]
    }

@router.get("/alerts")
def get_service_alerts(
    route_or_line: Optional[str] = Query(None, description="Filter alerts by line or bus route"),
    route_id: Optional[str] = Query(None, description="Alternative param for route or bus line")
):
    """
    Returns official live CTA service disruptions, reroutes, and elevator status.
    Source: https://www.transitchicago.com/api/1.0/alerts.aspx?outputType=JSON
    """
    target = route_or_line or route_id
    alerts = cta_alerts_client.get_live_alerts(route_or_line=target)
    return {
        "metadata": {
            "data_source": "OFFICIAL_CTA_CUSTOMER_ALERTS_LIVE",
            "is_live_api_active": True,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "count": len(alerts)
        },
        "count": len(alerts),
        "total_alerts": len(alerts),
        "alerts": [a.model_dump() for a in alerts]
    }

@router.get("/bus/routes")
def get_available_bus_routes():
    """
    Returns list of all active GTFS CTA bus routes with colors and descriptions.
    """
    routes_path = os.path.join(PROCESSED_DIR, "cleaned_gtfs_routes.csv")
    if not os.path.exists(routes_path):
        raise HTTPException(status_code=404, detail="Routes dataset not found")
        
    df_routes = pd.read_csv(routes_path)
    bus_routes = df_routes[df_routes["transit_mode"] == "Bus"].to_dict(orient="records")
    return {
        "count": len(bus_routes),
        "routes": bus_routes
    }

@router.get("/stations")
def get_all_rail_stations():
    """
    Returns directory of all 144 CTA rapid transit stations with GPS coordinates and lines served.
    """
    st_path = os.path.join(PROCESSED_DIR, "cleaned_l_stations_directory.csv")
    if not os.path.exists(st_path):
        raise HTTPException(status_code=404, detail="Station directory not found")
        
    df_st = pd.read_csv(st_path)
    return {
        "count": len(df_st),
        "stations": df_st.to_dict(orient="records")
    }

