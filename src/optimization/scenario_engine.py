"""
src/optimization/scenario_engine.py
RouteRanker Operational Scenario & Frequency Adjustment Engine

Simulates schedule and headway adjustments on bus routes using empirical transit
service elasticities (Pratt's frequency elasticity ε_freq ∈ [0.35, 0.50]):
- Estimates predicted boarding shift: ΔRidership = Baseline_Ridership * (1 + ε * ΔTrips/Base_Trips)
- Computes vehicle trip delta, marginal productivity, and operating cost impact.
"""

from typing import Dict, Any, Optional

# Empirical transit service elasticity (Simpson-Curtin / TCRP Report 95)
DEFAULT_FREQUENCY_ELASTICITY = 0.42
# Approximate CTA operational cost per bus revenue trip (operational estimate)
DEFAULT_COST_PER_TRIP = 85.0

def simulate_frequency_adjustment(
    route_id: str,
    base_weekday_rides: float,
    base_scheduled_trips: int,
    percent_trip_change: float,
    elasticity: float = DEFAULT_FREQUENCY_ELASTICITY,
    cost_per_trip: float = DEFAULT_COST_PER_TRIP
) -> Dict[str, Any]:
    """
    Simulates the impact of frequency expansion or headway reduction on a route.

    Args:
        route_id: Target bus route identifier.
        base_weekday_rides: Current average weekday passenger boardings.
        base_scheduled_trips: Current scheduled weekday trips.
        percent_trip_change: Percentage change in trips (e.g., +20 for +20%, -15 for -15%).
        elasticity: Demand elasticity with respect to service frequency.
        cost_per_trip: Estimated operating cost per trip.

    Returns:
        Structured scenario evaluation dictionary.
    """
    if base_scheduled_trips <= 0:
        base_scheduled_trips = 1

    trip_multiplier = 1.0 + (percent_trip_change / 100.0)
    simulated_trips = max(1, int(round(base_scheduled_trips * trip_multiplier)))
    actual_pct_change = ((simulated_trips - base_scheduled_trips) / base_scheduled_trips) * 100.0

    # Transit demand elasticity: % Δ demand = elasticity * % Δ frequency
    demand_multiplier = 1.0 + (elasticity * (actual_pct_change / 100.0))
    simulated_rides = max(0.0, round(base_weekday_rides * demand_multiplier, 1))

    delta_rides = round(simulated_rides - base_weekday_rides, 1)
    delta_trips = simulated_trips - base_scheduled_trips

    # Efficiency metrics
    base_productivity = round(base_weekday_rides / base_scheduled_trips, 2)
    simulated_productivity = round(simulated_rides / simulated_trips, 2)

    marginal_productivity = round(delta_rides / delta_trips, 2) if delta_trips != 0 else 0.0
    daily_cost_delta = round(delta_trips * cost_per_trip, 2)

    # Recommendations
    if percent_trip_change > 0:
        if simulated_productivity > 35:
            recommendation = "Highly viable expansion: Strong latent corridor demand absorbs added capacity."
        else:
            recommendation = "Moderate return: Added capacity yields diminishing marginal boardings."
    elif percent_trip_change < 0:
        recommendation = "Cost reduction scenario: Conserves operating budget with minor demand penalty."
    else:
        recommendation = "Neutral baseline: Current timetable preserved."

    return {
        "route_id": str(route_id),
        "percent_trip_change_requested": percent_trip_change,
        "base_scheduled_trips": base_scheduled_trips,
        "simulated_scheduled_trips": simulated_trips,
        "delta_trips": delta_trips,
        "base_weekday_rides": base_weekday_rides,
        "simulated_weekday_rides": simulated_rides,
        "delta_rides": delta_rides,
        "base_rides_per_trip": base_productivity,
        "simulated_rides_per_trip": simulated_productivity,
        "marginal_rides_per_added_trip": marginal_productivity,
        "daily_operating_cost_delta_usd": daily_cost_delta,
        "recommendation": recommendation
    }
