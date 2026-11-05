"""Ridership and train occupancy models."""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DataSource(str, PyEnum):
    """Data source enumeration."""
    SMART_CARD = "smart_card"
    TICKETING = "ticketing"
    SENSOR = "sensor"
    MANUAL = "manual"
    ESTIMATED = "estimated"


class RidershipRecord(Base):
    """Station ridership record model."""

    __tablename__ = "ridership_records"

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
    entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    source: Mapped[DataSource] = mapped_column(
        Enum(DataSource),
        default=DataSource.ESTIMATED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    station: Mapped["Station"] = relationship(back_populates="ridership_records")

    __table_args__ = (
        Index("ix_ridership_station_timestamp", "station_id", "timestamp"),
        Index("ix_ridership_timestamp_source", "timestamp", "source"),
    )

    def __repr__(self) -> str:
        return f"<RidershipRecord(station={self.station_id}, entries={self.entry_count}, exits={self.exit_count})>"


class TrainOccupancy(Base):
    """Train occupancy record model."""

    __tablename__ = "train_occupancy"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    train_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    occupancy_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    train: Mapped["Train"] = relationship(back_populates="occupancy_records")
    station: Mapped["Station"] = relationship()

    __table_args__ = (
        Index("ix_occupancy_train_timestamp", "train_id", "timestamp"),
        Index("ix_occupancy_station_timestamp", "station_id", "timestamp"),
    )

    @property
    def occupancy_rate(self) -> float:
        """Calculate occupancy rate as percentage."""
        if self.capacity == 0:
            return 0.0
        return (self.occupancy_count / self.capacity) * 100

    def __repr__(self) -> str:
        return f"<TrainOccupancy(train={self.train_id}, occupancy={self.occupancy_count}/{self.capacity})>"