"""In-App Notification & Real-Time Push Feed Module (Milestone 3).
Provides user notification workflows, read/unread state management,
and WebSocket broadcast channels.
"""

from typing import List, Optional, Set
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from ..db import get_db
from ..models import Notification, User
from .auth import get_current_user

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

ws_manager = ConnectionManager()

class NotificationCreate(BaseModel):
    title: str
    message: str
    category: str = "OPERATIONAL"
    severity: str = "INFO"  # INFO, WARNING, CRITICAL
    user_id: Optional[int] = None  # None = broadcast

class NotificationResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    message: str
    category: str
    severity: str
    is_read: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)

@router.get("", response_model=List[NotificationResponse])
def get_notifications(
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve notifications for the current user and broadcasts."""
    query = db.query(Notification).filter(
        (Notification.user_id == current_user.id) | (Notification.user_id == None)
    )
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)
    return query.order_by(Notification.id.desc()).limit(limit).all()

@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get count of unread notifications for the current user."""
    count = db.query(Notification).filter(
        ((Notification.user_id == current_user.id) | (Notification.user_id == None)),
        Notification.is_read == False
    ).count()
    return {"unread_count": count}

@router.post("", response_model=NotificationResponse)
async def create_notification(
    notif_in: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Publish a new notification and broadcast to active WebSocket listeners."""
    now_iso = datetime.now(timezone.utc).isoformat()
    new_notif = Notification(
        user_id=notif_in.user_id,
        title=notif_in.title,
        message=notif_in.message,
        category=notif_in.category.upper(),
        severity=notif_in.severity.upper(),
        is_read=False,
        created_at=now_iso
    )
    db.add(new_notif)
    db.commit()
    db.refresh(new_notif)

    # Broadcast via WebSocket
    await ws_manager.broadcast({
        "type": "NOTIFICATION",
        "id": new_notif.id,
        "title": new_notif.title,
        "message": new_notif.message,
        "severity": new_notif.severity,
        "timestamp": now_iso
    })

    return new_notif

@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a notification as read."""
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif

@router.websocket("/ws")
async def websocket_notifications_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time in-app operational notification push."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection open and receive optional client pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

