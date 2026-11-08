'''Dashboard API for public transit platform.
Provides quick summary statistics of the GTFS data.'''

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Route, Stop, Trip, StopTime, StationCrowd, TrainStatus

router = APIRouter()

@router.get('/summary')
def get_summary(db: Session = Depends(get_db)):
    """Return counts of core GTFS entities and operational indicators."""
    try:
        routes = db.query(Route).count()
        stops = db.query(Stop).count()
        trips = db.query(Trip).count()
        stop_times = db.query(StopTime).count()
        monitored_stations = db.query(StationCrowd).count()
        active_trains = db.query(TrainStatus).count()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        'routes': routes,
        'stops': stops,
        'trips': trips,
        'stop_times': stop_times,
        'monitored_stations': monitored_stations,
        'active_trains': active_trains
    }

