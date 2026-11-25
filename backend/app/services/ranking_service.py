"""Domain service for serving canonical multi-criteria route rankings, explanations, and sensitivity."""

import re
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.config import settings
from app.core.exceptions import EntityNotFoundError, InvalidParameterError
from app.repositories.json_repository import JSONRepository
from app.repositories.parquet_repository import ParquetRepository
from app.schemas.common import PaginationMeta, to_optional_float, to_optional_str
from app.schemas.ranking import (
    FeatureDriver,
    RankingItem,
    RankingListResponse,
    RankingPillars,
    RouteExplanationResponse,
    SensitivityListResponse,
    SensitivityScenarioItem,
)


class RankingService:
    """
    Service serving canonical Phase 7 multi-criteria rankings, explanations, and sensitivity.

    Strictly isolates BUS_PRIORITY, RAIL_PRIORITY, and UNIFIED_SUPPLY tracks and
    never recalculates rankings inside API requests.
    """

    VALID_TRACKS = {"BUS_PRIORITY", "RAIL_PRIORITY", "UNIFIED_SUPPLY"}
    ALLOWED_SORT_FIELDS = {
        "rank",
        "overall_score",
        "topsis_score",
        "topsis_rank",
        "pillar_demand_score",
        "pillar_service_score",
        "pillar_hub_score",
        "pillar_corridor_score",
        "route_id",
    }
    CONTRIB_COLUMN_MAP = {
        "forecasted_daily_demand_norm": "contrib_forecasted_daily_demand",
        "load_intensity_factor_norm": "contrib_load_intensity_factor",
        "scheduled_trips_norm": "contrib_scheduled_trips",
        "service_span_hours_norm": "contrib_service_span_hours",
        "am_headway_min_norm": "contrib_am_headway_min",
        "hub_stop_ratio_norm": "contrib_hub_stop_ratio",
        "corridor_duplication_index_norm": "contrib_corridor_duplication_index",
    }

    def __init__(
        self,
        parquet_repo: ParquetRepository,
        json_repo: JSONRepository,
    ) -> None:
        self._parquet_repo = parquet_repo
        self._json_repo = json_repo
        self._route_id_regex = re.compile(settings.ROUTE_ID_PATTERN)

    def _validate_route_id(self, route_id: str) -> str:
        cleaned = route_id.strip()
        if not self._route_id_regex.match(cleaned):
            raise InvalidParameterError(
                code="INVALID_ROUTE_ID",
                message="Invalid route identifier format.",
            )
        return cleaned

    def _build_ranking_item(self, row: pd.Series, track: str) -> RankingItem:
        """Convert a rankings master row + lightweight weight metadata into RankingItem."""
        route_id = str(row["route_id"])
        weight_meta = self._json_repo.get_weight_metadata(route_id=route_id, track=track)

        contributions: Dict[str, Optional[float]] = {
            key: to_optional_float(row[col])
            for key, col in self.CONTRIB_COLUMN_MAP.items()
        }

        if weight_meta is not None:
            original_weights = weight_meta["original_weights"]
            effective_weights = weight_meta["effective_weights"]
            missing_criteria = weight_meta["missing_criteria"]
            valid_coverage = weight_meta["valid_weight_coverage"]
        else:
            original_weights = {}
            effective_weights = {}
            missing_criteria = []
            valid_coverage = 1.0

        am_headway = to_optional_float(row["am_headway_min"])
        is_headway_missing = (am_headway is None) or ("am_headway_min_norm" in missing_criteria)

        return RankingItem(
            rank=int(row["rank"]),
            route_id=route_id,
            route_short_name=str(row["route_short_name"]),
            route_long_name=str(row["route_long_name"]),
            is_rail=bool(row["is_rail"]),
            track=str(row["track"]),
            profile=str(row["profile"]),
            overall_score=float(row["overall_score"]),
            percentile_rank=float(row["percentile_rank"]),
            topsis_score=float(row["topsis_score"]),
            topsis_rank=int(row["topsis_rank"]),
            scheduled_trips=int(row["scheduled_trips"]),
            service_span_hours=float(row["service_span_hours"]),
            am_headway_min=am_headway,
            corridor_duplication_index=float(row["corridor_duplication_index"]),
            operational_cluster=to_optional_str(row["operational_cluster_label"]),
            regional_partition=to_optional_str(row["regional_partition"]),
            pillars=RankingPillars(
                demand_pressure=float(row["pillar_demand_score"]),
                service_provision=float(row["pillar_service_score"]),
                network_hubs=float(row["pillar_hub_score"]),
                corridor_structure=float(row["pillar_corridor_score"]),
            ),
            contributions=contributions,
            original_weights=original_weights,
            effective_weights=effective_weights,
            valid_weight_coverage=round(float(valid_coverage), 6),
            is_headway_missing=is_headway_missing,
            missing_criteria=missing_criteria,
        )

    def _query_track_rankings(
        self,
        track: str,
        mode: Optional[str] = None,
        partition: Optional[str] = None,
        min_rank: Optional[int] = None,
        max_rank: Optional[int] = None,
        sort_by: str = "rank",
        order: str = "asc",
        limit: int = settings.DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> RankingListResponse:
        """Execute isolated track filtering, sorting, and pagination."""
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
        if min_rank is not None and max_rank is not None and min_rank > max_rank:
            raise InvalidParameterError(
                code="INVALID_RANK_RANGE",
                message="min_rank cannot exceed max_rank.",
            )
        if mode is not None and mode.lower() not in {"bus", "rail"}:
            raise InvalidParameterError(
                code="INVALID_MODE_FILTER",
                message="Mode filter must be 'bus' or 'rail'.",
            )

        df = self._parquet_repo.get_rankings_master()
        track_df = df[df["track"] == track]
        total_track_routes = len(track_df)
        profile_name = str(track_df["profile"].iloc[0]) if not track_df.empty else track

        mask = pd.Series(True, index=track_df.index)
        if mode is not None:
            mask &= track_df["is_rail"] == (mode.lower() == "rail")
        if partition is not None and partition.strip():
            mask &= (
                track_df["regional_partition"].fillna("").astype(str).str.lower()
                == partition.strip().lower()
            )
        if min_rank is not None:
            mask &= track_df["rank"] >= min_rank
        if max_rank is not None:
            mask &= track_df["rank"] <= max_rank

        filtered = track_df.loc[mask].copy()
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

        total_filtered = len(sorted_df)
        page_df = sorted_df.iloc[offset : offset + limit]
        items = [self._build_ranking_item(row, track) for _, row in page_df.iterrows()]

        active_filters: Dict[str, Any] = {}
        if mode is not None:
            active_filters["mode"] = mode.lower()
        if partition is not None and partition.strip():
            active_filters["partition"] = partition.strip()
        if min_rank is not None:
            active_filters["min_rank"] = min_rank
        if max_rank is not None:
            active_filters["max_rank"] = max_rank

        return RankingListResponse(
            track=track,
            profile=profile_name,
            total_routes=total_track_routes,
            data=items,
            pagination=PaginationMeta(
                total=total_filtered,
                offset=offset,
                limit=limit,
                returned=len(items),
                has_more=(offset + len(items)) < total_filtered,
            ),
            filters=active_filters,
        )

    def get_bus_rankings(
        self,
        partition: Optional[str] = None,
        min_rank: Optional[int] = None,
        max_rank: Optional[int] = None,
        sort_by: str = "rank",
        order: str = "asc",
        limit: int = settings.DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> RankingListResponse:
        """Serve Track 1: Bus Network Priority rankings (125 bus routes)."""
        return self._query_track_rankings(
            track="BUS_PRIORITY",
            partition=partition,
            min_rank=min_rank,
            max_rank=max_rank,
            sort_by=sort_by,
            order=order,
            limit=limit,
            offset=offset,
        )

    def get_rail_rankings(
        self,
        sort_by: str = "rank",
        order: str = "asc",
    ) -> RankingListResponse:
        """Serve Track 2: Heavy Rail Operational Priority rankings (8 rail lines)."""
        return self._query_track_rankings(
            track="RAIL_PRIORITY",
            sort_by=sort_by,
            order=order,
            limit=25,
            offset=0,
        )

    def get_unified_rankings(
        self,
        mode: Optional[str] = None,
        min_rank: Optional[int] = None,
        max_rank: Optional[int] = None,
        sort_by: str = "rank",
        order: str = "asc",
        limit: int = settings.DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> RankingListResponse:
        """Serve Track 3: Unified Operational Supply rankings (133 routes)."""
        return self._query_track_rankings(
            track="UNIFIED_SUPPLY",
            mode=mode,
            min_rank=min_rank,
            max_rank=max_rank,
            sort_by=sort_by,
            order=order,
            limit=limit,
            offset=offset,
        )

    def get_route_explanation(
        self,
        route_id: str,
        track: Optional[str] = None,
    ) -> RouteExplanationResponse:
        """Return precomputed ranking explanation and weight breakdown for a route."""
        cleaned_id = self._validate_route_id(route_id)

        if track is not None:
            resolved_track = track.strip().upper()
            if resolved_track not in self.VALID_TRACKS:
                raise InvalidParameterError(
                    code="INVALID_TRACK",
                    message=f"Unsupported ranking track '{track}'.",
                    details={"valid_tracks": sorted(self.VALID_TRACKS)},
                )
        else:
            # Auto-resolve primary track based on route mode
            expl_bus = self._json_repo.get_explanation(cleaned_id, "BUS_PRIORITY")
            if expl_bus is not None:
                resolved_track = "BUS_PRIORITY"
            else:
                resolved_track = "RAIL_PRIORITY"

        expl = self._json_repo.get_explanation(cleaned_id, resolved_track)
        if expl is None:
            raise EntityNotFoundError(
                code="EXPLANATION_NOT_FOUND",
                message=f"Ranking explanation for route '{cleaned_id}' in track '{resolved_track}' was not found.",
            )

        pillars_raw = expl.get("pillars", {})
        original_weights = {str(k): float(v) for k, v in expl.get("original_weights", {}).items()}
        effective_weights = {str(k): float(v) for k, v in expl.get("effective_weights", {}).items()}
        missing_criteria = [str(x) for x in expl.get("missing_criteria", [])]
        valid_coverage = sum(
            original_weights.get(k, 0.0)
            for k in original_weights
            if k not in missing_criteria
        )

        criterion_scores = {
            str(k): to_optional_float(v)
            for k, v in expl.get("criterion_scores", {}).items()
        }
        contributions = {
            str(k): to_optional_float(v)
            for k, v in expl.get("contributions", {}).items()
        }

        total_routes = self._json_repo.get_track_count(resolved_track)

        return RouteExplanationResponse(
            route_id=str(expl["route_id"]),
            route_short_name=str(expl["route_short_name"]),
            route_long_name=str(expl["route_long_name"]),
            is_rail=bool(expl["is_rail"]),
            operational_cluster_label=to_optional_str(expl.get("operational_cluster_label")),
            regional_partition=to_optional_str(expl.get("regional_partition")),
            track=str(expl["track"]),
            profile=str(expl["profile"]),
            overall_score=float(expl["overall_score"]),
            rank=int(expl["rank"]),
            total_routes=total_routes,
            percentile_rank=float(expl["percentile_rank"]),
            topsis_score=float(expl["topsis_score"]),
            topsis_rank=int(expl["topsis_rank"]),
            pillars=RankingPillars(
                demand_pressure=float(pillars_raw.get("demand_pressure", 0.0)),
                service_provision=float(pillars_raw.get("service_provision", 0.0)),
                network_hubs=float(pillars_raw.get("network_hubs", 0.0)),
                corridor_structure=float(pillars_raw.get("corridor_structure", 0.0)),
            ),
            criterion_scores=criterion_scores,
            original_weights=original_weights,
            effective_weights=effective_weights,
            contributions=contributions,
            missing_criteria=missing_criteria,
            is_headway_missing="am_headway_min_norm" in missing_criteria,
            valid_weight_coverage=round(float(valid_coverage), 6),
            top_positive_drivers=[FeatureDriver(**d) for d in expl.get("top_positive_drivers", [])],
            top_negative_drivers=[FeatureDriver(**d) for d in expl.get("top_negative_drivers", [])],
            narrative=str(expl["narrative"]),
        )

    def get_sensitivity(
        self,
        track: Optional[str] = None,
        target_criterion: Optional[str] = None,
    ) -> SensitivityListResponse:
        """Return OAT weight perturbation sensitivity scenarios."""
        df = self._parquet_repo.get_sensitivity_analysis()
        mask = pd.Series(True, index=df.index)

        filters: Dict[str, str] = {}
        if track is not None:
            resolved_track = track.strip().upper()
            if resolved_track not in self.VALID_TRACKS:
                raise InvalidParameterError(
                    code="INVALID_TRACK",
                    message=f"Unsupported ranking track '{track}'.",
                    details={"valid_tracks": sorted(self.VALID_TRACKS)},
                )
            mask &= df["track"] == resolved_track
            filters["track"] = resolved_track

        if target_criterion is not None and target_criterion.strip():
            crit = target_criterion.strip()
            mask &= df["target_criterion"] == crit
            filters["target_criterion"] = crit

        filtered = df.loc[mask].sort_values(
            by=["track", "target_criterion", "delta"],
            ascending=[True, True, True],
            kind="mergesort",
        )

        items = [
            SensitivityScenarioItem(
                scenario_id=str(row["scenario_id"]),
                track=str(row["track"]),
                target_criterion=str(row["target_criterion"]),
                delta=float(row["delta"]),
                spearman_rho=float(row["spearman_rho"]),
                mean_absolute_rank_shift=float(row["mean_absolute_rank_shift"]),
                max_rank_shift=int(row["max_rank_shift"]),
                top_10_overlap=float(row["top_10_overlap"]),
                top_20_overlap=float(row["top_20_overlap"]),
            )
            for _, row in filtered.iterrows()
        ]

        return SensitivityListResponse(
            total_scenarios=len(items),
            data=items,
            filters=filters,
        )
