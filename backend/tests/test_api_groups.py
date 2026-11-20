"""Stage 6b: GET /api/route-groups on the real data version in routeranker_test."""
from __future__ import annotations

import json
import math
import re
from datetime import date

import pandas as pd

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
    assert body["caveats"] == caveats and len(caveats) == 4
    assert {u["route"] for u in body["ungrouped"]} == UNGROUPED and all(u["reason"] for u in body["ungrouped"])
    selected = [f["feature"] for f in body["groups"][0]["features"] if f["selected_for_clustering"]]
    assert selected == body["method"]["selected_features"] and len(selected) == 5
    assert "Stage 5 report" in body["method"]["k_table"]
    assert all(f["unit"] for g in body["groups"] for f in g["features"])


def test_before_the_profile_period_ends_groups_are_not_shown(client):
    body = client.get("/api/route-groups", params={"cutoff": "2026-03-01"}).json()
    assert body["available"] is False and "after the cutoff" in body["reason"]
    assert set(body) <= {"data_version", "mode", "mode_label", "cutoff", "available", "reason"}


def test_after_the_profile_period_groups_are_unchanged_and_no_later_date_appears(client):
    full = client.get("/api/route-groups").json()
    cut = client.get("/api/route-groups", params={"cutoff": "2026-05-31"}).json()
    assert cut["groups"] == full["groups"] and cut["caveats"] == full["caveats"]
    assert max(date.fromisoformat(s) for s in ISO.findall(json.dumps(cut))) <= date(2026, 5, 31)
