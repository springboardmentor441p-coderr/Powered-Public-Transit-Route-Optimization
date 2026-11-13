"""Safe GTFS .zip upload & schedule/integrity/overlap inspection endpoint."""

from __future__ import annotations

import re
import shutil
import stat
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.app.data import clean_records
from src.build_route_profiles import format_seconds_to_hhmm, haversine
from src.build_review_list import classify_overlap_pair
from src.build_schedule import count_trip_hours, parse_time_to_seconds
from src.check_gtfs_integrity import check_gtfs_zip_integrity

router = APIRouter(prefix="/api", tags=["gtfs"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB hard cap
MAX_UNCOMPRESSED_BYTES = 300 * 1024 * 1024  # 300 MB decompression bomb guard


def _find_extracted_file(extract_dir: Path, filename: str) -> Path | None:
    direct = extract_dir / filename
    if direct.is_file():
        return direct
    for p in extract_dir.rglob("*"):
        if p.is_file() and p.name.lower() == filename.lower():
            return p
    return None


def _validate_and_extract_zip(zip_path: Path, extract_dir: Path) -> None:
    """Inspect every ZipInfo entry for Zip Slip / symlinks BEFORE extracting."""
    extract_root = extract_dir.resolve()
    total_uncompressed = 0

    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            if not name or "\x00" in name:
                raise HTTPException(status_code=400, detail="Invalid empty or NUL zip entry name.")

            # Reject Unix symlinks stored in zip
            unix_mode = (info.external_attr >> 16) & 0o170000
            if stat.S_ISLNK(unix_mode):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsafe symlink entry rejected in zip: {name}",
                )

            # Reject traversal or absolute / drive-letter paths across POSIX & Windows syntax
            if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name):
                raise HTTPException(
                    status_code=400,
                    detail=f"Absolute zip entry path rejected (Zip Slip check): {name}",
                )

            posix_parts = PurePosixPath(name).parts
            win_parts = PureWindowsPath(name).parts
            if ".." in posix_parts or ".." in win_parts:
                raise HTTPException(
                    status_code=400,
                    detail=f"Path traversal entry rejected (Zip Slip check): {name}",
                )

            resolved = (extract_root / name).resolve()
            if not resolved.is_relative_to(extract_root):
                raise HTTPException(
                    status_code=400,
                    detail=f"Zip entry resolves outside temporary directory (Zip Slip check): {name}",
                )

            total_uncompressed += max(0, info.file_size)
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Uncompressed GTFS archive exceeds 300 MB safety limit.",
                )

        z.extractall(extract_root)


def _compute_shape_lengths(shapes_df: pd.DataFrame | None) -> dict[str, float]:
    if shapes_df is None or shapes_df.empty:
        return {}
    needed = {"shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"}
    if not needed.issubset(shapes_df.columns):
        return {}
    df = shapes_df[list(needed)].copy()
    df["shape_pt_lat"] = df["shape_pt_lat"].astype(float)
    df["shape_pt_lon"] = df["shape_pt_lon"].astype(float)
    df["shape_pt_sequence"] = df["shape_pt_sequence"].astype(int)
    df = df.sort_values(["shape_id", "shape_pt_sequence"])

    df["prev_lat"] = df.groupby("shape_id")["shape_pt_lat"].shift(1)
    df["prev_lon"] = df.groupby("shape_id")["shape_pt_lon"].shift(1)
    valid = df["prev_lat"].notna()
    df["seg_km"] = 0.0
    df.loc[valid, "seg_km"] = haversine(
        df.loc[valid, "prev_lat"],
        df.loc[valid, "prev_lon"],
        df.loc[valid, "shape_pt_lat"],
        df.loc[valid, "shape_pt_lon"],
    )
    return df.groupby("shape_id")["seg_km"].sum().to_dict()


@router.post("/gtfs/upload")
async def upload_gtfs(request: Request, file: UploadFile = File(...)) -> dict:
    store = request.app.state.store
    filename = Path(file.filename or "upload.zip").name

    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip GTFS archives are supported.")

    tmp_dir = tempfile.mkdtemp(prefix="gtfs_upload_")
    try:
        tmp_root = Path(tmp_dir)
        zip_path = tmp_root / "uploaded.zip"
        extract_dir = tmp_root / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Stream upload and enforce 50 MB size limit before extraction
        total_bytes = 0
        with open(zip_path, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Uploaded file exceeds 50 MB limit ({total_bytes / (1024 * 1024):.1f} MB).",
                    )
                out_f.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded .zip file is empty.")

        try:
            _validate_and_extract_zip(zip_path, extract_dir)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail=f"Invalid .zip archive: {exc}") from exc

        # Step 4a: Milestone 1 referential integrity & timestamp checks
        try:
            integrity = check_gtfs_zip_integrity(zip_path, label=filename, quiet=True)
        except (ValueError, KeyError, pd.errors.ParserError, zipfile.BadZipFile) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"GTFS archive failed validation: {exc}",
            ) from exc

        # Read extracted tables for schedule, profiles, and overlap checks
        routes_p = _find_extracted_file(extract_dir, "routes.txt")
        trips_p = _find_extracted_file(extract_dir, "trips.txt")
        st_p = _find_extracted_file(extract_dir, "stop_times.txt")
        cal_p = _find_extracted_file(extract_dir, "calendar.txt")
        cal_dates_p = _find_extracted_file(extract_dir, "calendar_dates.txt")
        shapes_p = _find_extracted_file(extract_dir, "shapes.txt")

        routes_df = pd.read_csv(routes_p, dtype=str)
        trips_df = pd.read_csv(trips_p, dtype=str)
        st_df = pd.read_csv(st_p, dtype=str)
        cal_df = pd.read_csv(cal_p, dtype=str) if cal_p else None
        cal_dates_df = pd.read_csv(cal_dates_p, dtype=str) if cal_dates_p else None
        shapes_df = pd.read_csv(shapes_p, dtype=str) if shapes_p else None

        # Precompute trip departure/arrival seconds and durations
        st_df["seq"] = st_df["stop_sequence"].astype(int)
        st_sorted = st_df.sort_values(["trip_id", "seq"])
        first_st = st_sorted.groupby("trip_id", as_index=False).first()[
            ["trip_id", "departure_time"]
        ]
        last_st = st_sorted.groupby("trip_id", as_index=False).last()[
            ["trip_id", "arrival_time"]
        ]
        first_st["dep_sec"] = first_st["departure_time"].apply(parse_time_to_seconds)
        last_st["arr_sec"] = last_st["arrival_time"].apply(parse_time_to_seconds)

        trips_enriched = trips_df.merge(
            first_st[["trip_id", "dep_sec"]], on="trip_id", how="inner"
        ).merge(last_st[["trip_id", "arr_sec"]], on="trip_id", how="inner")
        trips_enriched["duration_min"] = (
            trips_enriched["arr_sec"] - trips_enriched["dep_sec"]
        ) / 60.0

        # Identify representative weekday, Saturday, and Sunday service_ids
        if cal_df is not None and not cal_df.empty:
            non_bm = cal_df[~cal_df["service_id"].str.endswith("-BM", na=False)]
            base_cal = non_bm if not non_bm.empty else cal_df
            wk_services = set(
                base_cal[
                    (base_cal["monday"] == "1")
                    | (base_cal["tuesday"] == "1")
                    | (base_cal["wednesday"] == "1")
                ]["service_id"]
            )
            sat_services = set(base_cal[base_cal["saturday"] == "1"]["service_id"])
            sun_services = set(base_cal[base_cal["sunday"] == "1"]["service_id"])
            # Pick a representative weekday within calendar range if available
            try:
                start_dt = datetime.strptime(str(base_cal["start_date"].min()), "%Y%m%d")
                rep_date = start_dt
                while rep_date.weekday() != 2:  # Wednesday
                    rep_date += timedelta(days=1)
            except Exception:
                rep_date = datetime(2026, 5, 13)
        else:
            all_srv = set(trips_enriched["service_id"].dropna())
            wk_services = all_srv
            sat_services = set()
            sun_services = set()
            rep_date = datetime(2026, 5, 13)

        if not wk_services:
            wk_services = set(trips_enriched["service_id"].dropna())

        wk_trips = trips_enriched[trips_enriched["service_id"].isin(wk_services)].copy()
        sat_trips = trips_enriched[trips_enriched["service_id"].isin(sat_services)].copy()
        sun_trips = trips_enriched[trips_enriched["service_id"].isin(sun_services)].copy()

        # Re-use Milestone 1 count_trip_hours for hourly schedule summary (24h + spillover collapsed cleanly into rep_date / next-day)
        trip_tuples = list(
            zip(wk_trips["route_id"], wk_trips["dep_sec"].astype(int), wk_trips["arr_sec"].astype(int))
        )
        grid = defaultdict(lambda: [0, 0, 0.0])
        rep_str = rep_date.strftime("%Y-%m-%d")
        next_str = (rep_date + timedelta(days=1)).strftime("%Y-%m-%d")
        count_trip_hours(rep_date, trip_tuples, grid, rep_str, next_str)

        # Collapse service-day clock hours by clock hour (0-23) across representative weekday + overnight spillover
        hourly_counts = defaultdict(lambda: [0, 0, 0.0])
        for (r_id, _d_str, hr), vals in grid.items():
            hourly_counts[(r_id, int(hr))][0] += vals[0]
            hourly_counts[(r_id, int(hr))][1] += vals[1]
            hourly_counts[(r_id, int(hr))][2] += vals[2]

        network_hourly = []
        for hr in range(24):
            starts = sum(v[0] for (r, h), v in hourly_counts.items() if h == hr)
            runs = sum(v[1] for (r, h), v in hourly_counts.items() if h == hr)
            svc_h = round(sum(v[2] for (r, h), v in hourly_counts.items() if h == hr), 2)
            network_hourly.append(
                {
                    "hour": hr,
                    "trips_starting": int(starts),
                    "trips_running": int(runs),
                    "service_hours": svc_h,
                }
            )

        # Route stop sets & exclusivity (pure calculation; does NOT write reports/)
        trip_route_map = trips_df[["trip_id", "route_id"]].drop_duplicates()
        st_stops = st_df[["trip_id", "stop_id"]].merge(trip_route_map, on="trip_id", how="inner")
        route_stops = st_stops.groupby("route_id")["stop_id"].unique().apply(set).to_dict()

        stop_route_counts: dict[str, int] = defaultdict(int)
        for sset in route_stops.values():
            for sid in sset:
                stop_route_counts[sid] += 1

        shape_lengths = _compute_shape_lengths(shapes_df)

        # Study route lookup from app_data/routes_summary.csv
        study_lookup = store.routes_summary.set_index("route").to_dict(orient="index")

        wk_counts = wk_trips.groupby("route_id").size().to_dict()
        sat_counts = sat_trips.groupby("route_id").size().to_dict()
        sun_counts = sun_trips.groupby("route_id").size().to_dict()
        route_meta_map = routes_df.set_index("route_id").to_dict(orient="index")

        # Fast grouped stats for weekday trips
        grouped_wk = {r: grp for r, grp in wk_trips.groupby("route_id")}
        grouped_all = {r: grp for r, grp in trips_enriched.groupby("route_id")}

        route_rows = []
        study_matched_count = 0
        non_study_count = 0

        for r in sorted(route_meta_map.keys()):
            r_meta = route_meta_map[r]
            r_grp = grouped_wk.get(r)
            if r_grp is None:
                r_grp = grouped_all.get(r)

            r_stops = route_stops.get(r, set())
            excl_count = sum(1 for sid in r_stops if stop_route_counts[sid] == 1)
            excl_share = round(excl_count / len(r_stops), 4) if r_stops else None

            if r_grp is not None and not r_grp.empty:
                min_dep = int(r_grp["dep_sec"].min())
                max_dep = int(r_grp["dep_sec"].max())
                avg_dur = round(float(r_grp["duration_min"].mean()), 1)
                first_dep = format_seconds_to_hhmm(min_dep)
                last_dep = format_seconds_to_hhmm(max_dep)

                dir_lens = []
                if "direction_id" in r_grp.columns and "shape_id" in r_grp.columns:
                    for d_val in ["0", "1"]:
                        d_sub = r_grp[r_grp["direction_id"] == d_val]
                        if not d_sub.empty and d_sub["shape_id"].notna().any():
                            top_sh = d_sub["shape_id"].value_counts().index[0]
                            if top_sh in shape_lengths:
                                dir_lens.append(shape_lengths[top_sh])
                elif "shape_id" in r_grp.columns and r_grp["shape_id"].notna().any():
                    top_sh = r_grp["shape_id"].value_counts().index[0]
                    if top_sh in shape_lengths:
                        dir_lens.append(shape_lengths[top_sh])

                len_km = round(float(np.mean(dir_lens)), 2) if dir_lens else None
                speed_kmh = (
                    round(len_km / (avg_dur / 60.0), 1)
                    if (len_km is not None and avg_dur and avg_dur > 0)
                    else None
                )
            else:
                first_dep = None
                last_dep = None
                avg_dur = None
                len_km = None
                speed_kmh = None

            study_info = study_lookup.get(r)
            if study_info is not None:
                study_matched_count += 1
                has_hist = True
                status_note = "Matched to Manhattan study route (Jan–Oct 2026 ridership history available)"
                group_label = study_info.get("group_label")
                avg_daily = study_info.get("avg_daily_riders")
                peak_rpt = study_info.get("peak_riders_per_trip")
            else:
                non_study_count += 1
                has_hist = False
                status_note = "no ridership history, schedule analysis only"
                group_label = None
                avg_daily = None
                peak_rpt = None

            route_rows.append(
                {
                    "route_id": r,
                    "route_short_name": r_meta.get("route_short_name") or r,
                    "route_long_name": r_meta.get("route_long_name") or "",
                    "service_type": "Select Bus Service (+)" if "+" in r else "Local",
                    "stop_count": len(r_stops),
                    "exclusive_stops": excl_count,
                    "exclusive_stop_share": excl_share,
                    "trips_per_weekday": int(wk_counts.get(r, 0)),
                    "trips_per_saturday": int(sat_counts.get(r, 0)),
                    "trips_per_sunday": int(sun_counts.get(r, 0)),
                    "first_departure": first_dep,
                    "last_departure": last_dep,
                    "avg_trip_duration_min": avg_dur,
                    "route_length_km": len_km,
                    "avg_scheduled_speed_kmh": speed_kmh,
                    "has_ridership_history": has_hist,
                    "study_group_label": group_label,
                    "study_avg_daily_riders": avg_daily,
                    "study_peak_riders_per_trip": peak_rpt,
                    "status_note": status_note,
                }
            )

        # Pairwise stop overlap summary (top 50 overlapping pairs)
        pair_rows = []
        active_routes = sorted(route_stops.keys())
        for i in range(len(active_routes)):
            r1 = active_routes[i]
            s1 = route_stops[r1]
            for j in range(i + 1, len(active_routes)):
                r2 = active_routes[j]
                s2 = route_stops[r2]
                shared = s1 & s2
                if shared:
                    min_len = min(len(s1), len(s2))
                    pair_rows.append(
                        {
                            "route_1": r1,
                            "route_2": r2,
                            "smaller_route": r1 if len(s1) <= len(s2) else r2,
                            "larger_route": r2 if len(s1) <= len(s2) else r1,
                            "shared_stops_count": len(shared),
                            "smaller_route_stops": min_len,
                            "overlap_share": round(len(shared) / min_len, 4),
                            "jaccard_similarity": round(len(shared) / len(s1 | s2), 4),
                            "overlap_category": classify_overlap_pair(r1, r2),
                        }
                    )
        pair_rows.sort(key=lambda x: (-x["overlap_share"], -x["shared_stops_count"]))

        clean_routes = clean_records(pd.DataFrame(route_rows)) if route_rows else []
        return {
            "filename": filename,
            "file_size_mb": round(total_bytes / (1024 * 1024), 3),
            "period": "Uploaded GTFS timetable archive (schedule & stop-overlap analysis only for new feeds)",
            "source": f"Uploaded GTFS zip ({filename}) checked with Milestone 1 integrity/profile/overlap pipeline",
            "integrity": integrity,
            "summary": {
                "routes_in_feed": len(routes_df),
                "routes_with_trips": integrity["n_routes_with_trips"],
                "study_routes_matched": study_matched_count,
                "non_study_routes_schedule_only": non_study_count,
                "overlapping_pairs_total": len(pair_rows),
                "calendar_exceptions_count": int(len(cal_dates_df)) if cal_dates_df is not None else 0,
                "representative_weekday_date": rep_str,
            },
            "network_hourly_schedule": network_hourly,
            "routes": clean_routes,
            "top_overlaps": pair_rows[:50],
        }
    finally:
        await file.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)

