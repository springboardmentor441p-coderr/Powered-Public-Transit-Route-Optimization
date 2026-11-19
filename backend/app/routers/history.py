"""Observed history endpoints: daily route history, route comparison and rankings.

All values come from app_data/obs_review_hourly_distribution.parquet, which holds
recorded boardings and GTFS scheduled service for the Aug-Oct 2026 typical days.
Holidays and outage hours are not in that table; they are listed back to the
screen as excluded dates so a gap is never shown as zero.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.data import clean_records

router = APIRouter(prefix="/api", tags=["history"])

OBS_START = "2026-08-01"
OBS_END = "2026-10-31"
DAY_TYPES = ("Typical Weekday", "Typical Saturday", "Typical Sunday")
EXCLUDED_DATES = {
    "2026-09-07": "Labor Day (holiday schedule, left out of typical days)",
    "2026-10-12": "Columbus Day (holiday schedule, left out of typical days)",
}
OBS_SOURCE = "app_data/obs_review_hourly_distribution.parquet (recorded boardings + GTFS scheduled service)"


def _check_range(start: str | None, end: str | None) -> tuple[str, str]:
    s = start or OBS_START
    e = end or OBS_END
    try:
        pd.Timestamp(s)
        pd.Timestamp(e)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Dates must look like YYYY-MM-DD ({exc}).") from exc
    if s < OBS_START or e > OBS_END:
        raise HTTPException(
            status_code=422,
            detail=f"Supported dates are {OBS_START} to {OBS_END}. You asked for {s} to {e}.",
        )
    if s > e:
        raise HTTPException(status_code=422, detail="Start date must be on or before the end date.")
    return s, e


def _check_day_type(day_type: str | None, allow_all: bool = True) -> str | None:
    if day_type is None or day_type == "" or (allow_all and day_type == "all"):
        return None
    if day_type not in DAY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"day_type must be one of {list(DAY_TYPES)}" + (" or 'all'." if allow_all else "."),
        )
    return day_type


def _replay_cap(request: Request, replay_id: str | None, end: str) -> tuple[str, dict | None]:
    """When a replay session is given, hide dates the replay has not revealed yet."""
    if not replay_id:
        return end, None
    rows = request.app.state.runtime.query(
        "SELECT clock_date, delay_days FROM replay_sessions WHERE session_id = ?", (replay_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Replay session '{replay_id}' not found.")
    clock = pd.Timestamp(rows[0]["clock_date"])
    latest = (clock - pd.Timedelta(days=int(rows[0]["delay_days"]))).strftime("%Y-%m-%d")
    capped = min(end, latest)
    return capped, {"replay_id": replay_id, "latest_revealed_date": latest}


def _filter_obs(store, start: str, end: str, day_type: str | None, routes: list[str] | None = None) -> pd.DataFrame:
    df = store.obs_review_hourly
    mask = (df["date"] >= start) & (df["date"] <= end)
    if day_type:
        mask &= df["day_type"] == day_type
    if routes:
        mask &= df["route"].isin(routes)
    return df[mask]


def _metrics(df: pd.DataFrame) -> dict:
    """Period indicators as ratios of sums over the same matched hours."""
    days = int(df["date"].nunique())
    boardings = float(df["ridership"].sum())
    svc = float(df["service_hours"].sum())
    trips = float(df["trips_running"].sum())
    active = df[df["trips_running"] > 0]
    above = active["ridership"] / active["trips_running"] > active["threshold_p75"]
    return {
        "observed_days": days,
        "observed_hours": int(len(df)),
        "total_boardings": round(boardings, 1),
        "total_service_hours": round(svc, 2),
        "total_trips_running": round(trips, 1),
        "mean_daily_boardings": round(boardings / days, 1) if days else None,
        "riders_per_service_hour": round(boardings / svc, 2) if svc > 0 else None,
        "riders_per_trip": round(boardings / trips, 2) if trips > 0 else None,
        "share_hours_above_p75": round(float(above.mean()), 4) if len(active) else None,
        "avg_trips_running_per_day": round(trips / days, 1) if days else None,
    }


def _excluded_in_range(start: str, end: str) -> list[dict]:
    return [{"date": d, "reason": r} for d, r in EXCLUDED_DATES.items() if start <= d <= end]


@router.get("/routes/{route}/daily")
def get_route_daily(
    request: Request,
    route: str,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    day_type: str | None = Query(default=None),
    replay_id: str | None = Query(default=None),
) -> dict:
    store = request.app.state.store
    if route not in store.valid_routes:
        raise HTTPException(status_code=404, detail=f"Route '{route}' not found in the 41 Manhattan study routes.")
    s, e = _check_range(start, end)
    dt = _check_day_type(day_type)
    e, replay_info = _replay_cap(request, replay_id, e)

    df = _filter_obs(store, s, e, dt, [route]) if s <= e else store.obs_review_hourly.iloc[0:0]
    daily = (
        df.groupby(["date", "day_type"], as_index=False)
        .agg(
            boardings=("ridership", "sum"),
            service_hours=("service_hours", "sum"),
            trips_running=("trips_running", "sum"),
            active_hours=("hour", "count"),
        )
        .sort_values("date")
    )
    daily["riders_per_service_hour"] = (daily["boardings"] / daily["service_hours"]).where(
        daily["service_hours"] > 0
    ).round(2)
    daily["service_hours"] = daily["service_hours"].round(2)

    return {
        "route": route,
        "period": f"{s} to {e}" + (f" ({dt})" if dt else " (all typical day types)"),
        "source": OBS_SOURCE,
        "provenance": "Published boardings · Scheduled service",
        "replay": replay_info,
        "excluded_dates": _excluded_in_range(s, e),
        "summary": _metrics(df) if len(df) else None,
        "rows": clean_records(daily),
    }


@router.get("/compare")
def compare_routes(
    request: Request,
    routes: str = Query(..., description="Comma separated, 2 to 4 routes"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    day_type: str | None = Query(default=None),
    replay_id: str | None = Query(default=None),
) -> dict:
    store = request.app.state.store
    picked = [r.strip() for r in routes.split(",") if r.strip()]
    picked = list(dict.fromkeys(picked))
    if len(picked) < 2 or len(picked) > 4:
        raise HTTPException(status_code=422, detail="Pick between 2 and 4 different routes to compare.")
    bad = [r for r in picked if r not in store.valid_routes]
    if bad:
        raise HTTPException(status_code=404, detail=f"Unknown route(s): {', '.join(bad)}.")
    s, e = _check_range(start, end)
    dt = _check_day_type(day_type)
    e, replay_info = _replay_cap(request, replay_id, e)

    df = _filter_obs(store, s, e, dt, picked) if s <= e else store.obs_review_hourly.iloc[0:0]
    prof_cols = [
        "route", "route_long_name", "service_type", "stop_count", "route_length_km",
        "trips_per_weekday", "trips_per_saturday", "trips_per_sunday", "first_departure",
        "exclusive_stop_share", "group_id", "group_label",
    ]
    prof = store.routes_summary[store.routes_summary["route"].isin(picked)]
    prof = prof[[c for c in prof_cols if c in prof.columns]]
    prof_map = {r["route"]: r for r in clean_records(prof)}

    out_routes = []
    for r in picked:
        sub = df[df["route"] == r]
        bands = []
        for tb, g in sub.groupby("time_band"):
            m = _metrics(g)
            bands.append({"time_band": tb, **m})
        hourly = (
            sub.groupby("hour", as_index=False)
            .agg(boardings=("ridership", "sum"), days=("date", "nunique"), trips=("trips_running", "sum"))
        )
        n_days = max(int(sub["date"].nunique()), 1)
        hourly["mean_boardings"] = (hourly["boardings"] / n_days).round(1)
        daily = sub.groupby("date", as_index=False).agg(boardings=("ridership", "sum"))
        out_routes.append(
            {
                "route": r,
                "profile": prof_map.get(r),
                "metrics": _metrics(sub) if len(sub) else None,
                "time_bands": clean_records(pd.DataFrame(bands)) if bands else [],
                "hourly": clean_records(hourly[["hour", "mean_boardings"]]),
                "daily": clean_records(daily),
                "geometry": store.route_geometries.get("routes", {}).get(r),
            }
        )

    pairs = store.route_overlap_pairs
    pair_rows = pairs[pairs["route_1"].isin(picked) & pairs["route_2"].isin(picked)]

    return {
        "period": f"{s} to {e}" + (f" ({dt})" if dt else " (all typical day types)"),
        "source": OBS_SOURCE + " · routes_summary.csv · route_overlap_pairs.csv · route_geometries.json",
        "provenance": "Published boardings · Scheduled service",
        "geometry_version": store.route_geometries.get("source_snapshot"),
        "replay": replay_info,
        "excluded_dates": _excluded_in_range(s, e),
        "routes": out_routes,
        "shared_stops": clean_records(pair_rows),
    }


def _rank_table(
    store,
    df: pd.DataFrame,
    indicator: str,
    ascending: bool,
    min_days: int,
    min_trips: float,
    candidates: list[str],
) -> pd.DataFrame:
    rows = []
    for r, g in df.groupby("route"):
        m = _metrics(g)
        rows.append({"route": r, **m})
    seen = {row["route"] for row in rows}
    for r in candidates:
        if r not in seen:
            rows.append({"route": r, "observed_days": 0, "observed_hours": 0})
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    for col in ("mean_daily_boardings", "riders_per_service_hour", "riders_per_trip",
                "share_hours_above_p75", "avg_trips_running_per_day"):
        if col not in t.columns:
            t[col] = None
    t = t.astype({c: "object" for c in t.columns if c != "route"}).where(t.notna(), None)
    reasons = []
    for _, row in t.iterrows():
        why = []
        if row["observed_days"] == 0:
            reasons.append("no recorded service of this day type in the period")
            continue
        if row["observed_days"] < min_days:
            why.append(f"only {int(row['observed_days'])} observed days (needs {min_days})")
        if (row["avg_trips_running_per_day"] or 0) < min_trips:
            why.append(f"fewer than {min_trips:g} trips running per day on average")
        if row[indicator] is None or pd.isna(row[indicator]):
            why.append("indicator not available (no valid denominator)")
        reasons.append("; ".join(why) if why else None)
    t["ineligible_reason"] = reasons
    t["eligible"] = t["ineligible_reason"].isna()
    elig = t[t["eligible"]]
    t["rank"] = None
    if not elig.empty:
        ranks = elig[indicator].astype(float).rank(method="min", ascending=ascending).astype(int)
        t.loc[ranks.index, "rank"] = ranks
    t["rank"] = t["rank"].astype("object")
    meta = store.routes_summary.set_index("route")
    t["route_long_name"] = t["route"].map(meta["route_long_name"])
    t["group_label"] = t["route"].map(meta["group_label"]) if "group_label" in meta else None
    t["group_id"] = t["route"].map(meta["group_id"]) if "group_id" in meta else None
    t["_sort"] = t["rank"].apply(lambda x: 10_000 if x is None else int(x))
    return t.sort_values(["_sort", "route"]).drop(columns="_sort")


@router.get("/rankings")
def get_rankings(
    request: Request,
    indicator: str = Query(default="riders_per_service_hour"),
    direction: str = Query(default="desc"),
    day_type: str = Query(default="Typical Weekday"),
    min_days: int | None = Query(default=None, ge=1, le=90),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    group_id: int | None = Query(default=None),
    replay_id: str | None = Query(default=None),
) -> dict:
    store = request.app.state.store
    cfg = store.ranking_config
    if indicator not in cfg["indicators"]:
        raise HTTPException(status_code=422, detail=f"indicator must be one of {list(cfg['indicators'])}.")
    if direction not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="direction must be 'asc' or 'desc'.")
    dt = _check_day_type(day_type, allow_all=False)
    s, e = _check_range(start, end)
    e, replay_info = _replay_cap(request, replay_id, e)
    gate = int(min_days if min_days is not None else cfg["default_min_observed_days"])
    min_trips = float(cfg["min_avg_trips_running_per_day"])
    ascending = direction == "asc"

    df = _filter_obs(store, s, e, dt) if s <= e else store.obs_review_hourly.iloc[0:0]
    if group_id is not None:
        members = store.routes_summary.loc[store.routes_summary["group_id"] == group_id, "route"]
        df = df[df["route"].isin(members)]

    candidates = store.routes_summary["route"].astype(str).tolist()
    if group_id is not None:
        candidates = store.routes_summary.loc[store.routes_summary["group_id"] == group_id, "route"].astype(str).tolist()
    table = _rank_table(store, df, indicator, ascending, gate, min_trips, candidates)

    sensitivity = []
    for v in cfg.get("sensitivity_min_days_values", []):
        t2 = _rank_table(store, df, indicator, ascending, int(v), min_trips, candidates)
        top = t2[t2["eligible"]].head(5)["route"].tolist() if not t2.empty else []
        sensitivity.append(
            {
                "min_days": int(v),
                "eligible_routes": int(t2["eligible"].sum()) if not t2.empty else 0,
                "top_5": top,
            }
        )

    return {
        "period": f"{s} to {e} ({dt})",
        "source": OBS_SOURCE + " · app_data/ranking_config.json",
        "provenance": "Published boardings · Scheduled service",
        "replay": replay_info,
        "excluded_dates": _excluded_in_range(s, e),
        "resolved_config": {
            "config_version": cfg["config_version"],
            "indicator": indicator,
            "indicator_definition": cfg["indicators"][indicator],
            "direction": direction,
            "day_type": dt,
            "min_observed_days": gate,
            "min_observed_days_reason": cfg["min_observed_days_reason"],
            "min_avg_trips_running_per_day": min_trips,
            "group_id": group_id,
            "ties": "Tied values share the same rank (1, 2, 2, 4).",
        },
        "indicators": cfg["indicators"],
        "count": int(len(table)),
        "eligible_count": int(table["eligible"].sum()) if not table.empty else 0,
        "rows": clean_records(table) if not table.empty else [],
        "sensitivity": sensitivity,
    }
