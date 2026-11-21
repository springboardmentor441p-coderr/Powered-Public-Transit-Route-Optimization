"""Stage 6b: GET /api/rankings on the real data version in routeranker_test, plus a synthetic data version that
proves a cutoff can flip a ranking end to end (SQL included)."""
from __future__ import annotations

import json
import math
import re
from datetime import date, timedelta

import pandas as pd
import pytest

from analytics.groups.profiles import load_matched, load_schedule, utilization_profiles
from backend.app.routers.rankings import CFG, METRICS
from backend.importer.import_data import DEFAULTS, REPO_ROOT

CUT = date(2026, 5, 31)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
VDIR = DEFAULTS["version_dir"]
PERIOD_NAMES = ["full_matched_window", "development"]


def get(client, **params):
    r = client.get("/api/rankings", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def close(a, b, rel=1e-8) -> bool:
    return (a is None and b is None) or (a is not None and b is not None and math.isclose(a, b, rel_tol=rel))


# ------------------------------------------------------------------ equal to Stage 5
@pytest.mark.parametrize("period", PERIOD_NAMES)
def test_rankings_equal_stage5_for_every_period_daytype_and_metric(client, conn, period):
    db = pd.DataFrame(conn.execute("SELECT * FROM utilization_profiles WHERE period_name = %s", (period,)).fetchall(),
                      columns=[c.name for c in conn.execute("SELECT * FROM utilization_profiles LIMIT 0").description])
    csv = pd.read_csv(REPO_ROOT / "reports" / "stage5_rankings.csv", dtype={"route": str})
    csv = csv[csv["period_name"] == period]
    for daytype in "WAU":
        for metric, (rank_col, value_col, num_col, den_col, _, _) in METRICS.items():
            body = get(client, metric=metric, period=period, daytype=daytype)
            api = {r["route"]: r for r in body["rows"]}
            want = db[db["daytype"] == daytype].set_index("route")
            assert set(api) == set(want.index), (period, daytype, metric)
            for route, w in want.iterrows():
                a = api[route]
                assert a["eligible"] == bool(w[f"{rank_col}_eligible"])
                assert a["rank"] == (None if pd.isna(w[rank_col]) else int(w[rank_col]))
                assert a["reason"] == (None if pd.isna(w[f"{rank_col}_reason"]) else w[f"{rank_col}_reason"])
                assert a["observed_days"] == int(w["observed_days"])
                assert close(a["numerator"], None if pd.isna(w[num_col]) else float(w[num_col]))
                assert close(a["denominator"], None if pd.isna(w[den_col]) else float(w[den_col]))
                assert close(a["value"], None if pd.isna(w[value_col]) else float(w[value_col]))
            c = csv[csv["daytype"] == daytype].set_index("route")  # the committed report: values to 6 decimals
            for route, w in c.iterrows():
                if not pd.isna(w[value_col]):
                    assert abs(api[route]["value"] - w[value_col]) <= 5e-7
            assert body["counts"]["ranked"] == int(want[f"{rank_col}_eligible"].sum())


def test_reference_period_is_the_default_and_its_counts(client, conn):
    body = get(client)
    assert body["period"]["name"] == CFG["periods"]["reference_ranking_period"] == "full_matched_window"
    assert body["configuration"]["min_observed_days"] == 20 and body["configuration"]["non_reference_gate"] is False
    ranked = {d: get(client, metric="observed_daily_demand", daytype=d)["counts"]["ranked"] for d in "WAU"}
    want = {d: conn.execute("""SELECT count(*) FROM utilization_profiles WHERE period_name = 'full_matched_window'
                               AND daytype = %s AND observed_daily_demand_rank_eligible""", (d,)).fetchone()[0]
            for d in "WAU"}
    assert ranked == want


# ------------------------------------------------------------------ cutoff
def test_a_cutoff_changes_a_ranking_and_equals_stage5_on_the_cut_rows(client):
    full = get(client, metric="rides_per_scheduled_hour")
    body = get(client, metric="rides_per_scheduled_hour", cutoff=str(CUT))
    assert max(date.fromisoformat(s) for s in ISO.findall(json.dumps(body))) <= CUT
    assert body["period"] == {"name": "full_matched_window", "label": "Full matched window", "start": "2025-11-23",
                              "end": str(CUT), "clipped_to_cutoff": True}
    matched = load_matched(VDIR / "expanded_matched_utilization.csv")  # independent of the database
    schedule = load_schedule(VDIR / "expanded_scheduled_route_day_service.csv", matched)
    matched = matched[matched["date"] <= pd.Timestamp(CUT)]
    schedule = schedule[schedule["date"] <= pd.Timestamp(CUT)]
    direct = utilization_profiles(matched, "x", "2025-11-23", str(CUT), CFG, schedule)
    direct = direct[direct["daytype"] == "W"].set_index("route")
    api = {r["route"]: r for r in body["rows"]}
    assert set(api) == set(direct.index)
    for route, w in direct.iterrows():
        rank = w["service_productivity_metric_rank"]
        assert api[route]["rank"] == (None if pd.isna(rank) else int(rank))
        assert api[route]["observed_days"] == int(w["observed_days"])
    before = {r["route"]: r for r in full["rows"]}
    assert any(api[r]["observed_days"] < before[r]["observed_days"] for r in api)
    assert any(api[r]["rank"] != before[r]["rank"] for r in api if r in before)


@pytest.fixture
def synthetic(conn, loaded):
    """A tiny data version where route X leads before 2026-02-15 and route Y leads after it. imported_at is set far
    in the past, so it never becomes the default version; everything is deleted afterwards."""
    dv, src, gtfs = "synthetic__cutoff_flip", "synthetic_rides", "synthetic_gtfs"
    days = [date(2026, 1, 5) + timedelta(days=i) for i in range(82)]
    days = [d for d in days if d.weekday() < 5]  # weekdays only: daytype W
    split = date(2026, 2, 15)
    with conn.transaction():
        conn.execute("""INSERT INTO dataset_versions VALUES (%s, '3.8', '2026-01-01', '2026-03-31', '2026-03-31',
                        now(), 'synthetic', '{}', '2000-01-01', 'synthetic', '{}')""", (dv,))
        for sid, kind in [(src, "rides"), (gtfs, "gtfs")]:
            conn.execute("INSERT INTO source_files VALUES (%s, %s, %s, 'synthetic', %s, 1, now(), NULL, NULL, true)",
                         (dv, sid, kind, "0" * 64))
        conn.execute("""INSERT INTO gtfs_snapshots VALUES (%s, %s, '2025-12-31', '2025-12-31', '2026-03-31',
                        '2026-01-01', '2026-03-31')""", (dv, gtfs))
        for d in days:
            for route, rides in [("X", 200 if d <= split else 100), ("Y", 100 if d <= split else 400)]:
                conn.execute("INSERT INTO daily_ridership VALUES (%s, %s, %s, 'W', %s, %s)", (dv, route, d, rides, src))
                conn.execute("INSERT INTO daily_schedule VALUES (%s, %s, %s, %s, %s, 10, 5.0, true, 0)",
                             (dv, route, d, gtfs, route))
                conn.execute("""INSERT INTO matched_utilization VALUES (%s, %s, %s, 'W', %s, %s, %s, 10, 5.0, true, 0,
                                %s, %s)""", (dv, route, d, rides, gtfs, route, rides / 10, rides / 5))
    yield dv
    with conn.transaction():
        for t in ["matched_utilization", "daily_schedule", "daily_ridership", "gtfs_snapshots", "source_files",
                  "dataset_versions"]:
            conn.execute(f"DELETE FROM {t} WHERE data_version = %s", (dv,))


def test_synthetic_cutoff_flips_the_order(client, synthetic):
    common = {"data_version": synthetic, "metric": "observed_daily_demand", "start": "2026-01-01",
              "end": "2026-03-31", "daytype": "W"}
    uncut = {r["route"]: r["rank"] for r in get(client, **common)["rows"]}
    cut = {r["route"]: r["rank"] for r in get(client, **common, cutoff="2026-02-15")["rows"]}
    assert uncut == {"X": 2, "Y": 1}  # Y overtakes after Feb 15
    assert cut == {"X": 1, "Y": 2}  # with the cutoff, only the earlier days count
    assert get(client)["data_version"] != synthetic  # never the default version


# ------------------------------------------------------------------ eligibility and gates
def test_ineligible_rows_stay_listed_unranked_with_their_reason(client):
    body = get(client, metric="rides_per_scheduled_hour", period="development", daytype="A")
    assert body["counts"]["ranked"] == 0 and body["counts"]["routes"] > 0
    for r in body["rows"]:
        assert r["rank"] is None and r["eligible"] is False and r["reason"]
        assert (r["reason"].startswith("fewer than 20 observed days") or
                r["reason"] in {"no scheduled service of this day type", "no matched days of this day type"})


def test_min_days_default_explicit_and_non_reference(client):
    default = get(client, period="development", daytype="A")
    explicit_20 = get(client, period="development", daytype="A", min_days=20)
    low = get(client, period="development", daytype="A", min_days=8)
    assert default["configuration"]["non_reference_gate"] is False
    assert explicit_20["configuration"]["non_reference_gate"] is False  # resolved gate equals the reference
    assert explicit_20["rows"] == default["rows"]
    assert low["configuration"]["non_reference_gate"] is True and low["configuration"]["min_observed_days"] == 8
    assert low["counts"]["ranked"] > 0 == default["counts"]["ranked"]


def test_ranking_within_a_group(client, conn):
    body = get(client, group_id=0)
    members = {r[0] for r in conn.execute("SELECT route FROM group_memberships WHERE group_id = 0").fetchall()}
    assert {r["route"] for r in body["rows"]} <= members and len(body["rows"]) == 67
    ranks = sorted(r["rank"] for r in body["rows"] if r["rank"] is not None)
    assert ranks[0] == 1 and ranks[-1] <= 67


# ------------------------------------------------------------------ overlap review
def test_overlap_review_equals_stage5(client):
    body = get(client, metric="route_overlap_review")
    assert body["geometry_version"] == body["default_geometry_version"] == "mdb-389-202603260020"
    csv = pd.read_csv(VDIR / "groups__dev20251123_20260331" / "route_stop_overlap.csv", dtype=str,
                      keep_default_na=False)
    csv = csv[csv["geometry_version"] == body["geometry_version"]]
    api = {(r["route_a"], r["route_b"]): r for r in body["rows"]}
    assert len(api) == len(csv) == body["counts"]["pairs"]
    for w in csv.itertuples():
        a = api[(w.route_a, w.route_b)]
        assert a["rank"] == int(w.overlap_review_rank) and a["shared_stop_count"] == int(w.shared_stop_count)
        assert math.isclose(a["jaccard_stop_overlap"], float(w.jaccard_stop_overlap), rel_tol=1e-9)
        assert a["interpretation"] == w.interpretation and a["interpretation"].startswith("corridor review only")
    assert [r["rank"] for r in body["rows"]] == sorted(r["rank"] for r in body["rows"])


def test_overlap_review_under_a_cutoff_hides_later_archives(client):
    body = get(client, metric="route_overlap_review", cutoff="2026-03-01")
    assert "mdb-389-202603260020" not in body["available_geometry_versions"]
    assert body["geometry_version"] == body["available_geometry_versions"][-1] == "mdb-389-202602100132"
    r = client.get("/api/rankings", params={"metric": "route_overlap_review", "cutoff": "2026-03-01",
                                            "geometry_version": "mdb-389-202603260020"})
    assert r.status_code == 422


# ------------------------------------------------------------------ bad requests
@pytest.mark.parametrize("params", [
    {"metric": "nope"}, {"daytype": "X"}, {"period": "development", "start": "2026-01-01", "end": "2026-02-01"},
    {"start": "2026-02-01", "end": "2026-01-01"}, {"start": "2026-01-01"}, {"min_days": 0},
    {"start": "2026-06-01", "end": "2026-07-31", "cutoff": "2026-05-31"},
    {"group_id": 0, "cutoff": "2026-03-01"},
    {"metric": "route_overlap_review", "min_days": 20}, {"metric": "route_overlap_review", "period": "development"},
    {"metric": "route_overlap_review", "group_id": 0}, {"geometry_version": "mdb-389-202603260020"},
])
def test_bad_requests_are_422(client, params):
    r = client.get("/api/rankings", params=params)
    assert r.status_code == 422, (params, r.text)
