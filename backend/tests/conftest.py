"""Shared fixtures for the database tests: they only ever touch routeranker_test."""
from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.app.db import get_conn, open_conn
from backend.app.main import app
from backend.importer.import_data import DEFAULTS, REPO_ROOT, collect, create_schema, read_env, write

TABLES = ["dataset_versions", "source_files", "gtfs_snapshots", "routes", "route_shapes", "daily_ridership",
          "daily_schedule", "matched_utilization", "ridership_without_schedule", "schedule_without_ridership",
          "group_versions", "utilization_profiles", "route_profiles", "group_memberships", "route_stop_coverage",
          "route_stop_overlap", "model_versions"]


@pytest.fixture(scope="session")
def test_url() -> str:
    env_file = REPO_ROOT / "backend" / ".env"
    url = read_env(env_file).get("TEST_DATABASE_URL") if env_file.exists() else None
    if not url:
        pytest.skip("TEST_DATABASE_URL not set in backend/.env")
    with psycopg.connect(url) as c:  # guard: never run destructive fixtures against the real database
        if c.execute("SELECT current_database()").fetchone()[0] != "routeranker_test":
            pytest.fail("TEST_DATABASE_URL must point at routeranker_test")
    return url


@pytest.fixture(scope="session")
def conn(test_url):
    with psycopg.connect(test_url, autocommit=True) as c:
        yield c
        reset(c)  # leave the test database empty


@pytest.fixture(scope="session")
def collected():
    """Real inputs, verified and collected once per session (no database involved)."""
    return collect(DEFAULTS)


@pytest.fixture
def loaded(conn, collected):
    """routeranker_test holding the real data version. Imported once; re-imported only if a test emptied it
    (the rollback tests do), so the slow load is not repeated needlessly. Returns the stored import report."""
    tables, meta = collected
    dv = meta["data_version"]
    if conn.execute("SELECT to_regclass('public.dataset_versions') IS NULL").fetchone()[0] or \
            not conn.execute("SELECT count(*) FROM dataset_versions WHERE data_version = %s", (dv,)).fetchone()[0]:
        reset(conn)
        create_schema(conn)
        write(conn, tables, meta)
    return conn.execute("SELECT import_report FROM dataset_versions WHERE data_version = %s", (dv,)).fetchone()[0]


@pytest.fixture
def client(test_url, loaded):
    """The real app, with its database dependency pointed at routeranker_test (same read-only connection type)."""
    def test_conn():
        with open_conn(test_url) as c:
            yield c
    app.dependency_overrides[get_conn] = test_conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def reset(c: psycopg.Connection) -> None:
    c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


def counts(c: psycopg.Connection) -> dict[str, int]:
    return {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
