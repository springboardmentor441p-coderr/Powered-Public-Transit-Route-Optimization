#!/usr/bin/env python3
"""
AI_RouteRanker - CLI Script for Ridership Preprocessing
Executes ridership cleaning, duplicate detection, and Parquet/CSV generation.
Complies with Milestone 3.1 specifications.
"""

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics.preprocessing.ridership_pipeline import preprocess_ridership


def main():
    parser = argparse.ArgumentParser(description="Preprocess raw CTA ridership data into clean analytical formats.")
    parser.add_argument(
        "--raw-path",
        default=os.path.join("data", "raw", "ridership", "cta_ridership.csv"),
        help="Path to raw CTA ridership CSV",
    )
    parser.add_argument(
        "--out-dir",
        default=os.path.join("data", "processed", "ridership"),
        help="Output directory for processed ridership tables",
    )
    parser.add_argument(
        "--db-path",
        default=os.path.join("data", "processed", "ai_routeranker.duckdb"),
        help="Path to persistent DuckDB database",
    )
    parser.add_argument(
        "--project-root",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        help="Root path of AI_RouteRanker project",
    )

    args = parser.parse_args()
    os.chdir(args.project_root)

    print("=" * 80)
    print("AI_RouteRanker - Executing Ridership Preprocessing Pipeline")
    print("=" * 80)
    print(f"  Raw Source: {args.raw_path}")
    print(f"  Output Dir: {args.out_dir}")
    print(f"  DuckDB DB:  {args.db_path}")

    start_time = time.time()
    clean_parquet = os.path.join(args.out_dir, "cta_ridership_clean.parquet")
    clean_csv = os.path.join(args.out_dir, "cta_ridership_clean.csv")
    quarantine_csv = os.path.join(args.out_dir, "cta_ridership_quarantine.csv")

    metrics = preprocess_ridership(
        raw_csv_path=args.raw_path,
        clean_parquet_path=clean_parquet,
        clean_csv_path=clean_csv,
        quarantine_csv_path=quarantine_csv,
        db_path=args.db_path,
    )
    elapsed = time.time() - start_time

    print(f"\n[Ridership Preprocessing Completed in {elapsed:.2f}s]")
    print(f"  Total Raw Records:        {metrics['total_raw_records']:,}")
    print(f"  Clean Records Produced:   {metrics['clean_records']:,}")
    print(f"  Quarantined Records:      {metrics['quarantined_records']:,}")
    print(f"  Duplicate Keys Detected:  {metrics['duplicate_keys']:,}")
    print(f"  Duplicate Rows Removed:   {metrics['duplicate_rows']:,}")
    print(f"  Distinct Route Identifiers: {metrics['distinct_routes']}")
    print(f"  Observation Date Range:   {metrics['min_date']} to {metrics['max_date']}")
    print(f"  Genuine Zero-Rides Kept:  {metrics['zero_rides_records']:,}")
    print(f"  Clean Parquet Size:       {os.path.getsize(clean_parquet) / (1024*1024):.2f} MB")
    print(f"  Clean CSV Size:           {os.path.getsize(clean_csv) / (1024*1024):.2f} MB")
    print(f"  Quarantine CSV Size:      {os.path.getsize(quarantine_csv):,} bytes")
    print("=" * 80)


if __name__ == "__main__":
    main()
