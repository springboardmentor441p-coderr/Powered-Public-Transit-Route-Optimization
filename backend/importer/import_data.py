"""Stage 6a, Step 58: import one data version into PostgreSQL (spec 9.17.2, 9.19.2 "import data").

Order of work:
  1. verify every input against its manifest (sha256 and row count) BEFORE touching the database;
  2. refuse a data_version that is already imported (versions sit side by side; nothing is overwritten);
  3. load every table with COPY inside ONE transaction;
  4. re-check the Stage 2/5 identities in SQL on the loaded rows; any failure rolls everything back;
  5. store the import report in dataset_versions and write it as Markdown.

Values from the processed CSVs go to PostgreSQL as their exact CSV text (an empty cell -> NULL), so each number is
parsed once, by the database, from what Stage 2/5 wrote; a value that does not fit its column type fails the import.
Stop-ID cells become text[] ("" -> {}, never {""}). In route_group_membership.csv, group "ungrouped" -> NULL
group_id (the reason stays in its own column); any other non-numeric group value is refused.

From the repo root (CMD), first time on an empty database:
  python -I backend\\importer\\import_data.py --create-schema
Later versions (schema already present):
  python -I backend\\importer\\import_data.py --version-dir data\\processed\\<data_version>
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # `python -I` skips the script folder; add our own repo root
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402
import psycopg  # noqa: E402

from analytics.models.train_stage4a import now  # noqa: E402
from analytics.reconstruction.build_stage2 import git_commit, sha256  # noqa: E402
from analytics.reconstruction.gtfs_tables import bus_crosswalk, open_snapshot  # noqa: E402
from analytics.reconstruction.matching import load_ridership  # noqa: E402

GROUPS = "groups__dev20251123_20260331"
SCHEMA = REPO_ROOT / "backend" / "db" / "schema.sql"
DEFAULTS = {
    "version_dir": REPO_ROOT / "data/processed/cta_ref__r20261113__gtfs8__to20260731",
    "register": REPO_ROOT / "reports/source_register.csv",
    "sources": REPO_ROOT / "analytics/config/sources.json",
    "group_names": REPO_ROOT / "analytics/config/group_names.json",
    "stage5_manifest": REPO_ROOT / "artifacts/stage5/groups_manifest.json",
    "model_manifest": REPO_ROOT / "artifacts/stage4a/model_manifest.json",
}
STOP_ARRAYS = {"served_stop_ids", "exclusive_stop_ids", "shared_stop_ids"}
UNGROUPED = "ungrouped"


class ImportRefused(RuntimeError):
    """The import must not run or must not be kept: already imported, an input changed, or an identity failed."""


@dataclass
class Table:
    name: str
    columns: list[str]        # target columns, in row order
    rows: list[tuple]
    scope: tuple[str, str]    # (version column, value): counts after loading are taken within this version
    source: str


# ------------------------------------------------------------------ reading inputs (no database)
def read_env(path: Path) -> dict[str, str]:
    return dict(line.strip().split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                if "=" in line and not line.lstrip().startswith("#"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_text(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """Every cell as its exact text; nothing is converted or guessed."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)
    if columns is not None and list(df.columns) != columns:
        raise ImportRefused(f"{path.name}: columns {list(df.columns)} differ from the expected {columns}")
    return df


def cells(df: pd.DataFrame, cols: list[str], prefix: tuple = ()) -> list[tuple]:
    """CSV text -> COPY values: '' -> None (NULL); stop-ID columns split on ';' with '' -> [] (never [''])."""
    arrays = [c in STOP_ARRAYS for c in cols]
    return [prefix + tuple((v.split(";") if v else []) if arr else (v if v != "" else None)
                           for v, arr in zip(rec, arrays))
            for rec in df[cols].itertuples(index=False, name=None)]


def membership_group_ids(df: pd.DataFrame) -> pd.DataFrame:
    """group 'ungrouped' -> '' (NULL group_id; the reason column keeps why). Any other value must be a whole number."""
    g = df["group"]
    bad = sorted(set(g[(g != UNGROUPED) & ~g.str.fullmatch(r"\d+")]))
    if bad:
        raise ImportRefused(f"route_group_membership.csv: non-numeric group values {bad} (only '{UNGROUPED}' "
                            "is allowed besides group numbers)")
    return df.assign(group=g.where(g != UNGROUPED, ""))


class Verifier:
    """Re-hashes each input and compares it with the sha (and row count) its manifest recorded."""

    def __init__(self) -> None:
        self.files: dict[str, dict] = {}

    def check(self, label: str, path: Path, expected_sha: str, expected_rows: int | None = None) -> Path:
        actual = sha256(path)
        if actual != expected_sha:
            raise ImportRefused(f"{label}: sha256 {actual[:12]}... differs from its manifest {expected_sha[:12]}...")
        self.files[label] = {"path": str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/"),
                             "sha256": actual, "manifest_rows": expected_rows}
        return path


def collect(p: dict) -> tuple[list[Table], dict]:
    """Verify every input and build every table's rows in memory. Touches no database."""
    vdir, gdir = p["version_dir"], p["version_dir"] / GROUPS
    man, gman = load_json(vdir / "manifest.json"), load_json(gdir / "groups_data_manifest.json")
    geo = load_json(vdir / "geometry" / "geometry_manifest.json")
    s5, m4 = load_json(p["stage5_manifest"]), load_json(p["model_manifest"])
    names, sources = load_json(p["group_names"]), load_json(p["sources"])
    dv, gv = man["data_version"], gman["data_version"]
    if dv != vdir.name or gv != f"{dv}/{GROUPS}" or geo["data_version"] != f"{dv}/geometry":
        raise ImportRefused(f"manifest versions {dv!r}, {gv!r}, {geo['data_version']!r} do not match {vdir.name!r}")
    v = Verifier()

    # ---- processed products: sha256 and row counts from their own manifests
    for name, rec in man["outputs"].items():
        v.check(name, vdir / name, rec["sha256"], rec["rows"])
    for name, rec in gman["outputs"].items():
        v.check(f"{GROUPS}/{name}", gdir / name, rec["sha256"], rec["rows"])
    geo_rec = geo["outputs"]["route_shapes.csv"]
    v.check("geometry/route_shapes.csv", vdir / "geometry" / "route_shapes.csv", geo_rec["sha256"], geo_rec["rows"])
    if s5["data_products"]["outputs"] != gman["outputs"]:
        raise ImportRefused("Stage 5 artifact manifest and groups data manifest describe different products")
    v.check("group_names.json", p["group_names"], gman["names_sha256"])
    v.check("route_groups.joblib", REPO_ROOT / s5["file"]["file"], s5["file"]["sha256"])
    pipe = m4["serving_bundle"]["pipeline_file"]
    v.check(pipe, REPO_ROOT / m4["files"][pipe]["file"], m4["files"][pipe]["sha256"])

    # ---- raw sources: register sha == Stage 2 manifest fingerprint == bytes on disk
    with open(p["register"], newline="", encoding="utf-8") as f:
        register = list(csv.DictReader(f))
    if {r["snapshot_id"] for r in register} != set(man["input_fingerprints"]):
        raise ImportRefused("source register and Stage 2 manifest list different sources")
    for r in register:
        if r["sha256"] != man["input_fingerprints"][r["snapshot_id"]]:
            raise ImportRefused(f"{r['snapshot_id']}: register sha differs from the Stage 2 manifest")
        v.check(r["snapshot_id"], REPO_ROOT / r["local_path"], r["sha256"])
    tables: list[Table] = []
    scope = ("data_version", dv)

    tables.append(Table("source_files", ["data_version", "snapshot_id", "dataset_id", "source_url", "sha256",
                                         "byte_size", "downloaded_at", "row_count", "expected_sha256",
                                         "fingerprint_match"],
                        cells(pd.DataFrame(register), ["snapshot_id", "dataset_id", "source_url", "sha256", "byte_size",
                                                       "downloaded_at", "row_count", "expected_sha256",
                                                       "fingerprint_match"], (dv,)),
                        scope, "reports/source_register.csv"))
    tables.append(Table("gtfs_snapshots", ["data_version", "snapshot_id", "captured_date", "active_start", "active_end",
                                           "applied_start", "applied_end"],
                        [(dv, a["snapshot_id"], a["captured"], *a["active_window"], *a["applied_dates"])
                         for a in sources["gtfs"]["archives"]], scope, "analytics/config/sources.json"))

    # ---- routes: bus routes of each archive's routes.txt (the ZIP was verified above)
    reg = {r["snapshot_id"]: r for r in register}
    route_rows, route_ids = [], {}
    for a in sources["gtfs"]["archives"]:
        sid = a["snapshot_id"]
        con, _ = open_snapshot((REPO_ROOT / reg[sid]["local_path"]).parent / "extracted")
        try:
            cw = bus_crosswalk(con, sid)
        finally:
            con.close()
        for r in cw.itertuples(index=False):
            long_name = None if pd.isna(r.route_long_name) or r.route_long_name == "" else r.route_long_name
            route_rows.append((dv, sid, r.route, r.route_id, r.route, long_name))
            route_ids[(sid, r.route)] = r.route_id
    tables.append(Table("routes", ["data_version", "geometry_version", "route", "route_id", "route_short_name",
                                   "route_long_name"], route_rows, scope, "GTFS routes.txt (bus, per archive)"))

    shapes = csv_text(vdir / "geometry" / "route_shapes.csv")
    wrong_id = [(g, r) for g, r, i in zip(shapes["geometry_version"], shapes["route"], shapes["route_id"])
                if route_ids.get((g, r)) != i]
    if wrong_id:
        raise ImportRefused(f"route_shapes route_id differs from routes.txt for {wrong_id[:5]}")
    shape_cols = ["geometry_version", "route", "direction_id", "direction_label", "shape_id", "trip_days_using_shape",
                  "active_trip_days", "trips_using_shape", "active_trips", "tied_top_shapes", "point_count",
                  "line_geojson"]
    tables.append(Table("route_shapes", ["data_version", *shape_cols], cells(shapes, shape_cols, (dv,)), scope,
                        "geometry/route_shapes.csv"))

    # ---- full daily ridership (Stage 2's own parser), cut at the data version's ridership cutoff
    rid_sid = next(r["snapshot_id"] for r in register if r["dataset_id"] == sources["ridership"]["dataset_id"])
    rides, parse = load_ridership(REPO_ROOT / reg[rid_sid]["local_path"])
    cutoff = date.fromisoformat(man["ridership_cutoff"])
    after = rides["date"] > cutoff
    kept = rides[~after]
    if kept["rides"].isna().any():
        raise ImportRefused(f"{int(kept['rides'].isna().sum())} ridership rows have no rides value")
    if not kept["daytype"].isin(["W", "A", "U"]).all():
        raise ImportRefused(f"unexpected daytypes {sorted(set(kept['daytype']) - {'W', 'A', 'U'})}")
    tables.append(Table("daily_ridership", ["data_version", "route", "service_date", "daytype", "rides",
                                            "source_snapshot_id"],
                        [(dv, r, d.isoformat(), t, int(n), rid_sid)
                         for r, d, t, n in kept[["route", "date", "daytype", "rides"]].itertuples(index=False)],
                        scope, reg[rid_sid]["local_path"]))
    ridership = {**parse, "kept_rows": len(kept), "excluded_after_cutoff": int(after.sum()),
                 "excluded_first_date": str(rides.loc[after, "date"].min()) if after.any() else None,
                 "excluded_last_date": str(rides.loc[after, "date"].max()) if after.any() else None,
                 "kept_first_date": str(kept["date"].min()), "kept_last_date": str(kept["date"].max()),
                 "kept_routes": int(kept["route"].nunique()), "kept_zero_ride_rows": int((kept["rides"] == 0).sum()),
                 "spec_reference": sources["ridership"]["spec_reference"]}

    # ---- Stage 2 daily tables ("date" in the CSVs = the GTFS service date)
    def stage2(name: str, table: str, csv_cols: list[str], drop: list[str] | None = None) -> None:
        df = csv_text(vdir / name)
        for col in drop or []:
            if (df[col] != "").any():
                raise ImportRefused(f"{name}: column {col} is expected to be empty on every row")
        target = ["data_version", *["service_date" if c == "date" else c for c in csv_cols]]
        tables.append(Table(table, target, cells(df, csv_cols, (dv,)), scope, name))

    stage2("expanded_scheduled_route_day_service.csv", "daily_schedule",
           ["route", "date", "snapshot_id", "route_id", "scheduled_trips", "scheduled_service_hours",
            "duration_complete", "trips_missing_duration"])
    stage2("expanded_matched_utilization.csv", "matched_utilization",
           ["route", "date", "daytype", "rides", "snapshot_id", "route_id", "scheduled_trips",
            "scheduled_service_hours", "duration_complete", "trips_missing_duration", "rides_per_scheduled_trip",
            "rides_per_scheduled_hour"])
    stage2("expanded_ridership_without_schedule.csv", "ridership_without_schedule",
           ["route", "date", "daytype", "rides", "selected_snapshot_id", "unmatched_reason",
            "identifier_absent_from_all_archives"])
    stage2("expanded_schedule_without_ridership.csv", "schedule_without_ridership",
           ["route", "date", "missing_reason"], drop=["rides"])

    # ---- Stage 5 products
    gscope = ("group_version", gv)
    tables.append(Table("group_versions", ["group_version", "data_version", "artifact_version", "artifact_sha256",
                                           "profile_start", "profile_end", "k", "features", "group_names", "caveats",
                                           "default_overlap_version", "settings_sha256", "names_sha256", "manifest",
                                           "built_git_commit"],
                        [(gv, dv, s5["artifact_version"], s5["file"]["sha256"], *s5["profile_period"], str(s5["k"]),
                          json.dumps(s5["features"]), json.dumps(s5["group_names"]), json.dumps(names["caveats"]),
                          s5["default_overlap_version"], gman["settings_sha256"], gman["names_sha256"],
                          json.dumps(s5), s5["git_commit"])],
                        gscope, "artifacts/stage5/groups_manifest.json + analytics/config/group_names.json"))
    for name, table, rename, prepare in [
            ("expanded_utilization_profiles.csv", "utilization_profiles", {}, None),
            ("route_profiles.csv", "route_profiles", {}, None),
            ("route_group_membership.csv", "group_memberships", {"group": "group_id"}, membership_group_ids),
            ("route_stop_coverage.csv", "route_stop_coverage", {}, None),
            ("route_stop_overlap.csv", "route_stop_overlap", {}, None)]:
        df = csv_text(gdir / name)
        if prepare is not None:
            df = prepare(df)
        cols = list(df.columns)
        tables.append(Table(table, ["group_version", *[rename.get(c, c) for c in cols]], cells(df, cols, (gv,)),
                            gscope, f"{GROUPS}/{name}"))

    # ---- model metadata (the .joblib itself stays in artifacts/)
    tables.append(Table("model_versions", ["model_version", "data_version", "selected_method", "pipeline_location",
                                           "pipeline_sha256", "frozen_at", "manifest", "built_git_commit"],
                        [(m4["artifact_version"], m4["data_version"], m4["selected_method"],
                          m4["files"][pipe]["file"], m4["files"][pipe]["sha256"], m4["frozen_at"], json.dumps(m4),
                          m4["git_commit"])],
                        ("model_version", m4["artifact_version"]), "artifacts/stage4a/model_manifest.json"))

    # ---- every table's row count must equal what its manifest recorded
    expected = {"daily_schedule": "expanded_scheduled_route_day_service.csv",
                "matched_utilization": "expanded_matched_utilization.csv",
                "ridership_without_schedule": "expanded_ridership_without_schedule.csv",
                "schedule_without_ridership": "expanded_schedule_without_ridership.csv",
                "route_shapes": "geometry/route_shapes.csv",
                **{t: f"{GROUPS}/{f}" for t, f in [("utilization_profiles", "expanded_utilization_profiles.csv"),
                                                  ("route_profiles", "route_profiles.csv"),
                                                  ("group_memberships", "route_group_membership.csv"),
                                                  ("route_stop_coverage", "route_stop_coverage.csv"),
                                                  ("route_stop_overlap", "route_stop_overlap.csv")]}}
    for t in tables:
        if t.name in expected and len(t.rows) != v.files[expected[t.name]]["manifest_rows"]:
            raise ImportRefused(f"{t.name}: {len(t.rows)} rows, manifest says {v.files[expected[t.name]]['manifest_rows']}")

    meta = {"data_version": dv, "group_version": gv, "model_version": m4["artifact_version"], "stage2_manifest": man,
            "inputs": v.files, "ridership": ridership, "reconciliation": man["reconciliation"],
            "geometry": {k: geo[k] for k in ["label", "definition", "tie_rule", "tie_label", "coordinate_order"]}}
    return tables, meta


# ------------------------------------------------------------------ the database
IDENTITIES = {  # each query counts VIOLATING rows; every one must return 0
    "matched rows agree with daily_ridership (daytype, rides)": """
        SELECT count(*) FROM matched_utilization m JOIN daily_ridership r USING (data_version, route, service_date)
        WHERE m.data_version = %(dv)s AND (m.daytype <> r.daytype OR m.rides <> r.rides)""",
    "matched rows agree with daily_schedule": """
        SELECT count(*) FROM matched_utilization m JOIN daily_schedule s USING (data_version, route, service_date)
        WHERE m.data_version = %(dv)s AND (m.snapshot_id <> s.snapshot_id OR m.route_id <> s.route_id
              OR m.scheduled_trips <> s.scheduled_trips OR m.duration_complete <> s.duration_complete
              OR m.scheduled_service_hours IS DISTINCT FROM s.scheduled_service_hours)""",
    "ridership_without_schedule rows agree with daily_ridership": """
        SELECT count(*) FROM ridership_without_schedule w JOIN daily_ridership r USING (data_version, route, service_date)
        WHERE w.data_version = %(dv)s AND (w.daytype <> r.daytype OR w.rides <> r.rides)""",
    "no ridership_without_schedule row has a schedule row": """
        SELECT count(*) FROM ridership_without_schedule w JOIN daily_schedule s USING (data_version, route, service_date)
        WHERE w.data_version = %(dv)s""",
    "no schedule_without_ridership row has a ridership row": """
        SELECT count(*) FROM schedule_without_ridership w JOIN daily_ridership r USING (data_version, route, service_date)
        WHERE w.data_version = %(dv)s""",
    "ridership in the analysis window = matched + ridership_without_schedule (difference)": """
        SELECT (SELECT count(*) FROM daily_ridership r JOIN dataset_versions d USING (data_version)
                WHERE r.data_version = %(dv)s AND r.service_date BETWEEN d.analysis_start AND d.analysis_end)
             - (SELECT count(*) FROM matched_utilization WHERE data_version = %(dv)s)
             - (SELECT count(*) FROM ridership_without_schedule WHERE data_version = %(dv)s)""",
    "schedule = matched + schedule_without_ridership (difference)": """
        SELECT (SELECT count(*) FROM daily_schedule WHERE data_version = %(dv)s)
             - (SELECT count(*) FROM matched_utilization WHERE data_version = %(dv)s)
             - (SELECT count(*) FROM schedule_without_ridership WHERE data_version = %(dv)s)""",
    "every schedule date lies within its snapshot's applied dates": """
        SELECT count(*) FROM daily_schedule s JOIN gtfs_snapshots g USING (data_version, snapshot_id)
        WHERE s.data_version = %(dv)s AND s.service_date NOT BETWEEN g.applied_start AND g.applied_end""",
    "profile observed days and ride sums equal the matched rows of their period": """
        SELECT count(*) FROM utilization_profiles p
        CROSS JOIN LATERAL (SELECT count(*) AS n, sum(m.rides) AS s FROM matched_utilization m
                            WHERE m.data_version = %(dv)s AND m.route = p.route AND m.daytype = p.daytype
                              AND m.service_date BETWEEN p.period_start AND p.period_end) a
        WHERE p.group_version = %(gv)s AND (p.observed_days <> a.n OR p.rides_sum IS DISTINCT FROM a.s)""",
}


def create_schema(conn: psycopg.Connection) -> None:
    n = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'").fetchone()[0]
    if n:
        raise ImportRefused(f"--create-schema needs an empty database; it already has {n} tables")
    conn.execute(SCHEMA.read_text(encoding="utf-8"))  # the file has its own BEGIN/COMMIT


def write(conn: psycopg.Connection, tables: list[Table], meta: dict) -> dict:
    """Everything inside ONE transaction: an exception anywhere leaves the database exactly as it was."""
    dv, gv, man = meta["data_version"], meta["group_version"], meta["stage2_manifest"]
    t0 = time.perf_counter()
    with conn.transaction():
        if conn.execute("SELECT 1 FROM dataset_versions WHERE data_version = %s", (dv,)).fetchone():
            raise ImportRefused(f"{dv} is already imported; a changed export must become a new data version")
        conn.execute("""INSERT INTO dataset_versions (data_version, spec_version, analysis_start, analysis_end,
                            ridership_cutoff, built_at, built_git_commit, manifest, import_git_commit, import_report)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '{}')""",
                     (dv, man["spec_version"], *man["analysis_period"], man["ridership_cutoff"], man["created_at"],
                      man["git_commit"], json.dumps(man), git_commit()))
        loaded = {}
        for t in tables:
            with conn.cursor().copy(f"COPY {t.name} ({', '.join(t.columns)}) FROM STDIN") as cp:
                for row in t.rows:
                    cp.write_row(row)
            col, value = t.scope
            n = conn.execute(f"SELECT count(*) FROM {t.name} WHERE {col} = %s", (value,)).fetchone()[0]
            if n != len(t.rows):
                raise ImportRefused(f"{t.name}: {n} rows in the database after COPY, {len(t.rows)} sent")
            loaded[t.name] = {"rows": n, "source": t.source}
        identities = {name: conn.execute(sql, {"dv": dv, "gv": gv}).fetchone()[0] for name, sql in IDENTITIES.items()}
        failed = {k: v for k, v in identities.items() if v != 0}
        if failed:
            raise ImportRefused(f"identities failed after loading (rolled back): {failed}")
        report = {"data_version": dv, "imported_at": now(), "import_git_commit": git_commit(),
                  "schema_sha256": sha256(SCHEMA), "tables": loaded, "identities": identities,
                  "seconds": round(time.perf_counter() - t0, 1),
                  **{k: meta[k] for k in ["group_version", "model_version", "inputs", "ridership", "reconciliation",
                                          "geometry"]}}
        conn.execute("UPDATE dataset_versions SET import_report = %s WHERE data_version = %s", (json.dumps(report), dv))
    return report


def _rows(n: int | None) -> str:
    return "" if n is None else f"{n:,}"


def write_markdown(report: dict, path: Path) -> None:
    r = report["ridership"]
    ref = r["spec_reference"]
    lines = [
        f"# Stage 6a import report: `{report['data_version']}`", "",
        f"Imported {report['imported_at']} by commit `{report['import_git_commit']}` in {report['seconds']} s. "
        f"Schema sha256 `{report['schema_sha256'][:16]}…`. All loading ran in one transaction.", "",
        "## Tables", "", "| table | rows | source |", "|---|---:|---|",
        *[f"| `{t}` | {v['rows']:,} | {v['source']} |" for t, v in report["tables"].items()], "",
        "## Daily ridership (full history)", "",
        f"- raw export rows {r['raw_rows']:,}; exact duplicates removed {r['exact_duplicates_removed']}",
        f"- **kept** {r['kept_rows']:,} rows, {r['kept_first_date']} → {r['kept_last_date']}, {r['kept_routes']} route "
        f"identifiers, {r['kept_zero_ride_rows']} recorded zeros (kept as 0)",
        f"- **excluded** {r['excluded_after_cutoff']:,} rows after the ridership cutoff "
        f"({r['excluded_first_date']} → {r['excluded_last_date']}); they belong to a later data version",
        f"- spec 9.3.1 reference (compared, never forced): records {ref['records']:,}, identifiers "
        f"{ref['route_identifiers']}, {ref['first_date']} → {ref['last_date']}, zeros {ref['zero_count_records']}", "",
        "## Identities re-checked in SQL after loading (violations; all must be 0)", "",
        "| identity | violations |", "|---|---:|",
        *[f"| {k} | {v} |" for k, v in report["identities"].items()], "",
        "## Inputs verified before loading (sha256 against their manifests)", "",
        "| input | sha256 | manifest rows |", "|---|---|---:|",
        *[f"| `{k}` | `{v['sha256'][:16]}…` | {_rows(v['manifest_rows'])} |" for k, v in report["inputs"].items()], "",
        "## Geometry", "",
        f"- label: **{report['geometry']['label']}**; tie label: \"{report['geometry']['tie_label']}\"; "
        f"coordinates {report['geometry']['coordinate_order']}",
        f"- definition: {report['geometry']['definition']}", "",
        "## Limitations", "",
        "- Extracted GTFS `.txt` files are read after their ZIP's sha256 is verified; they are not re-hashed "
        "(as in Stages 2 and 5).",
        "- The Stage 3 feature tables are not imported yet; Stage 7 (replay) adds them.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, default=REPO_ROOT / "backend" / ".env")
    ap.add_argument("--url-var", default="DATABASE_URL", help="which variable in --env holds the connection URL")
    ap.add_argument("--create-schema", action="store_true", help="apply backend/db/schema.sql to an EMPTY database")
    ap.add_argument("--report", type=Path, default=REPO_ROOT / "reports" / "stage6_import_report.md")
    for k, d in DEFAULTS.items():
        ap.add_argument(f"--{k.replace('_', '-')}", type=Path, default=d)
    args = ap.parse_args()
    paths = {k: getattr(args, k) for k in DEFAULTS}

    try:
        tables, meta = collect(paths)  # all verification happens before any connection is opened
    except ImportRefused as e:
        raise SystemExit(f"IMPORT REFUSED before connecting, nothing was changed: {e}")
    url = read_env(args.env).get(args.url_var)
    if not url:
        raise SystemExit(f"{args.url_var} is not set in {args.env}")
    try:
        with psycopg.connect(url, autocommit=True) as conn:  # transactions are opened explicitly
            if args.create_schema:
                create_schema(conn)
            report = write(conn, tables, meta)
    except ImportRefused as e:
        raise SystemExit(f"IMPORT REFUSED, nothing was changed: {e}")
    except psycopg.Error as e:  # the message may quote a value, never the URL
        raise SystemExit(f"IMPORT FAILED and was rolled back: {type(e).__name__}: {e.diag.message_primary}")
    write_markdown(report, args.report)
    for t, v in report["tables"].items():
        print(f"{t:28s} {v['rows']:>10,}")
    print(f"identities: {sum(v == 0 for v in report['identities'].values())} of {len(report['identities'])} hold; "
          f"{report['seconds']} s; report -> {args.report}")


if __name__ == "__main__":
    main()
