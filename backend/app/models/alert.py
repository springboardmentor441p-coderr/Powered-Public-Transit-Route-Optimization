"""Alert model."""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AlertType(str, PyEnum):
    """Alert type enumeration."""
    OVERCROWDING = "overcrowding"
    DELAY = "delay"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"
    SCHEDULE_CHANGE = "schedule_change"
    SYSTEM = "system"


class AlertSeverity(str, PyEnum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alert(Base):
    """Alert model for notifications and announcements."""

    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    type: Mapped[AlertType] = mapped_column(
        Enum(AlertType),
        nullable=False,
        index=True,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    station_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    train_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trains.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_dismissed: Mapped[bool] = mapped_column(default=False, nullable=False)
    dismissed_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    station: Mapped[Optional["Station"]] = relationship()
    train: Mapped[Optional["Train"]] = relationship()

    __table_args__ = (
        Index("ix_alerts_type_severity", "type", "severity"),
        Index("ix_alerts_station_created", "station_id", "created_at"),
        Index("ix_alerts_active", "is_read", "is_dismissed", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, type={self.type}, severity={self.severity})>"