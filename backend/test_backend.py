# backend/test_backend.py
"""End-to-end test script for the backend package.

Tests:
  1. Database initialisation (tables created)
  2. CSV metadata ingestion (files discovered and recorded)
  3. Duplicate prevention (re-running ingestion should skip all files)
  4. GTFS .txt metadata ingestion
  5. Query layer functions (all return expected types)
  6. Table row counts match expectations
"""

import os
import sys
import json

# Ensure the project root is on sys.path so `backend` is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.config import DB_PATH, REPORTS_DIR, ROUTE_CLUSTERING_DIR, BASE_DIR
from backend.db import init_db, get_connection
from backend.ingest import ingest_csv_metadata, ingest_gtfs_txt_metadata
from backend import api


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def test_db_init():
    separator("TEST 1: Database Initialisation")

    # Remove old DB if present (clean test)
    if os.path.isfile(DB_PATH):
        os.remove(DB_PATH)
        print(f"  Removed old DB: {DB_PATH}")

    init_db()

    assert os.path.isfile(DB_PATH), f"DB file not created at {DB_PATH}"
    print(f"  DB file created: {DB_PATH}")

    conn = get_connection()
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r['name'] for r in cur.fetchall()]
    conn.close()

    expected = {'collection_log', 'dataset_metadata', 'snapshot_history'}
    found = set(tables)
    assert expected.issubset(found), f"Missing tables: {expected - found}"
    print(f"  Tables present: {sorted(tables)}")
    print("  PASS")


def test_csv_ingestion():
    separator("TEST 2: CSV Metadata Ingestion")

    result = ingest_csv_metadata()

    assert result['files_processed'] > 0, "No CSV files were processed"
    assert len(result['errors']) == 0, f"Errors occurred: {result['errors']}"
    print(f"  Run ID:          {result['run_id']}")
    print(f"  Files processed: {result['files_processed']}")
    print(f"  Files skipped:   {result['files_skipped']}")
    print(f"  Errors:          {len(result['errors'])}")
    print("  PASS")
    return result['files_processed']


def test_duplicate_prevention(expected_count: int):
    separator("TEST 3: Duplicate Prevention")

    result = ingest_csv_metadata()

    assert result['files_processed'] == 0, (
        f"Expected 0 new files on re-run, got {result['files_processed']}"
    )
    assert result['files_skipped'] == expected_count, (
        f"Expected {expected_count} skipped, got {result['files_skipped']}"
    )
    print(f"  Second run: {result['files_processed']} processed, {result['files_skipped']} skipped")
    print("  PASS — no duplicates inserted")


def test_gtfs_txt_ingestion():
    separator("TEST 4: GTFS .txt Metadata Ingestion")

    result = ingest_gtfs_txt_metadata()

    print(f"  GTFS files processed: {result['files_processed']}")
    print(f"  GTFS files skipped:   {result['files_skipped']}")
    print(f"  Errors:               {len(result['errors'])}")
    # We expect at least some .txt files (stops.txt, routes.txt, etc.)
    total = result['files_processed'] + result['files_skipped']
    assert total > 0, "No GTFS .txt files found in project root"
    print("  PASS")


def test_query_layer():
    separator("TEST 5: Query Layer Functions")

    # get_all_datasets
    datasets = api.get_all_datasets()
    assert isinstance(datasets, list), "get_all_datasets should return a list"
    assert len(datasets) > 0, "get_all_datasets returned empty"
    print(f"  get_all_datasets():          {len(datasets)} rows")

    # get_dataset_summary
    summary = api.get_dataset_summary()
    assert isinstance(summary, list), "get_dataset_summary should return a list"
    print(f"  get_dataset_summary():       {len(summary)} unique files")

    # get_collection_history
    history = api.get_collection_history()
    assert isinstance(history, list), "get_collection_history should return a list"
    assert len(history) >= 3, f"Expected >=3 collection runs, got {len(history)}"
    print(f"  get_collection_history():    {len(history)} runs")

    # get_latest_collection_status
    latest = api.get_latest_collection_status()
    assert latest is not None, "get_latest_collection_status returned None"
    assert 'status' in latest, "Missing 'status' key"
    print(f"  get_latest_collection_status(): status={latest['status']}")

    # get_snapshot_history (should be empty — no snapshots downloaded yet)
    snaps = api.get_snapshot_history()
    assert isinstance(snaps, list), "get_snapshot_history should return a list"
    print(f"  get_snapshot_history():      {len(snaps)} snapshots")

    # get_table_counts
    counts = api.get_table_counts()
    assert isinstance(counts, dict), "get_table_counts should return a dict"
    print(f"  get_table_counts():          {json.dumps(counts)}")

    # get_dataset_by_filename (pick first file from summary)
    if summary:
        fname = summary[0]['filename']
        rows = api.get_dataset_by_filename(fname)
        assert len(rows) >= 1, f"Expected at least 1 row for {fname}"
        print(f"  get_dataset_by_filename('{fname}'): {len(rows)} row(s)")

    print("  PASS")


def test_table_counts():
    separator("TEST 6: Table Row Counts Verification")

    counts = api.get_table_counts()
    assert counts['dataset_metadata'] > 0, "dataset_metadata table is empty"
    assert counts['collection_log'] >= 3, "Expected >=3 collection log entries"
    print(f"  dataset_metadata:  {counts['dataset_metadata']} rows")
    print(f"  collection_log:    {counts['collection_log']} rows")
    print(f"  snapshot_history:  {counts['snapshot_history']} rows")
    print("  PASS")


def print_dataset_detail():
    separator("DATASET DETAIL (for verification)")
    summary = api.get_dataset_summary()
    for ds in summary:
        print(f"  {ds['filename']:45s}  rows={ds['row_count']:>6}  "
              f"size={ds['file_size_bytes']:>8}B  sha256={ds['sha256'][:12]}...")


# ── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Chennai MTC RouteRanker — Backend Test Suite")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"DB path:      {DB_PATH}")

    passed = 0
    failed = 0

    try:
        test_db_init()
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    csv_count = 0
    try:
        csv_count = test_csv_ingestion()
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    try:
        test_duplicate_prevention(csv_count)
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    try:
        test_gtfs_txt_ingestion()
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    try:
        test_query_layer()
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    try:
        test_table_counts()
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1

    print_dataset_detail()

    separator("FINAL RESULTS")
    print(f"  Passed: {passed}/6")
    print(f"  Failed: {failed}/6")
    print(f"  Status: {'ALL TESTS PASSED' if failed == 0 else 'SOME TESTS FAILED'}")
    sys.exit(0 if failed == 0 else 1)
