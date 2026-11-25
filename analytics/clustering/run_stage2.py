"""
AI_RouteRanker - Phase 6.1 Stage 2 Canonical Pipeline Execution
Strictly follows the approved Phase 6.1 methodology:
  1. Equirectangular spatial projection of 11,020 boarding stops (location_type=0).
  2. Geographic stop clustering via DBSCAN (eps=300m, min_samples=2) with chaining diagnostics.
  3. Demand attribution, 5 headway windows, service span, and stop eligibility waterfall.
  4. Functional stop typology via KMeans (k in [3, 8], 5 features, StandardScaler, random_state=42).
  5. 5-seed sampled silhouette evaluation with noise exclusion and represented weighting.
  6. Individual transit hub ranking across Configs A, B, and C with sensitivity metrics.
  7. Peripheral and low-density coverage analysis.
Outputs are saved cleanly under artifacts/clustering/ and reports/clustering/.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import time
import json
import duckdb
import ctypes
import numpy as np
import pandas as pd

from analytics.clustering.spatial_projection import SpatialProjector
from analytics.clustering.demand_aggregator import (
    DemandAggregator,
    CANONICAL_SNAPSHOT_ID,
    REPRESENTATIVE_DATE,
    TIER2_TRAIN_START,
    TIER2_TRAIN_END,
    HEADWAY_WINDOWS,
)
from analytics.clustering.stop_clustering import StopClusterer
from analytics.clustering.evaluator import ClusteringEvaluator


def get_memory_status():
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ('dwLength', ctypes.c_ulong),
            ('dwMemoryLoad', ctypes.c_ulong),
            ('ullTotalPhys', ctypes.c_ulonglong),
            ('ullAvailPhys', ctypes.c_ulonglong),
            ('ullTotalPageFile', ctypes.c_ulonglong),
            ('ullAvailPageFile', ctypes.c_ulonglong),
            ('ullTotalVirtual', ctypes.c_ulonglong),
            ('ullAvailVirtual', ctypes.c_ulonglong),
            ('sullAvailExtendedVirtual', ctypes.c_ulonglong),
        ]
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    avail_mb = stat.ullAvailPhys / (1024 * 1024)
    return {
        "memory_load_pct": int(stat.dwMemoryLoad),
        "total_phys_mb": float(stat.ullTotalPhys / (1024 * 1024)),
        "avail_phys_mb": float(avail_mb),
    }


def check_memory_guard(stage_name: str):
    mem = get_memory_status()
    print(f"[{stage_name}] Memory Check: Avail {mem['avail_phys_mb']:.1f} MB, Load {mem['memory_load_pct']}%")
    if mem['avail_phys_mb'] < 600.0 or mem['memory_load_pct'] > 95:
        raise MemoryError(f"CRITICAL: Memory threshold exceeded at {stage_name}! Avail: {mem['avail_phys_mb']} MB, Load: {mem['memory_load_pct']}%")
    return mem


def run_stage2_pipeline():
    start_time = time.time()
    check_memory_guard("PIPELINE_START")

    # Output directories
    artifacts_dir = os.path.join("artifacts", "clustering")
    reports_dir = os.path.join("reports", "clustering")
    os.makedirs(artifacts_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    db_path = os.path.join("data", "processed", "ai_routeranker.duckdb")
    print(f"Connecting read-only to DuckDB: {db_path}")
    con = duckdb.connect(db_path, read_only=True)

    # -------------------------------------------------------------
    # 1. EXTRACT CANONICAL DATA
    # -------------------------------------------------------------
    print("--- 1. Extracting Canonical Data ---")
    # All 11,020 boarding stops
    stops_df = con.execute(f"""
        SELECT stop_id, stop_code, stop_name, stop_desc, stop_lat, stop_lon, location_type, parent_station
        FROM analytical.gtfs_stops
        WHERE snapshot_id = '{CANONICAL_SNAPSHOT_ID}' AND location_type = 0
        ORDER BY stop_id
    """).df()
    print(f"Extracted {len(stops_df)} boarding stops.")
    assert len(stops_df) == 11020, f"Expected 11,020 boarding stops, found {len(stops_df)}"

    # Active trips on representative service date 2026-06-10
    active_trips_df = con.execute(f"""
        WITH active_services AS (
            SELECT service_id
            FROM analytical.gtfs_calendar
            WHERE snapshot_id = '{CANONICAL_SNAPSHOT_ID}'
              AND wednesday = 1
              AND start_date <= '{REPRESENTATIVE_DATE}'
              AND end_date >= '{REPRESENTATIVE_DATE}'
              AND service_id NOT IN (
                  SELECT service_id 
                  FROM analytical.gtfs_calendar_dates 
                  WHERE snapshot_id = '{CANONICAL_SNAPSHOT_ID}' 
                    AND date = '{REPRESENTATIVE_DATE}' 
                    AND exception_type = 2
              )
            UNION
            SELECT service_id
            FROM analytical.gtfs_calendar_dates
            WHERE snapshot_id = '{CANONICAL_SNAPSHOT_ID}' 
              AND date = '{REPRESENTATIVE_DATE}' 
              AND exception_type = 1
        )
        SELECT t.trip_id, t.route_id, t.direction_id, t.service_id
        FROM analytical.gtfs_trips t
        JOIN active_services s ON t.service_id = s.service_id
        WHERE t.snapshot_id = '{CANONICAL_SNAPSHOT_ID}'
    """).df()
    print(f"Extracted {len(active_trips_df)} active trips on {REPRESENTATIVE_DATE}.")

    # Stop times for active trips at boarding stops
    stop_times_df = con.execute(f"""
        WITH active_services AS (
            SELECT service_id
            FROM analytical.gtfs_calendar
            WHERE snapshot_id = '{CANONICAL_SNAPSHOT_ID}'
              AND wednesday = 1
              AND start_date <= '{REPRESENTATIVE_DATE}'
              AND end_date >= '{REPRESENTATIVE_DATE}'
              AND service_id NOT IN (
                  SELECT service_id 
                  FROM analytical.gtfs_calendar_dates 
                  WHERE snapshot_id = '{CANONICAL_SNAPSHOT_ID}' 
                    AND date = '{REPRESENTATIVE_DATE}' 
                    AND exception_type = 2
              )
            UNION
            SELECT service_id
            FROM analytical.gtfs_calendar_dates
            WHERE snapshot_id = '{CANONICAL_SNAPSHOT_ID}' 
              AND date = '{REPRESENTATIVE_DATE}' 
              AND exception_type = 1
        ),
        act_trips AS (
            SELECT t.trip_id, t.route_id, t.direction_id
            FROM analytical.gtfs_trips t
            JOIN active_services s ON t.service_id = s.service_id
            WHERE t.snapshot_id = '{CANONICAL_SNAPSHOT_ID}'
        )
        SELECT 
            st.stop_id,
            st.trip_id,
            tr.route_id,
            tr.direction_id,
            st.arrival_seconds,
            st.departure_seconds
        FROM analytical.gtfs_stop_times st
        JOIN act_trips tr ON st.trip_id = tr.trip_id
        JOIN analytical.gtfs_stops s ON st.stop_id = s.stop_id
        WHERE st.snapshot_id = '{CANONICAL_SNAPSHOT_ID}'
          AND s.snapshot_id = '{CANONICAL_SNAPSHOT_ID}'
          AND s.location_type = 0
    """).df()
    print(f"Extracted {len(stop_times_df)} scheduled stop visits.")

    # Mapped routes (exact matches)
    route_mapping_df = con.execute(f"""
        SELECT ridership_route, gtfs_route_id
        FROM analytical.route_mapping
        WHERE snapshot_id = '{CANONICAL_SNAPSHOT_ID}' AND match_status = 'exact_match'
    """).df()
    mapped_routes_set = set(route_mapping_df["gtfs_route_id"].unique())
    print(f"Confirmed {len(mapped_routes_set)} exact-match mapped routes.")

    # Tier 2 demand (average daily ridership by route between 2025-11-23 and 2026-04-23)
    route_demand_df = con.execute(f"""
        WITH mapped AS (
            SELECT ridership_route, gtfs_route_id
            FROM analytical.route_mapping
            WHERE snapshot_id = '{CANONICAL_SNAPSHOT_ID}' AND match_status = 'exact_match'
        ),
        t2_rides AS (
            SELECT route, avg(rides) as mean_daily_rides
            FROM analytical.cta_ridership_clean
            WHERE date >= '{TIER2_TRAIN_START}' AND date <= '{TIER2_TRAIN_END}'
            GROUP BY route
        )
        SELECT m.gtfs_route_id as route_id, t2.mean_daily_rides
        FROM mapped m
        JOIN t2_rides t2 ON m.ridership_route = t2.route
    """).df()
    print(f"Computed Tier 2 demand for {len(route_demand_df)} mapped routes.")
    con.close()

    check_memory_guard("DATA_EXTRACTED")

    # -------------------------------------------------------------
    # 2. SPATIAL PROJECTION
    # -------------------------------------------------------------
    print("--- 2. Executing Spatial Projection ---")
    projector = SpatialProjector()
    x_coords, y_coords = projector.forward(stops_df["stop_lat"].values, stops_df["stop_lon"].values)
    stops_df["proj_x"] = x_coords
    stops_df["proj_y"] = y_coords

    # Compute bounding-box and sample distortion metrics
    lat_min, lat_max = stops_df["stop_lat"].min(), stops_df["stop_lat"].max()
    lon_min, lon_max = stops_df["stop_lon"].min(), stops_df["stop_lon"].max()
    print(f"Coordinate Bounding Box: Lat [{lat_min:.6f}, {lat_max:.6f}], Lon [{lon_min:.6f}, {lon_max:.6f}]")
    
    # Measure sample distortion on 1,000 random stop pairs to verify empirical distortion
    np.random.seed(42)
    sample_indices = np.random.choice(len(stops_df), size=(1000, 2), replace=False)
    sample_errors = []
    for idx1, idx2 in sample_indices:
        _, _, err = projector.calculate_distortion(
            stops_df.loc[idx1, "stop_lat"], stops_df.loc[idx1, "stop_lon"],
            stops_df.loc[idx2, "stop_lat"], stops_df.loc[idx2, "stop_lon"]
        )
        sample_errors.append(err)
    sample_errors = np.array(sample_errors)
    distortion_stats = {
        "sample_size": len(sample_errors),
        "mean_distortion_pct": float(np.mean(sample_errors)),
        "median_distortion_pct": float(np.median(sample_errors)),
        "max_sample_distortion_pct": float(np.max(sample_errors)),
        "bounding_box_baseline_pct": 0.3373,
    }
    print(f"Distortion Sample (N=1000): Mean={distortion_stats['mean_distortion_pct']:.4f}%, Max={distortion_stats['max_sample_distortion_pct']:.4f}%")

    # -------------------------------------------------------------
    # 3. GEOGRAPHIC DBSCAN CLUSTERING
    # -------------------------------------------------------------
    print("--- 3. Executing Geographic DBSCAN Clustering ---")
    clusterer = StopClusterer(eps=300.0, min_samples=2)
    dbscan_labels, dbscan_diag_dict = clusterer.run_spatial_dbscan(
        x_coords=stops_df["proj_x"].values,
        y_coords=stops_df["proj_y"].values,
        eps=300.0,
        min_samples=2
    )
    stops_df["dbscan_cluster"] = dbscan_labels

    # Convert diagnostic dict to DataFrame
    chaining_df = pd.DataFrame.from_dict(dbscan_diag_dict, orient="index")
    
    n_dbscan_clusters = len(chaining_df)
    n_noise_stops = int((stops_df["dbscan_cluster"] == -1).sum())
    n_clustered_stops = int((stops_df["dbscan_cluster"] != -1).sum())
    n_chained_clusters = int(chaining_df["is_chained"].sum()) if "is_chained" in chaining_df.columns else 0
    print(f"DBSCAN Results: {n_dbscan_clusters} valid clusters, {n_noise_stops} noise stops, {n_clustered_stops} clustered stops.")
    print(f"Chaining Diagnostics: {n_chained_clusters} clusters flagged with chaining warning.")

    check_memory_guard("DBSCAN_COMPLETED")

    # -------------------------------------------------------------
    # 4. SERVICE FEATURES, HEADWAYS, & DEMAND ATTRIBUTION
    # -------------------------------------------------------------
    print("--- 4. Computing Service Features & Demand Attribution ---")
    # Stop-route visits on representative date
    stop_route_visits = stop_times_df.groupby(["stop_id", "route_id"]).size().reset_index(name="visits")

    # Run demand attribution
    demand_summary_df = DemandAggregator.compute_route_stop_demand_attribution(
        stop_visits_df=stop_route_visits,
        route_demand_df=route_demand_df,
        mapped_routes=mapped_routes_set,
    )

    # Compute headways for all 5 windows
    headway_dfs = {}
    for w_name in HEADWAY_WINDOWS.keys():
        hw_w = DemandAggregator.calculate_headways_for_window(stop_times_df, w_name)
        headway_dfs[w_name] = hw_w

    # Merge all headway metrics onto demand summary
    feature_master = demand_summary_df.copy()
    for w_name, hw_w in headway_dfs.items():
        feature_master = feature_master.merge(hw_w, on="stop_id", how="left")

    # Service span hours: (max_departure - min_arrival) / 3600 per stop
    span_df = stop_times_df.groupby("stop_id").agg(
        min_arr=("arrival_seconds", "min"),
        max_dep=("departure_seconds", "max")
    ).reset_index()
    span_df["service_span_hours"] = (span_df["max_dep"] - span_df["min_arr"]) / 3600.0
    feature_master = feature_master.merge(span_df[["stop_id", "service_span_hours"]], on="stop_id", how="left")

    # Add stops with 0 visits back into feature_master so all 11,020 stops are accounted for
    all_stops_base = stops_df[["stop_id"]].copy()
    feature_master = all_stops_base.merge(feature_master, on="stop_id", how="left")
    feature_master["total_visits"] = feature_master["total_visits"].fillna(0).astype(int)
    feature_master["routes_served"] = feature_master["routes_served"].fillna(0).astype(int)
    feature_master["mapped_routes_served"] = feature_master["mapped_routes_served"].fillna(0).astype(int)
    feature_master["unmapped_routes_served"] = feature_master["unmapped_routes_served"].fillna(0).astype(int)
    feature_master["mapped_visits"] = feature_master["mapped_visits"].fillna(0).astype(int)
    feature_master["unmapped_visits"] = feature_master["unmapped_visits"].fillna(0).astype(int)
    feature_master["demand_coverage_status"] = feature_master["demand_coverage_status"].fillna("UNAVAILABLE")
    feature_master["service_span_hours"] = feature_master["service_span_hours"].fillna(0.0)

    # Compute demand intensity proxy
    feature_master["demand_intensity"] = feature_master.apply(
        lambda r: DemandAggregator.compute_demand_intensity(r["attributed_demand"], r["mapped_visits"]),
        axis=1
    )

    # Conservation verification
    total_attributed_demand = float(feature_master["attributed_demand"].sum(skipna=True))
    total_mapped_route_demand = float(route_demand_df["mean_daily_rides"].sum())
    demand_conservation_delta = abs(total_attributed_demand - total_mapped_route_demand)
    print(f"Demand Conservation: Total Attributed={total_attributed_demand:.2f}, Total Route={total_mapped_route_demand:.2f}, Delta={demand_conservation_delta:.4f}")

    # -------------------------------------------------------------
    # 5. STOP ELIGIBILITY WATERFALL
    # -------------------------------------------------------------
    print("--- 5. Executing Stop Eligibility Waterfall ---")
    feature_master, eligibility_summary = DemandAggregator.classify_stop_eligibility(feature_master)
    print("Eligibility Waterfall Table:")
    for cat, vals in eligibility_summary["table"].items():
        print(f"  - {cat}: {vals['count']} ({vals['percentage']:.2f}%)")
    assert eligibility_summary["is_fully_reconciled"], "Eligibility summary failed reconciliation!"

    # Combine spatial and service features
    stops_full = stops_df.merge(feature_master, on="stop_id", how="left")

    check_memory_guard("ELIGIBILITY_COMPLETED")

    # -------------------------------------------------------------
    # 6. FUNCTIONAL KMEANS & SILHOUETTE EVALUATION
    # -------------------------------------------------------------
    print("--- 6. Executing Functional KMeans & Silhouette Evaluation ---")
    eligible_mask = (stops_full["primary_eligibility_status"] == "ELIGIBLE")
    eligible_stops = stops_full[eligible_mask].copy().reset_index(drop=True)
    n_eligible = len(eligible_stops)
    print(f"Eligible population for KMeans: {n_eligible} stops.")

    # Prepare 5 functional features:
    # 1. ln(total_visits + 1)
    # 2. routes_served
    # 3. am_peak_headway (mean_headway_interval_weighted_am_peak)
    # 4. attributed_demand
    # 5. service_span_hours
    feature_cols = [
        "log_visits",
        "routes_served",
        "mean_headway_interval_weighted_am_peak",
        "attributed_demand",
        "service_span_hours"
    ]
    eligible_stops["log_visits"] = np.log1p(eligible_stops["total_visits"].values)

    raw_kmeans_matrix = eligible_stops[feature_cols].values
    assert not np.isnan(raw_kmeans_matrix).any(), "NaN found in eligible KMeans features!"

    # Fit candidate K in [3, 8]
    kmeans_results = clusterer.evaluate_kmeans_candidates(
        raw_features=raw_kmeans_matrix,
        candidate_k=list(range(3, 9))
    )
    scaled_kmeans_matrix = kmeans_results["scaled_features"]

    # Evaluate silhouettes using ClusteringEvaluator
    evaluator = ClusteringEvaluator()
    eval_rows = []
    for k_val in range(3, 9):
        cand = kmeans_results["candidates"][k_val]
        labels = cand["labels"]
        inertia = cand["inertia"]
        sil_res = evaluator.evaluate_sampled_silhouette(
            X=scaled_kmeans_matrix,
            labels=labels,
            sample_size=3000,
            seeds=ClusteringEvaluator.APPROVED_SEEDS
        )
        eval_rows.append({
            "k": k_val,
            "inertia": inertia,
            "status": sil_res["status"],
            "silhouette_mean": sil_res["mean_score"],
            "silhouette_std": sil_res["score_std"],
            "score_min": sil_res["score_range"][0],
            "score_max": sil_res["score_range"][1],
            "unweighted_reference_mean": sil_res["unweighted_reference_mean"],
            "n_represented_stops": sil_res["n_represented_stops"],
            "cluster_sizes": cand["cluster_sizes"]
        })
        print(f"  - K={k_val}: Inertia={inertia:.2f}, Silhouette Mean={sil_res['mean_score']:.4f} +/- {sil_res['score_std']:.4f}, Status={sil_res['status']}")

    eval_summary = pd.DataFrame(eval_rows)

    # Attach all K cluster assignments to eligible stops
    for k_val in range(3, 9):
        eligible_stops[f"kmeans_k{k_val}"] = kmeans_results["candidates"][k_val]["labels"]
        stops_full[f"kmeans_k{k_val}"] = np.nan
        stops_full.loc[eligible_mask, f"kmeans_k{k_val}"] = kmeans_results["candidates"][k_val]["labels"]

    check_memory_guard("KMEANS_COMPLETED")

    # -------------------------------------------------------------
    # 7. TRANSIT HUB RANKINGS (CONFIGS A, B, C)
    # -------------------------------------------------------------
    print("--- 7. Computing Transit Hub Rankings ---")
    ranked_eligible = evaluator.compute_hub_rankings(eligible_stops)
    hub_sensitivity = evaluator.evaluate_hub_sensitivity(ranked_eligible)

    # Merge ranking columns back
    ranking_cols = [
        "score_config_a", "rank_config_a",
        "score_config_b", "rank_config_b",
        "score_config_c", "rank_config_c"
    ]
    for col in ranking_cols:
        eligible_stops[col] = ranked_eligible[col]
        stops_full[col] = np.nan
        stops_full.loc[eligible_mask, col] = ranked_eligible[col]

    print(f"Hub Spearman Rank Correlations: r_s(A, B)={hub_sensitivity['spearman_rank_corr_a_b']:.4f}, r_s(A, C)={hub_sensitivity['spearman_rank_corr_a_c']:.4f}, r_s(B, C)={hub_sensitivity['spearman_rank_corr_b_c']:.4f}")
    print(f"Top 100 Jaccard Overlaps: J(A, B)={hub_sensitivity['top100_jaccard_a_b']:.4f}, J(A, C)={hub_sensitivity['top100_jaccard_a_c']:.4f}, J(B, C)={hub_sensitivity['top100_jaccard_b_c']:.4f}")

    # Top candidate hubs (Score >= 90 AND routes_served >= 5)
    # Note: score_config is 0.0 - 1.0; 90 corresponds to score >= 0.90
    candidate_hubs_a = eligible_stops[(eligible_stops["score_config_a"] >= 0.90) & (eligible_stops["routes_served"] >= 5)]
    candidate_hubs_b = eligible_stops[(eligible_stops["score_config_b"] >= 0.90) & (eligible_stops["routes_served"] >= 5)]
    candidate_hubs_c = eligible_stops[(eligible_stops["score_config_c"] >= 0.90) & (eligible_stops["routes_served"] >= 5)]
    print(f"Candidate Hubs Identified (Score>=0.90, Routes>=5): Config A: {len(candidate_hubs_a)}, Config B: {len(candidate_hubs_b)}, Config C: {len(candidate_hubs_c)}")

    # -------------------------------------------------------------
    # 8. PERIPHERAL & LOW-DENSITY COVERAGE ANALYSIS
    # -------------------------------------------------------------
    print("--- 8. Executing Peripheral & Low-Density Coverage Analysis ---")
    # Distance from network center of gravity
    cog_x, cog_y = stops_full["proj_x"].mean(), stops_full["proj_y"].mean()
    stops_full["dist_to_center_km"] = np.sqrt((stops_full["proj_x"] - cog_x)**2 + (stops_full["proj_y"] - cog_y)**2) / 1000.0

    # Categorize unclustered stops
    unclustered_df = stops_full[stops_full["dbscan_cluster"] == -1].copy()
    zero_visits_df = stops_full[stops_full["total_visits"] == 0].copy()
    unavailable_demand_df = stops_full[stops_full["primary_eligibility_status"] == "EXCLUDED_UNAVAILABLE_DEMAND"].copy()
    no_am_headway_df = stops_full[stops_full["primary_eligibility_status"] == "EXCLUDED_NO_AM_HEADWAY"].copy()

    coverage_metrics = {
        "total_stops": len(stops_full),
        "unclustered_noise_stops": len(unclustered_df),
        "unclustered_pct": float(len(unclustered_df) / len(stops_full) * 100.0),
        "zero_visit_stops": len(zero_visits_df),
        "zero_visit_pct": float(len(zero_visits_df) / len(stops_full) * 100.0),
        "unavailable_demand_stops": len(unavailable_demand_df),
        "unavailable_demand_pct": float(len(unavailable_demand_df) / len(stops_full) * 100.0),
        "no_am_headway_stops": len(no_am_headway_df),
        "no_am_headway_pct": float(len(no_am_headway_df) / len(stops_full) * 100.0),
        "mean_dist_to_center_km": float(stops_full["dist_to_center_km"].mean()),
        "max_dist_to_center_km": float(stops_full["dist_to_center_km"].max()),
        "p90_dist_to_center_km": float(stops_full["dist_to_center_km"].quantile(0.90)),
        "p95_dist_to_center_km": float(stops_full["dist_to_center_km"].quantile(0.95)),
    }
    print(f"Coverage Metrics: {coverage_metrics['unclustered_noise_stops']} noise stops ({coverage_metrics['unclustered_pct']:.2f}%), "
          f"{coverage_metrics['zero_visit_stops']} zero-visit stops ({coverage_metrics['zero_visit_pct']:.2f}%), "
          f"P95 distance to center: {coverage_metrics['p95_dist_to_center_km']:.2f} km")

    check_memory_guard("COVERAGE_COMPLETED")

    # -------------------------------------------------------------
    # 9. OUTPUT GENERATION & PERSISTENCE
    # -------------------------------------------------------------
    print("--- 9. Saving Analytical Outputs ---")

    # 1. Spatial DBSCAN assignments and chaining diagnostics
    stops_full[[
        "stop_id", "stop_name", "stop_lat", "stop_lon", "proj_x", "proj_y", "dbscan_cluster"
    ]].to_parquet(os.path.join(artifacts_dir, "spatial_dbscan_assignments.parquet"), index=False)
    chaining_df.to_parquet(os.path.join(artifacts_dir, "dbscan_chaining_diagnostics.parquet"), index=False)

    # 2. Stop-level feature master with demand, headway, and eligibility
    stops_full.to_parquet(os.path.join(artifacts_dir, "stop_level_feature_master.parquet"), index=False)

    # 3. Functional KMeans assignments and candidate evaluation
    eval_summary.to_csv(os.path.join(artifacts_dir, "kmeans_candidate_evaluation.csv"), index=False)
    eligible_stops[[
        "stop_id", "stop_name", "total_visits", "routes_served", "mean_headway_interval_weighted_am_peak",
        "attributed_demand", "service_span_hours", "log_visits",
        "kmeans_k3", "kmeans_k4", "kmeans_k5", "kmeans_k6", "kmeans_k7", "kmeans_k8"
    ]].to_parquet(os.path.join(artifacts_dir, "kmeans_cluster_assignments.parquet"), index=False)

    # 4. Hub rankings for configurations A, B, and C
    eligible_stops[[
        "stop_id", "stop_name", "stop_lat", "stop_lon", "total_visits", "routes_served",
        "attributed_demand", "demand_intensity",
        "score_config_a", "rank_config_a",
        "score_config_b", "rank_config_b",
        "score_config_c", "rank_config_c",
    ]].to_parquet(os.path.join(artifacts_dir, "transit_hub_rankings.parquet"), index=False)

    # Top 100 summaries as CSVs for human inspection
    for cfg in ["a", "b", "c"]:
        top100_cfg = eligible_stops.sort_values(f"rank_config_{cfg}").head(100)[[
            f"rank_config_{cfg}", "stop_id", "stop_name", f"score_config_{cfg}",
            "total_visits", "routes_served", "attributed_demand", "demand_intensity"
        ]]
        top100_cfg.to_csv(os.path.join(artifacts_dir, f"top100_hubs_config_{cfg}.csv"), index=False)

    # 5. Peripheral and low-density coverage analysis
    unclustered_df[[
        "stop_id", "stop_name", "stop_lat", "stop_lon", "proj_x", "proj_y",
        "dist_to_center_km", "total_visits", "routes_served", "primary_eligibility_status"
    ]].to_parquet(os.path.join(artifacts_dir, "peripheral_and_noise_stops.parquet"), index=False)

    # 6. Pipeline execution metadata
    total_elapsed = time.time() - start_time
    pipeline_metadata = {
        "snapshot_id": CANONICAL_SNAPSHOT_ID,
        "representative_service_date": REPRESENTATIVE_DATE,
        "demand_attribution_period": f"{TIER2_TRAIN_START} to {TIER2_TRAIN_END}",
        "boarding_stops_input_count": len(stops_df),
        "active_stop_visits_count": len(stop_times_df),
        "dbscan_parameters": {"eps_meters": 300.0, "min_samples": 2, "noise_label": -1},
        "dbscan_cluster_count": n_dbscan_clusters,
        "dbscan_noise_stop_count": n_noise_stops,
        "dbscan_chained_cluster_count": n_chained_clusters,
        "kmeans_parameters": {
            "features": feature_cols,
            "candidates": list(range(3, 9)),
            "scaler": "StandardScaler",
            "random_state": 42,
            "n_init": 10
        },
        "kmeans_eligible_stops_count": n_eligible,
        "silhouette_parameters": {
            "seeds": [42, 101, 2024, 777, 9999],
            "sample_size": 3000,
            "noise_excluded": True
        },
        "hub_ranking_sensitivity": hub_sensitivity,
        "distortion_statistics": distortion_stats,
        "coverage_metrics": coverage_metrics,
        "demand_conservation": {
            "total_attributed_demand": total_attributed_demand,
            "total_mapped_route_demand": total_mapped_route_demand,
            "delta": demand_conservation_delta
        },
        "execution_time_seconds": total_elapsed,
        "final_memory_status": get_memory_status()
    }

    with open(os.path.join(artifacts_dir, "phase6_1_stage2_metadata.json"), "w") as f:
        json.dump(pipeline_metadata, f, indent=2)

    print(f"--- Pipeline Execution Completed in {total_elapsed:.2f} seconds ---")
    return pipeline_metadata


if __name__ == "__main__":
    run_stage2_pipeline()
