"""Cached readers for Phase 1-4 artifacts (never reads raw stop_times per call)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import polars as pl


class DatasetUnavailable(FileNotFoundError):
    """Raised when an endpoint's required processed output is absent."""


class DataRepository:
    """Read-only access to phase outputs, cached for the life of the process."""

    def __init__(self, processed_dir: Path):
        self.processed_dir = processed_dir

    def _path(self, phase: str, filename: str) -> Path:
        return self.processed_dir / phase / filename

    @lru_cache(maxsize=64)
    def frame(self, phase: str, filename: str) -> pl.DataFrame:
        path = self._path(phase, filename)
        if not path.is_file():
            raise DatasetUnavailable(f"Required dataset is unavailable: {path}")
        if path.suffix.lower() == ".parquet":
            return pl.read_parquet(path)
        if path.suffix.lower() == ".csv":
            identity_columns = {
                "route_id", "route_id_a", "route_id_b", "stop_id", "trip_id", "service_id", "agency_id",
            }
            return pl.read_csv(
                path, infer_schema_length=1000, try_parse_dates=False,
                schema_overrides={column: pl.String for column in identity_columns},
            )
        raise DatasetUnavailable(f"Unsupported processed dataset format: {path}")

    @lru_cache(maxsize=16)
    def document(self, phase: str, filename: str) -> dict[str, Any]:
        path = self._path(phase, filename)
        if not path.is_file():
            raise DatasetUnavailable(f"Required report is unavailable: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DatasetUnavailable(f"Could not read processed report: {path}") from exc

    def has(self, phase: str, filename: str) -> bool:
        return self._path(phase, filename).is_file()

    def path(self, phase: str, filename: str) -> Path:
        return self._path(phase, filename)
