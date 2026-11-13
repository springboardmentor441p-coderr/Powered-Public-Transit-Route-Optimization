"""
Export finished Milestone 1-3 tables and compact summaries into app_data/.

The Week 7-8 FastAPI backend and React frontend read ONLY from app_data/.
This script never touches data/processed/test_features.parquet and never modifies
reports/test_runs.log.

Usage:
    python -m src.export_app_data
"""

from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import src.build_matched_table as bmt
from src.build_review_list import (
    classify_overlap_pair,
    load_observed_review_window_hourly,
)
from src.predict import (
    EXTENDED_PUBLIC_HOLIDAYS,
    build_schedule_for_range,
    load_clean_ridership_history,
)

ROOT = Path(__file__).resolve().parents[1]
APP_DATA_DIR = ROOT / "app_data"
DATA_PROC = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"
TAB_DIR = REPORTS_DIR / "tables"
CONFIG_PATH = ROOT / "configs" / "optimization_thresholds.json"
GTFS_SPRING_ZIP = ROOT / "data" / "raw" / "gtfs" / "manhattan" / "2026-04-09" / "original.zip"
CLUSTERING_JOBLIB = ROOT / "models" / "route_clustering.joblib"


def _git_describe() -> tuple[str, str]:
    """Return (git_describe_dirty, short_sha) without failing outside git."""
    desc = "unknown"
    sha = "unknown"
    try:
        desc = subprocess.check_output(
            ["git", "describe", "--always", "--dirty"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass
    return desc, sha


def _to_json_safe(obj):
    """Recursively replace NaN/NaT/numpy scalars with JSON-safe native Python types."""
    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if pd.isna(obj) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if pd.isna(obj) if not isinstance(obj, (str, bytes, bool, int)) else False:
        return None
    return obj


def _load_october_full_hourly(matched_df: pd.DataFrame) -> pd.DataFrame:
    """Load full 2026-10-01..2026-10-31 hourly schedule + cleaned ridership + outage flags."""
    s1, h1 = build_schedule_for_range("2026-10-01", "2026-10-16", "2026-09-03")
    s2, h2 = build_schedule_for_range("2026-10-17", "2026-10-31", "2026-10-17")
    sched_oct = pd.concat([s1, s2], ignore_index=True)
    hol_flags = {**h1, **h2}

    rid_hist = load_clean_ridership_history("2026-10-31")
    rid_oct = rid_hist[
        (rid_hist["date"] >= "2026-10-01") & (rid_hist["date"] <= "2026-10-31")
    ].copy()

    oct_df = sched_oct.merge(rid_oct, on=["route", "date", "hour"], how="left")
    oct_df["ridership"] = oct_df["ridership"].fillna(0.0)
    oct_df["transfers"] = oct_df["transfers"].fillna(0.0)

    # Apply Step 11 20% relative outage check across Sep + Oct (excluding Columbus Day)
    sep_ctx = matched_df[
        (matched_df["date"] >= "2026-09-01") & (matched_df["date"] <= "2026-09-30")
    ][["route", "date", "hour", "ridership", "trips_running"]]
    oct_active = oct_df[oct_df["trips_running"] > 0][
        ["route", "date", "hour", "ridership", "trips_running"]
    ]
    comb_ctx = pd.concat([sep_ctx, oct_active], ignore_index=True)

    orig_hol = bmt.PUBLIC_HOLIDAYS
    try:
        bmt.PUBLIC_HOLIDAYS = EXTENDED_PUBLIC_HOLIDAYS
        outage_hours = {
            (d, int(h))
            for d, h, *_ in bmt.find_outage_hours_relative(comb_ctx, threshold=0.20)
            if d >= "2026-10-01"
        }
    finally:
        bmt.PUBLIC_HOLIDAYS = orig_hol

    dt_s = pd.to_datetime(oct_df["date"])
    oct_df["month"] = dt_s.dt.month
    oct_df["day_of_week"] = dt_s.dt.day_name()
    oct_df["is_weekend"] = oct_df["day_of_week"].isin(["Saturday", "Sunday"])
    oct_df["is_public_holiday"] = oct_df["date"].isin(EXTENDED_PUBLIC_HOLIDAYS)
    oct_df["holiday_schedule"] = oct_df["date"].map(hol_flags).fillna(False).astype(bool)
    oct_df["is_storm"] = oct_df["date"].isin(bmt.STORM_DATES) | pd.Series(
        list(zip(oct_df["date"], oct_df["hour"].astype(int))), index=oct_df.index
    ).isin(outage_hours)
    oct_df["is_outlier"] = False
    oct_df["time_band"] = oct_df["hour"].apply(bmt.assign_time_band)
    oct_df["riders_per_trip"] = np.where(
        oct_df["trips_running"] > 0,
        (oct_df["ridership"] / oct_df["trips_running"]).round(4),
        np.nan,
    )
    oct_df["riders_per_service_hour"] = np.where(
        oct_df["service_hours"] > 0,
        (oct_df["ridership"] / oct_df["service_hours"]).round(4),
        np.nan,
    )
    return oct_df


def _export_network_tables(matched_df: pd.DataFrame, oct_df: pd.DataFrame) -> dict:
    """Export network_daily.csv (Jan-Oct) and network_hourly.csv."""
    cols = [
        "route",
        "date",
        "hour",
        "day_of_week",
        "is_weekend",
        "is_public_holiday",
        "holiday_schedule",
        "is_storm",
        "is_outlier",
        "time_band",
        "ridership",
        "trips_running",
        "service_hours",
    ]
    full = pd.concat([matched_df[cols], oct_df[cols]], ignore_index=True)
    full["day_type"] = np.where(
        full["is_public_holiday"] | full["holiday_schedule"] | full["is_storm"] | full["is_outlier"],
        "Special/Excluded",
        np.where(
            full["day_of_week"] == "Saturday",
            "Typical Saturday",
            np.where(full["day_of_week"] == "Sunday", "Typical Sunday", "Typical Weekday"),
        ),
    )

    daily = (
        full.groupby("date", as_index=False)
        .agg(
            day_of_week=("day_of_week", "first"),
            day_type=("day_type", "first"),
            is_weekend=("is_weekend", "first"),
            is_public_holiday=("is_public_holiday", "any"),
            holiday_schedule=("holiday_schedule", "any"),
            is_storm=("is_storm", "any"),
            has_outlier=("is_outlier", "any"),
            total_ridership=("ridership", "sum"),
            total_trips_running=("trips_running", "sum"),
            total_service_hours=("service_hours", "sum"),
            active_routes=("route", "nunique"),
        )
        .sort_values("date")
    )

    # Re-insert missing telemetry dates (2026-01-10..15) as NaN instead of 0
    all_dates = pd.DataFrame(
        {"date": pd.date_range("2026-01-04", "2026-10-31", freq="D").strftime("%Y-%m-%d")}
    )
    daily = all_dates.merge(daily, on="date", how="left")
    missing_mask = daily["total_ridership"].isna() | daily["date"].isin(bmt.MISSING_RIDERSHIP_DATES)
    daily["is_missing"] = missing_mask
    dt_idx = pd.to_datetime(daily["date"])
    daily["day_of_week"] = daily["day_of_week"].fillna(dt_idx.dt.day_name())
    daily["is_weekend"] = (
        daily["is_weekend"].astype("boolean").fillna(daily["day_of_week"].isin(["Saturday", "Sunday"])).astype(bool)
    )
    daily["day_type"] = np.where(daily["is_missing"], "Missing Ridership", daily["day_type"])
    for col in ["total_ridership", "total_trips_running", "total_service_hours", "active_routes"]:
        daily.loc[daily["is_missing"], col] = np.nan

    daily["riders_per_trip"] = np.where(
        (~daily["is_missing"]) & (daily["total_trips_running"] > 0),
        (daily["total_ridership"] / daily["total_trips_running"]).round(2),
        np.nan,
    )
    daily["riders_per_service_hour"] = np.where(
        (~daily["is_missing"]) & (daily["total_service_hours"] > 0),
        (daily["total_ridership"] / daily["total_service_hours"]).round(2),
        np.nan,
    )
    daily["period_tag"] = np.select(
        [
            daily["date"] <= "2026-05-31",
            daily["date"] <= "2026-07-31",
            daily["date"] <= "2026-09-30",
        ],
        ["train", "val", "test"],
        default="october",
    )
    daily.to_csv(APP_DATA_DIR / "network_daily.csv", index=False)

    # Hourly network profiles over typical normal days (Jan-Sep main + Aug-Oct review window)
    normal_main = full[
        (full["date"] <= "2026-09-30")
        & (~full["is_public_holiday"])
        & (~full["holiday_schedule"])
        & (~full["is_storm"])
        & (~full["is_outlier"])
        & (full["trips_running"] > 0)
    ].copy()
    normal_main["period"] = "jan_sep_typical"

    normal_review = full[
        (full["date"] >= "2026-08-01")
        & (~full["is_public_holiday"])
        & (~full["holiday_schedule"])
        & (~full["is_storm"])
        & (~full["is_outlier"])
        & (full["trips_running"] > 0)
    ].copy()
    normal_review["period"] = "aug_oct_typical"

    hourly_frames = []
    for sub in [normal_main, normal_review]:
        # First sum across Manhattan routes per (date, day_type, hour) -> network clock-hour totals
        net_hr = (
            sub.groupby(["period", "date", "day_type", "hour", "time_band"], as_index=False)
            .agg(
                net_ridership=("ridership", "sum"),
                net_trips=("trips_running", "sum"),
                net_service_hours=("service_hours", "sum"),
            )
        )
        net_hr["net_rpt"] = np.where(
            net_hr["net_trips"] > 0, net_hr["net_ridership"] / net_hr["net_trips"], np.nan
        )
        net_hr["net_rpsh"] = np.where(
            net_hr["net_service_hours"] > 0,
            net_hr["net_ridership"] / net_hr["net_service_hours"],
            np.nan,
        )
        agg = (
            net_hr.groupby(["period", "day_type", "hour", "time_band"], as_index=False)
            .agg(
                n_days=("date", "nunique"),
                mean_network_ridership=("net_ridership", "mean"),
                q25_network_ridership=("net_ridership", lambda s: s.quantile(0.25)),
                median_network_ridership=("net_ridership", "median"),
                q75_network_ridership=("net_ridership", lambda s: s.quantile(0.75)),
                mean_network_trips=("net_trips", "mean"),
                mean_network_service_hours=("net_service_hours", "mean"),
                mean_riders_per_trip=("net_rpt", "mean"),
                mean_riders_per_service_hour=("net_rpsh", "mean"),
            )
        )
        for c in [
            "mean_network_ridership",
            "q25_network_ridership",
            "median_network_ridership",
            "q75_network_ridership",
            "mean_network_trips",
            "mean_network_service_hours",
            "mean_riders_per_trip",
            "mean_riders_per_service_hour",
        ]:
            agg[c] = agg[c].round(2)
        hourly_frames.append(agg)

    pd.concat(hourly_frames, ignore_index=True).sort_values(
        ["period", "day_type", "hour"]
    ).to_csv(APP_DATA_DIR / "network_hourly.csv", index=False)

    return {
        "matched_rows": len(matched_df),
        "daily_rows": len(daily),
        "normal_main_hours": len(normal_main),
        "october_all_hours": len(oct_df),
    }


def _export_route_geometries(kept_routes: list[str]) -> dict:
    """Extract ordered stop coordinates and simplified GTFS shapes for all 41 routes."""
    if not GTFS_SPRING_ZIP.exists():
        return {"source_snapshot": "not_found", "routes": {}}

    with zipfile.ZipFile(GTFS_SPRING_ZIP) as z:
        trips = pd.read_csv(
            z.open("trips.txt"),
            usecols=["route_id", "direction_id", "trip_id", "shape_id"],
            dtype=str,
        )
        shapes = pd.read_csv(
            z.open("shapes.txt"),
            usecols=["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
            dtype=str,
        )
        stops = pd.read_csv(
            z.open("stops.txt"),
            usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"],
            dtype=str,
        )
        stop_times = pd.read_csv(
            z.open("stop_times.txt"),
            usecols=["trip_id", "stop_id", "stop_sequence"],
            dtype=str,
        )

    shapes["shape_pt_lat"] = shapes["shape_pt_lat"].astype(float).round(5)
    shapes["shape_pt_lon"] = shapes["shape_pt_lon"].astype(float).round(5)
    shapes["shape_pt_sequence"] = shapes["shape_pt_sequence"].astype(int)
    stops["stop_lat"] = stops["stop_lat"].astype(float).round(5)
    stops["stop_lon"] = stops["stop_lon"].astype(float).round(5)
    stop_times["stop_sequence"] = stop_times["stop_sequence"].astype(int)

    trips = trips[trips["route_id"].isin(kept_routes)].copy()
    st_kept = stop_times[stop_times["trip_id"].isin(set(trips["trip_id"]))].copy()
    stops_map = stops.set_index("stop_id").to_dict(orient="index")

    geometries = {}
    all_lats = []
    all_lons = []

    for r in sorted(kept_routes):
        r_trips = trips[trips["route_id"] == r]
        polylines = []
        rep_stops = []
        dir_names = []

        for d_id in ["0", "1"]:
            d_t = r_trips[r_trips["direction_id"] == d_id]
            if d_t.empty:
                continue
            # Representative shape by most frequent shape_id
            shape_counts = d_t["shape_id"].dropna().value_counts()
            if not shape_counts.empty:
                top_shape = shape_counts.index[0]
                s_pts = shapes[shapes["shape_id"] == top_shape].sort_values("shape_pt_sequence")
                # Keep at most ~140 evenly sampled points per direction to stay fast in Leaflet
                if len(s_pts) > 140:
                    idx = np.unique(np.linspace(0, len(s_pts) - 1, 140, dtype=int))
                    s_pts = s_pts.iloc[idx]
                coords = list(zip(s_pts["shape_pt_lat"].tolist(), s_pts["shape_pt_lon"].tolist()))
                coords = [[float(lat), float(lon)] for lat, lon in coords]
                polylines.append({"direction_id": d_id, "coords": coords})
                all_lats.extend([c[0] for c in coords])
                all_lons.extend([c[1] for c in coords])

            # Longest trip stop endpoints & sample stops
            d_st = st_kept[st_kept["trip_id"].isin(set(d_t["trip_id"]))]
            if not d_st.empty:
                longest_trip = d_st.groupby("trip_id")["stop_sequence"].max().idxmax()
                seq_stops = d_st[d_st["trip_id"] == longest_trip].sort_values("stop_sequence")[
                    "stop_id"
                ].tolist()
                if seq_stops:
                    start_info = stops_map.get(seq_stops[0], {})
                    end_info = stops_map.get(seq_stops[-1], {})
                    dir_names.append(
                        {
                            "direction_id": d_id,
                            "start_stop_name": start_info.get("stop_name"),
                            "end_stop_name": end_info.get("stop_name"),
                            "stop_count": len(seq_stops),
                        }
                    )
                    if not rep_stops:
                        for idx, sid in enumerate(seq_stops):
                            if idx == 0 or idx == len(seq_stops) - 1 or idx % 4 == 0:
                                info = stops_map.get(sid)
                                if info:
                                    rep_stops.append(
                                        {
                                            "stop_id": sid,
                                            "stop_name": info["stop_name"],
                                            "lat": float(info["stop_lat"]),
                                            "lon": float(info["stop_lon"]),
                                        }
                                    )

        r_lats = [c[0] for p in polylines for c in p["coords"]]
        r_lons = [c[1] for p in polylines for c in p["coords"]]
        center = (
            [round(float(np.mean(r_lats)), 5), round(float(np.mean(r_lons)), 5)]
            if r_lats
            else None
        )
        geometries[r] = {
            "route": r,
            "center": center,
            "polylines": polylines,
            "directions": dir_names,
            "sample_stops": rep_stops,
        }

    payload = {
        "source_snapshot": "2026-04-09",
        "center": [round(float(np.mean(all_lats)), 5), round(float(np.mean(all_lons)), 5)]
        if all_lats
        else [40.7831, -73.9712],
        "routes": geometries,
    }
    (APP_DATA_DIR / "route_geometries.json").write_text(
        json.dumps(_to_json_safe(payload), indent=2), encoding="utf-8"
    )
    return {"routes_with_geometry": len(geometries)}


def _export_route_tables(matched_df: pd.DataFrame, oct_df: pd.DataFrame) -> None:
    """Export routes_summary.csv, route_hourly_pattern.csv, overlaps, thresholds, time bands."""
    profiles = pd.read_csv(REPORTS_DIR / "route_profiles.csv")
    cov = pd.read_csv(TAB_DIR / "m2_route_stop_coverage.csv")
    clusters = pd.read_csv(TAB_DIR / "m3_route_clusters_assigned.csv")
    variability = pd.read_csv(TAB_DIR / "m2_route_demand_variability.csv")
    p75 = pd.read_csv(TAB_DIR / "m2_high_demand_thresholds.csv")
    p75_piv = (
        p75.pivot(index="route", columns="day_type", values="threshold_p75")
        .rename(
            columns={
                "Typical Weekday": "p75_weekday",
                "Typical Saturday": "p75_saturday",
                "Typical Sunday": "p75_sunday",
            }
        )
        .reset_index()
    )

    summary = (
        profiles.rename(columns={"route_id": "route"})
        .merge(cov, on="route", how="left")
        .merge(
            clusters[
                [
                    "route_id",
                    "group_id",
                    "group_label",
                    "is_outlier_removed_before_kmeans",
                    "dbscan_eps180_cluster",
                    "dbscan_eps180_label",
                    "knn_3_distance",
                    "pc1_40",
                    "pc2_40",
                    "weekday_riders_est",
                    "weekend_to_weekday_ratio",
                    "morning_peak_share",
                    "night_share",
                    "peak_riders_per_service_hour",
                    "demand_variability",
                ]
            ].rename(columns={"route_id": "route"}),
            on="route",
            how="left",
        )
        .merge(p75_piv, on="route", how="left")
    )
    summary.to_csv(APP_DATA_DIR / "routes_summary.csv", index=False)
    variability.to_csv(APP_DATA_DIR / "route_hourly_variability.csv", index=False)

    # Summarized hourly pattern per (route, day_type, hour) on typical Jan-Sep normal days
    # Plus separate Aug-Oct typical period so route detail never touches raw 233k rows
    cols = [
        "route",
        "date",
        "hour",
        "day_of_week",
        "is_public_holiday",
        "holiday_schedule",
        "is_storm",
        "is_outlier",
        "time_band",
        "ridership",
        "trips_running",
        "service_hours",
        "riders_per_trip",
        "riders_per_service_hour",
    ]
    full = pd.concat([matched_df[cols], oct_df[cols]], ignore_index=True)
    typical = full[
        (~full["is_public_holiday"])
        & (~full["holiday_schedule"])
        & (~full["is_storm"])
        & (~full["is_outlier"])
        & (full["trips_running"] > 0)
    ].copy()
    typical["day_type"] = np.where(
        typical["day_of_week"] == "Saturday",
        "Typical Saturday",
        np.where(typical["day_of_week"] == "Sunday", "Typical Sunday", "Typical Weekday"),
    )

    jan_sep = typical[typical["date"] <= "2026-09-30"].copy()
    jan_sep["period"] = "jan_sep_typical"
    aug_oct = typical[typical["date"] >= "2026-08-01"].copy()
    aug_oct["period"] = "aug_oct_typical"

    pattern_frames = []
    for sub in [jan_sep, aug_oct]:
        agg = (
            sub.groupby(["period", "route", "day_type", "hour", "time_band"], as_index=False)
            .agg(
                n_days=("date", "nunique"),
                mean_ridership=("ridership", "mean"),
                q25_ridership=("ridership", lambda s: s.quantile(0.25)),
                median_ridership=("ridership", "median"),
                q75_ridership=("ridership", lambda s: s.quantile(0.75)),
                mean_trips_running=("trips_running", "mean"),
                mean_service_hours=("service_hours", "mean"),
                mean_riders_per_trip=("riders_per_trip", "mean"),
                mean_riders_per_service_hour=("riders_per_service_hour", "mean"),
            )
        )
        for c in [
            "mean_ridership",
            "q25_ridership",
            "median_ridership",
            "q75_ridership",
            "mean_trips_running",
            "mean_service_hours",
            "mean_riders_per_trip",
            "mean_riders_per_service_hour",
        ]:
            agg[c] = agg[c].round(2)
        pattern_frames.append(agg)

    pd.concat(pattern_frames, ignore_index=True).sort_values(
        ["period", "route", "day_type", "hour"]
    ).to_csv(APP_DATA_DIR / "route_hourly_pattern.csv", index=False)

    # Overlap pairs with explicit overlap category
    pairs = pd.read_csv(TAB_DIR / "m2_route_overlap_all_pairs.csv")
    pairs["overlap_category"] = [
        classify_overlap_pair(r1, r2) for r1, r2 in zip(pairs["route_1"], pairs["route_2"])
    ]
    pairs.to_csv(APP_DATA_DIR / "route_overlap_pairs.csv", index=False)

    p75.to_csv(APP_DATA_DIR / "route_thresholds.csv", index=False)
    cov.to_csv(APP_DATA_DIR / "route_coverage.csv", index=False)
    shutil.copy2(
        TAB_DIR / "m2_route_performance_table.csv",
        APP_DATA_DIR / "route_time_band_performance.csv",
    )


def _export_october_hourly_forecast(oct_df: pd.DataFrame) -> None:
    """Export 12,270 October hourly predictions joined with cleaned October actuals."""
    oct_pred = pd.read_csv(TAB_DIR / "m3_october_predictions.csv")
    actuals = oct_df[["route", "date", "hour", "ridership", "riders_per_trip", "is_storm", "is_public_holiday", "holiday_schedule"]].rename(
        columns={
            "ridership": "actual_ridership",
            "riders_per_trip": "actual_riders_per_trip",
        }
    )
    merged = oct_pred.merge(actuals, on=["route", "date", "hour"], how="left")
    merged["actual_high_demand_per_trip"] = np.where(
        merged["actual_riders_per_trip"].notna(),
        (merged["actual_riders_per_trip"] > merged["threshold_p75"]).astype(int),
        np.nan,
    )
    merged["baseline_4wk_riders_per_trip"] = np.where(
        merged["trips_running"] > 0,
        (merged["lag_mean_available"] / merged["trips_running"]).round(4),
        np.nan,
    )
    merged.to_parquet(APP_DATA_DIR / "october_hourly_forecast_vs_actual.parquet", index=False)


def _export_groups_metadata() -> None:
    """Export cluster assignments, profiles, stability tables, and PCA metadata."""
    import joblib

    obj = joblib.load(CLUSTERING_JOBLIB)
    pca = obj["pca_2d_40routes"]
    meta = {
        "outlier_route": obj["outlier_removed_before_clustering"],
        "selected_k_on_40_routes": int(obj["selected_k_on_40_routes"]),
        "selected_features": list(obj["selected_features"]),
        "pca_explained_variance_ratio": [round(float(x), 4) for x in pca.explained_variance_ratio_],
        "pca_total_variance_explained": round(float(pca.explained_variance_ratio_.sum()), 4),
        "group_metadata": _to_json_safe(obj["group_metadata"]),
        "overlap_note": (
            "Route groups reflect 9 route-level schedule/demand characteristics plus exclusive stop share "
            "(40 routes with M35 analyzed separately as an outlier). Shared corridors appear as moderate "
            "exclusive stop shares (median 44.7% in Group 1 vs 50.0% in Group 2 and 69.1% in Group 3); "
            "pair-level corridor relationships require inspecting the stop overlap pairs alongside group labels."
        ),
        "k2_vs_k3_decision_note": (
            "The pre-set stability rule selected k=2 (10-start ARI 1.000, LOO ARI 0.987, sil 0.255), "
            "but k=3 was chosen as an explicit departure because k=2 merges low-volume routes (~1,431 "
            "weekday riders/day) with ~6,871-rider short crosstown corridors."
        ),
    }
    (APP_DATA_DIR / "route_groups.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    shutil.copy2(TAB_DIR / "m3_route_clusters_assigned.csv", APP_DATA_DIR / "route_groups_assigned.csv")
    shutil.copy2(TAB_DIR / "m3_cluster_group_profiles_unscaled.csv", APP_DATA_DIR / "route_groups_profiles.csv")
    shutil.copy2(TAB_DIR / "m3_clustering_k_selection.csv", APP_DATA_DIR / "route_groups_k_selection.csv")
    shutil.copy2(TAB_DIR / "m3_clustering_k2_vs_k3_comparison.csv", APP_DATA_DIR / "route_groups_k2_vs_k3.csv")
    shutil.copy2(TAB_DIR / "m3_clustering_dbscan_summary.csv", APP_DATA_DIR / "route_groups_dbscan.csv")


def _export_evaluation_and_review_tables() -> None:
    """Copy finished evaluation, October, review, and scenario tables + compact obs parquet."""
    copies = {
        "m3_forecast_model_comparison.csv": "validation_forecast_comparison.csv",
        "m3_forecast_weekly_check.csv": "validation_forecast_weekly.csv",
        "m3_eval_best_forecast_by_route.csv": "validation_forecast_by_route_hgb.csv",
        "m3_eval_baseline_4wk_by_route.csv": "validation_forecast_by_route_4wk.csv",
        "m3_classification_fair_ranking.csv": "validation_classification_comparison.csv",
        "m3_test_forecast_overall.csv": "test_forecast_overall.csv",
        "m3_test_forecast_by_week.csv": "test_forecast_by_week.csv",
        "m3_test_forecast_by_route.csv": "test_forecast_by_route.csv",
        "m3_test_eval_hgb_forecast_by_day_type.csv": "test_forecast_by_day_type.csv",
        "m3_test_eval_hgb_forecast_by_time_band.csv": "test_forecast_by_time_band.csv",
        "m3_test_classification_overall.csv": "test_classification_overall.csv",
        "m3_test_eval_forecast_div_trips_by_route.csv": "test_classification_by_route_official.csv",
        "m3_test_eval_rule_b_by_route.csv": "test_classification_by_route_rule_b.csv",
        "m3_october_forecast_summary.csv": "october_forecast_summary.csv",
        "m3_october_forecast_by_day.csv": "october_forecast_by_day.csv",
        "m3_october_forecast_by_route.csv": "october_forecast_by_route.csv",
        "m3_october_classification_summary.csv": "october_classification_summary.csv",
        "m3_october_diagnostic_checks.csv": "october_diagnostic_checks.csv",
        "m3_step7_review_list.csv": "review_list.csv",
        "m3_step8_candidate_scenarios.csv": "step8_candidate_scenarios.csv",
        "m3_step8_shared_corridor_merge_checks.csv": "step8_shared_corridor_merge_checks.csv",
        "m3_step9_budget_neutral_reallocation.csv": "step9_budget_neutral_reallocation.csv",
    }
    for src_name, dst_name in copies.items():
        shutil.copy2(TAB_DIR / src_name, APP_DATA_DIR / dst_name)

    shutil.copy2(CONFIG_PATH, APP_DATA_DIR / "optimization_thresholds.json")

    # Export compact observed hourly distribution for live Step 8/9 scenario simulation
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        cfg = json.load(fh)
    win = cfg["step7_9_review_window"]
    obs = load_observed_review_window_hourly(win["start_date"], win["end_date"])
    obs_compact = obs[
        [
            "route",
            "date",
            "hour",
            "day_group",
            "day_type",
            "time_band",
            "trips_running",
            "service_hours",
            "ridership",
            "threshold_p75",
        ]
    ].copy()
    obs_compact.to_parquet(APP_DATA_DIR / "obs_review_hourly_distribution.parquet", index=False)


def _export_overview_and_version(net_meta: dict) -> None:
    """Export overview.json and version.json cleanly without loading test_features.parquet."""
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    sources_df = pd.read_csv(REPORTS_DIR / "source_register.csv")
    gtfs_df = pd.read_csv(REPORTS_DIR / "gtfs_versions.csv")
    splits_df = pd.read_csv(TAB_DIR / "m2_data_splits_summary.csv")
    cleaning = json.loads((REPORTS_DIR / "ridership_cleaning_summary.json").read_text(encoding="utf-8"))
    review_df = pd.read_csv(APP_DATA_DIR / "review_list.csv")
    daily_df = pd.read_csv(APP_DATA_DIR / "network_daily.csv")
    oct_eval_df = pd.read_parquet(APP_DATA_DIR / "october_hourly_forecast_vs_actual.parquet")

    test_log_path = REPORTS_DIR / "test_runs.log"
    test_log_lines = (
        [line.strip() for line in test_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if test_log_path.exists()
        else []
    )

    desc, sha = _git_describe()
    export_ts = datetime.now(timezone.utc).isoformat()

    overview = {
        "study_window": {
            "ridership_raw_start": "2026-01-01",
            "ridership_raw_end": "2026-10-31",
            "matched_main_start": "2026-01-04",
            "matched_main_end": "2026-09-30",
            "october_operational_start": "2026-10-18",
            "october_operational_end": "2026-10-31",
            "review_window_start": cfg["step7_9_review_window"]["start_date"],
            "review_window_end": cfg["step7_9_review_window"]["end_date"],
            "review_window_summary": cfg["step7_9_review_window"]["dates_summary"],
        },
        "sources": _to_json_safe(sources_df.to_dict(orient="records")),
        "gtfs_versions": _to_json_safe(gtfs_df.to_dict(orient="records")),
        "splits": _to_json_safe(splits_df.to_dict(orient="records"))
        + [
            {
                "set": "October Operational Check",
                "start_date": "2026-10-18",
                "end_date": "2026-10-31",
                "rows": 12270,
                "routes": 41,
            }
        ],
        "cleaning": {
            "raw_rows_jan_sep": int(cleaning["raw_rows"]),
            "clean_rows_jan_sep": int(cleaning["clean_rows"]),
            "routes_kept": int(cleaning["routes_kept"]),
            "zero_ridership_rows_kept": int(cleaning["zero_ridership_rows_kept"]),
            "zero_ridership_share": float(cleaning["zero_ridership_share"]),
            "validation_issues": cleaning["validation"],
            "dropped_routes": [d for d in cleaning["route_decisions"] if d["decision"] == "drop"],
            "kept_routes": [d["route"] for d in cleaning["route_decisions"] if d["decision"] == "keep"],
        },
        "exclusions": {
            "missing_ridership_dates": cleaning["missing_dates"],
            "storm_dates": sorted(list(bmt.STORM_DATES)),
            "public_holidays": sorted(list(EXTENDED_PUBLIC_HOLIDAYS.keys())),
            "holiday_details": EXTENDED_PUBLIC_HOLIDAYS,
            "excluded_outage_blocks": [
                {"date": "2026-01-04", "hours": "00:00-04:59", "reason": "System-wide zero/near-zero ridership (<20% typical)"},
                {"date": "2026-01-09", "hours": "22:00-23:59", "reason": "System-wide zero/near-zero ridership (<20% typical)"},
                {"date": "2026-03-28", "hours": "01:00-04:59", "reason": "System-wide zero/near-zero ridership (<20% typical)"},
                {"date": "2026-08-16", "hours": "21:00-22:59", "reason": "System-wide near-zero telemetry drop (2 hours)"},
            ],
            "outlier_route_hours": [
                {"route": "M35", "date": "2026-09-19", "hours": "14:00-19:59", "reason": "6-hour event surge (up to ~1,783 riders/hr vs ~24 typical)"}
            ],
            "october_outage_hours_flagged": 0,
        },
        "row_counts": {
            "matched_hourly_jan_sep": int(net_meta["matched_rows"]),
            "network_daily_days": int(len(daily_df)),
            "review_list_cells": int(len(review_df)),
            "fewer_trips_candidates": int((review_df["review_category"] == "fewer_trips_candidate").sum()),
            "more_trips_candidates": int((review_df["review_category"] == "more_trips_candidate").sum()),
            "october_operational_rows": int(len(oct_eval_df)),
        },
    }
    (APP_DATA_DIR / "overview.json").write_text(
        json.dumps(_to_json_safe(overview), indent=2), encoding="utf-8"
    )

    version = {
        "git_commit": desc,
        "git_sha": sha,
        "export_date": export_ts,
        "study_window": "2026-01-04 to 2026-10-31 (Training: Jan-May, Validation: Jun-Jul, Test: Aug-Sep, Operational Check: Oct 18-31; Review Window: Aug-Oct observed typical days)",
        "data_sources": "MTA Bus Hourly Ridership (2026-01 to 2026-10) & NYC Manhattan Bus GTFS Feeds (2025-12-30 to 2026-10-17)",
        "official_test_runs_logged": len(test_log_lines),
        "official_test_log": test_log_lines,
        "scenario_assumption": "Riders stay the same when trips change (0.0 elasticity arithmetic simulation)",
        "terminology_note": "Uses plain threshold terms ('high riders per trip'); avoids crowding/underused claims.",
    }
    (APP_DATA_DIR / "version.json").write_text(
        json.dumps(version, indent=2), encoding="utf-8"
    )


def export_all() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    matched_df = pd.read_parquet(DATA_PROC / "matched_hourly.parquet")
    oct_df = _load_october_full_hourly(matched_df)
    kept_routes = sorted(matched_df["route"].unique().tolist())

    net_meta = _export_network_tables(matched_df, oct_df)
    geom_meta = _export_route_geometries(kept_routes)
    _export_route_tables(matched_df, oct_df)
    _export_october_hourly_forecast(oct_df)
    _export_groups_metadata()
    _export_evaluation_and_review_tables()
    _export_overview_and_version(net_meta)

    files = sorted(p.name for p in APP_DATA_DIR.iterdir())
    print(f"Exported {len(files)} files to app_data/ (geometries={geom_meta['routes_with_geometry']} routes):")
    for f in files:
        size_kb = (APP_DATA_DIR / f).stat().st_size / 1024
        print(f"  - {f} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    export_all()
