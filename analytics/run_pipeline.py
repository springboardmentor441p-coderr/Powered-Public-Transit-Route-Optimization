"""
analytics/run_pipeline.py
RouteRanker Data Pipeline Orchestrator

Executes all pipeline stages sequentially:
Step 1: Source Registration & Integrity Check
Step 2: Clean Daily Boardings
Step 3: GTFS Schedule Parsing & Service Profile
Step 4: Route Structure & Corridor Overlap
Step 5: Leakage-Safe Feature Engineering
Step 6: Machine Learning Training & Evaluation
Step 7: Route Productivity, Clustering & Priorities
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from analytics import (
    source_register,
    clean_boardings,
    parse_gtfs_schedule,
    route_structure_and_overlap,
    feature_engineering,
    train_evaluate_models,
    route_productivity_ranking
)

def run_full_pipeline():
    start_total = time.time()
    print("=" * 70)
    print("ROUTERANKER: EXECUTING COMPLETE END-TO-END ANALYTICS PIPELINE")
    print("=" * 70)

    stages = [
        ("Step 1: Source Registration", source_register.register_sources),
        ("Step 2: Clean Boardings", clean_boardings.clean_boardings),
        ("Step 3: GTFS Schedule Parsing", parse_gtfs_schedule.parse_gtfs_schedule),
        ("Step 4: Route Structure & Overlap", route_structure_and_overlap.compute_route_overlap),
        ("Step 5: Feature Engineering", feature_engineering.engineer_features),
        ("Step 6: Model Training & Evaluation", train_evaluate_models.train_and_evaluate),
        ("Step 7: Route Productivity & Ranking", route_productivity_ranking.compute_productivity_and_rankings)
    ]

    for name, func in stages:
        t0 = time.time()
        print(f"\n>>> Starting {name}...")
        try:
            func()
            elapsed = time.time() - t0
            print(f">>> {name} completed successfully in {elapsed:.2f}s.")
        except Exception as e:
            print(f"\n[FATAL ERROR] {name} failed: {e}")
            raise e

    total_elapsed = time.time() - start_total
    print("\n" + "=" * 70)
    print(f"PIPELINE RUN COMPLETE! Total time: {total_elapsed:.2f} seconds.")
    print("=" * 70)

if __name__ == "__main__":
    run_full_pipeline()
