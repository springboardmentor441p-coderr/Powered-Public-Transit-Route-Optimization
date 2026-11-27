"""Stage 8 deliverable "saved scenario examples": backend/scenarios/save_examples.py, run against routeranker_test.

The script is the one deliberate writer of scenarios to the app database, so its rules are tested here on the test
database only: the first run saves the three examples; any later run saves nothing and only re-checks them; every
example recomputes to an identical hash; the export goes where --out says and never to the committed report unless asked.
"""
from __future__ import annotations

import hashlib
import json
import sys

import pytest

from backend.importer.import_data import REPO_ROOT
from backend.importer.import_stage8 import reset_test_scenarios
from backend.scenarios import save_examples

COMMITTED = REPO_ROOT / "reports" / "stage8_scenario_examples.json"


@pytest.fixture
def fresh(stage8, test_url, tmp_path):
    """An empty scenarios table on routeranker_test and a .env that names ONLY the test database, so the script
    cannot reach the app database even by mistake. Emptied again afterwards."""
    reset_test_scenarios(stage8)
    env = tmp_path / ".env"
    env.write_text(f"TEST_DATABASE_URL={test_url}\n", encoding="utf-8")
    yield stage8, env, tmp_path
    reset_test_scenarios(stage8)


def run(monkeypatch, capsys, env, out) -> str:
    monkeypatch.setattr(sys, "argv", ["save_examples.py", "--env", str(env), "--url-var", "TEST_DATABASE_URL",
                                      "--out", str(out)])
    save_examples.main()
    return capsys.readouterr().out


def examples(conn) -> list[tuple]:
    return conn.execute("SELECT scenario_id, result_sha256 FROM scenarios WHERE origin = 'example' "
                        "ORDER BY created_at").fetchall()


def test_first_run_saves_the_three_examples_and_exports_them(fresh, monkeypatch, capsys):
    conn, env, tmp = fresh
    out = run(monkeypatch, capsys, env, tmp / "examples.json")
    assert out.count("saved: ") == 3 and out.count("recomputed identically: ") == 3
    assert len(examples(conn)) == 3
    data = json.loads((tmp / "examples.json").read_text(encoding="utf-8"))
    assert [d["name"] for d in data] == [name for name, _ in save_examples.EXAMPLES]
    for d in data:
        assert d["origin"] == "example" and d["recompute_identical"] is True
        assert len(d["result_sha256"]) == 64 and d["assumptions"]       # every scenario states its assumptions


def test_a_second_run_saves_nothing_and_rechecks_the_same_hashes(fresh, monkeypatch, capsys):
    conn, env, tmp = fresh
    run(monkeypatch, capsys, env, tmp / "first.json")
    before = examples(conn)
    total = conn.execute("SELECT count(*) FROM scenarios").fetchone()[0]
    out = run(monkeypatch, capsys, env, tmp / "second.json")
    assert "3 examples already saved: nothing new is saved" in out and "saved: " not in out.replace("already saved", "")
    assert examples(conn) == before
    assert conn.execute("SELECT count(*) FROM scenarios").fetchone()[0] == total
    first = json.loads((tmp / "first.json").read_text(encoding="utf-8"))
    second = json.loads((tmp / "second.json").read_text(encoding="utf-8"))
    assert [d["result_sha256"] for d in first] == [d["result_sha256"] for d in second]


def test_the_test_database_reproduces_the_committed_examples(fresh, monkeypatch, capsys):
    """Same data version, same requests -> the same scenario ids and result hashes as the committed export (which was
    made on the app database)."""
    if not COMMITTED.exists():
        pytest.skip("reports/stage8_scenario_examples.json not present")
    _, env, tmp = fresh
    run(monkeypatch, capsys, env, tmp / "examples.json")
    ours = json.loads((tmp / "examples.json").read_text(encoding="utf-8"))
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert [(d["scenario_id"], d["result_sha256"]) for d in ours] == \
           [(d["scenario_id"], d["result_sha256"]) for d in committed]


def test_the_committed_report_is_only_the_default_and_is_not_touched_with_out(fresh, monkeypatch, capsys):
    _, env, tmp = fresh
    assert save_examples.OUT == COMMITTED
    digest = hashlib.sha256(COMMITTED.read_bytes()).hexdigest() if COMMITTED.exists() else None
    run(monkeypatch, capsys, env, tmp / "examples.json")
    assert (hashlib.sha256(COMMITTED.read_bytes()).hexdigest() if COMMITTED.exists() else None) == digest


def test_the_app_database_url_is_never_needed(fresh, monkeypatch, capsys):
    """With only TEST_DATABASE_URL in the .env, asking for the default DATABASE_URL fails before connecting."""
    _, env, tmp = fresh
    monkeypatch.setattr(sys, "argv", ["save_examples.py", "--env", str(env), "--out", str(tmp / "x.json")])
    with pytest.raises(KeyError):
        save_examples.main()
    assert not (tmp / "x.json").exists()
