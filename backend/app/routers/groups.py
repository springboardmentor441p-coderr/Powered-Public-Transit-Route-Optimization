"""GET /api/route-groups: the Stage 5 route groups (spec 9.17.3 "group summaries, period, model version and
memberships"; 9.16.2 "similar group").

Summaries are recomputed from the imported route_profiles by Stage 5's own clustering.group_summary, so they equal
reports/stage5_group_summary.csv. All caveats are returned, always. Ungrouped routes come with their reasons.
The groups were fitted on the development period; under a cutoff before its end they are not shown (200 with
available = false and the reason, so the screen can say why). The k table (silhouette, stability) is not imported;
the response points to the Stage 5 report for it.

`route_values` (Stage 6c) carries every profiled route's own values for the "Alike" scatter: missing -> null with a
reason (route 169's weekend ratios), structural zero -> 0 with status no_scheduled_service. Hidden with the groups
under an early cutoff.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import psycopg
from fastapi import APIRouter, Depends, Query

from analytics.groups.clustering import group_summary
from backend.app.db import GROUPS_AFTER_CUTOFF, cutoff_block, get_conn, group_version_for, permitted_through, \
    resolve_version
from backend.app.db import request_cutoff
from backend.app.labels import UNITS, envelope, prose
from backend.app.routers.rankings import CFG

router = APIRouter(tags=["groups"])
FEATURE_UNITS = {  # original units for the summary columns
    "mean_weekday_rides": UNITS["rides"], "weekday_rides_cv": "coefficient of variation (weekday rides)",
    "saturday_to_weekday_rides_ratio": "Saturday rides / weekday rides",
    "sunday_holiday_to_weekday_rides_ratio": "Sunday/holiday rides / weekday rides",
    "mean_weekday_scheduled_trips": UNITS["scheduled_trips"],
    "weekday_rides_per_scheduled_hour": UNITS["rides_per_scheduled_hour"],
    "mean_weekday_trip_duration_minutes": "minutes per scheduled trip",
}
FEATURE_LABELS = {  # plain names for the screens; the keys above stay for machines
    "mean_weekday_rides": "Average weekday rides",
    "weekday_rides_cv": "Weekday ride variability",
    "saturday_to_weekday_rides_ratio": "Saturday level vs weekday",
    "sunday_holiday_to_weekday_rides_ratio": "Sunday/holiday level vs weekday",
    "mean_weekday_scheduled_trips": "Weekday scheduled trips",
    "weekday_rides_per_scheduled_hour": "Weekday rides per scheduled hour",
    "mean_weekday_trip_duration_minutes": "Average weekday trip length",
}
K_TABLE_NOTE = "k table (silhouette, stability, half-period agreement): Stage 5 report, section 4"
STATUSES = ("available", "no_scheduled_service", "insufficient_observations")
WEEKEND = {"saturday_to_weekday_rides_ratio": ("saturday", "Saturday"),
           "sunday_holiday_to_weekday_rides_ratio": ("sunday_holiday", "Sunday/holiday")}
VALUES_NOTE = ("each route's own development-period profile value. A missing value is shown as missing, with its reason: it is "
               "never 0 and never the median the clustering filled in. A structural zero (no scheduled service) is 0.")


def profile_value(p: dict, feature: str) -> dict:
    """One stored profile value with its status. Read from route_profiles, never from the clustering input, so a
    value the clustering filled with a median comes back as null with its reason."""
    v = p[feature]
    if feature in WEEKEND:
        key, name = WEEKEND[feature]
        status = p[f"{key}_service_status"]
        if status == "no_scheduled_service":
            return {"value": 0.0, "status": status,
                    "reason": f"no scheduled {name} service: a structural zero (no buses ran), not a missing value"}
        if status == "insufficient_observations" or v is None:
            gate = CFG["gates"]["cluster_min_weekend_days"]
            return {"value": None, "status": "insufficient_observations",
                    "reason": f"unavailable: {p[f'{key}_observed_days']} matched {name} days of "
                              f"{p[f'{key}_scheduled_days']} scheduled (fewer than {gate})"}
        return {"value": float(v), "status": "available", "reason": None}
    if v is None:
        return {"value": None, "status": "unavailable", "reason": "unavailable in the stored development profile"}
    return {"value": float(v), "status": "available", "reason": None}


@router.get("/api/route-groups")
def route_groups(cutoff: date | None = Depends(request_cutoff),
                 data_version: str | None = None, conn: psycopg.Connection = Depends(get_conn)) -> dict:
    v = resolve_version(conn, data_version)
    through = permitted_through(v, cutoff)
    gv = group_version_for(conn, v["data_version"], through)
    if gv is None:
        return envelope(v, cutoff_block(v, cutoff), available=False, reason=GROUPS_AFTER_CUTOFF)
    g = conn.execute("""SELECT group_version, artifact_version, artifact_sha256, profile_start, profile_end, k,
                               features, group_names, caveats, built_git_commit
                        FROM group_versions WHERE group_version = %s""", (gv["group_version"],)).fetchone()
    profile_rows = conn.execute("SELECT * FROM route_profiles WHERE group_version = %s ORDER BY route",
                                (g["group_version"],)).fetchall()
    prof = pd.DataFrame(profile_rows)
    members = conn.execute("""SELECT route, group_id, group_name, reason FROM group_memberships
                              WHERE group_version = %s ORDER BY route""", (g["group_version"],)).fetchall()
    labels = pd.Series({m["route"]: m["group_id"] for m in members if m["group_id"] is not None}, dtype="int64")
    summary = group_summary(prof, labels, CFG)  # Stage 5's own function
    selected = g["features"]
    features = CFG["clustering"]["candidates_in_priority_order"]
    group_of = {m["route"]: m["group_id"] for m in members}
    route_values = [
        {"route": p["route"], "group_id": group_of.get(p["route"]),
         "weekday_observed_days": int(p["weekday_observed_days"]),
         "values": [{"feature": f, "label": FEATURE_LABELS[f], "unit": FEATURE_UNITS[f], **profile_value(p, f)}
                    for f in features]}
        for p in profile_rows]
    groups = []
    for row in summary.to_dict("records"):
        gid = int(row["group"])
        groups.append({
            "group_id": gid, "name": g["group_names"][str(gid)], "size": int(row["routes"]),
            "routes": sorted(labels.index[labels == gid]),
            "features": [{"feature": f, "label": FEATURE_LABELS[f], "unit": FEATURE_UNITS[f],
                          "selected_for_clustering": f in selected,
                          **{s: float(row[f"{f}_{s}"]) for s in ("median", "mean", "min", "max")}}
                         for f in CFG["clustering"]["candidates_in_priority_order"]],
            "weekend_service": {f"{n}_{s}": int(row[f"{n}_{s}"]) for n in ("saturday", "sunday_holiday")
                                for s in STATUSES},
        })
    return envelope(
        v, cutoff_block(v, cutoff), available=True,
        group_version=g["group_version"], artifact_version=g["artifact_version"],
        artifact_sha256=g["artifact_sha256"], built_git_commit=g["built_git_commit"],
        profile_period={"start": g["profile_start"], "end": g["profile_end"],
                        "note": "groups describe what a route is like over this period; fitted once, then frozen"},
        method={"k": g["k"], "selected_features": selected,
                "selected_feature_labels": [FEATURE_LABELS[f] for f in selected], "algorithm": "KMeans on standardised features",
                "k_rule": prose(CFG["clustering"]["_k_rule"]), "k_table": K_TABLE_NOTE},
        caveats=[prose(c) for c in g["caveats"]],
        groups=groups,
        ungrouped=[{"route": m["route"], "reason": m["reason"]} for m in members if m["group_id"] is None],
        route_values_note=VALUES_NOTE, route_values=route_values,
    )
