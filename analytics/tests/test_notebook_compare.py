"""The notebook's rules are reproduced as the notebook states them (comparison only), and the comparison never
modifies our outputs."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from analytics.groups.notebook_compare import compare, notebook_profiles, notebook_ranking

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "analytics" / "config" / "groups.json").read_text(encoding="utf-8"))
NC = CFG["notebook_comparison"]


def rows(route, daytype, n, rides=100.0, trips=10, hours=5.0, start="2026-01-05"):
    return pd.DataFrame({"route": route, "date": pd.date_range(start, periods=n), "daytype": daytype,
                         "rides": rides, "scheduled_trips": trips, "scheduled_hours": hours})


def test_notebook_drops_a_weekday_only_route_that_the_spec_keeps():
    t = pd.concat([rows("FULL", "W", 20), rows("FULL", "A", 8, start="2026-03-01"),
                   rows("FULL", "U", 8, start="2026-04-01"), rows("WKDAY", "W", 25)])
    prof, reasons = notebook_profiles(t, NC)
    assert list(prof["route"]) == ["FULL"]
    assert reasons["WKDAY"] == "fewer than 8 Saturdays or 8 Sundays/holidays in training"


def test_notebook_ranking_is_sequential_so_ties_get_different_ranks():
    t = pd.concat([rows("P", "W", 20, rides=100.0), rows("Q", "W", 20, rides=100.0, start="2026-03-01"),
                   rows("R", "W", 20, rides=50.0, start="2026-05-01")])
    r = notebook_ranking(t, NC)
    w = r[r["daytype"] == "W"].set_index("route")["notebook_rank"]
    assert sorted(w[["P", "Q"]]) == [1, 2] and w["R"] == 3  # tied P and Q get 1 and 2 (ours would give both 1)
    assert r[r["daytype"] == "A"].empty


def test_compare_only_reads_our_outputs():
    fr = pd.concat([rows(r, "W", 25, rides=100.0 * (i + 1), start="2025-12-01") for i, r in enumerate("PQRST")])
    fr["split"] = "train"
    ours = pd.DataFrame({"route": list("PQRST"), "base_eligible": True,
                         "saturday_service_status": "no_scheduled_service",
                         "sunday_holiday_service_status": "no_scheduled_service"})
    labels = pd.Series([0, 0, 1, 1, 1], index=list("PQRST"))
    ranking = pd.DataFrame({"route": list("PQRST"), "daytype": "W",
                            "service_productivity_metric_rank_eligible": True,
                            "service_productivity_metric_rank": pd.array([5, 4, 3, 2, 1], dtype="Int64")})
    before = (ours.copy(deep=True), labels.copy(deep=True), ranking.copy(deep=True), fr.copy(deep=True))
    out = compare(fr, ours, labels, ["mean_weekday_rides"], 2, ranking, CFG)
    pd.testing.assert_frame_equal(ours, before[0])
    pd.testing.assert_series_equal(labels, before[1])
    pd.testing.assert_frame_equal(ranking, before[2])
    pd.testing.assert_frame_equal(fr, before[3])
    assert out["profiles"]["notebook valid profiles (recomputed)"] == 0  # no weekend rows: all dropped
    rho = out["ranking"].set_index("daytype").loc["W", "rank Spearman on common routes"]
    assert np.isclose(rho, 1.0)  # same order by rides per hour
