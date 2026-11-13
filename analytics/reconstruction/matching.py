"""Step 14: exact route/date matching of rides with selected daily scheduled service (spec 9.6.4).

Three separate outputs (never merged back together):
  matched                    = route/date present on both sides
  ridership_without_schedule = a passenger observation with no selected scheduled service
  schedule_without_ridership = scheduled service with NO passenger observation; rides stay MISSING, never 0
Identities that must hold exactly:
  ridership observations = matched + ridership_without_schedule
  schedule records       = matched + schedule_without_ridership
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .gtfs_tables import normalize_route

KEY = ["route", "date"]


class RidershipConflictError(ValueError):
    """Two different records for one route/date: must be investigated, never summed."""


def load_ridership(path: Path) -> tuple[pd.DataFrame, dict]:
    """Parse the raw CSV (read-only). Returns route (trimmed str), date (datetime.date), daytype, rides (Int64)."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(raw.columns) != ["route", "date", "daytype", "rides"]:
        raise ValueError(f"unexpected ridership columns {list(raw.columns)}")
    df = pd.DataFrame({
        "route": normalize_route(raw["route"]),
        "date": pd.to_datetime(raw["date"].str.strip(), format="%m/%d/%Y", errors="raise").dt.date,
        "daytype": raw["daytype"].str.strip(),
        # remove thousands separators; an empty value stays <NA> (missing), it never becomes 0
        "rides": pd.to_numeric(raw["rides"].str.replace(",", "", regex=False).str.strip().replace("", pd.NA),
                               errors="raise").astype("Int64"),
    })
    if (df["rides"] < 0).any():
        raise ValueError("negative rides in ridership source")
    dup = df.duplicated(keep="first")
    df = df[~dup].reset_index(drop=True)
    conflicts = df[df.duplicated(KEY, keep=False)]
    if not conflicts.empty:
        raise RidershipConflictError(f"{conflicts.groupby(KEY).ngroups} conflicting route/date keys, e.g. "
                                     f"{conflicts.head(4).values.tolist()}")
    return df, {"raw_rows": len(raw), "exact_duplicates_removed": int(dup.sum()),
                "missing_rides": int(df["rides"].isna().sum())}


def _ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    num, den = num.astype("Float64"), den.astype("Float64")
    return (num / den.where(den > 0)).round(6)  # positive denominator required; otherwise missing


def match(schedule: pd.DataFrame, rides: pd.DataFrame, selection: pd.DataFrame,
          routes_by_snapshot: dict[str, set[str]], routes_any_archive: set[str]) -> dict[str, pd.DataFrame]:
    """schedule: daily_service rows; rides: ridership rows already restricted to the analysis period."""
    m = schedule.merge(rides, on=KEY, how="outer", validate="one_to_one", indicator=True)  # raises on dup keys

    matched = m[m["_merge"] == "both"].drop(columns="_merge").copy()
    matched["rides_per_scheduled_trip"] = _ratio(matched["rides"], matched["scheduled_trips"])
    matched["rides_per_scheduled_hour"] = _ratio(matched["rides"], matched["scheduled_service_hours"])
    matched = matched[["route", "date", "daytype", "rides", "snapshot_id", "route_id", "scheduled_trips",
                       "scheduled_service_hours", "duration_complete", "trips_missing_duration",
                       "rides_per_scheduled_trip", "rides_per_scheduled_hour"]]

    rws = m[m["_merge"] == "right_only"][["route", "date", "daytype", "rides"]].copy()
    sel = dict(zip(selection["date"], selection["snapshot_id"]))
    rws["selected_snapshot_id"] = rws["date"].map(sel)

    def reason(r):
        sid = r["selected_snapshot_id"]
        if sid is None or pd.isna(sid):
            return "no_snapshot_for_date"
        if r["route"] not in routes_by_snapshot.get(sid, set()):
            return "route_absent_from_selected_snapshot"
        return "route_in_snapshot_no_active_trips"
    rws["unmatched_reason"] = rws.apply(reason, axis=1) if len(rws) else pd.Series(dtype="string")
    rws["identifier_absent_from_all_archives"] = ~rws["route"].isin(routes_any_archive)

    swr = m[m["_merge"] == "left_only"][["route", "date", "snapshot_id", "route_id", "scheduled_trips",
                                         "scheduled_service_hours", "duration_complete",
                                         "trips_missing_duration"]].copy()
    swr["rides"] = pd.array([pd.NA] * len(swr), dtype="Int64")  # explicit missingness, never zero
    swr["missing_reason"] = "no_ridership_record"

    out = {"matched": matched, "ridership_without_schedule": rws, "schedule_without_ridership": swr}
    for k, v in out.items():
        out[k] = v.sort_values(KEY).reset_index(drop=True)
    return out


def per_route(df: pd.DataFrame, with_rides: bool) -> pd.DataFrame:
    """Per-route breakdown in the format of spec 9.6.4.1: records, (rides), first and last date."""
    g = df.groupby("route")
    out = pd.DataFrame({"records": g.size(), "first_date": g["date"].min(), "last_date": g["date"].max()})
    if with_rides:
        out.insert(1, "rides", g["rides"].sum(min_count=1).astype("Int64"))
    return out.sort_values(["records", "route"], ascending=[False, True]).reset_index()


def reconciliation(res: dict[str, pd.DataFrame], schedule: pd.DataFrame, rides: pd.DataFrame) -> dict:
    n_m, n_rws, n_swr = (len(res[k]) for k in ["matched", "ridership_without_schedule", "schedule_without_ridership"])
    sched_routes = schedule["route"].nunique()
    complete_routes = sched_routes - res["schedule_without_ridership"]["route"].nunique()
    return {
        "ridership_observations": len(rides),
        "schedule_records": len(schedule),
        "matched": n_m,
        "ridership_without_schedule": n_rws,
        "schedule_without_ridership": n_swr,
        "identity_ridership_holds": len(rides) == n_m + n_rws,
        "identity_schedule_holds": len(schedule) == n_m + n_swr,
        "matched_dates": res["matched"]["date"].nunique(),
        "matched_routes": res["matched"]["route"].nunique(),
        "schedule_dates": schedule["date"].nunique(),
        "schedule_routes": sched_routes,
        "ridership_dates": rides["date"].nunique(),
        "ridership_routes": rides["route"].nunique(),
        "schedule_conditioned_coverage_pct": round(100 * n_m / len(schedule), 3) if len(schedule) else None,
        "routes_with_records_on_every_scheduled_date": complete_routes,
        "matched_zero_ride_rows": int((res["matched"]["rides"] == 0).sum()),
    }
