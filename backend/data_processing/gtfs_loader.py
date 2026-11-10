"""GTFS Loader Module for RouteRanker.

Loads and extracts GTFS zip archives, discovers required and optional files,
and loads raw GTFS tables safely with proper data types.
"""

from __future__ import annotations

import logging
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import pandas as pd

logger = logging.getLogger(__name__)

# Standard GTFS files
REQUIRED_GTFS_FILES: Set[str] = {
    "agency.txt",
    "routes.txt",
    "stops.txt",
    "trips.txt",
    "stop_times.txt",
    "calendar.txt",
}

OPTIONAL_GTFS_FILES: Set[str] = {
    "feed_info.txt",
    "calendar_dates.txt",
    "shapes.txt",
    "frequencies.txt",
    "fare_attributes.txt",
    "fare_rules.txt",
}

# String columns that should never be converted to float/int unintentionally
GTFS_STRING_COLUMNS: Dict[str, List[str]] = {
    "agency": ["agency_id", "agency_name", "agency_phone", "agency_lang"],
    "routes": ["route_id", "agency_id", "route_short_name", "route_long_name", "route_desc"],
    "stops": ["stop_id", "stop_code", "stop_name", "stop_desc", "zone_id", "parent_station"],
    "trips": ["trip_id", "route_id", "service_id", "trip_headsign", "trip_short_name", "block_id", "shape_id"],
    "stop_times": ["trip_id", "stop_id", "arrival_time", "departure_time", "stop_headsign"],
    "calendar": ["service_id"],
    "feed_info": ["feed_publisher_name", "feed_publisher_url", "feed_lang", "feed_version"],
}


@dataclass
class GTFSManifest:
    """Metadata about loaded GTFS files."""
    source_path: Path
    is_archive: bool
    present_files: List[str]
    missing_required_files: List[str]
    missing_optional_files: List[str]
    file_sizes_bytes: Dict[str, int] = field(default_factory=dict)
    estimated_row_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Check if all required GTFS files are present."""
        return len(self.missing_required_files) == 0


class GTFSLoader:
    """Loads and unpacks GTFS feeds."""

    def __init__(self, raw_data_path: Optional[Union[str, Path]] = None) -> None:
        """Initialize GTFS Loader with path to raw zip or directory.

        If None, attempts discovery in default project locations.
        """
        if raw_data_path is not None:
            self.raw_path = Path(raw_data_path)
        else:
            self.raw_path = self._discover_default_gtfs_path()

        logger.info(f"GTFSLoader initialized with path: {self.raw_path}")

    @staticmethod
    def _discover_default_gtfs_path() -> Path:
        """Attempt to locate mtc-gtfs.zip or mtc-gtfs directory in project."""
        candidates = [
            Path("RouteRanker/data/raw/mtc-gtfs.zip"),
            Path("../data/raw/mtc-gtfs.zip"),
            Path("data/raw/mtc-gtfs.zip"),
            Path("../../mtc-gtfs.zip"),
            Path("d:/infosys springboard/milestone 1/proj/RouteRanker/data/raw/mtc-gtfs.zip"),
            Path("d:/infosys springboard/milestone 1/mtc-gtfs.zip"),
            Path("d:/infosys springboard/milestone 1/mtc-gtfs"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        return Path("RouteRanker/data/raw/mtc-gtfs.zip").resolve()

    def inspect_feed(self) -> GTFSManifest:
        """Inspect the GTFS source without fully loading large tables into memory."""
        if not self.raw_path.exists():
            raise FileNotFoundError(f"GTFS source not found at: {self.raw_path}")

        present: List[str] = []
        sizes: Dict[str, int] = {}

        if self.raw_path.is_file() and zipfile.is_zipfile(self.raw_path):
            with zipfile.ZipFile(self.raw_path, "r") as z:
                for info in z.infolist():
                    name = Path(info.filename).name
                    if name.endswith(".txt"):
                        present.append(name)
                        sizes[name] = info.file_size
            is_archive = True
        elif self.raw_path.is_dir():
            for p in self.raw_path.glob("*.txt"):
                present.append(p.name)
                sizes[p.name] = p.stat().st_size
            is_archive = False
        else:
            raise ValueError(f"Path is neither a valid zip nor directory: {self.raw_path}")

        present_set = set(present)
        missing_req = sorted(list(REQUIRED_GTFS_FILES - present_set))
        missing_opt = sorted(list(OPTIONAL_GTFS_FILES - present_set))

        manifest = GTFSManifest(
            source_path=self.raw_path,
            is_archive=is_archive,
            present_files=sorted(present),
            missing_required_files=missing_req,
            missing_optional_files=missing_opt,
            file_sizes_bytes=sizes,
        )
        return manifest

    def extract_to_dir(self, target_dir: Union[str, Path], force: bool = False) -> Path:
        """Extract GTFS zip to target directory if it is an archive."""
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        if not self.raw_path.is_file() or not zipfile.is_zipfile(self.raw_path):
            logger.info("Raw path is already an extracted directory. Returning directory.")
            return self.raw_path

        # Check if already extracted
        all_required = True
        for req in REQUIRED_GTFS_FILES:
            if not (target_path / req).exists():
                all_required = False
                break

        if all_required and not force:
            logger.info(f"Target directory {target_path} already contains GTFS files. Skipping extract.")
            return target_path

        logger.info(f"Extracting GTFS archive {self.raw_path} to {target_path}...")
        with zipfile.ZipFile(self.raw_path, "r") as z:
            for member in z.namelist():
                filename = Path(member).name
                if filename.endswith(".txt"):
                    target_file = target_path / filename
                    with z.open(member) as source, open(target_file, "wb") as target:
                        target.write(source.read())

        logger.info(f"Extracted GTFS files to {target_path}")
        return target_path

    def load_table(
        self,
        table_name: str,
        extracted_dir: Optional[Union[str, Path]] = None,
        usecols: Optional[List[str]] = None,
        chunksize: Optional[int] = None,
    ) -> Any:
        """Load a specific GTFS table into a pandas DataFrame or iterator."""
        if not table_name.endswith(".txt"):
            filename = f"{table_name}.txt"
            base_key = table_name
        else:
            filename = table_name
            base_key = table_name.replace(".txt", "")

        dtype_spec = {col: str for col in GTFS_STRING_COLUMNS.get(base_key, [])}

        if extracted_dir:
            file_path = Path(extracted_dir) / filename
            if not file_path.exists():
                raise FileNotFoundError(f"GTFS table not found: {file_path}")
            return pd.read_csv(
                file_path,
                dtype=dtype_spec,
                usecols=usecols,
                chunksize=chunksize,
                encoding="utf-8-sig",
                low_memory=False,
            )

        if self.raw_path.is_file() and zipfile.is_zipfile(self.raw_path):
            with zipfile.ZipFile(self.raw_path, "r") as z:
                # Find matching file in zip (supporting subfolder inside zip)
                match = None
                for name in z.namelist():
                    if Path(name).name.lower() == filename.lower():
                        match = name
                        break
                if not match:
                    raise FileNotFoundError(f"Table {filename} not in zip archive {self.raw_path}")
                with z.open(match) as f:
                    return pd.read_csv(
                        f,
                        dtype=dtype_spec,
                        usecols=usecols,
                        chunksize=chunksize,
                        encoding="utf-8-sig",
                        low_memory=False,
                    )
        else:
            file_path = self.raw_path / filename
            if not file_path.exists():
                raise FileNotFoundError(f"GTFS table not found: {file_path}")
            return pd.read_csv(
                file_path,
                dtype=dtype_spec,
                usecols=usecols,
                chunksize=chunksize,
                encoding="utf-8-sig",
                low_memory=False,
            )

    def load_all_tables(
        self,
        extracted_dir: Optional[Union[str, Path]] = None,
        exclude_stop_times: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """Load all present GTFS tables.

        Optionally skip stop_times.txt if it is to be processed via DuckDB streaming.
        """
        manifest = self.inspect_feed()
        tables: Dict[str, pd.DataFrame] = {}

        for filename in manifest.present_files:
            key = filename.replace(".txt", "")
            if key == "stop_times" and exclude_stop_times:
                continue
            logger.info(f"Loading GTFS table: {filename}...")
            tables[key] = self.load_table(filename, extracted_dir=extracted_dir)

        return tables

