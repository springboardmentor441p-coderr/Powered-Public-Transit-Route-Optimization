"""Stage 6c: the texts the screens show as sent (labels, notes, caveats, reasons) are plain words.

No spec section numbers ("(spec 9.12)") and no API field names ("routes_reporting") in visible text. Spec
references travel in their own `spec_reference` field, shown only under "How was this number made?".
"""
from __future__ import annotations

import re

import pytest

VISIBLE = {"caveat", "caveats", "meaning", "note", "total_note", "label", "gate_label", "interpretation", "reason",
           "route_values_note", "groups_note", "comparable_note", "k_rule", "k_table", "mode_label",
           "numerator_label", "denominator_label", "unit", "daytype_label", "name", "kind_label", "test_status",
           "target_label", "metric_label", "selection_note", "basis_label", "rank_note"}
NOT_TEXT = {"name"}  # "name" is also an internal period key; it is checked only where it is a group name
SPEC = re.compile(r"\bspec\s+\d", re.I)
FIELD = re.compile(r"\b[a-z]+_[a-z0-9_]+\b")

REQUESTS = [
    ("/api/network/trend", {}),
    ("/api/data/coverage", {}),
    ("/api/routes", {}),
    ("/api/routes/22/history", {}),
    ("/api/routes/169/history", {}),                      # scheduled days without a record (Stage 2 reason)
    ("/api/routes/1001/history", {}),                     # rides without any scheduled service
    ("/api/rankings", {"metric": "rides_per_scheduled_hour", "daytype": "W"}),
    ("/api/rankings", {"metric": "observed_daily_demand", "daytype": "A", "min_days": 8}),
    ("/api/rankings", {"metric": "rides_per_scheduled_trip", "daytype": "U", "period": "development"}),
    ("/api/rankings", {"metric": "route_overlap_review"}),
    ("/api/routes/compare", {"routes": "49,X49", "daytype": "W"}),
    ("/api/route-groups", {}),
    ("/api/map/lines", {}),
    ("/api/models/summary", {}),
    ("/api/routes/compare", {"routes": "10,22", "same_days": "true"}),
]


def visible_texts(obj, key=None, in_groups=False):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from visible_texts(v, k, in_groups or k == "groups")
    elif isinstance(obj, list):
        for v in obj:
            yield from visible_texts(v, key, in_groups)
    elif isinstance(obj, str) and key in VISIBLE and (key not in NOT_TEXT or in_groups):
        yield key, obj


@pytest.mark.parametrize("url, params", REQUESTS)
def test_visible_texts_have_no_spec_numbers_or_field_names(client, url, params):
    body = client.get(url, params=params)
    assert body.status_code == 200, body.text
    texts = list(visible_texts(body.json()))
    assert texts, url
    for key, text in texts:
        assert not SPEC.search(text), (url, key, text)
        assert not FIELD.search(text), (url, key, text)


def test_spec_references_and_part_labels_travel_separately(client):
    r = client.get("/api/rankings", params={"metric": "rides_per_scheduled_hour", "daytype": "W"}).json()
    assert r["metric"]["spec_reference"] == "spec 9.12"
    assert (r["metric"]["numerator_label"], r["metric"]["denominator_label"]) == ("recorded rides", "scheduled trip-hours")
    assert r["period"]["label"] == "Full matched window"
    o = client.get("/api/rankings", params={"metric": "route_overlap_review"}).json()
    assert o["metric"]["spec_reference"] == "spec 9.12"
