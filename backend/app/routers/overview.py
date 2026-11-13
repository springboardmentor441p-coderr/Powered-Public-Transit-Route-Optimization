"""Overview and network ridership pattern endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.data import clean_records
from backend.app.schemas import GenericTableResponse, OverviewResponse

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview(request: Request) -> OverviewResponse:
    store = request.app.state.store
    return OverviewResponse(
        period=store.version["study_window"],
        source="app_data/overview.json & app_data/version.json (MTA Ridership Jan–Oct 2026 & Manhattan GTFS)",
        version=store.version,
        overview=store.overview,
    )


@router.get("/network/daily", response_model=GenericTableResponse)
def get_network_daily(
    request: Request,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    period_tag: str | None = Query(default=None, description="Filter by train, val, test, or october"),
) -> GenericTableResponse:
    store = request.app.state.store
    df = store.network_daily.copy()
    if period_tag is not None:
        valid_tags = {"train", "val", "test", "october"}
        if period_tag not in valid_tags:
            raise HTTPException(status_code=400, detail=f"Invalid period_tag '{period_tag}'. Must be one of {sorted(valid_tags)}.")
        df = df[df["period_tag"] == period_tag]
    if start_date is not None:
        df = df[df["date"] >= start_date]
    if end_date is not None:
        df = df[df["date"] <= end_date]

    return GenericTableResponse(
        period="2026-01-04 to 2026-10-31 (daily totals across 41 Manhattan routes; missing dates kept null)",
        source="app_data/network_daily.csv (matched Jan–Sep + cleaned Oct 2026)",
        count=len(df),
        rows=clean_records(df),
        metadata={"missing_dates_count": int(df["is_missing"].sum()) if len(df) else 0},
    )


@router.get("/network/hourly", response_model=GenericTableResponse)
def get_network_hourly(
    request: Request,
    period: str = Query(default="jan_sep_typical", description="jan_sep_typical or aug_oct_typical"),
    day_type: str | None = Query(default=None),
) -> GenericTableResponse:
    store = request.app.state.store
    valid_periods = {"jan_sep_typical", "aug_oct_typical"}
    if period not in valid_periods:
        raise HTTPException(status_code=400, detail=f"Invalid period '{period}'. Must be one of {sorted(valid_periods)}.")
    df = store.network_hourly[store.network_hourly["period"] == period].copy()
    if day_type is not None:
        df = df[df["day_type"] == day_type]

    period_label = (
        "Jan–Sep 2026 typical normal days (excluding holidays, storms, outages, and M35 surge)"
        if period == "jan_sep_typical"
        else "Aug–Oct 2026 typical normal days (90 typical days: 63 weekday + 27 weekend)"
    )
    return GenericTableResponse(
        period=period_label,
        source="app_data/network_hourly.csv (aggregated by day_type and hour across 41 routes)",
        count=len(df),
        rows=clean_records(df),
    )

