"""Domain service for Phase 6.1 spatial hubs, stop clusters, and bounding-box queries."""

from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.config import settings
from app.core.exceptions import InvalidParameterError
from app.repositories.spatial_repository import SpatialRepository
from app.schemas.common import PaginationMeta, to_optional_float, to_optional_int
from app.schemas.spatial import (
    BoundingBoxMeta,
    ClusterSummaryResponse,
    CoordinatePair,
    HubRankingItem,
    SpatialHubsListResponse,
    SpatialMethodologyMeta,
    SpatialStopHubItem,
    TopHubsResponse,
)


class SpatialService:
    """Service providing read-only spatial hub rankings, DBSCAN clusters, and map queries."""

    VALID_CONFIGS = {"a", "b", "c"}
    ALLOWED_SORT_FIELDS = {"rank", "score", "total_visits", "routes_served", "stop_id"}

    def __init__(self, spatial_repo: SpatialRepository) -> None:
        self._spatial_repo = spatial_repo

    def _validate_config(self, config: str) -> str:
        c = config.strip().lower()
        if c not in self.VALID_CONFIGS:
            raise InvalidParameterError(
                code="INVALID_HUB_CONFIG",
                message="Hub ranking config must be 'a', 'b', or 'c'.",
            )
        return c

    @staticmethod
    def _build_coordinates(lat_raw: Any, lon_raw: Any) -> CoordinatePair:
        lat = to_optional_float(lat_raw)
        lon = to_optional_float(lon_raw)
        if lat is None or lon is None or not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            return CoordinatePair(lat=None, lon=None, coordinates_available=False)
        return CoordinatePair(lat=lat, lon=lon, coordinates_available=True)

    @staticmethod
    def _validate_bbox(
        min_lat: Optional[float],
        min_lon: Optional[float],
        max_lat: Optional[float],
        max_lon: Optional[float],
    ) -> Optional[BoundingBoxMeta]:
        vals = [min_lat, min_lon, max_lat, max_lon]
        if all(v is None for v in vals):
            return None
        if any(v is None for v in vals):
            raise InvalidParameterError(
                code="INVALID_BBOX",
                message="All four bounding box parameters (min_lat, min_lon, max_lat, max_lon) must be provided together.",
            )
        assert min_lat is not None and min_lon is not None and max_lat is not None and max_lon is not None
        if not (-90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
            raise InvalidParameterError(
                code="INVALID_BBOX",
                message="Latitude bounds must be within [-90, 90].",
            )
        if not (-180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0):
            raise InvalidParameterError(
                code="INVALID_BBOX",
                message="Longitude bounds must be within [-180, 180].",
            )
        if min_lat > max_lat or min_lon > max_lon:
            raise InvalidParameterError(
                code="INVALID_BBOX",
                message="Bounding box min coordinates cannot exceed max coordinates.",
            )
        return BoundingBoxMeta(min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon)

    def get_top_hubs(
        self,
        config: str = "a",
        limit: int = settings.DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> TopHubsResponse:
        """Return paginated top-100 transit hubs for the selected weighting config."""
        cfg = self._validate_config(config)
        rank_col = f"rank_config_{cfg}"
        score_col = f"score_config_{cfg}"

        df = self._spatial_repo.get_hub_rankings()
        if cfg == "a":
            canonical_ids = self._spatial_repo.get_top100_config_a_order()
            order_map = {sid: idx for idx, sid in enumerate(canonical_ids)}
            top_df = df[df["stop_id"].isin(order_map)].copy()
            top_df["_canonical_order"] = top_df["stop_id"].map(order_map)
            top_df = top_df.sort_values(by=["_canonical_order"], ascending=[True], kind="mergesort")
            source_artifact = "artifacts/clustering/top100_hubs_config_a.csv + transit_hub_rankings.parquet"
        else:
            top_df = df.sort_values(
                by=[rank_col, "stop_id"],
                ascending=[True, True],
                kind="mergesort",
            ).head(100)
            source_artifact = "artifacts/clustering/transit_hub_rankings.parquet"

        total = len(top_df)
        page_df = top_df.iloc[offset : offset + limit]

        items = [
            HubRankingItem(
                rank=int(row[rank_col]),
                stop_id=str(row["stop_id"]),
                stop_name=str(row["stop_name"]),
                coordinates=self._build_coordinates(row["stop_lat"], row["stop_lon"]),
                config=cfg,
                hub_score=float(row[score_col]),
                total_visits=int(row["total_visits"]),
                routes_served=int(row["routes_served"]),
                attributed_demand_proxy=float(row["attributed_demand"]),
                demand_intensity=float(row["demand_intensity"]),
            )
            for _, row in page_df.iterrows()
        ]

        return TopHubsResponse(
            config=cfg,
            total_top_hubs=total,
            data=items,
            pagination=PaginationMeta(
                total=total,
                offset=offset,
                limit=limit,
                returned=len(items),
                has_more=(offset + len(items)) < total,
            ),
            methodology=SpatialMethodologyMeta(source_artifact=source_artifact),
        )

    def list_spatial_hubs(
        self,
        config: str = "a",
        min_routes: Optional[int] = None,
        dbscan_cluster: Optional[int] = None,
        eligible_only: bool = False,
        min_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lat: Optional[float] = None,
        max_lon: Optional[float] = None,
        sort_by: str = "rank",
        order: str = "asc",
        limit: int = settings.DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> SpatialHubsListResponse:
        """Return paginated, filtered spatial stops/hubs with DBSCAN and bounding-box filters."""
        cfg = self._validate_config(config)
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
        bbox = self._validate_bbox(min_lat, min_lon, max_lat, max_lon)

        rank_col = f"rank_config_{cfg}"
        score_col = f"score_config_{cfg}"

        df = self._spatial_repo.get_spatial_stops_with_clusters()
        mask = pd.Series(True, index=df.index)

        if eligible_only:
            mask &= df["hub_ranking_eligible"]
        if min_routes is not None:
            mask &= df["routes_served"].fillna(-1) >= min_routes
        if dbscan_cluster is not None:
            mask &= df["dbscan_cluster"] == dbscan_cluster
        if bbox is not None:
            mask &= (
                df["stop_lat"].notna()
                & df["stop_lon"].notna()
                & (df["stop_lat"] >= bbox.min_lat)
                & (df["stop_lat"] <= bbox.max_lat)
                & (df["stop_lon"] >= bbox.min_lon)
                & (df["stop_lon"] <= bbox.max_lon)
            )

        filtered = df.loc[mask].copy()
        sort_col_map = {
            "rank": rank_col,
            "score": score_col,
            "total_visits": "total_visits",
            "routes_served": "routes_served",
            "stop_id": "stop_id",
        }
        target_col = sort_col_map[sort_by]
        ascending = order == "asc"

        if target_col == "stop_id":
            sorted_df = filtered.sort_values(by=["stop_id"], ascending=[ascending], kind="mergesort")
        else:
            sorted_df = filtered.sort_values(
                by=[target_col, "stop_id"],
                ascending=[ascending, True],
                na_position="last",
                kind="mergesort",
            )

        total = len(sorted_df)
        page_df = sorted_df.iloc[offset : offset + limit]

        items: List[SpatialStopHubItem] = []
        for _, row in page_df.iterrows():
            cluster_id = int(row["dbscan_cluster"])
            items.append(
                SpatialStopHubItem(
                    stop_id=str(row["stop_id"]),
                    stop_name=str(row["stop_name"]),
                    coordinates=self._build_coordinates(row["stop_lat"], row["stop_lon"]),
                    dbscan_cluster=cluster_id,
                    is_noise_point=(cluster_id == -1),
                    hub_ranking_eligible=bool(row["hub_ranking_eligible"]),
                    rank=to_optional_int(row[rank_col]),
                    hub_score=to_optional_float(row[score_col]),
                    total_visits=to_optional_int(row["total_visits"]),
                    routes_served=to_optional_int(row["routes_served"]),
                    attributed_demand_proxy=to_optional_float(row["attributed_demand"]),
                    demand_intensity=to_optional_float(row["demand_intensity"]),
                )
            )

        active_filters: Dict[str, Any] = {"config": cfg, "eligible_only": eligible_only}
        if min_routes is not None:
            active_filters["min_routes"] = min_routes
        if dbscan_cluster is not None:
            active_filters["dbscan_cluster"] = dbscan_cluster

        return SpatialHubsListResponse(
            config=cfg,
            data=items,
            pagination=PaginationMeta(
                total=total,
                offset=offset,
                limit=limit,
                returned=len(items),
                has_more=(offset + len(items)) < total,
            ),
            bounding_box=bbox,
            filters=active_filters,
            methodology=SpatialMethodologyMeta(
                source_artifact="artifacts/clustering/spatial_dbscan_assignments.parquet + transit_hub_rankings.parquet"
            ),
        )

    def get_cluster_summary(self) -> ClusterSummaryResponse:
        """Return Phase 6.1 DBSCAN and KMeans clustering summary metadata."""
        meta = self._spatial_repo.get_cluster_metadata()
        return ClusterSummaryResponse(
            snapshot_id=str(meta["snapshot_id"]),
            representative_service_date=str(meta["representative_service_date"]),
            demand_attribution_period=str(meta["demand_attribution_period"]),
            boarding_stops_input_count=int(meta["boarding_stops_input_count"]),
            active_stop_visits_count=int(meta["active_stop_visits_count"]),
            dbscan_parameters=dict(meta["dbscan_parameters"]),
            dbscan_cluster_count=int(meta["dbscan_cluster_count"]),
            dbscan_noise_stop_count=int(meta["dbscan_noise_stop_count"]),
            dbscan_chained_cluster_count=int(meta["dbscan_chained_cluster_count"]),
            kmeans_parameters=dict(meta["kmeans_parameters"]),
            kmeans_eligible_stops_count=int(meta["kmeans_eligible_stops_count"]),
            hub_ranking_sensitivity=dict(meta["hub_ranking_sensitivity"]),
            coverage_metrics=dict(meta["coverage_metrics"]),
            methodology=SpatialMethodologyMeta(
                source_artifact="artifacts/clustering/phase6_1_stage2_metadata.json"
            ),
        )
