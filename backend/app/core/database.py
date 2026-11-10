"""Database and Parquet Analytical Engine for RouteRanker.

Manages DuckDB analytical queries on 1.36M+ row Parquet tables.
Provides transparent fallbacks to SQLite and Polars when DuckDB is unavailable.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False


class DatabaseManager:
    """Analytical database manager for DuckDB and SQLite."""

    _instance: Optional[DatabaseManager] = None
    _duckdb_conn: Optional[Any] = None
    _table_cache: Dict[str, pd.DataFrame] = {}

    def __new__(cls) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self) -> None:
        self.duckdb_path = settings.DUCKDB_PATH
        self.sqlite_path = settings.SQLITE_PATH
        self.processed_dir = settings.DATA_PROCESSED_DIR
        self._table_cache = {}

    def is_duckdb_available(self) -> bool:
        return HAS_DUCKDB

    def is_data_ready(self) -> bool:
        """Check if all required processed parquet files exist."""
        required = [
            "routes.parquet",
            "stops.parquet",
            "trips.parquet",
            "stop_times.parquet",
            "route_features.parquet",
            "route_stops.parquet",
        ]
        return all((self.processed_dir / f).exists() for f in required)

    def get_duckdb_conn(self) -> Optional[Any]:
        """Obtain or initialize DuckDB persistent connection."""
        if not HAS_DUCKDB:
            return None

        if self._duckdb_conn is None:
            try:
                self.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
                self._duckdb_conn = duckdb.connect(str(self.duckdb_path))
                self._register_duckdb_views()
            except Exception as e:
                logger.error(f"Failed to open DuckDB connection: {e}")
                return None

        return self._duckdb_conn

    def _register_duckdb_views(self) -> None:
        """Register Parquet files as views in DuckDB."""
        if self._duckdb_conn is None:
            return
        for p_file in self.processed_dir.glob("*.parquet"):
            table_name = p_file.stem
            posix_path = str(p_file).replace("\\", "/")
            try:
                self._duckdb_conn.execute(
                    f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{posix_path}');"
                )
            except Exception as e:
                logger.warning(f"Could not register DuckDB view for {table_name}: {e}")

    def get_table(self, table_name: str, use_cache: bool = True) -> pd.DataFrame:
        """Read a processed table into pandas DataFrame with caching."""
        if use_cache and table_name in self._table_cache:
            return self._table_cache[table_name]

        p_file = self.processed_dir / f"{table_name}.parquet"
        if not p_file.exists():
            raise FileNotFoundError(f"Processed table {table_name}.parquet not found in {self.processed_dir}")

        if HAS_POLARS:
            try:
                df = pl.read_parquet(p_file).to_pandas()
            except Exception:
                df = pd.DataFrame(pl.read_parquet(p_file).to_dict())
        else:
            df = pd.read_parquet(p_file)

        if use_cache:
            self._table_cache[table_name] = df
        return df

    def query_df(self, query: str, params: Optional[List[Any]] = None) -> pd.DataFrame:
        """Execute analytical SQL query using DuckDB, with SQLite/Pandas fallback."""
        if HAS_DUCKDB:
            conn = self.get_duckdb_conn()
            if conn is not None:
                try:
                    if params:
                        return conn.execute(query, params).df()
                    return conn.execute(query).df()
                except Exception as e:
                    logger.warning(f"DuckDB query failed, attempting SQLite fallback: {e}")

        # SQLite fallback
        if self.sqlite_path.exists():
            with sqlite3.connect(self.sqlite_path) as s_conn:
                if params:
                    return pd.read_sql_query(query, s_conn, params=params)
                return pd.read_sql_query(query, s_conn)

        raise RuntimeError("No database engine available to execute query.")

    def get_registered_tables(self) -> List[str]:
        """List all available processed table names."""
        return [p.stem for p in self.processed_dir.glob("*.parquet")]

    def clear_cache(self) -> None:
        """Clear in-memory table cache."""
        self._table_cache.clear()


db = DatabaseManager()
