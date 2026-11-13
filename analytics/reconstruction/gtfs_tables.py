"""Step 10: open one GTFS snapshot in DuckDB, keep buses, and build the public-route crosswalk (spec 9.5.1).

All identifiers stay strings and are scoped to their snapshot. GTFS route_id is internal; the public
identifier that matches the ridership `route` column is route_short_name (trimmed, case kept).
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

GTFS_FILES = ["routes", "trips", "calendar", "calendar_dates", "stop_times"]
BUS_ROUTE_TYPE = "3"


class CrosswalkError(ValueError):
    """The route_short_name -> route_id mapping is not one-to-one, so joining would be ambiguous."""


def normalize_route(s: pd.Series) -> pd.Series:
    """The single normalization used on BOTH sides of the join: trim surrounding whitespace, keep as string."""
    return s.astype("string").str.strip()


def _csv_view(con: duckdb.DuckDBPyConnection, name: str, path: Path) -> None:
    # all_varchar keeps IDs like "08" or "67801" as text; the BOM (if any) is removed from header names.
    con.execute(f"CREATE OR REPLACE TEMP VIEW raw_{name} AS SELECT * FROM read_csv('{path.as_posix()}', "
                "header=true, all_varchar=true, quote='\"', escape='\"', strict_mode=false)")
    cols = [r[0] for r in con.execute(f"DESCRIBE raw_{name}").fetchall()]
    select = ", ".join(f'trim("{c}") AS "{c.strip().lstrip(chr(0xFEFF))}"' for c in cols)
    con.execute(f"CREATE OR REPLACE TEMP VIEW {name} AS SELECT {select} FROM raw_{name}")


def open_snapshot(extracted_dir: Path) -> tuple[duckdb.DuckDBPyConnection, set[str]]:
    """Return a DuckDB connection with one view per present GTFS file (all values trimmed strings)."""
    con = duckdb.connect()
    present = set()
    for name in GTFS_FILES:
        p = Path(extracted_dir) / f"{name}.txt"
        if p.exists() and p.stat().st_size > 0:
            _csv_view(con, name, p)
            present.add(name)
    for name, cols in [("calendar", "service_id VARCHAR, monday VARCHAR, tuesday VARCHAR, wednesday VARCHAR, "
                                    "thursday VARCHAR, friday VARCHAR, saturday VARCHAR, sunday VARCHAR, "
                                    "start_date VARCHAR, end_date VARCHAR"),
                       ("calendar_dates", "service_id VARCHAR, date VARCHAR, exception_type VARCHAR")]:
        if name not in present:  # a valid feed may define service with only one of the two files
            con.execute(f"CREATE TEMP TABLE {name} ({cols})")
    missing = {"routes", "trips", "stop_times"} - present
    if missing:
        raise FileNotFoundError(f"{extracted_dir}: missing required GTFS files {sorted(missing)}")
    return con, present


def validate_crosswalk(cw: pd.DataFrame, snapshot_id: str) -> None:
    empty = cw["route"].isna() | (cw["route"] == "")
    if empty.any():
        raise CrosswalkError(f"{snapshot_id}: {int(empty.sum())} bus routes have an empty route_short_name: "
                             f"{cw.loc[empty, 'route_id'].tolist()[:10]}")
    for key in ["route", "route_id"]:
        dup = cw[cw.duplicated(key, keep=False)]
        if not dup.empty:
            raise CrosswalkError(f"{snapshot_id}: {key} is not unique among bus routes: "
                                 f"{dup.sort_values(key).values.tolist()[:10]}")


def bus_crosswalk(con: duckdb.DuckDBPyConnection, snapshot_id: str) -> pd.DataFrame:
    """Bus routes (route_type 3) of one snapshot: columns snapshot_id, route_id, route, route_long_name, has_trips."""
    cols = [r[0] for r in con.execute("DESCRIBE routes").fetchall()]
    long_name = "route_long_name" if "route_long_name" in cols else "NULL"
    cw = con.execute(f"""
        SELECT r.route_id, r.route_short_name AS route, {long_name} AS route_long_name,
               r.route_id IN (SELECT route_id FROM trips) AS has_trips
        FROM routes r WHERE r.route_type = '{BUS_ROUTE_TYPE}' ORDER BY r.route_id""").df()
    cw["route"] = normalize_route(cw["route"])
    cw.insert(0, "snapshot_id", snapshot_id)
    validate_crosswalk(cw, snapshot_id)
    con.register("_cw_df", cw)
    con.execute("CREATE OR REPLACE TEMP TABLE bus_cw AS SELECT * FROM _cw_df")
    con.unregister("_cw_df")
    return cw
