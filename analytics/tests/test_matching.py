"""Spec 9.19.1 correctness cases for exact matching and reconciliation (missing vs zero, both directions)."""
from __future__ import annotations

import io
from datetime import date

import pandas as pd
import pytest

from analytics.reconstruction.matching import RidershipConflictError, load_ridership, match, per_route, reconciliation

D1, D2, D3 = date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4)


def schedule(rows):
    df = pd.DataFrame(rows, columns=["route", "date", "scheduled_trips", "scheduled_service_hours"])
    df["snapshot_id"], df["route_id"] = "snap", "R" + df["route"]
    df["scheduled_trips"] = df["scheduled_trips"].astype("Int64")
    df["scheduled_service_hours"] = df["scheduled_service_hours"].astype("Float64")
    df["duration_complete"] = df["scheduled_service_hours"].notna()
    df["trips_missing_duration"] = pd.array([0] * len(df), dtype="Int64")
    return df


def rides(rows):
    df = pd.DataFrame(rows, columns=["route", "date", "daytype", "rides"])
    df["rides"] = df["rides"].astype("Int64")
    return df


SEL = pd.DataFrame({"date": [D1, D2, D3], "snapshot_id": ["snap", "snap", "snap"]})


def run(s, r):
    res = match(s, r, SEL, {"snap": {"1", "2"}}, {"1", "2"})
    return res, reconciliation(res, s, r)


# 9.19.1 (Stage 2 part): "genuine zero rides stay zero" / missing observations are never zero.
def test_missing_rides_stay_missing_and_zero_stays_zero():
    s = schedule([("1", D1, 10, 5.0), ("1", D2, 10, 5.0)])
    r = rides([("1", D1, "W", 0)])  # a real zero on D1; no record at all on D2
    res, _ = run(s, r)
    m = res["matched"]
    assert len(m) == 1 and m.iloc[0]["rides"] == 0  # genuine zero kept as 0
    assert m.iloc[0]["rides_per_scheduled_trip"] == 0
    swr = res["schedule_without_ridership"]
    assert len(swr) == 1 and swr.iloc[0]["date"] == D2
    assert pd.isna(swr.iloc[0]["rides"])  # missing, NOT 0
    csv = swr.to_csv(index=False)
    assert ",,no_ridership_record" in csv  # written as an empty field, not "0"


# 9.19.1: "Reconciliation reports both unmatched directions and reproduces the per-route coverage checks."
def test_reconciliation_reports_both_directions_with_identities():
    s = schedule([("1", D1, 10, 5.0), ("1", D2, 10, 5.0), ("169", D3, 1, 0.5)])
    r = rides([("1", D1, "W", 100), ("1", D2, "W", 120), ("2", D2, "W", 7),
               ("1001", D1, "W", 400), ("1001", D3, "W", 410)])
    res = match(s, r, SEL, {"snap": {"1", "2", "169"}}, {"1", "2", "169"})
    rec = reconciliation(res, s, r)
    assert (rec["matched"], rec["ridership_without_schedule"], rec["schedule_without_ridership"]) == (2, 3, 1)
    assert rec["identity_ridership_holds"] and rec["identity_schedule_holds"]
    assert rec["ridership_observations"] == rec["matched"] + rec["ridership_without_schedule"]
    assert rec["schedule_records"] == rec["matched"] + rec["schedule_without_ridership"]

    rws = res["ridership_without_schedule"].set_index(["route", "date"])
    assert rws.loc[("1001", D1), "unmatched_reason"] == "route_absent_from_selected_snapshot"
    assert rws.loc[("1001", D1), "identifier_absent_from_all_archives"]
    assert rws.loc[("2", D2), "unmatched_reason"] == "route_in_snapshot_no_active_trips"
    assert not rws.loc[("2", D2), "identifier_absent_from_all_archives"]
    assert rws["rides"].sum() == 817  # positive rides are retained, never discarded

    by_route = per_route(res["ridership_without_schedule"], with_rides=True).set_index("route")
    assert by_route.loc["1001"].tolist() == [2, 810, D1, D3]
    assert per_route(res["schedule_without_ridership"], with_rides=False).set_index("route").loc["169", "records"] == 1
    assert rec["routes_with_records_on_every_scheduled_date"] == 1  # route 1 yes, route 169 no


def test_hours_ratio_missing_when_hours_missing_or_trips_zero():
    s = schedule([("1", D1, 10, None), ("2", D1, 0, 0.0)])
    r = rides([("1", D1, "W", 50), ("2", D1, "W", 5)])
    m = run(s, r)[0]["matched"].set_index("route")
    assert pd.isna(m.loc["1", "rides_per_scheduled_hour"]) and m.loc["1", "rides_per_scheduled_trip"] == 5
    assert pd.isna(m.loc["2", "rides_per_scheduled_trip"]) and pd.isna(m.loc["2", "rides_per_scheduled_hour"])


def test_duplicate_keys_fail_one_to_one_validation():
    s = schedule([("1", D1, 10, 5.0), ("1", D1, 11, 5.5)])
    with pytest.raises(pd.errors.MergeError):
        run(s, rides([("1", D1, "W", 1)]))


def test_route_identifiers_matched_exactly_after_trim():
    s = schedule([("X9", D1, 10, 5.0)])
    r = rides([("x9", D1, "W", 3), ("9", D1, "W", 4)])  # case and prefix matter
    res = match(s, r, SEL, {"snap": {"X9"}}, {"X9"})
    assert len(res["matched"]) == 0 and len(res["ridership_without_schedule"]) == 2


def write_csv(tmp_path, text):
    p = tmp_path / "rides.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_ridership_parses_explicitly_and_keeps_missing(tmp_path):
    p = write_csv(tmp_path, 'route,date,daytype,rides\n 3 ,03/02/2026,W,"1,234"\n3,03/03/2026,W,0\n'
                            '3,03/04/2026,W,\n3,03/04/2026,W,\n')  # last line is an exact copy
    df, info = load_ridership(p)
    assert df["route"].tolist() == ["3", "3", "3"]
    assert df["date"].tolist() == [D1, D2, D3]  # month/day order is explicit
    assert df["rides"].iloc[0] == 1234 and df["rides"].iloc[1] == 0
    assert pd.isna(df["rides"].iloc[2])  # an empty value stays missing, it never becomes 0
    assert info["exact_duplicates_removed"] == 1


def test_conflicting_ridership_records_are_not_summed(tmp_path):
    p = write_csv(tmp_path, "route,date,daytype,rides\n3,03/02/2026,W,10\n3,03/02/2026,W,12\n")
    with pytest.raises(RidershipConflictError):
        load_ridership(p)
