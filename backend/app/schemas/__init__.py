"""Pydantic schemas package."""
from app.schemas.auth import (  # noqa: F401
    Token,
    TokenPayload,
    LoginRequest,
    RegisterRequest,
    UserResponse,
    RefreshTokenRequest,
)
from app.schemas.station import (  # noqa: F401
    StationBase,
    StationCreate,
    StationUpdate,
    StationResponse,
    LineBase,
    LineCreate,
    LineUpdate,
    LineResponse,
)
from app.schemas.train import (  # noqa: F401
    TrainBase,
    TrainCreate,
    TrainUpdate,
    TrainResponse,
    ScheduleBase,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
)
from app.schemas.ridership import (  # noqa: F401
    RidershipRecordCreate,
    RidershipRecordResponse,
    TrainOccupancyCreate,
    TrainOccupancyResponse,
)
from app.schemas.congestion import (  # noqa: F401
    CongestionEventResponse,
    CongestionHeatmapPoint,
)
from app.schemas.alert import (  # noqa: F401
    AlertBase,
    AlertCreate,
    AlertUpdate,
    AlertResponse,
)
from app.schemas.prediction import (  # noqa: F401
    CrowdPredictionRequest,
    CrowdPredictionResponse,
    DemandForecastResponse,
    TrafficPatternResponse,
)
from app.schemas.analytics import (  # noqa: F401
    TrafficAnalyticsResponse,
    StationPerformanceResponse,
    OperationalMonitoringResponse,
)

__all__ = [
    # Auth
    "Token",
    "TokenPayload",
    "LoginRequest",
    "RegisterRequest",
    "UserResponse",
    "RefreshTokenRequest",
    # Station
    "StationBase",
    "StationCreate",
    "StationUpdate",
    "StationResponse",
    "LineBase",
    "LineCreate",
    "LineUpdate",
    "LineResponse",
    # Train
    "TrainBase",
    "TrainCreate",
    "TrainUpdate",
    "TrainResponse",
    "ScheduleBase",
    "ScheduleCreate",
    "ScheduleUpdate",
    "ScheduleResponse",
    # Ridership
    "RidershipRecordCreate",
    "RidershipRecordResponse",
    "TrainOccupancyCreate",
    "TrainOccupancyResponse",
    # Congestion
    "CongestionEventResponse",
    "CongestionHeatmapPoint",
    # Alert
    "AlertBase",
    "AlertCreate",
    "AlertUpdate",
    "AlertResponse",
    # Prediction
    "CrowdPredictionRequest",
    "CrowdPredictionResponse",
    "DemandForecastResponse",
    "TrafficPatternResponse",
    # Analytics
    "TrafficAnalyticsResponse",
    "StationPerformanceResponse",
    "OperationalMonitoringResponse",
]