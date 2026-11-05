"""Data modes and evidence labels. Every number shown to a user carries one of these provenance tags."""
MODES = {
    "A": dict(label="GTFS schedule analysis", short="Schedule only",
              note="Only the published timetable is analysed. There is no passenger information, so crowding and utilisation are NOT assessed."),
    "B": dict(label="GTFS + observed ridership", short="Observed ridership",
              note="Passenger counts supplied by the user are used. Results are only as good as that data's coverage and quality."),
    "C": dict(label="Estimated demand (proxy)", short="Estimated demand",
              note="No passenger counts. A relative demand INDEX is derived from stop locations. It is not passengers and is only comparable within a city."),
    "S": dict(label="Synthetic demonstration", short="Synthetic demo",
              note="GTFS-style data and ridership were GENERATED for testing and demonstration. Nothing here is a real-world observation."),
}
EVIDENCE = {
    "observed": "Observed data supplied by the user",
    "derived_schedule": "Metric derived from the published timetable",
    "model_prediction": "Machine-learning model prediction",
    "proxy_estimate": "Estimate from a documented proxy (not observed)",
    "synthetic_demo": "Synthetic demonstration data",
    "optimization_simulation": "Simulated outcome under stated assumptions (not measured)",
}
STATUS_LABEL = {"underutilized": "Potentially underutilized", "balanced": "Balanced service",
                "overcrowded": "Potential capacity pressure", "insufficient": "Insufficient evidence"}
INSUFFICIENT_MSG = "Insufficient data for a reliable recommendation."
INSUFFICIENT_FIX = ("Missing: observed passenger counts per route and hour (e.g. ticketing/APC data, columns route_id, day_type, hour, boardings). "
                    "Obtain them from the operator and upload them together with the GTFS feed.")

def evidence_for_mode(mode):
    return {"A": ["derived_schedule", "optimization_simulation"], "B": ["observed", "derived_schedule", "optimization_simulation"],
            "C": ["derived_schedule", "proxy_estimate", "optimization_simulation"],
            "S": ["synthetic_demo", "derived_schedule", "model_prediction", "optimization_simulation"]}[mode]
