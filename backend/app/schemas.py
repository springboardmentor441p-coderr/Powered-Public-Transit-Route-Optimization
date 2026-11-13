"""Pydantic request & response models for the Transit Optimization API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator


class ScenarioRequest(BaseModel):
    route: str = Field(..., min_length=1, max_length=32)
    day_group: str = Field(
        ...,
        description="Day group ('weekday' or 'weekend', also accepts 'Typical Weekday'/'Typical Saturday'/'Typical Sunday').",
    )
    time_band: str = Field(
        ...,
        description="Canonical time band: early_morning, morning_peak, midday, evening_peak, or night.",
    )
    trip_change_pct: float = Field(
        ...,
        gt=-100.0,
        le=200.0,
        description="Percentage change in scheduled trips (e.g., -20, -10, +10, +20).",
    )

    @field_validator("day_group")
    @classmethod
    def normalize_day_group(cls, value: str) -> str:
        v = value.strip().lower()
        if v in {"weekday", "typical weekday"}:
            return "weekday"
        if v in {"weekend", "typical saturday", "typical sunday"}:
            return "weekend"
        raise ValueError("day_group must be 'weekday' or 'weekend'")

    @field_validator("time_band")
    @classmethod
    def validate_time_band(cls, value: str) -> str:
        allowed = {"early_morning", "morning_peak", "midday", "evening_peak", "night"}
        v = value.strip().lower()
        if v not in allowed:
            raise ValueError(f"time_band must be one of {sorted(allowed)}")
        return v


class ScenarioResult(BaseModel):
    route: str
    day_group: str
    days_count: int
    days_in_day_group: int
    time_band: str
    review_category: str
    group_id: int
    exclusive_stop_share: float
    scenario_trip_change_pct: float
    effective_trip_change_pct: float
    base_trips: int
    new_trips: int
    delta_trips: int
    base_service_hours: float
    new_service_hours: float
    delta_service_hours: float
    delta_service_hours_per_day: float | None = None
    pct_of_day_group_service_hours: float | None = None
    pct_of_window_network_service_hours: float | None = None
    constant_obs_ridership: float
    base_riders_per_trip: float
    new_riders_per_trip: float | None = None
    base_riders_per_service_hour: float
    new_riders_per_service_hour: float | None = None
    base_high_demand_hours: int
    sim_high_demand_hours: int
    high_demand_hours_delta: int
    guardrail_status: str


class ScenarioResponse(BaseModel):
    assumption: str
    assumption_detail: str
    period: str
    source: str
    scenario: ScenarioResult


class OverviewResponse(BaseModel):
    period: str
    source: str
    version: dict[str, Any]
    overview: dict[str, Any]


class GenericTableResponse(BaseModel):
    period: str
    source: str
    count: int
    rows: list[dict[str, Any]]
    metadata: dict[str, Any] | None = None


class RouteDetailResponse(BaseModel):
    period: str
    source: str
    route: str
    profile: dict[str, Any]
    thresholds: list[dict[str, Any]]
    hourly_patterns: list[dict[str, Any]]
    time_band_performance: list[dict[str, Any]]
    review_cells: list[dict[str, Any]]
    overlaps: list[dict[str, Any]]
    geometry: dict[str, Any] | None = None


class RouteForecastResponse(BaseModel):
    period: str
    source: str
    route: str
    validation_summary: dict[str, Any]
    test_summary: dict[str, Any]
    test_classification: list[dict[str, Any]]
    october_summary: dict[str, Any] | None = None
    october_daily: list[dict[str, Any]]
    october_hourly: list[dict[str, Any]]
    note: str


class GroupsResponse(BaseModel):
    period: str
    source: str
    metadata: dict[str, Any]
    routes: list[dict[str, Any]]
    group_profiles: list[dict[str, Any]]
    k_selection: list[dict[str, Any]]
    k2_vs_k3: list[dict[str, Any]]
    dbscan_summary: list[dict[str, Any]]
    geometries: dict[str, Any]


class EvaluationResponse(BaseModel):
    period: str
    source: str
    validation: dict[str, Any]
    test: dict[str, Any]
    october: dict[str, Any]
    official_test_runs_logged: int
    official_test_log: list[str]

