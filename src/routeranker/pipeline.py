"""End-to-end training pipeline.

    python -m routeranker.pipeline            # use cached raw data, download what is missing
    python -m routeranker.pipeline --refresh  # re-download latest month(s) first
    python -m routeranker.pipeline --skip-download

Stages: collect -> clean -> engineer features -> EDA -> preprocess ->
cluster -> classify -> forecast -> optimise -> persist artefacts.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime

import joblib
import pandas as pd

from . import config as C
from . import data_collection as dc
from .cleaning import (clean_evasion, clean_ridership, clean_routes, clean_schedule, clean_speeds, clean_wait)
from .clustering import run_clustering, stop_overlap
from .diagrams import architecture_diagram, model_figures, pipeline_diagram
from .eda import run_eda
from .feature_engineering import build_route_hour_table, build_route_profiles, classify_occupancy
from .optimization import impact_summary, optimize_frequencies
from .preprocessing import ProfileEncoder, model_matrix, time_split
from .supervised import train_classifiers, train_forecasters

log = logging.getLogger("routeranker.pipeline")
HISTORY_COLS = ["route_id", "ts", "date", "hour", "dow", "day_type", "is_holiday", "ridership", "est_riders",
                "transfers", "trips",
                "load_per_trip", "occupancy", "perf_class", "productivity", "speed_mph", "avg_wait_min",
                "revenue_hours", "capacity", "trip_minutes"]


def _read(name: str) -> pd.DataFrame:
    """Read one cached raw parquet table."""
    return pd.read_parquet(C.RAW_DIR / f"{name}.parquet")


def load_raw(download: bool, refresh: bool) -> dict[str, pd.DataFrame]:
    """Stage 1 - collect (or read cached) raw tables."""
    if download:
        needed = ["segment_speeds", "route_speeds", "wait_assessment", "fare_evasion", "routes", "stops",
                  "schedule_trips_per_hour", "schedule_route_geometry"]
        if refresh or any(not (C.RAW_DIR / f"{n}.parquet").exists() for n in needed):
            dc.collect_all()
        else:
            dc.collect_hourly_ridership()
    files = sorted((C.RAW_DIR / "ridership").glob("ridership_*.parquet"))
    return {
        "ridership": pd.concat([pd.read_parquet(f) for f in files], ignore_index=True),
        "tph": _read("schedule_trips_per_hour"), "geo": _read("schedule_route_geometry"),
        "seg": _read("segment_speeds"), "monthly": _read("route_speeds"), "wait": _read("wait_assessment"),
        "routes": _read("routes"), "stops": _read("stops"),
        "evasion": _read("fare_evasion") if (C.RAW_DIR / "fare_evasion.parquet").exists() else None,
    }


def run(download: bool = True, refresh: bool = False) -> dict:
    """Execute all pipeline stages and persist data, models, metrics and figures."""
    t0 = time.time()
    stage_times = {}

    def mark(name):
        """Record the elapsed time of a finished stage."""
        stage_times[name] = round(time.time() - t0 - sum(stage_times.values()), 1)
        log.info("== stage '%s' done (%.1fs)", name, stage_times[name])

    raw = load_raw(download, refresh); mark("1_data_collection")

    # ---- cleaning
    rid, clean_rep = clean_ridership(raw["ridership"])
    trips, geo = clean_schedule(raw["tph"], raw["geo"])
    speeds_hourly, route_speed = clean_speeds(raw["seg"], raw["monthly"])
    wait = clean_wait(raw["wait"])
    evasion = clean_evasion(raw["evasion"])
    clean_rep["fare_evasion_rates"] = evasion
    catalog, paths, stops = clean_routes(raw["routes"], raw["stops"], route_speed)
    # keep routes that have both ridership and a schedule
    scheduled = set(trips.loc[trips["trips"] > 0, "route_id"])
    clean_rep["routes_without_schedule"] = sorted(set(rid["route_id"]) - scheduled)
    rid = rid[rid["route_id"].isin(scheduled)]
    clean_rep["routes_modelled"] = int(rid["route_id"].nunique())
    mark("2_cleaning")

    # ---- features
    route_static = (catalog[["route_id", "route_type", "borough"]]
                    .merge(geo[["route_id", "length_mi", "n_stops"]], how="outer")
                    .merge(wait, how="left").merge(route_speed[["route_id", "route_speed_mph"]], how="left"))
    route_static = route_static[route_static["route_id"].isin(rid["route_id"].unique())]
    missing = set(rid["route_id"]) - set(route_static["route_id"])
    if missing:
        from .cleaning import borough_of
        route_static = pd.concat([route_static, pd.DataFrame({"route_id": sorted(missing)})], ignore_index=True)
        route_static["borough"] = route_static["borough"].fillna(route_static["route_id"].map(borough_of))
        route_static["route_type"] = route_static["route_type"].fillna(
            route_static["route_id"].map(lambda r: "Select Bus Service" if r.endswith("+") else "Local"))
    route_static["length_mi"] = route_static["length_mi"].fillna(route_static["length_mi"].median())
    route_static["evasion_factor"] = 1 / (1 - route_static["route_type"].map(evasion).fillna(evasion["Other"]))
    rh = build_route_hour_table(rid, trips, speeds_hourly, route_static)
    # calibrate class thresholds on the training period's service hours
    cutoff_cal = rh["date"].max() - pd.Timedelta(days=C.VALIDATION_DAYS - 1)
    occ = rh.loc[(rh["trips"] > 0) & (rh["date"] < cutoff_cal), "occupancy"].dropna()
    C.set_thresholds(occ.quantile(C.UNDER_QUANTILE), occ.quantile(C.OVER_QUANTILE))
    C.THRESHOLDS_FILE.write_text(json.dumps({"underutilized_max": C.UNDERUTILIZED_MAX,
                                             "overcrowded_min": C.OVERCROWDED_MIN,
                                             "target_occupancy": C.TARGET_OCCUPANCY,
                                             "quantiles": [C.UNDER_QUANTILE, C.OVER_QUANTILE]}, indent=2))
    rh["perf_class"] = classify_occupancy(rh["occupancy"])
    log.info("calibrated thresholds: under < %.3f, over > %.3f", C.UNDERUTILIZED_MAX, C.OVERCROWDED_MIN)
    profiles = build_route_profiles(rh)
    mark("3_feature_engineering")

    # ---- overlap + EDA
    overlap = stop_overlap(stops, profiles["route_id"].tolist())
    eda_summary = run_eda(rh, profiles, overlap, clean_rep)
    mark("4_eda")

    # ---- preprocessing
    train, valid, cutoff = time_split(rh)
    enc = ProfileEncoder().fit(train)
    train_e, Xtr = model_matrix(train, enc)
    valid_e, Xva = model_matrix(valid, enc)
    mark("5_preprocessing")

    # ---- clustering
    cl_prof, cl = run_clustering(profiles)
    mark("6_clustering")

    # ---- classification (route-hours with service only)
    mtr, mva = train_e["perf_class"].notna().to_numpy(), valid_e["perf_class"].notna().to_numpy()
    clf = train_classifiers(Xtr[mtr], train_e.loc[mtr, "perf_class"], Xva[mva], valid_e.loc[mva, "perf_class"])
    mark("7_classification")

    # ---- forecasting
    reg = train_forecasters(Xtr, train_e["log_ridership"], Xva, valid_e["ridership"])
    valid_e["pred"] = reg["validation_predictions"]
    mark("8_forecasting")

    # ---- optimisation impact on the validation period (actual loads)
    opt = optimize_frequencies(valid_e)
    impact = impact_summary(opt)
    mark("9_optimisation")

    # ---- persist artefacts
    P = C.PROCESSED_DIR
    centroids = stops.groupby("route_id")[["latitude", "longitude"]].mean().reset_index()
    route_info = (cl_prof.merge(catalog.drop(columns=["route_type", "borough"]), on="route_id", how="left")
                  .merge(route_static[["route_id", "route_speed_mph", "evasion_factor"]], on="route_id", how="left")
                  .merge(centroids, on="route_id", how="left"))
    route_info["route_long_name"] = route_info["route_long_name"].fillna(route_info["route_id"])
    route_info.to_parquet(P / "route_info.parquet", index=False)
    rh[HISTORY_COLS].to_parquet(P / "route_hour.parquet", index=False)
    trips.to_parquet(P / "trips.parquet", index=False)
    speeds_hourly.to_parquet(P / "speeds_hourly.parquet", index=False)
    paths[paths["route_id"].isin(route_info["route_id"])].to_parquet(P / "paths.parquet", index=False)
    stops.to_parquet(P / "stops.parquet", index=False)
    overlap.to_parquet(P / "overlap.parquet", index=False)
    valid_e[["route_id", "ts", "hour", "ridership", "pred", "perf_class"]].to_parquet(P / "validation_predictions.parquet", index=False)

    joblib.dump(enc, C.MODELS_DIR / "profile_encoder.joblib")
    joblib.dump(clf[clf["best"]]["model"], C.MODELS_DIR / "classifier.joblib")
    joblib.dump(reg[reg["best"]]["model"], C.MODELS_DIR / "forecaster.joblib")
    joblib.dump({k: cl[k] for k in ("kmeans", "dbscan", "scaler", "pca")}, C.MODELS_DIR / "clustering.joblib")
    # alternates kept for comparison in the app
    other_clf = "XGBoost" if clf["best"] == "RandomForest" else "RandomForest"
    joblib.dump(clf[other_clf]["model"], C.MODELS_DIR / f"classifier_{other_clf.lower()}.joblib", compress=3)

    figs = model_figures(cl_prof, cl["metrics"], clf, reg, valid_e)
    figs["architecture"] = architecture_diagram()
    figs["pipeline"] = pipeline_diagram()

    strip = lambda d: {k: v for k, v in d.items() if k not in ("model",)}  # noqa: E731
    metrics = {
        "clustering": cl["metrics"],
        "classification": {"best": clf["best"], "RandomForest": strip(clf["RandomForest"]),
                           "XGBoost": strip(clf["XGBoost"]), "feature_importance": clf["feature_importance"],
                           "class_distribution_train": train_e["perf_class"].value_counts().to_dict(),
                           "class_distribution_valid": valid_e["perf_class"].value_counts().to_dict()},
        "forecasting": {"best": reg["best"], "SeasonalProfileBaseline": reg["SeasonalProfileBaseline"],
                        "RandomForest": strip(reg["RandomForest"]), "XGBoost": strip(reg["XGBoost"]),
                        "feature_importance": reg["feature_importance"]},
        "optimisation_impact_validation": impact,
        "split": {"train_rows": int(len(train)), "valid_rows": int(len(valid)), "cutoff": str(cutoff.date()),
                  "train_start": str(train["date"].min().date()), "valid_end": str(valid["date"].max().date())},
        "figures": figs,
    }
    (C.METRICS_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    manifest = {
        "built_at_ist": datetime.now(C.IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        "data_start": str(rh["date"].min().date()), "data_end": str(rh["date"].max().date()),
        "last_timestamp_local": str(rh["ts"].max()),
        "granularity": "hourly",
        "routes": int(rh["route_id"].nunique()), "route_hours": int(len(rh)),
        "stage_seconds": stage_times, "total_seconds": round(time.time() - t0, 1),
        "sources": {k: {"id": s.dataset_id, "name": s.name, "url": s.url, "granularity": s.granularity,
                        "role": s.role} for k, s in C.SOURCES.items()},
        "raw_rows": {k: int(len(v)) for k, v in raw.items()},
        "assumptions": {"vehicle_capacity": C.VEHICLE_CAPACITY, "peak_load_factor": C.PEAK_LOAD_FACTOR,
                        "fare_evasion_rates": evasion, "threshold_quantiles": [C.UNDER_QUANTILE, C.OVER_QUANTILE],
                        "underutilized_max": C.UNDERUTILIZED_MAX, "overcrowded_min": C.OVERCROWDED_MIN,
                        "target_occupancy": C.TARGET_OCCUPANCY, "min_trips_per_hour": C.MIN_TRIPS_PER_HOUR,
                        "validation_days": C.VALIDATION_DAYS},
    }
    mark("10_persist")
    manifest["stage_seconds"] = stage_times
    (C.METRICS_DIR / "pipeline_manifest.json").write_text(json.dumps(manifest, indent=2))
    log.info("Pipeline finished in %.1f min", (time.time() - t0) / 60)
    return {"manifest": manifest, "metrics": metrics, "eda": eda_summary}


def main():
    """Command-line entry point (flags: --refresh, --skip-download)."""
    ap = argparse.ArgumentParser(description="RouteRanker training pipeline")
    ap.add_argument("--refresh", action="store_true", help="re-download every source")
    ap.add_argument("--skip-download", action="store_true", help="use cached raw parquet only")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run(download=not a.skip_download, refresh=a.refresh)


if __name__ == "__main__":
    main()
