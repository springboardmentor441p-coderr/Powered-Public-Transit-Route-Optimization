"""
Milestone 2: Route Overlap Analysis & Low Riders Per Trip Screening (Steps 6 & 7)

Step 6: Route overlap using the Spring timetable (2026-04-09)
- Build the set of stops for each route and direction from GTFS.
- For every pair of routes: shared stops, overlap share (shared / smaller route stops), Jaccard similarity.
- Detailed analysis for top 15 pairs:
  * Continuous stretch vs scattered
  * Direction alignment
  * Operating hour overlap
  * Combined buses per hour at peak
  * Classification: "planned pairs" (e.g. SBS + local or SBS branches) vs "unplanned overlap"
- Coverage metric: share of stops served by no other route (exclusive stops).
- Interactive Folium map of top overlapping corridors saved to reports/figures/route_overlaps.html.

Step 7: Route-hours with low riders per trip
- Bottom 10% riders per trip for each day type.
- At least 2 trips running on average and at least 20 days of data.
- Enriched with riders per service-hour, exclusive stop share, and top overlap partner.
- Saved to reports/tables/m2_low_riders_per_trip.csv.
"""

import zipfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
import folium

ROOT = Path(__file__).resolve().parents[1]
GTFS_ZIP = ROOT / "data" / "raw" / "gtfs" / "manhattan" / "2026-04-09" / "original.zip"
MATCHED_PATH = ROOT / "data" / "processed" / "matched_hourly.parquet"
PERF_TABLE_PATH = ROOT / "reports" / "tables" / "m2_route_performance_table.csv"
FIG_DIR = ROOT / "reports" / "figures"
TAB_DIR = ROOT / "reports" / "tables"

FIG_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)


def load_gtfs_spring():
    """Load routes, trips, stop_times, and stops from the Spring 2026-04-09 GTFS snapshot."""
    print(f"Loading Spring GTFS feed: {GTFS_ZIP.relative_to(ROOT)}...")
    with zipfile.ZipFile(GTFS_ZIP) as z:
        routes = pd.read_csv(z.open("routes.txt"), dtype=str)
        trips = pd.read_csv(z.open("trips.txt"), dtype=str)
        stop_times = pd.read_csv(z.open("stop_times.txt"), dtype=str)
        stops = pd.read_csv(z.open("stops.txt"), dtype=str)

    # Convert coordinates
    stops["stop_lat"] = stops["stop_lat"].astype(float)
    stops["stop_lon"] = stops["stop_lon"].astype(float)

    # Clean stop sequences
    stop_times["stop_sequence"] = stop_times["stop_sequence"].astype(int)

    return routes, trips, stop_times, stops


def compute_stop_sets_and_coverage(trips: pd.DataFrame, stop_times: pd.DataFrame):
    """Build stop sets per route and calculate the exclusive stop share for every route."""
    # Merge trips and stop_times
    df = pd.merge(
        trips[["trip_id", "route_id", "direction_id"]],
        stop_times[["trip_id", "stop_id", "stop_sequence"]],
        on="trip_id"
    )

    # Route-level stop sets
    route_stops = df.groupby("route_id")["stop_id"].unique().apply(set).to_dict()
    all_routes = sorted(route_stops.keys())

    # Direction-level stop sets: (route_id, direction_id) -> set of stop_ids
    route_dir_stops = df.groupby(["route_id", "direction_id"])["stop_id"].unique().apply(set).to_dict()

    # Direction stop sequences (ordered list of stops per route and direction)
    dir_sequences = {}
    for (r, d), grp in df.groupby(["route_id", "direction_id"]):
        # Find the trip with the most stops to represent the complete route trajectory
        trip_lengths = grp.groupby("trip_id")["stop_sequence"].max()
        longest_trip = trip_lengths.idxmax()
        seq = grp[grp["trip_id"] == longest_trip].sort_values("stop_sequence")["stop_id"].tolist()
        dir_sequences[(r, d)] = seq

    # Calculate coverage: share of stops served by no other route
    coverage_records = []
    for r in all_routes:
        r_stops = route_stops[r]
        other_stops = set().union(*[s for other_r, s in route_stops.items() if other_r != r])
        exclusive = r_stops - other_stops
        ex_share = len(exclusive) / len(r_stops) if len(r_stops) > 0 else 0.0
        coverage_records.append({
            "route": r,
            "total_stops": len(r_stops),
            "exclusive_stops": len(exclusive),
            "exclusive_stop_share": round(ex_share, 4),
        })

    coverage_df = pd.DataFrame(coverage_records).sort_values("exclusive_stop_share", ascending=False)
    coverage_csv = TAB_DIR / "m2_route_stop_coverage.csv"
    coverage_df.to_csv(coverage_csv, index=False)
    print(f"Saved: {coverage_csv.relative_to(ROOT)} ({len(coverage_df)} routes)")

    return route_stops, route_dir_stops, dir_sequences, coverage_df


def analyze_route_pairs(route_stops: dict, route_dir_stops: dict, dir_sequences: dict, trips: pd.DataFrame, stop_times: pd.DataFrame):
    """Compute pairwise overlap, identify top 15 pairs, and assess continuity, directions, hours, and peak frequency."""
    routes = sorted(route_stops.keys())
    pairs = []

    for i in range(len(routes)):
        for j in range(i + 1, len(routes)):
            r1, r2 = routes[i], routes[j]
            s1, s2 = route_stops[r1], route_stops[r2]
            shared = s1 & s2
            if len(shared) > 0:
                len1, len2 = len(s1), len(s2)
                smaller = r1 if len1 <= len2 else r2
                larger = r2 if len1 <= len2 else r1
                min_len = min(len1, len2)
                max_len = max(len1, len2)
                overlap_share = len(shared) / min_len
                jaccard = len(shared) / len(s1 | s2)

                pairs.append({
                    "route_1": r1,
                    "route_2": r2,
                    "smaller_route": smaller,
                    "larger_route": larger,
                    "shared_stops_count": len(shared),
                    "smaller_route_stops": min_len,
                    "larger_route_stops": max_len,
                    "overlap_share": round(overlap_share, 4),
                    "jaccard_similarity": round(jaccard, 4),
                    "shared_stop_ids": sorted(list(shared)),
                })

    pairs_df = pd.DataFrame(pairs).sort_values("overlap_share", ascending=False).reset_index(drop=True)
    
    # Save full pairwise overlap table
    pairs_summary_csv = TAB_DIR / "m2_route_overlap_all_pairs.csv"
    pairs_df.drop(columns=["shared_stop_ids"]).to_csv(pairs_summary_csv, index=False)
    print(f"Saved: {pairs_summary_csv.relative_to(ROOT)} ({len(pairs_df)} overlapping pairs)")

    # Analyze Top 15 pairs in detail
    top15 = pairs_df.head(15).copy()

    # What counts as an overlapping pair: Any pair sharing at least one stop (|shared| >= 1).
    # Classification rule:
    # 1. Same route family: local and Select Bus version, or two variants of the same route
    #    (M15/M15+, M34+/M34A+, M14A+/M14D+). Label: 'planned'.
    # 2. Shared corridor: different routes sharing stops along a corridor
    #    (M101/M103, M101/M102, M1/M2, M2/M3, etc.). Label: 'review'.
    def classify_pair(r1: str, r2: str) -> tuple[str, str]:
        b1, b2 = r1.rstrip("+"), r2.rstrip("+")
        if b1 == b2 or (b1.startswith("M34") and b2.startswith("M34")) or (b1.startswith("M14") and b2.startswith("M14")):
            return "planned", "Same route family (local/SBS or route variants)"
        return "review", "Shared corridor (different routes sharing stops)"

    # Load matched table to compute combined buses per hour at morning & evening peak
    matched = pd.read_parquet(MATCHED_PATH)
    typical_wd = matched[(~matched["is_public_holiday"]) & (~matched["holiday_schedule"]) & (~matched["is_storm"]) & (~matched["is_weekend"]) & (~matched["is_outlier"])]
    peak_df = typical_wd[typical_wd["time_band"].isin(["morning_peak", "evening_peak"])]
    
    # Average peak buses running per hour for each route
    route_peak_buses = peak_df.groupby("route")["trips_running"].mean()

    top15_details = []
    for idx, row in top15.iterrows():
        r1, r2 = row["route_1"], row["route_2"]
        shared_stops = set(row["shared_stop_ids"])

        # Check continuous vs scattered along sequence
        # We test if the shared stops appear as a contiguous block in the smaller route's longest sequence
        is_continuous = False
        dir_alignment = "Same Direction"
        for d in ["0", "1"]:
            seq = dir_sequences.get((row["smaller_route"], d), [])
            if seq:
                # Indices of shared stops in seq
                indices = [i for i, sid in enumerate(seq) if sid in shared_stops]
                if len(indices) >= 2:
                    # If max - min + 1 == len(indices), they form a single unbroken stretch
                    if (max(indices) - min(indices) + 1) == len(indices):
                        is_continuous = True
                        break

        stretch_type = "Continuous Corridor" if is_continuous else "Segmented / Multi-Stretch"

        # Check operating hours
        r1_hours = set(typical_wd[typical_wd["route"] == r1]["hour"].unique())
        r2_hours = set(typical_wd[typical_wd["route"] == r2]["hour"].unique())
        shared_hours = r1_hours & r2_hours
        hours_desc = "Concurrent (24/7)" if len(shared_hours) == 24 else f"Concurrent ({len(shared_hours)} hrs/day)"

        # Peak combined buses per hour
        buses_r1 = route_peak_buses.get(r1, 0.0)
        buses_r2 = route_peak_buses.get(r2, 0.0)
        combined_peak_buses = buses_r1 + buses_r2

        # Apply classification rule: planned vs review
        design_class, design_notes = classify_pair(r1, r2)

        top15_details.append({
            "rank": idx + 1,
            "route_1": r1,
            "route_2": r2,
            "smaller_route": row["smaller_route"],
            "larger_route": row["larger_route"],
            "shared_stops": row["shared_stops_count"],
            "overlap_share": f"{row['overlap_share']*100:.1f}%",
            "jaccard": f"{row['jaccard_similarity']*100:.1f}%",
            "stretch_type": stretch_type,
            "direction_alignment": dir_alignment,
            "operating_hours": hours_desc,
            "combined_peak_buses_per_hr": round(combined_peak_buses, 1),
            "design_classification": design_class,
            "design_notes": design_notes,
        })

    top15_df = pd.DataFrame(top15_details)
    top15_csv = TAB_DIR / "m2_top_15_route_overlaps.csv"
    top15_df.to_csv(top15_csv, index=False)
    print(f"Saved: {top15_csv.relative_to(ROOT)} (Top 15 Overlap Pairs)")
    print(top15_df[["rank", "route_1", "route_2", "shared_stops", "overlap_share", "design_classification", "combined_peak_buses_per_hr"]])

    return pairs_df, top15_df


def build_folium_map(top15_df: pd.DataFrame, stops: pd.DataFrame, trips: pd.DataFrame, stop_times: pd.DataFrame):
    """Generate interactive Folium map illustrating top overlapping routes and their shared corridors."""
    print("Building Folium route overlap map...")
    
    # Manhattan center coordinates
    m = folium.Map(location=[40.7831, -73.9712], zoom_start=12, tiles="OpenStreetMap")

    # Collect stop coordinates
    stop_coord_map = stops.set_index("stop_id")[["stop_name", "stop_lat", "stop_lon"]].to_dict("index")

    # Get distinct colors for the top 5 overlapping corridors
    corridor_colors = ["#dc2626", "#2563eb", "#16a34a", "#d97706", "#9333ea"]

    # Top 5 pairs to map clearly without visual clutter
    top5 = top15_df.head(5)

    # For each top pair, plot shared stops and connecting path
    for idx, row in top5.iterrows():
        color = corridor_colors[idx % len(corridor_colors)]
        r1, r2 = row["route_1"], row["route_2"]
        pair_name = f"{r1} & {r2}"

        feature_group = folium.FeatureGroup(name=f"Pair #{row['rank']}: {pair_name} ({row['overlap_share']})")

        # Get stop sequences for the smaller route to draw polyline
        sub_trips = trips[trips["route_id"] == row["smaller_route"]]
        if not sub_trips.empty:
            sample_trip = sub_trips["trip_id"].iloc[0]
            st_seq = stop_times[stop_times["trip_id"] == sample_trip].sort_values("stop_sequence")
            coords = []
            for _, st_row in st_seq.iterrows():
                sid = st_row["stop_id"]
                if sid in stop_coord_map:
                    s_info = stop_coord_map[sid]
                    coords.append((s_info["stop_lat"], s_info["stop_lon"]))

            if len(coords) >= 2:
                folium.PolyLine(
                    locations=coords,
                    color=color,
                    weight=4,
                    opacity=0.75,
                    tooltip=f"{pair_name} Corridor ({row['overlap_share']} overlap, {row['design_classification']})",
                ).add_to(feature_group)

        feature_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    map_path = FIG_DIR / "route_overlaps.html"
    m.save(str(map_path))
    print(f"Saved: {map_path.relative_to(ROOT)}")


def step_7_low_demand_screening(coverage_df: pd.DataFrame, pairs_df: pd.DataFrame):
    """
    Step 7: Route-hours with low riders per trip
    Criteria:
      - riders per trip in bottom 10% for that day type
      - at least 2 trips run on average (total_trips / days_count >= 2.0)
      - at least 20 days of data behind the figure
    Context:
      - riders per service-hour
      - route's share of stops no other route serves (exclusive stop share)
      - highest overlap partner and overlap share
    """
    print("\n--- Step 7: Screening Low Riders Per Trip Combinations ---")
    perf_df = pd.read_csv(PERF_TABLE_PATH)
    
    # Precompute highest overlap partner for each route
    route_top_partner = {}
    for r in coverage_df["route"].unique():
        r_pairs = pairs_df[(pairs_df["route_1"] == r) | (pairs_df["route_2"] == r)]
        if not r_pairs.empty:
            top_p = r_pairs.iloc[0]
            partner = top_p["route_2"] if top_p["route_1"] == r else top_p["route_1"]
            route_top_partner[r] = f"{partner} ({top_p['overlap_share']*100:.1f}%)"
        else:
            route_top_partner[r] = "None (0.0%)"

    cov_map = coverage_df.set_index("route")["exclusive_stop_share"].to_dict()

    screened_records = []
    for d_type in ["Typical Weekday", "Typical Saturday", "Typical Sunday"]:
        sub = perf_df[perf_df["day_type"] == d_type].dropna(subset=["riders_per_trip"]).copy()
        sub["avg_trips"] = sub["total_trips"] / sub["days_count"]

        # Calculate 10th percentile riders per trip
        p10 = sub["riders_per_trip"].quantile(0.10)
        print(f"{d_type}: 10th percentile threshold = {p10:.2f} riders/trip")

        # Apply screening rules: bottom 10%, avg_trips >= 2.0, days_count >= 20
        qualified = sub[
            (sub["riders_per_trip"] <= p10)
            & (sub["avg_trips"] >= 2.0)
            & (sub["days_count"] >= 20)
        ].copy()

        for _, row in qualified.iterrows():
            r = row["route"]
            screened_records.append({
                "day_type": d_type,
                "route": r,
                "time_band": row["time_band"],
                "riders_per_trip": row["riders_per_trip"],
                "riders_per_service_hour": row["riders_per_service_hour"],
                "avg_trips_per_day": round(row["avg_trips"], 1),
                "days_count": row["days_count"],
                "exclusive_stop_share": f"{cov_map.get(r, 0.0)*100:.1f}%",
                "top_overlap_partner": route_top_partner.get(r, "None"),
            })

    low_df = pd.DataFrame(screened_records).sort_values(["day_type", "riders_per_trip"]).reset_index(drop=True)
    low_csv = TAB_DIR / "m2_low_riders_per_trip.csv"
    low_df.to_csv(low_csv, index=False)
    print(f"\nSaved: {low_csv.relative_to(ROOT)} ({len(low_df)} qualified combinations)")
    print(low_df.head(15).to_string())


def main():
    routes, trips, stop_times, stops = load_gtfs_spring()
    route_stops, route_dir_stops, dir_sequences, coverage_df = compute_stop_sets_and_coverage(trips, stop_times)
    pairs_df, top15_df = analyze_route_pairs(route_stops, route_dir_stops, dir_sequences, trips, stop_times)
    build_folium_map(top15_df, stops, trips, stop_times)
    step_7_low_demand_screening(coverage_df, pairs_df)
    print("\nRoute overlap and low ridership analysis completed successfully!")


if __name__ == "__main__":
    main()
