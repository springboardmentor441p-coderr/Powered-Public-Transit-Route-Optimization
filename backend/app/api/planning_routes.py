"""
RouteRanker: Route Planning REST API
Exposes endpoints for:
- Origin to Destination multi-modal routing
- Searchable list of all Chicago stops and stations
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
import os
import pandas as pd

from route_optimization.route_planner import cta_route_planner

router = APIRouter(prefix="/api/route", tags=["Route Optimization & Planning"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

@router.get("/plan")
def plan_transit_trip(
    origin: str = Query(..., description="Origin station name or ID (e.g. Belmont, O'Hare, Clark/Lake)"),
    destination: str = Query(..., description="Destination station name or ID (e.g. Jackson, Midway, Lake)"),
    preference: str = Query("fastest", description="'fastest' (minimum duration) or 'min_transfers' (fewer line changes)")
):
    """
    Computes optimal transit itinerary between Chicago CTA stops with step-by-step instructions and waypoints.
    """
    res = cta_route_planner.plan_route(origin_id=origin, destination_id=destination, preference=preference)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.get("/locations")
def search_transit_locations(query: Optional[str] = Query(None, description="Search query")):
    """
    Returns searchable stops and stations for auto-complete in the frontend route planner.
    """
    st_path = os.path.join(PROCESSED_DIR, "cleaned_l_stations_directory.csv")
    if not os.path.exists(st_path):
        raise HTTPException(status_code=404, detail="Station directory not found")
        
    df = pd.read_csv(st_path)
    locations = []
    
    # 1. Rail Stations
    for _, row in df.iterrows():
        name = str(row["station_name"])
        lines = str(row["lines_served"])
        if query and query.lower() not in name.lower() and query.lower() not in lines.lower():
            continue
        locations.append({
            "id": f"RAIL_{row['station_id']}",
            "name": name,
            "type": "Rail Station ('L')",
            "subtitle": f"{lines} Line{'s' if ',' in lines else ''}",
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"])
        })
        
    # 2. Key Bus Hubs and Corridor Bus Stops from Network Graph
    try:
        cta_route_planner._load_graph()
        G = cta_route_planner._graph
        if G:
            for n, d in G.nodes(data=True):
                if d.get("node_type") == "bus_stop":
                    b_name = d.get("name", "")
                    b_desc = d.get("descriptive_name", f"Route {d.get('route_id', '')} Bus Stop")
                    if query and query.lower() not in b_name.lower() and query.lower() not in b_desc.lower():
                        continue
                    locations.append({
                        "id": n,
                        "name": b_name,
                        "type": "Bus Stop / Hub",
                        "subtitle": b_desc,
                        "latitude": float(d.get("latitude", 0.0)),
                        "longitude": float(d.get("longitude", 0.0))
                    })
    except Exception as e:
        # Fallback to key intermodal terminals if graph fails to load
        fallback_bus_stops = [
            {"id": "BUS_79_Ford_City_Mall", "name": "Ford City Mall", "type": "Bus Terminal", "subtitle": "Route 79 Western Terminus", "latitude": 41.758, "longitude": -87.734},
            {"id": "BUS_66_Navy_Pier_Terminal", "name": "Navy Pier Terminal", "type": "Bus Terminal", "subtitle": "Route 66 Eastern Terminus", "latitude": 41.892, "longitude": -87.608},
            {"id": "BUS_9_95th_Ashland", "name": "95th/Ashland", "type": "Bus Hub", "subtitle": "Route 9 Southern Terminus", "latitude": 41.721, "longitude": -87.663}
        ]
        for b in fallback_bus_stops:
            if query and query.lower() not in b["name"].lower():
                continue
            locations.append(b)
        
    return {
        "count": len(locations),
        "locations": locations
    }

