"""Shared fixtures for the database tests: they only ever touch routeranker_test."""
from __future__ import annotations

import psycopg
import pytest

from backend.importer.import_data import DEFAULTS, REPO_ROOT, collect, read_env

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


def reset(c: psycopg.Connection) -> None:
    c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


def counts(c: psycopg.Connection) -> dict[str, int]:
    return {t: c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
