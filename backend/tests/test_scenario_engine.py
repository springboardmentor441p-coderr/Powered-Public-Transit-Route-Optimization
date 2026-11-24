"""Stage 8 scenario arithmetic, with no database (spec 9.15): identities, structural zeros, missing values, limits,
and re-ranking by Stage 5's own rules."""
from __future__ import annotations

import pandas as pd
import pytest

from backend.scenarios.engine import ScenarioRefused, canonical_sha256, compare, factor, validate_inputs

NAN = float("nan")


def base_frame() -> pd.DataFrame:
    """A small network for one day type. A: ordinary; B: ordinary, lower productivity; C: incomplete durations;
    Z: no scheduled service on this day type (structural zero); F: only 5 observed days (below the gate);
    T: a tie with A on rides per scheduled hour; X: rides without a matching timetable."""
    rows = [
        # route, n, sched days, incomplete, rides, trips, hours, structural, reason
        ("A", 25, 25, 0, 50_000.0, 2_500.0, 1_250.0, False, None),
        ("B", 25, 25, 0, 20_000.0, 2_000.0, 1_000.0, False, None),
        ("C", 25, 25, 3, 30_000.0, 1_500.0, NAN, False, None),
        ("Z", 0, 0, 0, NAN, NAN, NAN, True, None),
        ("F", 5, 5, 0, 5_000.0, 200.0, 100.0, False, None),
        ("T", 22, 22, 0, 44_000.0, 2_200.0, 1_100.0, False, None),
        ("X", 0, 0, 0, NAN, NAN, NAN, False, "recorded rides have no matching timetable"),
    ]
    return pd.DataFrame(rows, columns=["route", "observed_days", "scheduled_service_days", "incomplete_duration_days",
                                       "rides_sum", "scheduled_trips_sum", "scheduled_hours_sum", "structural_zero",
                                       "unavailable_reason"])


def run(service=None, stress=None, selected=("A", "B", "C", "Z", "F", "T", "X"), days=25, gate=20):
    inputs = validate_inputs(service, stress)
    return compare(base_frame(), list(selected), inputs, days, "W", gate)


def row(out, r):
    return next(x for x in out["rows"] if x["route"] == r)


# ------------------------------------------------------------------------------------------- identities
def test_a_zero_percent_change_equals_the_baseline_exactly():
    out = run([{"trips": {"how": "percent", "value": 0}}])
    for x in out["rows"]:
        b, s = x["baseline"], x["scenario"]
        for k in ("rides_per_day", "trips_per_day", "hours_per_day", "rides_per_scheduled_trip",
                  "rides_per_scheduled_hour", "rank_rides_per_scheduled_trip", "rank_rides_per_scheduled_hour"):
            assert s[k] == b[k], (x["route"], k)  # bit-identical, not approximately equal
    assert out["other_rank_changes"] == []
    net = out["totals"]["network"]["rides_per_scheduled_hour"]
    assert net["baseline"] == net["scenario"]


def test_trips_times_1_2_divides_rides_per_trip_and_per_hour_by_1_2_when_demand_is_fixed():
    out = run([{"routes": ["A"], "trips": {"how": "percent", "value": 20}}], selected=("A", "B"))
    a = row(out, "A")
    assert factor(20) == 1.2
    assert a["scenario"]["rides_per_day"] == a["baseline"]["rides_per_day"]  # demand held fixed
    assert a["scenario"]["trips_per_day"] == pytest.approx(a["baseline"]["trips_per_day"] * 1.2, rel=1e-12)
    assert a["scenario"]["hours_per_day"] == pytest.approx(a["baseline"]["hours_per_day"] * 1.2, rel=1e-12)
    assert a["scenario"]["rides_per_scheduled_trip"] == pytest.approx(a["baseline"]["rides_per_scheduled_trip"] / 1.2,
                                                                      rel=1e-12)
    assert a["scenario"]["rides_per_scheduled_hour"] == pytest.approx(a["baseline"]["rides_per_scheduled_hour"] / 1.2,
                                                                      rel=1e-12)
    assert a["scenario"]["mean_trip_minutes"] == pytest.approx(a["baseline"]["mean_trip_minutes"], rel=1e-12)
    b = row(out, "B")
    assert b["status"] == "unchanged" and b["scenario"]["trips_per_day"] == b["baseline"]["trips_per_day"]


def test_spec_illustration_50_to_60_trips_at_40_minutes():
    """Spec 9.15.1's illustrative table: 1,000 rides, 50 -> 60 trips, 40 minutes per trip."""
    base = pd.DataFrame([("S", 1, 1, 0, 1000.0, 50.0, 50 * 40 / 60, False, None)], columns=base_frame().columns)
    out = compare(base, ["S"], validate_inputs([{"trips": {"how": "percent", "value": 20}}], None), 1, "W", 1)
    s = row(out, "S")["scenario"]
    assert s["trips_per_day"] == pytest.approx(60)
    assert s["hours_per_day"] == pytest.approx(40.0)
    assert s["rides_per_scheduled_trip"] == pytest.approx(16.67, abs=0.005)
    assert s["rides_per_scheduled_hour"] == pytest.approx(25.0)


def test_a_minus_15_percent_demand_stress_scales_rides_by_exactly_0_85():
    out = run(stress={"percent": -15, "scope": "baseline_routes"})
    assert factor(-15) == 0.85
    for x in out["rows"]:
        if x["baseline"]["rides_sum"] is None:
            assert x["scenario"]["rides_sum"] is None  # nothing to scale stays missing
            continue
        assert x["scenario"]["rides_sum"] == x["baseline"]["rides_sum"] * 0.85
        assert x["demand_assumed"] is True
        assert x["scenario"]["scheduled_trips_sum"] == x["baseline"]["scheduled_trips_sum"]


def test_a_network_stress_moves_every_ratio_equally_so_no_rank_changes():
    out = run(stress={"percent": -15, "scope": "network"})
    for x in out["rows"]:
        assert x["scenario"]["rank_rides_per_scheduled_hour"] == x["baseline"]["rank_rides_per_scheduled_hour"]


def test_a_new_value_per_day_sets_the_daily_mean():
    out = run([{"routes": ["A"], "trips": {"how": "per_day", "value": 120}}], selected=("A",))
    a = row(out, "A")
    assert a["scenario"]["trips_per_day"] == pytest.approx(120)
    assert a["scenario"]["mean_trip_minutes"] == pytest.approx(a["baseline"]["mean_trip_minutes"])


def test_trip_hours_alone_keep_the_trips_and_imply_a_new_duration():
    out = run([{"routes": ["A"], "trip_hours": {"how": "percent", "value": 10}}], selected=("A",))
    a = row(out, "A")
    assert a["scenario"]["trips_per_day"] == a["baseline"]["trips_per_day"]
    assert a["scenario"]["mean_trip_minutes"] == pytest.approx(a["baseline"]["mean_trip_minutes"] * 1.1)


# ------------------------------------------------------------------------------------------- never 0
def test_minus_100_percent_gives_unavailable_ratios_not_zero():
    out = run([{"routes": ["A"], "trips": {"how": "percent", "value": -100}}], selected=("A",))
    s = row(out, "A")["scenario"]
    assert s["trips_per_day"] == 0.0  # zero service is a real scenario value
    assert s["rides_per_scheduled_trip"] is None and s["rides_per_scheduled_hour"] is None
    assert "undefined" in s["reasons"]["rides_per_trip"]
    assert s["rank_rides_per_scheduled_hour"] is None and s["rank_rides_per_scheduled_hour_reason"]


def test_a_structural_zero_is_not_scaled_by_a_percent_and_is_never_0():
    out = run([{"trips": {"how": "percent", "value": 20}}])
    z = row(out, "Z")
    assert z["status"] == "unchanged" and "percentage has nothing to scale" in z["note"]
    for side in ("baseline", "scenario"):
        for k in ("rides_per_day", "trips_per_day", "rides_per_scheduled_trip", "rides_per_scheduled_hour"):
            assert z[side][k] is None
            assert z[side]["reasons"]
    assert "no scheduled service" in z["baseline"]["reasons"]["trips_per_day"]


def test_a_percent_on_only_a_structural_zero_is_refused():
    with pytest.raises(ScenarioRefused, match="give a number of trips per day"):
        run([{"routes": ["Z"], "trips": {"how": "percent", "value": 20}}])


def test_adding_service_to_a_structural_zero_needs_a_trip_count_and_keeps_ratios_unknown():
    out = run([{"routes": ["Z"], "trips": {"how": "per_day", "value": 40}}])
    z = row(out, "Z")
    assert z["status"] == "service_added"
    assert z["scenario"]["trips_per_day"] == pytest.approx(40) and z["scenario"]["days"] == 25
    assert z["scenario"]["rides_per_day"] is None
    assert z["scenario"]["rides_per_scheduled_trip"] is None  # unknown, not invented
    assert "demand there is unknown" in z["scenario"]["reasons"]["rides_per_trip"]
    assert z["scenario"]["hours_per_day"] is None  # no duration to assume without a stated value
    assert z["scenario"]["rank_rides_per_scheduled_hour"] is None


def test_incomplete_durations_keep_hours_missing_and_refuse_an_hours_change():
    out = run([{"routes": ["C"], "trips": {"how": "percent", "value": 20}}], selected=("C",))
    c = row(out, "C")
    assert c["baseline"]["hours_per_day"] is None and c["scenario"]["hours_per_day"] is None
    assert c["scenario"]["rides_per_scheduled_trip"] == pytest.approx(c["baseline"]["rides_per_scheduled_trip"] / 1.2)
    assert "incomplete" in c["scenario"]["reasons"]["hours_per_day"]
    with pytest.raises(ScenarioRefused, match="incomplete trip durations"):
        run([{"routes": ["C"], "trip_hours": {"how": "percent", "value": 20}}], selected=("C",))


def test_a_route_without_a_timetable_match_cannot_get_a_service_change():
    with pytest.raises(ScenarioRefused, match="no matching timetable"):
        run([{"routes": ["X"], "trips": {"how": "per_day", "value": 10}}])


# ------------------------------------------------------------------------------------------- ranking rules
def test_the_baseline_ranks_are_stage_5s_gate_and_ties():
    out = run([{"routes": ["A"], "trips": {"how": "percent", "value": 0}}])
    a, t, f = row(out, "A")["baseline"], row(out, "T")["baseline"], row(out, "F")["baseline"]
    assert a["rides_per_scheduled_hour"] == t["rides_per_scheduled_hour"] == 40.0
    assert a["rank_rides_per_scheduled_hour"] == t["rank_rides_per_scheduled_hour"] == 1  # ties share the lowest rank
    assert row(out, "B")["baseline"]["rank_rides_per_scheduled_hour"] == 3
    assert f["rank_rides_per_scheduled_hour"] is None and f["rank_rides_per_scheduled_hour_reason"] == \
        "fewer than 20 observed days (5)"
    assert row(out, "C")["baseline"]["rank_rides_per_scheduled_hour_reason"] == "scheduled hours incomplete on 3 days"


def test_rank_views_is_the_same_function_stage_5_uses():
    from analytics.groups import profiles
    assert profiles.utilization_profiles.__code__.co_names.count("rank_views") == 1


def test_a_service_increase_moves_the_route_down_and_others_up():
    out = run([{"routes": ["A"], "trips": {"how": "percent", "value": 100}}])
    a = row(out, "A")
    # A: 40 -> 20 rides per scheduled hour, now tied with B (20): both share rank 2; T (40) moves up to 1 alone
    assert a["scenario"]["rides_per_scheduled_hour"] == pytest.approx(20.0)
    assert a["scenario"]["rank_rides_per_scheduled_hour"] == 2 and a["rank_change"]["rides_per_scheduled_hour"] == -1
    assert row(out, "B")["scenario"]["rank_rides_per_scheduled_hour"] == 2
    assert row(out, "B")["rank_change"]["rides_per_scheduled_hour"] == 1
    assert row(out, "T")["scenario"]["rank_rides_per_scheduled_hour"] == 1


# ------------------------------------------------------------------------------------------- refusals
@pytest.mark.parametrize("service, stress, words", [
    ([{"trips": {"how": "per_day", "value": -5}}], None, "cannot be negative"),
    ([{"trips": {"how": "percent", "value": 250}}], None, "between -100 and 200"),
    ([{"trips": {"how": "percent", "value": -101}}], None, "between -100 and 200"),
    ([{"trips": {"how": "percent", "value": float("nan")}}], None, "must be a number"),
    ([{"trips": {"how": "percent", "value": "20"}}], None, "must be a number"),
    ([{"trips": {"how": "factor", "value": 2}}], None, "percentage or a new value"),
    ([{}], None, "neither trips nor trip-hours"),
    (None, {"percent": -95}, "between -90 and 100"),
    (None, {"percent": 10, "scope": "city"}, "baseline routes, chosen routes or the network"),
    (None, None, "needs a service change or a demand assumption"),
    ([{"routes": ["A"], "trips": {"how": "percent", "value": 5}},
      {"routes": ["A"], "trips": {"how": "percent", "value": 5}}], None, "only one service change"),
    ([{"trips": {"how": "percent", "value": 5}}] * 6, None, "at most 5"),
])
def test_invalid_inputs_are_refused_with_a_reason(service, stress, words):
    with pytest.raises(ScenarioRefused, match=words):
        validate_inputs(service, stress)


def test_a_change_outside_the_baseline_is_refused():
    with pytest.raises(ScenarioRefused, match="not in the baseline"):
        run([{"routes": ["Q"], "trips": {"how": "percent", "value": 5}}], selected=("A",))


# ------------------------------------------------------------------------------------------- hashing
def test_the_hash_is_exact_and_stable():
    a = run([{"routes": ["A"], "trips": {"how": "percent", "value": 20}}])
    b = run([{"routes": ["A"], "trips": {"how": "percent", "value": 20}}])
    strip = lambda o: {k: o[k] for k in ("rows", "totals", "other_rank_changes", "ranked_routes")}
    assert canonical_sha256(strip(a)) == canonical_sha256(strip(b))
    c = run([{"routes": ["A"], "trips": {"how": "percent", "value": 20.000001}}])
    assert canonical_sha256(strip(a)) != canonical_sha256(strip(c))
    assert canonical_sha256({"x": 0.1 + 0.2}) != canonical_sha256({"x": 0.3})  # floats compared bit for bit
