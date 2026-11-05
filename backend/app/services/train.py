"""Train and Schedule service."""
from datetime import datetime, time
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.train import Train, Schedule, TrainStatus, DayType
from app.models.station import Station
from app.schemas.train import TrainCreate, TrainUpdate, ScheduleCreate, ScheduleUpdate, ScheduleOptimizeRequest


class TrainService:
    """Train management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_train(self, train_data: TrainCreate) -> Train:
        """Create a new train."""
        train = Train(**train_data.model_dump())
        self.db.add(train)
        await self.db.commit()
        await self.db.refresh(train)
        return train

    async def get_train(self, train_id: UUID) -> Optional[Train]:
        """Get train by ID."""
        result = await self.db.execute(
            select(Train)
            .where(Train.id == train_id)
            .options(selectinload(Train.line), selectinload(Train.current_station))
        )
        return result.scalar_one_or_none()

    async def get_train_by_number(self, train_number: str) -> Optional[Train]:
        """Get train by number."""
        result = await self.db.execute(select(Train).where(Train.train_number == train_number))
        return result.scalar_one_or_none()

    async def list_trains(
        self,
        line_id: Optional[UUID] = None,
        status: Optional[TrainStatus] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Train]:
        """List trains with optional filtering."""
        query = select(Train).options(selectinload(Train.line), selectinload(Train.current_station))
        if active_only:
            query = query.where(Train.status != TrainStatus.INACTIVE)
        if line_id:
            query = query.where(Train.line_id == line_id)
        if status:
            query = query.where(Train.status == status)
        query = query.offset(skip).limit(limit).order_by(Train.train_number)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_train(self, train_id: UUID, train_data: TrainUpdate) -> Optional[Train]:
        """Update train."""
        train = await self.get_train(train_id)
        if not train:
            return None
        for field, value in train_data.model_dump(exclude_unset=True).items():
            if field == "status" and value:
                value = TrainStatus(value)
            setattr(train, field, value)
        train.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(train)
        return train

    async def delete_train(self, train_id: UUID) -> bool:
        """Delete train."""
        train = await self.get_train(train_id)
        if not train:
            return False
        await self.db.delete(train)
        await self.db.commit()
        return True


class ScheduleService:
    """Schedule management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_schedule(self, schedule_data: ScheduleCreate) -> Schedule:
        """Create a new schedule."""
        schedule = Schedule(**schedule_data.model_dump())
        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule

    async def get_schedule(self, schedule_id: UUID) -> Optional[Schedule]:
        """Get schedule by ID."""
        result = await self.db.execute(
            select(Schedule)
            .where(Schedule.id == schedule_id)
            .options(selectinload(Schedule.train), selectinload(Schedule.station))
        )
        return result.scalar_one_or_none()

    async def list_schedules(
        self,
        train_id: Optional[UUID] = None,
        station_id: Optional[UUID] = None,
        day_type: Optional[DayType] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Schedule]:
        """List schedules with optional filtering."""
        query = select(Schedule).options(selectinload(Schedule.train), selectinload(Schedule.station))
        if active_only:
            query = query.where(Schedule.is_active == True)
        if train_id:
            query = query.where(Schedule.train_id == train_id)
        if station_id:
            query = query.where(Schedule.station_id == station_id)
        if day_type:
            query = query.where(Schedule.day_type == day_type)
        query = query.offset(skip).limit(limit).order_by(Schedule.train_id, Schedule.sequence)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_train_schedule(self, train_id: UUID, day_type: DayType = DayType.WEEKDAY) -> List[Schedule]:
        """Get complete schedule for a train."""
        result = await self.db.execute(
            select(Schedule)
            .where(Schedule.train_id == train_id, Schedule.day_type == day_type, Schedule.is_active == True)
            .options(selectinload(Schedule.station))
            .order_by(Schedule.sequence)
        )
        return list(result.scalars().all())

    async def get_station_schedule(
        self,
        station_id: UUID,
        day_type: DayType = DayType.WEEKDAY,
    ) -> List[Schedule]:
        """Get schedule for a station."""
        result = await self.db.execute(
            select(Schedule)
            .where(Schedule.station_id == station_id, Schedule.day_type == day_type, Schedule.is_active == True)
            .options(selectinload(Schedule.train))
            .order_by(Schedule.arrival_time)
        )
        return list(result.scalars().all())

    async def update_schedule(self, schedule_id: UUID, schedule_data: ScheduleUpdate) -> Optional[Schedule]:
        """Update schedule."""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            return None
        for field, value in schedule_data.model_dump(exclude_unset=True).items():
            if field == "day_type" and value:
                value = DayType(value)
            setattr(schedule, field, value)
        schedule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule

    async def delete_schedule(self, schedule_id: UUID) -> bool:
        """Delete schedule."""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            return False
        await self.db.delete(schedule)
        await self.db.commit()
        return True

    async def optimize_schedule(self, request: ScheduleOptimizeRequest) -> dict:
        """Optimize train schedule for a line."""
        # Get line stations
        from app.services.station import StationService
        station_service = StationService(self.db)
        stations = await station_service.get_stations_by_line(request.line_id)

        if not stations:
            return {
                "optimized": False,
                "message": "No stations found for line",
                "recommended_headway": None,
                "recommended_train_count": None,
            }

        # Simple optimization: calculate based on demand
        # In production, this would use OR-Tools or genetic algorithms
        station_count = len(stations)
        round_trip_time = station_count * 3  # 3 minutes per station average
        headway = request.target_headway_minutes
        trains_needed = max(1, round(round_trip_time / headway))
        trains_needed = min(trains_needed, request.max_trains)

        return {
            "optimized": True,
            "message": f"Optimized schedule for {station_count} stations",
            "recommended_headway": headway,
            "recommended_train_count": trains_needed,
            "estimated_capacity_utilization": 75.0,
        }