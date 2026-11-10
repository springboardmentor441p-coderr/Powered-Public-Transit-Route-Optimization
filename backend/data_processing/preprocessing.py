"""GTFS Preprocessing and Analytical Tables Pipeline.

Processes raw GTFS feeds, sanitizes records, normalizes 24h+ timestamps,
computes analytical aggregations (route stops, service summary, overlap, coverage),
and stores output Parquet files in data/processed/ and registers DuckDB tables.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

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

from data_processing.gtfs_loader import GTFSLoader
from data_processing.gtfs_validator import (
    DataQualityReport,
    GTFSValidator,
    parse_gtfs_time_seconds,
)

logger = logging.getLogger(__name__)


class GTFSPreprocessor:
    """Preprocesses GTFS data and creates analytical parquet tables."""

    def __init__(
        self,
        raw_zip_or_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None,
    ) -> None:
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.raw_path = raw_zip_or_dir or (self.project_root / "data" / "raw" / "mtc-gtfs.zip")
        self.processed_dir = processed_dir or (self.project_root / "data" / "processed")
        self.extracted_dir = self.project_root / "data" / "raw" / "extracted"

        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.extracted_dir.mkdir(parents=True, exist_ok=True)

        self.loader = GTFSLoader(self.raw_path)
        self.validator = GTFSValidator()
        self.quality_report: Optional[DataQualityReport] = None

    def run_pipeline(self) -> Dict[str, Any]:
        """Execute the end-to-end preprocessing pipeline."""
        t0 = time.time()
        logger.info("Starting GTFS preprocessing pipeline...")

        # 1. Extract zip if needed
        self.loader.extract_to_dir(self.extracted_dir)

        # 2. Load small & medium tables for validation and sanitization
        raw_tables = {
            "agency": self.loader.load_table("agency.txt", extracted_dir=self.extracted_dir),
            "calendar": self.loader.load_table("calendar.txt", extracted_dir=self.extracted_dir),
            "routes": self.loader.load_table("routes.txt", extracted_dir=self.extracted_dir),
            "stops": self.loader.load_table("stops.txt", extracted_dir=self.extracted_dir),
            "trips": self.loader.load_table("trips.txt", extracted_dir=self.extracted_dir),
        }
        if (self.extracted_dir / "feed_info.txt").exists():
            raw_tables["feed_info"] = self.loader.load_table("feed_info.txt", extracted_dir=self.extracted_dir)

        # 3. Validate and sanitize
        sanitized_tables, self.quality_report = self.validator.validate_and_sanitize_all(raw_tables)

        # 4. Process calendar: add active_days_count
        cal_df = sanitized_tables["calendar"]
        day_cols = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        cal_df["active_days_count"] = cal_df[day_cols].sum(axis=1)

        # 5. Process stop_times (1.36M rows)
        stop_times_df, times_gt24_count = self._process_stop_times()
        self.quality_report.times_exceeding_24h_count = times_gt24_count
        self.quality_report.stop_times_count = len(stop_times_df)

        # Save primary cleaned tables to Parquet
        self._save_df_to_parquet(sanitized_tables["agency"], self.processed_dir / "agency.parquet")
        self._save_df_to_parquet(sanitized_tables["routes"], self.processed_dir / "routes.parquet")
        self._save_df_to_parquet(sanitized_tables["stops"], self.processed_dir / "stops.parquet")
        self._save_df_to_parquet(sanitized_tables["trips"], self.processed_dir / "trips.parquet")
        self._save_df_to_parquet(cal_df, self.processed_dir / "calendar.parquet")
        if "feed_info" in sanitized_tables:
            self._save_df_to_parquet(sanitized_tables["feed_info"], self.processed_dir / "feed_info.parquet")
        self._save_df_to_parquet(stop_times_df, self.processed_dir / "stop_times.parquet")

        # 6. Generate analytical tables
        logger.info("Generating route_stops and route_service_summary...")
        route_stops_df = self._generate_route_stops(sanitized_tables["routes"], sanitized_tables["stops"], sanitized_tables["trips"], stop_times_df)
        self._save_df_to_parquet(route_stops_df, self.processed_dir / "route_stops.parquet")

        logger.info("Generating route_service_summary...")
        summary_df = self._generate_route_service_summary(sanitized_tables["routes"], sanitized_tables["trips"], stop_times_df)
        self._save_df_to_parquet(summary_df, self.processed_dir / "route_service_summary.parquet")

        logger.info("Generating stop_coverage...")
        coverage_df = self._generate_stop_coverage(sanitized_tables["stops"], sanitized_tables["trips"], stop_times_df)
        self._save_df_to_parquet(coverage_df, self.processed_dir / "stop_coverage.parquet")

        logger.info("Generating route_stop_overlap...")
        overlap_df = self._generate_route_stop_overlap(route_stops_df, sanitized_tables["routes"])
        self._save_df_to_parquet(overlap_df, self.processed_dir / "route_stop_overlap.parquet")

        # 7. Persist quality report
        report_path = self.processed_dir / "data_quality_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.quality_report.to_dict(), f, indent=2)

        # 8. Create DuckDB & SQLite database tables
        self._populate_analytical_databases()

        elapsed = round(time.time() - t0, 2)
        logger.info(f"GTFS preprocessing complete in {elapsed} seconds.")
        return {
            "status": "success",
            "elapsed_seconds": elapsed,
            "quality_score": self.quality_report.quality_score,
            "tables_processed": [
                "agency", "routes", "stops", "trips", "calendar", "stop_times",
                "route_stops", "route_service_summary", "stop_coverage", "route_stop_overlap"
            ],
            "report": self.quality_report.to_dict(),
        }

    def _process_stop_times(self) -> Tuple[pd.DataFrame, int]:
        """Process 1.36M stop_times rows: sanitize, parse times, add day_offset & normalized time."""
        logger.info("Processing 1.36M stop_times.txt...")
        stop_times_file = self.extracted_dir / "stop_times.txt"

        if HAS_POLARS:
            # High-performance Polars processing
            df = pl.read_csv(
                stop_times_file,
                schema_overrides={
                    "trip_id": pl.Utf8,
                    "stop_id": pl.Utf8,
                    "arrival_time": pl.Utf8,
                    "departure_time": pl.Utf8,
                    "stop_sequence": pl.Int32,
                },
            )
            # Parse time components
            parts = df["arrival_time"].str.split_exact(":", 2)
            h = parts.struct.field("field_0").cast(pl.Int32)
            m = parts.struct.field("field_1").cast(pl.Int32)
            s = parts.struct.field("field_2").cast(pl.Int32)

            arr_secs = h * 3600 + m * 60 + s
            norm_h = h % 24
            day_offset = (h // 24).cast(pl.Int8)
            exceeds_24h = h >= 24
            times_gt24_count = int(exceeds_24h.sum())

            norm_arr = pl.concat_str([
                norm_h.cast(pl.Utf8).str.zfill(2),
                pl.lit(":"),
                m.cast(pl.Utf8).str.zfill(2),
                pl.lit(":"),
                s.cast(pl.Utf8).str.zfill(2),
            ])

            # Also departure time
            dep_parts = df["departure_time"].str.split_exact(":", 2)
            dep_h = dep_parts.struct.field("field_0").cast(pl.Int32)
            dep_m = dep_parts.struct.field("field_1").cast(pl.Int32)
            dep_s = dep_parts.struct.field("field_2").cast(pl.Int32)
            dep_secs = dep_h * 3600 + dep_m * 60 + dep_s
            norm_dep_h = dep_h % 24
            norm_dep = pl.concat_str([
                norm_dep_h.cast(pl.Utf8).str.zfill(2),
                pl.lit(":"),
                dep_m.cast(pl.Utf8).str.zfill(2),
                pl.lit(":"),
                dep_s.cast(pl.Utf8).str.zfill(2),
            ])

            df = df.with_columns([
                arr_secs.alias("arrival_seconds"),
                dep_secs.alias("departure_seconds"),
                norm_arr.alias("normalized_arrival_time"),
                norm_dep.alias("normalized_departure_time"),
                day_offset.alias("day_offset"),
                exceeds_24h.alias("exceeds_24h"),
            ])
            # Strip whitespace
            df = df.with_columns([
                pl.col("trip_id").str.strip_chars(),
                pl.col("stop_id").str.strip_chars(),
            ])
            try:
                pandas_df = df.to_pandas()
            except Exception:
                pandas_df = pd.DataFrame(df.to_dict())
            return pandas_df, times_gt24_count

        # Fallback to pandas chunked processing
        chunks = []
        times_gt24_count = 0
        for chunk in pd.read_csv(
            stop_times_file,
            dtype={"trip_id": str, "stop_id": str, "arrival_time": str, "departure_time": str},
            chunksize=250000,
            low_memory=False,
        ):
            chunk["trip_id"] = chunk["trip_id"].str.strip()
            chunk["stop_id"] = chunk["stop_id"].str.strip()
            arr_secs = []
            dep_secs = []
            norm_arrs = []
            norm_deps = []
            offsets = []
            gt24_flags = []
            for arr, dep in zip(chunk["arrival_time"], chunk["departure_time"]):
                a_sec, a_norm, a_off, a_gt = parse_gtfs_time_seconds(arr)
                d_sec, d_norm, _, _ = parse_gtfs_time_seconds(dep)
                arr_secs.append(a_sec)
                dep_secs.append(d_sec)
                norm_arrs.append(a_norm)
                norm_deps.append(d_norm)
                offsets.append(a_off)
                gt24_flags.append(a_gt)
                if a_gt:
                    times_gt24_count += 1
            chunk["arrival_seconds"] = arr_secs
            chunk["departure_seconds"] = dep_secs
            chunk["normalized_arrival_time"] = norm_arrs
            chunk["normalized_departure_time"] = norm_deps
            chunk["day_offset"] = offsets
            chunk["exceeds_24h"] = gt24_flags
            chunks.append(chunk)

        result_df = pd.concat(chunks, ignore_index=True)
        return result_df, times_gt24_count

    def _generate_route_stops(
        self,
        routes_df: pd.DataFrame,
        stops_df: pd.DataFrame,
        trips_df: pd.DataFrame,
        stop_times_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Derive distinct route stop sequences by selecting the most frequent pattern per route."""
        # Merge trip to route
        trips_sub = trips_df[["trip_id", "route_id", "direction_id"]].copy()
        merged = stop_times_df[["trip_id", "stop_id", "stop_sequence"]].merge(trips_sub, on="trip_id")

        # Pick one representative trip per (route_id, direction_id) that has maximum stops
        trip_lengths = merged.groupby(["route_id", "direction_id", "trip_id"]).size().reset_index(name="stop_count")
        idx_max = trip_lengths.groupby(["route_id", "direction_id"])["stop_count"].idxmax()
        best_trips = trip_lengths.loc[idx_max]["trip_id"]

        route_stops = merged[merged["trip_id"].isin(best_trips)].drop(columns=["trip_id"]).drop_duplicates()
        route_stops = route_stops.sort_values(by=["route_id", "direction_id", "stop_sequence"])

        # Merge stop details
        stops_sub = stops_df[["stop_id", "stop_name", "stop_lat", "stop_lon"]]
        route_stops = route_stops.merge(stops_sub, on="stop_id", how="left")

        # Merge route short name
        routes_sub = routes_df[["route_id", "route_short_name", "route_long_name"]]
        route_stops = route_stops.merge(routes_sub, on="route_id", how="left")

        return route_stops

    def _generate_route_service_summary(
        self,
        routes_df: pd.DataFrame,
        trips_df: pd.DataFrame,
        stop_times_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate scheduled trip counts, first/last departures, service spans, and average run-times."""
        trips_sub = trips_df[["trip_id", "route_id", "direction_id"]].copy()

        # Find trip start and end times
        trip_times = stop_times_df.groupby("trip_id").agg(
            first_departure_sec=("departure_seconds", "min"),
            last_arrival_sec=("arrival_seconds", "max"),
            stop_count=("stop_id", "count"),
        ).reset_index()

        trip_times["trip_duration_min"] = (trip_times["last_arrival_sec"] - trip_times["first_departure_sec"]) / 60.0
        # Filter negative or unreasonable duration if any
        trip_times["trip_duration_min"] = trip_times["trip_duration_min"].clip(lower=1.0, upper=300.0)

        merged = trips_sub.merge(trip_times, on="trip_id", how="inner")

        # Aggregate per route
        summary = merged.groupby("route_id").agg(
            total_trips=("trip_id", "count"),
            direction_0_trips=("direction_id", lambda x: (x == 0).sum()),
            direction_1_trips=("direction_id", lambda x: (x == 1).sum()),
            earliest_departure_sec=("first_departure_sec", "min"),
            latest_departure_sec=("first_departure_sec", "max"),
            avg_trip_duration_min=("trip_duration_min", "mean"),
            min_trip_duration_min=("trip_duration_min", "min"),
            max_trip_duration_min=("trip_duration_min", "max"),
            avg_stops_per_trip=("stop_count", "mean"),
        ).reset_index()

        # Service span
        summary["service_span_hours"] = (summary["latest_departure_sec"] - summary["earliest_departure_sec"]) / 3600.0
        summary["service_span_hours"] = summary["service_span_hours"].round(2)
        summary["avg_trip_duration_min"] = summary["avg_trip_duration_min"].round(1)

        # Helper to format seconds back to HH:MM:SS
        def sec_to_time_str(secs: float) -> str:
            if pd.isna(secs):
                return "00:00:00"
            s = int(secs)
            h = (s // 3600) % 24
            m = (s % 3600) // 60
            sec = s % 60
            return f"{h:02d}:{m:02d}:{sec:02d}"

        summary["first_departure_time"] = summary["earliest_departure_sec"].apply(sec_to_time_str)
        summary["last_departure_time"] = summary["latest_departure_sec"].apply(sec_to_time_str)

        # Merge with route basic information
        routes_sub = routes_df[["route_id", "route_short_name", "route_long_name", "route_type"]]
        result = routes_sub.merge(summary, on="route_id", how="left").fillna({
            "total_trips": 0,
            "direction_0_trips": 0,
            "direction_1_trips": 0,
            "service_span_hours": 0.0,
            "avg_trip_duration_min": 0.0,
            "min_trip_duration_min": 0.0,
            "max_trip_duration_min": 0.0,
            "avg_stops_per_trip": 0.0,
            "first_departure_time": "N/A",
            "last_departure_time": "N/A",
        })

        result["total_trips"] = result["total_trips"].astype(int)
        result["direction_0_trips"] = result["direction_0_trips"].astype(int)
        result["direction_1_trips"] = result["direction_1_trips"].astype(int)

        return result

    def _generate_stop_coverage(
        self,
        stops_df: pd.DataFrame,
        trips_df: pd.DataFrame,
        stop_times_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate stop service coverage: serving routes, trips per day, transfer hubs."""
        trips_sub = trips_df[["trip_id", "route_id"]]
        merged = stop_times_df[["trip_id", "stop_id"]].merge(trips_sub, on="trip_id")

        stop_stats = merged.groupby("stop_id").agg(
            routes_count=("route_id", "nunique"),
            trips_per_day=("trip_id", "count"),
            routes_served=("route_id", lambda x: ",".join(sorted(list(set(x))[:20]))),
        ).reset_index()

        coverage = stops_df.merge(stop_stats, on="stop_id", how="left").fillna({
            "routes_count": 0,
            "trips_per_day": 0,
            "routes_served": "",
        })

        coverage["routes_count"] = coverage["routes_count"].astype(int)
        coverage["trips_per_day"] = coverage["trips_per_day"].astype(int)
        # Hub flag: stop served by 5 or more routes
        coverage["is_transfer_hub"] = coverage["routes_count"] >= 5

        return coverage

    def _generate_route_stop_overlap(
        self,
        route_stops_df: pd.DataFrame,
        routes_df: pd.DataFrame,
        min_overlap_pct: float = 20.0,
        max_pairs: int = 1000,
    ) -> pd.DataFrame:
        """Compute pairwise Jaccard stop overlap between routes."""
        logger.info("Computing pairwise route stop overlaps...")
        # Get set of stops per route
        route_to_stops = route_stops_df.groupby("route_id")["stop_id"].apply(set).to_dict()
        routes_info = routes_df.set_index("route_id")["route_short_name"].to_dict()

        # Invert index: stop_id -> list of route_ids
        stop_to_routes: Dict[str, List[str]] = {}
        for r_id, stops in route_to_stops.items():
            for s in stops:
                stop_to_routes.setdefault(s, []).append(r_id)

        # Candidate pairs that share at least 3 stops
        pair_counts: Dict[Tuple[str, str], int] = {}
        for s, r_list in stop_to_routes.items():
            n = len(r_list)
            if n > 1 and n < 500:  # avoid combinatorial explosion on mega-terminals
                for i in range(n):
                    r_a = r_list[i]
                    for j in range(i + 1, n):
                        r_b = r_list[j]
                        pair = (r_a, r_b) if r_a < r_b else (r_b, r_a)
                        pair_counts[pair] = pair_counts.get(pair, 0) + 1

        records = []
        for (r_a, r_b), shared_stops in pair_counts.items():
            if shared_stops < 4:
                continue
            stops_a = route_to_stops[r_a]
            stops_b = route_to_stops[r_b]
            len_a = len(stops_a)
            len_b = len(stops_b)
            if len_a == 0 or len_b == 0:
                continue

            union_len = len(stops_a.union(stops_b))
            jaccard_pct = round((shared_stops / union_len) * 100.0, 2)
            if jaccard_pct < min_overlap_pct:
                continue

            records.append({
                "route_id_a": r_a,
                "route_id_b": r_b,
                "route_short_name_a": routes_info.get(r_a, r_a),
                "route_short_name_b": routes_info.get(r_b, r_b),
                "shared_stops": shared_stops,
                "stops_count_a": len_a,
                "stops_count_b": len_b,
                "overlap_ratio_a": round(shared_stops / len_a, 3),
                "overlap_ratio_b": round(shared_stops / len_b, 3),
                "jaccard_overlap_pct": jaccard_pct,
            })

        overlap_df = pd.DataFrame(records)
        if not overlap_df.empty:
            overlap_df = overlap_df.sort_values(by="jaccard_overlap_pct", ascending=False).head(max_pairs)
        else:
            overlap_df = pd.DataFrame(columns=[
                "route_id_a", "route_id_b", "route_short_name_a", "route_short_name_b",
                "shared_stops", "stops_count_a", "stops_count_b", "overlap_ratio_a",
                "overlap_ratio_b", "jaccard_overlap_pct",
            ])

        return overlap_df

    def _save_df_to_parquet(self, df: pd.DataFrame, target_path: Path) -> None:
        """Save DataFrame to Parquet using Polars, pyarrow, or fastparquet."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if HAS_POLARS:
            try:
                pl.from_pandas(df).write_parquet(target_path)
            except Exception:
                pl.from_dict(df.to_dict(orient="list")).write_parquet(target_path)
        else:
            df.to_parquet(target_path, index=False)
        logger.info(f"Saved Parquet: {target_path} ({target_path.stat().st_size:,} bytes)")

    def _populate_analytical_databases(self) -> None:
        """Create SQLite analytical mirror and DuckDB database."""
        # 1. SQLite database
        sqlite_path = self.processed_dir / "routeranker.db"
        logger.info(f"Populating SQLite analytical database: {sqlite_path}")
        with sqlite3.connect(sqlite_path) as conn:
            for p_file in self.processed_dir.glob("*.parquet"):
                table_name = p_file.stem
                if table_name in ["stop_times"]:
                    # Store subset or summary in sqlite to keep file lightweight
                    continue
                if HAS_POLARS:
                    try:
                        df = pl.read_parquet(p_file).to_pandas()
                    except Exception:
                        df = pd.DataFrame(pl.read_parquet(p_file).to_dict())
                else:
                    df = pd.read_parquet(p_file)
                df.to_sql(table_name, conn, if_exists="replace", index=False)
                # Create indexes
                if table_name == "routes":
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_routes_id ON routes(route_id);")
                elif table_name == "stops":
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_stops_id ON stops(stop_id);")


        conn.close()

        # 2. DuckDB database
        if HAS_DUCKDB:
            duckdb_path = self.processed_dir / "routeranker.duckdb"
            logger.info(f"Populating DuckDB database: {duckdb_path}")
            conn = duckdb.connect(str(duckdb_path))
            for p_file in self.processed_dir.glob("*.parquet"):
                table_name = p_file.stem
                p_file_str = str(p_file).replace("\\", "/")
                conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{p_file_str}');")
            conn.close()
            logger.info("DuckDB database views registered.")
