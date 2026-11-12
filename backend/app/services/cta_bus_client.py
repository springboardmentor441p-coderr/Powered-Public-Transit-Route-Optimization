"""
RouteRanker: CTA Bus Tracker API Client
Integrates official CTA Bus Tracker API v2:
http://www.ctabustracker.com/bustime/api/v2/
Endpoints: getvehicles, getpredictions, getroutes, getstops
Handles rate-limits, timeouts, caching, and fallback.
"""

import os
import urllib.request
import urllib.parse
import json
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone
from dotenv import load_dotenv

from backend.app.schemas.transit_schemas import (
    BusVehiclePosition, BusArrivalPrediction, APIResponseMetadata
)
from backend.app.services.transit_cache import global_transit_cache
from backend.app.services.gtfs_simulation_fallback import gtfs_simulator

load_dotenv()
logger = logging.getLogger(__name__)

BUS_API_BASE = "http://www.ctabustracker.com/bustime/api/v2/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RouteRanker-Transit/1.0"

class CTABusClient:
    def __init__(self):
        self.api_key = os.getenv("CTA_BUS_API_KEY", "").strip()
        self.is_configured = bool(self.api_key and not self.api_key.startswith("YOUR_"))

    def get_vehicle_positions(self, route_id: str = None) -> Tuple[List[BusVehiclePosition], APIResponseMetadata]:
        cache_key = f"bus_vehicles_{route_id or 'all'}"
        cached_entry = global_transit_cache.get(cache_key)
        if cached_entry:
            vehicles, updated_at = cached_entry
            meta = APIResponseMetadata(
                data_source="LIVE_CTA_API" if self.is_configured else "GTFS_SCHEDULE_DERIVED",
                is_live_api_active=self.is_configured,
                last_updated=updated_at,
                cached=True,
                message="Served from RouteRanker memory cache"
            )
            return vehicles, meta

        # Attempt Live CTA Bus Tracker API if key configured
        if self.is_configured:
            live_vehicles = self._fetch_live_vehicles(route_id)
            if live_vehicles is not None:
                updated_at = global_transit_cache.set(cache_key, live_vehicles)
                meta = APIResponseMetadata(
                    data_source="LIVE_CTA_API",
                    is_live_api_active=True,
                    last_updated=updated_at,
                    cached=False,
                    message="Live telemetry fetched from official CTA Bus Tracker API v2"
                )
                return live_vehicles, meta

        # Fallback to verified GTFS schedule trajectory simulation
        sim_vehicles = gtfs_simulator.get_simulated_buses(route_id)
        updated_at = global_transit_cache.set(cache_key, sim_vehicles, ttl=20)
        meta = APIResponseMetadata(
            data_source="GTFS_SCHEDULE_DERIVED",
            is_live_api_active=False,
            last_updated=updated_at,
            cached=False,
            message="Schedule-derived vehicle telemetry (CTA Bus API key not configured or returned error)"
        )
        return sim_vehicles, meta

    def get_arrival_predictions(self, stop_id: str) -> Tuple[List[BusArrivalPrediction], APIResponseMetadata]:
        cache_key = f"bus_pred_{stop_id}"
        cached_entry = global_transit_cache.get(cache_key)
        if cached_entry:
            preds, updated_at = cached_entry
            meta = APIResponseMetadata(
                data_source="LIVE_CTA_API" if self.is_configured else "GTFS_SCHEDULE_DERIVED",
                is_live_api_active=self.is_configured,
                last_updated=updated_at,
                cached=True
            )
            return preds, meta

        if self.is_configured:
            live_preds = self._fetch_live_predictions(stop_id)
            if live_preds is not None:
                updated_at = global_transit_cache.set(cache_key, live_preds)
                meta = APIResponseMetadata(
                    data_source="LIVE_CTA_API",
                    is_live_api_active=True,
                    last_updated=updated_at,
                    cached=False,
                    message="Official CTA Bus Tracker stop predictions"
                )
                return live_preds, meta

        sim_preds = gtfs_simulator.get_simulated_bus_predictions(stop_id)
        updated_at = global_transit_cache.set(cache_key, sim_preds, ttl=30)
        meta = APIResponseMetadata(
            data_source="GTFS_SCHEDULE_DERIVED",
            is_live_api_active=False,
            last_updated=updated_at,
            cached=False,
            message="Timetable-derived stop arrival countdown"
        )
        return sim_preds, meta

    def _fetch_live_vehicles(self, route_id: str = None) -> List[BusVehiclePosition]:
        params = {
            "key": self.api_key,
            "format": "json"
        }
        if route_id:
            params["rt"] = str(route_id)
        else:
            params["rt"] = "79,9,66,4,49,X9,22,8"  # Top busy CTA corridors

        url = f"{BUS_API_BASE}getvehicles?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=7) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                bt_resp = data.get("bustime-response", {})
                
                if "error" in bt_resp:
                    logger.warning(f"CTA Bus API returned error: {bt_resp['error']}")
                    return None
                    
                vehicles_raw = bt_resp.get("vehicle", [])
                vehicles = []
                for v in vehicles_raw:
                    vehicles.append(BusVehiclePosition(
                        vehicle_id=str(v.get("vid")),
                        route_id=str(v.get("rt")),
                        destination=str(v.get("des")),
                        latitude=float(v.get("lat")),
                        longitude=float(v.get("lon")),
                        heading=int(v.get("hdg", 0)),
                        speed_mph=float(v.get("spd", 0.0)),
                        is_delayed=bool(v.get("dly", False)),
                        pattern_id=str(v.get("pid", "")),
                        timestamp=str(v.get("tmstmp"))
                    ))
                return vehicles
        except Exception as e:
            logger.warning(f"Error calling live CTA Bus API: {e}")
            return None

    def _fetch_live_predictions(self, stop_id: str) -> List[BusArrivalPrediction]:
        params = {
            "key": self.api_key,
            "stpid": str(stop_id),
            "format": "json"
        }
        url = f"{BUS_API_BASE}getpredictions?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=7) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                bt_resp = data.get("bustime-response", {})
                if "error" in bt_resp:
                    return None
                    
                preds_raw = bt_resp.get("prd", [])
                predictions = []
                for p in preds_raw:
                    # Parse countdown
                    prdtm_str = p.get("prdtm", "")
                    mins = 0
                    try:
                        prdtm_dt = datetime.strptime(prdtm_str, "%Y%m%d %H:%M")
                        now_dt = datetime.now()
                        mins = max(0, int((prdtm_dt - now_dt).total_seconds() / 60))
                    except:
                        pass
                        
                    predictions.append(BusArrivalPrediction(
                        prediction_type=str(p.get("typ", "A")),
                        stop_id=str(p.get("stpid")),
                        stop_name=str(p.get("stpnm")),
                        vehicle_id=str(p.get("vid")),
                        route_id=str(p.get("rt")),
                        destination=str(p.get("des")),
                        predicted_arrival_time=prdtm_str,
                        countdown_minutes=mins,
                        is_delayed=bool(p.get("dly", False))
                    ))
                return predictions
        except Exception as e:
            logger.warning(f"Error calling CTA Bus predictions API: {e}")
            return None

cta_bus_client = CTABusClient()

