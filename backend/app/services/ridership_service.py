"""Domain service for historical route-level CTA ridership time series."""

import re
from datetime import date, datetime
from typing import Optional

from app.core.config import settings
from app.core.exceptions import EntityNotFoundError, InvalidParameterError
from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.parquet_repository import ParquetRepository
from app.schemas.ridership import (
    DateRangeMeta,
    RidershipMethodologyMeta,
    RidershipObservation,
    RidershipTimeseriesResponse,
)


class RidershipService:
    """Service providing bounded, read-only historical ridership time series."""

    VALID_GRANULARITIES = {"monthly", "daily"}
    VALID_DAYTYPES = {"W", "A", "U"}

    def __init__(
        self,
        duckdb_repo: DuckDBRepository,
        parquet_repo: ParquetRepository,
    ) -> None:
        self._duckdb_repo = duckdb_repo
        self._parquet_repo = parquet_repo
        self._route_id_regex = re.compile(settings.ROUTE_ID_PATTERN)
        self._default_start = date.fromisoformat(settings.RIDERSHIP_DEFAULT_START_DATE)
        self._default_end = date.fromisoformat(settings.RIDERSHIP_DEFAULT_END_DATE)

    def _validate_route_id(self, route_id: str) -> str:
        cleaned = route_id.strip()
        if not self._route_id_regex.match(cleaned):
            raise InvalidParameterError(
                code="INVALID_ROUTE_ID",
                message="Invalid route identifier format.",
            )
        return cleaned

    def get_route_timeseries(
        self,
        route_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        granularity: str = "monthly",
        daytype: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> RidershipTimeseriesResponse:
        """Retrieve bounded historical ridership time series for a canonical CTA route."""
        cleaned_id = self._validate_route_id(route_id)

        gran = granularity.strip().lower()
        if gran not in self.VALID_GRANULARITIES:
            raise InvalidParameterError(
                code="INVALID_GRANULARITY",
                message="Granularity must be 'monthly' or 'daily'.",
            )

        resolved_daytype: Optional[str] = None
        if daytype is not None:
            resolved_daytype = daytype.strip().upper()
            if resolved_daytype not in self.VALID_DAYTYPES:
                raise InvalidParameterError(
                    code="INVALID_DAYTYPE",
                    message="Daytype must be 'W' (Weekday), 'A' (Saturday), or 'U' (Sunday/Holiday).",
                )

        eff_start = start_date or self._default_start
        eff_end = end_date or self._default_end

        if eff_start > eff_end:
            raise InvalidParameterError(
                code="INVALID_DATE_RANGE",
                message="start_date cannot be later than end_date.",
            )

        if gran == "daily" and (eff_end - eff_start).days > settings.RIDERSHIP_MAX_DAILY_SPAN_DAYS:
            raise InvalidParameterError(
                code="DATE_RANGE_TOO_LARGE",
                message=(
                    f"Daily granularity queries are bounded to at most "
                    f"{settings.RIDERSHIP_MAX_DAILY_SPAN_DAYS} days."
                ),
            )

        # Verify route exists in canonical 133-route roster
        feature_cols = ["route_id", "route_short_name", "route_long_name", "route_type", "is_rail"]
        df_feat = self._parquet_repo.get_feature_master(columns=feature_cols)
        matches = df_feat[df_feat["route_id"] == cleaned_id]
        if matches.empty:
            raise EntityNotFoundError(
                code="ROUTE_NOT_FOUND",
                message=f"Route '{cleaned_id}' was not found in the canonical CTA network.",
            )

        route_row = matches.iloc[0]
        is_rail = bool(route_row["is_rail"])
        methodology = RidershipMethodologyMeta(granularity=gran)  # type: ignore[arg-type]
        req_range = DateRangeMeta(start_date=eff_start, end_date=eff_end)

        # Rail ridership is not stored by line ID in analytical.daily_ridership
        if is_rail:
            return RidershipTimeseriesResponse(
                route_id=cleaned_id,
                route_short_name=str(route_row["route_short_name"]),
                route_long_name=str(route_row["route_long_name"]),
                route_type=int(route_row["route_type"]),
                is_rail=True,
                ridership_available=False,
                unavailable_reason=(
                    "Historical rail ridership is recorded at station turnstile level "
                    "rather than line ID in analytical.daily_ridership."
                ),
                requested_date_range=req_range,
                actual_date_range=None,
                observation_count=0,
                total_observations=0,
                offset=offset,
                limit=limit,
                has_more=False,
                methodology=methodology,
                data=[],
            )

        if gran == "monthly":
            rows = self._duckdb_repo.get_monthly_ridership(
                route_id=cleaned_id,
                start_date=eff_start,
                end_date=eff_end,
                daytype=resolved_daytype,
            )
        else:
            rows = self._duckdb_repo.get_daily_ridership(
                route_id=cleaned_id,
                start_date=eff_start,
                end_date=eff_end,
                daytype=resolved_daytype,
            )

        total_obs = len(rows)
        sliced = rows[offset : offset + limit] if limit is not None else rows[offset:]
        observations = [RidershipObservation(**r) for r in sliced]

        actual_range: Optional[DateRangeMeta] = None
        if observations:
            first_p = observations[0].period
            last_p = observations[-1].period
            if gran == "monthly":
                actual_start = datetime.strptime(first_p + "-01", "%Y-%m-%d").date()
                actual_end = datetime.strptime(last_p + "-01", "%Y-%m-%d").date()
            else:
                actual_start = date.fromisoformat(first_p)
                actual_end = date.fromisoformat(last_p)
            actual_range = DateRangeMeta(start_date=actual_start, end_date=actual_end)

        return RidershipTimeseriesResponse(
            route_id=cleaned_id,
            route_short_name=str(route_row["route_short_name"]),
            route_long_name=str(route_row["route_long_name"]),
            route_type=int(route_row["route_type"]),
            is_rail=False,
            ridership_available=True,
            unavailable_reason=None,
            requested_date_range=req_range,
            actual_date_range=actual_range,
            observation_count=len(observations),
            total_observations=total_obs,
            offset=offset,
            limit=limit,
            has_more=(offset + len(observations)) < total_obs,
            methodology=methodology,
            data=observations,
        )
