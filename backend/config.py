# Configuration for Chennai MTC RouteRanker backend
"""Central configuration constants used by all backend modules."""

import os

# Base directory of the project (parent of backend/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# ── Data directories ──────────────────────────────────────────────
DATA_DIR = os.path.join(BASE_DIR, 'data')
GTFS_SNAPSHOT_DIR = os.path.join(DATA_DIR, 'gtfs_snapshots')
LOG_DIR = os.path.join(DATA_DIR, 'ingestion_logs')

# ── SQLite database (placed inside data/) ─────────────────────────
DB_PATH = os.path.join(DATA_DIR, 'mtc_gtfs.db')

# ── Existing analytical output directories (read-only) ────────────
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
ROUTE_CLUSTERING_DIR = os.path.join(BASE_DIR, 'route_clustering')

# ── Logging ───────────────────────────────────────────────────────
BACKEND_LOG = os.path.join(LOG_DIR, 'backend.log')

# Ensure directories exist at import time
for _d in (DATA_DIR, GTFS_SNAPSHOT_DIR, LOG_DIR):
    os.makedirs(_d, exist_ok=True)
