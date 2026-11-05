"""Ridership and train occupancy service."""
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ridership import RidershipRecord, TrainOccupancy, DataSource
from app.schemas.ridership import RidershipRecordCreate, TrainOccupancyCreate


class RidershipService:
    """Ridership data management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_ridership_record(self, record_data: RidershipRecordCreate) -> RidershipRecord:
        """Create a ridership record."""
        record = RidershipRecord(**record_data.model_dump())
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def bulk_create_ridership(self, records: List[RidershipRecordCreate]) -> int:
        """Bulk create ridership records."""
        db_records = [RidershipRecord(**r.model_dump()) for r in records]
        self.db.add_all(db_records)
        await self.db.commit()
        return len(db_records)

    async def get_station_ridership(
        self,
        station_id: UUID,
        start_time: datetime,
        end_time: datetime,
        source: Optional[DataSource] = None,
    ) -> List[RidershipRecord]:
        """Get ridership records for a station in time range."""
        query = select(RidershipRecord).where(
            RidershipRecord.station_id == station_id,
            RidershipRecord.timestamp >= start_time,
            RidershipRecord.timestamp <= end_time,
        )
        if source:
            query = query.where(RidershipRecord.source == source)
        query = query.order_by(RidershipRecord.timestamp)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_ridership(self, station_id: UUID) -> Optional[RidershipRecord]:
        """Get latest ridership record for a station."""
        result = await self.db.execute(
            select(RidershipRecord)
            .where(RidershipRecord.station_id == station_id)
            .order_by(desc(RidershipRecord.timestamp))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_station_ridership_summary(
        self,
        station_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Get ridership summary for a station."""
        result = await self.db.execute(
            select(
                func.sum(RidershipRecord.entry_count).label("total_entries"),
                func.sum(RidershipRecord.exit_count).label("total_exits"),
                func.avg(RidershipRecord.entry_count).label("avg_entries"),
                func.max(RidershipRecord.entry_count).label("peak_entries"),
            ).where(
                RidershipRecord.station_id == station_id,
                RidershipRecord.timestamp >= start_time,
                RidershipRecord.timestamp <= end_time,
            )
        )
        row = result.one()
        return {
            "total_entries": row.total_entries or 0,
            "total_exits": row.total_exits or 0,
            "avg_entries": float(row.avg_entries or 0),
            "peak_entries": row.peak_entries or 0,
        }


class TrainOccupancyService:
    """Train occupancy management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_occupancy_record(self, record_data: TrainOccupancyCreate) -> TrainOccupancy:
        """Create a train occupancy record."""
        record = TrainOccupancy(**record_data.model_dump())
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def bulk_create_occupancy(self, records: List[TrainOccupancyCreate]) -> int:
        """Bulk create occupancy records."""
        db_records = [TrainOccupancy(**r.model_dump()) for r in records]
        self.db.add_all(db_records)
        await self.db.commit()
        return len(db_records)

    async def get_train_occupancy(
        self,
        train_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> List[TrainOccupancy]:
        """Get occupancy records for a train in time range."""
        result = await self.db.execute(
            select(TrainOccupancy)
            .where(
                TrainOccupancy.train_id == train_id,
                TrainOccupancy.timestamp >= start_time,
                TrainOccupancy.timestamp <= end_time,
            )
            .order_by(TrainOccupancy.timestamp)
        )
        return list(result.scalars().all())

    async def get_station_occupancy(
        self,
        station_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> List[TrainOccupancy]:
        """Get occupancy records for a station in time range."""
        result = await self.db.execute(
            select(TrainOccupancy)
            .where(
                TrainOccupancy.station_id == station_id,
                TrainOccupancy.timestamp >= start_time,
                TrainOccupancy.timestamp <= end_time,
            )
            .order_by(TrainOccupancy.timestamp)
        )
        return list(result.scalars().all())

    async def get_latest_occupancy(self, train_id: UUID) -> Optional[TrainOccupancy]:
        """Get latest occupancy record for a train."""
        result = await self.db.execute(
            select(TrainOccupancy)
            .where(TrainOccupancy.train_id == train_id)
            .order_by(desc(TrainOccupancy.timestamp))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_current_system_occupancy(self) -> dict:
        """Get current system-wide occupancy."""
        now = datetime.utcnow()
        five_min_ago = now - timedelta(minutes=5)

        result = await self.db.execute(
            select(
                func.sum(TrainOccupancy.occupancy_count).label("total_occupancy"),
                func.sum(TrainOccupancy.capacity).label("total_capacity"),
                func.count(TrainOccupancy.id).label("active_trains"),
            ).where(TrainOccupancy.timestamp >= five_min_ago)
        )
        row = result.one()
        total_occupancy = row.total_occupancy or 0
        total_capacity = row.total_capacity or 1

        return {
            "total_occupancy": total_occupancy,
            "total_capacity": total_capacity,
            "occupancy_rate": (total_occupancy / total_capacity) * 100,
            "active_trains": row.active_trains or 0,
        }