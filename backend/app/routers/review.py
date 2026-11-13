"""Review list endpoints (Step 7 observed typical Aug-Oct 2026 cells)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.data import clean_records
from backend.app.schemas import GenericTableResponse

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/review", response_model=GenericTableResponse)
def get_review_list(
    request: Request,
    day_group: str | None = Query(default=None, description="weekday or weekend"),
    review_category: str | None = Query(default=None),
    time_band: str | None = Query(default=None),
    route: str | None = Query(default=None),
    group_id: int | None = Query(default=None),
    min_days: int | None = Query(default=None, ge=1),
    sort_by: str = Query(default="high_demand_freq_pct"),
    sort_dir: str = Query(default="desc"),
) -> GenericTableResponse:
    store = request.app.state.store
    df = store.review_list.copy()

    if day_group is not None:
        dg = day_group.strip().lower()
        if dg not in {"weekday", "weekend"}:
            raise HTTPException(status_code=400, detail="day_group must be 'weekday' or 'weekend'.")
        df = df[df["day_group"] == dg]
    if review_category is not None:
        df = df[df["review_category"] == review_category]
    if time_band is not None:
        df = df[df["time_band"] == time_band]
    if route is not None:
        df = df[df["route"] == route]
    if group_id is not None:
        df = df[df["group_id"] == group_id]
    if min_days is not None:
        df = df[df["days_count"] >= min_days]

    if sort_by not in df.columns:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by column '{sort_by}'.")
    ascending = sort_dir.strip().lower() == "asc"
    df = df.sort_values(sort_by, ascending=ascending, na_position="last")

    all_df = store.review_list
    summary = {
        "total_cells": int(len(all_df)),
        "category_counts": {
            str(k): int(v) for k, v in all_df["review_category"].value_counts().items()
        },
        "thresholds": store.optimization_thresholds["step7_review_thresholds"],
    }

    return GenericTableResponse(
        period="2026-08-01 to 2026-10-31 (90 typical days: 63 weekdays + 27 weekend days; Labor/Columbus/outages/M35 surge excluded)",
        source="app_data/review_list.csv (Step 7 observed ridership & GTFS scheduled service-hours)",
        count=len(df),
        rows=clean_records(df),
        metadata=summary,
    )

