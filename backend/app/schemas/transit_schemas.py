"""
RouteRanker: Real-Time Transit Data Schemas
Pydantic schemas modeling CTA Bus Tracker, Train Tracker, and Alerts feeds.
Strictly distinguishes live API positions from schedule-derived simulations.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class APIResponseMetadata(BaseModel):
    data_source: str = Field(..., description="'LIVE_CTA_API' or 'GTFS_SCHEDULE_DERIVED'")
    is_live_api_active: bool = Field(..., description="True if official CTA API key was used successfully")
    last_updated: str = Field(..., description="ISO 8601 timestamp of data generation")
    cached: bool = Field(False, description="True if served from local memory cache")
    message: Optional[str] = None

class BusVehiclePosition(BaseModel):
    vehicle_id: str = Field(..., description="CTA vehicle ID")
    route_id: str = Field(..., description="Bus route number (e.g., 79, 9, 66)")
    destination: str = Field(..., description="Destination display heading")
    latitude: float = Field(..., description="Vehicle latitude")
    longitude: float = Field(..., description="Vehicle longitude")
    heading: int = Field(..., description="Heading in degrees (0-359)")
    speed_mph: float = Field(..., description="Current speed in miles per hour")
    is_delayed: bool = Field(False, description="True if CTA flags vehicle as delayed")
    pattern_id: Optional[str] = None
    timestamp: str = Field(..., description="Timestamp of vehicle location fix")

class BusArrivalPrediction(BaseModel):
    prediction_type: str = Field(..., description="'A' for arrival, 'D' for departure")
    stop_id: str = Field(..., description="CTA bus stop ID")
    stop_name: str = Field(..., description="Bus stop descriptive name")
    vehicle_id: str = Field(..., description="Assigned vehicle ID")
    route_id: str = Field(..., description="Bus route number")
    destination: str = Field(..., description="Trip terminal destination")
    predicted_arrival_time: str = Field(..., description="Estimated arrival timestamp")
    countdown_minutes: int = Field(..., description="Estimated minutes until arrival")
    is_delayed: bool = Field(False, description="Delay status flag")

class TrainPosition(BaseModel):
    run_number: str = Field(..., description="CTA train run number (e.g., 102)")
    line_name: str = Field(..., description="Line code: Red, Blue, Brn, G, Org, P, Pnk, Y")
    destination_name: str = Field(..., description="Destination station name")
    latitude: float = Field(..., description="Train latitude")
    longitude: float = Field(..., description="Train longitude")
    heading: int = Field(..., description="Heading in degrees (0-359)")
    next_station_id: Optional[str] = None
    next_station_name: Optional[str] = None
    is_approaching: bool = Field(False, description="True if train is approaching station")
    is_delayed: bool = Field(False, description="True if train is delayed")
    timestamp: str = Field(..., description="Timestamp of position record")

class TrainArrivalPrediction(BaseModel):
    station_id: str = Field(..., description="CTA rail station ID (MAP_ID)")
    stop_id: str = Field(..., description="Specific platform stop ID")
    station_name: str = Field(..., description="Station descriptive name")
    platform_description: str = Field(..., description="Platform direction (e.g., O'Hare-bound)")
    run_number: str = Field(..., description="Train run number")
    line_name: str = Field(..., description="Rail line name")
    destination_name: str = Field(..., description="Destination terminal name")
    arrival_time: str = Field(..., description="Predicted arrival timestamp")
    countdown_minutes: int = Field(..., description="Estimated minutes until arrival")
    is_approaching: bool = Field(False, description="Approaching indicator")
    is_delayed: bool = Field(False, description="Delay indicator")

class TransitAlert(BaseModel):
    alert_id: str = Field(..., description="Unique CTA alert ID")
    headline: str = Field(..., description="Alert headline summary")
    short_description: str = Field(..., description="Brief summary of service impact")
    full_description: str = Field(..., description="Detailed instructions or explanation")
    severity: str = Field(..., description="Severity classification")
    impact_level: str = Field(..., description="Impact category (e.g., Planned Reroute, Delay)")
    service_impacted: str = Field(..., description="Lines or bus routes affected")
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class TransitStatusResponse(BaseModel):
    bus_api_configured: bool
    train_api_configured: bool
    alerts_api_active: bool
    bus_vehicle_count: int
    train_count: int
    active_alerts_count: int
    last_system_refresh: str
    cache_ttl_seconds: int
    data_source_mode: str
    disclaimer: str = (
        "Live vehicle positions show spatial vehicle locations only. "
        "Vehicle coordinates do NOT represent live passenger occupancy or crowd density."
    )

