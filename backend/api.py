# backend/api.py
"""Query layer for the backend SQLite database.

Provides reusable functions that return Python dicts / lists.
All functions handle a missing database or missing tables gracefully
by returning empty results rather than raising exceptions.
"""

import sqlite3
import os
import logging
from backend.config import DB_PATH

logger = logging.getLogger(__name__)


# ── Internal helper ──────────────────────────────────────────────
def _safe_query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a read query and return rows as list-of-dicts.
    Returns an empty list if the DB or table does not exist."""
    if not os.path.isfile(DB_PATH):
        logger.warning("Database file not found: %s", DB_PATH)
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except sqlite3.OperationalError as exc:
        # e.g. "no such table"
        logger.warning("Query failed (table may not exist): %s", exc)
        return []


# ── Public API ───────────────────────────────────────────────────

def get_all_datasets() -> list[dict]:
    """Return all dataset metadata records, newest first."""
    return _safe_query(
        "SELECT * FROM dataset_metadata ORDER BY ingested_at DESC"
    )


def get_dataset_by_filename(filename: str) -> list[dict]:
    """Return metadata records matching a filename (may be multiple versions)."""
    return _safe_query(
        "SELECT * FROM dataset_metadata WHERE filename = ? ORDER BY ingested_at DESC",
        (filename,),
    )


def get_dataset_summary() -> list[dict]:
    """Return one row per unique filename with latest ingested_at."""
    return _safe_query(
        """
        SELECT filename,
               filepath,
               file_size_bytes,
               row_count,
               columns,
               sha256,
               modified_at,
               MAX(ingested_at) AS latest_ingested_at
          FROM dataset_metadata
         GROUP BY filepath
         ORDER BY filename
        """
    )


def get_collection_history(limit: int = 50) -> list[dict]:
    """Return the most recent collection log entries."""
    return _safe_query(
        "SELECT * FROM collection_log ORDER BY started_at DESC LIMIT ?",
        (limit,),
    )


def get_latest_collection_status() -> dict | None:
    """Return the single most recent collection log entry, or None."""
    rows = _safe_query(
        "SELECT * FROM collection_log ORDER BY started_at DESC LIMIT 1"
    )
    return rows[0] if rows else None


def get_snapshot_history(limit: int = 50) -> list[dict]:
    """Return GTFS snapshot history entries."""
    return _safe_query(
        "SELECT * FROM snapshot_history ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )


def get_table_counts() -> dict:
    """Return a dict of {table_name: row_count} for all backend tables."""
    tables = ['dataset_metadata', 'collection_log', 'snapshot_history']
    result = {}
    for t in tables:
        rows = _safe_query(f"SELECT COUNT(*) AS cnt FROM {t}")
        result[t] = rows[0]['cnt'] if rows else 0
    return result


# ── CLI entry point ──────────────────────────────────────────────
if __name__ == "__main__":
    import json
    print("=== Table row counts ===")
    print(json.dumps(get_table_counts(), indent=2))
    print()
    print("=== Dataset summary ===")
    for ds in get_dataset_summary():
        print(f"  {ds['filename']:45s}  rows={ds['row_count']:>6}  size={ds['file_size_bytes']:>8} bytes")
    print()
    print("=== Latest collection status ===")
    status = get_latest_collection_status()
    print(json.dumps(status, indent=2) if status else "  (no collection runs yet)")
