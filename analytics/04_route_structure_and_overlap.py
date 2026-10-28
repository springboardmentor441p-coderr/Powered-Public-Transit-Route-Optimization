"""
analytics/04_route_structure_and_overlap.py
RouteRanker Data Pipeline - Step 4: Route Structure & Corridor Overlap

Computes stop-level exclusivity and pairwise route overlap:
1. Extracts unique stop sets per route from stop_times.txt and stops.txt.
2. Computes stop exclusivity (% of stops served exclusively by that route).
3. Computes pairwise Jaccard similarity (|A ∩ B| / |A ∪ B|) and containment ratio.
4. Highlights high-overlap corridors for operational route optimization.
5. Exports data/processed/route_structure.parquet and data/processed/route_overlap.parquet.
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from itertools import combinations

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"

def compute_route_overlap():
    print("=" * 60)
    print("ROUTERANKER PIPELINE: STEP 4 - ROUTE STRUCTURE & OVERLAP")
    print("=" * 60)

    gtfs_dir = DATA_DIR / "google_transit"
    if not gtfs_dir.exists():
        gtfs_dir = DATA_DIR / "mdb-389-202609160157"

    routes_file = str(gtfs_dir / "routes.txt").replace("\\", "/")
    trips_file = str(gtfs_dir / "trips.txt").replace("\\", "/")
    stop_times_file = str(gtfs_dir / "stop_times.txt").replace("\\", "/")

    con = duckdb.connect(database=":memory:")
    con.execute("SET max_memory = '512MB';")
    con.execute("SET threads = 4;")

    # Extract route-to-stop mapping for bus routes
    con.execute(f"""
        CREATE TABLE route_stops AS
        SELECT DISTINCT
            CAST(t.route_id AS VARCHAR) AS route_id,
            CAST(st.stop_id AS VARCHAR) AS stop_id
        FROM read_csv_auto('{stop_times_file}') st
        JOIN read_csv_auto('{trips_file}') t ON CAST(st.trip_id AS VARCHAR) = CAST(t.trip_id AS VARCHAR)
        JOIN read_csv_auto('{routes_file}') r ON CAST(t.route_id AS VARCHAR) = CAST(r.route_id AS VARCHAR)
        WHERE CAST(r.route_type AS INTEGER) = 3;
    """)

    df_route_stops = con.execute("SELECT route_id, stop_id FROM route_stops").df()
    con.close()

    # Build route -> set of stops
    route_stop_map = df_route_stops.groupby("route_id")["stop_id"].apply(set).to_dict()
    routes = sorted(list(route_stop_map.keys()))
    print(f"[EXTRACTED] Stops extracted for {len(routes)} bus routes.")

    # 1. Compute stop exclusivity per route
    # Frequency of each stop across all routes
    stop_counts = df_route_stops["stop_id"].value_counts().to_dict()

    structure_records = []
    for r in routes:
        stops = route_stop_map[r]
        total_stops = len(stops)
        if total_stops == 0:
            continue
        exclusive_stops = sum(1 for s in stops if stop_counts.get(s, 0) == 1)
        shared_stops = total_stops - exclusive_stops
        exclusivity_pct = round((exclusive_stops / total_stops) * 100.0, 2)

        structure_records.append({
            "route_id": r,
            "total_stops": total_stops,
            "exclusive_stops": exclusive_stops,
            "shared_stops": shared_stops,
            "exclusivity_pct": exclusivity_pct
        })

    df_structure = pd.DataFrame(structure_records).sort_values("exclusivity_pct", ascending=False)

    # 2. Compute pairwise Jaccard overlap and containment
    overlap_records = []
    for r1, r2 in combinations(routes, 2):
        s1 = route_stop_map[r1]
        s2 = route_stop_map[r2]

        shared = s1.intersection(s2)
        shared_count = len(shared)
        if shared_count > 0:
            union_count = len(s1.union(s2))
            jaccard = round(shared_count / union_count, 4)
            containment_r1 = round(shared_count / len(s1), 4)
            containment_r2 = round(shared_count / len(s2), 4)
            smaller_containment = max(containment_r1, containment_r2)

            overlap_records.append({
                "route_a": r1,
                "route_b": r2,
                "shared_stops": shared_count,
                "jaccard_similarity": jaccard,
                "containment_a": containment_r1,
                "containment_b": containment_r2,
                "smaller_route_containment": smaller_containment
            })

    df_overlap = pd.DataFrame(overlap_records).sort_values("jaccard_similarity", ascending=False)

    # Save parquet files
    out_struct = PROCESSED_DIR / "route_structure.parquet"
    out_overlap = PROCESSED_DIR / "route_overlap.parquet"

    df_structure.to_parquet(out_struct, engine="pyarrow", index=False)
    df_overlap.to_parquet(out_overlap, engine="pyarrow", index=False)

    print(f"[EXPORTED] {out_struct.relative_to(WORKSPACE_ROOT)} ({len(df_structure)} routes)")
    print(f"[EXPORTED] {out_overlap.relative_to(WORKSPACE_ROOT)} ({len(df_overlap)} overlapping route pairs)")

    print("\n[TOP 5 HIGH-OVERLAP CORRIDOR PAIRS]:")
    print(df_overlap.head(5)[["route_a", "route_b", "shared_stops", "jaccard_similarity", "smaller_route_containment"]].to_string())

    return df_structure, df_overlap

if __name__ == "__main__":
    compute_route_overlap()
