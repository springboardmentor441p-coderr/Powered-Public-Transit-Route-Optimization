"""Read-only data access repositories for analytical artifacts."""

from app.repositories.corridor_repository import CorridorRepository
from app.repositories.duckdb_repository import DuckDBRepository
from app.repositories.forecast_repository import ForecastRepository
from app.repositories.json_repository import JSONRepository
from app.repositories.parquet_repository import ParquetRepository
from app.repositories.spatial_repository import SpatialRepository

__all__ = [
    "CorridorRepository",
    "DuckDBRepository",
    "ForecastRepository",
    "ParquetRepository",
    "JSONRepository",
    "SpatialRepository",
]
