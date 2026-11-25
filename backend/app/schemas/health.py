from datetime import datetime, timezone
from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    """Schema for application health-check responses."""
    status: str = Field(default="ok", description="Status indicator")
    message: str = Field(default="AI_RouteRanker backend is running successfully", description="Informational message")
    project: str = Field(default="AI_RouteRanker", description="Project name")
    version: str = Field(default="0.1.0", description="API version")
    environment: str = Field(default="development", description="Current environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the health check"
    )
