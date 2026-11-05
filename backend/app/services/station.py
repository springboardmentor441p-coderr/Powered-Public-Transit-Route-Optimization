"""Station and Line service."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.station import Station, Line
from app.schemas.station import StationCreate, StationUpdate, LineCreate, LineUpdate


class StationService:
    """Station and line management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Line methods
    async def create_line(self, line_data: LineCreate) -> Line:
        """Create a new line."""
        line = Line(**line_data.model_dump())
        self.db.add(line)
        await self.db.commit()
        await self.db.refresh(line)
        return line

    async def get_line(self, line_id: UUID) -> Optional[Line]:
        """Get line by ID."""
        result = await self.db.execute(
            select(Line).where(Line.id == line_id).options(selectinload(Line.stations))
        )
        return result.scalar_one_or_none()

    async def get_line_by_code(self, code: str) -> Optional[Line]:
        """Get line by code."""
        result = await self.db.execute(select(Line).where(Line.code == code))
        return result.scalar_one_or_none()

    async def list_lines(self, active_only: bool = True, skip: int = 0, limit: int = 100) -> List[Line]:
        """List lines."""
        query = select(Line).options(selectinload(Line.stations))
        if active_only:
            query = query.where(Line.is_active == True)
        query = query.offset(skip).limit(limit).order_by(Line.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_line(self, line_id: UUID, line_data: LineUpdate) -> Optional[Line]:
        """Update line."""
        line = await self.get_line(line_id)
        if not line:
            return None
        for field, value in line_data.model_dump(exclude_unset=True).items():
            setattr(line, field, value)
        line.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(line)
        return line

    async def delete_line(self, line_id: UUID) -> bool:
        """Delete line."""
        line = await self.get_line(line_id)
        if not line:
            return False
        await self.db.delete(line)
        await self.db.commit()
        return True

    # Station methods
    async def create_station(self, station_data: StationCreate) -> Station:
        """Create a new station."""
        station = Station(**station_data.model_dump())
        self.db.add(station)
        await self.db.commit()
        await self.db.refresh(station)
        return station

    async def get_station(self, station_id: UUID) -> Optional[Station]:
        """Get station by ID."""
        result = await self.db.execute(
            select(Station).where(Station.id == station_id).options(selectinload(Station.line))
        )
        return result.scalar_one_or_none()

    async def get_station_by_code(self, code: str) -> Optional[Station]:
        """Get station by code."""
        result = await self.db.execute(select(Station).where(Station.code == code))
        return result.scalar_one_or_none()

    async def list_stations(
        self,
        line_id: Optional[UUID] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Station]:
        """List stations with optional filtering."""
        query = select(Station).options(selectinload(Station.line))
        if active_only:
            query = query.where(Station.is_active == True)
        if line_id:
            query = query.where(Station.line_id == line_id)
        query = query.offset(skip).limit(limit).order_by(Station.line_id, Station.order)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_stations_by_line(self, line_id: UUID) -> List[Station]:
        """Get all stations for a line in order."""
        result = await self.db.execute(
            select(Station)
            .where(Station.line_id == line_id, Station.is_active == True)
            .order_by(Station.order)
        )
        return list(result.scalars().all())

    async def update_station(self, station_id: UUID, station_data: StationUpdate) -> Optional[Station]:
        """Update station."""
        station = await self.get_station(station_id)
        if not station:
            return None
        for field, value in station_data.model_dump(exclude_unset=True).items():
            setattr(station, field, value)
        station.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(station)
        return station

    async def delete_station(self, station_id: UUID) -> bool:
        """Delete station."""
        station = await self.get_station(station_id)
        if not station:
            return False
        await self.db.delete(station)
        await self.db.commit()
        return True

    async def get_station_count(self, line_id: Optional[UUID] = None) -> int:
        """Get total station count."""
        query = select(func.count(Station.id)).where(Station.is_active == True)
        if line_id:
            query = query.where(Station.line_id == line_id)
        result = await self.db.execute(query)
        return result.scalar() or 0