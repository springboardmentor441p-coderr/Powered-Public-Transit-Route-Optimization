"""Stage 5 overlap rules on a tiny hand-made GTFS feed (spec 9.7, 9.12)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from analytics.groups.overlap import INTERPRETATION, OverlapError, coverage, overlap, verify, version_tables
from analytics.reconstruction.gtfs_tables import open_snapshot

ROUTES = ("route_id,route_short_name,route_long_name,route_type\n"
          "R1,1,Bronzeville,3\nR9,X9,Ashland Express,3\nR55,55,Garfield,3\nRED,,Red Line,1\n")
CAL = "WK,1,1,1,1,1,0,0,20260101,20261231\nWE,0,0,0,0,0,1,1,20260101,20261231\n"
MONDAY = date(2026, 3, 2)


def stops(trip, ids):
    return "".join(f"{trip},08:{i:02d}:00,08:{i:02d}:00,{s},{i + 1}\n" for i, s in enumerate(ids))


@pytest.fixture
def tables(feed):
    trips = ("R1,WK,t1\nR1,WK,t1b\nR9,WK,t9\nR55,WK,t55\n"
             "R55,WE,t55we\n"            # weekend-only trip: inactive on the applied Monday
             "RED,WK,trail\n")           # rail trip sharing a stop: not a bus route
    st = (stops("t1", ["A", "B", "C"]) + stops("t1b", ["C", "D", "007"]) + stops("t9", ["C", "D", "E"])
          + stops("t55", ["X1", "X2"]) + stops("t55we", ["Z", "E"]) + stops("trail", ["C", "R1S"]))
    con, _ = open_snapshot(feed(trips=trips, stop_times=st, calendar=CAL, routes=ROUTES))
    out = version_tables(con, "v1", [MONDAY])
    con.close()
    return out


def test_jaccard_and_smaller_route_overlap(tables):
    ov = tables["overlap"].set_index(["route_a", "route_b"])
    r = ov.loc[("1", "X9")]  # 1 = {007, A, B, C, D}; X9 = {C, D, E}; shared {C, D}
    assert r["shared_stop_count"] == 2 and r["shared_stop_ids"] == "C;D"
    assert r["jaccard_stop_overlap"] == pytest.approx(2 / 6)
    assert r["smaller_route_stop_overlap"] == pytest.approx(2 / 3)
    assert r["overlap_review_rank"] == 1 and r["interpretation"] == INTERPRETATION
    assert len(ov) == 1  # 55 shares nothing with 1 or X9 on the applied date


def test_exclusive_stops(tables):
    cov = tables["coverage"].set_index("route")
    assert cov.loc["1", "exclusive_stop_ids"] == "007;A;B"
    assert cov.loc["1", "exclusive_stop_fraction"] == pytest.approx(3 / 5)
    assert cov.loc["X9", "exclusive_stop_ids"] == "E" and cov.loc["55", "exclusive_stop_fraction"] == 1.0


def test_inactive_service_and_rail_stops_are_excluded(tables):
    served = set(tables["served"]["stop_id"])
    assert "Z" not in served  # only served by the weekend trip, inactive on the applied Monday
    assert "R1S" not in served  # only served by the rail trip
    assert "E" in served and set(tables["served"]["route"]) == {"1", "X9", "55"}


def test_identifiers_stay_strings(tables):
    s = tables["served"]
    assert "007" in set(s["stop_id"]) and "X9" in set(s["route"])  # no '7', no lost prefix
    assert s["stop_id"].map(type).eq(str).all() and s["geometry_version"].eq("v1").all()


def test_identity_checks_pass_and_catch_a_broken_table(tables):
    assert all(tables["checks"].values())
    broken = tables["coverage"].copy()
    broken.loc[broken["route"] == "1", "exclusive_stop_ids"] = "007;A;B;C"  # C is shared, not exclusive
    with pytest.raises(OverlapError):
        verify(tables["served"], broken, tables["overlap"])


def test_ties_share_the_review_rank():
    served = pd.DataFrame({"geometry_version": "v", "route": ["P", "P", "Q", "Q", "R", "R", "S", "S"],
                           "stop_id": ["a", "b", "a", "c", "d", "e", "d", "f"]})
    ov = overlap(served).set_index(["route_a", "route_b"])
    assert ov.loc[("P", "Q"), "overlap_review_rank"] == ov.loc[("R", "S"), "overlap_review_rank"] == 1


def served_frame(version, rows):
    return pd.DataFrame([(version, r, s) for r, ids in rows.items() for s in ids],
                        columns=["geometry_version", "route", "stop_id"])


def test_two_versions_together_give_the_same_results_as_each_version_separately():
    """Stop 'c' is exclusive to P in v1 but shared with Q in v2; route stop counts differ between versions.
    If anything were keyed by stop or route alone, the combined run would mix the two timetables."""
    v1 = served_frame("v1", {"P": ["a", "b", "c"], "Q": ["a", "d"]})
    v2 = served_frame("v2", {"P": ["a", "c"], "Q": ["c", "d", "e", "f"], "R": ["e"]})
    both = pd.concat([v1, v2], ignore_index=True)

    def rows(df, keys):
        return df.sort_values(keys).reset_index(drop=True)

    cov_sep = pd.concat([coverage(v1), coverage(v2)], ignore_index=True)
    ov_sep = pd.concat([overlap(v1), overlap(v2)], ignore_index=True)
    cov_both, ov_both = coverage(both), overlap(both)
    pd.testing.assert_frame_equal(rows(cov_both, ["geometry_version", "route"]),
                                  rows(cov_sep, ["geometry_version", "route"]))
    pd.testing.assert_frame_equal(rows(ov_both, ["geometry_version", "route_a", "route_b"]),
                                  rows(ov_sep, ["geometry_version", "route_a", "route_b"]))
    assert all(verify(both, cov_both, ov_both).values())
    c = cov_both.set_index(["geometry_version", "route"])
    assert c.loc[("v1", "P"), "exclusive_stop_ids"] == "b;c"  # c exclusive in v1, a shared with Q in v1 ...
    assert c.loc[("v2", "P"), "exclusive_stop_ids"] == "a"  # ... the reverse in v2: c shared, a exclusive
    assert c.loc[("v1", "P"), "served_stop_count"] == 3 and c.loc[("v2", "P"), "served_stop_count"] == 2
    o = ov_both.set_index(["geometry_version", "route_a", "route_b"])
    assert o.loc[("v2", "P", "Q"), "jaccard_stop_overlap"] == pytest.approx(1 / 5)  # {c} / {a, c, d, e, f}
    assert ("v1", "P", "R") not in o.index  # R does not exist in v1
