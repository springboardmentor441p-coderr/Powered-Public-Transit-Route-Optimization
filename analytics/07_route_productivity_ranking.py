"""
analytics/07_route_productivity_ranking.py
RouteRanker Data Pipeline - Step 7: Route Productivity, Clustering & Review Priorities

Analyzes route productivity and operational efficiency:
1. Joins recent 2026 ridership performance with GTFS scheduled service supply.
2. Computes boardings-per-trip efficiency ratios by daytype (W, A, U).
3. Clusters routes via KMeans (k=4) into structural transit archetypes:
   - High-Volume Trunk Corridors
   - Dense Urban Feeders
   - Moderate Community Connectors
   - Low-Density / Specialized Routes
4. Generates explainable Review Priority Tiers:
   - Priority Tier 1 (Frequency Expansion Candidate): High load per trip.
   - Priority Tier 2 (Balanced Steady-State): Capacity well-matched to demand.
   - Priority Tier 3 (Consolidation / Headway Adjustment Candidate): Low load, high overlap.
5. Exports data/processed/productivity_rankings.parquet and data/processed/route_clusters.parquet.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"

def compute_productivity_and_rankings():
    print("=" * 60)
    print("ROUTERANKER PIPELINE: STEP 7 - ROUTE PRODUCTIVITY & CLUSTERING")
    print("=" * 60)

    boardings_path = PROCESSED_DIR / "boardings_clean.parquet"
    service_path = PROCESSED_DIR / "route_scheduled_service.parquet"
    structure_path = PROCESSED_DIR / "route_structure.parquet"

    df_boardings = pd.read_parquet(boardings_path)
    df_service = pd.read_parquet(service_path)
    df_structure = pd.read_parquet(structure_path)

    # 1. Compute 2026 Ridership Aggregates by Route and Daytype
    df_2026 = df_boardings[df_boardings["date"] >= "2026-01-01"].copy()
    print(f"[INPUT] Evaluating 2026 ridership ({len(df_2026):,} daily records across {df_2026['route'].nunique()} routes)...")

    agg_w = df_2026[df_2026["daytype"] == "W"].groupby("route")["rides"].agg(
        total_weekday_rides="sum",
        mean_weekday_rides="mean",
        observed_weekdays="count"
    ).reset_index()

    agg_a = df_2026[df_2026["daytype"] == "A"].groupby("route")["rides"].agg(
        mean_saturday_rides="mean"
    ).reset_index()

    agg_u = df_2026[df_2026["daytype"] == "U"].groupby("route")["rides"].agg(
        mean_sunday_rides="mean"
    ).reset_index()

    # 2. Merge with GTFS Scheduled Service & Structure
    merged = pd.merge(df_service, agg_w, left_on="route_id", right_on="route", how="inner")
    merged = pd.merge(merged, agg_a, on="route", how="left").fillna({"mean_saturday_rides": 0})
    merged = pd.merge(merged, agg_u, on="route", how="left").fillna({"mean_sunday_rides": 0})
    merged = pd.merge(merged, df_structure[["route_id", "exclusive_stops", "exclusivity_pct"]], on="route_id", how="left").fillna(0)

    # 3. Calculate Productivity Metrics (Boardings per Scheduled Trip)
    # Avoid division by zero with clip(1, None)
    merged["rides_per_weekday_trip"] = np.round(
        merged["mean_weekday_rides"] / merged["weekday_scheduled_trips"].clip(1, None), 2
    )
    merged["rides_per_saturday_trip"] = np.round(
        merged["mean_saturday_rides"] / merged["saturday_scheduled_trips"].clip(1, None), 2
    )
    merged["rides_per_sunday_trip"] = np.round(
        merged["mean_sunday_rides"] / merged["sunday_scheduled_trips"].clip(1, None), 2
    )

    # 4. Route Archetype Clustering via KMeans
    cluster_features = ["mean_weekday_rides", "weekday_scheduled_trips", "stops_count", "exclusivity_pct"]
    X_cluster = merged[cluster_features].copy().fillna(0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_cluster)

    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    merged["cluster_id"] = kmeans.fit_predict(X_scaled)

    # Label clusters meaningfully based on mean ridership and trips
    cluster_profiles = merged.groupby("cluster_id")[["mean_weekday_rides", "weekday_scheduled_trips"]].mean()
    sorted_clusters = cluster_profiles.sort_values("mean_weekday_rides", ascending=False).index.tolist()

    archetype_names = {
        sorted_clusters[0]: "Trunk Corridor (High Volume & Supply)",
        sorted_clusters[1]: "Dense Urban Feeder (Moderate-High Load)",
        sorted_clusters[2]: "Community Connector (Moderate Service)",
        sorted_clusters[3]: "Local / Specialized Service (Lower Density)"
    }
    merged["archetype"] = merged["cluster_id"].map(archetype_names)

    # 5. Explainable Review Priority Assignment
    # Determine percentiles for productivity and volume
    p75_prod = merged["rides_per_weekday_trip"].quantile(0.75)
    p25_prod = merged["rides_per_weekday_trip"].quantile(0.25)

    def assign_priority(row):
        # Human-review advisory suggestions based on boardings-per-scheduled-trip ratio (not vehicle occupancy)
        if row["weekday_scheduled_trips"] > 0 and row["rides_per_weekday_trip"] >= p75_prod:
            return "Tier 1: Frequency Expansion Review (High Boardings-per-Trip)"
        elif row["weekday_scheduled_trips"] > 0 and row["rides_per_weekday_trip"] <= p25_prod and row["exclusivity_pct"] < 40:
            return "Tier 3: Route Consolidation Review (Low Boardings-per-Trip, High Overlap)"
        else:
            return "Tier 2: Balanced Operational Baseline"

    merged["review_priority"] = merged.apply(assign_priority, axis=1)

    # Sort by weekday productivity
    merged = merged.sort_values("rides_per_weekday_trip", ascending=False).reset_index(drop=True)

    # Export
    out_rankings = PROCESSED_DIR / "productivity_rankings.parquet"
    merged.to_parquet(out_rankings, engine="pyarrow", index=False)
    print(f"[EXPORTED] {out_rankings.relative_to(WORKSPACE_ROOT)} ({len(merged)} routes analyzed)")

    print("\n[TOP 5 MOST PRODUCTIVE ROUTES (Rides per Scheduled Trip)]:")
    print(merged[["route_id", "route_short_name", "mean_weekday_rides", "weekday_scheduled_trips", "rides_per_weekday_trip", "review_priority"]].head(5).to_string())

    print("\n[REVIEW PRIORITY BREAKDOWN]:")
    print(merged["review_priority"].value_counts().to_string())

    return merged

if __name__ == "__main__":
    compute_productivity_and_rankings()
