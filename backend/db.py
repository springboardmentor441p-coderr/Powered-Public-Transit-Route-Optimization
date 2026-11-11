"""Small PostgreSQL access layer; data imports and replay updates are transactional."""
from contextlib import contextmanager
import os
import re

import psycopg
from psycopg.rows import dict_row


def database_url():
    return os.environ.get('DATABASE_URL', 'postgresql://router_local@127.0.0.1:55432/router')


def schema_name():
    name = os.environ.get('ROUTER_DB_SCHEMA', 'public')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', name):
        raise ValueError('Invalid database schema')
    return name


@contextmanager
def connection():
    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=5,
                         options=f'-c search_path={schema_name()}') as conn:
        yield conn


SCHEMA = '''
CREATE TABLE IF NOT EXISTS rr_dataset_versions (
 id text PRIMARY KEY, imported_at timestamptz NOT NULL DEFAULT now(), metadata jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS rr_settings (key text PRIMARY KEY, value text NOT NULL);
CREATE TABLE IF NOT EXISTS rr_routes (
 data_version text REFERENCES rr_dataset_versions(id), route text NOT NULL,
 name text NOT NULL, PRIMARY KEY(data_version,route)
);
CREATE TABLE IF NOT EXISTS rr_daily (
 data_version text NOT NULL, route text NOT NULL, date date NOT NULL,
 rides double precision, published_rides double precision, day_type text NOT NULL,
 scheduled_trips double precision, scheduled_hours double precision,
 eligible boolean NOT NULL, schedule_eligible boolean NOT NULL,
 schedule_snapshot text, prior_snapshot text, quality jsonb NOT NULL,
 PRIMARY KEY(data_version,route,date),
 FOREIGN KEY(data_version,route) REFERENCES rr_routes(data_version,route),
 CHECK(rides IS NULL OR rides >= 0)
);
CREATE INDEX IF NOT EXISTS rr_daily_date ON rr_daily(data_version,date);
CREATE TABLE IF NOT EXISTS rr_geometry (
 data_version text NOT NULL, route text NOT NULL, geometry_version text NOT NULL,
 available_from date NOT NULL, paths jsonb NOT NULL,
 PRIMARY KEY(data_version,route,geometry_version)
);
CREATE TABLE IF NOT EXISTS rr_profiles (
 data_version text NOT NULL, route text NOT NULL, profile_version text NOT NULL,
 first_date date NOT NULL, last_date date NOT NULL, payload jsonb NOT NULL,
 PRIMARY KEY(data_version,route,profile_version)
);
CREATE TABLE IF NOT EXISTS rr_models (
 id text PRIMARY KEY, data_version text REFERENCES rr_dataset_versions(id), metadata jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS rr_replays (
 id text PRIMARY KEY, parent_session_id text REFERENCES rr_replays(id),
 data_version text REFERENCES rr_dataset_versions(id), model_version text REFERENCES rr_models(id),
 start_date date NOT NULL, end_date date NOT NULL, virtual_date date NOT NULL,
 state text NOT NULL CHECK(state IN ('paused','running','completed')),
 speed_seconds double precision NOT NULL CHECK(speed_seconds >= 1 AND speed_seconds <= 3600),
 reporting_delay_days integer NOT NULL DEFAULT 14,
 wall_anchor timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(start_date <= virtual_date AND virtual_date <= end_date)
);
CREATE TABLE IF NOT EXISTS rr_forecasts (
 id text PRIMARY KEY, session_key text NOT NULL, session_id text REFERENCES rr_replays(id),
 route text NOT NULL, target_date date NOT NULL, issued_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), data_version text REFERENCES rr_dataset_versions(id),
 model_version text REFERENCES rr_models(id), available_through date NOT NULL,
 prediction double precision, status text NOT NULL,
 payload jsonb NOT NULL, UNIQUE(session_key,route,target_date,model_version),
 CHECK(prediction IS NULL OR prediction >= 0)
);
CREATE INDEX IF NOT EXISTS rr_forecast_session ON rr_forecasts(session_id,target_date);
CREATE TABLE IF NOT EXISTS rr_scenarios (
 id text PRIMARY KEY, session_id text REFERENCES rr_replays(id),
 data_version text REFERENCES rr_dataset_versions(id), route text NOT NULL, date date NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), payload jsonb NOT NULL
);
'''


def initialize(conn):
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('routeranker_schema_v1'))")
    conn.execute(SCHEMA)


def current_version(conn):
    row = conn.execute("SELECT value FROM rr_settings WHERE key='current_data_version'").fetchone()
    if not row:
        raise ValueError('No imported analysis bundle. Run python -m backend.import_data.')
    return row['value']
