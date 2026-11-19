"""Stage 5, Step 49: route stop coverage and pairwise stop overlap per geometry version (spec 9.7, 9.8, 9.12).

Geometry version = one GTFS archive (snapshot_id). Within it, a route's served stops are the distinct stop_ids of
its BUS trips whose service is active on at least one of the archive's applied dates (the dates Stage 2 selected
it for), so an outgoing timetable in the same ZIP counts only where it applied. stop_ids stay strings, scoped to
their version. pickup/drop-off types are not filtered (every stop event in stop_times counts as served).

Every count, exclusivity test and identity is keyed by (geometry_version, route) or (geometry_version, stop_id),
so a table holding several versions can never mix their timetables.

Interpretation (spec 4.1, 9.15): corridor review only. Shared stop IDs are not merge/split evidence: there is no
direction, service window, walking access, transfer or journey information here.
"""
from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd

from analytics.reconstruction.gtfs_tables import bus_crosswalk
from analytics.reconstruction.service_calendar import active_service_dates, load_calendar, load_calendar_dates

SEP = ";"
VS = ["geometry_version", "stop_id"]
VR = ["geometry_version", "route"]
INTERPRETATION = ("corridor review only: shared stop IDs are not merge/split evidence (no direction, walking "
                  "access, transfers or journeys)")
OVERLAP_COLUMNS = ["geometry_version", "route_a", "route_b", "route_a_stop_count", "route_b_stop_count",
                   "shared_stop_count", "shared_stop_ids", "jaccard_stop_overlap", "smaller_route_stop_overlap"]


class OverlapError(ValueError):
    pass


def served_stops(con: duckdb.DuckDBPyConnection, snapshot_id: str, applied: list[date]) -> pd.DataFrame:
    """Distinct (route, stop_id) for bus trips active on >= 1 applied date. Creates TEMP TABLE bus_cw."""
    bus_crosswalk(con, snapshot_id)
    active = active_service_dates(load_calendar(con), load_calendar_dates(con), applied)
    services = active[["service_id"]].drop_duplicates()
    con.register("_svc", services)
    try:
        s = con.execute("""
            SELECT DISTINCT cw.route, st.stop_id
            FROM trips t
            JOIN _svc ON _svc.service_id = t.service_id
            JOIN bus_cw cw ON cw.route_id = t.route_id
            JOIN stop_times st ON st.trip_id = t.trip_id
            WHERE st.stop_id IS NOT NULL AND st.stop_id <> ''""").df()
    finally:
        con.unregister("_svc")
    s = s.astype({"route": str, "stop_id": str}).sort_values(["route", "stop_id"]).reset_index(drop=True)
    s.insert(0, "geometry_version", snapshot_id)
    return s


def _routes_per_stop(served: pd.DataFrame) -> pd.Series:
    return served.groupby(VS)["route"].nunique().rename("routes_at_stop")


def coverage(served: pd.DataFrame) -> pd.DataFrame:
    s = served.merge(_routes_per_stop(served).reset_index(), on=VS, how="left", validate="many_to_one")
    s["exclusive"] = s["routes_at_stop"].eq(1)  # exclusive WITHIN its own version only
    rows = []
    for (ver, route), g in s.groupby(VR, sort=True):
        stops, excl = sorted(g["stop_id"]), sorted(g.loc[g["exclusive"], "stop_id"])
        rows.append({"geometry_version": ver, "route": route, "served_stop_count": len(stops),
                     "served_stop_ids": SEP.join(stops), "exclusive_stop_count": len(excl),
                     "exclusive_stop_ids": SEP.join(excl), "exclusive_stop_fraction": len(excl) / len(stops)})
    return pd.DataFrame(rows)


def overlap(served: pd.DataFrame) -> pd.DataFrame:
    """One row per unordered route pair (route_a < route_b as strings) sharing at least one stop, per version."""
    counts = served.groupby(VR)["stop_id"].nunique()  # keyed by (version, route)
    pairs = served.merge(served, on=VS, suffixes=("_a", "_b"))  # same version AND same stop
    pairs = pairs[pairs["route_a"] < pairs["route_b"]]
    rows = []
    for (ver, a, b), g in pairs.groupby(["geometry_version", "route_a", "route_b"], sort=True):
        shared = sorted(g["stop_id"].unique())
        na, nb, k = int(counts[(ver, a)]), int(counts[(ver, b)]), len(shared)
        rows.append({"geometry_version": ver, "route_a": a, "route_b": b, "route_a_stop_count": na,
                     "route_b_stop_count": nb, "shared_stop_count": k, "shared_stop_ids": SEP.join(shared),
                     "jaccard_stop_overlap": k / (na + nb - k), "smaller_route_stop_overlap": k / min(na, nb)})
    out = pd.DataFrame(rows, columns=OVERLAP_COLUMNS)
    out["overlap_review_rank"] = (out.groupby("geometry_version")["jaccard_stop_overlap"]
                                  .rank(method="min", ascending=False).astype("Int64"))
    out["interpretation"] = INTERPRETATION
    return out


def _version_stop_set(cov: pd.DataFrame, column: str) -> set[tuple[str, str]]:
    return {(v, s) for v, ids in zip(cov["geometry_version"], cov[column]) for s in ids.split(SEP) if s}


def verify(served: pd.DataFrame, cov: pd.DataFrame, ov: pd.DataFrame) -> dict:
    """Identities that must hold (all keyed by version); any failure stops the build."""
    all_stops = set(zip(served["geometry_version"], served["stop_id"]))
    exclusive = _version_stop_set(cov, "exclusive_stop_ids")
    per_stop = _routes_per_stop(served)
    shared = set(per_stop[per_stop >= 2].index)
    served_rows = served.groupby("geometry_version").size()
    cov_rows = cov.groupby("geometry_version")["served_stop_count"].sum()
    checks = {
        "every stop exclusive or shared within its version, never both":
            exclusive | shared == all_stops and not exclusive & shared,
        "jaccard within [0, 1]": bool(ov["jaccard_stop_overlap"].between(0, 1).all()),
        "shared <= smaller route's count": bool((ov["shared_stop_count"] <=
                                                 ov[["route_a_stop_count", "route_b_stop_count"]].min(axis=1)).all()),
        "one row per unordered pair per version": not ov.duplicated(["geometry_version", "route_a", "route_b"]).any()
                                                  and bool((ov["route_a"] < ov["route_b"]).all()),
        "coverage counts equal served rows, per version": bool(cov_rows.reindex(served_rows.index).eq(served_rows).all()),
    }
    if not all(checks.values()):
        raise OverlapError(f"overlap identities failed: {[k for k, v in checks.items() if not v]}")
    return checks


def version_tables(con: duckdb.DuckDBPyConnection, snapshot_id: str, applied: list[date]) -> dict:
    served = served_stops(con, snapshot_id, applied)
    if served.empty:
        raise OverlapError(f"{snapshot_id}: no bus stops served on its applied dates")
    cov, ov = coverage(served), overlap(served)
    return {"served": served, "coverage": cov, "overlap": ov, "checks": verify(served, cov, ov)}
