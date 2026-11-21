"""Stage 6b: GET /api/route-groups on the real data version in routeranker_test."""
from __future__ import annotations

import json
import math
import re
from datetime import date

import pandas as pd
import pytest

from backend.app.labels import prose
from backend.importer.import_data import REPO_ROOT

ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
UNGROUPED = {"10", "130", "1001", "128", "19"}


def test_summaries_equal_the_committed_stage5_summary(client):
    body = client.get("/api/route-groups").json()
    csv = pd.read_csv(REPO_ROOT / "reports" / "stage5_group_summary.csv").set_index("group")
    assert len(body["groups"]) == len(csv) == 2
    for g in body["groups"]:
        want = csv.loc[g["group_id"]]
        assert g["size"] == want["routes"] and g["name"] == want["name"]
        assert ", ".join(g["routes"]) == want["route_list"]
        for f in g["features"]:
            for s in ("median", "mean", "min", "max"):
                # the imported route_profiles.csv keeps 10 significant digits; the summary CSV was computed from
                # full-precision profiles and printed to 6 decimals -> equal within both roundings
                assert math.isclose(f[s], want[f"{f['feature']}_{s}"], rel_tol=1e-9, abs_tol=5e-7), \
                    (g["group_id"], f["feature"], s)
        for k, n in g["weekend_service"].items():
            assert n == int(want[k]), k


def test_names_sizes_caveats_and_ungrouped(client):
    body = client.get("/api/route-groups").json()
    assert body["available"] is True and body["method"]["k"] == 2
    assert sorted(g["size"] for g in body["groups"]) == [56, 67]
    assert {g["name"] for g in body["groups"]} == {"Higher-demand, seven-day routes",
                                                    "Lower-demand routes, often with limited or no weekend service"}
    caveats = json.loads((REPO_ROOT / "analytics/config/group_names.json").read_text(encoding="utf-8"))["caveats"]
    assert body["caveats"] == [prose(c) for c in caveats] and len(caveats) == 4   # stored wording, screen typography
    assert {u["route"] for u in body["ungrouped"]} == UNGROUPED and all(u["reason"] for u in body["ungrouped"])
    selected = [f["feature"] for f in body["groups"][0]["features"] if f["selected_for_clustering"]]
    assert selected == body["method"]["selected_features"] and len(selected) == 5
    assert "Stage 5 report" in body["method"]["k_table"]
    assert all(f["unit"] for g in body["groups"] for f in g["features"])


def test_before_the_profile_period_ends_groups_are_not_shown(client):
    body = client.get("/api/route-groups", params={"cutoff": "2026-03-01"}).json()
    assert body["available"] is False and "after the cutoff" in body["reason"]
    assert set(body) <= {"data_version", "mode", "mode_label", "cutoff", "available", "reason"}


PROFILES = REPO_ROOT / "data/processed/cta_ref__r20261113__gtfs8__to20260731/groups__dev20251123_20260331" \
                       "/route_profiles.csv"
RATIOS = {"saturday_to_weekday_rides_ratio": "saturday", "sunday_holiday_to_weekday_rides_ratio": "sunday_holiday"}


def values_of(body) -> dict[str, dict[str, dict]]:
    return {r["route"]: {v["feature"]: v for v in r["values"]} for r in body["route_values"]}


def test_route_values_equal_the_stored_profiles(client):
    body = client.get("/api/route-groups").json()
    csv = pd.read_csv(PROFILES, dtype={"route": str}).set_index("route")
    got = values_of(body)
    assert set(got) == set(csv.index) and len(got) == 123
    members = {r: g["group_id"] for g in body["groups"] for r in g["routes"]}
    for route, feats in got.items():
        assert next(r for r in body["route_values"] if r["route"] == route)["group_id"] == members.get(route)
        for f, v in feats.items():
            stored = csv.at[route, f]
            if pd.isna(stored):
                assert v["value"] is None and v["reason"], (route, f)
            else:
                assert math.isclose(v["value"], stored, rel_tol=1e-9), (route, f)


def test_route_169_weekend_ratios_are_null_with_a_reason_never_zero_or_the_filled_median(client):
    v = values_of(client.get("/api/route-groups").json())["169"]
    for f in RATIOS:
        assert v[f]["value"] is None and v[f]["status"] == "insufficient_observations", f
        assert "unavailable" in v[f]["reason"] and "fewer than 8" in v[f]["reason"], f
    sun = v["sunday_holiday_to_weekday_rides_ratio"]
    assert "0 matched Sunday/holiday days of 3 scheduled" in sun["reason"]
    assert sun["value"] not in (0, 0.0) and sun["value"] != pytest.approx(0.511, abs=1e-3)


def test_structural_zeros_are_exactly_zero_and_match_the_profile_status(client):
    csv = pd.read_csv(PROFILES, dtype={"route": str}).set_index("route")
    got = values_of(client.get("/api/route-groups").json())
    n = 0
    for f, key in RATIOS.items():
        for route in csv.index[csv[f"{key}_service_status"] == "no_scheduled_service"]:
            v = got[route][f]
            assert v["value"] == 0.0 and v["status"] == "no_scheduled_service" and "structural zero" in v["reason"]
            n += 1
        for route in csv.index[csv[f"{key}_service_status"] == "available"]:
            assert got[route][f]["status"] == "available" and got[route][f]["value"] is not None
    assert n == 30 + 36  # 30 routes with no Saturday service; 36 with no Sunday/holiday service


@pytest.mark.parametrize("cutoff, shown", [("2026-03-01", False), ("2026-03-30", False), ("2026-03-31", True)])
def test_route_values_follow_the_groups_cutoff_rule(client, cutoff, shown):
    body = client.get("/api/route-groups", params={"cutoff": cutoff}).json()
    assert ("route_values" in body) is shown and body["available"] is shown
    if shown:
        assert len(body["route_values"]) == 123


def test_after_the_profile_period_groups_are_unchanged_and_no_later_date_appears(client):
    full = client.get("/api/route-groups").json()
    cut = client.get("/api/route-groups", params={"cutoff": "2026-05-31"}).json()
    assert cut["groups"] == full["groups"] and cut["caveats"] == full["caveats"]
    assert max(date.fromisoformat(s) for s in ISO.findall(json.dumps(cut))) <= date(2026, 5, 31)


def test_every_feature_has_a_plain_label(client):
    """Screens show feature labels, never the column keys (no underscores, no field names)."""
    body = client.get("/api/route-groups").json()
    labels = [f["label"] for g in body["groups"] for f in g["features"]]
    labels += [v["label"] for r in body["route_values"] for v in r["values"]]
    labels += body["method"]["selected_feature_labels"]
    assert labels and all(x and "_" not in x for x in labels)
    first = body["groups"][0]["features"]
    assert {f["feature"]: f["label"] for f in first}["weekday_rides_per_scheduled_hour"] == "Weekday rides per scheduled hour"


def test_screen_text_uses_plain_typography(client):
    """No "null", no ">=", ranges with an en dash; the stored wording is otherwise unchanged."""
    from backend.app.labels import prose
    assert prose("has >= 5 routes") == "has \u2265 5 routes"
    assert prose("overlap 13-60 vs 24-51") == "overlap 13\u201360 vs 24\u201351"
    assert prose("fitted on 2025-11-23 to 2026-03-31") == "fitted on 2025-11-23 to 2026-03-31"   # dates untouched
    body = client.get("/api/route-groups").json()
    texts = [body["route_values_note"], body["method"]["k_rule"], *body["caveats"]]
    assert all(">=" not in x and "null" not in x for x in texts)
    assert any("\u2265" in x for x in texts) and any("13\u201360" in x for x in body["caveats"])
