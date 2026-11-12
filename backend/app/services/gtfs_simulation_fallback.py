"""
RouteRanker: GTFS Schedule-Derived Transit Position Simulator
Used as graceful fallback when developer API keys are unconfigured in .env.
Simulates realistic vehicle locations along active GTFS transit corridors in Chicago.
"""

import os
import math
import time
import random
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime, timezone
from backend.app.schemas.transit_schemas import (
    BusVehiclePosition, TrainPosition, BusArrivalPrediction, TrainArrivalPrediction
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

# Cache routes and stations in memory
_stops_cache = None
_routes_cache = None
_stations_cache = None
_bus_shapes_cache = None

def _get_static_data():
    global _stops_cache, _routes_cache, _stations_cache, _bus_shapes_cache
    if _stops_cache is None:
        _stops_cache = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_gtfs_stops.csv"))
    if _routes_cache is None:
        _routes_cache = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_gtfs_routes.csv"))
    if _stations_cache is None:
        _stations_cache = pd.read_csv(os.path.join(PROCESSED_DIR, "cleaned_l_stations_directory.csv"))
    if _bus_shapes_cache is None:
        shapes_path = os.path.join(PROCESSED_DIR, "gtfs_bus_corridor_shapes.json")
        if os.path.exists(shapes_path):
            import json
            with open(shapes_path, "r") as f:
                _bus_shapes_cache = json.load(f)
        else:
            _bus_shapes_cache = {}
    return _stops_cache, _routes_cache, _stations_cache, _bus_shapes_cache

class GTFSSimulationFallback:
    def __init__(self):
        pass

    def get_simulated_buses(self, route_id: str = None) -> List[BusVehiclePosition]:
        stops_df, routes_df, _, bus_shapes = _get_static_data()
        
        bus_routes = routes_df[routes_df["transit_mode"] == "Bus"]
        if route_id:
            bus_routes = bus_routes[bus_routes["route_id"].astype(str).str.upper() == str(route_id).upper()]
            if bus_routes.empty:
                # If specific route not found, sample top routes
                bus_routes = routes_df[routes_df["transit_mode"] == "Bus"].head(5)
        else:
            # Show active vehicles across top Chicago bus corridors
            priority_routes = ["79", "9", "66", "4", "49", "X9", "22", "8", "53", "3"]
            bus_routes = bus_routes[bus_routes["route_id"].isin(priority_routes)]

        now_sec = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        
        vehicles = []
        for _, r in bus_routes.iterrows():
            rid = str(r["route_id"])
            dest = str(r["route_long_name"]) or f"Route {rid} Terminal"
            
            # Check if official GTFS shape points exist for this corridor
            shape_pts = bus_shapes.get(rid, [])
            
            # 4 vehicles per route spaced along actual route alignment
            num_vehicles = 4
            for v_idx in range(num_vehicles):
                vid = f"BUS-{rid}-{101 + v_idx}"
                
                if shape_pts and len(shape_pts) >= 4:
                    # Interpolate along authentic GTFS shape geometry
                    total_pts = len(shape_pts)
                    # Drift progression over 120 seconds
                    progress = ((now_sec / 120.0) + (v_idx / num_vehicles)) % 1.0
                    pt_idx = int(progress * (total_pts - 1))
                    next_pt_idx = min(total_pts - 1, pt_idx + 1)
                    sub_prog = (progress * (total_pts - 1)) - pt_idx
                    
                    lat1, lon1 = shape_pts[pt_idx]
                    lat2, lon2 = shape_pts[next_pt_idx]
                    lat = lat1 + (lat2 - lat1) * sub_prog
                    lon = lon1 + (lon2 - lon1) * sub_prog
                    
                    d_lat = lat2 - lat1
                    d_lon = lon2 - lon1
                    heading = int((math.degrees(math.atan2(d_lon, d_lat)) + 360) % 360)
                else:
                    # Fallback to bounded Chicago corridor alignment
                    base_lat = 41.80 + (int(rid) % 15) * 0.012 if rid.isdigit() else 41.88
                    base_lon = -87.68 + (v_idx * 0.02)
                    phase = (now_sec / 40.0 + v_idx * 1.5) % (2 * math.pi)
                    lat = base_lat + 0.008 * math.sin(phase)
                    lon = base_lon + 0.008 * math.cos(phase)
                    heading = int((math.degrees(phase) + 90) % 360)
                
                # Strict Chicago boundary validation: 41.6 <= lat <= 42.1, -87.85 <= lon <= -87.52
                lat = max(41.65, min(42.05, lat))
                lon = max(-87.85, min(-87.55, lon))
                
                speed = round(14.0 + 4.0 * math.sin(v_idx + now_sec / 20.0), 1)
                is_dly = (v_idx == 2 and (int(now_sec) // 60) % 3 == 0)
                
                vehicles.append(BusVehiclePosition(
                    vehicle_id=vid,
                    route_id=rid,
                    destination=dest,
                    latitude=round(lat, 5),
                    longitude=round(lon, 5),
                    heading=heading,
                    speed_mph=max(0.0, speed),
                    is_delayed=is_dly,
                    pattern_id=f"PAT-{rid}-GTFS",
                    timestamp=now_iso
                ))
        return vehicles

    def get_simulated_trains(self, line_name: str = None) -> List[TrainPosition]:
        _, _, stations_df, _ = _get_static_data()
        
        lines = ["Red", "Blue", "Brown", "Green", "Orange", "Purple", "Pink", "Yellow"]
        if line_name:
            target_line = line_name.capitalize()
            lines = [l for l in lines if l.lower() == target_line.lower()]
            if not lines:
                lines = ["Red", "Blue"]
                
        now_sec = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        
        trains = []
        run_counter = 100
        
        dest_map = {
            "Red": ("Howard", "95th/Dan Ryan"),
            "Blue": ("O'Hare", "Forest Park"),
            "Brown": ("Kimball", "Loop"),
            "Green": ("Harlem/Lake", "Ashland/63rd"),
            "Orange": ("Midway", "Loop"),
            "Purple": ("Linden", "Loop"),
            "Pink": ("54th/Cermak", "Loop"),
            "Yellow": ("Dempster-Skokie", "Howard")
        }
        
        for l in lines:
            line_stations = stations_df[stations_df["lines_served"].str.contains(l, case=False, na=False)]
            if line_stations.empty:
                continue
                
            dests = dest_map.get(l, ("Terminal North", "Terminal South"))
            
            # 2 trains in each direction
            for dir_idx, dest in enumerate(dests):
                for train_num in range(2):
                    run_counter += 1
                    phase = (now_sec / 50.0 + dir_idx * 2.0 + train_num * 1.8) % (2 * math.pi)
                    
                    # Pick station along line
                    idx = int(((math.sin(phase) + 1) / 2) * (len(line_stations) - 1))
                    curr_station = line_stations.iloc[idx]
                    next_idx = min(len(line_stations) - 1, idx + 1 if dir_idx == 0 else max(0, idx - 1))
                    next_station = line_stations.iloc[next_idx]
                    
                    lat = float(curr_station["latitude"]) + 0.002 * math.cos(phase)
                    lon = float(curr_station["longitude"]) + 0.002 * math.sin(phase)
                    heading = 0 if dir_idx == 0 else 180
                    
                    trains.append(TrainPosition(
                        run_number=str(run_counter),
                        line_name=l,
                        destination_name=dest,
                        latitude=round(lat, 5),
                        longitude=round(lon, 5),
                        heading=heading,
                        next_station_id=str(next_station["station_id"]),
                        next_station_name=str(next_station["station_name"]),
                        is_approaching=(train_num == 0),
                        is_delayed=(run_counter % 7 == 0),
                        timestamp=now_iso
                    ))
        return trains

    def get_simulated_bus_predictions(self, stop_id: str) -> List[BusArrivalPrediction]:
        stops_df, _, _ = _get_static_data()
        stop_match = stops_df[stops_df["stop_id"].astype(str) == str(stop_id)]
        stop_name = stop_match.iloc[0]["stop_name"] if not stop_match.empty else f"Stop {stop_id}"
        
        predictions = []
        for i, mins in enumerate([3, 11, 22]):
            arr_time = datetime.fromtimestamp(time.time() + mins * 60, timezone.utc).strftime("%Y%m%d %H:%M:%S")
            predictions.append(BusArrivalPrediction(
                prediction_type="A",
                stop_id=str(stop_id),
                stop_name=stop_name,
                vehicle_id=f"BUS-{1400 + i}",
                route_id="79" if i != 1 else "9",
                destination="Lakefront / Eastbound" if i != 1 else "Northbound",
                predicted_arrival_time=arr_time,
                countdown_minutes=mins,
                is_delayed=False
            ))
        return predictions

    def get_simulated_train_predictions(self, station_id: str) -> List[TrainArrivalPrediction]:
        _, _, stations_df, _ = _get_static_data()
        st_match = stations_df[stations_df["station_id"].astype(str) == str(station_id)]
        
        st_name = st_match.iloc[0]["station_name"] if not st_match.empty else f"Station {station_id}"
        lines_str = st_match.iloc[0]["lines_served"] if not st_match.empty else "Red"
        primary_line = lines_str.split(",")[0].strip()
        
        predictions = []
        for i, (mins, plat, dest) in enumerate([
            (2, "Northbound / Howard-bound", "Howard"),
            (7, "Southbound / 95th-bound", "95th/Dan Ryan"),
            (14, "Northbound / Howard-bound", "Howard")
        ]):
            arr_time = datetime.fromtimestamp(time.time() + mins * 60, timezone.utc).isoformat()
            predictions.append(TrainArrivalPrediction(
                station_id=str(station_id),
                stop_id=f"30{station_id[-3:] if len(station_id)>=3 else '100'}",
                station_name=st_name,
                platform_description=plat,
                run_number=f"{201 + i}",
                line_name=primary_line,
                destination_name=dest,
                arrival_time=arr_time,
                countdown_minutes=mins,
                is_approaching=(mins <= 2),
                is_delayed=False
            ))
        return predictions

gtfs_simulator = GTFSSimulationFallback()

