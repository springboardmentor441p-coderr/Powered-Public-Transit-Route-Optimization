"""Emergency Announcement Module for MetroFlow (Milestone 3).
Allows authorized transit administrators to broadcast urgent operational,
safety, and network emergency announcements.
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from ..db import get_db
from ..models import EmergencyAnnouncement, User
from .auth import get_current_user, get_current_active_admin

router = APIRouter()

class AnnouncementCreate(BaseModel):
    title: str
    message: str
    severity: str = "CRITICAL"  # MODERATE, SEVERE, CRITICAL
    affected_routes: Optional[str] = None
    affected_stops: Optional[str] = None

class AnnouncementResponse(BaseModel):
    id: int
    title: str
    message: str
    severity: str
    affected_routes: Optional[str] = None
    affected_stops: Optional[str] = None
    is_active: bool
    published_by: str
    published_at: str
    deactivated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

@router.get("/active", response_model=List[AnnouncementResponse])
def get_active_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve all currently active emergency announcements."""
    return db.query(EmergencyAnnouncement).filter(EmergencyAnnouncement.is_active == True).all()

@router.post("", response_model=AnnouncementResponse)
def create_emergency_announcement(
    ann_in: AnnouncementCreate,
    admin_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Publish a new emergency announcement (Admin only)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    new_ann = EmergencyAnnouncement(
        title=ann_in.title,
        message=ann_in.message,
        severity=ann_in.severity.upper(),
        affected_routes=ann_in.affected_routes,
        affected_stops=ann_in.affected_stops,
        is_active=True,
        published_by=admin_user.email,
        published_at=now_iso
    )
    db.add(new_ann)
    db.commit()
    db.refresh(new_ann)
    return new_ann

@router.post("/{announcement_id}/deactivate", response_model=AnnouncementResponse)
def deactivate_emergency_announcement(
    announcement_id: int,
    admin_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Deactivate/resolve an active emergency announcement (Admin only)."""
    ann = db.query(EmergencyAnnouncement).filter(EmergencyAnnouncement.id == announcement_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    now_iso = datetime.now(timezone.utc).isoformat()
    ann.is_active = False
    ann.deactivated_at = now_iso
    db.commit()
    db.refresh(ann)
    return ann

