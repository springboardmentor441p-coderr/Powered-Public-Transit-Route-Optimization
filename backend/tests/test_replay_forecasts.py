"""Stage 7: the stored replay forecasts cannot peek, are deterministic, are never rewritten, and reproduce Stage 4a.

All on routeranker_test (a disposable copy of the real data version). The leakage test changes every ride after a
cutoff, rebuilds the forecasts up to that cutoff, and requires them to be bit-identical (spec 9.19.1: "A replay
prediction cannot retrieve target-day/later rides before their availability boundary").
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from psycopg.rows import dict_row

from backend.importer.import_data import DEFAULTS
from backend.replay.build_forecasts import consistency, stage4_reference
from backend.replay.forecasting import (ForecastConflict, compute_day, day_inputs, ensure_run, run_hash, store_day,
                                        store_range)
from analytics.features.model_features import build_features

CUT = date(2026, 6, 30)
LAGS = ["boardings_1d_ago", "boardings_7d_ago", "boardings_14d_ago", "boardings_21d_ago", "boardings_28d_filled",
        "boardings_28d_available", "seasonal_count", "seasonal_mean", "scheduled_trips", "scheduled_hours"]


@pytest.fixture
def run(conn, stage7):
    return ensure_run(conn, DEFAULTS["version_dir"].name)


def predictions(conn, run_id, first: date, last: date) -> dict:
    return {(m, r, d): p for m, r, d, p in conn.execute(
        """SELECT method, route, target_date, prediction FROM forecasts
           WHERE run_id = %s AND target_date BETWEEN %s AND %s""", (run_id, first, last)).fetchall()}


def test_stored_forecasts_reproduce_stage4a_on_the_same_route_days(conn, run):
    c, ref = consistency(conn, run.run_id, run.model_method), stage4_reference(run.model_method)
    assert c["rows"] == ref["rows"] == 6542
    assert abs(c["model_mae"] - ref["model_mae"]) < 1e-6 and abs(c["base_mae"] - ref["base_mae"]) < 1e-6


def test_replay_features_equal_stage3_for_every_june_july_day(conn, run):
    """The replay rebuilds, day by day from the database, exactly the inputs Stage 4a was scored on."""
    want = pd.read_csv(DEFAULTS["version_dir"] / "features__delay1d" / "feature_rows.csv", dtype={"route": str})
    want = want[want["split"].eq("test")].set_index(["route", "date"]).sort_index()
    got = []
    d = run.first_target
    while d <= run.last_target:
        targets, history, _ = day_inputs(conn, run, d)
        f = build_features(targets, history, reporting_delay_days=1)
        f["date"] = f["date"].dt.strftime("%Y-%m-%d")
        got.append(f)
        d += timedelta(days=1)
    got = pd.concat(got).set_index(["route", "date"]).sort_index()
    assert list(got.index) == list(want.index)                                     # same 7,018 route-days
    for c in LAGS:
        assert np.allclose(got[c].astype(float), want[c].astype(float), equal_nan=True, rtol=0, atol=0), c
    assert (got["eligible"].to_numpy() == want["forecastable"].to_numpy()).all()


def test_no_peeking_changing_every_later_ride_leaves_earlier_forecasts_bit_identical(conn, run):
    before_hash = run_hash(conn, run.run_id, through=CUT)
    full_hash = run_hash(conn, run.run_id)
    before = predictions(conn, run.run_id, run.first_target, run.last_target)
    try:
        later_rows = conn.execute("SELECT count(*) FROM daily_ridership WHERE service_date > %s", (CUT,)).fetchone()[0]
        n = conn.execute("UPDATE daily_ridership SET rides = rides * 3 + 7 WHERE service_date > %s", (CUT,)).rowcount
        assert n == later_rows > 3000                                              # every later ride really changed
        conn.execute("DELETE FROM forecasts WHERE run_id = %s", (run.run_id,))
        store_range(conn, run, run.first_target, CUT)                              # rebuilt with the changed table
        assert run_hash(conn, run.run_id, through=CUT) == before_hash              # bit-identical up to the cutoff
        # the test is sensitive: a day whose inputs include changed rides does move
        later = compute_day(conn, run, CUT + timedelta(days=2))
        moved = sum(1 for r in later.itertuples() if r.status == "forecast"
                    and r.prediction != before[(r.method, r.route, r.target_date)])
        assert moved > 100
    finally:
        conn.execute("UPDATE daily_ridership SET rides = (rides - 7) / 3 WHERE service_date > %s", (CUT,))
        conn.execute("DELETE FROM forecasts WHERE run_id = %s", (run.run_id,))
        store_range(conn, run, run.first_target, run.last_target)
    assert run_hash(conn, run.run_id) == full_hash                                 # restored exactly


def test_two_builds_give_the_same_hash(conn, run):
    first = run_hash(conn, run.run_id)
    conn.execute("DELETE FROM forecasts WHERE run_id = %s", (run.run_id,))
    store_range(conn, run, run.first_target, run.last_target)
    assert run_hash(conn, run.run_id) == first


def test_a_retry_stores_nothing_and_rewrites_nothing(conn, run, client):
    day = date(2026, 6, 15)
    stamp = conn.execute("SELECT max(created_at) FROM forecasts WHERE run_id = %s AND target_date = %s",
                         (run.run_id, day)).fetchone()[0]
    again = store_day(conn, run, day)
    assert again["inserted"] == 0 and again["existing"] == again["rows"] > 0
    r1 = client.post("/api/forecasts", json={"route": "22", "target_date": day.isoformat()}).json()
    r2 = client.post("/api/forecasts", json={"route": "22", "target_date": day.isoformat()}).json()
    assert r1["stored"]["newly_stored"] == r2["stored"]["newly_stored"] == 0
    assert [f["prediction"] for f in r1["forecasts"]] == [f["prediction"] for f in r2["forecasts"]]
    assert conn.execute("SELECT max(created_at) FROM forecasts WHERE run_id = %s AND target_date = %s",
                        (run.run_id, day)).fetchone()[0] == stamp                  # nothing rewritten


def test_a_stored_forecast_that_differs_is_refused_not_rewritten(conn, run):
    day = date(2026, 6, 16)
    key = conn.execute("""SELECT route FROM forecasts WHERE run_id = %s AND target_date = %s AND status = 'forecast'
                          AND method = %s LIMIT 1""", (run.run_id, day, run.model_method)).fetchone()[0]
    conn.execute("UPDATE forecasts SET prediction = prediction + 1 WHERE run_id = %s AND target_date = %s AND route = %s "
                 "AND method = %s", (run.run_id, day, key, run.model_method))
    try:
        with pytest.raises(ForecastConflict, match="never rewritten"):
            store_day(conn, run, day)
    finally:
        conn.execute("UPDATE forecasts SET prediction = prediction - 1 WHERE run_id = %s AND target_date = %s "
                     "AND route = %s AND method = %s", (run.run_id, day, key, run.model_method))
    store_day(conn, run, day)                                                      # consistent again


def test_every_forecast_uses_a_timetable_captured_before_its_day(conn, run):
    """Spec 9.14.3: the forecast schedule is the latest archive captured strictly before the issue date."""
    bad = conn.execute("""SELECT count(*) FROM forecasts f JOIN gtfs_snapshots g
                              ON g.snapshot_id = f.input_snapshot AND g.data_version = %s
                          WHERE f.run_id = %s AND g.captured_date >= f.target_date""",
                       (run.data_version, run.run_id)).fetchone()[0]
    assert bad == 0
    rows = conn.cursor(row_factory=dict_row).execute(
        """SELECT DISTINCT input_snapshot, latest_ride_date FROM forecasts WHERE run_id = %s AND target_date = '2026-07-11'""",
        (run.run_id,)).fetchall()
    assert rows == [{"input_snapshot": "mdb-389-202605300003", "latest_ride_date": date(2026, 7, 10)}]
    assert conn.execute("SELECT count(*) FROM forecasts WHERE run_id = %s AND latest_ride_date >= issue_date",
                        (run.run_id,)).fetchone()[0] == 0


def test_unavailable_forecasts_have_a_reason_and_no_value(conn, run):
    rows = conn.execute("""SELECT prediction, withheld_reason FROM forecasts
                           WHERE run_id = %s AND status = 'unavailable'""", (run.run_id,)).fetchall()
    assert rows and all(p is None and r and r.startswith("missing: ") and "_" not in r for p, r in rows)
