# backend/db.py
"""SQLite database initialisation and connection helpers.

Creates the database file at config.DB_PATH and provides:
  - get_connection()   → returns a sqlite3.Connection with WAL mode
  - init_db()          → creates all tables idempotently
  - insert_collection_log()
  - insert_dataset_metadata()
  - insert_snapshot_record()
"""

import sqlite3
import logging
from backend.config import DB_PATH, BACKEND_LOG, LOG_DIR
import os

# ── Logging setup ────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=BACKEND_LOG,
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
)
logger = logging.getLogger(__name__)


# ── Connection factory ───────────────────────────────────────────
def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database with WAL journal mode."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row          # dict-like access
    return conn


# ── Schema creation (idempotent) ─────────────────────────────────
_SCHEMA_SQL = """
-- Metadata about each analytical CSV file discovered on disk
CREATE TABLE IF NOT EXISTS dataset_metadata (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT    NOT NULL,
    filepath        TEXT    NOT NULL,
    file_size_bytes INTEGER,
    row_count       INTEGER,
    columns         TEXT,               -- comma-separated column names
    sha256          TEXT,               -- hex digest
    modified_at     TEXT,               -- ISO-8601 file mtime
    ingested_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(filepath, sha256)            -- prevents duplicate records for unchanged files
);

-- Log of every collection / ingestion run
CREATE TABLE IF NOT EXISTS collection_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT    NOT NULL,       -- UUID for the run
    source      TEXT    NOT NULL,       -- e.g. 'csv_metadata', 'gtfs_snapshot'
    status      TEXT    NOT NULL,       -- 'success', 'skipped', 'error'
    message     TEXT,
    files_processed INTEGER DEFAULT 0,
    files_skipped   INTEGER DEFAULT 0,
    started_at  TEXT    NOT NULL,
    finished_at TEXT
);

-- History of GTFS snapshot downloads (future use)
CREATE TABLE IF NOT EXISTS snapshot_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date   TEXT    NOT NULL,   -- YYYY-MM-DD
    source_url      TEXT,
    files_included  TEXT,              -- comma-separated file names
    total_size_bytes INTEGER,
    sha256          TEXT,
    status          TEXT    NOT NULL DEFAULT 'pending',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(snapshot_date, sha256)
);
"""


def init_db() -> None:
    """Create all tables if they do not already exist."""
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        logger.info("Database initialised at %s", DB_PATH)
    finally:
        conn.close()


# ── Helper insert functions ──────────────────────────────────────
def insert_dataset_metadata(
    *,
    filename: str,
    filepath: str,
    file_size_bytes: int,
    row_count: int,
    columns: str,
    sha256: str,
    modified_at: str,
) -> bool:
    """Insert a dataset metadata row.  Returns True if inserted, False if duplicate."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO dataset_metadata
                (filename, filepath, file_size_bytes, row_count, columns, sha256, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (filename, filepath, file_size_bytes, row_count, columns, sha256, modified_at),
        )
        inserted = conn.total_changes > 0
        conn.commit()
        return inserted
    finally:
        conn.close()


def insert_collection_log(
    *,
    run_id: str,
    source: str,
    status: str,
    message: str = "",
    files_processed: int = 0,
    files_skipped: int = 0,
    started_at: str,
    finished_at: str = None,
) -> None:
    """Record a collection run in the log table."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO collection_log
                (run_id, source, status, message, files_processed, files_skipped, started_at, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, source, status, message, files_processed, files_skipped, started_at, finished_at),
        )
        conn.commit()
    finally:
        conn.close()


def insert_snapshot_record(
    *,
    snapshot_date: str,
    source_url: str = None,
    files_included: str = None,
    total_size_bytes: int = None,
    sha256: str = None,
    status: str = "pending",
) -> bool:
    """Insert a snapshot history row.  Returns True if inserted, False if duplicate."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO snapshot_history
                (snapshot_date, source_url, files_included, total_size_bytes, sha256, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (snapshot_date, source_url, files_included, total_size_bytes, sha256, status),
        )
        inserted = conn.total_changes > 0
        conn.commit()
        return inserted
    finally:
        conn.close()


# ── Run directly to initialise ───────────────────────────────────
if __name__ == "__main__":
    init_db()
    print(f"Database created / verified at: {DB_PATH}")
