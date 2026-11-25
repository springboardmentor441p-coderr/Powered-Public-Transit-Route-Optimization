"""FastAPI dependency providers for Stage 1 repositories and services."""

from functools import lru_cache

from fastapi import Depends

from app.repositories.corridor_repository import CorridorRepository
from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.forecast_repository import ForecastRepository
from app.repositories.json_repository import JSONRepository
from app.repositories.parquet_repository import ParquetRepository
from app.repositories.spatial_repository import SpatialRepository
from app.services.corridor_service import CorridorService
from app.services.forecast_service import ForecastService
from app.services.ranking_service import RankingService
from app.services.ridership_service import RidershipService
from app.services.route_service import RouteService
from app.services.spatial_service import SpatialService


@lru_cache()
def get_corridor_repository() -> CorridorRepository:
    """Provide singleton read-only CorridorRepository instance."""
    return CorridorRepository()


@lru_cache()
def get_forecast_repository() -> ForecastRepository:
    """Provide singleton read-only ForecastRepository instance."""
    return ForecastRepository()


@lru_cache()
def get_duckdb_repository() -> DuckDBRepository:
    """Provide singleton read-only DuckDBRepository instance."""
    return DuckDBRepository()


@lru_cache()
def get_spatial_repository() -> SpatialRepository:
    """Provide singleton read-only SpatialRepository instance."""
    return SpatialRepository()


@lru_cache()
def get_parquet_repository() -> ParquetRepository:
    """Provide singleton read-only ParquetRepository instance."""
    return ParquetRepository()


@lru_cache()
def get_json_repository() -> JSONRepository:
    """Provide singleton read-only JSONRepository instance."""
    return JSONRepository()


def get_route_service(
    parquet_repo: ParquetRepository = Depends(get_parquet_repository),
) -> RouteService:
    """Provide RouteService bound to the ParquetRepository."""
    return RouteService(parquet_repo=parquet_repo)


def get_ranking_service(
    parquet_repo: ParquetRepository = Depends(get_parquet_repository),
    json_repo: JSONRepository = Depends(get_json_repository),
) -> RankingService:
    """Provide RankingService bound to ParquetRepository and JSONRepository."""
    return RankingService(parquet_repo=parquet_repo, json_repo=json_repo)


def get_ridership_service(
    duckdb_repo: DuckDBRepository = Depends(get_duckdb_repository),
    parquet_repo: ParquetRepository = Depends(get_parquet_repository),
) -> RidershipService:
    """Provide RidershipService bound to DuckDBRepository and ParquetRepository."""
    return RidershipService(duckdb_repo=duckdb_repo, parquet_repo=parquet_repo)


def get_spatial_service(
    spatial_repo: SpatialRepository = Depends(get_spatial_repository),
) -> SpatialService:
    """Provide SpatialService bound to SpatialRepository."""
    return SpatialService(spatial_repo=spatial_repo)


def get_corridor_service(
    corridor_repo: CorridorRepository = Depends(get_corridor_repository),
    parquet_repo: ParquetRepository = Depends(get_parquet_repository),
) -> CorridorService:
    """Provide CorridorService bound to CorridorRepository and ParquetRepository."""
    return CorridorService(corridor_repo=corridor_repo, parquet_repo=parquet_repo)


def get_forecast_service(
    forecast_repo: ForecastRepository = Depends(get_forecast_repository),
) -> ForecastService:
    """Provide ForecastService bound to ForecastRepository."""
    return ForecastService(forecast_repo=forecast_repo)
