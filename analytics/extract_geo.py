import os
import json
import pandas as pd
import numpy as np

GTFS_DIR = "data/raw/gtfs/mdb-389-202607110020/extracted/"
DATA_DIR = "data/processed/v1"
OUTPUT_FILE = os.path.join(DATA_DIR, "cta_routes_geo.json")

print("Loading GTFS tables...")
routes_df = pd.read_csv(os.path.join(GTFS_DIR, "routes.txt"))
routes_df["route_id"] = routes_df["route_id"].astype(str)

profiles_df = pd.read_csv(os.path.join(DATA_DIR, "expanded_utilization_profiles.csv"))
clusters_df = pd.read_csv(os.path.join(DATA_DIR, "route_clusters.csv"))
clusters_df["route"] = clusters_df["route"].astype(str)
cluster_map = dict(zip(clusters_df["route"], clusters_df["cluster_label"]))

study_routes = set(profiles_df["route"].astype(str).unique())
print(f"Targeting {len(study_routes)} study routes...")

trips_df = pd.read_csv(os.path.join(GTFS_DIR, "trips.txt"), usecols=["route_id", "trip_id", "shape_id", "direction_id"])
trips_df["route_id"] = trips_df["route_id"].astype(str)
trips_df = trips_df[trips_df["route_id"].isin(study_routes)]

# Find top shape_id for each direction of each route
top_shapes_per_route = {}
top_trips_per_route = {}

for r, grp in trips_df.groupby("route_id"):
    dir_shapes = []
    dir_trips = []
    for d, d_grp in grp.groupby("direction_id"):
        shape_counts = d_grp["shape_id"].value_counts()
        if not shape_counts.empty:
            best_shape = shape_counts.index[0]
            dir_shapes.append(best_shape)
            sample_trip = d_grp[d_grp["shape_id"] == best_shape]["trip_id"].iloc[0]
            dir_trips.append(sample_trip)
    top_shapes_per_route[r] = dir_shapes
    top_trips_per_route[r] = dir_trips

all_needed_shapes = set(s for shapes in top_shapes_per_route.values() for s in shapes)
all_needed_trips = set(t for trips in top_trips_per_route.values() for t in trips)

print("Reading shapes.txt...")
shapes_df = pd.read_csv(os.path.join(GTFS_DIR, "shapes.txt"), usecols=["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
shapes_df = shapes_df[shapes_df["shape_id"].isin(all_needed_shapes)].sort_values(["shape_id", "shape_pt_sequence"])

print("Reading stop_times.txt and stops.txt...")
stop_times_df = pd.read_csv(os.path.join(GTFS_DIR, "stop_times.txt"), usecols=["trip_id", "stop_id", "stop_sequence"])
stop_times_df = stop_times_df[stop_times_df["trip_id"].isin(all_needed_trips)].sort_values(["trip_id", "stop_sequence"])

stops_df = pd.read_csv(os.path.join(GTFS_DIR, "stops.txt"))
stops_map = stops_df.set_index("stop_id").to_dict(orient="index")

# Downsample polyline points
def downsample_points(pts, max_pts=85):
    if len(pts) <= max_pts:
        return pts
    step = int(np.ceil(len(pts) / max_pts))
    sampled = pts[::step]
    if sampled[-1] != pts[-1]:
        sampled.append(pts[-1])
    return sampled

geo_routes = {}

CLUSTER_COLORS = {
    "High-Demand Trunk Corridors": "#059669",
    "Moderate Neighborhood Routes": "#0284c7",
    "Strong Urban Connectors": "#7c3aed",
    "Specialized / Lower-Volume Routes": "#d97706",
    "Ungrouped": "#64748b"
}

for _, r_row in routes_df[routes_df["route_id"].isin(study_routes)].iterrows():
    r_id = r_row["route_id"]
    r_short = str(r_row["route_short_name"]) if pd.notna(r_row["route_short_name"]) else r_id
    r_long = str(r_row["route_long_name"]) if pd.notna(r_row["route_long_name"]) else f"Route {r_id}"
    cluster = cluster_map.get(r_id, "Ungrouped")
    color = CLUSTER_COLORS.get(cluster, "#059669")

    # Polylines
    polylines = []
    route_shapes = top_shapes_per_route.get(r_id, [])
    for sid in route_shapes:
        s_data = shapes_df[shapes_df["shape_id"] == sid]
        pts = [[round(lat, 5), round(lon, 5)] for lat, lon in zip(s_data["shape_pt_lat"], s_data["shape_pt_lon"])]
        if pts:
            polylines.append(downsample_points(pts, max_pts=90))

    # Stops with rich data
    stops_list = []
    seen_stop_ids = set()
    route_trips = top_trips_per_route.get(r_id, [])
    for tid in route_trips:
        st_data = stop_times_df[stop_times_df["trip_id"] == tid]
        for sid in st_data["stop_id"]:
            if sid not in seen_stop_ids and sid in stops_map:
                seen_stop_ids.add(sid)
                s_info = stops_map[sid]
                name = str(s_info.get("stop_name", ""))
                desc = str(s_info.get("stop_desc", "")) if pd.notna(s_info.get("stop_desc")) else ""
                is_terminal = "Terminal" in name or "Terminal" in desc or "Transit Center" in name
                wheelchair = s_info.get("wheelchair_boarding", 1) == 1

                stops_list.append({
                    "stop_id": int(sid),
                    "name": name,
                    "desc": desc,
                    "lat": round(s_info["stop_lat"], 5),
                    "lon": round(s_info["stop_lon"], 5),
                    "is_terminal": is_terminal,
                    "wheelchair": wheelchair,
                    "routes_served": [r_id]
                })

    all_lats = [p[0] for line in polylines for p in line] + [s["lat"] for s in stops_list]
    all_lons = [p[1] for line in polylines for p in line] + [s["lon"] for s in stops_list]

    bounds = None
    if all_lats and all_lons:
        bounds = [
            [round(min(all_lats), 5), round(min(all_lons), 5)],
            [round(max(all_lats), 5), round(max(all_lons), 5)]
        ]

    geo_routes[r_id] = {
        "route_id": r_id,
        "name": r_short,
        "long_name": r_long,
        "cluster": cluster,
        "color": color,
        "polylines": polylines,
        "stops": stops_list,
        "bounds": bounds,
        "stop_count": len(stops_list),
        "point_count": sum(len(line) for line in polylines)
    }

print(f"Generated rich geo info for {len(geo_routes)} routes.")
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(geo_routes, f)

file_size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
print(f"Successfully saved to {OUTPUT_FILE} ({file_size_mb:.2f} MB)")
