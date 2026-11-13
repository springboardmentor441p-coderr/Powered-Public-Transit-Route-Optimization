"""Service-adjustment scenarios & budget-neutral reallocation endpoints.

Reuses src.recommend_adjustments.compute_cell_scenario_effect directly so API math
matches Step 8/9 CSV outputs with zero duplicated simulation logic.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.app.data import clean_records
from backend.app.schemas import GenericTableResponse, ScenarioRequest, ScenarioResponse, ScenarioResult
from src.recommend_adjustments import compute_cell_scenario_effect

router = APIRouter(prefix="/api", tags=["scenarios"])


@router.get("/scenarios/plan", response_model=GenericTableResponse)
def get_budget_neutral_plan(request: Request) -> GenericTableResponse:
    """Return Step 9 budget-neutral service-hour reallocation, candidate scenarios, and corridor merge checks."""
    store = request.app.state.store
    df = store.step9_reallocation.copy()
    return GenericTableResponse(
        period="Aug–Oct 2026 Observed Typical Days (63 weekdays + 27 weekend days)",
        source="app_data/step9_budget_neutral_reallocation.csv, step8_candidate_scenarios.csv & step8_shared_corridor_merge_checks.csv",
        count=len(df),
        rows=clean_records(df),
        metadata={
            "assumption": "riders stay the same when trips change",
            "assumption_detail": store.optimization_thresholds["step8_9_adjustment_rules"][
                "demand_assumption_statement"
            ],
            "candidate_scenarios": clean_records(store.step8_candidate_scenarios),
            "merge_checks": clean_records(store.step8_merge_checks),
        },
    )


@router.post("/scenarios", response_model=ScenarioResponse)
def calculate_scenario(request: Request, payload: ScenarioRequest) -> ScenarioResponse:
    store = request.app.state.store
    review_df = store.review_list
    obs_df = store.obs_review_hourly
    cfg = store.optimization_thresholds

    if payload.route not in store.valid_routes:
        raise HTTPException(status_code=404, detail=f"Route '{payload.route}' not found in study routes.")

    cell = review_df[
        (review_df["route"] == payload.route)
        & (review_df["day_group"] == payload.day_group)
        & (review_df["time_band"] == payload.time_band)
    ]
    if cell.empty:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No active scheduled cell found for route={payload.route}, "
                f"day_group={payload.day_group}, time_band={payload.time_band}."
            ),
        )
    cand = cell.iloc[0]

    sub_hrs = obs_df[
        (obs_df["route"] == payload.route)
        & (obs_df["day_group"] == payload.day_group)
        & (obs_df["time_band"] == payload.time_band)
    ]

    dg_svc_total = float(obs_df[obs_df["day_group"] == payload.day_group]["service_hours"].sum())
    net_window_svc = float(obs_df["service_hours"].sum())
    rules = cfg["step8_9_adjustment_rules"]
    c_cfg = cfg["step7_review_thresholds"]["coverage_guardrails"]

    effect = compute_cell_scenario_effect(
        route=str(cand["route"]),
        day_group=str(cand["day_group"]),
        days_count=int(cand["days_count"]),
        days_in_day_group=int(cand["days_in_day_group"]),
        time_band=str(cand["time_band"]),
        review_category=str(cand["review_category"]),
        group_id=int(cand["group_id"]),
        exclusive_stop_share=float(cand["exclusive_stop_share"]),
        active_hours=int(cand["active_hours"]),
        base_trips=int(cand["total_trips_running"]),
        base_service_hours=float(cand["total_service_hours"]),
        constant_obs_ridership=float(cand["total_obs_ridership"]),
        base_riders_per_trip=float(cand["obs_riders_per_trip"]),
        base_riders_per_service_hour=float(cand["obs_riders_per_service_hour"]),
        base_high_demand_hours=int(cand["high_demand_hours"]),
        hourly_trips=sub_hrs["trips_running"].values,
        hourly_riders=sub_hrs["ridership"].values,
        hourly_p75=sub_hrs["threshold_p75"].values,
        dg_svc_total=dg_svc_total,
        net_window_svc=net_window_svc,
        pct=float(payload.trip_change_pct),
        floor_per_hr=int(rules["min_trips_per_active_hour_floor"]),
        high_excl_threshold=float(c_cfg["high_exclusive_stop_share"]),
    )

    # Convert any NaN floats safely to None for Pydantic serialization
    cleaned_effect = clean_records(
        __import__("pandas").DataFrame([effect])
    )[0]

    return ScenarioResponse(
        assumption="riders stay the same when trips change",
        assumption_detail=rules["demand_assumption_statement"],
        period="2026-08-01 to 2026-10-31 (Aug–Oct observed typical days; p75 fixed from Jan–May)",
        source="app_data/review_list.csv & app_data/obs_review_hourly_distribution.parquet via src/recommend_adjustments.py",
        scenario=ScenarioResult(**cleaned_effect),
    )

