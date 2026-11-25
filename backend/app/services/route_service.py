"""Domain service for canonical CTA route directory and feature profiles."""

import re
from typing import Dict, Optional

import pandas as pd

from app.core.config import settings
from app.core.exceptions import EntityNotFoundError, InvalidParameterError
from app.repositories.parquet_repository import ParquetRepository
from app.schemas.common import (
    PaginationMeta,
    to_optional_float,
    to_optional_int,
    to_optional_str,
)
from app.schemas.route import (
    RouteCorridorMetrics,
    RouteDemandMetrics,
    RouteDetailResponse,
    RouteHubMetrics,
    RouteListResponse,
    RouteOperationalMetrics,
    RouteSummaryItem,
)


class RouteService:
    """Service providing read-only route listing, filtering, and detail profiles."""

    ALLOWED_SORT_FIELDS = {
        "route_id",
        "route_short_name",
        "scheduled_trips",
        "service_span_hours",
        "am_headway_min",
        "forecasted_daily_demand",
    }

    def __init__(self, parquet_repo: ParquetRepository) -> None:
        self._parquet_repo = parquet_repo
        self._route_id_regex = re.compile(settings.ROUTE_ID_PATTERN)

    def _validate_route_id(self, route_id: str) -> str:
        """Validate route_id format to prevent injection or path traversal."""
        cleaned = route_id.strip()
        if not self._route_id_regex.match(cleaned):
            raise InvalidParameterError(
                code="INVALID_ROUTE_ID",
                message="Invalid route identifier format.",
            )
        return cleaned

    def list_routes(
        self,
        mode: Optional[str] = None,
        cluster: Optional[str] = None,
        partition: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "route_id",
        order: str = "asc",
        limit: int = settings.DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> RouteListResponse:
        """Return a paginated, filtered, deterministically sorted list of routes."""
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
        if mode is not None and mode.lower() not in {"bus", "rail"}:
            raise InvalidParameterError(
                code="INVALID_MODE_FILTER",
                message="Mode filter must be 'bus' or 'rail'.",
            )

        summary_cols = [
            "route_id",
            "route_short_name",
            "route_long_name",
            "route_type",
            "is_rail",
            "operational_cluster_label",
            "regional_partition",
            "scheduled_trips",
            "service_span_hours",
            "am_headway_min",
            "forecasted_daily_demand",
        ]
        df = self._parquet_repo.get_feature_master(columns=summary_cols)
        mask = pd.Series(True, index=df.index)

        if mode is not None:
            is_rail_target = mode.lower() == "rail"
            mask &= df["is_rail"] == is_rail_target

        if cluster is not None and cluster.strip():
            target_cluster = cluster.strip().lower()
            mask &= df["operational_cluster_label"].fillna("").astype(str).str.lower() == target_cluster

        if partition is not None and partition.strip():
            target_part = partition.strip().lower()
            mask &= df["regional_partition"].fillna("").astype(str).str.lower() == target_part

        if search is not None and search.strip():
            q = search.strip().lower()
            mask &= (
                df["route_id"].astype(str).str.lower().str.contains(q, regex=False)
                | df["route_short_name"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
                | df["route_long_name"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
            )

        filtered = df.loc[mask].copy()
        ascending = order == "asc"
        if sort_by == "route_id":
            sorted_df = filtered.sort_values(by=["route_id"], ascending=[ascending], kind="mergesort")
        else:
            sorted_df = filtered.sort_values(
                by=[sort_by, "route_id"],
                ascending=[ascending, True],
                na_position="last",
                kind="mergesort",
            )

        total = len(sorted_df)
        page_df = sorted_df.iloc[offset : offset + limit]

        items = [
            RouteSummaryItem(
                route_id=str(row["route_id"]),
                route_short_name=str(row["route_short_name"]),
                route_long_name=str(row["route_long_name"]),
                route_type=int(row["route_type"]),
                is_rail=bool(row["is_rail"]),
                operational_cluster=to_optional_str(row["operational_cluster_label"]),
                regional_partition=to_optional_str(row["regional_partition"]),
                scheduled_trips=int(row["scheduled_trips"]),
                service_span_hours=float(row["service_span_hours"]),
                am_headway_min=to_optional_float(row["am_headway_min"]),
                forecasted_daily_demand=to_optional_float(row["forecasted_daily_demand"]),
            )
            for _, row in page_df.iterrows()
        ]

        active_filters: Dict[str, str] = {}
        if mode is not None:
            active_filters["mode"] = mode.lower()
        if cluster is not None and cluster.strip():
            active_filters["cluster"] = cluster.strip()
        if partition is not None and partition.strip():
            active_filters["partition"] = partition.strip()
        if search is not None and search.strip():
            active_filters["search"] = search.strip()

        return RouteListResponse(
            data=items,
            pagination=PaginationMeta(
                total=total,
                offset=offset,
                limit=limit,
                returned=len(items),
                has_more=(offset + len(items)) < total,
            ),
            filters=active_filters,
        )

    def get_route_detail(self, route_id: str) -> RouteDetailResponse:
        """Return verified feature profile for a single canonical route."""
        cleaned_id = self._validate_route_id(route_id)
        df = self._parquet_repo.get_feature_master()
        matches = df[df["route_id"] == cleaned_id]
        if matches.empty:
            raise EntityNotFoundError(
                code="ROUTE_NOT_FOUND",
                message=f"Route '{cleaned_id}' was not found in the canonical CTA network.",
            )

        row = matches.iloc[0]
        is_rail = bool(row["is_rail"])
        return RouteDetailResponse(
            route_id=str(row["route_id"]),
            route_short_name=str(row["route_short_name"]),
            route_long_name=str(row["route_long_name"]),
            route_type=int(row["route_type"]),
            is_rail=is_rail,
            regional_partition=to_optional_str(row["regional_partition"]),
            operational=RouteOperationalMetrics(
                scheduled_trips=int(row["scheduled_trips"]),
                service_span_hours=float(row["service_span_hours"]),
                am_headway_min=to_optional_float(row["am_headway_min"]),
                route_length_km=float(row["route_length_km"]),
                unique_stops_count=int(row["unique_stops_count"]),
                operational_cluster_k3=to_optional_int(row["operational_cluster_k3"]),
                operational_cluster_label=to_optional_str(row["operational_cluster_label"]),
            ),
            demand=RouteDemandMetrics(
                demand_metrics_available=not is_rail,
                historical_mean_daily_rides=to_optional_float(row["historical_mean_daily_rides"]),
                forecasted_daily_demand=to_optional_float(row["forecasted_daily_demand"]),
                rides_per_trip=to_optional_float(row["rides_per_trip"]),
                load_intensity_factor=to_optional_float(row["load_intensity_factor"]),
            ),
            hubs=RouteHubMetrics(
                hub_stop_count=int(row["hub_stop_count"]),
                hub_stop_ratio=float(row["hub_stop_ratio"]),
                hub_weighted_importance=float(row["hub_weighted_importance"]),
                hub_connectivity_index=float(row["hub_connectivity_index"]),
            ),
            corridor=RouteCorridorMetrics(
                max_corridor_overlap=float(row["max_corridor_overlap"]),
                mean_corridor_overlap=float(row["mean_corridor_overlap"]),
                shared_consecutive_stop_count=int(row["shared_consecutive_stop_count"]),
                corridor_duplication_ratio=float(row["corridor_duplication_ratio"]),
                corridor_duplication_index=float(row["corridor_duplication_index"]),
            ),
        )
