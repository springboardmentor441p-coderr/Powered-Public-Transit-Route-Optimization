"""Alert Management Module for MetroFlow (Milestone 3).
Provides centralized alert tracking across 7 operational categories,
configurable severity thresholds, and operator lifecycle management.
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from ..db import get_db
from ..models import Alert, Stop, Route, User
from .auth import get_current_user

router = APIRouter()

class AlertCreate(BaseModel):
    title: str
    category: str  # SERVICE_ACTIVITY, CONGESTION_INDICATOR, SCHEDULE_CHANGE, DELAY, INCIDENT, EMERGENCY, SYSTEM_EVENT
    severity: str = "INFO"  # INFO, WARNING, CRITICAL
    message: str
    target_stop_id: Optional[str] = None
    target_route_id: Optional[str] = None

class AlertResponse(BaseModel):
    id: int
    title: str
    category: str
    severity: str
    status: str
    message: str
    target_stop_id: Optional[str] = None
    target_route_id: Optional[str] = None
    created_at: str
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

@router.get("", response_model=List[AlertResponse])
def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, ACKNOWLEDGED, RESOLVED"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity: INFO, WARNING, CRITICAL"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve system operational alerts with category, severity, and status filtering."""
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status.upper())
    if category:
        query = query.filter(Alert.category == category.upper())
    if severity:
        query = query.filter(Alert.severity == severity.upper())
    return query.order_by(Alert.id.desc()).limit(limit).all()

@router.post("", response_model=AlertResponse)
def create_alert(
    alert_in: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new operational or congestion alert."""
    now_iso = datetime.now(timezone.utc).isoformat()
    new_alert = Alert(
        title=alert_in.title,
        category=alert_in.category.upper(),
        severity=alert_in.severity.upper(),
        status="ACTIVE",
        message=alert_in.message,
        target_stop_id=alert_in.target_stop_id,
        target_route_id=alert_in.target_route_id,
        created_at=now_iso
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    return new_alert

@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Acknowledge an active alert by an operator."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_by = current_user.email
    db.commit()
    db.refresh(alert)
    return alert

@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark an operational alert as resolved."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    now_iso = datetime.now(timezone.utc).isoformat()
    alert.status = "RESOLVED"
    alert.resolved_at = now_iso
    db.commit()
    db.refresh(alert)
    return alert

