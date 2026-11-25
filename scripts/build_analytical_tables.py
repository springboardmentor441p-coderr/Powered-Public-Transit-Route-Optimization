#!/usr/bin/env python3
"""
AI_RouteRanker - CLI Script to Build Integrated Analytical Tables
Generates all Milestone 3.1 integrated tables:
1. snapshot_metadata.parquet
2. route_mapping.parquet
3. gtfs_route_dim.parquet
4. daily_ridership.parquet
5. historical_schedule_match.parquet

Persists tables into DuckDB database (data/processed/ai_routeranker.duckdb)
and exports compressed Parquet files to data/processed/integrated/.
"""

import argparse
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics.preprocessing.integrated_pipeline import IntegratedAnalyticalPipeline


def main():
    parser = argparse.ArgumentParser(description="Build integrated analytical tables and export to Parquet.")
    parser.add_argument(
        "--db-path",
        default=os.path.join("data", "processed", "ai_routeranker.duckdb"),
        help="Path to persistent DuckDB database",
    )
    parser.add_argument(
        "--integrated-dir",
        default=os.path.join("data", "processed", "integrated"),
        help="Directory to store integrated Parquet files",
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

    t0 = time.time()
    pipeline = IntegratedAnalyticalPipeline(
        db_path=args.db_path,
        integrated_dir=args.integrated_dir,
        memory_limit=args.memory_limit,
    )

    pipeline.run_all()
    pipeline.close()

    print(f"\nCompleted in {time.time() - t0:.2f}s.")


if __name__ == "__main__":
    main()
