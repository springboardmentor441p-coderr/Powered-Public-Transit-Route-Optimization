"""Small SQLite store for things the app creates while it runs.

Holds replay sessions, the forecasts each replay issues, and saved scenarios.
This is separate from app_data/, which stays read-only. The database file lives
in backend/runtime/ (gitignored) unless a different folder is passed in.

Forecast rows use a primary key of (session_id, target_date, route, hour), so a
forecast is written once and never overwritten, even if the same day is
requested again.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = ROOT / "backend" / "runtime"

SCHEMA = """
CREATE TABLE IF NOT EXISTS replay_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    clock_date TEXT NOT NULL,
    delay_days INTEGER NOT NULL,
    speed_seconds REAL NOT NULL,
    status TEXT NOT NULL,
    last_tick_wall REAL,
    model_version TEXT NOT NULL,
    schedule_snapshot TEXT NOT NULL,
    data_version TEXT NOT NULL,
    replaced_by TEXT
);

CREATE TABLE IF NOT EXISTS replay_forecasts (
    session_id TEXT NOT NULL,
    target_date TEXT NOT NULL,
    route TEXT NOT NULL,
    hour INTEGER NOT NULL,
    issued_at TEXT NOT NULL,
    saved_at_wall TEXT NOT NULL,
    latest_ridership_date_used TEXT NOT NULL,
    delay_days INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    schedule_snapshot TEXT NOT NULL,
    trips_running REAL,
    trips_starting REAL,
    service_hours REAL,
    lags_available_count INTEGER,
    pred_boardings REAL,
    baseline_boardings REAL,
    status TEXT NOT NULL,
    PRIMARY KEY (session_id, target_date, route, hour)
);

CREATE TABLE IF NOT EXISTS saved_scenarios (
    scenario_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    label TEXT,
    inputs_json TEXT NOT NULL,
    result_json TEXT NOT NULL
);
"""


class RuntimeStore:
    def __init__(self, runtime_dir: Path | None = None) -> None:
        self.runtime_dir = runtime_dir or DEFAULT_RUNTIME_DIR
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.runtime_dir / "routeranker_runtime.sqlite3"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add columns introduced after a database file was first created."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(replay_forecasts)").fetchall()}
        if "trips_starting" not in cols:
            self._conn.execute("ALTER TABLE replay_forecasts ADD COLUMN trips_starting REAL")

    # ---- generic helpers -------------------------------------------------
    def execute(self, sql: str, params: tuple | dict = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def executemany(self, sql: str, rows: list[tuple]) -> int:
        with self._lock:
            cur = self._conn.executemany(sql, rows)
            self._conn.commit()
            return cur.rowcount

    def query(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- saved scenarios -------------------------------------------------
    def save_scenario(
        self, scenario_id: str, created_at: str, label: str | None, inputs: dict, result: dict
    ) -> None:
        self.execute(
            "INSERT INTO saved_scenarios (scenario_id, created_at, label, inputs_json, result_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (scenario_id, created_at, label, json.dumps(inputs), json.dumps(result)),
        )

    def list_scenarios(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM saved_scenarios ORDER BY created_at DESC")
        out = []
        for r in rows:
            out.append(
                {
                    "scenario_id": r["scenario_id"],
                    "created_at": r["created_at"],
                    "label": r["label"],
                    "inputs": json.loads(r["inputs_json"]),
                    "result": json.loads(r["result_json"]),
                }
            )
        return out
