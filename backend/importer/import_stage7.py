"""Stage 7 (replay), step 1: add the replay tables and the forecast targets to an imported data version.

ADDITIVE ONLY: creates the tables in backend/db/schema_stage7.sql (if they are not there yet) and loads
forecast_targets from Stage 3's feature_rows.csv, after checking that file's sha256 and row count against
features_manifest.json. Only timetable columns are loaded (route, date, forecast snapshot, scheduled trips/hours,
Sunday-like flag, split): rides and lags are never stored, the replay recomputes them from daily_ridership.
A data version whose targets are already loaded is refused (nothing is overwritten).

From the repo root (CMD):
  python -I backend\\importer\\import_stage7.py                       (the app database, DATABASE_URL)
  python -I backend\\importer\\import_stage7.py --url-var TEST_DATABASE_URL
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # `python -I` skips the script folder; add our own repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402
import psycopg  # noqa: E402

from backend.importer.import_data import DEFAULTS, ImportRefused, load_json, read_env, sha256  # noqa: E402

SCHEMA7 = REPO_ROOT / "backend" / "db" / "schema_stage7.sql"
FEATURES = "features__delay1d"
TARGET_COLUMNS = ["route", "date", "schedule_saved", "scheduled_trips", "scheduled_hours", "sunday_like_day", "split"]


def stage7_tables_exist(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT to_regclass('public.forecast_targets') IS NOT NULL").fetchone()[0]


def create_stage7_schema(conn: psycopg.Connection) -> None:
    """Apply the additive Stage 7 tables once. The Stage 6 tables must already exist."""
    if conn.execute("SELECT to_regclass('public.dataset_versions') IS NULL").fetchone()[0]:
        raise ImportRefused("the Stage 6 schema is missing: run backend/importer/import_data.py first")
    if not stage7_tables_exist(conn):
        conn.execute(SCHEMA7.read_text(encoding="utf-8"))


def read_targets(version_dir: Path) -> tuple[pd.DataFrame, dict]:
    """feature_rows.csv, verified against its manifest, reduced to the timetable columns."""
    fdir = version_dir / FEATURES
    man = load_json(fdir / "features_manifest.json")
    rec = man["outputs"]["feature_rows.csv"]
    path = fdir / "feature_rows.csv"
    actual = sha256(path)
    if actual != rec["sha256"]:
        raise ImportRefused(f"feature_rows.csv: sha256 {actual[:12]}... differs from its manifest {rec['sha256'][:12]}...")
    df = pd.read_csv(path, usecols=TARGET_COLUMNS, dtype={"route": str, "schedule_saved": str, "split": str})
    if len(df) != rec["rows"]:
        raise ImportRefused(f"feature_rows.csv has {len(df)} rows, its manifest says {rec['rows']}")
    if df.duplicated(["route", "date"]).any():
        raise ImportRefused("feature_rows.csv must have one row per route/date")
    if df["scheduled_trips"].isna().any() or df["schedule_saved"].isna().any():
        raise ImportRefused("every forecast target needs its forecast-time schedule (trips and snapshot)")
    return df, {"sha256": actual, "rows": int(rec["rows"]), "features_version": man["data_version"]}


def import_targets(conn: psycopg.Connection, data_version: str, df: pd.DataFrame) -> int:
    """Load the targets for one data version in one transaction; refuse if that version already has targets."""
    if conn.execute("SELECT count(*) FROM forecast_targets WHERE data_version = %s", (data_version,)).fetchone()[0]:
        raise ImportRefused(f"forecast targets for {data_version} are already imported")
    rows = [(data_version, r.route, r.date, r.schedule_saved, float(r.scheduled_trips),
             None if pd.isna(r.scheduled_hours) else float(r.scheduled_hours), bool(r.sunday_like_day), r.split)
            for r in df.itertuples(index=False)]
    with conn.transaction():
        with conn.cursor().copy("""COPY forecast_targets (data_version, route, target_date, forecast_snapshot,
                                   scheduled_trips, scheduled_hours, sunday_like_day, split) FROM STDIN""") as cp:
            for row in rows:
                cp.write_row(row)
    return len(rows)


def install(conn: psycopg.Connection, version_dir: Path = DEFAULTS["version_dir"]) -> dict:
    """Schema + targets for the data version in `version_dir` (the folder name is the data version)."""
    data_version = version_dir.name
    if not conn.execute("SELECT 1 FROM dataset_versions WHERE data_version = %s", (data_version,)).fetchone():
        raise ImportRefused(f"data version {data_version} is not imported: run import_data.py first")
    df, meta = read_targets(version_dir)
    create_stage7_schema(conn)
    n = import_targets(conn, data_version, df)
    return {"data_version": data_version, "targets": n, **meta}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, default=REPO_ROOT / "backend" / ".env")
    ap.add_argument("--url-var", default="DATABASE_URL")
    ap.add_argument("--version-dir", type=Path, default=DEFAULTS["version_dir"])
    args = ap.parse_args()
    url = read_env(args.env).get(args.url_var)
    if not url:
        raise SystemExit(f"{args.url_var} is not set in {args.env}")
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            out = install(conn, args.version_dir)
    except ImportRefused as e:
        raise SystemExit(f"STAGE 7 IMPORT REFUSED, nothing was changed: {e}")
    print(f"forecast targets imported: {out['targets']:,} rows for {out['data_version']} "
          f"(feature_rows.csv sha256 {out['sha256'][:12]}...)")


if __name__ == "__main__":
    main()
