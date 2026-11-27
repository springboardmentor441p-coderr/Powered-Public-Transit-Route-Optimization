"""Module 6b - Route optimisation suggestions and scenario simulation.

Rules operate on a route-hour frame that contains (predicted or actual)
ridership, scheduled trips and the KPI columns from
:func:`feature_engineering.add_performance_metrics`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .feature_engineering import add_performance_metrics


def required_trips(ridership: pd.Series, capacity: pd.Series, target: float | None = None) -> pd.Series:
    """Trips/hour needed so that estimated max-load equals ``target`` x capacity
    (``target`` defaults to the calibrated ``config.TARGET_OCCUPANCY`` at call time)."""
    target = target or C.TARGET_OCCUPANCY
    return np.ceil(ridership * C.PEAK_LOAD_FACTOR / (capacity * target))


def optimize_frequencies(frame: pd.DataFrame, ridership_col: str = "ridership") -> pd.DataFrame:
    """Re-size the timetable hour by hour.

    * Overcrowded hours -> add trips up to the target occupancy.
    * Underutilised hours -> remove trips but never below the policy floor
      (``MIN_TRIPS_PER_HOUR``) while the route is in service.
    Returns the frame with ``trips_opt``, ``delta_trips`` and optimised KPIs (suffix ``_opt``).
    """
    f = frame.copy()
    ev = f["evasion_factor"] if "evasion_factor" in f else 1.0
    need = required_trips(f[ridership_col] * ev, f["capacity"])
    in_service = f["trips"] > 0
    opt = f["trips"].copy()
    over = in_service & (f["occupancy"] > C.OVERCROWDED_MIN)
    under = in_service & (f["occupancy"] < C.UNDERUTILIZED_MAX) & (f["trips"] > C.MIN_TRIPS_PER_HOUR)
    opt[over] = np.maximum(f.loc[over, "trips"], need[over])
    opt[under] = np.maximum(need[under], C.MIN_TRIPS_PER_HOUR)
    opt[under] = np.minimum(opt[under], f.loc[under, "trips"])
    f["trips_opt"] = opt
    f["delta_trips"] = f["trips_opt"] - f["trips"]
    keep = [c for c in ("capacity", "trip_minutes", "transfers", "evasion_factor") if c in f]
    tmp = f[keep].copy()
    tmp["trips"] = f["trips_opt"]
    tmp["ridership"] = f[ridership_col]
    tmp = add_performance_metrics(tmp)
    for c in ("occupancy", "load_per_trip", "productivity", "avg_wait_min", "revenue_hours", "perf_class"):
        f[f"{c}_opt"] = tmp[c].values
    return f


def route_recommendations(opt: pd.DataFrame, profiles: pd.DataFrame, overlap: pd.DataFrame) -> pd.DataFrame:
    """Summarise the hourly re-sizing per route and add structural suggestions
    (merge with an overlapping low-demand route, split / short-turn long unreliable routes)."""
    g = opt.groupby("route_id")
    rec = pd.DataFrame({
        "ridership": g["ridership"].sum(),
        "est_riders": g["est_riders"].sum() if "est_riders" in opt else g["ridership"].sum(),
        "trips_now": g["trips"].sum(),
        "trips_opt": g["trips_opt"].sum(),
        "trips_added": g["delta_trips"].apply(lambda s: s[s > 0].sum()),
        "trips_removed": g["delta_trips"].apply(lambda s: -s[s < 0].sum()),
        "veh_hours_now": g["revenue_hours"].sum(),
        "veh_hours_opt": g["revenue_hours_opt"].sum(),
        "overcrowded_hours_now": g["perf_class"].apply(lambda s: (s == "Overcrowded").sum()),
        "overcrowded_hours_opt": g["perf_class_opt"].apply(lambda s: (s == "Overcrowded").sum()),
        "underutilized_hours_now": g["perf_class"].apply(lambda s: (s == "Underutilized").sum()),
        "underutilized_hours_opt": g["perf_class_opt"].apply(lambda s: (s == "Underutilized").sum()),
        "peak_occupancy_now": g["occupancy"].max(),
        "peak_occupancy_opt": g["occupancy_opt"].max(),
        "overcrowded_window": g.apply(lambda d: _window(d, d["perf_class"] == "Overcrowded"), include_groups=False),
        "underutilized_window": g.apply(lambda d: _window(d, d["perf_class"] == "Underutilized"), include_groups=False),
    }).reset_index()
    rec["productivity_now"] = rec["est_riders"] / rec["veh_hours_now"].replace(0, np.nan)
    rec["productivity_opt"] = rec["est_riders"] / rec["veh_hours_opt"].replace(0, np.nan)
    p = profiles.set_index("route_id")
    rec = rec.join(p[["length_mi", "reliability", "route_type", "borough", "pct_hours_underutilized",
                      "cluster_name"]], on="route_id")

    len_p90 = profiles["length_mi"].quantile(0.9)
    rel_med = profiles["reliability"].median()
    low_routes = set(profiles.loc[profiles["pct_hours_underutilized"] > 0.5, "route_id"])
    merge_partner = {}
    for _, row in overlap.iterrows():
        a, b = row["route_a"], row["route_b"]
        if a in low_routes and b not in merge_partner and a not in merge_partner and row["share_of_a"] > 0.4:
            merge_partner[a] = (b, row["share_of_a"])
        elif b in low_routes and b not in merge_partner and row["share_of_b"] > 0.4:
            merge_partner[b] = (a, row["share_of_b"])

    actions, reasons = [], []
    for _, r in rec.iterrows():
        a, why = [], []
        if r["trips_added"] > 0 and r["trips_removed"] > 0:
            a.append("Rebalance frequency")
            why.append(f"add {int(r['trips_added'])} trips in {r['overcrowded_window']} and "
                       f"remove {int(r['trips_removed'])} in {r['underutilized_window']}")
        elif r["trips_added"] > 0:
            a.append("Increase frequency")
            why.append(f"overcrowded {r['overcrowded_window']} (peak occupancy {r['peak_occupancy_now']:.0%}); "
                       f"+{int(r['trips_added'])} trips")
        elif r["trips_removed"] > 0:
            a.append("Reduce frequency")
            why.append(f"underutilised {r['underutilized_window']}; -{int(r['trips_removed'])} trips "
                       f"(saves {r['veh_hours_now'] - r['veh_hours_opt']:.1f} veh-h)")
        if r["route_id"] in merge_partner:
            partner, share = merge_partner[r["route_id"]]
            a.append(f"Merge with {partner}")
            why.append(f"{share:.0%} of its stops are also served by {partner} and it is underutilised most hours")
        if r["length_mi"] >= len_p90 and r["reliability"] < rel_med and r["overcrowded_hours_now"] > 0:
            a.append("Split / short-turn")
            why.append(f"long route ({r['length_mi']:.1f} mi) with below-median reliability "
                       f"({r['reliability']:.0%}) and crowding")
        if not a:
            a.append("Maintain")
            why.append("load stays within the balanced band all day")
        actions.append(" + ".join(a))
        reasons.append("; ".join(why))
    rec["action"] = actions
    rec["rationale"] = reasons
    rec["priority"] = (rec["overcrowded_hours_now"] * 2 + rec["underutilized_hours_now"]
                       + rec["action"].str.contains("Merge|Split").astype(int) * 3)
    return rec.sort_values("priority", ascending=False)


def _window(d: pd.DataFrame, mask: pd.Series) -> str:
    """Compress a set of flagged hours into readable spans such as '07-10h, 16-19h'."""
    hrs = sorted(d.loc[mask, "hour"].astype(int).tolist())
    if not hrs:
        return "-"
    spans, start, prev = [], hrs[0], hrs[0]
    for h in hrs[1:] + [None]:
        if h is None or h != prev + 1:
            spans.append(f"{start:02d}-{prev + 1:02d}h")
            if h is not None:
                start = h
        if h is not None:
            prev = h
    return ", ".join(spans[:3]) + (" ..." if len(spans) > 3 else "")


def impact_summary(opt: pd.DataFrame) -> dict:
    """Network-level current vs optimised comparison (evaluation criterion: optimisation effectiveness)."""
    s = opt[opt["trips"] > 0]
    rcol = "est_riders" if "est_riders" in s else "ridership"

    def share(col, cls):
        """Share of service route-hours whose class column equals ``cls``."""
        return float((s[col] == cls).mean())
    return {
        "route_hours": int(len(s)),
        "overcrowded_share_now": share("perf_class", "Overcrowded"),
        "overcrowded_share_opt": share("perf_class_opt", "Overcrowded"),
        "underutilized_share_now": share("perf_class", "Underutilized"),
        "underutilized_share_opt": share("perf_class_opt", "Underutilized"),
        "balanced_share_now": share("perf_class", "Balanced"),
        "balanced_share_opt": share("perf_class_opt", "Balanced"),
        "trips_now": float(s["trips"].sum()), "trips_opt": float(s["trips_opt"].sum()),
        "veh_hours_now": float(s["revenue_hours"].sum()), "veh_hours_opt": float(s["revenue_hours_opt"].sum()),
        "productivity_now": float(s[rcol].sum() / s["revenue_hours"].sum()),
        "productivity_opt": float(s[rcol].sum() / s["revenue_hours_opt"].sum()),
        "mean_wait_now": float(s["avg_wait_min"].mean()), "mean_wait_opt": float(s["avg_wait_min_opt"].mean()),
    }


def simulate_scenario(frame: pd.DataFrame, demand_change_pct: float = 0.0, frequency_multiplier: float = 1.0,
                      speed_change_pct: float = 0.0, capacity_override: float | None = None,
                      routes: list[str] | None = None, hours: tuple[int, int] = (0, 23),
                      ridership_col: str = "ridership") -> pd.DataFrame:
    """What-if simulator. Applies demand growth, frequency scaling, speed change (e.g. bus lanes)
    and/or a bigger vehicle to the selected routes & hours and recomputes every KPI.

    Returns a frame with baseline columns and ``*_sim`` columns side by side.
    """
    f = frame.copy()
    sel = f["hour"].between(*hours)
    if routes:
        sel &= f["route_id"].isin(routes)
    sim = f[[c for c in ("route_id", "hour", "capacity", "trip_minutes", "trips", "evasion_factor") if c in f]].copy()
    sim["ridership"] = f[ridership_col]
    sim.loc[sel, "ridership"] *= 1 + demand_change_pct / 100
    sim.loc[sel & (sim["trips"] > 0), "trips"] = np.maximum(
        np.round(sim.loc[sel & (sim["trips"] > 0), "trips"] * frequency_multiplier), 1)
    sim.loc[sel, "trip_minutes"] /= 1 + speed_change_pct / 100
    if capacity_override:
        sim.loc[sel, "capacity"] = capacity_override
    sim = add_performance_metrics(sim)
    for c in ("ridership", "trips", "capacity", "trip_minutes", "occupancy", "load_per_trip", "productivity",
              "avg_wait_min", "revenue_hours", "perf_class"):
        f[f"{c}_sim"] = sim[c].values
    f["in_scenario"] = sel
    return f
