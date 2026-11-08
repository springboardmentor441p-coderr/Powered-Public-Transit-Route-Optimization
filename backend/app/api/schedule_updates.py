"""Operational Schedule Updates Workflow Module (Milestone 3).
Allows operators to publish in-app schedule updates, trip cancellations,
and extra service runs separately from static GTFS records.
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from ..db import get_db
from ..models import ScheduleUpdate, Route, User
from .auth import get_current_user

router = APIRouter()

class ScheduleUpdateCreate(BaseModel):
    route_id: str
    trip_id: Optional[str] = None
    update_type: str = "DELAY"  # DELAY, CANCELLATION, EXTRA_SERVICE, REROUTE
    description: str
    delay_minutes: int = 0

class ScheduleUpdateResponse(BaseModel):
    id: int
    route_id: str
    trip_id: Optional[str] = None
    update_type: str
    description: str
    delay_minutes: int
    status: str
    created_by: str
    timestamp: str

    model_config = ConfigDict(from_attributes=True)

@router.get("", response_model=List[ScheduleUpdateResponse])
def get_schedule_updates(
    route_id: Optional[str] = Query(None, description="Filter by route ID"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve operational schedule updates published by operators."""
    query = db.query(ScheduleUpdate)
    if route_id:
        query = query.filter(ScheduleUpdate.route_id == route_id)
    return query.order_by(ScheduleUpdate.id.desc()).limit(limit).all()

@router.post("", response_model=ScheduleUpdateResponse)
def create_schedule_update(
    update_in: ScheduleUpdateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Publish a live operational schedule update."""
    route = db.query(Route).filter(Route.route_id == update_in.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Route '{update_in.route_id}' not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    new_update = ScheduleUpdate(
        route_id=update_in.route_id,
        trip_id=update_in.trip_id,
        update_type=update_in.update_type.upper(),
        description=update_in.description,
        delay_minutes=update_in.delay_minutes,
        status="PUBLISHED",
        created_by=current_user.email,
        timestamp=now_iso
    )
    db.add(new_update)
    db.commit()
    db.refresh(new_update)
    return new_update

