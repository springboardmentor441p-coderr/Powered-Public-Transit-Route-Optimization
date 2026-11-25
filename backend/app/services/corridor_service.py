"""Domain service for Phase 6.2 & 6.3 corridor clusters and route co-routing topology."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.core.config import settings
from app.core.exceptions import EntityNotFoundError, InvalidParameterError
from app.repositories.corridor_repository import CorridorRepository
from app.repositories.parquet_repository import ParquetRepository
from app.schemas.common import PaginationMeta, to_optional_float, to_optional_int, to_optional_str
from app.schemas.corridor import (
    CoRoutingPeerItem,
    CorridorClusterItem,
    CorridorClusterListResponse,
    CorridorMethodologyMeta,
    PatternCoRoutingProfile,
    RouteCoRoutingResponse,
    SharedStopSequenceItem,
)


class CorridorService:
    """Service providing read-only corridor clusters and directional co-routing topology."""

    CLUSTER_TYPE_MAP = {
        "buffer": "geographic_buffer_overlap",
        "frechet": "geometric_frechet_shape",
    }
    ALLOWED_SORT_FIELDS = {
        "pattern_id",
        "route_id",
        "cluster_id",
        "length_km",
        "hub_stop_ratio",
        "scheduled_trip_count",
    }

    def __init__(
        self,
        corridor_repo: CorridorRepository,
        parquet_repo: ParquetRepository,
    ) -> None:
        self._corridor_repo = corridor_repo
        self._parquet_repo = parquet_repo
        self._route_id_regex = re.compile(settings.ROUTE_ID_PATTERN)

    def _validate_route_id(self, route_id: str) -> str:
        cleaned = route_id.strip()
        if not self._route_id_regex.match(cleaned):
            raise InvalidParameterError(
                code="INVALID_ROUTE_ID",
                message="Invalid route identifier format.",
            )
        return cleaned

    @staticmethod
    def _parse_pattern_id(pattern_id: str) -> Tuple[str, Optional[int]]:
        """Extract (route_id, direction_id) from '{route_id}__dir_{d}'."""
        if "__dir_" in pattern_id:
            r_part, d_part = pattern_id.rsplit("__dir_", 1)
            try:
                return r_part, int(d_part)
            except ValueError:
                return r_part, None
        return pattern_id, None

    def list_corridor_clusters(
        self,
        k: int = 3,
        cluster_type: str = "buffer",
        cluster_id: Optional[int] = None,
        mode: Optional[str] = None,
        route_id: Optional[str] = None,
        direction_id: Optional[int] = None,
        sort_by: str = "pattern_id",
        order: str = "asc",
        limit: int = settings.DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> CorridorClusterListResponse:
        """Retrieve paginated, deterministically sorted directional corridor cluster assignments."""
        if k < 2 or k > 12:
            raise InvalidParameterError(
                code="INVALID_CLUSTER_K",
                message="Cluster count k must be between 2 and 12.",
            )
        ctype_key = cluster_type.strip().lower()
        if ctype_key not in self.CLUSTER_TYPE_MAP:
            raise InvalidParameterError(
                code="INVALID_CLUSTER_TYPE",
                message="cluster_type must be 'buffer' or 'frechet'.",
            )
        if mode is not None and mode.lower() not in {"bus", "rail"}:
            raise InvalidParameterError(
                code="INVALID_MODE_FILTER",
                message="Mode filter must be 'bus' or 'rail'.",
            )
        if direction_id is not None and direction_id not in {0, 1}:
            raise InvalidParameterError(
                code="INVALID_DIRECTION_ID",
                message="direction_id must be 0 or 1.",
            )
        if sort_by not in self.ALLOWED_SORT_FIELDS:
            raise InvalidParameterError(
                code="INVALID_SORT_FIELD",
                message=f"Unsupported sort_by field '{sort_by}'.",
                details={"allowed_fields": sorted(self.ALLOWED_SORT_FIELDS)},
            )
        if order not in {"asc", "desc"}:
            raise InvalidParameterError(
                code="INVALID_SORT_ORDER",
                message="Sort order must be 'asc' or 'desc'.",
            )

        cleaned_route_id: Optional[str] = None
        if route_id is not None and route_id.strip():
            cleaned_route_id = self._validate_route_id(route_id)

        clusters_df = self._corridor_repo.get_corridor_clusters()
        geo_df = self._corridor_repo.get_geometries_metadata()[
            ["pattern_id", "scheduled_trip_count", "length_km"]
        ]
        conn_df = self._corridor_repo.get_connectivity_matrix()[
            ["pattern_id", "hub_stop_count", "hub_stop_ratio"]
        ]
        feat_df = self._parquet_repo.get_feature_master(
            columns=[
                "route_id",
                "route_short_name",
                "route_long_name",
                "is_rail",
                "operational_cluster_label",
            ]
        )

        merged = (
            clusters_df.merge(geo_df, on="pattern_id", how="left")
            .merge(conn_df, on="pattern_id", how="left")
            .merge(feat_df, on="route_id", how="left")
        )

        buf_col = f"cluster_buffer_k{k}"
        fre_col = f"cluster_frechet_k{k}"
        target_cluster_col = buf_col if ctype_key == "buffer" else fre_col
        merged["cluster_id"] = merged[target_cluster_col]

        mask = pd.Series(True, index=merged.index)
        if cluster_id is not None:
            mask &= merged["cluster_id"] == cluster_id
        if mode is not None:
            mask &= merged["is_rail"] == (mode.lower() == "rail")
        if cleaned_route_id is not None:
            mask &= merged["route_id"] == cleaned_route_id
        if direction_id is not None:
            mask &= merged["direction_id"] == direction_id

        filtered = merged.loc[mask].copy()
        ascending = order == "asc"
        if sort_by == "pattern_id":
            sorted_df = filtered.sort_values(by=["pattern_id"], ascending=[ascending], kind="mergesort")
        else:
            sorted_df = filtered.sort_values(
                by=[sort_by, "pattern_id"],
                ascending=[ascending, True],
                na_position="last",
                kind="mergesort",
            )

        total = len(sorted_df)
        page_df = sorted_df.iloc[offset : offset + limit]
        resolved_ctype = self.CLUSTER_TYPE_MAP[ctype_key]

        items = [
            CorridorClusterItem(
                pattern_id=str(row["pattern_id"]),
                route_id=str(row["route_id"]),
                direction_id=int(row["direction_id"]),
                route_short_name=to_optional_str(row["route_short_name"]),
                route_long_name=to_optional_str(row["route_long_name"]),
                is_rail=bool(row["is_rail"]) if pd.notna(row["is_rail"]) else None,
                operational_cluster_label=to_optional_str(row["operational_cluster_label"]),
                k=k,
                cluster_type=resolved_ctype,  # type: ignore[arg-type]
                cluster_id=int(row["cluster_id"]),
                buffer_cluster_id=int(row[buf_col]),
                frechet_cluster_id=int(row[fre_col]),
                length_km=to_optional_float(row["length_km"]),
                scheduled_trip_count=to_optional_int(row["scheduled_trip_count"]),
                hub_stop_count=to_optional_int(row["hub_stop_count"]),
                hub_stop_ratio=to_optional_float(row["hub_stop_ratio"]),
            )
            for _, row in page_df.iterrows()
        ]

        active_filters: Dict[str, Any] = {"k": k, "cluster_type": resolved_ctype}
        if cluster_id is not None:
            active_filters["cluster_id"] = cluster_id
        if mode is not None:
            active_filters["mode"] = mode.lower()
        if cleaned_route_id is not None:
            active_filters["route_id"] = cleaned_route_id
        if direction_id is not None:
            active_filters["direction_id"] = direction_id

        return CorridorClusterListResponse(
            k=k,
            cluster_type=resolved_ctype,  # type: ignore[arg-type]
            data=items,
            pagination=PaginationMeta(
                total=total,
                offset=offset,
                limit=limit,
                returned=len(items),
                has_more=(offset + len(items)) < total,
            ),
            filters=active_filters,
            methodology=CorridorMethodologyMeta(
                source_artifacts=[
                    "artifacts/route_clustering/corridor_cluster_assignments.parquet",
                    "artifacts/route_clustering/route_direction_geometries_metadata.parquet",
                    "artifacts/ranking_features/route_direction_connectivity_matrix.parquet",
                ]
            ),
        )

    def _extract_matrix_peers(
        self,
        matrix_df: pd.DataFrame,
        pattern_id: str,
        metric_type: str,
        min_similarity: float,
        top_n: int,
    ) -> Tuple[List[CoRoutingPeerItem], int]:
        """Extract top-N non-self valid peer entries from a similarity matrix, omitting NaNs."""
        if pattern_id not in matrix_df.index:
            return [], 0

        series = matrix_df.loc[pattern_id]
        missing_count = 0
        candidates: List[Tuple[str, float]] = []

        for peer_pid, raw_val in series.items():
            peer_str = str(peer_pid)
            if peer_str == pattern_id:
                continue
            val = to_optional_float(raw_val)
            if val is None:
                missing_count += 1
                continue
            if val >= min_similarity:
                candidates.append((peer_str, val))

        candidates.sort(key=lambda x: (-x[1], x[0]))
        peers: List[CoRoutingPeerItem] = []
        for peer_pid, score in candidates[:top_n]:
            peer_route, peer_dir = self._parse_pattern_id(peer_pid)
            peers.append(
                CoRoutingPeerItem(
                    peer_pattern_id=peer_pid,
                    peer_route_id=peer_route,
                    peer_direction_id=peer_dir,
                    similarity_score=score,
                    metric_type=metric_type,  # type: ignore[arg-type]
                )
            )
        return peers, missing_count

    def get_route_co_routing(
        self,
        route_id: str,
        direction_id: Optional[int] = None,
        min_similarity: float = 0.0,
        top_n: int = 10,
    ) -> RouteCoRoutingResponse:
        """Return directional co-routing metrics and shared stop sequences for a canonical route."""
        cleaned_id = self._validate_route_id(route_id)
        if direction_id is not None and direction_id not in {0, 1}:
            raise InvalidParameterError(
                code="INVALID_DIRECTION_ID",
                message="direction_id must be 0 or 1.",
            )
        if min_similarity < 0.0 or min_similarity > 1.0:
            raise InvalidParameterError(
                code="INVALID_SIMILARITY_THRESHOLD",
                message="min_similarity must be between 0.0 and 1.0.",
            )

        feat_df = self._parquet_repo.get_feature_master(
            columns=[
                "route_id",
                "route_short_name",
                "route_long_name",
                "is_rail",
                "operational_cluster_label",
                "corridor_duplication_index",
            ]
        )
        route_matches = feat_df[feat_df["route_id"] == cleaned_id]
        if route_matches.empty:
            raise EntityNotFoundError(
                code="ROUTE_NOT_FOUND",
                message=f"Route '{cleaned_id}' was not found in the canonical CTA network.",
            )
        route_row = route_matches.iloc[0]

        clusters_df = self._corridor_repo.get_corridor_clusters()
        geo_df = self._corridor_repo.get_geometries_metadata()
        conn_df = self._corridor_repo.get_connectivity_matrix()
        buf_matrix = self._corridor_repo.get_buffer_similarity_matrix()
        jac_matrix = self._corridor_repo.get_jaccard_similarity_matrix()
        seq_df = self._corridor_repo.get_shared_stop_sequences()

        route_patterns = clusters_df[clusters_df["route_id"] == cleaned_id].sort_values(
            by=["direction_id", "pattern_id"], kind="mergesort"
        )
        if direction_id is not None:
            route_patterns = route_patterns[route_patterns["direction_id"] == direction_id]

        profiles: List[PatternCoRoutingProfile] = []
        for _, p_row in route_patterns.iterrows():
            pid = str(p_row["pattern_id"])
            did = int(p_row["direction_id"])

            geo_match = geo_df[geo_df["pattern_id"] == pid]
            conn_match = conn_df[conn_df["pattern_id"] == pid]

            length_km = to_optional_float(geo_match.iloc[0]["length_km"]) if not geo_match.empty else None
            trips = to_optional_int(geo_match.iloc[0]["scheduled_trip_count"]) if not geo_match.empty else None
            hub_cnt = to_optional_int(conn_match.iloc[0]["hub_stop_count"]) if not conn_match.empty else None
            hub_rat = to_optional_float(conn_match.iloc[0]["hub_stop_ratio"]) if not conn_match.empty else None

            buf_peers, buf_missing = self._extract_matrix_peers(
                buf_matrix, pid, "geographic_buffer_overlap", min_similarity, top_n
            )
            jac_peers, jac_missing = self._extract_matrix_peers(
                jac_matrix, pid, "stop_set_jaccard_similarity", min_similarity, top_n
            )

            seq_matches = seq_df[(seq_df["pattern_a"] == pid) | (seq_df["pattern_b"] == pid)].copy()
            seq_items: List[SharedStopSequenceItem] = []
            for _, s_row in seq_matches.iterrows():
                pa = str(s_row["pattern_a"])
                pb = str(s_row["pattern_b"])
                peer_pid = pb if pa == pid else pa
                peer_route, _ = self._parse_pattern_id(peer_pid)
                try:
                    stops_list = [str(x) for x in json.loads(str(s_row["shared_stops_json"]))]
                except Exception:
                    stops_list = []
                seq_items.append(
                    SharedStopSequenceItem(
                        pattern_a=pa,
                        pattern_b=pb,
                        peer_pattern_id=peer_pid,
                        peer_route_id=peer_route,
                        sequence_length=int(s_row["sequence_length"]),
                        start_stop_id=str(s_row["start_stop_id"]),
                        end_stop_id=str(s_row["end_stop_id"]),
                        shared_stops=stops_list,
                    )
                )
            seq_items.sort(key=lambda s: (-s.sequence_length, s.peer_pattern_id, s.start_stop_id))

            profiles.append(
                PatternCoRoutingProfile(
                    pattern_id=pid,
                    route_id=cleaned_id,
                    direction_id=did,
                    length_km=length_km,
                    scheduled_trip_count=trips,
                    hub_stop_count=hub_cnt,
                    hub_stop_ratio=hub_rat,
                    buffer_cluster_k3=to_optional_int(p_row.get("cluster_buffer_k3")),
                    frechet_cluster_k3=to_optional_int(p_row.get("cluster_frechet_k3")),
                    missing_buffer_entries_count=buf_missing,
                    missing_jaccard_entries_count=jac_missing,
                    geographic_overlap_peers=buf_peers,
                    stop_jaccard_peers=jac_peers,
                    shared_consecutive_sequences=seq_items[:top_n],
                )
            )

        return RouteCoRoutingResponse(
            route_id=cleaned_id,
            route_short_name=str(route_row["route_short_name"]),
            route_long_name=str(route_row["route_long_name"]),
            is_rail=bool(route_row["is_rail"]),
            operational_cluster_label=to_optional_str(route_row["operational_cluster_label"]),
            corridor_duplication_index=to_optional_float(route_row["corridor_duplication_index"]),
            patterns=profiles,
            methodology=CorridorMethodologyMeta(
                source_artifacts=[
                    "artifacts/route_clustering/buffer_overlap_similarity_matrix.parquet",
                    "artifacts/route_clustering/route_direction_jaccard_matrix.parquet",
                    "artifacts/route_clustering/shared_consecutive_stop_sequences.parquet",
                    "artifacts/route_clustering/corridor_cluster_assignments.parquet",
                ]
            ),
        )
