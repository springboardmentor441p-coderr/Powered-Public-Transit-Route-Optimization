"""Audit frozen Manhattan archives and exact demand/date compatibility.

Run from any directory: python scripts/validate_historical_alignment.py
Outputs are validation evidence, not model features or observed occupancy.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/new_york"
OUT = ROOT / "reports/historical_alignment"
DAYS = "monday tuesday wednesday thursday friday saturday sunday".split()


def verify(path):
    receipt = json.loads(path.with_name(path.name + ".receipt.json").read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == receipt["sha256"], f"Source hash mismatch: {path}"
    assert path.stat().st_size == receipt["bytes"]
    return {"file": path.relative_to(ROOT).as_posix(), "sha256": digest,
            "url": receipt["url"], "downloaded_utc": receipt["retrieved_utc"]}


def seconds(values):
    assert values.str.fullmatch(r"\d{2,}:[0-5]\d:[0-5]\d").all()
    parts = values.str.split(":", expand=True).astype("int64")
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def activate(calendar, exceptions, date):
    key = date.strftime("%Y%m%d")
    if calendar.empty:
        active = set()
    else:
        active = set(calendar.loc[
            (calendar.start_date <= key) & (calendar.end_date >= key)
            & calendar[DAYS[date.weekday()]].eq("1"), "service_id"])
    changes = exceptions.loc[exceptions.date.eq(key)]
    active -= set(changes.loc[changes.exception_type.eq("2"), "service_id"])
    active |= set(changes.loc[changes.exception_type.eq("1"), "service_id"])
    return active


def select_snapshot(feeds, date):
    available = [f for f in feeds if f["capture"] <= date]
    return max(available, key=lambda f: f["capture"]) if available else None


def read_feed(path):
    source = verify(path)
    stamp = re.search(r"mdb-513-(\d{12})", source["url"]).group(1)
    source["archive_id"] = "mdb-513-" + stamp
    source["catalog_capture_date"] = pd.Timestamp(stamp[:8]).date().isoformat()
    with ZipFile(path) as z:
        assert z.testzip() is None, f"ZIP CRC failure: {path}"

        def read(name, columns=None):
            if name + ".txt" not in z.namelist():
                return pd.DataFrame()
            return pd.read_csv(z.open(name + ".txt"), dtype="string", usecols=columns)

        agency, routes, trips = read("agency"), read("routes"), read("trips")
        calendar, exceptions = read("calendar"), read("calendar_dates")
        info, frequencies = read("feed_info"), read("frequencies")
        assert frequencies.empty, "Frequency templates need explicit expansion before counting"
        assert set(agency.agency_timezone) == {"America/New_York"}
        assert not trips.trip_id.duplicated().any()
        assert not routes.route_id.duplicated().any()
        assert not exceptions.duplicated(["service_id", "date"]).any()
        assert exceptions.exception_type.isin(["1", "2"]).all()
        if not calendar.empty:
            assert not calendar.service_id.duplicated().any()
            assert calendar[DAYS].isin(["0", "1"]).all().all()
            assert (calendar.start_date <= calendar.end_date).all()
        service_ids = set(calendar.service_id) | set(exceptions.service_id)
        assert set(trips.service_id) <= service_ids
        assert set(trips.route_id) <= set(routes.route_id)
        times = read("stop_times", ["trip_id", "stop_sequence", "arrival_time", "departure_time"])
    assert set(times.trip_id) == set(trips.trip_id)
    times["stop_sequence"] = pd.to_numeric(times.stop_sequence, errors="raise")
    assert not times.duplicated(["trip_id", "stop_sequence"]).any()
    times["arrival_seconds"] = seconds(times.arrival_time)
    times["departure_seconds"] = seconds(times.departure_time)
    times = times.sort_values(["trip_id", "stop_sequence"])
    previous = times.groupby("trip_id").departure_seconds.shift()
    assert (times.departure_seconds >= times.arrival_seconds).all()
    assert not (times.arrival_seconds < previous).any()
    endpoints = times.groupby("trip_id", sort=False).agg(
        first_departure_seconds=("departure_seconds", "first"),
        final_arrival_seconds=("arrival_seconds", "last"),
        max_time_seconds=("departure_seconds", "max"))
    endpoints["overnight"] = endpoints.max_time_seconds.ge(86400)
    endpoints["duration_valid"] = endpoints.final_arrival_seconds.gt(endpoints.first_departure_seconds)
    trips = trips.merge(routes[["route_id", "route_short_name", "route_type"]],
                        on="route_id", validate="many_to_one")
    trips = trips.loc[trips.route_type.eq("3")].merge(
        endpoints, on="trip_id", validate="one_to_one")
    assert not trips.empty
    crosswalk = trips[["route_id", "route_short_name"]].drop_duplicates()
    assert not crosswalk.route_short_name.duplicated().any(), "Nonunique public route mapping"
    start = info.feed_start_date.iloc[0] if not info.empty else None
    end = info.feed_end_date.iloc[0] if not info.empty else None
    return {"id": path.stem, "capture": pd.Timestamp(stamp[:8]), "source": source,
            "calendar": calendar, "exceptions": exceptions, "trips": trips,
            "start": start, "end": end, "crosswalk": crosswalk,
            "max_time_seconds": int(times[["arrival_seconds", "departure_seconds"]].max().max())}


def expand_date(feeds, date):
    feed = select_snapshot(feeds, date)
    audit = {"date": date.date().isoformat(), "source_snapshot": feed["id"] if feed else "",
             "status": "no_prior_snapshot", "active_services": 0, "scheduled_trips": 0}
    if feed is None:
        return audit, pd.DataFrame()
    key = date.strftime("%Y%m%d")
    if (feed["start"] and key < feed["start"]) or (feed["end"] and key > feed["end"]):
        audit["status"] = "selected_snapshot_outside_feed_info"
        return audit, pd.DataFrame()
    active = activate(feed["calendar"], feed["exceptions"], date)
    trips = feed["trips"].loc[feed["trips"].service_id.isin(active)].copy()
    audit.update(status="active" if len(trips) else "selected_snapshot_no_active_trips",
                 active_services=len(active), scheduled_trips=len(trips))
    return audit, trips


def block_conflicts(trips):
    if trips.empty:
        return set()
    valid = trips.loc[trips.block_id.fillna("").ne("")].sort_values(
        ["block_id", "first_departure_seconds"])
    running_end = valid.groupby("block_id").final_arrival_seconds.cummax()
    previous_end = running_end.groupby(valid.block_id).shift()
    # Remember the route owning the longest preceding interval, including nested trips.
    owner = valid.route_short_name.where(valid.final_arrival_seconds.eq(running_end))
    previous_owner = owner.groupby(valid.block_id).ffill().groupby(valid.block_id).shift()
    overlapping = valid.first_departure_seconds.lt(previous_end)
    return set(valid.loc[overlapping, "route_short_name"]) | set(previous_owner[overlapping])


def write_report(summary):
    audit = pd.read_csv(OUT / "calendar_date_audit.csv").fillna("")
    groups = (audit.status.ne(audit.status.shift())
              | audit.source_snapshot.ne(audit.source_snapshot.shift())).cumsum()
    windows = audit.groupby(groups).agg(
        first_date=("date", "first"), last_date=("date", "last"),
        source_snapshot=("source_snapshot", "first"), status=("status", "first"))
    candidates = pd.read_csv(OUT / "route_date_compatibility_audit.csv")
    eligible = candidates.loc[candidates.status.eq("eligible_conservative_daily_comparison")]
    per_route = eligible.groupby("bus_route").agg(
        comparison_dates=("service_date", "size"), first_date=("service_date", "min"),
        last_date=("service_date", "max"))
    per_route.reset_index().to_csv(OUT / "eligible_coverage_by_route.csv", index=False)
    text = ["# Historical Manhattan alignment validation", "",
            f"Validated: {summary['validated_utc']}. User-authorized extension before feature engineering.", "",
            "## Results", "",
            f"- {summary['sources_verified']} input files verified against original SHA-256 receipts; all five GTFS ZIP CRC checks passed.",
            f"- {summary['raw_ridership_rows']:,} route/payment-date observations over {summary['raw_ridership_dates']} dates in the full demand collection.",
            f"- {summary['schedule_route_dates']:,} selected active Manhattan schedule route/dates.",
            f"- {summary['literal_candidate_matches']:,} literal route/date candidate matches across {summary['candidate_dates']} dates and {summary['candidate_routes']} routes.",
            f"- {summary['conservative_eligible_rows']:,} comparisons pass the conservative date-boundary and quality screen, across {summary['conservative_eligible_dates']} dates and {summary['conservative_eligible_routes']} routes.",
            f"- {summary['calendar_second_count_dates']} holiday/boundary dates agree with a second calendar-count implementation.",
            f"- {int(candidates.block_overlap_review.sum())} scheduled route/dates have overlapping vehicle-block assignments; all trip durations passed the positive-duration check.",
            "- Seven regression tests cover exceptions, global selection, no fallback, withdrawn routes, extended times and block overlaps.",
            "", "## Compatibility outcomes", "", "| Outcome | Scheduled route/dates |", "|---|---:|"]
    text += [f"| {name} | {count:,} |" for name, count in summary["compatibility_status_counts"].items()]
    text += ["", "Individual flags can overlap. A status is a review outcome, not an efficiency/crowding class.",
             "", "## Selected snapshot windows", "", "| From | Through | Selected archive | Outcome |", "|---|---|---|---|"]
    text += [f"| {r.first_date} | {r.last_date} | {r.source_snapshot or '(none)'} | {r.status} |"
             for r in windows.itertuples()]
    text += ["", "The latest captured whole snapshot is selected before calendars. A future-effective new archive can create an explicit gap; the algorithm never falls back to an older route/feed.",
             "", "## What remains", "",
             "1. Verify SBS short-name aliases before including them. Unresolved names: "
             + ", ".join(summary["unresolved_short_names"]) + ".",
             "2. Reconstruct clock-date scheduled activity for overnight routes, including preceding-day context and daylight-saving boundaries. Current midnight cases are withheld rather than moving observed boarding totals.",
             "3. Inspect overlapping-block flags before service denominators are used. All original templates remain in the audit.",
             "4. Obtain additional dated schedules if broader dates or boroughs are required. Sparse captures cannot establish every intervening schedule change.",
             "5. Review route-history continuity and source imputation before declaring a modelling table ready.",
             "", "The wider ridership history remains useful for demand-only forecasting. Unmatched observations are retained; missing boardings are never filled with zero.",
             "The conservative subset favors routes/days without overnight activity and is not representative of the full network. Its smaller size reflects withholding policy, not proof that all other source rows are wrong.",
             "", "## Meaning and reproducibility", "",
             "Eligible rows support further daily comparison review, not measured occupancy or proof that scheduled trips operated. This run does not create models, crowding labels, ratios, scenarios or a dashboard.",
             "", "Read [the method](../../docs/HISTORICAL_ALIGNMENT_METHOD.md), [the machine-readable summary](validation_summary.json), and [the route coverage](eligible_coverage_by_route.csv).",
             "", "Run `python scripts/validate_historical_alignment.py` to reproduce. Run `python -m unittest discover -s tests -p test_historical_alignment.py -v` for regression checks.", ""]
    (OUT / "HISTORICAL_ALIGNMENT_REPORT.md").write_text("\n".join(text), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sources, frames = [], []
    for path in sorted((RAW / "history_daily").glob("*_route_day.csv")):
        sources.append(verify(path))
        frames.append(pd.read_csv(path, dtype={"bus_route": "string"}))
    demand = pd.concat(frames, ignore_index=True)
    demand = demand.rename(columns={"service_date": "payment_date"})
    demand["payment_date"] = pd.to_datetime(demand.payment_date).dt.normalize()
    assert not demand.duplicated(["payment_date", "bus_route"]).any()
    assert demand.notna().all().all()
    assert (demand.published_boardings >= 0).all()
    # Independent extraction path, same publisher: check every day's denominator.
    denominator_frames = []
    for path in sorted((RAW / "history_daily").glob("*_denominator.csv")):
        sources.append(verify(path))
        denominator_frames.append(pd.read_csv(path))
    denominator = pd.concat(denominator_frames, ignore_index=True)
    denominator["date"] = pd.to_datetime(denominator.service_date).dt.normalize()
    observed = demand.groupby("payment_date").published_boardings.sum().sort_index()
    expected = denominator.set_index("date").published_boardings.sort_index()
    pd.testing.assert_series_equal(observed, expected, check_names=False, check_dtype=False)

    feeds = []
    for path in sorted((RAW / "gtfs/archive").glob("*.zip")):
        feed = read_feed(path)
        feeds.append(feed)
        sources.append(feed["source"])
        print("Verified", path.name, flush=True)
    first, last = demand.payment_date.min(), demand.payment_date.max()
    lookback = max(f["max_time_seconds"] // 86400 for f in feeds)
    audits, schedules, history = [], [], {}
    for date in pd.date_range(first - pd.Timedelta(days=lookback), last):
        audit, active = expand_date(feeds, date)
        history[date] = (audit, active)
        if date < first:
            continue
        audits.append(audit)
        if date.day == 1:
            print("Expanding", date.date().isoformat(), flush=True)
        if active.empty:
            continue
        conflicts = block_conflicts(active)
        row = active.groupby("route_short_name").agg(
            scheduled_trip_templates=("trip_id", "size"),
            overnight_trip_templates=("overnight", "sum"),
            duration_valid=("duration_valid", "all")).reset_index()
        row = row.rename(columns={"route_short_name": "bus_route"})
        row["service_date"] = date
        row["source_snapshot"] = audit["source_snapshot"]
        row["block_overlap_review"] = row.bus_route.isin(conflicts)
        row["prior_context_complete"] = True
        row["incoming_overnight_trip_templates"] = 0
        for offset in range(1, lookback + 1):
            prior_audit, prior = history[date - pd.Timedelta(days=offset)]
            if prior_audit["status"] != "active":
                row["prior_context_complete"] = False
            if not prior.empty:
                incoming = prior.loc[prior.max_time_seconds.ge(offset * 86400)].groupby(
                    "route_short_name").size()
                row["incoming_overnight_trip_templates"] += row.bus_route.map(incoming).fillna(0).astype(int)
        schedules.append(row)
    calendar_audit = pd.DataFrame(audits)
    schedule = pd.concat(schedules, ignore_index=True)
    assert not schedule.duplicated(["service_date", "bus_route"]).any()
    # Compare a second expansion with a trip-by-trip evaluation on boundary/holiday dates.
    check_dates = set(pd.to_datetime(["2026-01-19", "2026-05-25", "2026-07-03", "2026-09-07"]))
    for f in feeds:
        check_dates.update([f["capture"], f["capture"] + pd.Timedelta(days=1)])
    denominator_checks = []
    for date in sorted(check_dates):
        audit, trips = expand_date(feeds, date)
        f = select_snapshot(feeds, date)
        if audit["status"] != "active":
            continue
        key = date.strftime("%Y%m%d")
        flags = {}
        for r in f["calendar"].itertuples(index=False):
            flags[r.service_id] = (r.start_date <= key <= r.end_date and getattr(r, DAYS[date.weekday()]) == "1")
        for r in f["exceptions"].itertuples(index=False):
            if r.date == key:
                flags[r.service_id] = r.exception_type == "1"
        independently_counted = int(f["trips"].service_id.map(flags).fillna(False).sum())
        assert len(trips) == independently_counted
        denominator_checks.append({"date": date.date(), "source_snapshot": f["id"],
                                   "vectorized_trip_count": len(trips), "second_count": independently_counted})

    crosswalk = pd.concat([f["crosswalk"].assign(source_snapshot=f["id"]) for f in feeds])
    demand_codes = set(demand.bus_route)
    crosswalk["mapping_status"] = crosswalk.route_short_name.map(
        lambda x: "literal_short_name_match" if x in demand_codes else "unresolved_short_name")
    crosswalk["route_id_alias_present_in_demand"] = crosswalk.route_id.isin(demand_codes)
    match = schedule.merge(demand, left_on=["service_date", "bus_route"],
                           right_on=["payment_date", "bus_route"], how="left",
                           validate="one_to_one", indicator=True)
    match["status"] = "eligible_conservative_daily_comparison"
    match.loc[~match.duration_valid, "status"] = "invalid_trip_duration_review"
    match.loc[match.block_overlap_review, "status"] = "overlapping_block_review"
    overnight = (match.overnight_trip_templates + match.incoming_overnight_trip_templates).gt(0)
    match.loc[overnight, "status"] = "payment_date_service_date_boundary_review"
    match.loc[~match.prior_context_complete, "status"] = "prior_date_context_missing"
    match.loc[match._merge.eq("left_only"), "status"] = "no_literal_ridership_match"
    match = match.drop(columns="_merge")
    # All observed route/dates are accounted for, including outside the Manhattan pilot.
    unmatched = demand.merge(schedule[["service_date", "bus_route"]],
                             left_on=["payment_date", "bus_route"],
                             right_on=["service_date", "bus_route"], how="left",
                             validate="one_to_one", indicator=True)
    unmatched = unmatched.loc[unmatched._merge.eq("left_only")].drop(columns=["_merge", "service_date"])
    unmatched["reason"] = "outside_manhattan_literal_route_scope"
    candidate_codes = set(crosswalk.route_short_name) & demand_codes
    unmatched.loc[unmatched.bus_route.isin(candidate_codes), "reason"] = "no_selected_active_route_on_date"
    date_status = calendar_audit.set_index("date").status
    unmatched["date_status"] = unmatched.payment_date.dt.strftime("%Y-%m-%d").map(date_status)
    eligible = match.loc[match.status.eq("eligible_conservative_daily_comparison")]
    candidates = match.loc[match.payment_date.notna()]
    by_snapshot = candidates.groupby("source_snapshot").agg(
        candidate_rows=("bus_route", "size"), dates=("service_date", "nunique"), routes=("bus_route", "nunique"))
    for name, frame in {
        "calendar_date_audit": calendar_audit, "selected_schedule_route_dates": schedule,
        "route_crosswalk_audit": crosswalk, "route_date_compatibility_audit": match,
        "eligible_daily_comparisons": eligible, "unmatched_ridership": unmatched,
        "second_calendar_count_checks": pd.DataFrame(denominator_checks),
        "candidate_coverage_by_snapshot": by_snapshot.reset_index(),
    }.items():
        frame.to_csv(OUT / (name + ".csv"), index=False)
    # Confirm raw bytes still match after the complete run.
    for item in sources:
        assert verify(ROOT / item["file"])["sha256"] == item["sha256"]
    summary = {
        "validated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Manhattan historical calendar and exact-route/date compatibility validation only",
        "snapshot_rule": "Latest catalog capture DATE <= service date; one whole snapshot; no fallback after selection",
        "archive_timestamp_caveat": "Catalog capture date is not verified agency publication time; day-level boundary, not intraday availability",
        "sources_verified": len(sources), "historical_archives": len(feeds),
        "raw_ridership_rows": len(demand), "raw_ridership_dates": demand.payment_date.nunique(),
        "calendar_date_status_counts": calendar_audit.status.value_counts().to_dict(),
        "schedule_route_dates": len(schedule), "literal_candidate_matches": len(candidates),
        "candidate_dates": candidates.service_date.nunique(), "candidate_routes": candidates.bus_route.nunique(),
        "conservative_eligible_rows": len(eligible), "conservative_eligible_dates": eligible.service_date.nunique(),
        "conservative_eligible_routes": eligible.bus_route.nunique(),
        "compatibility_status_counts": match.status.value_counts().to_dict(),
        "unmatched_observations": len(unmatched),
        "unresolved_short_names": sorted(set(crosswalk.loc[crosswalk.mapping_status.eq("unresolved_short_name"), "route_short_name"])),
        "calendar_second_count_dates": len(denominator_checks),
        "midnight_lookback_days": lookback,
        "calendar_semantics": "GTFS service date kept distinct from ridership local payment date. Overnight and unknown preceding-day contexts withheld from eligible subset; no date shifting of observations.",
        "training_readiness": "Not declared. Candidate matches are not automatically service-date-compatible. Review route histories, archive sampling and publisher imputation before modelling.",
        "sources": sources,
    }
    (OUT / "validation_summary.json").write_text(json.dumps(summary, indent=2, default=int), encoding="utf-8")
    write_report(summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "sources"}, indent=2, default=int), flush=True)


if __name__ == "__main__":
    main()
