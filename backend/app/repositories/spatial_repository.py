"""Read-only repository for Phase 6.1 spatial hub rankings and DBSCAN cluster artifacts."""

import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.config import settings
from app.core.exceptions import ArtifactUnavailableError

logger = logging.getLogger("ai_routeranker.repositories.spatial")


class SpatialRepository:
    """
    Read-only repository for Phase 6.1 spatial clustering and hub ranking artifacts.

    Uses column pruning, schema validation, thread-safe lazy initialization, and
    write-protected cached DataFrames without mutating canonical source files.
    """

    HUB_REQUIRED_COLUMNS: List[str] = [
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "total_visits",
        "routes_served",
        "attributed_demand",
        "demand_intensity",
        "score_config_a",
        "rank_config_a",
        "score_config_b",
        "rank_config_b",
        "score_config_c",
        "rank_config_c",
    ]

    DBSCAN_REQUIRED_COLUMNS: List[str] = [
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "dbscan_cluster",
    ]

    def __init__(
        self,
        hub_rankings_path: Optional[Path] = None,
        dbscan_assignments_path: Optional[Path] = None,
        metadata_path: Optional[Path] = None,
        top100_config_a_path: Optional[Path] = None,
    ) -> None:
        self._hub_rankings_path = Path(hub_rankings_path or settings.TRANSIT_HUB_RANKINGS_PATH)
        self._dbscan_path = Path(dbscan_assignments_path or settings.DBSCAN_ASSIGNMENTS_PATH)
        self._metadata_path = Path(metadata_path or settings.PHASE6_1_METADATA_PATH)
        self._top100_a_path = Path(top100_config_a_path or settings.TOP100_HUBS_CONFIG_A_PATH)
        self._lock = threading.Lock()
        self._hubs_df: Optional[pd.DataFrame] = None
        self._dbscan_df: Optional[pd.DataFrame] = None
        self._merged_df: Optional[pd.DataFrame] = None
        self._metadata: Optional[Dict[str, Any]] = None
        self._top100_a_ids: Optional[List[str]] = None

    def clear_cache(self) -> None:
        """Clear in-memory cached spatial artifacts."""
        with self._lock:
            self._hubs_df = None
            self._dbscan_df = None
            self._merged_df = None
            self._metadata = None
            self._top100_a_ids = None

    @staticmethod
    def _freeze_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Mark underlying NumPy arrays read-only to prevent in-place mutation."""
        for arr in df._mgr.arrays:
            if hasattr(arr, "_ndarray") and hasattr(arr._ndarray, "flags"):
                try:
                    arr._ndarray.flags.writeable = False
                except ValueError:
                    pass
        return df

    @staticmethod
    def _read_parquet_safe(
        path: Path,
        required_columns: List[str],
        artifact_label: str,
    ) -> pd.DataFrame:
        if not path.exists() or not path.is_file():
            logger.error("Required spatial artifact '%s' is missing.", artifact_label)
            raise ArtifactUnavailableError(
                code="ARTIFACT_MISSING",
                message=f"Required spatial artifact '{artifact_label}' is unavailable.",
            )
        try:
            df = pd.read_parquet(path, columns=required_columns)
        except KeyError as exc:
            logger.error("Spatial artifact '%s' missing columns: %s", artifact_label, exc)
            raise ArtifactUnavailableError(
                code="ARTIFACT_SCHEMA_INVALID",
                message=f"Spatial artifact '{artifact_label}' does not match the expected schema.",
            ) from exc
        except Exception as exc:
            logger.error("Failed to read spatial artifact '%s': %s", artifact_label, type(exc).__name__)
            raise ArtifactUnavailableError(
                code="ARTIFACT_CORRUPT",
                message=f"Spatial artifact '{artifact_label}' could not be read.",
            ) from exc

        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            raise ArtifactUnavailableError(
                code="ARTIFACT_SCHEMA_INVALID",
                message=f"Spatial artifact '{artifact_label}' is missing required fields.",
            )

        df["stop_id"] = df["stop_id"].astype(str).str.strip()
        return df

    def get_hub_rankings(self) -> pd.DataFrame:
        """Return cached transit_hub_rankings DataFrame (thread-safe)."""
        if self._hubs_df is not None:
            return self._hubs_df
        with self._lock:
            if self._hubs_df is not None:
                return self._hubs_df
            df = self._read_parquet_safe(
                self._hub_rankings_path,
                self.HUB_REQUIRED_COLUMNS,
                "transit_hub_rankings",
            )
            self._hubs_df = self._freeze_dataframe(df)
            return self._hubs_df

    def get_spatial_stops_with_clusters(self) -> pd.DataFrame:
        """
        Return cached left-joined view of DBSCAN stop assignments and hub rankings.

        Preserves all stops (including noise points dbscan_cluster == -1 and stops
        ineligible for hub ranking).
        """
        if self._merged_df is not None:
            return self._merged_df
        with self._lock:
            if self._merged_df is not None:
                return self._merged_df
            dbscan_df = self._read_parquet_safe(
                self._dbscan_path,
                self.DBSCAN_REQUIRED_COLUMNS,
                "spatial_dbscan_assignments",
            )
            hubs_df = self._hubs_df
            if hubs_df is None:
                hubs_df = self._read_parquet_safe(
                    self._hub_rankings_path,
                    self.HUB_REQUIRED_COLUMNS,
                    "transit_hub_rankings",
                )
                self._hubs_df = self._freeze_dataframe(hubs_df)

            hub_cols_to_merge = [
                "stop_id",
                "total_visits",
                "routes_served",
                "attributed_demand",
                "demand_intensity",
                "score_config_a",
                "rank_config_a",
                "score_config_b",
                "rank_config_b",
                "score_config_c",
                "rank_config_c",
            ]
            merged = dbscan_df.merge(
                hubs_df[hub_cols_to_merge],
                on="stop_id",
                how="left",
            )
            merged["hub_ranking_eligible"] = merged["rank_config_a"].notna()
            self._dbscan_df = self._freeze_dataframe(dbscan_df)
            self._merged_df = self._freeze_dataframe(merged)
            return self._merged_df

    def get_cluster_metadata(self) -> Dict[str, Any]:
        """Return a deep copy of Phase 6.1 metadata JSON (thread-safe)."""
        if self._metadata is not None:
            return copy.deepcopy(self._metadata)
        with self._lock:
            if self._metadata is not None:
                return copy.deepcopy(self._metadata)
            if not self._metadata_path.exists() or not self._metadata_path.is_file():
                raise ArtifactUnavailableError(
                    code="ARTIFACT_MISSING",
                    message="Required spatial artifact 'phase6_1_stage2_metadata' is unavailable.",
                )
            try:
                with self._metadata_path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception as exc:
                logger.error("Failed to parse Phase 6.1 metadata JSON: %s", type(exc).__name__)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_CORRUPT",
                    message="Spatial artifact 'phase6_1_stage2_metadata' could not be parsed.",
                ) from exc

            if not isinstance(raw, dict) or "dbscan_cluster_count" not in raw:
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message="Spatial artifact 'phase6_1_stage2_metadata' has invalid structure.",
                )

            self._metadata = raw
            return copy.deepcopy(self._metadata)

    def get_top100_config_a_order(self) -> List[str]:
        """Return the canonical ordered list of 100 stop_ids from top100_hubs_config_a.csv."""
        if self._top100_a_ids is not None:
            return list(self._top100_a_ids)
        with self._lock:
            if self._top100_a_ids is not None:
                return list(self._top100_a_ids)
            if not self._top100_a_path.exists() or not self._top100_a_path.is_file():
                raise ArtifactUnavailableError(
                    code="ARTIFACT_MISSING",
                    message="Required spatial artifact 'top100_hubs_config_a' is unavailable.",
                )
            try:
                df_csv = pd.read_csv(self._top100_a_path, usecols=["stop_id"])
            except Exception as exc:
                logger.error("Failed to parse top100_hubs_config_a.csv: %s", type(exc).__name__)
                raise ArtifactUnavailableError(
                    code="ARTIFACT_CORRUPT",
                    message="Spatial artifact 'top100_hubs_config_a' could not be read.",
                ) from exc

            ids = [str(x).strip() for x in df_csv["stop_id"].tolist() if pd.notna(x)]
            if not ids:
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message="Spatial artifact 'top100_hubs_config_a' contains no valid stop_ids.",
                )
            self._top100_a_ids = ids
            return list(self._top100_a_ids)
