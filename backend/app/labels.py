"""Visible labels and units (spec 9.13.3, 9.16.1). Every endpoint uses these; the frontend shows them as given."""
import re

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


def prose(text: str) -> str:
    """Screen typography for stored text: ">=" -> "\u2265", "<=" -> "\u2264", and a number range "13-60" -> "13\u201360".
    ISO dates such as 2026-03-31 are left alone (a range is two numbers with no other hyphen around them)."""
    text = text.replace(">=", "\u2265").replace("<=", "\u2264")
    return re.sub(r"(?<![\d-])(\d+)-(\d+)(?![\d-])", "\\1\u2013\\2", text)


def reason_words(code: str | None) -> str | None:
    return None if code is None else REASON_WORDS.get(code, code.replace("_", " "))


REPLAY_MODE, REPLAY_MODE_LABEL = "historical_replay", "Historical replay"


def envelope(version: dict, cutoff: dict, **body) -> dict:
    """Every response says which data version, which mode, and which cutoff it describes. A cutoff that came from a
    replay session makes the mode "Historical replay" (spec 9.13.1)."""
    replay = isinstance(cutoff, dict) and cutoff.get("replay")
    mode, label = (REPLAY_MODE, REPLAY_MODE_LABEL) if replay else (MODE, MODE_LABEL)
    return {"data_version": version["data_version"], "mode": mode, "mode_label": label, "cutoff": cutoff,
            **{k: v for k, v in body.items() if k != "mode_label"}}
