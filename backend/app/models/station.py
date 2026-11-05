"""Station and Line models."""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Line(Base):
    """Metro line model."""

    __tablename__ = "lines"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False)  # Hex color code
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
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
    stations: Mapped[list["Station"]] = relationship(
        back_populates="line",
        cascade="all, delete-orphan",
        order_by="Station.order",
    )

    def __repr__(self) -> str:
        return f"<Line(id={self.id}, name={self.name}, code={self.code})>"


class Station(Base):
    """Metro station model."""

    __tablename__ = "stations"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    line_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)  # Order on the line
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)  # Max passenger capacity
    zone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Fare zone
    is_interchange: Mapped[bool] = mapped_column(default=False, nullable=False)
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
    line: Mapped["Line"] = relationship(back_populates="stations")
    ridership_records: Mapped[list["RidershipRecord"]] = relationship(
        back_populates="station",
        cascade="all, delete-orphan",
    )
    congestion_events: Mapped[list["CongestionEvent"]] = relationship(
        back_populates="station",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("line_id", "order", name="uq_line_order"),
        Index("ix_stations_location", "latitude", "longitude"),
    )

    def __repr__(self) -> str:
        return f"<Station(id={self.id}, name={self.name}, code={self.code})>"