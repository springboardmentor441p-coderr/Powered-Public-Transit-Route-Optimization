"""
Conditional arithmetic service scenario calculator (Spec Section 9.15).
Preserves baseline predictions/observations, applies explicit trip/demand changes,
and surfaces duration & causal assumptions transparently.
"""

def calculate_service_scenario(
    baseline_rides: float,
    baseline_trips: int,
    baseline_hours: float | None,
    proposed_trips: int,
    demand_multiplier: float = 1.0,
    assumed_trip_duration_minutes: float | None = None,
) -> dict:
    if proposed_trips < 0 or baseline_trips <= 0:
        raise ValueError("Trips must be non-negative and baseline trips must be positive.")

    if assumed_trip_duration_minutes is None:
        if baseline_hours is not None and baseline_trips > 0:
            assumed_trip_duration_minutes = round((baseline_hours * 60.0) / baseline_trips, 2)
        else:
            assumed_trip_duration_minutes = 40.0

    scenario_rides = round(baseline_rides * demand_multiplier, 2)
    scenario_hours = round((proposed_trips * assumed_trip_duration_minutes) / 60.0, 2)

    base_rides_per_trip = round(baseline_rides / baseline_trips, 2)
    scen_rides_per_trip = round(scenario_rides / proposed_trips, 2) if proposed_trips > 0 else None

    base_rides_per_hour = round(baseline_rides / baseline_hours, 2) if baseline_hours and baseline_hours > 0 else None
    scen_rides_per_hour = round(scenario_rides / scenario_hours, 2) if scenario_hours > 0 else None

    return {
        "baseline": {
            "rides": round(baseline_rides, 2),
            "scheduled_trips": baseline_trips,
            "scheduled_service_hours": round(baseline_hours, 2) if baseline_hours else None,
            "rides_per_scheduled_trip": base_rides_per_trip,
            "rides_per_scheduled_hour": base_rides_per_hour,
        },
        "scenario": {
            "rides": scenario_rides,
            "scheduled_trips": proposed_trips,
            "scheduled_service_hours": scenario_hours,
            "rides_per_scheduled_trip": scen_rides_per_trip,
            "rides_per_scheduled_hour": scen_rides_per_hour,
        },
        "deltas": {
            "trips_delta": proposed_trips - baseline_trips,
            "trips_pct_change": round(((proposed_trips - baseline_trips) / baseline_trips) * 100.0, 2),
            "rides_per_trip_delta": round(scen_rides_per_trip - base_rides_per_trip, 2) if scen_rides_per_trip is not None else None,
        },
        "assumptions": {
            "assumed_mean_duration_minutes": assumed_trip_duration_minutes,
            "demand_multiplier": demand_multiplier,
            "note": "Conditional arithmetic under fixed duration and explicit demand assumption; does not establish vehicle/crew feasibility or causal ridership elasticity.",
        },
    }
