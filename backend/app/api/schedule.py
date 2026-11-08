"""Train Scheduling & Delay Handling Module for MetroFlow.
Handles train schedules, timetables, active routes, and delay management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from ..db import get_db
from ..models import Route, Trip, StopTime, Stop, TrainStatus, User
from .auth import get_current_user

router = APIRouter()

class RouteResponse(BaseModel):
    route_id: str
    agency_id: str
    route_short_name: Optional[str] = None
    route_long_name: Optional[str] = None
    route_type: int
    route_color: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class TripResponse(BaseModel):
    trip_id: str
    route_id: str
    service_id: str
    trip_headsign: Optional[str] = None
    direction_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class StopTimeScheduleItem(BaseModel):
    stop_sequence: int
    stop_id: str
    stop_name: str
    arrival_time: str
    departure_time: str

class DelayReportRequest(BaseModel):
    trip_id: str
    delay_minutes: int
    current_station_id: Optional[str] = None
    notes: Optional[str] = None

@router.get("/routes", response_model=List[RouteResponse])
def get_routes(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all available metro and transit lines/routes."""
    return db.query(Route).limit(limit).all()

@router.get("/trips", response_model=List[TripResponse])
def get_trips(
    route_id: Optional[str] = None,
    direction_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve scheduled trips, optionally filtered by route and direction."""
    query = db.query(Trip)
    if route_id:
        query = query.filter(Trip.route_id == route_id)
    if direction_id is not None:
        query = query.filter(Trip.direction_id == direction_id)
    return query.limit(limit).all()

@router.get("/timetable/{trip_id}", response_model=List[StopTimeScheduleItem])
def get_trip_timetable(
    trip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the full chronological station timetable for a specific train trip."""
    rows = (
        db.query(StopTime, Stop)
        .join(Stop, StopTime.stop_id == Stop.stop_id)
        .filter(StopTime.trip_id == trip_id)
        .order_by(StopTime.stop_sequence.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No timetable found for trip {trip_id}")

    return [
        StopTimeScheduleItem(
            stop_sequence=st.stop_sequence,
            stop_id=stop.stop_id,
            stop_name=stop.stop_name,
            arrival_time=st.arrival_time,
            departure_time=st.departure_time
        )
        for st, stop in rows
    ]

@router.get("/delays")
def get_active_delays(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch current system delays across all monitored trains."""
    delays = db.query(TrainStatus).filter(TrainStatus.delay_minutes > 0).all()
    return [
        {
            "train_number": t.train_number,
            "trip_id": t.trip_id,
            "route_id": t.route_id,
            "current_station_id": t.current_station_id,
            "delay_minutes": t.delay_minutes,
            "status": t.status,
            "occupancy_rate": t.occupancy_rate,
            "updated_at": t.updated_at
        }
        for t in delays
    ]

@router.post("/delays")
def report_or_update_delay(
    report: DelayReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Report or update a train delay in real time."""
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    
    train = db.query(TrainStatus).filter(TrainStatus.trip_id == report.trip_id).first()
    status_str = "CRITICAL_DELAY" if report.delay_minutes >= 15 else ("DELAYED" if report.delay_minutes > 0 else "ON_TIME")
    
    if train:
        train.delay_minutes = report.delay_minutes
        train.status = status_str
        if report.current_station_id:
            train.current_station_id = report.current_station_id
        train.updated_at = now_iso
    else:
        trip = db.query(Trip).filter(Trip.trip_id == report.trip_id).first()
        route_id = trip.route_id if trip else "UNKNOWN"
        train = TrainStatus(
            trip_id=report.trip_id,
            train_number=f"TR-{report.trip_id[:6]}",
            route_id=route_id,
            current_station_id=report.current_station_id,
            status=status_str,
            delay_minutes=report.delay_minutes,
            occupancy_rate=65.0,
            updated_at=now_iso
        )
        db.add(train)
    db.commit()
    db.refresh(train)
    return {
        "message": "Delay record updated successfully",
        "trip_id": train.trip_id,
        "train_number": train.train_number,
        "delay_minutes": train.delay_minutes,
        "status": train.status
    }

