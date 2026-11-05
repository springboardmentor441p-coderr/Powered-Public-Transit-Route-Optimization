"""Analytics schemas."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class TrafficAnalyticsResponse(BaseModel):
    """Traffic analytics response."""
    period_start: datetime
    period_end: datetime
    total_ridership: int
    avg_daily_ridership: float
    peak_hour: int
    peak_ridership: int
    by_line: Dict[str, int]
    by_station: Dict[str, int]
    trends: List[Dict[str, Any]]


class StationPerformancePoint(BaseModel):
    """Station performance point."""
    station_id: UUID
    station_name: str
    line_code: str
    total_entries: int
    total_exits: int
    avg_occupancy_rate: float
    congestion_events: int
    avg_delay_minutes: float
    on_time_performance: float


class StationPerformanceResponse(BaseModel):
    """Station performance response."""
    period_start: datetime
    period_end: datetime
    stations: List[StationPerformancePoint]
    summary: Dict[str, Any]


class OperationalMonitoringPoint(BaseModel):
    """Operational monitoring point."""
    timestamp: datetime
    active_trains: int
    total_capacity: int
    current_occupancy: int
    system_occupancy_rate: float
    delays: int
    alerts_active: int
    congestion_stations: int


class OperationalMonitoringResponse(BaseModel):
    """Operational monitoring response."""
    current: OperationalMonitoringPoint
    history: List[OperationalMonitoringPoint]
    alerts_summary: Dict[str, int]