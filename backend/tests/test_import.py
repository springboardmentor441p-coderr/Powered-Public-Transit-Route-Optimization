"""Stage 6a importer on the real data version, loaded into routeranker_test (spec 9.17.2, 9.19.2)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import psycopg
import pytest

from backend.importer.import_data import (DEFAULTS, GROUPS, ImportRefused, create_schema, membership_group_ids,
                                          write)
from backend.tests.conftest import counts, reset

VDIR = DEFAULTS["version_dir"]


def csv(name: str) -> pd.DataFrame:
    return pd.read_csv(VDIR / name, dtype=str, keep_default_na=False, na_filter=False)


@pytest.fixture(scope="module")
def imported(conn, collected):
    reset(conn)
    create_schema(conn)
    tables, meta = collected
    return write(conn, tables, meta)


def one(conn, sql: str, *args):
    return conn.execute(sql, args).fetchone()[0]


def test_every_table_has_exactly_the_rows_sent_and_the_manifest_counts(conn, collected, imported):
    tables, meta = collected
    db = counts(conn)
    for t in tables:
        assert db[t.name] == len(t.rows), t.name
        manifest_rows = next((v["manifest_rows"] for k, v in meta["inputs"].items()
                              if t.source.endswith(k) and v["manifest_rows"] is not None), None)
        if manifest_rows is not None:
            assert db[t.name] == manifest_rows, t.name
    assert db["dataset_versions"] == 1


def test_ridership_is_cut_at_the_cutoff_and_nothing_else_is_dropped(conn, collected, imported):
    r = collected[1]["ridership"]
    assert r["kept_rows"] + r["excluded_after_cutoff"] + r["exact_duplicates_removed"] == r["raw_rows"]
    cutoff = date.fromisoformat(collected[1]["stage2_manifest"]["ridership_cutoff"])
    assert one(conn, "SELECT max(service_date) FROM daily_ridership") <= cutoff
    assert date.fromisoformat(r["excluded_first_date"]) > cutoff


def test_all_sql_identities_hold(imported):
    assert imported["identities"] and all(v == 0 for v in imported["identities"].values())


def test_missing_stays_null_and_recorded_zero_stays_zero(conn, collected, imported):
    prof = csv(f"{GROUPS}/expanded_utilization_profiles.csv")
    assert one(conn, "SELECT count(*) FROM utilization_profiles WHERE rides_sum IS NULL") == (prof["rides_sum"] == "").sum()
    m = csv("expanded_matched_utilization.csv")
    assert (one(conn, "SELECT count(*) FROM matched_utilization WHERE rides_per_scheduled_hour IS NULL")
            == (m["rides_per_scheduled_hour"] == "").sum())
    zeros = collected[1]["ridership"]["kept_zero_ride_rows"]
    assert zeros > 0 and one(conn, "SELECT count(*) FROM daily_ridership WHERE rides = 0") == zeros


def test_stop_id_arrays_round_trip_and_empty_cells_are_empty_arrays(conn, imported):
    cov = csv(f"{GROUPS}/route_stop_coverage.csv")
    db = pd.DataFrame(conn.execute("""SELECT geometry_version, route, array_to_string(served_stop_ids, ';'),
                                             array_to_string(exclusive_stop_ids, ';'), cardinality(exclusive_stop_ids)
                                      FROM route_stop_coverage""").fetchall(),
                      columns=["geometry_version", "route", "served", "exclusive", "n_excl"])
    joined = cov.merge(db, on=["geometry_version", "route"], validate="one_to_one")
    assert (joined["served"] == joined["served_stop_ids"]).all()
    assert (joined["exclusive"] == joined["exclusive_stop_ids"]).all()
    empty = joined["exclusive_stop_ids"] == ""
    assert empty.sum() > 0 and (joined.loc[empty, "n_excl"] == 0).all()  # '' -> {}, never {''}
    assert one(conn, """SELECT count(*) FROM route_stop_coverage
                        WHERE '' = ANY (served_stop_ids) OR '' = ANY (exclusive_stop_ids)""") == 0
    assert one(conn, "SELECT count(*) FROM route_stop_overlap WHERE '' = ANY (shared_stop_ids)") == 0


def test_numbers_are_stored_exactly_as_written(conn, imported):
    m = csv("expanded_matched_utilization.csv")
    db = pd.DataFrame(conn.execute("""SELECT route, service_date::text, rides_per_scheduled_trip, scheduled_service_hours
                                      FROM matched_utilization""").fetchall(),
                      columns=["route", "date", "rpt", "hours"])
    j = m.merge(db, on=["route", "date"], validate="one_to_one")
    assert (j["rides_per_scheduled_trip"].astype(float) == j["rpt"]).all()
    assert (j["scheduled_service_hours"].astype(float) == j["hours"]).all()


def test_ungrouped_routes_have_null_group_id_and_keep_their_reasons(conn, imported):
    src = csv(f"{GROUPS}/route_group_membership.csv")
    rows = conn.execute("SELECT route, group_id, reason, group_name FROM group_memberships ORDER BY route").fetchall()
    db = pd.DataFrame(rows, columns=["route", "group_id", "reason", "group_name"])
    ungrouped, grouped = db[db["group_id"].isna()], db[db["group_id"].notna()]
    want = src[src["group"] == "ungrouped"]
    assert len(ungrouped) == len(want) == 5
    assert dict(zip(ungrouped["route"], ungrouped["reason"])) == dict(zip(want["route"], want["reason"]))
    assert ungrouped["group_name"].isna().all() and (ungrouped["reason"] != "grouped").all()
    assert len(grouped) == 123 and set(grouped["group_id"].astype(int)) == {0, 1}
    by_route = src.set_index("route")["group"]
    assert all(str(g) == by_route[r] for r, g in zip(grouped["route"], grouped["group_id"].astype(int)))


def test_membership_group_values_other_than_numbers_or_ungrouped_are_refused():
    ok = membership_group_ids(pd.DataFrame({"group": ["0", "1", "ungrouped"]}))
    assert ok["group"].tolist() == ["0", "1", ""]
    for bad in ["x", "1.0", "-1", " 1", "Ungrouped"]:
        with pytest.raises(ImportRefused, match="non-numeric group values"):
            membership_group_ids(pd.DataFrame({"group": ["0", bad]}))


def test_a_second_row_for_the_same_route_and_date_is_rejected(conn, imported):
    dv, route, d = conn.execute("SELECT data_version, route, service_date FROM daily_ridership LIMIT 1").fetchone()
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            conn.execute("INSERT INTO daily_ridership SELECT data_version, route, service_date, daytype, rides + 1, "
                         "source_snapshot_id FROM daily_ridership WHERE data_version = %s AND route = %s "
                         "AND service_date = %s", (dv, route, d))


def test_a_second_import_of_the_same_version_is_refused_and_changes_nothing(conn, collected, imported):
    before = counts(conn)
    with pytest.raises(ImportRefused, match="already imported"):
        write(conn, *collected)
    assert counts(conn) == before
