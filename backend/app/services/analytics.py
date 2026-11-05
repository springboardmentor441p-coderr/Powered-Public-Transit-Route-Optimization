"""Analytics and reporting service."""
from datetime import datetime, timedelta
from typing: Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ridership import RidershipRecord
from app.models.train import Train, TrainStatus
from app.models.station import Station, Line
from app.models.congestion import CongestionEvent
from app.models.alert import Alert
from app.schemas.analytics import (
    TrafficAnalyticsResponse,
    StationPerformanceResponse,
    StationPerformancePoint,
    OperationalMonitoringResponse,
    OperationalMonitoringPoint,
)


class AnalyticsService:
    """Analytics and reporting service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_traffic_analytics(
        self,
        start_time: datetime,
        end_time: datetime,
        line_id: Optional[UUID] = None,
    ) -> TrafficAnalyticsResponse:
        """Get traffic analytics for a period."""
        # Base query for ridership
        ridership_query = select(
            func.sum(RidershipRecord.entry_count).label("total_entries"),
            func.sum(RidershipRecord.exit_count).label("total_exits"),
        ).where(
            RidershipRecord.timestamp >= start_time,
            RidershipRecord.timestamp <= end_time,
        )

        if line_id:
            ridership_query = ridership_query.join(Station).where(Station.line_id == line_id)

        ridership_result = await self.db.execute(ridership_query)
        ridership_row = ridership_result.one()

        total_ridership = (ridership_row.total_entries or 0) + (ridership_row.total_exits or 0)
        days = (end_time - start_time).days or 1
        avg_daily = total_ridership / days

        # Peak hour analysis
        peak_query = select(
            func.extract("hour", RidershipRecord.timestamp).label("hour"),
            func.sum(RidershipRecord.entry_count + RidershipRecord.exit_count).label("total"),
        ).where(
            RidershipRecord.timestamp >= start_time,
            RidershipRecord.timestamp <= end_time,
        ).group_by("hour").order_by(desc("total")).limit(1)

        if line_id:
            peak_query = peak_query.join(Station).where(Station.line_id == line_id)

        peak_result = await self.db.execute(peak_query)
        peak_row = peak_result.one()
        peak_hour = int(peak_row.hour) if peak_row.hour else 8
        peak_ridership = peak_row.total or 0

        # By line
        by_line = {}
        if not line_id:
            line_query = select(
                Line.code,
                func.sum(RidershipRecord.entry_count + RidershipRecord.exit_count).label("total"),
            ).join(Station, Station.line_id == Line.id)\
            .join(RidershipRecord, RidershipRecord.station_id == Station.id)\
            .where(
                RidershipRecord.timestamp >= start_time,
                RidershipRecord.timestamp <= end_time,
            ).group_by(Line.code)

            line_result = await self.db.execute(line_query)
            for row in line_result:
                by_line[row.code] = row.total or 0

        # By station (top 10)
        station_query = select(
            Station.name,
            func.sum(RidershipRecord.entry_count + RidershipRecord.exit_count).label("total"),
        ).join(RidershipRecord)\
        .where(
            RidershipRecord.timestamp >= start_time,
            RidershipRecord.timestamp <= end_time,
        ).group_by(Station.name).order_by(desc("total")).limit(10)

        if line_id:
            station_query = station_query.where(Station.line_id == line_id)

        station_result = await self.db.execute(station_query)
        by_station = {row.name: row.total or 0 for row in station_result}

        # Trends (daily totals)
        trend_query = select(
            func.date(RidershipRecord.timestamp).label("date"),
            func.sum(RidershipRecord.entry_count + RidershipRecord.exit_count).label("total"),
        ).where(
            RidershipRecord.timestamp >= start_time,
            RidershipRecord.timestamp <= end_time,
        ).group_by("date").order_by("date")

        if line_id:
            trend_query = trend_query.join(Station).where(Station.line_id == line_id)

        trend_result = await self.db.execute(trend_query)
        trends = [
            {"date": str(row.date), "ridership": row.total or 0}
            for row in trend_result
        ]

        return TrafficAnalyticsResponse(
            period_start=start_time,
            period_end=end_time,
            total_ridership=total_ridership,
            avg_daily_ridership=avg_daily,
            peak_hour=peak_hour,
            peak_ridership=peak_ridership,
            by_line=by_line,
            by_station=by_station,
            trends=trends,
        )

    async def get_station_performance(
        self,
        start_time: datetime,
        end_time: datetime,
        line_id: Optional[UUID] = None,
    ) -> StationPerformanceResponse:
        """Get station performance metrics."""
        # Get stations
        station_query = select(Station).options(selectinload(Station.line)).where(Station.is_active == True)
        if line_id:
            station_query = station_query.where(Station.line_id == line_id)
        station_result = await self.db.execute(station_query)
        stations = list(station_result.scalars().all())

        performance_points = []
        for station in stations:
            # Ridership
            ridership_result = await self.db.execute(
                select(
                    func.sum(RidershipRecord.entry_count).label("entries"),
                    func.sum(RidershipRecord.exit_count).label("exits"),
                ).where(
                    RidershipRecord.station_id == station.id,
                    RidershipRecord.timestamp >= start_time,
                    RidershipRecord.timestamp <= end_time,
                )
            )
            ridership = ridership_result.one()

            # Congestion events
            congestion_result = await self.db.execute(
                select(func.count(CongestionEvent.id)).where(
                    CongestionEvent.station_id == station.id,
                    CongestionEvent.timestamp >= start_time,
                    CongestionEvent.timestamp <= end_time,
                )
            )
            congestion_count = congestion_result.scalar() or 0

            # Average occupancy
            from app.models.ridership import TrainOccupancy
            occupancy_result = await self.db.execute(
                select(func.avg(TrainOccupancy.occupancy_count * 100.0 / TrainOccupancy.capacity)).where(
                    TrainOccupancy.station_id == station.id,
                    TrainOccupancy.timestamp >= start_time,
                    TrainOccupancy.timestamp <= end_time,
                )
            )
            avg_occupancy = occupancy_result.scalar() or 0.0

            performance_points.append(StationPerformancePoint(
                station_id=station.id,
                station_name=station.name,
                line_code=station.line.code if station.line else "N/A",
                total_entries=ridership.entries or 0,
                total_exits=ridership.exits or 0,
                avg_occupancy_rate=avg_occupancy,
                congestion_events=congestion_count,
                avg_delay_minutes=0.0,  # Would need delay tracking
                on_time_performance=95.0,  # Placeholder
            ))

        summary = {
            "total_stations": len(performance_points),
            "avg_occupancy": sum(p.avg_occupancy_rate for p in performance_points) / len(performance_points) if performance_points else 0,
            "total_congestion_events": sum(p.congestion_events for p in performance_points),
        }

        return StationPerformanceResponse(
            period_start=start_time,
            period_end=end_time,
            stations=performance_points,
            summary=summary,
        )

    async def get_operational_monitoring(self) -> OperationalMonitoringResponse:
        """Get real-time operational monitoring data."""
        now = datetime.utcnow()
        five_min_ago = now - timedelta(minutes=5)
        hour_ago = now - timedelta(hours=1)

        # Current active trains
        trains_result = await self.db.execute(
            select(func.count(Train.id)).where(Train.status == TrainStatus.ACTIVE)
        )
        active_trains = trains_result.scalar() or 0

        # Current occupancy
        from app.models.ridership import TrainOccupancy
        occupancy_result = await self.db.execute(
            select(
                func.sum(TrainOccupancy.occupancy_count).label("occupancy"),
                func.sum(TrainOccupancy.capacity).label("capacity"),
            ).where(TrainOccupancy.timestamp >= five_min_ago)
        )
        occupancy_row = occupancy_result.one()
        current_occupancy = occupancy_row.occupancy or 0
        total_capacity = occupancy_row.capacity or 1
        occupancy_rate = (current_occupancy / total_capacity) * 100

        # Delays (placeholder)
        delays = 0

        # Active alerts
        alerts_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                Alert.is_dismissed == False,
                Alert.is_read == False,
            )
        )
        alerts_active = alerts_result.scalar() or 0

        # Congestion stations
        congestion_result = await self.db.execute(
            select(func.count(CongestionEvent.id.distinct())).where(
                CongestionEvent.resolved_at.is_(None),
            )
        )
        congestion_stations = congestion_result.scalar() or 0

        current = OperationalMonitoringPoint(
            timestamp=now,
            active_trains=active_trains,
            total_capacity=total_capacity,
            current_occupancy=current_occupancy,
            system_occupancy_rate=occupancy_rate,
            delays=delays,
            alerts_active=alerts_active,
            congestion_stations=congestion_stations,
        )

        # History (last hour, 5-min intervals)
        history = []
        for i in range(12):
            interval_start = now - timedelta(minutes=5 * (12 - i))
            interval_end = interval_start + timedelta(minutes=5)

            hist_occupancy = await self.db.execute(
                select(
                    func.sum(TrainOccupancy.occupancy_count).label("occupancy"),
                    func.sum(TrainOccupancy.capacity).label("capacity"),
                ).where(
                    TrainOccupancy.timestamp >= interval_start,
                    TrainOccupancy.timestamp < interval_end,
                )
            )
            hist_row = hist_occupancy.one()
            hist_occ = hist_row.occupancy or 0
            hist_cap = hist_row.capacity or 1

            history.append(OperationalMonitoringPoint(
                timestamp=interval_start,
                active_trains=active_trains,  # Simplified
                total_capacity=hist_cap,
                current_occupancy=hist_occ,
                system_occupancy_rate=(hist_occ / hist_cap) * 100,
                delays=0,
                alerts_active=alerts_active,
                congestion_stations=congestion_stations,
            ))

        alerts_summary = {
            "critical": 0,
            "warning": 0,
            "info": 0,
        }

        return OperationalMonitoringResponse(
            current=current,
            history=history,
            alerts_summary=alerts_summary,
        )