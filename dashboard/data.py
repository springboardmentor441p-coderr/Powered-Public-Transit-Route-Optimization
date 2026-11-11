"""Read-only, fingerprint-checked access to published analytical products."""
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/processed/new_york"
CATALOG = ROOT / "documentation/dashboard_data_manifest.json"
PREVIEWS = BASE / "forecast_previews"
DAY_TYPES = ["Weekday", "Saturday", "Sunday"]
STATES = {"planning_review": "Planning review", "source_clarification": "Source clarification",
          "no_rule_triggered": "No rule triggered", "insufficient_evidence": "Insufficient evidence"}


class DataUnavailable(ValueError):
    """An input is absent or no longer matches the reviewed data release."""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def catalog():
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DataUnavailable("The dashboard data manifest is missing or unreadable. See documentation/DASHBOARD.md.") from exc


def checked_bytes(path, expected):
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise DataUnavailable(f"Required local artifact unavailable: {Path(path).name}. Restore the validated data bundle.") from exc
    if hashlib.sha256(data).hexdigest() != expected:
        raise DataUnavailable(f"Fingerprint mismatch: {Path(path).name}. Restore or revalidate this release before using it.")
    return data


@st.cache_data(show_spinner=False, max_entries=64)
def _read_table(path, expected, size, modified_ns):
    # Stat fields invalidate the cache when a local file is replaced or edited.
    data = checked_bytes(path, expected)
    frame = pd.read_csv(BytesIO(data), low_memory=False, dtype={
        "bus_route": "string", "route_a": "string", "route_b": "string",
        "shape_id": "string", "stop_id": "string", "route_id": "string"})
    for column in ["payment_date", "local_hour", "first_date", "last_date", "origin"]:
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], errors="raise")
    return frame


def table(name):
    entry = catalog()["tables"].get(name)
    if entry is None:
        raise DataUnavailable(f"Unknown analytical table: {name}")
    path = ROOT / entry["path"]
    try:
        stat = path.stat()
    except OSError as exc:
        raise DataUnavailable(f"Missing {entry['path']}. Restore the local artifacts described in documentation/DASHBOARD.md.") from exc
    frame = _read_table(str(path), entry["sha256"], stat.st_size, stat.st_mtime_ns)
    if len(frame) != entry["rows"] or list(frame.columns) != entry["columns"]:
        raise DataUnavailable(f"Schema or row count mismatch: {name}")
    return frame


def document(name):
    entry = catalog()["documents"][name]
    return json.loads(checked_bytes(ROOT / entry["path"], entry["sha256"]))


def inventory():
    rows = []
    for kind in ["tables", "documents"]:
        for name, entry in catalog()[kind].items():
            path = ROOT / entry["path"]
            status = "missing" if not path.is_file() else "verified" if digest(path) == entry["sha256"] else "mismatch"
            rows.append({"artifact": name, "status": status, "rows": entry.get("rows"),
                         "path": entry["path"], "sha256": entry["sha256"]})
    return pd.DataFrame(rows)


def filtered_history(frame, route, start, end, day_types):
    """Leave missing observations missing, including empty user selections."""
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("Start date must not follow end date")
    return frame.loc[frame.bus_route.eq(route) & frame.payment_date.between(str(start), str(end))
                     & frame.day_type.isin(day_types)].copy()


def history_summary(frame):
    paired = frame.loc[frame.comparison_eligible.eq(True)]
    hours = paired.scheduled_service_hours.sum(min_count=1)
    demand = paired.analysis_boardings.sum(min_count=1)
    return {"observed_days": int(frame.analysis_boardings.notna().sum()),
            "mean_boardings": frame.analysis_boardings.mean(), "paired_days": len(paired),
            "boardings_per_bus_hour": demand / hours if pd.notna(hours) and hours > 0 else np.nan}


def route_paths(route):
    links, shapes = table("map_routes"), table("map_shapes")
    ids = links.loc[links.bus_route.eq(route), "shape_id"]
    selected = shapes.loc[shapes.shape_id.isin(ids)].sort_values(["shape_id", "shape_pt_sequence"])
    return [{"route": route, "shape": str(shape), "path": rows[["shape_pt_lon", "shape_pt_lat"]].values.tolist()}
            for shape, rows in selected.groupby("shape_id") if len(rows) >= 2]


def peer_overlaps(route):
    rows = table("overlap")
    rows = rows.loc[rows.route_a.eq(route) | rows.route_b.eq(route)].copy()
    is_a = rows.route_a.eq(route)
    rows["peer"] = np.where(is_a, rows.route_b, rows.route_a)
    rows["selected_route_only_stops"] = np.where(is_a, rows.a_only_stop_ids, rows.b_only_stop_ids)
    rows["peer_only_stops"] = np.where(is_a, rows.b_only_stop_ids, rows.a_only_stop_ids)
    return rows.sort_values(["jaccard", "peer"], ascending=[False, True])


def preview_list():
    available, rejected = [], []
    for folder in sorted(PREVIEWS.glob("*"), reverse=True):
        if not folder.is_dir():
            continue
        try:
            meta = json.loads((folder / "preview_manifest.json").read_text(encoding="utf-8"))
            if meta["preview_mode"] not in ["reference", "challenger"]:
                raise ValueError("Unknown preview mode")
            available.append({"id": folder.name, **meta})
        except (OSError, ValueError, KeyError):
            rejected.append(folder.name)
    return available, rejected


def load_preview(identifier):
    """Validate points and permitted ranges; previews never become operational forecasts."""
    folder = (PREVIEWS / identifier).resolve()
    if folder.parent != PREVIEWS.resolve():
        raise DataUnavailable("Invalid preview selection")
    try:
        meta = json.loads((folder / "preview_manifest.json").read_text(encoding="utf-8"))
        profile_entry = catalog()["documents"]["forecast_profile"]
        if meta["profile_sha256"] != profile_entry["sha256"]:
            raise DataUnavailable("Preview belongs to a different forecast profile")
        profile = document("forecast_profile")
        if meta["preview_mode"] not in ["reference", "challenger"]:
            raise DataUnavailable("Unknown forecast mode")
        strategy = profile[f"{meta['preview_mode']}_strategy"]
        if meta["strategy"] != strategy or meta["operationally_accepted"] is not False:
            raise DataUnavailable("Unexpected forecast strategy or acceptance claim")
        snapshot = (ROOT / meta["snapshot"] / "route_days.csv").resolve()
        if not snapshot.is_relative_to((ROOT / "data/raw/new_york_monitoring").resolve()):
            raise DataUnavailable("Forecast source is outside the validated monitoring collection")
        checked_bytes(snapshot, meta["snapshot_sha256"])
        for name, expected_hash in meta["upstream_hashes"].items():
            upstream = (BASE / name).resolve()
            if upstream.parent != BASE.resolve():
                raise DataUnavailable("Invalid forecast input path")
            checked_bytes(upstream, expected_hash)
        points = pd.read_csv(BytesIO(checked_bytes(folder / "point_forecasts.csv", meta["point_sha256"])))
        ranges = pd.read_csv(BytesIO(checked_bytes(folder / "empirical_ranges.csv", meta["range_sha256"])))
        checked_bytes(folder / "calibration_audit.csv", meta["calibration_audit_sha256"])
        points.payment_date = pd.to_datetime(points.payment_date)
        if points.duplicated(["bus_route", "payment_date"]).any() or len(points) != meta["point_rows"]:
            raise DataUnavailable("Forecast rows are incomplete or duplicated")
        routes = sorted(table("review").bus_route)
        dates = pd.date_range(meta["first_target"], meta["last_target"])
        expected = pd.MultiIndex.from_product([routes, dates])
        actual = pd.MultiIndex.from_frame(points[["bus_route", "payment_date"]])
        if len(dates) != 7 or len(expected.difference(actual)) or len(actual.difference(expected)):
            raise DataUnavailable("Forecast must contain all study routes for exactly seven target dates")
        if not np.isfinite(points.prediction).all() or points.prediction.lt(0).any():
            raise DataUnavailable("Forecast contains invalid point values")
        if not points.strategy.eq(strategy).all() or not points['mode'].eq("experimental_preview").all():
            raise DataUnavailable("Forecast point labels disagree with the manifest")
        issue = pd.Timestamp(meta["generated_utc"])
        source_date = pd.Timestamp(meta["source_observed_utc"]).tz_convert("UTC").tz_localize(None).normalize()
        issue_date = issue.tz_convert("UTC").tz_localize(None).normalize()
        if pd.Timestamp(meta["source_observed_utc"]) > issue:
            raise DataUnavailable("Forecast source was observed after issue time")
        cutoff = pd.Timestamp(meta["maturity_cutoff"])
        if cutoff > min(source_date, issue_date) - pd.Timedelta(days=15):
            raise DataUnavailable("Forecast history exceeds the source maturity cutoff")
        if not points.payment_date.gt(issue_date).all():
            raise DataUnavailable("Forecast was not issued before its target dates")
        if not pd.to_datetime(points.availability_cutoff).eq(cutoff).all() or not pd.to_datetime(points.max_history_date).le(cutoff).all():
            raise DataUnavailable("Forecast history does not respect its declared cutoff")
        levels = [x["level"] for x in profile["strategies"][strategy]["intervals"] if x["within_5_percentage_points"]]
        if set(meta["range_levels_available"]) != set(levels):
            raise DataUnavailable("Preview range policy differs from the validated profile")
        if len(ranges):
            ranges.payment_date = pd.to_datetime(ranges.payment_date)
            if ranges.duplicated(["bus_route", "payment_date", "level"]).any() or not ranges.level.isin(levels).all():
                raise DataUnavailable("Unsupported or duplicate empirical ranges")
            if not np.isfinite(ranges[["lower", "upper"]].to_numpy()).all() or (ranges.lower.lt(0) | ranges.upper.lt(ranges.lower)).any():
                raise DataUnavailable("Invalid empirical range bounds")
            for level in levels:
                part = ranges.loc[ranges.level.eq(level)]
                keys = pd.MultiIndex.from_frame(part[["bus_route", "payment_date"]])
                if len(keys) != len(expected) or len(expected.difference(keys)):
                    raise DataUnavailable("Incomplete empirical ranges")
                aligned = part.merge(points[["bus_route", "payment_date", "prediction"]],
                                     on=["bus_route", "payment_date"], suffixes=("_range", "_point"), validate="one_to_one")
                if not np.allclose(aligned.prediction_range, aligned.prediction_point, atol=1e-8, rtol=0) or not part.model.eq(strategy).all():
                    raise DataUnavailable("Range points disagree with the forecast")
        elif levels:
            raise DataUnavailable("Expected empirical ranges are missing")
        return meta, points, ranges
    except (OSError, KeyError, ValueError) as exc:
        if isinstance(exc, DataUnavailable):
            raise
        raise DataUnavailable("Forecast files are missing or inconsistent. Regenerate a validated preview.") from exc


def preview_age(meta, today=None):
    today = pd.Timestamp(today or datetime.now(timezone.utc).date()).normalize()
    if today > pd.Timestamp(meta["last_target"]):
        return "Archived preview — all target dates have passed"
    if today >= pd.Timestamp(meta["first_target"]):
        return "Issued preview — target window has started"
    return "Issued preview — future target window"


def generate_preview(mode, target_start):
    if mode not in ["reference", "challenger"]:
        raise ValueError("Unknown forecast mode")
    target = pd.Timestamp(target_start).date()
    now = datetime.now(timezone.utc).date()
    if not 1 <= (target - now).days <= 7:
        raise ValueError("Select a target start between tomorrow and seven days from today (UTC)")
    try:
        result = subprocess.run([sys.executable, str(ROOT / "scripts/forecast_preview.py"),
                                 "--mode", mode, "--target-start", target.isoformat()],
                                cwd=ROOT, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        raise DataUnavailable("Generation timed out. Existing previews are preserved.") from exc
    if result.returncode:
        raise DataUnavailable("Generation was withheld by the forecast validation checks. The source may be stale or incomplete. Refresh and validate observations using documentation/OCTOBER_VALIDATION.md; existing previews remain available.")
    payload = json.loads(result.stdout)
    identifier = Path(payload["output"]).name
    load_preview(identifier)
    return identifier


def csv_bytes(frame):
    # CSVs are intended for spreadsheets as well as analysis. Escape formula-like text.
    safe = frame.copy()
    for col in safe.select_dtypes(include=["object", "string"]):
        safe[col] = safe[col].map(lambda value: "'" + value if isinstance(value, str)
                                and value.lstrip().startswith(("=", "+", "-", "@")) else value)
    return safe.to_csv(index=False).encode("utf-8-sig")


def scenario_export(frame, metadata, extra_tables=None):
    payload = BytesIO()
    with ZipFile(payload, "w", ZIP_DEFLATED) as archive:
        archive.writestr("scenario.csv", csv_bytes(frame))
        archive.writestr("assumptions.json", json.dumps({
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "historical_mean_daily_arithmetic", "timetable_feasibility": "not_assessed",
            "automatic_service_change": False, "passenger_benefit_measured": False,
            "input_manifest_sha256": digest(CATALOG), **metadata}, indent=2, default=str))
        for name, table_frame in (extra_tables or {}).items():
            archive.writestr(name + ".csv", csv_bytes(table_frame))
    return payload.getvalue()
