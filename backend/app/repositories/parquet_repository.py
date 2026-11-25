"""Read-only Parquet repository with column pruning, schema validation, and safe caching."""

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.core.config import settings
from app.core.exceptions import ArtifactUnavailableError

logger = logging.getLogger("ai_routeranker.repositories.parquet")


class ParquetRepository:
    """
    Read-only repository for Parquet analytical artifacts.

    Loads required columns only, caches small immutable datasets per (path, columns)
    key, validates required schema columns, and never mutates source artifacts.
    """

    FEATURE_REQUIRED_COLUMNS: List[str] = [
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
        "hub_connectivity_index",
        "corridor_duplication_index",
    ]

    RANKING_REQUIRED_COLUMNS: List[str] = [
        "route_id",
        "route_short_name",
        "route_long_name",
        "route_type",
        "is_rail",
        "scheduled_trips",
        "service_span_hours",
        "am_headway_min",
        "operational_cluster_label",
        "regional_partition",
        "corridor_duplication_index",
        "track",
        "profile",
        "overall_score",
        "rank",
        "percentile_rank",
        "topsis_score",
        "topsis_rank",
        "pillar_demand_score",
        "pillar_service_score",
        "pillar_hub_score",
        "pillar_corridor_score",
        "contrib_forecasted_daily_demand",
        "contrib_load_intensity_factor",
        "contrib_scheduled_trips",
        "contrib_service_span_hours",
        "contrib_am_headway_min",
        "contrib_hub_stop_ratio",
        "contrib_corridor_duplication_index",
    ]

    SENSITIVITY_REQUIRED_COLUMNS: List[str] = [
        "scenario_id",
        "target_criterion",
        "delta",
        "spearman_rho",
        "mean_absolute_rank_shift",
        "max_rank_shift",
        "top_10_overlap",
        "top_20_overlap",
        "track",
    ]

    def __init__(
        self,
        feature_master_path: Optional[Path] = None,
        rankings_master_path: Optional[Path] = None,
        sensitivity_path: Optional[Path] = None,
    ) -> None:
        self._feature_master_path = Path(feature_master_path or settings.FEATURE_MASTER_PATH)
        self._rankings_master_path = Path(rankings_master_path or settings.RANKINGS_MASTER_PATH)
        self._sensitivity_path = Path(sensitivity_path or settings.SENSITIVITY_PATH)
        self._lock = threading.Lock()
        self._cache: Dict[Tuple[Path, Tuple[str, ...]], pd.DataFrame] = {}

    def clear_cache(self) -> None:
        """Clear in-memory cached dataframes."""
        with self._lock:
            self._cache.clear()

    def _load_parquet(
        self,
        path: Path,
        required_columns: List[str],
        artifact_label: str,
    ) -> pd.DataFrame:
        """Read a Parquet file with column pruning, schema validation, and thread-safe lazy caching."""
        cache_key = (path, tuple(required_columns))
        if cache_key in self._cache:
            return self._cache[cache_key]

        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

            if not path.exists() or not path.is_file():
                logger.error("Required artifact '%s' is missing.", artifact_label)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_MISSING",
                    message=f"Required analytical artifact '{artifact_label}' is unavailable.",
                )

            try:
                df = pd.read_parquet(path, columns=required_columns)
            except KeyError as exc:
                logger.error("Artifact '%s' is missing required columns: %s", artifact_label, exc)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message=f"Analytical artifact '{artifact_label}' does not match the expected schema.",
                ) from exc
            except Exception as exc:
                logger.error("Failed to read artifact '%s': %s", artifact_label, type(exc).__name__)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_CORRUPT",
                    message=f"Analytical artifact '{artifact_label}' could not be read.",
                ) from exc

            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                logger.error("Artifact '%s' missing columns: %s", artifact_label, missing_cols)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message=f"Analytical artifact '{artifact_label}' is missing required fields.",
                )

            # Normalize route_id as stripped string for reliable lookups
            if "route_id" in df.columns:
                df["route_id"] = df["route_id"].astype(str).str.strip()

            # Protect cached dataframe from accidental in-place mutation
            for arr in df._mgr.arrays:
                if hasattr(arr, "_ndarray") and hasattr(arr._ndarray, "flags"):
                    try:
                        arr._ndarray.flags.writeable = False
                    except ValueError:
                        pass

            self._cache[cache_key] = df
            return df

    def get_feature_master(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Return the cached Phase 6.3 feature master (or pruned column view)."""
        cols = columns or self.FEATURE_REQUIRED_COLUMNS
        df = self._load_parquet(
            self._feature_master_path,
            self.FEATURE_REQUIRED_COLUMNS,
            "route_ranker_feature_master",
        )
        return df[cols]

    def get_rankings_master(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Return the cached Phase 7 rankings master (or pruned column view)."""
        cols = columns or self.RANKING_REQUIRED_COLUMNS
        df = self._load_parquet(
            self._rankings_master_path,
            self.RANKING_REQUIRED_COLUMNS,
            "route_rankings_master",
        )
        return df[cols]

    def get_sensitivity_analysis(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Return the cached Phase 7 sensitivity analysis table."""
        cols = columns or self.SENSITIVITY_REQUIRED_COLUMNS
        df = self._load_parquet(
            self._sensitivity_path,
            self.SENSITIVITY_REQUIRED_COLUMNS,
            "ranking_sensitivity_analysis",
        )
        return df[cols]
