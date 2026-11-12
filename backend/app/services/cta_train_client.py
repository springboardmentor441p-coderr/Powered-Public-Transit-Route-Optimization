"""
RouteRanker: CTA Train Tracker API Client
Integrates official CTA Train Tracker API v1.0:
http://lapi.transitchicago.com/api/1.0/
Endpoints: ttpositions.aspx, ttarrivals.aspx
Handles line positions, station arrival predictions, rate-limits, and fallbacks.
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
    TrainPosition, TrainArrivalPrediction, APIResponseMetadata
)
from backend.app.services.transit_cache import global_transit_cache
from backend.app.services.gtfs_simulation_fallback import gtfs_simulator

load_dotenv()
logger = logging.getLogger(__name__)

TRAIN_API_BASE = "http://lapi.transitchicago.com/api/1.0/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RouteRanker-Transit/1.0"

class CTATrainClient:
    def __init__(self):
        self.api_key = os.getenv("CTA_TRAIN_API_KEY", "").strip()
        self.is_configured = bool(self.api_key and not self.api_key.startswith("YOUR_"))

    def get_train_positions(self, line_name: str = None) -> Tuple[List[TrainPosition], APIResponseMetadata]:
        cache_key = f"train_pos_{line_name or 'all'}"
        cached_entry = global_transit_cache.get(cache_key)
        if cached_entry:
            trains, updated_at = cached_entry
            meta = APIResponseMetadata(
                data_source="LIVE_CTA_API" if self.is_configured else "GTFS_SCHEDULE_DERIVED",
                is_live_api_active=self.is_configured,
                last_updated=updated_at,
                cached=True,
                message="Served from RouteRanker memory cache"
            )
            return trains, meta

        if self.is_configured:
            live_trains = self._fetch_live_trains(line_name)
            if live_trains is not None:
                updated_at = global_transit_cache.set(cache_key, live_trains)
                meta = APIResponseMetadata(
                    data_source="LIVE_CTA_API",
                    is_live_api_active=True,
                    last_updated=updated_at,
                    cached=False,
                    message="Live train telemetry fetched from official CTA Train Tracker API"
                )
                return live_trains, meta

        sim_trains = gtfs_simulator.get_simulated_trains(line_name)
        updated_at = global_transit_cache.set(cache_key, sim_trains, ttl=20)
        meta = APIResponseMetadata(
            data_source="GTFS_SCHEDULE_DERIVED",
            is_live_api_active=False,
            last_updated=updated_at,
            cached=False,
            message="Schedule-derived rail telemetry (CTA Train API key not configured or returned error)"
        )
        return sim_trains, meta

    def get_station_arrivals(self, station_id: str) -> Tuple[List[TrainArrivalPrediction], APIResponseMetadata]:
        cache_key = f"train_arr_{station_id}"
        cached_entry = global_transit_cache.get(cache_key)
        if cached_entry:
            arrivals, updated_at = cached_entry
            meta = APIResponseMetadata(
                data_source="LIVE_CTA_API" if self.is_configured else "GTFS_SCHEDULE_DERIVED",
                is_live_api_active=self.is_configured,
                last_updated=updated_at,
                cached=True
            )
            return arrivals, meta

        if self.is_configured:
            live_arr = self._fetch_live_arrivals(station_id)
            if live_arr is not None:
                updated_at = global_transit_cache.set(cache_key, live_arr)
                meta = APIResponseMetadata(
                    data_source="LIVE_CTA_API",
                    is_live_api_active=True,
                    last_updated=updated_at,
                    cached=False,
                    message="Official CTA Train Tracker station arrivals"
                )
                return live_arr, meta

        sim_arr = gtfs_simulator.get_simulated_train_predictions(station_id)
        updated_at = global_transit_cache.set(cache_key, sim_arr, ttl=30)
        meta = APIResponseMetadata(
            data_source="GTFS_SCHEDULE_DERIVED",
            is_live_api_active=False,
            last_updated=updated_at,
            cached=False,
            message="Timetable-derived station arrival countdown"
        )
        return sim_arr, meta

    def _fetch_live_trains(self, line_name: str = None) -> List[TrainPosition]:
        # Mapping line names to CTA query codes
        line_codes = {
            "red": "red", "blue": "blue", "brown": "brn", "brn": "brn",
            "green": "g", "g": "g", "orange": "org", "org": "org",
            "purple": "p", "p": "p", "pink": "pnk", "pnk": "pnk", "yellow": "y", "y": "y"
        }
        target_code = line_codes.get(str(line_name).lower(), "red,blue,brn,g,org,p,pnk,y")
        
        params = {
            "key": self.api_key,
            "rt": target_code,
            "outputType": "JSON"
        }
        url = f"{TRAIN_API_BASE}ttpositions.aspx?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=7) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ctatt = data.get("ctatt", {})
                if ctatt.get("errNm"):
                    logger.warning(f"CTA Train API returned error: {ctatt.get('errNm')}")
                    return None
                    
                routes_raw = ctatt.get("route", [])
                trains = []
                for r in routes_raw:
                    line_n = r.get("@name", "Train")
                    trains_raw = r.get("train", [])
                    if isinstance(trains_raw, dict):
                        trains_raw = [trains_raw]
                    for t in trains_raw:
                        trains.append(TrainPosition(
                            run_number=str(t.get("rn")),
                            line_name=line_n,
                            destination_name=str(t.get("destNm")),
                            latitude=float(t.get("lat")),
                            longitude=float(t.get("lon")),
                            heading=int(t.get("heading", 0)),
                            next_station_id=str(t.get("nextStaId")),
                            next_station_name=str(t.get("nextStaNm")),
                            is_approaching=(str(t.get("isApp")) == "1"),
                            is_delayed=(str(t.get("isDly")) == "1"),
                            timestamp=str(t.get("prdt"))
                        ))
                return trains
        except Exception as e:
            logger.warning(f"Error calling CTA Train Positions API: {e}")
            return None

    def _fetch_live_arrivals(self, station_id: str) -> List[TrainArrivalPrediction]:
        params = {
            "key": self.api_key,
            "mapid": str(station_id),
            "outputType": "JSON"
        }
        url = f"{TRAIN_API_BASE}ttarrivals.aspx?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=7) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ctatt = data.get("ctatt", {})
                if ctatt.get("errNm"):
                    return None
                    
                eta_list = ctatt.get("eta", [])
                if isinstance(eta_list, dict):
                    eta_list = [eta_list]
                    
                arrivals = []
                for e in eta_list:
                    arr_t = e.get("arrT", "")
                    mins = 0
                    try:
                        arr_dt = datetime.strptime(arr_t, "%Y-%m-%dT%H:%M:%S")
                        now_dt = datetime.now()
                        mins = max(0, int((arr_dt - now_dt).total_seconds() / 60))
                    except:
                        pass
                        
                    arrivals.append(TrainArrivalPrediction(
                        station_id=str(e.get("staId")),
                        stop_id=str(e.get("stpId")),
                        station_name=str(e.get("staNm")),
                        platform_description=str(e.get("stpDe")),
                        run_number=str(e.get("rn")),
                        line_name=str(e.get("rt")),
                        destination_name=str(e.get("destNm")),
                        arrival_time=arr_t,
                        countdown_minutes=mins,
                        is_approaching=(str(e.get("isApp")) == "1"),
                        is_delayed=(str(e.get("isDly")) == "1")
                    ))
                return arrivals
        except Exception as e:
            logger.warning(f"Error calling CTA Train Arrivals API: {e}")
            return None

cta_train_client = CTATrainClient()

