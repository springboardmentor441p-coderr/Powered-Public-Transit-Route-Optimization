"""
AI_RouteRanker - Phase 6.3 Ranking Configuration Module
Defines centralized parameters, canonical snapshot identifiers, artifact locations,
memory safety thresholds, approved feature dimensions, and normalization parameters.
"""

from typing import Dict, List, Set, Any
import os


class RankerConfig:
    """
    Centralized configuration for Phase 6.3 Feature Synthesis and Downstream Ranking.
    """
    # Canonical snapshot and service date
    SNAPSHOT_ID: str = "mdb-389-202605300003"
    REPRESENTATIVE_DATE: str = "2026-06-10"  # Wednesday

    # Expected route population
    EXPECTED_TOTAL_ROUTES: int = 133
    EXPECTED_BUS_ROUTES: int = 125
    EXPECTED_RAIL_ROUTES: int = 8
    EXPECTED_ROUTE_PATTERNS: int = 261

    # Canonical rail route identifiers
    RAIL_ROUTE_IDS: Set[str] = {
        "Red", "Blue", "Brn", "G", "Org", "P", "Pink", "Y"
    }

    # Specialized routes with documented missing AM peak headways
    SPECIALIZED_HEADWAY_EXCLUDED_ROUTES: Set[str] = {
        "10",   # Museum of Science & Industry (1 departure, 0 intervals)
        "130",  # Museum Campus (starts 09:27 AM)
        "N5"    # South Shore Night Bus (overnight service)
    }

    # Memory guard thresholds (strictly enforced on 8 GB RAM laptop)
    MEMORY_ABORT_THRESHOLD_MB: float = 600.0
    MEMORY_LOAD_ABORT_PCT: int = 95

    # Composite Index Formula Weights
    # Transit Hub Connectivity Index: H_r = w1 * stop_ratio + w2 * normalized_importance
    HUB_WEIGHT_STOP_RATIO: float = 0.40
    HUB_WEIGHT_IMPORTANCE: float = 0.60

    # Corridor Duplication Index: D_r = alpha * max_overlap + beta * mean_top5_overlap + gamma * shared_stop_ratio
    CORRIDOR_WEIGHT_MAX_OVERLAP: float = 0.40
    CORRIDOR_WEIGHT_TOP5_MEAN: float = 0.30
    CORRIDOR_WEIGHT_SHARED_RATIO: float = 0.30

    # Normalization parameters (percentile clipping bounds to guard against transit outliers)
    PERCENTILE_MIN: float = 1.0
    PERCENTILE_MAX: float = 99.0

    # Protected input artifact locations
    DATA_DIR: str = os.path.join("data", "processed")
    DUCKDB_PATH: str = os.path.join(DATA_DIR, "ai_routeranker.duckdb")
    MODEL_READY_FEATURES_PATH: str = os.path.join(DATA_DIR, "features", "model_ready_features.parquet")

    # Phase 6.1 Artifacts
    PHASE6_1_DIR: str = os.path.join("artifacts", "clustering")
    STOP_LEVEL_FEATURE_MASTER_PATH: str = os.path.join(PHASE6_1_DIR, "stop_level_feature_master.parquet")
    TRANSIT_HUB_RANKINGS_PATH: str = os.path.join(PHASE6_1_DIR, "transit_hub_rankings.parquet")
    TOP100_HUBS_CONFIG_A_PATH: str = os.path.join(PHASE6_1_DIR, "top100_hubs_config_a.csv")
    SPATIAL_DBSCAN_ASSIGNMENTS_PATH: str = os.path.join(PHASE6_1_DIR, "spatial_dbscan_assignments.parquet")

    # Phase 6.2 Artifacts
    PHASE6_2_DIR: str = os.path.join("artifacts", "route_clustering")
    ROUTE_OPERATIONAL_FEATURES_PATH: str = os.path.join(PHASE6_2_DIR, "route_level_operational_features.parquet")
    KMEANS_OPERATIONAL_ASSIGNMENTS_PATH: str = os.path.join(PHASE6_2_DIR, "kmeans_operational_assignments.parquet")
    BUFFER_OVERLAP_SIMILARITY_PATH: str = os.path.join(PHASE6_2_DIR, "buffer_overlap_similarity_matrix.parquet")
    SHARED_STOP_SEQUENCES_PATH: str = os.path.join(PHASE6_2_DIR, "shared_consecutive_stop_sequences.parquet")
    CORRIDOR_CLUSTER_ASSIGNMENTS_PATH: str = os.path.join(PHASE6_2_DIR, "corridor_cluster_assignments.parquet")

    # Milestone 5 Models
    RANDOM_FOREST_DIR: str = os.path.join("artifacts", "random_forest")
    TIER1_RF_MODEL_PATH: str = os.path.join(RANDOM_FOREST_DIR, "tier1_random_forest_tuned.joblib")
    TIER2_RF_MODEL_PATH: str = os.path.join(RANDOM_FOREST_DIR, "tier2_random_forest_tuned.joblib")

    # Phase 6.3 Dedicated Output Locations
    OUTPUT_DIR: str = os.path.join("artifacts", "ranking_features")
    FEATURE_MASTER_PATH: str = os.path.join(OUTPUT_DIR, "route_ranker_feature_master.parquet")
    CONNECTIVITY_MATRIX_PATH: str = os.path.join(OUTPUT_DIR, "route_direction_connectivity_matrix.parquet")
    METADATA_PATH: str = os.path.join(OUTPUT_DIR, "phase6_3_metadata.json")
    REPORTS_DIR: str = os.path.join("reports", "phase6_3")

    # The Approved 24 Feature Dimensions
    APPROVED_24_FEATURES: List[str] = [
        "route_id",
        "route_short_name",
        "route_long_name",
        "route_type",
        "is_rail",
        "scheduled_trips",
        "service_span_hours",
        "am_headway_min",
        "route_length_km",
        "unique_stops_count",
        "operational_cluster_k3",
        "operational_cluster_label",
        "historical_mean_daily_rides",
        "forecasted_daily_demand",
        "rides_per_trip",
        "hub_stop_count",
        "hub_stop_ratio",
        "hub_weighted_importance",
        "max_corridor_overlap",
        "mean_corridor_overlap",
        "shared_consecutive_stop_count",
        "corridor_duplication_ratio",
        "regional_partition",
        "load_intensity_factor",
    ]

    # Non-continuous / identifier features excluded from numeric normalization
    NON_NORMALIZED_COLUMNS: Set[str] = {
        "route_id",
        "route_short_name",
        "route_long_name",
        "route_type",
        "is_rail",
        "operational_cluster_k3",
        "operational_cluster_label",
        "regional_partition",
    }

    # Nullable columns by design
    NULLABLE_COLUMNS: Set[str] = {
        "am_headway_min",
        "operational_cluster_k3",
        "operational_cluster_label",
        "historical_mean_daily_rides",
        "forecasted_daily_demand",
        "rides_per_trip",
        "load_intensity_factor",
    }

    # =========================================================================
    # Phase 7 — Multi-Criteria Decision-Making (MCDM) Ranking Configuration
    # =========================================================================

    # Phase 7 Output Locations
    RANKING_RESULTS_DIR: str = os.path.join("artifacts", "ranking_results")
    ROUTE_RANKINGS_MASTER_PATH: str = os.path.join(RANKING_RESULTS_DIR, "route_rankings_master.parquet")
    ROUTE_RANKING_EXPLANATIONS_PATH: str = os.path.join(RANKING_RESULTS_DIR, "route_ranking_explanations.json")
    RANKING_SENSITIVITY_PATH: str = os.path.join(RANKING_RESULTS_DIR, "ranking_sensitivity_analysis.parquet")
    PHASE7_METADATA_PATH: str = os.path.join(RANKING_RESULTS_DIR, "phase7_metadata.json")
    PHASE7_REPORTS_DIR: str = os.path.join("reports", "phase7")

    # Ranking Tracks
    TRACK_BUS_PRIORITY: str = "BUS_PRIORITY"          # 125 bus routes (full demand + operational criteria)
    TRACK_RAIL_PRIORITY: str = "RAIL_PRIORITY"        # 8 rail lines (mode-appropriate supply & corridor criteria)
    TRACK_UNIFIED_SUPPLY: str = "UNIFIED_SUPPLY"      # 133 routes (mode-agnostic operational supply criteria)

    # Ranking Pillar Identifiers
    PILLAR_DEMAND: str = "demand_pressure"
    PILLAR_SERVICE: str = "service_provision"
    PILLAR_HUBS: str = "network_hubs"
    PILLAR_CORRIDOR: str = "corridor_structure"

    # Criteria to Pillar Mapping (Profile A)
    CRITERIA_TO_PILLAR_MAP: Dict[str, str] = {
        "forecasted_daily_demand_norm": PILLAR_DEMAND,
        "load_intensity_factor_norm": PILLAR_DEMAND,
        "scheduled_trips_norm": PILLAR_SERVICE,
        "service_span_hours_norm": PILLAR_SERVICE,
        "am_headway_min_norm": PILLAR_SERVICE,
        "hub_stop_ratio_norm": PILLAR_HUBS,
        "corridor_duplication_index_norm": PILLAR_CORRIDOR,
    }

    # Cost criteria requiring inversion: (1.0 - x_norm)
    COST_CRITERIA: Set[str] = {
        "am_headway_min_norm"
    }

    # Minimum valid criteria weight coverage threshold
    # If a route has valid criteria totaling less than this weight, score is marked unavailable
    MIN_VALID_WEIGHT_THRESHOLD: float = 0.50

    # Primary Profile A Weights (Balanced Operational Review Priority - Default)
    # Total sum = 1.000000
    PROFILE_A_WEIGHTS: Dict[str, float] = {
        "forecasted_daily_demand_norm": 0.15,
        "load_intensity_factor_norm": 0.20,
        "scheduled_trips_norm": 0.10,
        "service_span_hours_norm": 0.05,
        "am_headway_min_norm": 0.10,
        "hub_stop_ratio_norm": 0.20,
        "corridor_duplication_index_norm": 0.20,
    }

    # Profile B Weights (Overcrowding & Capacity Relief Focus)
    PROFILE_B_WEIGHTS: Dict[str, float] = {
        "forecasted_daily_demand_norm": 0.25,
        "load_intensity_factor_norm": 0.30,
        "scheduled_trips_norm": 0.10,
        "service_span_hours_norm": 0.05,
        "am_headway_min_norm": 0.10,
        "hub_stop_ratio_norm": 0.10,
        "corridor_duplication_index_norm": 0.10,
    }

    # Profile C Weights (Corridor Restructuring & Efficiency Focus)
    PROFILE_C_WEIGHTS: Dict[str, float] = {
        "forecasted_daily_demand_norm": 0.15,
        "load_intensity_factor_norm": 0.15,
        "scheduled_trips_norm": 0.05,
        "service_span_hours_norm": 0.05,
        "am_headway_min_norm": 0.05,
        "hub_stop_ratio_norm": 0.15,
        "corridor_duplication_index_norm": 0.40,
    }

    # Profile D Weights (Core Network Essentiality Focus)
    PROFILE_D_WEIGHTS: Dict[str, float] = {
        "forecasted_daily_demand_norm": 0.20,
        "load_intensity_factor_norm": 0.15,
        "scheduled_trips_norm": 0.15,
        "service_span_hours_norm": 0.10,
        "am_headway_min_norm": 0.15,
        "hub_stop_ratio_norm": 0.20,
        "corridor_duplication_index_norm": 0.05,
    }

    # Rail Priority Weights (Operational Supply & Alignment Focus - 8 rail lines)
    RAIL_PROFILE_WEIGHTS: Dict[str, float] = {
        "scheduled_trips_norm": 0.30,
        "service_span_hours_norm": 0.20,
        "am_headway_min_norm": 0.30,
        "corridor_duplication_index_norm": 0.20,
    }

    # Unified Supply Weights (Mode-Agnostic Operational Supply - 133 routes)
    UNIFIED_SUPPLY_WEIGHTS: Dict[str, float] = {
        "scheduled_trips_norm": 0.35,
        "service_span_hours_norm": 0.20,
        "am_headway_min_norm": 0.25,
        "corridor_duplication_index_norm": 0.20,
    }

    # All Profiles Dictionary
    WEIGHT_PROFILES: Dict[str, Dict[str, float]] = {
        "BALANCED_DEFAULT": PROFILE_A_WEIGHTS,
        "OVERCROWDING_RELIEF": PROFILE_B_WEIGHTS,
        "CORRIDOR_RESTRUCTURING": PROFILE_C_WEIGHTS,
        "NETWORK_ESSENTIALITY": PROFILE_D_WEIGHTS,
        "RAIL_PRIORITY": RAIL_PROFILE_WEIGHTS,
        "UNIFIED_SUPPLY": UNIFIED_SUPPLY_WEIGHTS,
    }

    # Sensitivity Analysis Perturbation Grid
    PERTURBATION_DELTAS: List[float] = [-0.20, -0.10, 0.10, 0.20]
    TOP_K_BENCHMARKS: List[int] = [10, 20]
