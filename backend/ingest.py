# backend/ingest.py
"""CSV metadata ingestion module.

Scans the project's analytical output directories (reports/, route_clustering/)
and records metadata about each CSV file into the SQLite database.

What is recorded per file:
  - filename, full path, file size, row count, column names, SHA-256, mtime

What is NOT done:
  - CSV contents are NOT copied into SQLite.
  - Original CSV files are NEVER modified or overwritten.
  - Duplicate records are prevented via the (filepath, sha256) UNIQUE constraint.
"""

import csv
import hashlib
import os
import uuid
from datetime import datetime, timezone

from backend.config import BASE_DIR, REPORTS_DIR, ROUTE_CLUSTERING_DIR
from backend.db import (
    init_db,
    insert_collection_log,
    insert_dataset_metadata,
    get_connection,
)

import logging
logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────
def _sha256(filepath: str) -> str:
    """Return hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def _csv_row_count(filepath: str) -> int:
    """Return number of data rows (excluding header) in a CSV file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return 0
            return sum(1 for _ in reader)
    except Exception:
        return -1


def _csv_columns(filepath: str) -> str:
    """Return comma-separated column names from the first row."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            return ','.join(header) if header else ''
    except Exception:
        return ''


def _iso_mtime(filepath: str) -> str:
    """Return the file's last-modified time as an ISO-8601 string."""
    ts = os.path.getmtime(filepath)
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# ── Core ingestion function ──────────────────────────────────────
def ingest_csv_metadata(directories: list[str] | None = None) -> dict:
    """Scan directories for CSV files and record their metadata.

    Parameters
    ----------
    directories : list[str] | None
        Directories to scan.  Defaults to REPORTS_DIR and ROUTE_CLUSTERING_DIR.

    Returns
    -------
    dict  with keys: run_id, files_processed, files_skipped, errors
    """
    if directories is None:
        directories = [REPORTS_DIR, ROUTE_CLUSTERING_DIR]

    # Ensure DB tables exist
    init_db()

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    files_processed = 0
    files_skipped = 0
    errors = []

    for directory in directories:
        if not os.path.isdir(directory):
            logger.warning("Directory does not exist, skipping: %s", directory)
            continue

        for root, _dirs, filenames in os.walk(directory):
            for fname in sorted(filenames):
                if not fname.lower().endswith('.csv'):
                    continue

                fpath = os.path.join(root, fname)
                try:
                    checksum = _sha256(fpath)
                    fsize = os.path.getsize(fpath)
                    rows = _csv_row_count(fpath)
                    cols = _csv_columns(fpath)
                    mtime = _iso_mtime(fpath)

                    inserted = insert_dataset_metadata(
                        filename=fname,
                        filepath=fpath,
                        file_size_bytes=fsize,
                        row_count=rows,
                        columns=cols,
                        sha256=checksum,
                        modified_at=mtime,
                    )

                    if inserted:
                        files_processed += 1
                        logger.info("Ingested metadata: %s (%d rows)", fname, rows)
                    else:
                        files_skipped += 1
                        logger.info("Skipped (unchanged): %s", fname)

                except Exception as exc:
                    errors.append(f"{fpath}: {exc}")
                    logger.error("Error processing %s: %s", fpath, exc)

    finished_at = datetime.now(timezone.utc).isoformat()

    # Record the run in the collection log
    insert_collection_log(
        run_id=run_id,
        source='csv_metadata',
        status='success' if not errors else 'partial',
        message='; '.join(errors) if errors else f'Processed {files_processed}, skipped {files_skipped}',
        files_processed=files_processed,
        files_skipped=files_skipped,
        started_at=started_at,
        finished_at=finished_at,
    )

    result = {
        'run_id': run_id,
        'files_processed': files_processed,
        'files_skipped': files_skipped,
        'errors': errors,
    }
    print(f"Ingestion complete: {files_processed} processed, {files_skipped} skipped, {len(errors)} errors")
    return result


# ── Also scan GTFS .txt files in the project root ────────────────
def ingest_gtfs_txt_metadata() -> dict:
    """Record metadata for the raw GTFS .txt files in the project root."""
    init_db()

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    files_processed = 0
    files_skipped = 0
    errors = []

    for fname in sorted(os.listdir(BASE_DIR)):
        if not fname.lower().endswith('.txt'):
            continue
        fpath = os.path.join(BASE_DIR, fname)
        if not os.path.isfile(fpath):
            continue

        try:
            checksum = _sha256(fpath)
            fsize = os.path.getsize(fpath)
            rows = _csv_row_count(fpath)        # GTFS .txt files are CSV-formatted
            cols = _csv_columns(fpath)
            mtime = _iso_mtime(fpath)

            inserted = insert_dataset_metadata(
                filename=fname,
                filepath=fpath,
                file_size_bytes=fsize,
                row_count=rows,
                columns=cols,
                sha256=checksum,
                modified_at=mtime,
            )
            if inserted:
                files_processed += 1
            else:
                files_skipped += 1
        except Exception as exc:
            errors.append(f"{fpath}: {exc}")

    finished_at = datetime.now(timezone.utc).isoformat()
    insert_collection_log(
        run_id=run_id,
        source='gtfs_txt_metadata',
        status='success' if not errors else 'partial',
        message=f'Processed {files_processed}, skipped {files_skipped}',
        files_processed=files_processed,
        files_skipped=files_skipped,
        started_at=started_at,
        finished_at=finished_at,
    )

    result = {
        'run_id': run_id,
        'files_processed': files_processed,
        'files_skipped': files_skipped,
        'errors': errors,
    }
    print(f"GTFS txt ingestion: {files_processed} processed, {files_skipped} skipped, {len(errors)} errors")
    return result


# ── CLI entry point ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Running CSV metadata ingestion...")
    print("=" * 60)
    r1 = ingest_csv_metadata()
    print()
    print("=" * 60)
    print("Running GTFS .txt metadata ingestion...")
    print("=" * 60)
    r2 = ingest_gtfs_txt_metadata()
    print()
    print("All ingestion runs complete.")
