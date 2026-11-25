"""Read-only repository for Phase 6.2 & 6.3 corridor clustering and similarity artifacts."""

import logging
import threading
from pathlib import Path
from typing import List, Optional

import pandas as pd

from app.core.config import settings
from app.core.exceptions import ArtifactUnavailableError

logger = logging.getLogger("ai_routeranker.repositories.corridor")


class CorridorRepository:
    """
    Read-only repository for Phase 6.2 corridor clustering, similarity matrices,
    shared stop sequences, geometries metadata, and Phase 6.3 connectivity matrix.

    Uses thread-safe lazy caching, schema/shape validation, and frozen NumPy arrays.
    """

    CLUSTERS_REQUIRED_COLUMNS: List[str] = [
        "pattern_id",
        "route_id",
        "direction_id",
    ] + [f"cluster_buffer_k{k}" for k in range(2, 13)] + [
        f"cluster_frechet_k{k}" for k in range(2, 13)
    ]

    SEQUENCES_REQUIRED_COLUMNS: List[str] = [
        "pattern_a",
        "pattern_b",
        "sequence_length",
        "start_stop_id",
        "end_stop_id",
        "shared_stops_json",
    ]

    GEOMETRIES_REQUIRED_COLUMNS: List[str] = [
        "pattern_id",
        "route_id",
        "direction_id",
        "scheduled_trip_count",
        "length_km",
    ]

    CONNECTIVITY_REQUIRED_COLUMNS: List[str] = [
        "pattern_id",
        "route_id",
        "direction_id",
        "hub_stop_count",
        "hub_stop_ratio",
    ]

    def __init__(
        self,
        clusters_path: Optional[Path] = None,
        buffer_matrix_path: Optional[Path] = None,
        jaccard_matrix_path: Optional[Path] = None,
        sequences_path: Optional[Path] = None,
        geometries_path: Optional[Path] = None,
        connectivity_path: Optional[Path] = None,
    ) -> None:
        self._clusters_path = Path(clusters_path or settings.CORRIDOR_CLUSTERS_PATH)
        self._buffer_path = Path(buffer_matrix_path or settings.BUFFER_SIMILARITY_PATH)
        self._jaccard_path = Path(jaccard_matrix_path or settings.JACCARD_SIMILARITY_PATH)
        self._sequences_path = Path(sequences_path or settings.SHARED_SEQUENCES_PATH)
        self._geometries_path = Path(geometries_path or settings.GEOMETRIES_META_PATH)
        self._connectivity_path = Path(connectivity_path or settings.CONNECTIVITY_MATRIX_PATH)

        self._lock = threading.Lock()
        self._clusters_df: Optional[pd.DataFrame] = None
        self._buffer_df: Optional[pd.DataFrame] = None
        self._jaccard_df: Optional[pd.DataFrame] = None
        self._sequences_df: Optional[pd.DataFrame] = None
        self._geometries_df: Optional[pd.DataFrame] = None
        self._connectivity_df: Optional[pd.DataFrame] = None

    def clear_cache(self) -> None:
        """Clear in-memory cached corridor artifacts."""
        with self._lock:
            self._clusters_df = None
            self._buffer_df = None
            self._jaccard_df = None
            self._sequences_df = None
            self._geometries_df = None
            self._connectivity_df = None

    @staticmethod
    def _freeze_dataframe(df: pd.DataFrame) -> pd.DataFrame:
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
        artifact_label: str,
        required_columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        if not path.exists() or not path.is_file():
            logger.error("Required corridor artifact '%s' is missing.", artifact_label)
            raise ArtifactUnavailableError(
                code="ARTIFACT_MISSING",
                message=f"Required corridor artifact '{artifact_label}' is unavailable.",
            )
        try:
            df = (
                pd.read_parquet(path, columns=required_columns)
                if required_columns is not None
                else pd.read_parquet(path)
            )
        except KeyError as exc:
            raise ArtifactUnavailableError(
                code="ARTIFACT_SCHEMA_INVALID",
                message=f"Corridor artifact '{artifact_label}' does not match expected schema.",
            ) from exc
        except Exception as exc:
            logger.error("Failed to read corridor artifact '%s': %s", artifact_label, type(exc).__name__)
            raise ArtifactUnavailableError(
                code="ARTIFACT_CORRUPT",
                message=f"Corridor artifact '{artifact_label}' could not be read.",
            ) from exc

        if required_columns is not None:
            missing = [c for c in required_columns if c not in df.columns]
            if missing:
                raise ArtifactUnavailableError(
                    code="ARTIFACT_SCHEMA_INVALID",
                    message=f"Corridor artifact '{artifact_label}' is missing required fields.",
                )
        return df

    def get_corridor_clusters(self) -> pd.DataFrame:
        """Return cached corridor cluster assignments DataFrame."""
        if self._clusters_df is not None:
            return self._clusters_df
        with self._lock:
            if self._clusters_df is not None:
                return self._clusters_df
            df = self._read_parquet_safe(
                self._clusters_path,
                "corridor_cluster_assignments",
                self.CLUSTERS_REQUIRED_COLUMNS,
            )
            df["pattern_id"] = df["pattern_id"].astype(str).str.strip()
            df["route_id"] = df["route_id"].astype(str).str.strip()
            self._clusters_df = self._freeze_dataframe(df)
            return self._clusters_df

    def get_geometries_metadata(self) -> pd.DataFrame:
        """Return cached route-direction geometries metadata DataFrame."""
        if self._geometries_df is not None:
            return self._geometries_df
        with self._lock:
            if self._geometries_df is not None:
                return self._geometries_df
            df = self._read_parquet_safe(
                self._geometries_path,
                "route_direction_geometries_metadata",
                self.GEOMETRIES_REQUIRED_COLUMNS,
            )
            df["pattern_id"] = df["pattern_id"].astype(str).str.strip()
            df["route_id"] = df["route_id"].astype(str).str.strip()
            self._geometries_df = self._freeze_dataframe(df)
            return self._geometries_df

    def get_connectivity_matrix(self) -> pd.DataFrame:
        """Return cached Phase 6.3 route-direction connectivity matrix DataFrame."""
        if self._connectivity_df is not None:
            return self._connectivity_df
        with self._lock:
            if self._connectivity_df is not None:
                return self._connectivity_df
            df = self._read_parquet_safe(
                self._connectivity_path,
                "route_direction_connectivity_matrix",
                self.CONNECTIVITY_REQUIRED_COLUMNS,
            )
            df["pattern_id"] = df["pattern_id"].astype(str).str.strip()
            df["route_id"] = df["route_id"].astype(str).str.strip()
            self._connectivity_df = self._freeze_dataframe(df)
            return self._connectivity_df

    def _load_square_matrix(self, path: Path, label: str) -> pd.DataFrame:
        df = self._read_parquet_safe(path, label, required_columns=None)
        if df.empty or df.shape[0] != df.shape[1]:
            raise ArtifactUnavailableError(
                code="ARTIFACT_SCHEMA_INVALID",
                message=f"Corridor similarity matrix '{label}' has invalid dimensions.",
            )
        df.index = df.index.astype(str).str.strip()
        df.columns = [str(c).strip() for c in df.columns]
        return self._freeze_dataframe(df)

    def get_buffer_similarity_matrix(self) -> pd.DataFrame:
        """Return cached 261x261 geographic buffer overlap similarity matrix."""
        if self._buffer_df is not None:
            return self._buffer_df
        with self._lock:
            if self._buffer_df is not None:
                return self._buffer_df
            self._buffer_df = self._load_square_matrix(
                self._buffer_path, "buffer_overlap_similarity_matrix"
            )
            return self._buffer_df

    def get_jaccard_similarity_matrix(self) -> pd.DataFrame:
        """Return cached 261x261 stop-set Jaccard similarity matrix."""
        if self._jaccard_df is not None:
            return self._jaccard_df
        with self._lock:
            if self._jaccard_df is not None:
                return self._jaccard_df
            self._jaccard_df = self._load_square_matrix(
                self._jaccard_path, "route_direction_jaccard_matrix"
            )
            return self._jaccard_df

    def get_shared_stop_sequences(self) -> pd.DataFrame:
        """Return cached shared consecutive stop sequences DataFrame."""
        if self._sequences_df is not None:
            return self._sequences_df
        with self._lock:
            if self._sequences_df is not None:
                return self._sequences_df
            df = self._read_parquet_safe(
                self._sequences_path,
                "shared_consecutive_stop_sequences",
                self.SEQUENCES_REQUIRED_COLUMNS,
            )
            df["pattern_a"] = df["pattern_a"].astype(str).str.strip()
            df["pattern_b"] = df["pattern_b"].astype(str).str.strip()
            self._sequences_df = self._freeze_dataframe(df)
            return self._sequences_df
