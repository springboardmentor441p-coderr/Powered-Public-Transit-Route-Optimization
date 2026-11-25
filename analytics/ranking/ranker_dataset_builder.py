"""
AI_RouteRanker - Phase 6.3 Ranker Dataset Builder Module
Orchestrates cross-phase feature synthesis, schema validation, memory safety checks,
and metadata generation. Canonical real-data execution is disabled in Stage 1.
"""

from typing import Dict, Optional, Any, Tuple
import os
import ctypes
import json
import time
import pandas as pd
import numpy as np

from analytics.ranking.config import RankerConfig
from analytics.ranking.hub_metrics import compute_route_hub_metrics, compute_pattern_hub_metrics
from analytics.ranking.corridor_metrics import compute_corridor_metrics
from analytics.ranking.demand_integrator import integrate_demand_predictions
from analytics.ranking.route_ranker_features import (
    synthesize_route_ranker_features,
    normalize_features,
    validate_feature_master,
)


class RankerDatasetBuilder:
    """
    Orchestrator for Phase 6.3 feature synthesis pipeline.
    Enforces memory safety checkpoints and produces execution metadata.
    """

    def __init__(self, config: Optional[RankerConfig] = None):
        self.config = config if config is not None else RankerConfig()

    @staticmethod
    def get_memory_status() -> Dict[str, float]:
        """
        Inspects physical RAM status using Win32 GlobalMemoryStatusEx without modifying system state.
        Falls back to psutil if ctypes call fails.
        """
        try:
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
            avail_mb = float(stat.ullAvailPhys / (1024 * 1024))
            total_mb = float(stat.ullTotalPhys / (1024 * 1024))
            return {
                "memory_load_pct": int(stat.dwMemoryLoad),
                "total_phys_mb": total_mb,
                "avail_phys_mb": avail_mb,
            }
        except Exception:
            try:
                import psutil
                vm = psutil.virtual_memory()
                return {
                    "memory_load_pct": int(vm.percent),
                    "total_phys_mb": float(vm.total / (1024 * 1024)),
                    "avail_phys_mb": float(vm.available / (1024 * 1024)),
                }
            except Exception:
                return {
                    "memory_load_pct": 50,
                    "total_phys_mb": 8192.0,
                    "avail_phys_mb": 4096.0,
                }

    def check_memory_guard(self, checkpoint_name: str) -> Dict[str, float]:
        """
        Enforces conservative memory monitoring, raising MemoryError if threshold breached.
        """
        mem = self.get_memory_status()
        if (mem["avail_phys_mb"] < self.config.MEMORY_ABORT_THRESHOLD_MB or
                mem["memory_load_pct"] > self.config.MEMORY_LOAD_ABORT_PCT):
            raise MemoryError(
                f"CRITICAL MEMORY GUARD: Checkpoint '{checkpoint_name}' aborted! "
                f"Avail: {mem['avail_phys_mb']:.1f} MB (min {self.config.MEMORY_ABORT_THRESHOLD_MB} MB), "
                f"Load: {mem['memory_load_pct']}% (max {self.config.MEMORY_LOAD_ABORT_PCT}%)"
            )
        return mem

    def build_synthetic_dataset(
        self,
        operational_df: pd.DataFrame,
        kmeans_df: Optional[pd.DataFrame] = None,
        route_stops_df: Optional[pd.DataFrame] = None,
        hub_rankings_df: Optional[pd.DataFrame] = None,
        top100_hubs_df: Optional[pd.DataFrame] = None,
        peripheral_stops_df: Optional[pd.DataFrame] = None,
        overlap_matrix: Optional[pd.DataFrame] = None,
        shared_sequences_df: Optional[pd.DataFrame] = None,
        corridor_assignments_df: Optional[pd.DataFrame] = None,
        model_ready_features_df: Optional[pd.DataFrame] = None,
        rf_model: Optional[Any] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Synthesizes the feature master from provided DataFrames with memory safety checks.
        Used for unit testing and controlled execution.

        Returns
        -------
        Tuple[pd.DataFrame, Dict[str, Any]]
            Synthesized feature master DataFrame and execution metadata dictionary.
        """
        start_time = time.time()
        self.check_memory_guard("synthetic_build_start")

        # 1. Hub metrics
        hub_metrics_df = None
        if route_stops_df is not None and top100_hubs_df is not None:
            hub_metrics_df = compute_route_hub_metrics(
                route_stops_df=route_stops_df,
                hub_rankings_df=hub_rankings_df if hub_rankings_df is not None else pd.DataFrame(),
                top100_hubs_df=top100_hubs_df,
                peripheral_stops_df=peripheral_stops_df,
            )

        # 2. Corridor metrics
        corridor_metrics_df = None
        if overlap_matrix is not None:
            corridor_metrics_df = compute_corridor_metrics(
                overlap_matrix=overlap_matrix,
                shared_sequences_df=shared_sequences_df,
                corridor_assignments_df=corridor_assignments_df,
                route_metadata_df=operational_df,
            )

        # 3. Demand integration
        demand_df = None
        if operational_df is not None:
            demand_df = integrate_demand_predictions(
                operational_features_df=operational_df,
                model_ready_features_df=model_ready_features_df,
                rf_model=rf_model,
                service_date=self.config.REPRESENTATIVE_DATE,
            )

        self.check_memory_guard("pre_synthesis_merge")

        # 4. Feature synthesis
        feature_master = synthesize_route_ranker_features(
            operational_df=operational_df,
            kmeans_df=kmeans_df,
            hub_metrics_df=hub_metrics_df,
            corridor_metrics_df=corridor_metrics_df,
            demand_df=demand_df,
        )

        # 5. Normalization
        normalized_master, norm_params = normalize_features(feature_master)

        # 6. Validation
        validation_results = validate_feature_master(
            normalized_master,
            expected_total=len(operational_df),
            expected_bus=int((~operational_df["is_rail"]).sum()) if "is_rail" in operational_df.columns else len(operational_df) - 8,
            expected_rail=int(operational_df["is_rail"].sum()) if "is_rail" in operational_df.columns else 8,
        )

        elapsed = time.time() - start_time
        final_mem = self.check_memory_guard("synthetic_build_complete")

        metadata = {
            "milestone": "Milestone 6",
            "phase": "Phase 6.3 - Multi-Criteria Route Ranker Feature Integration",
            "stage": "Stage 1 - Architecture & Unit Testing",
            "snapshot_id": self.config.SNAPSHOT_ID,
            "representative_service_date": self.config.REPRESENTATIVE_DATE,
            "elapsed_seconds": round(elapsed, 4),
            "record_count": len(normalized_master),
            "column_count": len(normalized_master.columns),
            "validation": validation_results,
            "normalization_parameters": norm_params,
            "memory_status": final_mem,
            "status": "STAGE_1_SYNTHETIC_BUILD_SUCCESS",
        }

        return normalized_master, metadata

    def execute_canonical_synthesis(self, allow_canonical: bool = False) -> Dict[str, Any]:
        """
        Executes the canonical Phase 6.3 real-data synthesis pipeline.
        Produces route_ranker_feature_master.parquet and connectivity artifacts.

        Parameters
        ----------
        allow_canonical : bool
            Must be explicitly set to True with user authorization to execute.

        Returns
        -------
        Dict[str, Any]
            Execution metadata dictionary.
        """
        if not allow_canonical:
            raise RuntimeError(
                "CANONICAL EXECUTION BLOCKED: Phase 6.3 requires explicit user authorization "
                "to execute real-data canonical synthesis."
            )

        start_time = time.time()
        output_dir = self.config.OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)

        target_master_path = self.config.FEATURE_MASTER_PATH
        target_conn_path = self.config.CONNECTIVITY_MATRIX_PATH
        target_meta_path = self.config.METADATA_PATH

        # Safeguard: Never silently overwrite existing outputs
        if os.path.exists(target_master_path):
            raise FileExistsError(
                f"CANONICAL OUTPUT CONFLICT: Final artifact already exists at {target_master_path}. "
                "Aborting execution to protect existing canonical data."
            )

        # 1. Preflight Memory Check
        mem_start = self.check_memory_guard("canonical_start")

        # 2. Load Phase 6.2 Operational Features
        if not os.path.exists(self.config.ROUTE_OPERATIONAL_FEATURES_PATH):
            raise FileNotFoundError(f"Missing required artifact: {self.config.ROUTE_OPERATIONAL_FEATURES_PATH}")
        ops_df = pd.read_parquet(self.config.ROUTE_OPERATIONAL_FEATURES_PATH)

        # Rename operational columns to match canonical schema definitions
        rename_map = {
            "total_scheduled_trips": "scheduled_trips",
            "am_peak_mean_headway_min": "am_headway_min",
            "mean_daily_rides": "historical_mean_daily_rides",
        }
        ops_df = ops_df.rename(columns=rename_map)
        ops_df["route_id"] = ops_df["route_id"].astype(str)

        # 3. Read DuckDB route dimensions and active stop mappings (Read-Only)
        import duckdb
        con = duckdb.connect(self.config.DUCKDB_PATH, read_only=True)

        # Load route_long_name from canonical snapshot
        route_dim = con.execute(f"""
            SELECT DISTINCT route_id, route_short_name, route_long_name
            FROM analytical.gtfs_routes
            WHERE snapshot_id = '{self.config.SNAPSHOT_ID}'
        """).fetchdf()
        route_dim["route_id"] = route_dim["route_id"].astype(str)

        if "route_long_name" not in ops_df.columns:
            ops_df = ops_df.merge(route_dim[["route_id", "route_long_name"]], on="route_id", how="left")

        # Active route-stops on canonical date 2026-06-10
        route_stops_query = f"""
        WITH active_services AS (
            SELECT DISTINCT c.service_id
            FROM analytical.gtfs_calendar c
            LEFT JOIN analytical.gtfs_calendar_dates cd_del
                ON c.service_id = cd_del.service_id
                AND c.snapshot_id = cd_del.snapshot_id
                AND cd_del.date = '{self.config.REPRESENTATIVE_DATE}'
                AND cd_del.exception_type = 2
            WHERE c.snapshot_id = '{self.config.SNAPSHOT_ID}'
              AND c.wednesday = 1
              AND '{self.config.REPRESENTATIVE_DATE}' BETWEEN c.start_date AND c.end_date
              AND cd_del.service_id IS NULL

            UNION

            SELECT DISTINCT cd_add.service_id
            FROM analytical.gtfs_calendar_dates cd_add
            WHERE cd_add.snapshot_id = '{self.config.SNAPSHOT_ID}'
              AND cd_add.date = '{self.config.REPRESENTATIVE_DATE}'
              AND cd_add.exception_type = 1
        ),
        active_trips AS (
            SELECT t.route_id, t.direction_id, t.trip_id
            FROM analytical.gtfs_trips t
            JOIN active_services s ON t.service_id = s.service_id
            WHERE t.snapshot_id = '{self.config.SNAPSHOT_ID}'
        )
        SELECT DISTINCT t.route_id, st.stop_id
        FROM active_trips t
        JOIN analytical.gtfs_stop_times st ON t.trip_id = st.trip_id
        WHERE st.snapshot_id = '{self.config.SNAPSHOT_ID}';
        """
        route_stops_df = con.execute(route_stops_query).fetchdf()

        # Pattern-stops for directional connectivity table
        pattern_stops_query = f"""
        WITH active_services AS (
            SELECT DISTINCT c.service_id
            FROM analytical.gtfs_calendar c
            LEFT JOIN analytical.gtfs_calendar_dates cd_del
                ON c.service_id = cd_del.service_id
                AND c.snapshot_id = cd_del.snapshot_id
                AND cd_del.date = '{self.config.REPRESENTATIVE_DATE}'
                AND cd_del.exception_type = 2
            WHERE c.snapshot_id = '{self.config.SNAPSHOT_ID}'
              AND c.wednesday = 1
              AND '{self.config.REPRESENTATIVE_DATE}' BETWEEN c.start_date AND c.end_date
              AND cd_del.service_id IS NULL

            UNION

            SELECT DISTINCT cd_add.service_id
            FROM analytical.gtfs_calendar_dates cd_add
            WHERE cd_add.snapshot_id = '{self.config.SNAPSHOT_ID}'
              AND cd_add.date = '{self.config.REPRESENTATIVE_DATE}'
              AND cd_add.exception_type = 1
        ),
        active_trips AS (
            SELECT t.route_id, t.direction_id, t.trip_id
            FROM analytical.gtfs_trips t
            JOIN active_services s ON t.service_id = s.service_id
            WHERE t.snapshot_id = '{self.config.SNAPSHOT_ID}'
        )
        SELECT DISTINCT 
            (t.route_id || '__dir_' || CAST(t.direction_id AS VARCHAR)) AS pattern_id,
            t.route_id,
            t.direction_id,
            st.stop_id
        FROM active_trips t
        JOIN analytical.gtfs_stop_times st ON t.trip_id = st.trip_id
        WHERE st.snapshot_id = '{self.config.SNAPSHOT_ID}';
        """
        pattern_stops_df = con.execute(pattern_stops_query).fetchdf()
        con.close()

        # 4. Load Phase 6.2 KMeans Typology
        km_df = pd.read_parquet(self.config.KMEANS_OPERATIONAL_ASSIGNMENTS_PATH)
        km_df["route_id"] = km_df["route_id"].astype(str)
        cluster_labels = {0: "Trunk", 1: "Feeder", 2: "Regional"}
        km_df["operational_cluster_k3"] = km_df["champion_cluster"]
        km_df["operational_cluster_label"] = km_df["operational_cluster_k3"].map(cluster_labels)

        # 5. Compute Transit Hub Metrics (Phase 6.1 Integration)
        top100_df = pd.read_csv(self.config.TOP100_HUBS_CONFIG_A_PATH)
        hub_rankings_df = pd.read_parquet(self.config.TRANSIT_HUB_RANKINGS_PATH)
        periph_df = pd.read_parquet(self.config.SPATIAL_DBSCAN_ASSIGNMENTS_PATH)

        hub_metrics_df = compute_route_hub_metrics(
            route_stops_df=route_stops_df,
            hub_rankings_df=hub_rankings_df,
            top100_hubs_df=top100_df,
            peripheral_stops_df=periph_df,
        )

        # Directional pattern-level hub connectivity for secondary link table
        pattern_hub_df = compute_pattern_hub_metrics(
            pattern_stops_df=pattern_stops_df,
            top100_hubs_df=top100_df,
            hub_rankings_df=hub_rankings_df,
        )

        self.check_memory_guard("post_hub_metrics")

        # 6. Compute Corridor Metrics (Phase 6.2 Integration)
        overlap_df = pd.read_parquet(self.config.BUFFER_OVERLAP_SIMILARITY_PATH)
        shared_df = pd.read_parquet(self.config.SHARED_STOP_SEQUENCES_PATH)
        corr_assign_df = pd.read_parquet(self.config.CORRIDOR_CLUSTER_ASSIGNMENTS_PATH)

        corridor_metrics_df = compute_corridor_metrics(
            overlap_matrix=overlap_df,
            shared_sequences_df=shared_df,
            corridor_assignments_df=corr_assign_df,
            route_metadata_df=ops_df,
        )

        self.check_memory_guard("post_corridor_metrics")

        # 7. Integrate Demand Predictions (Milestone 5 Inference)
        # Using pre-trained tuned model predictions strictly on canonical service date 2026-06-10
        pred_path = os.path.join(self.config.RANDOM_FOREST_DIR, "tier1_test_predictions_tuned.parquet")
        if not os.path.exists(pred_path):
            raise FileNotFoundError(f"Missing tuned predictions artifact: {pred_path}")

        pred_df = pd.read_parquet(pred_path)
        pred_date = pred_df[pred_df["date"].astype(str).str.startswith(self.config.REPRESENTATIVE_DATE)].copy()
        pred_date["route_id"] = pred_date["route"].astype(str)
        pred_date["forecasted_daily_demand"] = pred_date["rf_tuned_prediction"]

        demand_df = integrate_demand_predictions(
            operational_features_df=ops_df,
            model_ready_features_df=pred_date,
            service_date=self.config.REPRESENTATIVE_DATE,
        )

        self.check_memory_guard("pre_synthesis_merge")

        # 8. Synthesize Full Feature Master
        feature_master = synthesize_route_ranker_features(
            operational_df=ops_df,
            kmeans_df=km_df,
            hub_metrics_df=hub_metrics_df,
            corridor_metrics_df=corridor_metrics_df,
            demand_df=demand_df,
        )

        # 9. Apply Percentile MinMax Normalization
        normalized_master, norm_params = normalize_features(feature_master)

        # 10. Rigorous Validation Check
        validation_results = validate_feature_master(
            normalized_master,
            expected_total=self.config.EXPECTED_TOTAL_ROUTES,
            expected_bus=self.config.EXPECTED_BUS_ROUTES,
            expected_rail=self.config.EXPECTED_RAIL_ROUTES,
        )

        if not validation_results["is_valid"]:
            raise ValueError(f"CANONICAL VALIDATION FAILED: {validation_results['errors']}")

        # 11. Atomic Serialization to Disk
        temp_master_path = f"{target_master_path}.tmp"
        temp_conn_path = f"{target_conn_path}.tmp"
        temp_meta_path = f"{target_meta_path}.tmp"

        normalized_master.to_parquet(temp_master_path, index=False)
        pattern_hub_df.to_parquet(temp_conn_path, index=False)

        elapsed = time.time() - start_time
        final_mem = self.check_memory_guard("canonical_complete")

        metadata = {
            "milestone": "Milestone 6",
            "phase": "Phase 6.3 - Multi-Criteria Route Ranker Feature Integration",
            "stage": "Stage 2 - Canonical Real-Data Synthesis",
            "snapshot_id": self.config.SNAPSHOT_ID,
            "representative_service_date": self.config.REPRESENTATIVE_DATE,
            "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "elapsed_seconds": round(elapsed, 4),
            "record_count": len(normalized_master),
            "bus_count": int((~normalized_master["is_rail"]).sum()),
            "rail_count": int(normalized_master["is_rail"].sum()),
            "column_count": len(normalized_master.columns),
            "validation": validation_results,
            "normalization_parameters": norm_params,
            "memory_status": final_mem,
            "artifacts": {
                "route_ranker_feature_master": target_master_path,
                "route_direction_connectivity_matrix": target_conn_path,
            },
            "status": "CANONICAL_SYNTHESIS_SUCCESS",
        }

        with open(temp_meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Atomic replacement
        os.replace(temp_master_path, target_master_path)
        os.replace(temp_conn_path, target_conn_path)
        os.replace(temp_meta_path, target_meta_path)

        return metadata
