"""Visible labels and units (spec 9.13.3, 9.16.1). Every endpoint uses these; the frontend shows them as given."""
MODE = "historical_analysis"
MODE_LABEL = "Historical analysis"
LABELS = {  # spec 9.13.3 provenance labels
    "recorded_rides": "Recorded rides",
    "scheduled_trips": "Scheduled trips",
    "scheduled_hours": "Scheduled trip-hours",
    "predicted_rides": "Predicted rides",
    "historical_replay": "Historical replay",
    "scenario": "Scenario assumption",
}
UNITS = {  # spec 9.16.1; ratios keep the word "scheduled"
    "rides": "rides/day",
    "scheduled_trips": "scheduled trips/day",
    "scheduled_service_hours": "scheduled trip-hours/day",
    "rides_per_scheduled_trip": "rides per scheduled trip",
    "rides_per_scheduled_hour": "rides per scheduled hour",
}

# Stage 2's reason codes (analytics/reconstruction/matching.py) in plain words for the screens. Endpoints send the
# words as `reason` and the code as `reason_code`; an unknown code is shown as words, never hidden.
REASON_WORDS = {
    "no_snapshot_for_date": "no timetable applies to this date",
    "route_absent_from_selected_snapshot": "the route is not in the timetable that applies on this date",
    "route_in_snapshot_no_active_trips": "the route is in the timetable but has no trips on this date",
    "no_ridership_record": "service was scheduled but no ridership was recorded",
}


def reason_words(code: str | None) -> str | None:
    return None if code is None else REASON_WORDS.get(code, code.replace("_", " "))


def envelope(version: dict, cutoff: dict, **body) -> dict:
    """Every response says which data version, which mode, and which cutoff it describes."""
    return {"data_version": version["data_version"], "mode": MODE, "mode_label": MODE_LABEL, "cutoff": cutoff, **body}
