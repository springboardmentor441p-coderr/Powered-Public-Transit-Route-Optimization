"""Pydantic v2 schemas for historical Random Forest evaluation predictions."""

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PaginationMeta


class HistoricalPredictionItem(BaseModel):
    """Single historical evaluation prediction vs actual ridership observation."""

    model_config = ConfigDict(extra="forbid")

    route_id: str
    date: date
    daytype: str
    actual_rides: Optional[float] = Field(None, ge=0.0, description="Observed daily CTA rides")
    predicted_rides: Optional[float] = Field(None, description="Tuned Random Forest historical prediction")
    absolute_error: Optional[float] = Field(None, ge=0.0, description="|predicted_rides - actual_rides|")
    percentage_error: Optional[float] = Field(
        None,
        ge=0.0,
        description="(absolute_error / actual_rides) * 100; null when actual_rides == 0 or non-finite",
    )
    baseline_seasonal_naive_prediction: Optional[float] = Field(
        None, description="Seasonal naive baseline prediction (test and August holdout periods)"
    )
    baseline_b_strategy: Optional[str] = Field(
        None,
        description="Canonical Baseline B strategy ('calendar_t7', 'recent_28d_daytype', 'historical_mean', or null)",
    )
    fallback_baseline_b: Optional[bool] = Field(
        None,
        description="True when a fallback strategy ('recent_28d_daytype' or 'historical_mean') was used; False for primary 'calendar_t7'",
    )


class HistoricalForecastResponse(BaseModel):
    """Response schema for GET /api/v1/forecasting/historical."""

    model_config = ConfigDict(extra="forbid")

    forecast_scope: Literal["historical_evaluation_only"] = "historical_evaluation_only"
    future_forecasting_supported: Literal[False] = False
    future_forecasting_note: str = (
        "Autoregressive Random Forest models require observed historical lag features; "
        "no verified future-date inference pipeline exists beyond 2026-08-31."
    )
    tier: Literal["tier1", "tier2"]
    period: Literal["validation", "test", "august_holdout"]
    model_identifier: str
    evaluation_start: date
    evaluation_end: date
    total_records: int = Field(..., ge=0)
    returned_records: int = Field(..., ge=0)
    pagination: PaginationMeta
    filters: Dict[str, Any] = Field(default_factory=dict)
    data: List[HistoricalPredictionItem]


class TierPeriodEvaluationSummary(BaseModel):
    """Aggregate historical evaluation metrics for one (tier, period) partition."""

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier1", "tier2"]
    period: Literal["validation", "test", "august_holdout"]
    model_identifier: str
    evaluation_start: date
    evaluation_end: date
    rows_evaluated: int = Field(
        ..., ge=0, description="Number of common rows over which aggregate evaluation metrics were computed"
    )
    total_prediction_records: int = Field(
        ..., ge=0, description="Total prediction rows present in the canonical artifact for this partition"
    )
    evaluation_population_note: Optional[str] = Field(
        None, description="Note when total_prediction_records differs from metric rows_evaluated"
    )
    wape: float = Field(..., description="Weighted Absolute Percentage Error (%)")
    mae: float = Field(..., description="Mean Absolute Error (rides)")
    rmse: float = Field(..., description="Root Mean Squared Error (rides)")
    r2: float = Field(..., description="Coefficient of Determination (R^2)")
    baseline_b_wape: Optional[float] = None
    baseline_b_mae: Optional[float] = None
    baseline_b_rmse: Optional[float] = None
    baseline_b_r2: Optional[float] = None


class HistoricalForecastSummaryResponse(BaseModel):
    """Response schema for GET /api/v1/forecasting/historical/summary."""

    model_config = ConfigDict(extra="forbid")

    forecast_scope: Literal["historical_evaluation_only"] = "historical_evaluation_only"
    future_forecasting_supported: Literal[False] = False
    future_forecasting_note: str = (
        "Aggregate metrics reflect verified historical validation, test, and August holdout "
        "evaluations only. Future-date forecasting is not supported."
    )
    supported_combinations: List[str]
    summaries: List[TierPeriodEvaluationSummary]
