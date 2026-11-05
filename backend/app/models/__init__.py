"""Database models package."""
# Import all models to register them with SQLAlchemy
from app.models.user import User, RefreshToken  # noqa: F401
from app.models.station import Station, Line  # noqa: F401
from app.models.train import Train, Schedule  # noqa: F401
from app.models.ridership import RidershipRecord, TrainOccupancy  # noqa: F401
from app.models.congestion import CongestionEvent  # noqa: F401
from app.models.alert import Alert  # noqa: F401

__all__ = [
    "User",
    "RefreshToken",
    "Station",
    "Line",
    "Train",
    "Schedule",
    "RidershipRecord",
    "TrainOccupancy",
    "CongestionEvent",
    "Alert",
]