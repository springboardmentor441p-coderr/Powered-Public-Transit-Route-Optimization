"""A failed import must leave the database exactly as it was (one transaction), and a changed input must be
refused before any connection is opened."""
from __future__ import annotations

import dataclasses
import json
import shutil

import psycopg
import pytest

from backend.importer.import_data import DEFAULTS, ImportRefused, Verifier, collect, create_schema, write
from backend.tests.conftest import counts, reset


@pytest.fixture
def empty_db(conn):
    reset(conn)
    create_schema(conn)
    return conn


def replace_table(tables, name, rows):
    return [dataclasses.replace(t, rows=rows(t.rows)) if t.name == name else t for t in tables]


def test_a_bad_value_in_the_last_table_rolls_back_every_table(empty_db, collected):
    tables, meta = collected
    assert tables[-1].name == "model_versions"  # every other table is COPYed before this one fails
    col = tables[-1].columns.index("frozen_at")
    bad = replace_table(tables, "model_versions", lambda rows: [r[:col] + ("not-a-time",) + r[col + 1:] for r in rows])
    with pytest.raises(psycopg.errors.InvalidDatetimeFormat):
        write(empty_db, bad, meta)
    assert set(counts(empty_db).values()) == {0}


def test_an_identity_failure_after_loading_rolls_back_every_table(empty_db, collected):
    # one matched row's rides +1: every CHECK still passes, but it no longer equals daily_ridership
    tables, meta = collected
    t = next(t for t in tables if t.name == "matched_utilization")
    i = t.columns.index("rides")
    bad = replace_table(tables, "matched_utilization",
                        lambda rows: [rows[0][:i] + (str(int(rows[0][i]) + 1),) + rows[0][i + 1:], *rows[1:]])
    with pytest.raises(ImportRefused, match="matched rows agree with daily_ridership"):
        write(empty_db, bad, meta)
    assert set(counts(empty_db).values()) == {0}


def test_a_wrong_sha_is_refused(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hello", encoding="utf-8")
    with pytest.raises(ImportRefused, match="differs from its manifest"):
        Verifier().check("x.txt", f, "0" * 64)


def test_a_changed_input_is_refused_before_connecting(tmp_path):
    # an edited group_names.json (one extra key) no longer matches the sha Stage 5 recorded
    names = tmp_path / "group_names.json"
    shutil.copy(DEFAULTS["group_names"], names)
    data = json.loads(names.read_text(encoding="utf-8"))
    data["edited"] = True
    names.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ImportRefused, match="group_names.json: sha256"):
        collect({**DEFAULTS, "group_names": names})  # collect() never opens a connection
