"""Stage 8 schema: saved scenarios are immutable in SQL itself, and only the test database can be emptied."""
from __future__ import annotations

import json

import psycopg
import pytest

from backend.importer.import_data import ImportRefused
from backend.importer.import_stage8 import create_stage8_schema, reset_test_scenarios


def _insert(conn, sid="scn_schema_test"):
    dv = conn.execute("SELECT data_version FROM dataset_versions LIMIT 1").fetchone()[0]
    conn.execute("""INSERT INTO scenarios (scenario_id, lineage_id, version, name, origin, mode, cutoff, data_version,
                                           baseline, inputs, assumptions, result, result_sha256)
                    VALUES (%s, %s, 1, 'schema test', 'planner', 'historical_analysis', '2026-07-31', %s,
                            '{}', '{}', '[]', '{}', %s)""", (sid, sid, dv, "0" * 64))
    return sid


def test_a_second_install_changes_nothing(stage8):
    assert create_stage8_schema(stage8) is False


def test_update_and_delete_are_refused_by_the_database(stage8):
    sid = _insert(stage8)
    try:
        with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
            stage8.execute("UPDATE scenarios SET name = 'changed' WHERE scenario_id = %s", (sid,))
        with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
            stage8.execute("DELETE FROM scenarios WHERE scenario_id = %s", (sid,))
        assert stage8.execute("SELECT name FROM scenarios WHERE scenario_id = %s", (sid,)).fetchone()[0] == "schema test"
    finally:
        reset_test_scenarios(stage8)


def test_replay_mode_needs_a_session_and_v1_has_no_parent(stage8):
    dv = stage8.execute("SELECT data_version FROM dataset_versions LIMIT 1").fetchone()[0]
    with pytest.raises(psycopg.errors.CheckViolation):
        stage8.execute("""INSERT INTO scenarios (scenario_id, lineage_id, version, name, origin, mode, cutoff,
                          data_version, baseline, inputs, assumptions, result, result_sha256)
                          VALUES ('x', 'x', 1, 'n', 'planner', 'historical_replay', '2026-06-01', %s, '{}', '{}',
                                  '[]', '{}', %s)""", (dv, "0" * 64))
    with pytest.raises(psycopg.errors.CheckViolation):
        stage8.execute("""INSERT INTO scenarios (scenario_id, lineage_id, version, name, origin, mode, cutoff,
                          data_version, baseline, inputs, assumptions, result, result_sha256)
                          VALUES ('y', 'y', 2, 'n', 'planner', 'historical_analysis', '2026-06-01', %s, '{}', '{}',
                                  '[]', '{}', %s)""", (dv, "0" * 64))


def test_reset_is_refused_outside_the_test_database(stage8, monkeypatch):
    class Other:  # a connection that reports another database name
        def execute(self, *_):
            class R:
                def fetchone(self):
                    return ["routeranker"]
            return R()
    with pytest.raises(ImportRefused, match="routeranker_test"):
        reset_test_scenarios(Other())
