"""Stage 5, Step 45: route/day-type utilization profiles and the named rankings (spec 9.7.1, 9.7.2, 9.12).

One row per route x day type (W, A, U) x period, for EVERY route with a matched row in the period, from the
matched table (Stage 2):
  observed_days               distinct matched dates of that day type in the period (0 is a real count)
  rides_sum, scheduled_trips_sum, scheduled_hours_sum   sums over the SAME matched dates; missing (never 0)
                                                        when the route has no matched days of that day type
  mean_daily_rides            rides_sum / observed_days
  rides_per_scheduled_trip    rides_sum / scheduled_trips_sum      (positive denominator required)
  rides_per_scheduled_hour    rides_sum / scheduled_hours_sum      (positive denominator AND complete durations
                                                                   on every included day; otherwise unavailable)
  scheduled_service_days      dates of that day type with at least one scheduled trip (descriptive schedule), so
                              "no scheduled service" can be told apart from "ran, but no ridership record"
Ratios are ratios of sums, never an average of daily ratios (9.7.1).
Each named ranking applies the RANKING gate (ranking_min_observed_days) plus its own value check, then ranks
eligible rows descending within (period, day type), ties sharing the lowest rank. Ineligible rows stay in the
table, unranked, with their observed-day count and a reason (9.7.2). Clustering gates live elsewhere and are
applied independently.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

KEY = ["route", "date"]
DAYTYPES = ["W", "A", "U"]
VIEWS = {  # ranking column -> value column (spec 9.12 named indicators)
    "observed_daily_demand_rank": "mean_daily_rides",
    "rides_per_trip_rank": "rides_per_scheduled_trip",
    "service_productivity_metric_rank": "rides_per_scheduled_hour",
}
NO_DAYS = "no matched days of this day type"
NO_SERVICE = "no scheduled service of this day type"


class ProfileError(ValueError):
    pass


def schedule_with_daytype(schedule: pd.DataFrame, matched: pd.DataFrame) -> pd.DataFrame:
    """Scheduled route/days (Stage 2 descriptive schedule) labelled with the date's reported day type.
    Every route on a date shares one reported day type; a date with no ridership record keeps no label."""
    per_date = matched.groupby("date")["daytype"].nunique()
    if (per_date > 1).any():
        raise ProfileError("a date has more than one reported day type")
    dmap = matched.drop_duplicates("date").set_index("date")["daytype"]
    s = schedule[["route", "date", "scheduled_trips"]].copy()
    s["date"] = pd.to_datetime(s["date"])
    s["daytype"] = s["date"].map(dmap)
    return s


def load_schedule(path, matched: pd.DataFrame) -> pd.DataFrame:
    return schedule_with_daytype(pd.read_csv(path, dtype={"route": str}, parse_dates=["date"]), matched)


def load_matched(path) -> pd.DataFrame:
    m = pd.read_csv(path, dtype={"route": str, "daytype": str}, parse_dates=["date"])
    m["duration_complete"] = m["duration_complete"].map({True: True, False: False, "True": True,
                                                         "False": False}).astype("boolean")
    if m.duplicated(KEY).any():
        raise ProfileError("matched table must have one row per route/date")
    return m


def _days(n: pd.Series) -> pd.Series:
    return n.astype(str) + np.where(n == 1, " day", " days")


def utilization_profiles(matched: pd.DataFrame, period_name: str, start: str, end: str, cfg: dict,
                         schedule: pd.DataFrame | None = None) -> pd.DataFrame:
    """`schedule` (optional): output of schedule_with_daytype; without it, zero-day rows cannot say whether
    service was scheduled and keep the general reason."""
    gate = int(cfg["gates"]["ranking_min_observed_days"])
    m = matched[matched["date"].between(pd.Timestamp(start), pd.Timestamp(end)) & matched["daytype"].isin(DAYTYPES)]
    if m.duplicated(KEY).any():
        raise ProfileError("matched table must have one row per route/date")
    if m["rides"].isna().any():
        raise ProfileError("matched rows must have recorded rides")
    m = m.assign(incomplete=~m["duration_complete"].fillna(False).astype(bool) | m["scheduled_service_hours"].isna())
    g = m.groupby(["route", "daytype"], sort=True)
    agg = pd.DataFrame({
        "observed_days": g["date"].nunique(),
        "rides_sum": g["rides"].sum().astype(float),
        "scheduled_trips_sum": g["scheduled_trips"].sum().astype(float),
        "scheduled_hours_sum": g["scheduled_service_hours"].sum(min_count=1),
        "incomplete_duration_days": g["incomplete"].sum(),
    })
    # every route in the period gets W, A and U rows; a day type with no matched days is a real count of 0,
    # and its sums stay missing (no observations), never 0
    full = pd.MultiIndex.from_product([sorted(m["route"].unique()), DAYTYPES], names=["route", "daytype"])
    p = agg.reindex(full).reset_index()
    p["observed_days"] = p["observed_days"].fillna(0).astype("int64")
    p["incomplete_duration_days"] = p["incomplete_duration_days"].fillna(0).astype("int64")
    if schedule is not None:
        sc = schedule[schedule["date"].between(pd.Timestamp(start), pd.Timestamp(end))
                      & schedule["scheduled_trips"].gt(0) & schedule["daytype"].isin(DAYTYPES)]
        days = sc.groupby(["route", "daytype"])["date"].nunique()
        p["scheduled_service_days"] = (days.reindex(pd.MultiIndex.from_frame(p[["route", "daytype"]]))
                                       .fillna(0).astype("int64").to_numpy())
    else:
        p["scheduled_service_days"] = pd.array([pd.NA] * len(p), dtype="Int64")
    p.loc[p["incomplete_duration_days"] > 0, "scheduled_hours_sum"] = np.nan  # a partial sum would understate service
    p["mean_daily_rides"] = p["rides_sum"] / p["observed_days"].where(p["observed_days"] > 0)
    p["rides_per_scheduled_trip"] = p["rides_sum"] / p["scheduled_trips_sum"].where(p["scheduled_trips_sum"] > 0)
    p["rides_per_scheduled_hour"] = p["rides_sum"] / p["scheduled_hours_sum"].where(p["scheduled_hours_sum"] > 0)
    p["rides_sum"] = p["rides_sum"].astype("Int64")
    p["scheduled_trips_sum"] = p["scheduled_trips_sum"].astype("Int64")
    p.insert(0, "period_end", end)
    p.insert(0, "period_start", start)
    p.insert(0, "period_name", period_name)
    return rank_views(p, gate)


def rank_views(p: pd.DataFrame, gate: int) -> pd.DataFrame:
    """The named rankings on a profile table (one row per route x day type): the ranking gate, each view's value
    check and reason, then a descending rank within each day type, ties sharing the lowest rank. Ineligible rows stay,
    unranked, with their reason. Shared by Stage 5's profiles and the Stage 8 scenario re-ranking, so both apply
    exactly the same rules. Needs observed_days, scheduled_service_days, incomplete_duration_days and the view values."""
    p = p.copy()
    p["ranking_min_observed_days"] = gate
    for rank_col, value_col in VIEWS.items():
        reason = pd.Series("", index=p.index, dtype="object")
        none = p["observed_days"] == 0
        reason[none] = NO_DAYS
        reason[none & p["scheduled_service_days"].eq(0).fillna(False).to_numpy(dtype=bool)] = NO_SERVICE
        few = ~none & (p["observed_days"] < gate)
        reason[few] = "fewer than " + str(gate) + " observed days (" + p.loc[few, "observed_days"].astype(str) + ")"
        if value_col == "rides_per_scheduled_hour":
            inc = (reason == "") & (p["incomplete_duration_days"] > 0)
            reason[inc] = "scheduled hours incomplete on " + _days(p.loc[inc, "incomplete_duration_days"])
        bad = (reason == "") & p[value_col].isna()
        reason[bad] = "no positive denominator"
        eligible = reason == ""
        p[f"{rank_col}_eligible"] = eligible
        p[f"{rank_col}_reason"] = reason.replace("", np.nan)
        ranked = p.loc[eligible].groupby("daytype")[value_col].rank(method="min", ascending=False)
        p[rank_col] = ranked.reindex(p.index).astype("Int64")  # ineligible rows: no rank (<NA>), never 0
    return p


def all_ranking_periods(matched: pd.DataFrame, cfg: dict, schedule: pd.DataFrame | None = None) -> pd.DataFrame:
    out = [utilization_profiles(matched, name, s, e, cfg, schedule)
           for name, (s, e) in cfg["periods"]["ranking_periods"].items()]
    return pd.concat(out, ignore_index=True)


def gate_sensitivity(matched: pd.DataFrame, cfg: dict, schedule: pd.DataFrame | None = None) -> pd.DataFrame:
    """Ranked route counts per period and day type at other gate values (reported; the configured gate is unchanged)."""
    rows = []
    for gate in cfg["rankings"]["gate_sensitivity_values"]:
        c = {**cfg, "gates": {**cfg["gates"], "ranking_min_observed_days": gate}}
        p = all_ranking_periods(matched, c, schedule)
        for (period, daytype), g in p.groupby(["period_name", "daytype"]):
            rows.append({"period_name": period, "daytype": daytype, "gate": gate,
                         **{f"{v} ranked": int(g[f"{v}_eligible"].sum()) for v in VIEWS}})
    return pd.DataFrame(rows)


# ============================================================== Step 47: clustering profiles (spec 9.11.2)
WEEKEND = {"A": "saturday", "U": "sunday_holiday"}
NO_SERVICE_STATUS, FEW_STATUS, OK_STATUS = "no_scheduled_service", "insufficient_observations", "available"


def route_profiles(matched: pd.DataFrame, schedule: pd.DataFrame, start: str, end: str, cfg: dict) -> pd.DataFrame:
    """One row per route with a matched row in [start, end] (the development profile period). Clustering gates only;
    the ranking gate is never consulted here (9.7.2: the two are independent)."""
    g = cfg["gates"]
    m = matched[matched["date"].between(pd.Timestamp(start), pd.Timestamp(end)) & matched["daytype"].isin(DAYTYPES)]
    if m.duplicated(KEY).any():
        raise ProfileError("matched table must have one row per route/date")
    s = schedule[schedule["date"].between(pd.Timestamp(start), pd.Timestamp(end)) & schedule["scheduled_trips"].gt(0)]
    sched_days = s.groupby(["route", "daytype"])["date"].nunique()
    rows = []
    for route, r in m.groupby("route", sort=True):
        w = r[r["daytype"] == "W"]
        incomplete = int((~w["duration_complete"].fillna(False).astype(bool) | w["scheduled_service_hours"].isna()).sum())
        mean_w = float(w["rides"].mean()) if len(w) else np.nan
        row = {"route": route, "profile_start": start, "profile_end": end,
               "weekday_observed_days": int(w["date"].nunique()),
               "mean_weekday_rides": mean_w,
               "weekday_rides_cv": (float(w["rides"].std()) / mean_w) if len(w) >= 2 and mean_w > 0 else np.nan,
               "mean_weekday_scheduled_trips": float(w["scheduled_trips"].mean()) if len(w) else np.nan,
               "weekday_incomplete_duration_days": incomplete}
        trips, hours = float(w["scheduled_trips"].sum()), float(w["scheduled_service_hours"].sum())
        complete = incomplete == 0 and len(w) > 0
        row["mean_weekday_trip_duration_minutes"] = 60 * hours / trips if complete and trips > 0 else np.nan
        row["weekday_rides_per_scheduled_hour"] = float(w["rides"].sum()) / hours if complete and hours > 0 else np.nan
        for dt, name in WEEKEND.items():
            d = r[r["daytype"] == dt]
            obs, sch = int(d["date"].nunique()), int(sched_days.get((route, dt), 0))
            row[f"{name}_observed_days"], row[f"{name}_scheduled_days"] = obs, sch
            if obs >= int(g["cluster_min_weekend_days"]):
                status = OK_STATUS
                ratio = float(d["rides"].mean()) / mean_w if mean_w > 0 else np.nan
            elif obs == 0 and sch == 0:
                status, ratio = NO_SERVICE_STATUS, 0.0  # structural zero: no buses ran (schedule), not a missing value
            else:
                status, ratio = FEW_STATUS, np.nan  # service ran but too few observations: genuinely unavailable
            row[f"{name}_service_status"] = status
            row[f"{name}_to_weekday_rides_ratio"] = ratio
        base_ok = row["weekday_observed_days"] >= int(g["cluster_min_weekday_days"])
        row["base_eligible"] = base_ok
        row["ungrouped_reason"] = (np.nan if base_ok else
                                   f"fewer than {g['cluster_min_weekday_days']} matched weekdays "
                                   f"({row['weekday_observed_days']}) in the profile period")
        rows.append(row)
    out = pd.DataFrame(rows)
    if len(out):
        out["ungrouped_reason"] = out["ungrouped_reason"].astype(object)  # text, even when every route passes
    return out


def transformed(profiles: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    c = cfg["clustering"]
    x = profiles[c["candidates_in_priority_order"]].astype(float).copy()
    for f in c["log1p_features"]:
        x[f] = np.log1p(x[f])
    return x


def select_features(profiles: pd.DataFrame, cfg: dict) -> dict:
    """Fixed rules (groups.json), applied to base-eligible routes: availability, then |Spearman| in priority order."""
    c = cfg["clustering"]
    base = profiles[profiles["base_eligible"].astype(bool)]
    x = transformed(base, cfg)
    availability = x.notna().mean()
    decisions, kept = [], []
    for f in c["candidates_in_priority_order"]:
        if availability[f] < c["min_feature_availability"]:
            decisions.append({"feature": f, "kept": False, "availability": float(availability[f]),
                              "reason": f"available for {availability[f]:.1%} of base-eligible routes (< "
                                        f"{c['min_feature_availability']:.0%})"})
            continue
        clash = [(k, float(x[f].corr(x[k], method="spearman"))) for k in kept]
        clash = [(k, rho) for k, rho in clash if abs(rho) >= c["max_abs_spearman"]]
        if clash:
            k, rho = max(clash, key=lambda t: abs(t[1]))
            decisions.append({"feature": f, "kept": False, "availability": float(availability[f]),
                              "reason": f"|Spearman| {abs(rho):.3f} with `{k}` (kept, higher priority)"})
        else:
            kept.append(f)
            decisions.append({"feature": f, "kept": True, "availability": float(availability[f]), "reason": ""})
    return {"selected": kept, "decisions": pd.DataFrame(decisions),
            "spearman": x.corr(method="spearman"), "base_routes": int(len(base))}
