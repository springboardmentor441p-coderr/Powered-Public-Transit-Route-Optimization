"""
RouteRanker: Phase 10 Smart Service Recommendation Engine & Scenario Simulator
Transportation Decision-Support System for Chicago Transit Authority (CTA) Service Planners.
Features:
- Service frequency scenario simulation (adjusting scheduled trips from T_current to T_proposed).
- Headway reduction, seat capacity changes, and passenger-to-trip loading ratios.
- Explainable, data-backed operational recommendations based on historical and forecasted demand.
- Transparent disclosures: labels nominal capacity vs actual APC occupancy.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from ml.forecasting.demand_forecast_service import demand_forecast_service
from ml.forecasting.crowd_classification_service import crowd_classification_service

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
PHASE4_DIR = os.path.join(PROCESSED_DIR, "phase4")

# Typical single-day scheduled trips from official CTA GTFS schedules
GTFS_BASELINE_WEEKDAY_TRIPS = {
    "79": 148,
    "9": 144,
    "66": 148,
    "4": 110,
    "49": 120,
    "X9": 50,
}

class SmartRecommendationEngine:
    def __init__(self):
        self._routes_df = None
        self._bus_history = None

    def _load_data(self):
        if self._routes_df is None:
            r_path = os.path.join(PROCESSED_DIR, "cleaned_gtfs_routes.csv")
            self._routes_df = pd.read_csv(r_path)
        if self._bus_history is None:
            bh_path = os.path.join(PHASE4_DIR, "cta_daily_bus_route_forecasting_ready.csv")
            self._bus_history = pd.read_csv(bh_path, low_memory=False)

    def simulate_frequency_scenario(self, route_id: str, proposed_trips: int) -> Dict[str, Any]:
        """
        Simulates changing daily scheduled trips on a CTA corridor.
        Evaluates headway impact, nominal vehicle capacity, and demand loading intensity.
        """
        self._load_data()
        r_str = str(route_id).upper()
        
        # 1. Lookup Route Context
        route_meta = self._routes_df[self._routes_df["route_id"].astype(str) == r_str]
        route_name = route_meta.iloc[0]["route_long_name"] if not route_meta.empty else f"Route {r_str}"
        
        # 2. Historical & Forecasted Passenger Demand
        sub_hist = self._bus_history[self._bus_history["route_id"].astype(str) == r_str]
        hist_mean_demand = int(sub_hist["rides"].mean()) if not sub_hist.empty else 8500
        
        # Fetch route forecast
        fc_res = demand_forecast_service.get_route_forecast(r_str, horizon_days=7)
        projected_next_weekday = hist_mean_demand
        if "forecast" in fc_res and fc_res["forecast"]:
            for f in fc_res["forecast"]:
                if f.get("day_of_week") not in ["Saturday", "Sunday"]:
                    projected_next_weekday = f["predicted_rides"]
                    break

        # 3. Baseline Daily Scheduled Trips from GTFS
        baseline_trips = GTFS_BASELINE_WEEKDAY_TRIPS.get(r_str, 120)
        
        # 4. Operational Computations (Standard 18-hour daily span: 6:00 AM to 12:00 AM)
        service_hours = 18.0
        service_minutes = service_hours * 60.0
        
        curr_headway_min = round(service_minutes / max(1, baseline_trips), 1)
        prop_headway_min = round(service_minutes / max(1, proposed_trips), 1)
        headway_change_min = round(prop_headway_min - curr_headway_min, 1)
        
        # Standard 40ft low-floor CTA coach nominal capacity assumption: 40 seated + 20 standing = 60 spaces per vehicle trip
        bus_nominal_capacity = 60
        curr_nominal_capacity = baseline_trips * bus_nominal_capacity
        prop_nominal_capacity = proposed_trips * bus_nominal_capacity
        nominal_capacity_delta = prop_nominal_capacity - curr_nominal_capacity
        
        # Average passenger boardings per scheduled daily trip
        curr_boardings_per_trip = round(projected_next_weekday / max(1, baseline_trips), 1)
        prop_boardings_per_trip = round(projected_next_weekday / max(1, proposed_trips), 1)
        
        # Estimated Trip-Aggregate Boarding Ratio (daily boardings per trip relative to nominal vehicle capacity)
        # Note: This is an aggregate ratio, NOT instantaneous onboard occupancy
        curr_boarding_ratio = round((curr_boardings_per_trip / bus_nominal_capacity) * 100, 1)
        prop_boarding_ratio = round((prop_boardings_per_trip / bus_nominal_capacity) * 100, 1)
        
        # 5. Demand Classification
        demand_class = crowd_classification_service.classify_route_demand(r_str, projected_next_weekday)
        
        # 6. Generate Data-Driven Explainable Recommendations
        recommendations = []
        trip_diff = proposed_trips - baseline_trips
        
        if trip_diff > 0:
            if curr_boardings_per_trip > 75:
                recommendations.append({
                    "category": "Service Frequency Expansion",
                    "priority": "HIGH",
                    "title": "Alleviate Corridor Passenger Volume Density",
                    "rationale": (
                        f"Route {r_str} records an estimated ~{curr_boardings_per_trip} average boardings per scheduled trip across its full route length, "
                        f"reflecting high corridor daily volume against nominal vehicle capacity ({bus_nominal_capacity} passengers). "
                        f"Adding +{trip_diff} daily trips ({baseline_trips} -> {proposed_trips} trips) shortens scheduled average headway from {curr_headway_min}m to {prop_headway_min}m, "
                        f"distributing boardings to ~{prop_boardings_per_trip} boardings/trip (lowering nominal boarding ratio from {curr_boarding_ratio}% to {prop_boarding_ratio}%). "
                        f"Actual crowding reduction depends on peak-hour run dispatching and stop-by-stop passenger turnover."
                    )
                })
            else:
                recommendations.append({
                    "category": "Capacity Enhancement",
                    "priority": "MEDIUM",
                    "title": "Moderate Capacity Enhancement",
                    "rationale": (
                        f"Adding +{trip_diff} trips expands corridor nominal scheduled capacity by +{nominal_capacity_delta:,} spaces. "
                        f"Current demand ({projected_next_weekday:,} boardings/day) operates within standard service limits. "
                        f"Target additional frequency specifically during morning (7-9 AM) and evening (4-6 PM) rush peaks."
                    )
                })
        elif trip_diff < 0:
            if prop_boardings_per_trip > 75:
                recommendations.append({
                    "category": "Service Cut Warning",
                    "priority": "CRITICAL",
                    "title": "Service Reduction Likely to Increase Peak Crowding Risk",
                    "rationale": (
                        f"Cutting {abs(trip_diff)} trips stretches average headway from {curr_headway_min}m to {prop_headway_min}m. "
                        f"This increases average passenger load intensity to ~{prop_boardings_per_trip} boardings/trip ({prop_boarding_ratio}% nominal boarding ratio), "
                        f"heightening the risk of platform delays and localized peak-period bunching."
                    )
                })
            else:
                recommendations.append({
                    "category": "Headway Rationalization",
                    "priority": "LOW",
                    "title": "Off-Peak Frequency Adjustment Feasible",
                    "rationale": (
                        f"Lower off-peak boarding volume indicates trip reduction is feasible if confined strictly to late evening hours (after 9:00 PM)."
                    )
                })
        else:
            recommendations.append({
                "category": "Status Quo",
                "priority": "NEUTRAL",
                "title": "Current Timetable Retained",
                "rationale": (
                    f"Route {r_str} scheduled frequency matches baseline operating parameters. "
                    f"Average headway remains {curr_headway_min} minutes."
                )
            })

        primary_rec = recommendations[0]

        return {
            "route_id": r_str,
            "route_name": route_name,
            "route": {
                "route_id": r_str,
                "route_long_name": route_name
            },
            "demand_classification": demand_class,
            "baseline": {
                "scheduled_daily_trips": baseline_trips,
                "baseline_headway_minutes": curr_headway_min,
                "baseline_daily_capacity": curr_nominal_capacity,
                "baseline_boardings_per_trip": curr_boardings_per_trip,
                "baseline_boarding_ratio": curr_boarding_ratio
            },
            "simulation": {
                "proposed_trips": proposed_trips,
                "operating_headway_minutes": prop_headway_min,
                "total_daily_capacity": prop_nominal_capacity,
                "estimated_boardings_per_trip": prop_boardings_per_trip,
                "estimated_boarding_ratio": prop_boarding_ratio
            },
            "impact": {
                "trips_delta": trip_diff,
                "headway_minutes_delta": headway_change_min,
                "capacity_delta": nominal_capacity_delta,
                "boarding_ratio_delta": round(prop_boarding_ratio - curr_boarding_ratio, 1)
            },
            "recommendation": {
                "title": primary_rec.get("title"),
                "action_category": primary_rec.get("category"),
                "explanation": primary_rec.get("rationale")
            },
            "simulation_inputs": {
                "baseline_scheduled_trips": baseline_trips,
                "proposed_trips": proposed_trips,
                "trips_delta": trip_diff,
                "trips_percent_change": round((trip_diff / max(1, baseline_trips)) * 100, 1),
                "assumed_vehicle_capacity": bus_nominal_capacity
            },
            "metrics_comparison": {
                "headway": {
                    "current_minutes": curr_headway_min,
                    "proposed_minutes": prop_headway_min,
                    "delta_minutes": headway_change_min
                },
                "nominal_scheduled_capacity": {
                    "current_nominal": curr_nominal_capacity,
                    "proposed_nominal": prop_nominal_capacity,
                    "delta_capacity": nominal_capacity_delta
                },
                "passenger_loading_intensity": {
                    "projected_daily_demand": projected_next_weekday,
                    "current_boardings_per_trip": curr_boardings_per_trip,
                    "proposed_boardings_per_trip": prop_boardings_per_trip,
                    "current_boarding_ratio_pct": curr_boarding_ratio,
                    "proposed_boarding_ratio_pct": prop_boarding_ratio
                }
            },
            "recommendations": recommendations,
            "occupancy_disclaimer": (
                "Nominal Daily Scheduled Capacity is calculated as scheduled trips multiplied by assumed nominal coach capacity (60 passengers). "
                "Boardings per scheduled trip represents cumulative passenger boardings divided by daily trips across the full corridor route; "
                "it does NOT equal instantaneous onboard passenger occupancy. Actual onboard crowding is spatio-temporal and requires stop-level APC sensor data."
            ),
            "assumptions": [
                "Headways assume an 18-hour operating service window (6:00 AM to 12:00 AM).",
                "Nominal standard 40-foot CTA bus capacity is benchmarked at 60 spaces (40 seated + 20 standing).",
                "Passenger demand reflects next-weekday forecast generated by RouteRanker ML models.",
                "Corridor models represent aggregate scheduled trips; actual dispatching schedules distribute trips to morning/evening peak hours."
            ]
        }

smart_recommendation_engine = SmartRecommendationEngine()
