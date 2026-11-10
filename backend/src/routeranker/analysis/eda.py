"""Exploratory analysis of scheduled GTFS service.

All service counts and headways describe GTFS schedule records. They are not
observations of actual bus operations, passenger demand, or traffic.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

import polars as pl

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
REQUIRED_TABLES = ("routes", "stops", "trips", "stop_times", "calendar")


def _require_columns(frame: pl.DataFrame, filename: str, columns: set[str]) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError(f"{filename} is missing required EDA columns: {missing}")


def _gtfs_time(seconds: int | None) -> str | None:
    """Format seconds while retaining hours above 24:00:00."""
    if seconds is None:
        return None
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _safe_cell(value: Any) -> str:
    """Escape feed-provided text before putting it into a Markdown table."""
    return html.escape(str(value)).replace("|", "&#124;").replace("`", "&#96;").replace("\n", " ")


def _calendar_weekday_table(calendar: pl.DataFrame) -> pl.DataFrame:
    """Turn GTFS calendar flags into one row per service and weekday."""
    long = calendar.unpivot(
        on=list(WEEKDAYS), index="service_id", variable_name="weekday", value_name="active"
    )
    return long.with_columns(pl.col("active").cast(pl.Int8, strict=False))


def _trip_departures(trips: pl.LazyFrame, stop_times: pl.LazyFrame) -> pl.DataFrame:
    """Find each trip's first scheduled departure by stop_sequence."""
    starts = stop_times.group_by("trip_id").agg(
        pl.col("departure_time_seconds").sort_by("stop_sequence_value").first().alias("first_departure_seconds"),
        pl.col("arrival_time_seconds").sort_by("stop_sequence_value").last().alias("last_arrival_seconds"),
        pl.col("stop_id").sort_by("stop_sequence_value").first().alias("first_stop_id"),
    )
    return (
        trips.join(starts, on="trip_id", how="left")
        .select("trip_id", "route_id", "service_id", "direction_id", "first_departure_seconds", "last_arrival_seconds", "first_stop_id")
        .collect(engine="streaming")
    )


def _headway_summary(departures: pl.DataFrame) -> pl.DataFrame:
    """Calculate timetable gaps within route/service/direction groups.

    A headway here is the difference between consecutive first-stop scheduled
    departure times. Groups with fewer than two trips have no estimate.
    """
    group_keys = ["route_id", "service_id", "direction_id"]
    ordered = departures.sort(group_keys + ["first_departure_seconds"])
    gaps = ordered.with_columns(
        pl.col("first_departure_seconds").diff().over(group_keys).alias("headway_seconds")
    )
    return gaps.group_by(group_keys).agg(
        pl.col("headway_seconds").count().alias("headway_observations"),
        pl.col("headway_seconds").mean().alias("mean_headway_seconds"),
        pl.col("headway_seconds").median().alias("median_headway_seconds"),
        pl.col("headway_seconds").min().alias("min_headway_seconds"),
        pl.col("headway_seconds").max().alias("max_headway_seconds"),
        (pl.col("headway_seconds") == 0).sum().alias("zero_gap_count"),
    ).sort(group_keys)


def _route_pair_overlap(route_stops: pl.DataFrame, route_stop_counts: pl.DataFrame) -> pl.DataFrame:
    """Return shared-stop counts and Jaccard similarity for all route pairs.

    The self-join is performed on the compact distinct route-stop relation,
    never on the full 1.36 million row stop_times table.
    """
    pairs = (
        route_stops.lazy()
        .join(route_stops.lazy(), on="stop_id", how="inner", suffix="_b")
        .filter(pl.col("route_id") < pl.col("route_id_b"))
        .group_by("route_id", "route_id_b")
        .agg(pl.col("stop_id").n_unique().alias("shared_stop_count"))
        .collect(engine="streaming")
    )
    count_a = route_stop_counts.rename({"route_id": "route_id_a", "stop_count": "route_a_stop_count"})
    count_b = route_stop_counts.rename({"route_id": "route_id_b", "stop_count": "route_b_stop_count"})
    return (
        pairs.rename({"route_id": "route_id_a"})
        .join(count_a, on="route_id_a", how="left")
        .join(count_b, on="route_id_b", how="left")
        .with_columns(
            (
                pl.col("shared_stop_count")
                / (pl.col("route_a_stop_count") + pl.col("route_b_stop_count") - pl.col("shared_stop_count"))
            ).alias("jaccard_similarity")
        )
        .sort(["shared_stop_count", "jaccard_similarity"], descending=True)
    )


def _chart_outputs(
    route_summary: pl.DataFrame,
    hourly: pl.DataFrame,
    stop_summary: pl.DataFrame,
    charts_dir: Path,
) -> list[str]:
    """Write static EDA charts; all chart titles identify scheduled metrics."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    charts_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

    top = route_summary.filter(pl.col("trip_count") > 0).sort("trip_count", descending=True).head(20)
    fig, ax = plt.subplots(figsize=(12, 6))
    if top.height:
        labels = top.get_column("route_id").to_list()
        values = top.get_column("trip_count").to_list()
        ax.barh(labels[::-1], values[::-1], color="#176B87")
    ax.set_title("Top 20 Routes by GTFS Trip Records")
    ax.set_xlabel("Scheduled trip records (calendar templates; not ridership)")
    ax.set_ylabel("Route ID")
    fig.tight_layout()
    path = charts_dir / "top_routes_by_scheduled_trip_records.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    files.append(str(path))

    max_hour = int(hourly["service_hour"].max() or 25)
    all_hours = pl.DataFrame({"service_hour": list(range(max(25, max_hour) + 1))}).join(hourly, on="service_hour", how="left").with_columns(pl.col("scheduled_trip_records").fill_null(0))
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(all_hours["service_hour"].to_list(), all_hours["scheduled_trip_records"].to_list(), color="#3A9D8F")
    ax.set_title("Scheduled Trip Starts by GTFS Service Hour")
    ax.set_xlabel("Service hour (24+ means after midnight in GTFS notation)")
    ax.set_ylabel("Trip records starting in hour")
    ax.set_xticks(range(0, 26, 2))
    fig.tight_layout()
    path = charts_dir / "scheduled_trip_starts_by_service_hour.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    files.append(str(path))

    used_stops = stop_summary.filter(pl.col("route_count") > 0)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(used_stops["route_count"].to_list(), bins=30, color="#E9A23B", edgecolor="white")
    ax.set_title("GTFS Stop Coverage by Number of Routes")
    ax.set_xlabel("Routes serving a stop")
    ax.set_ylabel("Stop count")
    fig.tight_layout()
    path = charts_dir / "stop_route_coverage_distribution.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    files.append(str(path))
    return files


def _write_report(report: dict[str, Any], path: Path) -> None:
    """Write concise, escaped Markdown findings and scope notes."""
    totals = report["totals"]
    lines = [
        "# RouteRanker GTFS exploratory data analysis", "",
        "## Scope", "",
        "This report describes scheduled GTFS records only. Trip counts, service frequencies, and headways do not measure passenger demand, actual bus operations, traffic, or occupancy.",
        "First service time is the earliest first-stop scheduled departure; last service time is the latest final-stop scheduled arrival. Headways compare consecutive first-stop departure times within route, calendar service, and direction groups.",
        "Weekday estimates apply `calendar.txt` weekday flags to trip templates. See the limitations section for calendar exceptions and frequency-file availability.", "",
        "## Feed totals", "",
        f"- Route records: {totals['route_records']:,} ({totals['routes_with_trips']:,} referenced by trips)",
        f"- Stop records: {totals['stop_records']:,} ({totals['stops_used']:,} referenced by stop_times)",
        f"- Trip records: {totals['trip_records']:,}",
        f"- Stop-time records: {totals['stop_time_records']:,}",
        f"- Calendar service rows: {totals['calendar_service_rows']:,} ({totals['calendar_services_used_by_trips']:,} referenced by trips; {totals['calendar_services_unused']:,} unused)",
        f"- Calendar definition date span: {totals['calendar_start_date_min']} to {totals['calendar_end_date_max']} (from start/end dates in calendar.txt)",
        f"- Distinct route-stop pairs: {totals['route_stop_pairs']:,}",
        f"- Stops served by at least two routes: {totals['shared_stops']:,}",
        f"- Route pairs sharing one or more stops: {totals['route_pairs_with_shared_stops']:,}",
        f"- Stop-time records with arrival or departure at/after 24:00:00: {totals['after_midnight_stop_time_records']:,}",
        f"- Trips with first scheduled departure at/after 24:00:00: {totals['after_midnight_trip_starts']:,}", "",
        "## Scheduled service levels", "",
        f"- Highest template-week scheduled trip count among routes with trips: **{_safe_cell(report['service_level']['highest_route'])}** with {report['service_level']['highest_weekly_trip_count']:,} calendar-flagged trip instances.",
        f"- Lowest nonzero template-week scheduled trip count among routes with trips: **{_safe_cell(report['service_level']['lowest_route'])}** with {report['service_level']['lowest_weekly_trip_count']:,} calendar-flagged trip instances.",
        "- Route raw trip-record counts are schedule trip definitions. Template-week totals repeat each trip on the weekdays enabled by its service calendar; they are not measured observed operations.", "",
        "| Weekday | Scheduled trip records enabled by calendar |", "|---|---:|"]
    for day, count in report["scheduled_trips_by_weekday"].items():
        lines.append(f"| {day.title()} | {count:,} |")
    lines += ["",
        "### Top routes by template-week scheduled trips", "",
        "| Route ID | Trip records | Stops | Template-week trips | First departure | Last arrival |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in report["top_routes"]:
        lines.append(
            f"| {_safe_cell(row['route_id'])} | {row['trip_count']:,} | {row['stop_count']:,} | {row['template_week_trip_count']:,} | {row['first_service_time'] or '—'} | {row['last_service_time'] or '—'} |"
        )
    lines += ["", "## Headways and time-of-day patterns", "",
              f"- Route/service/direction groups with at least one estimated scheduled headway: {report['headways']['groups_with_estimates']:,}.",
              f"- Groups with one or fewer trips (no headway estimate): {report['headways']['groups_without_estimates']:,}.",
              f"- Groups with simultaneous scheduled starts (zero gaps): {report['headways']['groups_with_zero_gaps']:,}.",
              f"- Median of group median scheduled headways: {report['headways']['median_of_group_medians_seconds']} seconds.",
              f"- Most common first-departure service hour: {report['time_of_day']['busiest_service_hour']}:00, across {report['time_of_day']['busiest_hour_trip_records']:,} trip records.",
              "- The hourly total counts trip templates across all service IDs; templates with different calendar days may not operate together on one date.",
              f"- Service frequency counts are based on scheduled trips in `trips.txt`; {report['limitations']['frequency_note']}",
              "- Headways are timetable gaps between scheduled first-stop departures. They are not observed arrival regularity or passenger waiting time.", "",
              "## Shared stops", "",
              "The full route-pair table is in `route_pair_overlap.parquet`; it contains shared stop counts and Jaccard similarity computed from distinct stop sets.",
              "A shared stop indicates geographic/network overlap in the supplied stop IDs, not passenger transfer behavior or route substitutability.", "",
              "| Route A | Route B | Shared stops | Jaccard similarity |", "|---|---|---:|---:|"]
    for row in report["top_shared_route_pairs"]:
        lines.append(f"| {_safe_cell(row['route_id_a'])} | {_safe_cell(row['route_id_b'])} | {row['shared_stop_count']:,} | {row['jaccard_similarity']:.4f} |")
    lines += ["", "## Data quality and unusual patterns", ""]
    for finding in report["findings"]:
        lines.append(f"- {finding}")
    lines += ["", "## Data limitations", ""]
    lines += [f"- {limitation}" for limitation in report["limitations"]["notes"]]
    lines += ["", "## Outputs", ""]
    for name in report["output_files"]:
        lines.append(f"- `{name}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_eda(processed_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Analyze Phase 1 Parquet tables and write reusable EDA outputs.

    The stop_times table is scanned lazily and reduced to trip starts,
    trip-stop counts, and distinct route-stop pairs before collecting compact
    relations for reports and charts.
    """
    processed_dir = Path(processed_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    missing = [name for name in REQUIRED_TABLES if not (processed_dir / f"{name}.parquet").is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required Phase 1 Parquet tables in {processed_dir}: {missing}")

    routes = pl.read_parquet(processed_dir / "routes.parquet")
    stops = pl.read_parquet(processed_dir / "stops.parquet")
    calendar = pl.read_parquet(processed_dir / "calendar.parquet")
    trips = pl.scan_parquet(processed_dir / "trips.parquet")
    stop_times = pl.scan_parquet(processed_dir / "stop_times.parquet")
    _require_columns(routes, "routes.parquet", {"route_id", "route_type"})
    _require_columns(stops, "stops.parquet", {"stop_id", "stop_name", "stop_lat_value", "stop_lon_value"})
    _require_columns(calendar, "calendar.parquet", {"service_id", *WEEKDAYS, "start_date", "end_date"})
    trip_columns = set(trips.collect_schema().names())
    stop_time_columns = set(stop_times.collect_schema().names())
    _require_columns(pl.DataFrame(schema={c: pl.String for c in trip_columns}), "trips.parquet", {"trip_id", "route_id", "service_id", "direction_id"})
    _require_columns(pl.DataFrame(schema={c: pl.String for c in stop_time_columns}), "stop_times.parquet", {"trip_id", "stop_id", "stop_sequence_value", "arrival_time_seconds", "departure_time_seconds"})

    trip_departures = _trip_departures(trips, stop_times)
    if trip_departures.filter(pl.col("first_departure_seconds").is_null()).height:
        raise ValueError("Some trips have no first scheduled departure in stop_times.parquet.")

    trip_stats = trip_departures.group_by("route_id").agg(
        pl.col("trip_id").n_unique().alias("trip_count"),
        pl.col("first_departure_seconds").min().alias("first_departure_seconds"),
        pl.col("last_arrival_seconds").max().alias("last_arrival_seconds"),
    )
    route_stops = (
        stop_times.join(trips.select("trip_id", "route_id"), on="trip_id", how="inner")
        .select("route_id", "stop_id")
        .unique()
        .collect(engine="streaming")
    )
    used_network_stop_count = route_stops.get_column("stop_id").n_unique()
    route_stop_counts = route_stops.group_by("route_id").agg(pl.col("stop_id").n_unique().alias("stop_count"))
    route_summary = (
        routes.join(trip_stats, on="route_id", how="left")
        .join(route_stop_counts, on="route_id", how="left")
        .with_columns(
            pl.col("trip_count").fill_null(0).cast(pl.Int64),
            pl.col("stop_count").fill_null(0).cast(pl.Int64),
        )
        .with_columns(
            (pl.col("stop_count") * 100.0 / used_network_stop_count).alias("used_network_stop_coverage_pct")
            if used_network_stop_count else pl.lit(0.0).alias("used_network_stop_coverage_pct")
        )
    )

    trip_stop_stats = stop_times.group_by("stop_id").agg(pl.col("trip_id").n_unique().alias("trip_count")).collect(engine="streaming")
    stop_route_counts = route_stops.group_by("stop_id").agg(pl.col("route_id").n_unique().alias("route_count"))
    stop_summary = (
        stops.join(trip_stop_stats, on="stop_id", how="left")
        .join(stop_route_counts, on="stop_id", how="left")
        .with_columns(pl.col("trip_count").fill_null(0).cast(pl.Int64), pl.col("route_count").fill_null(0).cast(pl.Int64))
    )

    trip_rows = trips.collect(engine="streaming")
    route_service_counts = trip_rows.group_by("route_id", "service_id").agg(pl.len().alias("trip_count"))
    calendar_long = _calendar_weekday_table(calendar)
    route_weekday = (
        route_service_counts.join(calendar_long, on="service_id", how="left")
        .filter(pl.col("active") == 1)
        .group_by("route_id", "weekday")
        .agg(pl.col("trip_count").sum().alias("scheduled_trip_count"))
    )
    weekdays = pl.DataFrame({"weekday": list(WEEKDAYS)})
    route_weekday = (
        routes.select("route_id").join(weekdays, how="cross")
        .join(route_weekday, on=["route_id", "weekday"], how="left")
        .with_columns(pl.col("scheduled_trip_count").fill_null(0).cast(pl.Int64))
        .sort(["route_id", "weekday"])
    )
    weekly_totals = route_weekday.group_by("route_id").agg(
        pl.col("scheduled_trip_count").sum().alias("template_week_trip_count"),
        pl.col("scheduled_trip_count").max().alias("max_weekday_trip_count"),
    )
    route_summary = (
        route_summary.join(weekly_totals, on="route_id", how="left")
        .with_columns(pl.col("template_week_trip_count").fill_null(0), pl.col("max_weekday_trip_count").fill_null(0))
        .with_columns(
            pl.col("first_departure_seconds").map_elements(_gtfs_time, return_dtype=pl.String).alias("first_service_time"),
            pl.col("last_arrival_seconds").map_elements(_gtfs_time, return_dtype=pl.String).alias("last_service_time"),
        )
        .sort(["trip_count", "route_id"], descending=[True, False])
    )

    # Group first-stop starts by route, service calendar, and direction.
    headways = _headway_summary(trip_departures)
    route_service_headways = (
        trip_departures.group_by("route_id", "service_id", "direction_id").agg(
            pl.len().alias("scheduled_trip_count"),
            pl.col("first_departure_seconds").min().alias("first_departure_seconds"),
            pl.col("last_arrival_seconds").max().alias("last_arrival_seconds"),
        )
        .join(headways, on=["route_id", "service_id", "direction_id"], how="left")
        .with_columns(
            pl.col("first_departure_seconds").map_elements(_gtfs_time, return_dtype=pl.String).alias("first_service_time"),
            pl.col("last_arrival_seconds").map_elements(_gtfs_time, return_dtype=pl.String).alias("last_service_time"),
        )
        .sort(["route_id", "service_id", "direction_id"])
    )

    # A calendar-based weekday count is available; date exceptions are not.
    weekday_totals = route_weekday.group_by("weekday").agg(pl.col("scheduled_trip_count").sum()).sort("weekday")
    weekday_totals.write_csv(output_dir / "scheduled_trips_by_weekday.csv")

    hourly = (
        trip_departures.with_columns((pl.col("first_departure_seconds") // 3600).alias("service_hour"))
        .group_by("service_hour")
        .agg(pl.len().alias("scheduled_trip_records"))
        .sort("service_hour")
    )
    hourly.write_csv(output_dir / "scheduled_trips_by_service_hour.csv")

    route_pair_overlap = _route_pair_overlap(route_stops, route_stop_counts)
    route_summary.write_csv(output_dir / "route_summary.csv")
    stop_summary.write_csv(output_dir / "stop_summary.csv")
    route_weekday.write_csv(output_dir / "route_scheduled_trips_by_weekday.csv")
    route_service_headways.write_csv(output_dir / "route_service_headways.csv")
    route_stops.write_parquet(output_dir / "route_stop_coverage.parquet", compression="zstd")
    route_pair_overlap.write_parquet(output_dir / "route_pair_overlap.parquet", compression="zstd")
    route_pair_overlap.head(100).write_csv(output_dir / "top_shared_route_pairs.csv")

    # Calendar analysis includes unused service records to make feed coverage visible.
    service_counts = trip_rows.group_by("service_id").agg(pl.len().alias("trip_record_count"))
    calendar_analysis = calendar.join(service_counts, on="service_id", how="left").with_columns(
        pl.col("trip_record_count").fill_null(0).cast(pl.Int64),
        (pl.col("trip_record_count").fill_null(0) > 0).alias("referenced_by_trips"),
    )
    calendar_analysis.write_csv(output_dir / "service_calendar_summary.csv")

    chart_paths = _chart_outputs(route_summary, hourly, stop_summary, output_dir / "charts")

    # Restrict service-level rankings to routes referenced by trips.
    active_routes = route_summary.filter(pl.col("trip_count") > 0)
    high_route = active_routes.sort(["template_week_trip_count", "route_id"], descending=[True, False]).row(0, named=True)
    low_route = active_routes.sort(["template_week_trip_count", "route_id"]).row(0, named=True)
    top_routes = (
        route_summary.sort(["template_week_trip_count", "trip_count", "route_id"], descending=[True, True, False])
        .head(10)
        .select("route_id", "trip_count", "stop_count", "template_week_trip_count", "first_service_time", "last_service_time")
        .to_dicts()
    )
    top_shared = route_pair_overlap.head(10).to_dicts()
    h_summary = headways
    groups_with_estimates = h_summary.filter(pl.col("headway_observations") > 0).height
    groups_with_zero = h_summary.filter(pl.col("zero_gap_count") > 0).height
    busiest_hour = hourly.sort(["scheduled_trip_records", "service_hour"], descending=[True, False]).row(0, named=True)

    phase1_report_path = processed_dir / "data_quality_report.json"
    phase1_report = json.loads(phase1_report_path.read_text(encoding="utf-8")) if phase1_report_path.is_file() else {}
    phase1_issues = phase1_report.get("issues", [])
    phase1_counts = {issue.get("code"): issue.get("count", 0) for issue in phase1_issues}
    phase1_files = phase1_report.get("files", {}).values()
    duplicate_rows_total = sum(int(item.get("duplicate_rows", 0)) for item in phase1_files)
    duplicate_primary_key_total = sum(int(item.get("duplicate_primary_key_rows", 0)) for item in phase1_files)
    unresolved_references_total = sum(
        int(value) for key, value in phase1_report.get("metrics", {}).items()
        if key.endswith("_unresolved_unique_references")
    )
    source_files = phase1_report.get("files", {})
    calendar_dates_info = source_files.get("calendar_dates.txt", {})
    frequency_info = source_files.get("frequencies.txt", {})
    shapes_info = source_files.get("shapes.txt", {})
    calendar_dates_available = calendar_dates_info.get("presence") == "present"
    frequencies_available = frequency_info.get("presence") == "present"
    shapes_available = shapes_info.get("presence") == "present"
    calendar_dates_rows = int(calendar_dates_info.get("rows", 0))
    limitations = {
        "calendar_dates_available": calendar_dates_available,
        "calendar_dates_rows": calendar_dates_rows,
        "frequencies_available": frequencies_available,
        "shapes_available": shapes_available,
        "frequency_note": (
            "GTFS frequencies.txt entries are available; route headways shown here still use trip start times."
            if frequencies_available else
            "`frequencies.txt` is absent, so frequency-based service is not included; headways are estimated from trip start times."
        ),
        "notes": [
            (f"calendar_dates.txt has {calendar_dates_rows:,} exception rows; weekday totals apply calendar.txt flags and do not expand dates."
             if calendar_dates_available else "calendar_dates.txt is absent, so service exception dates cannot be incorporated."),
            ("shapes.txt is present; this EDA still uses stop IDs for route coverage and computes no route length/area."
             if shapes_available else "shapes.txt is absent, so no route geometry, route length, or spatial coverage area was inferred."),
            ("frequencies.txt is present but frequency-based rows are not used to estimate headways."
             if frequencies_available else "frequencies.txt is absent, so frequency-based service is unavailable."),
        ],
    }
    route_rows, stop_rows, trip_rows_count = routes.height, stops.height, trip_departures.height
    calendar_start_dates = [value for value in calendar.get_column("start_date").drop_nulls().to_list() if value]
    calendar_end_dates = [value for value in calendar.get_column("end_date").drop_nulls().to_list() if value]
    trip_stop_count = stop_times.select(pl.len()).collect(engine="streaming").item()
    used_stops_count = stop_summary.filter(pl.col("trip_count") > 0).height
    shared_stops_count = stop_summary.filter(pl.col("route_count") > 1).height
    after_midnight_trip_starts = trip_departures.filter(pl.col("first_departure_seconds") >= 86400).height
    after_midnight_stop_time_records = int(
        stop_times.select(
            (pl.col("arrival_time_seconds").ge(86400) | pl.col("departure_time_seconds").ge(86400)).sum()
        ).collect(engine="streaming").item()
    )
    estimated_headway_groups = h_summary.filter(pl.col("headway_observations") > 0)
    median_group_medians = estimated_headway_groups.select(pl.col("median_headway_seconds").median()).item() if estimated_headway_groups.height else None
    weekday_records = {
        row["weekday"]: int(row["scheduled_trip_count"])
        for row in weekday_totals.iter_rows(named=True)
    }

    findings = [
        f"{route_rows - active_routes.height:,} route records have no trip records; they are retained in route_summary.csv with zero counts.",
        f"{stop_rows - used_stops_count:,} stop records are not referenced by stop_times; they are retained in stop_summary.csv with zero counts.",
        f"{calendar_analysis.filter(~pl.col('referenced_by_trips')).height:,} calendar service rows are unused by trips.",
        f"{shared_stops_count:,} stops are served by more than one route; this is network overlap, not evidence of transfers or demand.",
        f"{after_midnight_stop_time_records:,} stop-time records are at or after 24:00:00; {after_midnight_trip_starts:,} trip starts occur after midnight in GTFS service-hour notation.",
        f"Phase 1 quality checks found {duplicate_rows_total:,} duplicate full rows, {duplicate_primary_key_total:,} duplicate primary-key rows, and {unresolved_references_total:,} unresolved unique references.",
        limitations["notes"][0],
        limitations["notes"][1],
    ]
    if phase1_counts.get("blank_values", 0):
        findings.append(f"Phase 1 recorded {phase1_counts['blank_values']:,} blank source values, including blank feed metadata dates.")
    report = {
        "source_parquet_directory": str(processed_dir),
        "output_directory": str(output_dir),
        "totals": {
            "route_records": route_rows,
            "routes_with_trips": active_routes.height,
            "stop_records": stop_rows,
            "stops_used": used_stops_count,
            "trip_records": trip_rows_count,
            "stop_time_records": int(trip_stop_count),
            "route_stop_pairs": route_stops.height,
            "shared_stops": shared_stops_count,
            "route_pairs_with_shared_stops": route_pair_overlap.height,
            "after_midnight_trip_starts": after_midnight_trip_starts,
            "after_midnight_stop_time_records": after_midnight_stop_time_records,
            "calendar_service_rows": calendar_analysis.height,
            "calendar_services_used_by_trips": calendar_analysis.filter(pl.col("referenced_by_trips")).height,
            "calendar_services_unused": calendar_analysis.filter(~pl.col("referenced_by_trips")).height,
            "calendar_start_date_min": min(calendar_start_dates) if calendar_start_dates else None,
            "calendar_end_date_max": max(calendar_end_dates) if calendar_end_dates else None,
        },
        "service_level": {
            "highest_route": high_route["route_id"],
            "highest_weekly_trip_count": int(high_route["template_week_trip_count"]),
            "lowest_route": low_route["route_id"],
            "lowest_weekly_trip_count": int(low_route["template_week_trip_count"]),
        },
        "headways": {
            "groups_with_estimates": groups_with_estimates,
            "groups_without_estimates": h_summary.height - groups_with_estimates,
            "groups_with_zero_gaps": groups_with_zero,
            "median_of_group_medians_seconds": median_group_medians,
        },
        "time_of_day": {
            "busiest_service_hour": int(busiest_hour["service_hour"]),
            "busiest_hour_trip_records": int(busiest_hour["scheduled_trip_records"]),
            "hourly_trip_record_counts": {str(row["service_hour"]): int(row["scheduled_trip_records"]) for row in hourly.iter_rows(named=True)},
        },
        "scheduled_trips_by_weekday": weekday_records,
        "data_quality": {
            "duplicate_full_rows": duplicate_rows_total,
            "duplicate_primary_key_rows": duplicate_primary_key_total,
            "unresolved_unique_references": unresolved_references_total,
            "phase1_blank_value_warnings": int(phase1_counts.get("blank_values", 0)),
        },
        "limitations": limitations,
        "top_routes": top_routes,
        "top_shared_route_pairs": top_shared,
        "findings": findings,
        "output_files": [
            "route_summary.csv", "stop_summary.csv", "route_scheduled_trips_by_weekday.csv",
            "scheduled_trips_by_weekday.csv", "scheduled_trips_by_service_hour.csv",
            "route_service_headways.csv", "service_calendar_summary.csv",
            "route_stop_coverage.parquet", "route_pair_overlap.parquet", "top_shared_route_pairs.csv",
            "eda_report.json", "eda_report.md", "charts/top_routes_by_scheduled_trip_records.png",
            "charts/scheduled_trip_starts_by_service_hour.png", "charts/stop_route_coverage_distribution.png",
        ],
    }
    (output_dir / "eda_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_report(report, output_dir / "eda_report.md")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run exploratory analysis on processed GTFS Parquet tables.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/gtfs"), help="Phase 1 Parquet directory")
    parser.add_argument("--output", type=Path, default=Path("data/processed/eda"), help="EDA outputs directory")
    args = parser.parse_args()
    report = run_eda(args.input, args.output)
    print(json.dumps({"totals": report["totals"], "service_level": report["service_level"], "output_directory": report["output_directory"]}, indent=2))


if __name__ == "__main__":
    main()

