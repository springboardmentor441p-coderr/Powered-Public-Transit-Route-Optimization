"""Train and Schedule models."""
from datetime import datetime, time
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TrainStatus(str, PyEnum):
    """Train status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    DELAYED = "delayed"


class DayType(str, PyEnum):
    """Day type for scheduling."""
    WEEKDAY = "weekday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"
    HOLIDAY = "holiday"


class Train(Base):
    """Train model."""

    __tablename__ = "trains"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    train_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    line_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capacity: Mapped[int] = mapped_column(Integer, default=500, nullable=False)  # Max passenger capacity
    status: Mapped[TrainStatus] = mapped_column(
        Enum(TrainStatus),
        default=TrainStatus.ACTIVE,
        nullable=False,
    )
    current_station_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    line: Mapped["Line"] = relationship()
    current_station: Mapped[Optional["Station"]] = relationship()
    schedules: Mapped[list["Schedule"]] = relationship(
        back_populates="train",
        cascade="all, delete-orphan",
    )
    occupancy_records: Mapped[list["TrainOccupancy"]] = relationship(
        back_populates="train",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Train(id={self.id}, number={self.train_number}, status={self.status})>"


class Schedule(Base):
    """Train schedule model."""

    __tablename__ = "schedules"

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
    arrival_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    departure_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    day_type: Mapped[DayType] = mapped_column(
        Enum(DayType),
        default=DayType.WEEKDAY,
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # Order in train's route
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    train: Mapped["Train"] = relationship(back_populates="schedules")
    station: Mapped["Station"] = relationship()

    __table_args__ = (
        UniqueConstraint("train_id", "station_id", "day_type", name="uq_train_station_day"),
        Index("ix_schedules_train_sequence", "train_id", "sequence"),
    )

    def __repr__(self) -> str:
        return f"<Schedule(train={self.train_id}, station={self.station_id}, seq={self.sequence})>"