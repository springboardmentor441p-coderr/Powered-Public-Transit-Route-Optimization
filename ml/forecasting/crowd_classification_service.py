"""
RouteRanker: Demand and Crowd Level Classification Service
Applies statistically grounded, transparent threshold tiers derived from historical CTA boarding distributions.
Classifies passenger demand into:
- Low Demand
- Moderate Demand
- High Demand
- Potentially Overcrowded
Enforces strict transparency: results represent demand intensity classifications based on farebox/turnstile
counts, NOT real-time passenger sensor occupancy.
"""

from typing import Dict, Any, List

class CrowdClassificationService:
    def __init__(self):
        # Empirical System Daily Ridership Thresholds (Post-pandemic baseline)
        self.system_thresholds = {
            "low_max": 650000,        # < 650k (Sundays/Holidays)
            "moderate_max": 950000,   # 650k - 950k (Saturdays & light weekdays)
            "high_max": 1150000,      # 950k - 1.15M (Regular busy weekdays)
            # > 1.15M: Potentially Overcrowded (Major festival / Cubs / surge weekdays)
        }
        
        # Route-level Daily Boarding Thresholds
        self.bus_route_thresholds = {
            "low_max": 5000,
            "moderate_max": 12000,
            "high_max": 16500
        }
        
        # Station-level Daily Turnstile Entry Thresholds
        self.rail_station_thresholds = {
            "low_max": 2500,
            "moderate_max": 6500,
            "high_max": 10000
        }

    def classify_system_demand(self, total_rides: int) -> Dict[str, Any]:
        if total_rides < self.system_thresholds["low_max"]:
            category = "Low Demand"
            badge_color = "teal"
            desc = "Light passenger activity; system operating well below baseline capacity."
        elif total_rides < self.system_thresholds["moderate_max"]:
            category = "Moderate Demand"
            badge_color = "blue"
            desc = "Moderate transit activity typical of weekend or intermediate service days."
        elif total_rides < self.system_thresholds["high_max"]:
            category = "High Demand"
            badge_color = "amber"
            desc = "High commuter passenger demand across major corridors."
        else:
            category = "High Daily System Volume (Peak Overcrowding Risk)"
            badge_color = "rose"
            desc = "Peak network demand surge; key transit lines may experience peak-hour crowding."

        return {
            "daily_demand": total_rides,
            "classification": category,
            "badge_color": badge_color,
            "description": desc,
            "thresholds": self.system_thresholds,
            "methodology_note": (
                "Demand classifications are derived from empirical historical boarding percentiles. "
                "Classifications indicate aggregate daily passenger volume and do NOT represent "
                "instantaneous onboard sensor occupancy or trip-level overcrowding."
            )
        }

    def classify_route_demand(self, route_id: str, daily_boardings: int) -> Dict[str, Any]:
        if daily_boardings < self.bus_route_thresholds["low_max"]:
            cat = "Low Demand"
            color = "teal"
            action = "Routine monitoring; scheduled capacity exceeds current demand."
        elif daily_boardings < self.bus_route_thresholds["moderate_max"]:
            cat = "Moderate Demand"
            color = "blue"
            action = "Balanced service headways recommended."
        elif daily_boardings < self.bus_route_thresholds["high_max"]:
            cat = "High Demand"
            color = "amber"
            action = "High corridor passenger volumes; maintain frequent peak headways."
        else:
            cat = "High Daily Corridor Volume (Peak Overcrowding Risk)"
            color = "rose"
            action = "Corridor approaching upper daily capacity tier; monitor peak-period load factors."

        return {
            "route_id": str(route_id),
            "projected_daily_boardings": daily_boardings,
            "classification": cat,
            "badge_color": color,
            "recommended_action": action,
            "thresholds": self.bus_route_thresholds,
            "methodology_note": (
                "Classification is an aggregate daily demand tier based on historical CTA boardings. "
                "Actual passenger crowding is spatio-temporal and depends on scheduled bus frequency, "
                "dispatch headways, and vehicle capacity (standard 60-passenger capacity)."
            )
        }

    def classify_station_demand(self, station_id: str, daily_entries: int) -> Dict[str, Any]:
        if daily_entries < self.rail_station_thresholds["low_max"]:
            cat = "Low Demand"
            color = "teal"
        elif daily_entries < self.rail_station_thresholds["moderate_max"]:
            cat = "Moderate Demand"
            color = "blue"
        elif daily_entries < self.rail_station_thresholds["high_max"]:
            cat = "High Demand"
            color = "amber"
        else:
            cat = "High Daily Station Volume (Peak Overcrowding Risk)"
            color = "rose"

        return {
            "station_id": str(station_id),
            "projected_daily_entries": daily_entries,
            "classification": cat,
            "badge_color": color,
            "thresholds": self.rail_station_thresholds,
            "methodology_note": (
                "Station entries represent daily turnstile volume, not instantaneous platform crowd density."
            )
        }

crowd_classification_service = CrowdClassificationService()

