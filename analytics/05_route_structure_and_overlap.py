"""
Step 6: Route stop coverage, exclusive stops, pairwise Jaccard overlap, and geometry export.
"""
import os
import json
import pandas as pd

PROCESSED_DIR = "data/processed"

def run():
    reg = pd.read_parquet(os.path.join(PROCESSED_DIR, "source_register.parquet"))
    latest_gtfs = reg[reg["dataset_id"] == "cta_gtfs_schedule"].sort_values("catalog_retrieved_date").iloc[-1]
    snap_id = latest_gtfs["snapshot_id"]
    ext_dir = os.path.join(os.path.dirname(latest_gtfs["file_path"]), "extracted")

    routes = pd.read_csv(os.path.join(ext_dir, "routes.txt"), dtype=str)
    bus_routes = routes[routes["route_type"].str.strip() == "3"][["route_id", "route_short_name", "route_long_name"]].copy()
    bus_routes["route_short_name"] = bus_routes["route_short_name"].str.strip()

    trips = pd.read_csv(os.path.join(ext_dir, "trips.txt"), dtype=str).merge(bus_routes, on="route_id", how="inner")
    stop_times = pd.read_csv(os.path.join(ext_dir, "stop_times.txt"), dtype=str)
    stops = pd.read_csv(os.path.join(ext_dir, "stops.txt"), dtype={"stop_id": str, "stop_name": str, "stop_lat": float, "stop_lon": float})
    shapes = pd.read_csv(os.path.join(ext_dir, "shapes.txt"), dtype={"shape_id": str, "shape_pt_lat": float, "shape_pt_lon": float, "shape_pt_sequence": int})

    trip_stops = stop_times[["trip_id", "stop_id"]].drop_duplicates().merge(
        trips[["trip_id", "route_short_name"]].drop_duplicates(), on="trip_id", how="inner"
    )
    route_stops = trip_stops[["route_short_name", "stop_id"]].drop_duplicates()

    stop_route_counts = route_stops.groupby("stop_id")["route_short_name"].nunique().to_dict()
    route_to_stops = route_stops.groupby("route_short_name")["stop_id"].apply(set).to_dict()

    structure_rows = []
    for r_code, s_set in sorted(route_to_stops.items()):
        excl = {s for s in s_set if stop_route_counts.get(s, 0) == 1}
        structure_rows.append({
            "snapshot_id": snap_id,
            "route": r_code,
            "served_stop_count": len(s_set),
            "exclusive_stop_count": len(excl),
            "exclusive_stop_fraction": round(len(excl) / max(1, len(s_set)), 4),
        })

    overlap_rows = []
    route_keys = sorted(route_to_stops.keys())
    for i in range(len(route_keys)):
        for j in range(i + 1, len(route_keys)):
            r1, r2 = route_keys[i], route_keys[j]
            s1, s2 = route_to_stops[r1], route_to_stops[r2]
            shared = len(s1 & s2)
            if shared > 0:
                union = len(s1 | s2)
                smaller = min(len(s1), len(s2))
                overlap_rows.append({
                    "snapshot_id": snap_id,
                    "route_a": r1,
                    "route_b": r2,
                    "shared_stop_count": shared,
                    "jaccard_stop_overlap": round(shared / union, 4),
                    "smaller_route_stop_overlap": round(shared / smaller, 4),
                })

    # Export primary shape coordinates per route for Leaflet maps
    route_shapes = trips[["route_short_name", "shape_id"]].dropna().drop_duplicates("route_short_name")
    shape_geom = {}
    for _, row in route_shapes.iterrows():
        pts = shapes[shapes["shape_id"] == row["shape_id"]].sort_values("shape_pt_sequence")
        shape_geom[row["route_short_name"]] = pts[["shape_pt_lat", "shape_pt_lon"]].values.tolist()

    pd.DataFrame(structure_rows).to_parquet(os.path.join(PROCESSED_DIR, "route_structure.parquet"), index=False)
    pd.DataFrame(overlap_rows).to_parquet(os.path.join(PROCESSED_DIR, "route_overlap.parquet"), index=False)
    stops.to_parquet(os.path.join(PROCESSED_DIR, "stops_reference.parquet"), index=False)
    with open(os.path.join(PROCESSED_DIR, "route_shapes.json"), "w") as f:
        json.dump({"snapshot_id": snap_id, "shapes": shape_geom}, f)

    print(f"[05_structure] Built structure for {len(structure_rows)} routes and {len(overlap_rows)} overlapping pairs.")

if __name__ == "__main__":
    run()
