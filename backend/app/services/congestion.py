"""Congestion monitoring service."""
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.congestion import CongestionEvent, CongestionSeverity
from app.models.station import Station
from app.models.train import Train
from app.schemas.congestion import CongestionHeatmapPoint, StationCongestionStatus


class CongestionService:
    """Congestion monitoring and analysis service."""

    SEVERITY_THRESHOLDS = {
        CongestionSeverity.LOW: (0, 50),
        CongestionSeverity.MEDIUM: (50, 75),
        CongestionSeverity.HIGH: (75, 90),
        CongestionSeverity.CRITICAL: (90, 100),
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    def _calculate_severity(self, occupancy_rate: float) -> CongestionSeverity:
        """Calculate severity based on occupancy rate."""
        for severity, (low, high) in self.SEVERITY_THRESHOLDS.items():
            if low <= occupancy_rate < high:
                return severity
        return CongestionSeverity.CRITICAL

    async def create_congestion_event(
        self,
        station_id: UUID,
        passenger_count: int,
        capacity: int,
        predicted: bool = False,
    ) -> CongestionEvent:
        """Create a congestion event."""
        occupancy_rate = (passenger_count / capacity) * 100 if capacity > 0 else 0
        severity = self._calculate_severity(occupancy_rate)

        event = CongestionEvent(
            station_id=station_id,
            severity=severity,
            predicted=predicted,
            passenger_count=passenger_count,
            capacity=capacity,
            timestamp=datetime.utcnow(),
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_station_congestion(
        self,
        station_id: UUID,
        hours: int = 24,
    ) -> List[CongestionEvent]:
        """Get congestion events for a station."""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        result = await self.db.execute(
            select(CongestionEvent)
            .where(
                CongestionEvent.station_id == station_id,
                CongestionEvent.timestamp >= start_time,
            )
            .order_by(desc(CongestionEvent.timestamp))
        )
        return list(result.scalars().all())

    async def get_current_congestion(self, station_id: UUID) -> Optional[CongestionEvent]:
        """Get current congestion for a station."""
        result = await self.db.execute(
            select(CongestionEvent)
            .where(
                CongestionEvent.station_id == station_id,
                CongestionEvent.resolved_at.is_(None),
            )
            .order_by(desc(CongestionEvent.timestamp))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def resolve_congestion(self, event_id: UUID) -> bool:
        """Resolve a congestion event."""
        result = await self.db.execute(
            select(CongestionEvent).where(CongestionEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event or event.resolved_at:
            return False
        event.resolved_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def get_all_current_congestion(self) -> List[CongestionEvent]:
        """Get all current unresolved congestion events."""
        result = await self.db.execute(
            select(CongestionEvent)
            .where(CongestionEvent.resolved_at.is_(None))
            .options(selectinload(CongestionEvent.station))
            .order_by(desc(CongestionEvent.timestamp))
        )
        return list(result.scalars().all())

    async def get_congestion_heatmap(self) -> List[CongestionHeatmapPoint]:
        """Get congestion data for heatmap visualization."""
        events = await self.get_all_current_congestion()
        heatmap = []
        for event in events:
            if event.station:
                heatmap.append(CongestionHeatmapPoint(
                    station_id=event.station_id,
                    station_name=event.station.name,
                    latitude=event.station.latitude,
                    longitude=event.station.longitude,
                    severity=event.severity.value,
                    occupancy_rate=event.occupancy_rate,
                    passenger_count=event.passenger_count,
                    capacity=event.capacity,
                    timestamp=event.timestamp,
                    predicted=event.predicted,
                ))
        return heatmap

    async def get_station_statuses(self) -> List[StationCongestionStatus]:
        """Get congestion status for all active stations."""
        result = await self.db.execute(
            select(Station)
            .where(Station.is_active == True)
            .options(selectinload(Station.line))
        )
        stations = list(result.scalars().all())

        statuses = []
        for station in stations:
            # Get latest occupancy
            from app.services.ridership import TrainOccupancyService
            occupancy_service = TrainOccupancyService(self.db)
            latest = await occupancy_service.get_latest_occupancy_by_station(station.id)

            current_occupancy = latest.occupancy_count if latest else 0
            occupancy_rate = (current_occupancy / station.capacity * 100) if station.capacity > 0 else 0
            severity = self._calculate_severity(occupancy_rate).value

            # Determine trend (simplified)
            trend = "stable"

            # Get predicted severity
            predicted_event = await self.db.execute(
                select(CongestionEvent)
                .where(
                    CongestionEvent.station_id == station.id,
                    CongestionEvent.predicted == True,
                    CongestionEvent.timestamp > datetime.utcnow(),
                )
                .order_by(CongestionEvent.timestamp)
                .limit(1)
            )
            predicted = predicted_event.scalar_one_or_none()

            statuses.append(StationCongestionStatus(
                station_id=station.id,
                station_name=station.name,
                line_code=station.line.code if station.line else "N/A",
                current_occupancy=current_occupancy,
                capacity=station.capacity,
                occupancy_rate=occupancy_rate,
                severity=severity,
                trend=trend,
                last_updated=latest.timestamp if latest else datetime.utcnow(),
                predicted_severity=predicted.severity.value if predicted else None,
            ))

        return statuses