"""
AI_RouteRanker - Modeling Data Loader Module
Reads model-ready feature datasets in read-only mode with memory-efficient
date-sliced queries. Preserves original Parquet immutability.
"""

import os
import hashlib
import logging
from typing import Optional, List, Dict, Any
import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


class DataLoader:
    """Loads and inspects model-ready features without mutating on-disk data."""

    DEFAULT_FEATURE_STORE = os.path.join("data", "processed", "features", "model_ready_features.parquet")
    EXPECTED_TOTAL_ROWS = 1124170
    EXPECTED_COLUMN_COUNT = 43

    def __init__(self, parquet_path: Optional[str] = None):
        self.parquet_path = parquet_path or self.DEFAULT_FEATURE_STORE
        if not os.path.exists(self.parquet_path):
            raise FileNotFoundError(f"Feature store not found at {self.parquet_path}")
        self._norm_path = self.parquet_path.replace(os.sep, "/")

    def get_file_metadata(self) -> Dict[str, Any]:
        """Returns file size, modification timestamp, and SHA-256 for immutability verification."""
        stat = os.stat(self.parquet_path)
        sha256 = hashlib.sha256()
        with open(self.parquet_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return {
            "path": self.parquet_path,
            "size_bytes": stat.st_size,
            "modified_time": stat.st_mtime,
            "sha256": sha256.hexdigest(),
        }

    def inspect_schema(self) -> List[Dict[str, str]]:
        """Inspects column names and types via DuckDB without full table load."""
        con = duckdb.connect()
        try:
            df_desc = con.execute(f"DESCRIBE SELECT * FROM '{self._norm_path}'").df()
            return df_desc.to_dict(orient="records")
        finally:
            con.close()

    def get_row_and_column_counts(self) -> tuple[int, int]:
        """Returns (row_count, column_count) quickly via DuckDB metadata."""
        con = duckdb.connect()
        try:
            row_count = con.execute(f"SELECT COUNT(*) FROM '{self._norm_path}'").fetchone()[0]
            col_count = len(con.execute(f"DESCRIBE SELECT * FROM '{self._norm_path}'").fetchall())
            return row_count, col_count
        finally:
            con.close()

    def load_slice(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Loads a memory-efficient slice of the feature store.
        Applies predicate pushdown and column pruning via DuckDB.
        """
        cols_clause = ", ".join(f'"{c}"' for c in columns) if columns else "*"
        where_clauses = []
        if start_date:
            where_clauses.append(f"date >= '{start_date}'")
        if end_date:
            where_clauses.append(f"date <= '{end_date}'")

        where_stmt = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"SELECT {cols_clause} FROM '{self._norm_path}' {where_stmt} ORDER BY route ASC, date ASC"

        con = duckdb.connect()
        try:
            df = con.execute(query).df()
            logger.info("Loaded %d rows from %s (filters: %s)", len(df), self.parquet_path, where_stmt)
            return df
        finally:
            con.close()

    def load_tier1_dataset(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Loads complete Post-Pandemic Macro regime (2022-01-01 to 2026-08-31)."""
        return self.load_slice(start_date="2022-01-01", end_date="2026-08-31", columns=columns)

    def load_tier2_dataset(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Loads complete Contemporary GTFS regime (2025-11-23 to 2026-07-31)."""
        return self.load_slice(start_date="2025-11-23", end_date="2026-07-31", columns=columns)
