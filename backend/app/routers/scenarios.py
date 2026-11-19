"""Service-adjustment scenarios & budget-neutral reallocation endpoints.

Reuses src.recommend_adjustments.compute_cell_scenario_effect directly so API math
matches Step 8/9 CSV outputs with zero duplicated simulation logic.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

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
    high_excl_threshold = float(c_cfg["high_exclusive_stop_share"])

    excl_share = float(cand["exclusive_stop_share"])
    requested_pct = float(payload.trip_change_pct)
    applied_pct = requested_pct
    guardrail_capped = False
    max_recommended_cut_pct = -10.0 if excl_share >= high_excl_threshold else None
    guardrail_warning: str | None = None

    if excl_share >= high_excl_threshold and requested_pct < -10.0:
        if payload.apply_guardrail_cap:
            applied_pct = -10.0
            guardrail_capped = True
            guardrail_warning = (
                f"Cut capped at -10% (requested {requested_pct:+.1f}%): {cand['route']} serves "
                f"{excl_share * 100:.1f}% exclusive stops (>= {high_excl_threshold * 100:.0f}% coverage "
                "guardrail), matching the review list -10% trim limit."
            )
        else:
            guardrail_warning = (
                f"Warning: requested cut {requested_pct:+.1f}% exceeds the -10% coverage cap for "
                f"{cand['route']} ({excl_share * 100:.1f}% exclusive stops >= "
                f"{high_excl_threshold * 100:.0f}% threshold)."
            )

    effect = compute_cell_scenario_effect(
        route=str(cand["route"]),
        day_group=str(cand["day_group"]),
        days_count=int(cand["days_count"]),
        days_in_day_group=int(cand["days_in_day_group"]),
        time_band=str(cand["time_band"]),
        review_category=str(cand["review_category"]),
        group_id=int(cand["group_id"]),
        exclusive_stop_share=excl_share,
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
        pct=applied_pct,
        floor_per_hr=int(rules["min_trips_per_active_hour_floor"]),
        high_excl_threshold=high_excl_threshold,
    )
    if guardrail_capped:
        effect["guardrail_status"] = "capped_at_10pct_exclusivity_guardrail"
    elif guardrail_warning is None and effect["guardrail_status"] == "warning_pushes_hours_above_threshold":
        effect_delta = int(effect["high_demand_hours_delta"])
        guardrail_warning = (
            f"Warning: cutting trips here pushes +{effect_delta} additional hour(s) above the "
            "high riders-per-trip p75 threshold."
        )
    effect["requested_trip_change_pct"] = requested_pct
    effect["guardrail_capped"] = guardrail_capped
    effect["max_recommended_cut_pct"] = max_recommended_cut_pct
    effect["guardrail_warning"] = guardrail_warning

    # Convert any NaN floats safely to None for Pydantic serialization
    cleaned_effect = clean_records(pd.DataFrame([effect]))[0]

    return ScenarioResponse(
        assumption="riders stay the same when trips change",
        assumption_detail=rules["demand_assumption_statement"],
        period="2026-08-01 to 2026-10-31 (Aug–Oct observed typical days; p75 fixed from Jan–May)",
        source="app_data/review_list.csv & app_data/obs_review_hourly_distribution.parquet via src/recommend_adjustments.py",
        scenario=ScenarioResult(**cleaned_effect),
    )



# ---------------------------------------------------------------------------
# Single-day scenario with a baseline date, demand source and demand stress.
# ---------------------------------------------------------------------------

FORECAST_DEMAND_START = "2026-10-18"
FORECAST_DEMAND_END = "2026-10-31"


class DayScenarioRequest(BaseModel):
    route: str = Field(..., min_length=1, max_length=32)
    date: str = Field(..., description="Baseline service date, YYYY-MM-DD")
    demand_source: str = Field(default="observed", description="observed or forecast")
    trip_change_pct: float = Field(default=0.0, ge=-50.0, le=50.0)
    demand_multiplier: float = Field(default=1.0, ge=0.5, le=1.5)
    apply_guardrail_cap: bool = True
    save: bool = False
    label: str | None = Field(default=None, max_length=80)


def _day_metrics(trips: np.ndarray, svc: np.ndarray, demand: np.ndarray, p75: np.ndarray) -> dict:
    t = float(trips.sum())
    s = float(svc.sum())
    d = float(demand.sum())
    active = trips > 0
    rpt = np.divide(demand, trips, out=np.zeros_like(demand, dtype=float), where=active)
    above = int(((rpt > p75) & active).sum())
    return {
        "boardings": round(d, 1),
        "trips_running": round(t, 1),
        "service_hours": round(s, 2),
        "riders_per_service_hour": round(d / s, 2) if s > 0 else None,
        "riders_per_trip": round(d / t, 2) if t > 0 else None,
        "hours_above_p75": above,
        "active_hours": int(active.sum()),
        "max_hour_riders_per_trip": round(float(rpt[active].max()), 2) if active.any() else None,
    }


@router.post("/scenarios/day")
def calculate_day_scenario(request: Request, payload: DayScenarioRequest) -> dict:
    store = request.app.state.store
    cfg = store.optimization_thresholds
    route = payload.route.strip()
    if route not in store.valid_routes:
        raise HTTPException(status_code=404, detail=f"Route '{route}' not found in study routes.")
    try:
        date = pd.Timestamp(payload.date).strftime("%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must look like YYYY-MM-DD.") from exc
    source = payload.demand_source.strip().lower()
    if source not in {"observed", "forecast"}:
        raise HTTPException(status_code=422, detail="demand_source must be 'observed' or 'forecast'.")

    if source == "observed":
        rows = store.obs_review_hourly[
            (store.obs_review_hourly["route"] == route) & (store.obs_review_hourly["date"] == date)
        ].sort_values("hour")
        if rows.empty:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No recorded boardings for {route} on {date}. Observed baselines cover typical days "
                    "2026-08-01 to 2026-10-31 (Labor Day and Columbus Day are left out)."
                ),
            )
        demand = rows["ridership"].to_numpy(dtype=float)
        demand_label = "Published boardings (recorded)"
        demand_version = "MTA Bus Hourly Ridership, Aug-Oct 2026 typical days"
    else:
        if not (FORECAST_DEMAND_START <= date <= FORECAST_DEMAND_END):
            raise HTTPException(
                status_code=422,
                detail=f"Forecast demand is only saved for {FORECAST_DEMAND_START} to {FORECAST_DEMAND_END}.",
            )
        oc = store.october_hourly_forecast_vs_actual
        rows = oc[(oc["route"] == route) & (oc["date"] == date)].sort_values("hour")
        if rows.empty:
            raise HTTPException(status_code=404, detail=f"No saved forecast rows for {route} on {date}.")
        demand = rows["pred_ridership"].to_numpy(dtype=float)
        demand_label = "Predicted boardings (experimental)"
        demand_version = "Saved October forecast table from models/final_forecaster.joblib (GTFS 2026-10-17)"

    trips = rows["trips_running"].to_numpy(dtype=float)
    svc = rows["service_hours"].to_numpy(dtype=float)
    p75 = rows["threshold_p75"].to_numpy(dtype=float)
    day_type = str(rows["day_type"].iloc[0])

    rules = cfg["step8_9_adjustment_rules"]
    floor = float(rules["min_trips_per_active_hour_floor"])
    high_excl = float(cfg["step7_review_thresholds"]["coverage_guardrails"]["high_exclusive_stop_share"])
    prof = store.routes_summary[store.routes_summary["route"] == route].iloc[0]
    excl_share = float(prof["exclusive_stop_share"])

    requested = float(payload.trip_change_pct)
    applied = requested
    warnings: list[str] = []
    capped = False
    if excl_share >= high_excl and requested < -10.0:
        if payload.apply_guardrail_cap:
            applied = -10.0
            capped = True
            warnings.append(
                f"Cut capped at -10% (you asked for {requested:+.0f}%). {route} has {excl_share * 100:.0f}% of its "
                f"stops served by no other route, which is at or above the {high_excl * 100:.0f}% coverage rule."
            )
        else:
            warnings.append(
                f"{requested:+.0f}% is deeper than the -10% coverage limit for {route} "
                f"({excl_share * 100:.0f}% of stops served only by this route)."
            )

    new_trips = trips * (1.0 + applied / 100.0)
    floor_mask = (trips >= floor) & (new_trips < floor)
    new_trips = np.where(floor_mask, floor, new_trips)
    if floor_mask.any():
        warnings.append(f"{int(floor_mask.sum())} hour(s) kept at the minimum of {floor:g} trip running.")
    ratio = np.divide(new_trips, trips, out=np.ones_like(trips), where=trips > 0)
    new_svc = svc * ratio
    stressed = demand * float(payload.demand_multiplier)

    baseline = _day_metrics(trips, svc, demand, p75)
    stress_only = _day_metrics(trips, svc, stressed, p75)
    scenario = _day_metrics(new_trips, new_svc, stressed, p75)

    # Scheduled departures are only exported for the October check dates (18-31 Oct).
    oc = store.october_hourly_forecast_vs_actual
    dep_rows = oc[(oc["route"] == route) & (oc["date"] == date)]
    base_dep = float(dep_rows["trips_starting"].sum()) if not dep_rows.empty else None
    baseline["scheduled_departures"] = base_dep
    stress_only["scheduled_departures"] = base_dep
    scenario["scheduled_departures"] = round(base_dep * (1.0 + applied / 100.0), 1) if base_dep is not None else None
    if scenario["hours_above_p75"] > baseline["hours_above_p75"]:
        warnings.append(
            f"{scenario['hours_above_p75'] - baseline['hours_above_p75']} more hour(s) end up above the route's "
            "high riders-per-trip line."
        )

    rpt_base = np.divide(demand, trips, out=np.full_like(demand, np.nan), where=trips > 0)
    rpt_new = np.divide(stressed, new_trips, out=np.full_like(stressed, np.nan), where=new_trips > 0)
    hourly = pd.DataFrame(
        {
            "hour": rows["hour"].to_numpy(),
            "baseline_trips": trips,
            "scenario_trips": np.round(new_trips, 2),
            "baseline_boardings": np.round(demand, 1),
            "scenario_boardings": np.round(stressed, 1),
            "baseline_riders_per_trip": np.round(rpt_base, 2),
            "scenario_riders_per_trip": np.round(rpt_new, 2),
            "threshold_p75": p75,
        }
    )

    changed = []
    if applied != 0:
        changed.append(f"Trips running changed by {applied:+.0f}% in every scheduled hour")
    if payload.demand_multiplier != 1.0:
        changed.append(f"Demand multiplied by {payload.demand_multiplier:.2f} (stress test)")
    if not changed:
        changed.append("No change (baseline only)")

    inputs = {
        "route": route,
        "date": date,
        "day_type": day_type,
        "demand_source": source,
        "trip_change_pct_requested": requested,
        "trip_change_pct_applied": applied,
        "demand_multiplier": float(payload.demand_multiplier),
        "apply_guardrail_cap": payload.apply_guardrail_cap,
    }
    result = {
        "baseline": baseline,
        "stress_only": stress_only,
        "scenario": scenario,
        "guardrail_capped": capped,
        "warnings": warnings,
    }
    assumptions = [
        "Riders stay the same when trips change. Only the demand multiplier changes boardings.",
        "Service hours change in step with trips, so the average trip length stays the same.",
        "The demand multiplier is a stress test. It is not a forecast of how riders would react.",
        f"Every scheduled hour keeps at least {floor:g} trip running.",
        f"Routes with {high_excl * 100:.0f}% or more of stops served by no other route are capped at a -10% cut.",
        "No vehicle, crew or budget limits are checked here.",
    ]

    response = {
        "provenance": "Scenario assumptions",
        "demand_label": demand_label,
        "baseline_version": {"demand": demand_version, "schedule": "GTFS scheduled trips and service hours for that date"},
        "inputs": inputs,
        "changed_parameters": changed,
        "assumptions": assumptions,
        "result": result,
        "hourly": clean_records(hourly),
        "scenario_id": None,
        "saved_at": None,
    }
    if payload.save:
        sid = uuid.uuid4().hex[:10]
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        request.app.state.runtime.save_scenario(
            sid,
            created,
            payload.label,
            {**inputs, "demand_label": demand_label, "changed_parameters": changed, "assumptions": assumptions},
            result,
        )
        response["scenario_id"] = sid
        response["saved_at"] = created
    return response


@router.get("/scenarios/saved")
def list_saved_scenarios(request: Request) -> dict:
    rows = request.app.state.runtime.list_scenarios()
    return {
        "provenance": "Scenario assumptions",
        "source": "backend/runtime SQLite (saved_scenarios table)",
        "count": len(rows),
        "rows": rows,
    }
