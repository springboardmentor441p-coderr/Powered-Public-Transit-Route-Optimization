"""Congestion event model."""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CongestionSeverity(str, PyEnum):
    """Congestion severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CongestionEvent(Base):
    """Congestion event model for tracking station congestion."""

    __tablename__ = "congestion_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    station_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    severity: Mapped[CongestionSeverity] = mapped_column(
        Enum(CongestionSeverity),
        nullable=False,
    )
    predicted: Mapped[bool] = mapped_column(default=False, nullable=False)
    passenger_count: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    station: Mapped["Station"] = relationship(back_populates="congestion_events")

    __table_args__ = (
        Index("ix_congestion_station_timestamp", "station_id", "timestamp"),
        Index("ix_congestion_severity_timestamp", "severity", "timestamp"),
    )

    @property
    def occupancy_rate(self) -> float:
        """Calculate occupancy rate as percentage."""
        if self.capacity == 0:
            return 0.0
        return (self.passenger_count / self.capacity) * 100

    def __repr__(self) -> str:
        return f"<CongestionEvent(station={self.station_id}, severity={self.severity}, predicted={self.predicted})>"