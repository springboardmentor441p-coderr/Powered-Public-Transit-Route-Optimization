#!/usr/bin/env python3
"""
AI_RouteRanker - CLI Script for GTFS Relational Ingestion
Executes sequential ingestion of 8 historical GTFS archives into DuckDB & Parquet.
Complies with Milestone 3.1 specifications.
"""

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics.preprocessing.gtfs_pipeline import GTFSIngestionPipeline


def main():
    parser = argparse.ArgumentParser(description="Ingest 8 historical GTFS snapshots into DuckDB and Parquet.")
    parser.add_argument(
        "--gtfs-raw-dir",
        default=os.path.join("data", "raw", "gtfs"),
        help="Root directory of raw GTFS archives",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join("data", "processed", "gtfs"),
        help="Output directory for processed GTFS Parquet tables",
    )
    parser.add_argument(
        "--db-path",
        default=os.path.join("data", "processed", "ai_routeranker.duckdb"),
        help="Path to persistent DuckDB database",
    )
    parser.add_argument(
        "--memory-limit",
        default="4GB",
        help="DuckDB memory ceiling (default: 4GB for 8GB RAM laptops)",
    )
    parser.add_argument(
        "--project-root",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        help="Root path of AI_RouteRanker project",
    )

    args = parser.parse_args()
    os.chdir(args.project_root)

    print("=" * 80)
    print("AI_RouteRanker - Executing Sequential GTFS Relational Ingestion")
    print("=" * 80)
    print(f"  GTFS Raw Dir:   {args.gtfs_raw_dir}")
    print(f"  Processed Dir:  {args.output_dir}")
    print(f"  DuckDB Target:  {args.db_path}")
    print(f"  Memory Ceiling: {args.memory_limit}")

    t_total = time.time()
    pipeline = GTFSIngestionPipeline(
        gtfs_raw_dir=args.gtfs_raw_dir,
        output_dir=args.output_dir,
        db_path=args.db_path,
        memory_limit=args.memory_limit,
    )

    results = pipeline.ingest_all_snapshots()
    pipeline.close()

    total_elapsed = time.time() - t_total
    total_trips = sum(r["trips_count"] for r in results)
    total_stop_times = sum(r["stop_times_count"] for r in results)

    print("\n" + "=" * 80)
    print(f"GTFS Ingestion Complete across 8 Snapshots in {total_elapsed:.2f}s")
    print(f"  Total Trips Ingested:      {total_trips:,}")
    print(f"  Total Stop Times Ingested: {total_stop_times:,}")
    print(f"  All PK Integrity Passed:   {all(r['pk_passed'] for r in results)}")
    print(f"  All FK Integrity Passed:   {all(r['fk_passed'] for r in results)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
