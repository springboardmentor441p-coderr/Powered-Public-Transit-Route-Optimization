"""Alert API routes."""
from datetime import datetime
from typing: Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.alert import AlertService
from app.models.alert import AlertType, AlertSeverity
from app.schemas.alert import AlertCreate, AlertUpdate, AlertResponse, AlertSummary

router = APIRouter()


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_data: AlertCreate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert."""
    service = AlertService(db)
    alert = await service.create_alert(alert_data, current_user.id)
    return AlertResponse.model_validate(alert)


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    type: Optional[str] = None,
    severity: Optional[str] = None,
    station_id: Optional[UUID] = None,
    train_id: Optional[UUID] = None,
    unread_only: bool = False,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List alerts with filtering."""
    service = AlertService(db)

    alert_type = None
    if type:
        try:
            alert_type = AlertType(type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid alert type")

    alert_severity = None
    if severity:
        try:
            alert_severity = AlertSeverity(severity)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid severity")

    alerts = await service.list_alerts(
        alert_type, alert_severity, station_id, train_id,
        unread_only, active_only, skip, limit
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/summary", response_model=AlertSummary)
async def get_alert_summary(
    db: AsyncSession = Depends(get_db),
):
    """Get alert summary for dashboard."""
    service = AlertService(db)
    return await service.get_alert_summary()


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get alert by ID."""
    service = AlertService(db)
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: UUID,
    alert_data: AlertUpdate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Update alert (mark read/dismissed)."""
    service = AlertService(db)
    alert = await service.update_alert(alert_id, alert_data)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/read", response_model=AlertResponse)
async def mark_alert_read(
    alert_id: UUID,
    current_user=Depends(require_role("admin", "operator", "viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Mark alert as read."""
    service = AlertService(db)
    alert = await service.update_alert(alert_id, AlertUpdate(is_read=True))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/dismiss", response_model=AlertResponse)
async def dismiss_alert(
    alert_id: UUID,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss alert."""
    service = AlertService(db)
    alert = await service.update_alert(alert_id, AlertUpdate(is_dismissed=True, dismissed_by=current_user.id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


@router.post("/read-all")
async def mark_all_read(
    current_user=Depends(require_role("admin", "operator", "viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Mark all alerts as read for current user."""
    service = AlertService(db)
    count = await service.mark_all_read(current_user.id)
    return {"marked_read": count}


@router.post("/cleanup")
async def cleanup_expired_alerts(
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Clean up expired alerts."""
    service = AlertService(db)
    count = await service.cleanup_expired_alerts()
    return {"cleaned_up": count}