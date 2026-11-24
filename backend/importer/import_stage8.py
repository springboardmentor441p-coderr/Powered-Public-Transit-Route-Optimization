r"""Stage 8 (scenarios): add the scenarios table to a database that already holds the Stage 6 and Stage 7 tables.

ADDITIVE ONLY: runs backend/db/schema_stage8.sql once (if the table is not there yet). No data is loaded.

From the repo root (CMD):
  python -I backend\importer\import_stage8.py                       (the app database, DATABASE_URL)
  python -I backend\importer\import_stage8.py --url-var TEST_DATABASE_URL
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # `python -I` skips the script folder; add our own repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import psycopg  # noqa: E402

from backend.importer.import_data import ImportRefused, read_env  # noqa: E402

SCHEMA8 = REPO_ROOT / "backend" / "db" / "schema_stage8.sql"
TEST_DATABASE = "routeranker_test"


def stage8_tables_exist(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT to_regclass('public.scenarios') IS NOT NULL").fetchone()[0]


def create_stage8_schema(conn: psycopg.Connection) -> bool:
    """Apply the Stage 8 table once; True if it was created now. The Stage 6 and 7 tables must exist."""
    if conn.execute("SELECT to_regclass('public.replay_sessions') IS NULL").fetchone()[0]:
        raise ImportRefused("the Stage 7 tables are missing: run backend/importer/import_stage7.py first")
    if stage8_tables_exist(conn):
        return False
    conn.execute(SCHEMA8.read_text(encoding="utf-8"))
    return True


def reset_test_scenarios(conn: psycopg.Connection) -> None:
    """TEST DATABASE ONLY: empty the scenarios table (TRUNCATE does not fire the row trigger). Refused anywhere else,
    so the app database's saved scenarios can never be removed by a check."""
    name = conn.execute("SELECT current_database()").fetchone()[0]
    if name != TEST_DATABASE:
        raise ImportRefused(f"scenarios may only be reset in {TEST_DATABASE}, not in {name}")
    conn.execute("TRUNCATE scenarios")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, default=REPO_ROOT / "backend" / ".env")
    ap.add_argument("--url-var", default="DATABASE_URL")
    ap.add_argument("--reset-test", action="store_true", help=f"empty the scenarios table ({TEST_DATABASE} only)")
    args = ap.parse_args()
    url = read_env(args.env).get(args.url_var)
    if not url:
        raise SystemExit(f"{args.url_var} is not set in {args.env}")
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            created = create_stage8_schema(conn)
            if args.reset_test:
                reset_test_scenarios(conn)
            n = conn.execute("SELECT count(*) FROM scenarios").fetchone()[0]
            db = conn.execute("SELECT current_database()").fetchone()[0]
    except ImportRefused as e:
        raise SystemExit(f"STAGE 8 REFUSED, nothing was changed: {e}")
    print(f"{db}: scenarios table {'created' if created else 'already present'}; {n} saved scenarios")


if __name__ == "__main__":
    main()
