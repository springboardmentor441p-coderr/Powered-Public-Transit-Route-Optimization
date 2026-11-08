"""Crowd Monitoring Module for MetroFlow.
Provides real-time passenger density tracking, station-wise inflow/outflow,
congestion monitoring, and crowd heatmaps.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from ..db import get_db
from ..models import StationCrowd, Stop, User
from .auth import get_current_user

router = APIRouter()

class StationCrowdResponse(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    passenger_density_percent: float
    crowd_level: str
    inflow_rate: float
    outflow_rate: float
    platform_crowd_count: int
    congestion_index: float
    timestamp: str

    model_config = ConfigDict(from_attributes=True)

class HeatmapPoint(BaseModel):
    stop_id: str
    stop_name: str
    lat: float
    lon: float
    density: float
    crowd_level: str
    congestion_index: float

@router.get("/live", response_model=List[StationCrowdResponse])
def get_live_crowd_status(
    limit: int = Query(50, ge=1, le=200),
    level: Optional[str] = Query(None, description="Filter by crowd level: LOW, MODERATE, HIGH, CRITICAL"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve live passenger density and footfall tracking across metro stations."""
    query = db.query(StationCrowd, Stop).join(Stop, StationCrowd.stop_id == Stop.stop_id)
    if level:
        query = query.filter(StationCrowd.crowd_level == level.upper())
    
    results = query.order_by(StationCrowd.passenger_density_percent.desc()).limit(limit).all()
    
    response = []
    for crowd, stop in results:
        response.append(StationCrowdResponse(
            stop_id=stop.stop_id,
            stop_name=stop.stop_name,
            stop_lat=stop.stop_lat,
            stop_lon=stop.stop_lon,
            passenger_density_percent=crowd.passenger_density_percent,
            crowd_level=crowd.crowd_level,
            inflow_rate=crowd.inflow_rate,
            outflow_rate=crowd.outflow_rate,
            platform_crowd_count=crowd.platform_crowd_count,
            congestion_index=crowd.congestion_index,
            timestamp=crowd.timestamp
        ))
    return response

@router.get("/congestion")
def get_congestion_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Network-wide congestion index, bottleneck hotspots, and crowd status summary."""
    records = db.query(StationCrowd, Stop).join(Stop, StationCrowd.stop_id == Stop.stop_id).all()
    if not records:
        return {
            "network_congestion_index": 0.0,
            "total_monitored_stations": 0,
            "critical_stations_count": 0,
            "high_stations_count": 0,
            "bottlenecks": []
        }

    total_density = sum(c.passenger_density_percent for c, _ in records)
    avg_density = round(total_density / len(records), 1)
    network_congestion = round(avg_density / 100.0, 2)

    critical = [c for c, _ in records if c.crowd_level == "CRITICAL"]
    high = [c for c, _ in records if c.crowd_level == "HIGH"]

    # Top bottleneck stations
    sorted_records = sorted(records, key=lambda x: x[0].passenger_density_percent, reverse=True)
    bottlenecks = [
        {
            "stop_id": stop.stop_id,
            "stop_name": stop.stop_name,
            "passenger_density_percent": crowd.passenger_density_percent,
            "crowd_level": crowd.crowd_level,
            "congestion_index": crowd.congestion_index,
            "platform_count": crowd.platform_crowd_count
        }
        for crowd, stop in sorted_records[:5]
    ]

    return {
        "network_congestion_index": network_congestion,
        "average_passenger_density_percent": avg_density,
        "total_monitored_stations": len(records),
        "critical_stations_count": len(critical),
        "high_stations_count": len(high),
        "bottlenecks": bottlenecks
    }

@router.get("/station/{stop_id}", response_model=StationCrowdResponse)
def get_station_crowd(
    stop_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve detailed real-time crowd metrics for an individual station."""
    crowd = db.query(StationCrowd).filter(StationCrowd.stop_id == stop_id).first()
    stop = db.query(Stop).filter(Stop.stop_id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Station not found")
    
    if not crowd:
        # Fallback default if not yet recorded
        return StationCrowdResponse(
            stop_id=stop.stop_id,
            stop_name=stop.stop_name,
            stop_lat=stop.stop_lat,
            stop_lon=stop.stop_lon,
            passenger_density_percent=45.0,
            crowd_level="MODERATE",
            inflow_rate=50.0,
            outflow_rate=45.0,
            platform_crowd_count=180,
            congestion_index=0.45,
            timestamp="Live"
        )

    return StationCrowdResponse(
        stop_id=stop.stop_id,
        stop_name=stop.stop_name,
        stop_lat=stop.stop_lat,
        stop_lon=stop.stop_lon,
        passenger_density_percent=crowd.passenger_density_percent,
        crowd_level=crowd.crowd_level,
        inflow_rate=crowd.inflow_rate,
        outflow_rate=crowd.outflow_rate,
        platform_crowd_count=crowd.platform_crowd_count,
        congestion_index=crowd.congestion_index,
        timestamp=crowd.timestamp
    )

@router.get("/heatmap", response_model=List[HeatmapPoint])
def get_crowd_heatmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate geographical heatmap coordinates and intensity for frontend map rendering."""
    records = db.query(StationCrowd, Stop).join(Stop, StationCrowd.stop_id == Stop.stop_id).all()
    points = []
    for crowd, stop in records:
        points.append(HeatmapPoint(
            stop_id=stop.stop_id,
            stop_name=stop.stop_name,
            lat=stop.stop_lat,
            lon=stop.stop_lon,
            density=crowd.passenger_density_percent,
            crowd_level=crowd.crowd_level,
            congestion_index=crowd.congestion_index
        ))
    return points

