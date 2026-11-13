"""Step 15: archive integrity / timetable regimes (spec 9.6.5) and light descriptive summaries (9.6.2, 9.6.4.2-3).

These are checks and descriptions only. They never change the selected daily schedule.
"""
from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd


# ----------------------------------------------------------------------------- per-snapshot fingerprints
def bus_payload_fingerprint(con: duckdb.DuckDBPyConnection) -> dict:
    """Order-independent content fingerprint of bus trip records and bus stop events (needs bus_cw)."""
    trips = con.execute("""SELECT count(*), coalesce(sum(hash(t.trip_id, t.route_id, t.service_id)::HUGEINT), 0)
                           FROM trips t JOIN bus_cw USING (route_id)""").fetchone()
    events = con.execute("""SELECT count(*), coalesce(sum(hash(st.trip_id, st.stop_id, st.stop_sequence,
                                   st.arrival_time, st.departure_time)::HUGEINT), 0)
                            FROM stop_times st JOIN trips t USING (trip_id) JOIN bus_cw USING (route_id)""").fetchone()
    return {"bus_trips": int(trips[0]), "bus_trips_hash": str(trips[1]),
            "bus_stop_events": int(events[0]), "bus_stop_events_hash": str(events[1])}


def bus_calendar_regimes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Distinct calendar.txt validity ranges used by bus trips (outgoing/incoming timetables show up here)."""
    rows = con.execute("""
        SELECT c.start_date, c.end_date, count(DISTINCT c.service_id) AS services, count(t.trip_id) AS trips
        FROM calendar c JOIN trips t USING (service_id) JOIN bus_cw USING (route_id)
        GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
    return [{"start_date": s, "end_date": e, "services": int(n), "bus_trips": int(k)} for s, e, n, k in rows]


def regimes_disjoint(regimes: list[dict]) -> bool:
    rs = sorted((r["start_date"], r["end_date"]) for r in regimes)
    return all(a[1] < b[0] for a, b in zip(rs, rs[1:]))


# ----------------------------------------------------------------------------- same-date overlap comparison
def compare_overlap(older: pd.DataFrame, newer: pd.DataFrame, older_id: str, newer_id: str,
                    dates: list[date]) -> dict:
    """Compare two snapshots' calculated daily service on the same dates (route/date trips and hours)."""
    o = older[older["date"].isin(dates)]
    n = newer[newer["date"].isin(dates)]
    both_dates = sorted(set(o["date"]) & set(n["date"]))
    o, n = o[o["date"].isin(both_dates)], n[n["date"].isin(both_dates)]
    m = o.merge(n, on=["route", "date"], how="outer", suffixes=("_old", "_new"), indicator=True)
    both = m[m["_merge"] == "both"]
    hours_diff = ((both["scheduled_service_hours_old"].astype("Float64")
                   - both["scheduled_service_hours_new"].astype("Float64")).abs() > 1e-6).fillna(True)
    trip_diff = both["scheduled_trips_old"] != both["scheduled_trips_new"]
    diff_dates = set(both.loc[(hours_diff | trip_diff).to_numpy(dtype=bool), "date"])
    diff_dates |= set(m.loc[m["_merge"] != "both", "date"])
    return {
        "dates_with_differences": [str(d) for d in sorted(diff_dates)],
        "older": older_id, "newer": newer_id,
        "dates_probed": [str(d) for d in dates], "dates_both_define_service": [str(d) for d in both_dates],
        "route_dates_compared": int(len(both)),
        "route_dates_only_older": int((m["_merge"] == "left_only").sum()),
        "route_dates_only_newer": int((m["_merge"] == "right_only").sum()),
        "trip_count_differences": int(trip_diff.sum()),
        "hours_differences": int(hours_diff.sum()),
    }


def newer_only_regime_starts(older_regimes: list[dict], newer_regimes: list[dict]) -> list[str]:
    """Start dates of bus calendar ranges that exist only in the newer archive (a timetable the older one lacks)."""
    old = {(r["start_date"], r["end_date"]) for r in older_regimes}
    return sorted({f"{r['start_date'][:4]}-{r['start_date'][4:6]}-{r['start_date'][6:]}"
                   for r in newer_regimes if (r["start_date"], r["end_date"]) not in old})


def explain_overlap(o: dict, newer_starts: list[str]) -> str:
    """Classify an overlap result. Differences confined to dates on/after a newer-only timetable start are a
    genuine timetable change visible only in the newer archive, not a reconstruction disagreement."""
    if not o["dates_both_define_service"]:
        return "no common dates"
    if not o["dates_with_differences"]:
        return "no differences"
    first_diff = min(o["dates_with_differences"])
    start = max((s for s in newer_starts if s <= first_diff), default=None)  # timetable in force at first diff
    if start is not None:
        same = [d for d in o["dates_both_define_service"] if d < start]
        return (f"differences only from {start} (start of a timetable present only in the newer archive); "
                f"{len(same)} earlier common date(s) agree")
    return "UNEXPLAINED differences"


# ----------------------------------------------------------------------------- ridership descriptions
def window_summary(rides: pd.DataFrame, start: date, end: date) -> dict:
    w = rides[(rides["date"] >= start) & (rides["date"] <= end)]
    return {"start": str(start), "end": str(end), "records": len(w), "route_identifiers": w["route"].nunique(),
            "calendar_dates": w["date"].nunique(), "rides_sum": int(w["rides"].sum())}


def route_window(rides: pd.DataFrame, route: str, start: date, end: date) -> dict:
    w = rides[(rides["route"] == route) & (rides["date"] >= start) & (rides["date"] <= end)]
    return {"route": route, "records": len(w), "rides": int(w["rides"].sum()) if len(w) else 0}


def route_name_presence(rides: pd.DataFrame, start: date, end: date, routes: set[str]) -> dict:
    w = rides[(rides["date"] >= start) & (rides["date"] <= end)]
    inside = w["route"].isin(routes)
    return {"records": len(w), "records_with_route_in_archives": int(inside.sum()),
            "pct": round(100 * inside.mean(), 2) if len(w) else None,
            "absent_identifiers": sorted(w.loc[~inside, "route"].unique().tolist())}


def monthly_record_days(rides: pd.DataFrame, routes: list[str], year: int, months: list[int]) -> pd.DataFrame:
    rows = []
    for mth in months:
        days = pd.Period(f"{year}-{mth:02d}").days_in_month
        r = {"month": f"{year}-{mth:02d}", "calendar_days": days}
        for route in routes:
            sel = rides[(rides["route"] == route)
                        & rides["date"].map(lambda d: d.year == year and d.month == mth)]
            r[f"route_{route}_record_days"] = sel["date"].nunique()
        rows.append(r)
    return pd.DataFrame(rows)


def monthly_coverage(rides: pd.DataFrame) -> pd.DataFrame:
    """Records, routes and day-type mix per month (descriptive record availability, not completeness)."""
    df = rides.assign(month=rides["date"].map(lambda d: f"{d.year}-{d.month:02d}"))
    g = df.groupby("month")
    out = pd.DataFrame({"records": g.size(), "routes": g["route"].nunique(), "dates": g["date"].nunique(),
                        "rides": g["rides"].sum()})
    dt = df.pivot_table(index="month", columns="daytype", values="route", aggfunc="size", fill_value=0)
    return out.join(dt.add_prefix("daytype_")).reset_index()
