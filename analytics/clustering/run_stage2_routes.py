"""
AI_RouteRanker - Phase 6.2 Stage 2 Canonical Real-Data Experiment
Executes the approved Phase 6.2 methodology on canonical GTFS Chicago transit data:
  Pillar A: Spatial Route Corridor Similarity (100m buffer overlap & discrete Fréchet distance)
  Pillar B: Shared-Stop & Network Route Connectivity (Jaccard & consecutive physical stop sequences)
  Pillar C: Route-Level Operational Typology (KMeans K in [3, 7] across 5 operational features)
Saves outputs under artifacts/route_clustering/ and reports memory checkpoints throughout.
"""

import os
import sys
import time
import json
import inspect
import duckdb
import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from analytics.clustering.spatial_projection import SpatialProjector
from analytics.clustering.route_geometry import RouteGeometryExtractor
from analytics.clustering.route_similarity import RouteSimilarityEngine
from analytics.clustering.route_connectivity import RouteConnectivityAnalyzer
from analytics.clustering.route_features import RouteFeatureExtractor
from analytics.clustering.route_evaluator import RouteEvaluator
from analytics.clustering.route_experiment import RouteExperimentConfig, RouteExperimentOrchestrator


def run_phase6_2_stage2():
    start_time = time.time()
    print("=" * 80)
    print("AI_RouteRanker - PHASE 6.2 STAGE 2 CANONICAL EXPERIMENT EXECUTION")
    print("=" * 80)

    # 1. Initialize configuration and orchestrator
    config = RouteExperimentConfig()
    orchestrator = RouteExperimentOrchestrator(config)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    output_dir = os.path.join(project_root, "artifacts", "route_clustering")
    os.makedirs(output_dir, exist_ok=True)
    print(f"Artifacts output directory: {output_dir}")

    # Check memory guard at start
    mem_init = orchestrator.check_memory_guard("Experiment Initialization")
    print(f"Initial Memory: Avail={mem_init['avail_phys_mb']:.1f} MB, Load={mem_init['memory_load_pct']}%")

    # Connect read-only to DuckDB
    con = orchestrator.get_readonly_connection()
    print(f"Connected read-only to DuckDB store.")

    # -------------------------------------------------------------------------
    # STEP 1: CANONICAL DATA EXTRACTION & W-01 SAFEGUARD
    # -------------------------------------------------------------------------
    print("\n--- STEP 1: CANONICAL DATA EXTRACTION ---")
    
    # 1.1 All 133 GTFS routes in canonical snapshot
    routes_df = con.execute(f"""
        SELECT route_id, route_short_name, route_long_name, route_type
        FROM analytical.gtfs_routes
        WHERE snapshot_id = '{config.SNAPSHOT_ID}'
        ORDER BY route_type, route_id
    """).df()
    print(f"Total canonical routes: {len(routes_df)} (Bus={int((routes_df['route_type'] == 3).sum())}, Rail={int((routes_df['route_type'] == 1).sum())})")
    assert len(routes_df) == 133, f"Expected 133 routes, found {len(routes_df)}!"

    # 1.2 Active trips on canonical representative service date (2026-06-10)
    active_trips_df = con.execute(f"""
        WITH active_services AS (
            SELECT service_id
            FROM analytical.gtfs_calendar
            WHERE snapshot_id = '{config.SNAPSHOT_ID}'
              AND wednesday = 1
              AND start_date <= '{config.REPRESENTATIVE_DATE}'
              AND end_date >= '{config.REPRESENTATIVE_DATE}'
              AND service_id NOT IN (
                  SELECT service_id 
                  FROM analytical.gtfs_calendar_dates 
                  WHERE snapshot_id = '{config.SNAPSHOT_ID}' 
                    AND date = '{config.REPRESENTATIVE_DATE}' 
                    AND exception_type = 2
              )
            UNION
            SELECT service_id
            FROM analytical.gtfs_calendar_dates
            WHERE snapshot_id = '{config.SNAPSHOT_ID}' 
              AND date = '{config.REPRESENTATIVE_DATE}' 
              AND exception_type = 1
        )
        SELECT t.trip_id, t.route_id, t.direction_id, t.shape_id, t.service_id
        FROM analytical.gtfs_trips t
        JOIN active_services s ON t.service_id = s.service_id
        WHERE t.snapshot_id = '{config.SNAPSHOT_ID}'
    """).df()
    print(f"Extracted {len(active_trips_df)} active trips on {config.REPRESENTATIVE_DATE}.")

    # --- CRITICAL W-01 SAFEGUARD IMPLEMENTATION & ASSERTION ---
    active_trips_df["service_date"] = config.REPRESENTATIVE_DATE
    assert "service_date" in active_trips_df.columns, "W-01 Failure: service_date column missing from active_trips_df!"
    assert (active_trips_df["service_date"] == config.REPRESENTATIVE_DATE).all(), f"W-01 Failure: Trips found with date != {config.REPRESENTATIVE_DATE}!"
    assert active_trips_df["service_date"].nunique() == 1, "W-01 Failure: Multiple service dates detected in active_trips_df!"
    hw_source = inspect.getsource(RouteFeatureExtractor._calculate_route_am_headway)
    assert "service_date" in hw_source, "W-01 Failure: RouteFeatureExtractor source does not group by service_date!"
    print("W-01 SAFEGUARD PASSED: Canonical single service date '2026-06-10' verified across all active trips.")

    # 1.3 Active stop times at physical boarding stops (location_type = 0)
    stop_times_df = con.execute(f"""
        WITH active_services AS (
            SELECT service_id
            FROM analytical.gtfs_calendar
            WHERE snapshot_id = '{config.SNAPSHOT_ID}'
              AND wednesday = 1
              AND start_date <= '{config.REPRESENTATIVE_DATE}'
              AND end_date >= '{config.REPRESENTATIVE_DATE}'
              AND service_id NOT IN (
                  SELECT service_id 
                  FROM analytical.gtfs_calendar_dates 
                  WHERE snapshot_id = '{config.SNAPSHOT_ID}' 
                    AND date = '{config.REPRESENTATIVE_DATE}' 
                    AND exception_type = 2
              )
            UNION
            SELECT service_id
            FROM analytical.gtfs_calendar_dates
            WHERE snapshot_id = '{config.SNAPSHOT_ID}' 
              AND date = '{config.REPRESENTATIVE_DATE}' 
              AND exception_type = 1
        ),
        act_trips AS (
            SELECT t.trip_id, t.route_id, t.direction_id
            FROM analytical.gtfs_trips t
            JOIN active_services s ON t.service_id = s.service_id
            WHERE t.snapshot_id = '{config.SNAPSHOT_ID}'
        )
        SELECT 
            st.trip_id,
            st.stop_id,
            st.stop_sequence,
            st.arrival_seconds,
            st.departure_seconds,
            tr.route_id,
            tr.direction_id
        FROM analytical.gtfs_stop_times st
        JOIN act_trips tr ON st.trip_id = tr.trip_id
        JOIN analytical.gtfs_stops s ON st.stop_id = s.stop_id
        WHERE st.snapshot_id = '{config.SNAPSHOT_ID}'
          AND s.snapshot_id = '{config.SNAPSHOT_ID}'
          AND s.location_type = 0
        ORDER BY st.trip_id, st.stop_sequence
    """).df()
    print(f"Extracted {len(stop_times_df)} scheduled physical boarding stop visits.")

    # 1.4 Supplementary ridership (descriptive only)
    ridership_df = con.execute(f"""
        WITH mapped AS (
            SELECT DISTINCT ridership_route, gtfs_route_id
            FROM analytical.route_mapping
            WHERE match_status = 'exact_match'
        ),
        rides AS (
            SELECT route, avg(rides) as mean_daily_rides
            FROM analytical.cta_ridership_clean
            WHERE daytype = 'W'
              AND date >= '2025-11-01'
              AND date <= '2026-05-31'
            GROUP BY route
        )
        SELECT m.gtfs_route_id as route_id, r.mean_daily_rides
        FROM mapped m
        JOIN rides r ON m.ridership_route = r.route
    """).df()
    print(f"Extracted supplementary ridership for {len(ridership_df)} mapped routes.")

    orchestrator.check_memory_guard("Post Data Extraction")

    # -------------------------------------------------------------------------
    # STEP 2: PILLAR A — SPATIAL ROUTE CORRIDOR SIMILARITY
    # -------------------------------------------------------------------------
    print("\n--- STEP 2: PILLAR A — SPATIAL CORRIDOR SIMILARITY ---")
    geom_extractor = RouteGeometryExtractor(target_downsample_dist=config.DOWNSAMPLE_SPACING_METERS)
    
    # Select representative shape for each route-direction
    rep_shapes_df, shape_exclusions_df = geom_extractor.select_representative_shapes(active_trips_df)
    n_patterns = len(rep_shapes_df)
    print(f"Identified {n_patterns} active route-direction patterns (Exclusions: {len(shape_exclusions_df)}).")

    # Fetch shape coordinate points for all representative shapes
    rep_shape_ids = rep_shapes_df["representative_shape_id"].unique().tolist()
    shape_ids_str = "', '".join(rep_shape_ids)
    all_shapes_df = con.execute(f"""
        SELECT shape_id, shape_pt_lat, shape_pt_lon, shape_pt_sequence
        FROM analytical.gtfs_shapes
        WHERE snapshot_id = '{config.SNAPSHOT_ID}'
          AND shape_id IN ('{shape_ids_str}')
        ORDER BY shape_id, shape_pt_sequence
    """).df()
    print(f"Fetched {len(all_shapes_df)} raw shape points across {len(rep_shape_ids)} representative shapes.")

    # Process, project, and downsample each shape
    geometries = {}
    geom_meta_rows = []
    route_dir_lengths = {}

    for _, row in rep_shapes_df.iterrows():
        r_id = str(row["route_id"])
        d_id = int(row["direction_id"])
        s_id = str(row["representative_shape_id"])
        pattern_id = f"{r_id}__dir_{d_id}"

        shape_points = all_shapes_df[all_shapes_df["shape_id"] == s_id].copy()
        if len(shape_points) < 2:
            print(f"Warning: Shape {s_id} has < 2 points for pattern {pattern_id}!")
            continue

        downsampled_coords, meta = geom_extractor.process_and_project_shape(shape_points)
        geometries[pattern_id] = downsampled_coords
        route_dir_lengths[pattern_id] = meta["total_length_meters"] / 1000.0

        geom_meta_rows.append({
            "pattern_id": pattern_id,
            "route_id": r_id,
            "direction_id": d_id,
            "representative_shape_id": s_id,
            "scheduled_trip_count": int(row["trip_count"]),
            "total_route_dir_trips": int(row["total_route_dir_trips"]),
            "shape_coverage_ratio": float(row["shape_coverage_ratio"]),
            "alternative_shapes_count": int(row["alternative_shapes_count"]),
            "raw_point_count": int(meta["raw_point_count"]),
            "downsampled_point_count": int(meta["downsampled_point_count"]),
            "length_km": float(meta["total_length_meters"] / 1000.0),
        })

    geometries_metadata_df = pd.DataFrame(geom_meta_rows)
    print(f"Successfully processed {len(geometries)} route-direction trajectories.")

    orchestrator.check_memory_guard("Post Geometry Processing")

    # Compute pairwise similarity and distance matrices
    print("Computing pairwise 100m buffer overlap and discrete Fréchet distance matrices...")
    t_sim_0 = time.time()
    similarity_matrices = RouteSimilarityEngine.compute_pairwise_similarity_matrices(
        geometries,
        buffer_radius=config.BUFFER_RADIUS_METERS
    )
    t_sim_1 = time.time()
    print(f"Pairwise similarity computation completed in {t_sim_1 - t_sim_0:.2f}s.")

    pattern_ids = similarity_matrices["pattern_ids"]
    buf_overlap_mat = similarity_matrices["buffer_overlap_matrix"]
    buf_dist_mat = similarity_matrices["buffer_distance_matrix"]
    frechet_dist_mat = similarity_matrices["frechet_distance_matrix"]

    # Hierarchical corridor clustering on Buffer Distance Matrix
    print("Evaluating Hierarchical Agglomerative Clustering on Buffer Distance Matrix...")
    buf_eval = RouteEvaluator.evaluate_hierarchical_corridors(
        distance_matrix=buf_dist_mat,
        pattern_ids=pattern_ids,
        k_values=config.CORRIDOR_K_RANGE,
        linkage="average"
    )
    buf_eval_summary = buf_eval["evaluation_summary"].copy()
    buf_eval_summary["metric"] = "BUFFER_OVERLAP_100M"

    # Hierarchical corridor clustering on Fréchet Distance Matrix
    print("Evaluating Hierarchical Agglomerative Clustering on Discrete Fréchet Distance Matrix...")
    fre_eval = RouteEvaluator.evaluate_hierarchical_corridors(
        distance_matrix=frechet_dist_mat,
        pattern_ids=pattern_ids,
        k_values=config.CORRIDOR_K_RANGE,
        linkage="average"
    )
    fre_eval_summary = fre_eval["evaluation_summary"].copy()
    fre_eval_summary["metric"] = "DISCRETE_FRECHET"

    corridor_eval_summary = pd.concat([buf_eval_summary, fre_eval_summary], ignore_index=True)
    print("Corridor clustering evaluation summary:")
    print(corridor_eval_summary.to_string(index=False))

    # Compile corridor cluster assignments for each evaluated K
    corridor_assignments_rows = []
    for idx, p_id in enumerate(pattern_ids):
        r_id, d_id = p_id.split("__dir_")
        row_dict = {
            "pattern_id": p_id,
            "route_id": r_id,
            "direction_id": int(d_id),
        }
        for k in config.CORRIDOR_K_RANGE:
            if k in buf_eval["candidate_results"]:
                row_dict[f"cluster_buffer_k{k}"] = int(buf_eval["candidate_results"][k]["labels"][idx])
            if k in fre_eval["candidate_results"]:
                row_dict[f"cluster_frechet_k{k}"] = int(fre_eval["candidate_results"][k]["labels"][idx])
        corridor_assignments_rows.append(row_dict)
    corridor_assignments_df = pd.DataFrame(corridor_assignments_rows)

    orchestrator.check_memory_guard("Post Pillar A Corridor Clustering")

    # -------------------------------------------------------------------------
    # STEP 3: PILLAR B — SHARED-STOP & ROUTE CONNECTIVITY
    # -------------------------------------------------------------------------
    print("\n--- STEP 3: PILLAR B — SHARED-STOP & ROUTE CONNECTIVITY ---")
    
    # Extract unique boarding stop sets
    route_stop_sets = RouteConnectivityAnalyzer.extract_route_direction_stop_sets(stop_times_df)
    print(f"Extracted boarding stop sets for {len(route_stop_sets)} route-direction patterns.")

    # Compute pairwise Jaccard connectivity matrix
    print("Computing pairwise Jaccard similarity and shared stop matrices...")
    connectivity_results = RouteConnectivityAnalyzer.compute_pairwise_connectivity_matrix(route_stop_sets)
    jaccard_mat = connectivity_results["jaccard_similarity_matrix"]
    shared_stops_mat = connectivity_results["shared_stops_matrix"]

    # Extract ordered representative stop sequences
    route_stop_sequences = RouteConnectivityAnalyzer.extract_route_direction_stop_sequences(stop_times_df)
    print(f"Extracted representative ordered stop sequences for {len(route_stop_sequences)} patterns.")

    # Find shared contiguous consecutive stop sequences
    print("Identifying contiguous shared consecutive stop sequences (min_sequence_length=2)...")
    consecutive_matches = RouteConnectivityAnalyzer.find_shared_consecutive_stop_sequences(
        route_stop_sequences,
        min_sequence_length=2
    )
    print(f"Identified {len(consecutive_matches)} shared consecutive stop sequence segments.")

    consecutive_records = []
    for match in consecutive_matches:
        consecutive_records.append({
            "pattern_a": match["pattern_a"],
            "pattern_b": match["pattern_b"],
            "sequence_length": int(match["sequence_length"]),
            "shared_sequence_str": " -> ".join(match["shared_sequence"]),
            "start_stop_id": match["shared_sequence"][0],
            "end_stop_id": match["shared_sequence"][-1],
            "shared_stops_json": json.dumps(match["shared_sequence"]),
        })
    consecutive_df = pd.DataFrame(consecutive_records)

    orchestrator.check_memory_guard("Post Pillar B Connectivity")

    # -------------------------------------------------------------------------
    # STEP 4: PILLAR C — ROUTE-LEVEL OPERATIONAL TYPOLOGY
    # -------------------------------------------------------------------------
    print("\n--- STEP 4: PILLAR C — ROUTE-LEVEL OPERATIONAL TYPOLOGY ---")
    
    # Compute route-level aggregated lengths from representative shapes
    # Max length across directions represents total route corridor extent
    route_lengths_km = {}
    for p_id, l_km in route_dir_lengths.items():
        r_id = p_id.split("__dir_")[0]
        if r_id not in route_lengths_km or l_km > route_lengths_km[r_id]:
            route_lengths_km[r_id] = l_km

    # Extract 5 operational features
    print("Extracting 5 canonical route operational features...")
    operational_features_df = RouteFeatureExtractor.compute_route_features(
        routes_df=routes_df,
        trips_df=active_trips_df,
        stop_times_df=stop_times_df,
        route_lengths_km=route_lengths_km,
        ridership_df=ridership_df,
    )
    print(f"Computed operational features for {len(operational_features_df)} routes.")
    print("Feature summary statistics:")
    feature_cols = [
        "log_scheduled_trips", "service_span_hours", "am_peak_mean_headway_min",
        "route_length_km", "unique_stops_count"
    ]
    print(operational_features_df[feature_cols].describe().to_string())

    # Check for missing values in predictor columns
    missing_pred = operational_features_df[feature_cols].isna().sum()
    print("Missing values in KMeans predictors:")
    print(missing_pred.to_string())

    # Fit and evaluate operational KMeans across K in [3, 7]
    print("Evaluating operational KMeans clustering across K in [3, 7]...")
    kmeans_results = RouteEvaluator.evaluate_operational_kmeans(
        feature_df=operational_features_df,
        feature_cols=feature_cols,
        k_values=config.OPERATIONAL_K_RANGE,
        random_state=config.RANDOM_STATE,
        n_init=config.N_INIT,
    )
    kmeans_eval_summary = kmeans_results["evaluation_summary"].copy()
    print("Operational KMeans evaluation summary:")
    print(kmeans_eval_summary.to_string(index=False))

    # Compile KMeans assignments
    valid_routes_df = kmeans_results["valid_routes_df"].copy()
    for k in config.OPERATIONAL_K_RANGE:
        valid_routes_df[f"cluster_k{k}"] = kmeans_results["candidate_results"][k]["labels"]

    # Select champion K based on maximum valid silhouette score
    valid_eval = kmeans_eval_summary[kmeans_eval_summary["status"] == "VALID"]
    champion_k = int(valid_eval.loc[valid_eval["silhouette"].idxmax(), "k"])
    champion_sil = float(valid_eval.loc[valid_eval["silhouette"].idxmax(), "silhouette"])
    print(f"Champion Operational KMeans model: K={champion_k} (Silhouette = {champion_sil:.4f})")
    valid_routes_df["champion_cluster"] = valid_routes_df[f"cluster_k{champion_k}"]

    # Cluster profiles for champion model
    champion_profiles = kmeans_results["candidate_results"][champion_k]["cluster_summaries"]

    orchestrator.check_memory_guard("Post Pillar C KMeans")

    # -------------------------------------------------------------------------
    # STEP 5: SAVE ARTIFACTS
    # -------------------------------------------------------------------------
    print("\n--- STEP 5: SAVING ARTIFACTS TO artifacts/route_clustering/ ---")
    
    # 5.1 Geometries metadata
    geom_meta_path = os.path.join(output_dir, "route_direction_geometries_metadata.parquet")
    geometries_metadata_df.to_parquet(geom_meta_path, index=False)
    print(f"Saved: {geom_meta_path}")

    # 5.2 Pairwise matrices as DataFrames
    df_buf_overlap = pd.DataFrame(buf_overlap_mat, index=pattern_ids, columns=pattern_ids)
    df_buf_dist = pd.DataFrame(buf_dist_mat, index=pattern_ids, columns=pattern_ids)
    df_frechet_dist = pd.DataFrame(frechet_dist_mat, index=pattern_ids, columns=pattern_ids)
    df_jaccard = pd.DataFrame(jaccard_mat, index=connectivity_results["pattern_ids"], columns=connectivity_results["pattern_ids"])
    df_shared_stops = pd.DataFrame(shared_stops_mat, index=connectivity_results["pattern_ids"], columns=connectivity_results["pattern_ids"])

    buf_overlap_path = os.path.join(output_dir, "buffer_overlap_similarity_matrix.parquet")
    buf_dist_path = os.path.join(output_dir, "buffer_distance_matrix.parquet")
    frechet_dist_path = os.path.join(output_dir, "frechet_distance_matrix.parquet")
    jaccard_path = os.path.join(output_dir, "route_direction_jaccard_matrix.parquet")
    shared_stops_path = os.path.join(output_dir, "route_direction_shared_stops_matrix.parquet")

    df_buf_overlap.to_parquet(buf_overlap_path)
    df_buf_dist.to_parquet(buf_dist_path)
    df_frechet_dist.to_parquet(frechet_dist_path)
    df_jaccard.to_parquet(jaccard_path)
    df_shared_stops.to_parquet(shared_stops_path)
    print(f"Saved pairwise similarity and distance matrices.")

    # 5.3 Corridor clustering results
    corridor_eval_path = os.path.join(output_dir, "corridor_clustering_evaluation.csv")
    corridor_eval_summary.to_csv(corridor_eval_path, index=False)
    corridor_assign_path = os.path.join(output_dir, "corridor_cluster_assignments.parquet")
    corridor_assignments_df.to_parquet(corridor_assign_path, index=False)
    print(f"Saved corridor clustering evaluation and assignments.")

    # 5.4 Shared consecutive stop sequences
    consec_path = os.path.join(output_dir, "shared_consecutive_stop_sequences.parquet")
    consecutive_df.to_parquet(consec_path, index=False)
    print(f"Saved: {consec_path}")

    # 5.5 Operational features and KMeans results
    op_feat_path = os.path.join(output_dir, "route_level_operational_features.parquet")
    operational_features_df.to_parquet(op_feat_path, index=False)
    kmeans_eval_path = os.path.join(output_dir, "kmeans_operational_evaluation.csv")
    kmeans_eval_summary.to_csv(kmeans_eval_path, index=False)
    kmeans_assign_path = os.path.join(output_dir, "kmeans_operational_assignments.parquet")
    valid_routes_df.to_parquet(kmeans_assign_path, index=False)
    print(f"Saved operational features and KMeans results.")

    # 5.6 Exclusions & quality records
    exclusions_dict = {
        "snapshot_id": config.SNAPSHOT_ID,
        "representative_service_date": config.REPRESENTATIVE_DATE,
        "total_canonical_routes": len(routes_df),
        "total_active_routes": int(active_trips_df["route_id"].nunique()),
        "total_active_route_directions": len(rep_shapes_df),
        "shape_exclusions_count": len(shape_exclusions_df),
        "shape_exclusions": shape_exclusions_df.to_dict(orient="records"),
        "unmapped_ridership_routes_count": int(operational_features_df["mean_daily_rides"].isna().sum()),
        "unmapped_ridership_routes": operational_features_df[operational_features_df["mean_daily_rides"].isna()]["route_id"].tolist(),
    }
    exclusions_path = os.path.join(output_dir, "exclusion_and_quality_records.json")
    with open(exclusions_path, "w", encoding="utf-8") as f:
        json.dump(exclusions_dict, f, indent=2)
    print(f"Saved: {exclusions_path}")

    # 5.7 Metadata & reproducibility manifest
    end_time = time.time()
    elapsed_sec = end_time - start_time
    mem_final = orchestrator.get_memory_status()

    metadata_dict = {
        "milestone": "Milestone 6",
        "phase": "Phase 6.2 - Spatial Route Clustering & Route Analysis",
        "stage": "Stage 2 - Canonical Real-Data Execution",
        "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_seconds": float(elapsed_sec),
        "configuration": {
            "snapshot_id": config.SNAPSHOT_ID,
            "representative_service_date": config.REPRESENTATIVE_DATE,
            "buffer_radius_meters": config.BUFFER_RADIUS_METERS,
            "downsample_spacing_meters": config.DOWNSAMPLE_SPACING_METERS,
            "operational_k_range": config.OPERATIONAL_K_RANGE,
            "corridor_k_range": config.CORRIDOR_K_RANGE,
            "random_state": config.RANDOM_STATE,
            "n_init": config.N_INIT,
        },
        "population_counts": {
            "canonical_routes": len(routes_df),
            "bus_routes": int((routes_df["route_type"] == 3).sum()),
            "rail_routes": int((routes_df["route_type"] == 1).sum()),
            "active_trips": len(active_trips_df),
            "route_direction_patterns": len(rep_shapes_df),
            "consecutive_shared_sequences": len(consecutive_df),
        },
        "champion_operational_kmeans": {
            "k": champion_k,
            "silhouette": champion_sil,
            "inertia": float(kmeans_results["candidate_results"][champion_k]["inertia"]),
            "cluster_profiles": champion_profiles,
        },
        "memory_monitoring": {
            "initial_avail_mb": float(mem_init["avail_phys_mb"]),
            "final_avail_mb": float(mem_final["avail_phys_mb"]),
            "initial_load_pct": int(mem_init["memory_load_pct"]),
            "final_load_pct": int(mem_final["memory_load_pct"]),
            "guard_threshold_min_avail_mb": config.MEMORY_ABORT_THRESHOLD_MB,
            "guard_threshold_max_load_pct": config.MEMORY_LOAD_ABORT_PCT,
            "guard_triggered": False,
        },
        "artifacts_directory": output_dir,
    }
    metadata_path = os.path.join(output_dir, "phase6_2_stage2_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata_dict, f, indent=2)
    print(f"Saved: {metadata_path}")

    con.close()
    print(f"\nPhase 6.2 Stage 2 Canonical Experiment completed successfully in {elapsed_sec:.2f}s!")
    return metadata_dict


if __name__ == "__main__":
    run_phase6_2_stage2()
