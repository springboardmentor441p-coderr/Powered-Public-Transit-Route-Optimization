from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    """Schema for application health-check responses."""
    status: str = Field(default="ok", description="Status indicator")
    message: str = Field(default="AI_RouteRanker backend is running successfully", description="Informational message")
    project: str = Field(default="AI_RouteRanker", description="Project name")
    version: str = Field(default="0.1.0", description="API version")
    environment: str = Field(default="development", description="Current environment")
    data_ready: bool = Field(default=True, description="True when all required DuckDB and artifact files exist")
    missing_artifacts_count: int = Field(default=0, ge=0, description="Count of missing required runtime artifacts")
    hydration_status: str = Field(default="disabled", description="Runtime dataset hydration status")
    hydration_progress: Optional[str] = Field(default=None, description="Verified/total remote runtime files")
    hydration_error: Optional[str] = Field(default=None, description="Sanitized error message if hydration failed")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the health check"
    )
