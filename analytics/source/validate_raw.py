"""Stage 1: raw source validation (spec 9.6.1) and the quality report.

Reads the source register, validates every registered ridership CSV and GTFS archive, and writes
    reports/stage1_quality_report.md
    reports/stage1_quality_checks.json
Conflicting ridership route/date records are quarantined (never summed) to
    data/processed/<snapshot_id>/ridership_conflicts_quarantine.csv
Raw files are only read, never modified.

Usage (CMD):
    python -I analytics\\source\\validate_raw.py --config analytics\\config\\sources.json --register data\\raw\\source_register.csv --out reports
"""
from __future__ import annotations

import argparse
import csv
import json
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

PASS, FAIL, WARN, INFO = "PASS", "FAIL", "WARN", "INFO"
TIME_RE = r"^\s*\d{1,3}:[0-5]\d:[0-5]\d\s*$"  # hours may exceed 24 (e.g. 25:10:00)

REQUIRED = {  # spec 9.5.1
    "routes.txt": ["route_id", "route_short_name", "route_type"],
    "trips.txt": ["trip_id", "route_id", "service_id"],
    "calendar.txt": ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday",
                     "saturday", "sunday", "start_date", "end_date"],
    "calendar_dates.txt": ["service_id", "date", "exception_type"],
    "stop_times.txt": ["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"],
    "stops.txt": ["stop_id", "stop_lat", "stop_lon"],
    "shapes.txt": ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
    "agency.txt": ["agency_timezone"],
}
OPTIONAL_COLS = {"trips.txt": ["direction_id", "shape_id"], "routes.txt": ["route_long_name"],
                 "stops.txt": ["stop_name"]}


class Checks:
    def __init__(self, source: str):
        self.source = source
        self.items: list[dict] = []

    def add(self, check: str, status: str, detail: str, **values):
        self.items.append({"source": self.source, "check": check, "status": status,
                           "detail": detail, **({"values": values} if values else {})})


# ----------------------------------------------------------------------------- ridership
def validate_ridership(row: dict, cfg: dict, root: Path) -> tuple[Checks, dict]:
    ref = cfg["ridership"]["spec_reference"]
    c = Checks(row["snapshot_id"])
    path = root / row["local_path"]
    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    expected_cols = ["route", "date", "daytype", "rides"]
    cols = list(df.columns)
    c.add("CSV schema", PASS if cols == expected_cols else FAIL, f"columns = {cols}")
    if cols != expected_cols:
        return c, {}

    n = len(df)
    route = df["route"].str.strip()
    c.add("Row count", INFO, f"{n:,} data records")
    ws = int((df["route"] != route).sum())
    c.add("Route whitespace", INFO if ws == 0 else WARN, f"{ws:,} route values have surrounding whitespace (trimmed for analysis)")
    miss_route = int((route == "").sum())
    miss_date = int((df["date"].str.strip() == "").sum())
    c.add("Missing identifiers", PASS if miss_route + miss_date == 0 else FAIL,
          f"{miss_route:,} empty route, {miss_date:,} empty date")

    date = pd.to_datetime(df["date"].str.strip(), format="%m/%d/%Y", errors="coerce")
    bad_date = int(date.isna().sum()) - miss_date
    c.add("Date parsing (MM/DD/YYYY)", PASS if bad_date == 0 else FAIL, f"{bad_date:,} unparseable non-empty dates")

    rides_txt = df["rides"].str.replace(",", "", regex=False).str.strip()
    rides = pd.to_numeric(rides_txt, errors="coerce")
    sep = int(df["rides"].str.contains(",", regex=False).sum())
    bad_num = int(rides.isna().sum())
    c.add("Numeric conversion", PASS if bad_num == 0 else FAIL,
          f"{bad_num:,} non-numeric/empty rides; {sep:,} values contained a ',' separator")
    neg = int((rides < 0).sum())
    frac = int(((rides % 1) != 0).sum())
    c.add("Negative counts", PASS if neg == 0 else FAIL, f"{neg:,} negative rides")
    c.add("Fractional counts", PASS if frac == 0 else FAIL, f"{frac:,} non-integer rides")

    daytype = df["daytype"].str.strip()
    unknown = daytype[~daytype.isin(["W", "A", "U"])]
    c.add("Day types (W/A/U)", PASS if unknown.empty else FAIL,
          f"{len(unknown):,} unknown; observed = {sorted(daytype.unique().tolist())}")

    zeros = int((rides == 0).sum())
    c.add("Genuine zero counts", INFO, f"{zeros:,} records with rides = 0 (kept; not missing)")

    dup_mask = df.duplicated(keep="first")
    dups = int(dup_mask.sum())
    c.add("Exact duplicate records", PASS if dups == 0 else WARN,
          f"{dups:,} exact copies (to be removed in processing, with this report as the record)")

    dedup = pd.DataFrame({"route": route, "date": date, "daytype": daytype, "rides": rides})[~dup_mask]
    key_dup = dedup.duplicated(subset=["route", "date"], keep=False)
    conflicts = dedup[key_dup & dedup["date"].notna()]
    n_keys = conflicts.groupby(["route", "date"]).ngroups if not conflicts.empty else 0
    qdir = root / "data" / "processed" / row["snapshot_id"]
    if not conflicts.empty:
        qdir.mkdir(parents=True, exist_ok=True)
        conflicts.sort_values(["route", "date"]).to_csv(qdir / "ridership_conflicts_quarantine.csv", index=False)
    c.add("Conflicting route/date records", PASS if n_keys == 0 else WARN,
          f"{n_keys:,} route/date keys with differing records ({len(conflicts):,} rows) "
          + ("quarantined, not summed" if n_keys else ""))

    # ---- content comparison with the spec's reference version (9.3.1)
    cutoff = pd.Timestamp(ref["observation_cutoff"])
    inside = date <= cutoff
    after = date > cutoff
    r_in = route[inside]
    d_in = date[inside]
    ours = {
        "records": int(inside.sum()),
        "route_identifiers": int(r_in.nunique()),
        "first_date": d_in.min().date().isoformat() if inside.any() else None,
        "last_date": d_in.max().date().isoformat() if inside.any() else None,
        "zero_count_records": int(((rides == 0) & inside).sum()),
    }
    comparison = []
    for k in ["records", "route_identifiers", "first_date", "last_date", "zero_count_records"]:
        exp, got = ref[k], ours[k]
        if isinstance(exp, int):
            diff = got - exp
            diff_txt = f"{diff:+,}"
        else:
            diff = (pd.Timestamp(got) - pd.Timestamp(exp)).days if got else None
            diff_txt = f"{diff:+d} days" if diff is not None else "n/a"
        comparison.append({"metric": k, "spec": exp, "ours": got,
                           "result": "MATCH" if got == exp else "MISMATCH", "difference": diff_txt})

    post = {
        "records": int(after.sum()),
        "first_date": date[after].min().date().isoformat() if after.any() else None,
        "last_date": date[after].max().date().isoformat() if after.any() else None,
        "route_identifiers": int(route[after].nunique()),
        "rides_sum": int(rides[after].sum()) if after.any() else 0,
    }
    yearly = (pd.DataFrame({"year": d_in.dt.year}).value_counts().sort_index())
    extra = {"comparison": comparison, "post_cutoff": post,
             "records_by_year_to_cutoff": {int(k[0]): int(v) for k, v in yearly.items()},
             "spec_cutoff": ref["observation_cutoff"]}
    return c, extra


# ----------------------------------------------------------------------------- GTFS
def zip_checks(c: Checks, zip_path: Path, ext: Path) -> list[str]:
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as e:
        c.add("ZIP readable", FAIL, str(e))
        return []
    with zf:
        c.add("ZIP readable", PASS, f"{len(zf.infolist())} members")
        bad = zf.testzip()
        c.add("ZIP CRC (testzip)", PASS if bad is None else FAIL, "all member CRCs valid" if bad is None else f"first bad member: {bad}")
        problems = []
        names = []
        for info in zf.infolist():
            if info.is_dir():
                continue
            names.append(info.filename)
            out = ext / info.filename
            if not out.exists():
                problems.append(f"{info.filename}: not extracted")
                continue
            if out.stat().st_size != info.file_size:
                problems.append(f"{info.filename}: size {out.stat().st_size} != {info.file_size}")
                continue
            crc = 0
            with open(out, "rb") as f:
                while block := f.read(1024 * 1024):
                    crc = zlib.crc32(block, crc)
            if crc != info.CRC:
                problems.append(f"{info.filename}: CRC mismatch")
        c.add("Extracted-byte agreement", PASS if not problems else FAIL,
              "every extracted file matches ZIP size and CRC32" if not problems else "; ".join(problems[:5]))
        return names


def gtfs_view(con, name: str, path: Path):
    con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_csv('{path.as_posix()}', "
                "header=true, all_varchar=true, quote='\"', escape='\"', strict_mode=false)")
    return [r[0].strip().lstrip("﻿") for r in con.execute(f"DESCRIBE {name}").fetchall()]


def q1(con, sql: str):
    return con.execute(sql).fetchone()[0]


def validate_gtfs(row: dict, archive: dict, cfg: dict, root: Path) -> tuple[Checks, dict]:
    sid = row["snapshot_id"]
    c = Checks(sid)
    zip_path = root / row["local_path"]
    ext = zip_path.parent / "extracted"
    members = zip_checks(c, zip_path, ext)
    info: dict = {}

    con = duckdb.connect()
    present = {}
    for fname, req in REQUIRED.items():
        p = ext / fname
        if not p.exists():
            status = INFO if fname == "calendar.txt" and (ext / "calendar_dates.txt").exists() else FAIL
            c.add(f"Required file {fname}", status, "missing")
            continue
        cols = gtfs_view(con, fname[:-4], p)
        missing = [x for x in req if x not in cols]
        opt_missing = [x for x in OPTIONAL_COLS.get(fname, []) if x not in cols]
        c.add(f"Required columns {fname}", PASS if not missing else FAIL,
              ("all present" if not missing else f"missing {missing}")
              + (f"; optional absent: {opt_missing}" if opt_missing else ""))
        present[fname[:-4]] = cols
    if not {"routes", "trips", "stop_times", "stops"} <= present.keys():
        return c, info

    # -- unique keys
    for tbl, key in [("routes", "route_id"), ("trips", "trip_id"), ("stops", "stop_id")]:
        total = q1(con, f"SELECT count(*) FROM {tbl}")
        dup = q1(con, f"SELECT count(*) - count(DISTINCT {key}) FROM {tbl}")
        empty = q1(con, f"SELECT count(*) FROM {tbl} WHERE coalesce(trim({key}),'') = ''")
        c.add(f"Unique key {tbl}.{key}", PASS if dup == 0 and empty == 0 else FAIL,
              f"{total:,} rows, {dup:,} duplicates, {empty:,} empty")

    # -- foreign keys
    svc_sources = []
    if "calendar" in present:
        svc_sources.append("SELECT service_id FROM calendar")
    if "calendar_dates" in present:
        svc_sources.append("SELECT service_id FROM calendar_dates")
    con.execute("CREATE TEMP TABLE services AS " + " UNION ".join(svc_sources))
    fks = [
        ("trips.route_id -> routes", "SELECT count(*) FROM trips t LEFT JOIN routes r USING (route_id) WHERE r.route_id IS NULL"),
        ("trips.service_id -> calendar/calendar_dates", "SELECT count(*) FROM trips t LEFT JOIN services s USING (service_id) WHERE s.service_id IS NULL"),
        ("stop_times.trip_id -> trips", "SELECT count(*) FROM stop_times st LEFT JOIN trips t USING (trip_id) WHERE t.trip_id IS NULL"),
        ("stop_times.stop_id -> stops", "SELECT count(*) FROM stop_times st LEFT JOIN stops s USING (stop_id) WHERE s.stop_id IS NULL"),
    ]
    if "shapes" in present and "shape_id" in present["trips"]:
        fks.append(("trips.shape_id -> shapes", "SELECT count(*) FROM trips t WHERE coalesce(t.shape_id,'') <> '' "
                    "AND t.shape_id NOT IN (SELECT DISTINCT shape_id FROM shapes)"))
    for name, sql in fks:
        bad = q1(con, sql)
        c.add(f"Foreign key {name}", PASS if bad == 0 else FAIL, f"{bad:,} orphan rows")
    no_st = q1(con, "SELECT count(*) FROM trips WHERE trip_id NOT IN (SELECT DISTINCT trip_id FROM stop_times)")
    c.add("Trips without stop_times", INFO if no_st == 0 else WARN, f"{no_st:,} trips have no stop events")

    # -- calendar validity
    if "calendar" in present:
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        bad_flags = q1(con, "SELECT count(*) FROM calendar WHERE " + " OR ".join(f"trim({d}) NOT IN ('0','1')" for d in days))
        bad_dates = q1(con, "SELECT count(*) FROM calendar WHERE try_strptime(trim(start_date),'%Y%m%d') IS NULL "
                            "OR try_strptime(trim(end_date),'%Y%m%d') IS NULL")
        bad_order = q1(con, "SELECT count(*) FROM calendar WHERE try_strptime(trim(start_date),'%Y%m%d') > try_strptime(trim(end_date),'%Y%m%d')")
        dup_svc = q1(con, "SELECT count(*) - count(DISTINCT service_id) FROM calendar")
        ok = bad_flags + bad_dates + bad_order + dup_svc == 0
        c.add("Calendar validity (calendar.txt)", PASS if ok else FAIL,
              f"{bad_flags} bad weekday flags, {bad_dates} unparseable dates, {bad_order} start>end, {dup_svc} duplicate service_id")
    if "calendar_dates" in present:
        bad_d = q1(con, "SELECT count(*) FROM calendar_dates WHERE try_strptime(trim(date),'%Y%m%d') IS NULL")
        bad_t = q1(con, "SELECT count(*) FROM calendar_dates WHERE trim(exception_type) NOT IN ('1','2')")
        dup = q1(con, "SELECT count(*) FROM (SELECT service_id, date FROM calendar_dates GROUP BY 1,2 HAVING count(*)>1)")
        c.add("Calendar validity (calendar_dates.txt)", PASS if bad_d + bad_t + dup == 0 else FAIL,
              f"{bad_d} unparseable dates, {bad_t} bad exception_type, {dup} duplicate service/date pairs")

    # -- stop_times: duplicate sequences, time syntax, durations (DuckDB)
    dup_seq = q1(con, "SELECT count(*) FROM (SELECT trip_id, try_cast(stop_sequence AS INTEGER) s FROM stop_times "
                      "GROUP BY 1,2 HAVING count(*)>1)")
    bad_seq = q1(con, "SELECT count(*) FROM stop_times WHERE try_cast(stop_sequence AS INTEGER) IS NULL")
    c.add("Duplicate stop sequences", PASS if dup_seq == 0 and bad_seq == 0 else FAIL,
          f"{dup_seq:,} duplicated (trip_id, stop_sequence); {bad_seq:,} non-integer stop_sequence")
    bad_time = q1(con, f"""SELECT count(*) FROM stop_times WHERE
        (coalesce(trim(arrival_time),'') <> '' AND NOT regexp_matches(arrival_time, '{TIME_RE}')) OR
        (coalesce(trim(departure_time),'') <> '' AND NOT regexp_matches(departure_time, '{TIME_RE}'))""")
    empty_time = q1(con, "SELECT count(*) FROM stop_times WHERE coalesce(trim(arrival_time),'')='' OR coalesce(trim(departure_time),'')=''")
    over24 = q1(con, "SELECT count(*) FROM stop_times WHERE try_cast(split_part(trim(departure_time),':',1) AS INTEGER) >= 24")
    c.add("Time syntax (H:MM:SS, >24h allowed)", PASS if bad_time == 0 else FAIL,
          f"{bad_time:,} malformed; {empty_time:,} rows with an empty time (allowed between timepoints); "
          f"{over24:,} departures at/after 24:00:00 (kept on their original service date)")

    con.execute("""CREATE TEMP TABLE trip_ends AS
        WITH st AS (
          SELECT trip_id, try_cast(stop_sequence AS INTEGER) seq,
            CASE WHEN regexp_matches(arrival_time, ?) THEN
              cast(split_part(trim(arrival_time),':',1) AS INTEGER)*3600 + cast(split_part(trim(arrival_time),':',2) AS INTEGER)*60
              + cast(split_part(trim(arrival_time),':',3) AS INTEGER) END arr,
            CASE WHEN regexp_matches(departure_time, ?) THEN
              cast(split_part(trim(departure_time),':',1) AS INTEGER)*3600 + cast(split_part(trim(departure_time),':',2) AS INTEGER)*60
              + cast(split_part(trim(departure_time),':',3) AS INTEGER) END dep
          FROM stop_times)
        SELECT trip_id, arg_min(dep, seq) first_dep, arg_max(arr, seq) last_arr FROM st GROUP BY trip_id""",
                [TIME_RE, TIME_RE])
    total_trips = q1(con, "SELECT count(*) FROM trip_ends")
    missing_end = q1(con, "SELECT count(*) FROM trip_ends WHERE first_dep IS NULL OR last_arr IS NULL")
    negative = q1(con, "SELECT count(*) FROM trip_ends WHERE last_arr < first_dep")
    c.add("Duration completeness", PASS if missing_end + negative == 0 else WARN,
          f"{total_trips:,} trips with stop events; {missing_end:,} missing a first departure or last arrival; "
          f"{negative:,} with last arrival before first departure")

    # -- agency timezone
    if "agency" in present:
        tzs = [r[0] for r in con.execute("SELECT DISTINCT trim(agency_timezone) FROM agency").fetchall()]
        exp_tz = cfg["gtfs"]["agency_timezone"]
        c.add("Agency timezone", PASS if tzs == [exp_tz] else FAIL, f"agency_timezone = {tzs}")

    # -- frequencies.txt (spec 9.5.1: empty in the selected feeds)
    fpath = ext / "frequencies.txt"
    if fpath.exists():
        cols = gtfs_view(con, "frequencies", fpath) if fpath.stat().st_size > 0 else []
        nfreq = q1(con, "SELECT count(*) FROM frequencies") if cols else 0
        c.add("frequencies.txt", PASS if nfreq == 0 else WARN, f"{nfreq:,} rows" + (" - must be expanded before counting" if nfreq else " (empty, as in spec)"))
    else:
        c.add("frequencies.txt", INFO, "file absent")

    # -- informational counts compared with the spec
    bus_routes = q1(con, "SELECT count(DISTINCT t.route_id) FROM trips t JOIN routes r USING (route_id) WHERE trim(r.route_type)='3'")
    bus_trips = q1(con, "SELECT count(*) FROM trips t JOIN routes r USING (route_id) WHERE trim(r.route_type)='3'")
    bus_st = q1(con, "SELECT count(*) FROM stop_times st JOIN trips t USING (trip_id) JOIN routes r USING (route_id) WHERE trim(r.route_type)='3'")
    win = (None, None)
    if "calendar" in present:
        win = con.execute("""SELECT min(try_strptime(trim(start_date),'%Y%m%d'))::DATE, max(try_strptime(trim(end_date),'%Y%m%d'))::DATE
            FROM calendar WHERE service_id IN (SELECT t.service_id FROM trips t JOIN routes r USING (route_id) WHERE trim(r.route_type)='3')""").fetchone()
    spec = cfg["gtfs"]["spec_reference"]
    info = {
        "bus_routes_with_trips": bus_routes, "spec_bus_routes_with_trips": spec["bus_routes_with_trips"].get(sid),
        "bus_trips": bus_trips, "bus_stop_times": bus_st, "spec_bus_stop_times": spec["bus_stop_times"].get(sid),
        "bus_calendar_window": [str(win[0]) if win[0] else None, str(win[1]) if win[1] else None],
        "spec_active_window": archive["active_window"],
        "members": members,
    }
    con.close()
    return c, info


# ----------------------------------------------------------------------------- report
def write_report(out: Path, register: list[dict], results: list[dict]) -> None:
    def esc(s):
        return str(s).replace("|", "\\|")
    L = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    L += ["# Stage 1 quality report: raw source validation", "",
          f"Generated {now} by `analytics/source/validate_raw.py` (spec v3.8, section 9.6.1).", "",
          "> ZIP integrity and the checks below are narrower than full GTFS specification validation, "
          "and they do not verify actually operated service (spec 9.6.1, 9.22.2).", ""]

    L += ["## 1. Source register and fingerprints (spec 9.22.1)", "",
          "| dataset | snapshot | bytes | sha256 (first 16) | fingerprint | primary |", "|---|---|---:|---|---|---|"]
    for r in register:
        fp = "MATCH" if r["fingerprint_match"] == "True" else "MISMATCH"
        L.append(f"| {r['dataset_id']} | {r['snapshot_id']} | {int(r['byte_size']):,} | `{r['sha256'][:16]}` | {fp} | {r['is_primary']} |")
    L.append("")

    for res in results:
        L += [f"## {res['kind']}: `{res['source']}`", ""]
        if res["kind"] == "Ridership":
            reg = res["register"]
            L += [f"- Downloaded: {reg['downloaded_at']} ({reg['acquisition']})",
                  f"- Publisher 'last updated' (rowsUpdatedAt): {reg['source_last_updated'] or 'n/a'}",
                  f"- Records in file: {int(reg['row_count']):,}", ""]
        L += ["| check | status | detail |", "|---|---|---|"]
        for it in res["checks"]:
            L.append(f"| {esc(it['check'])} | **{it['status']}** | {esc(it['detail'])} |")
        L.append("")
        x = res["extra"]
        if res["kind"] == "Ridership" and x:
            L += [f"### Content check vs spec 9.3.1 (rows dated on/before {x['spec_cutoff']})", "",
                  "The raw file is unchanged; this compares only the rows inside the spec's observation period.", "",
                  "| metric | spec | this version | result | difference |", "|---|---:|---:|---|---:|"]
            for m in x["comparison"]:
                sv = f"{m['spec']:,}" if isinstance(m["spec"], int) else m["spec"]
                ov = f"{m['ours']:,}" if isinstance(m["ours"], int) else m["ours"]
                L.append(f"| {m['metric']} | {sv} | {ov} | **{m['result']}** | {m['difference']} |")
            p = x["post_cutoff"]
            L += ["", f"### Rows after {x['spec_cutoff']} (kept in the raw file, reported separately)", "",
                  f"- Records: {p['records']:,}",
                  f"- Dates: {p['first_date']} to {p['last_date']}",
                  f"- Route identifiers: {p['route_identifiers']}",
                  f"- Sum of rides: {p['rides_sum']:,}", ""]
        if res["kind"] == "GTFS" and x:
            def cmp(a, b):
                return "" if b is None else (" (spec: {:,}, **{}**)".format(b, "MATCH" if a == b else "MISMATCH"))
            L += ["Informational counts:", "",
                  f"- Bus routes (route_type 3) referenced by trips: {x['bus_routes_with_trips']}{cmp(x['bus_routes_with_trips'], x['spec_bus_routes_with_trips'])}",
                  f"- Bus trips: {x['bus_trips']:,}",
                  f"- Bus stop_times: {x['bus_stop_times']:,}{cmp(x['bus_stop_times'], x['spec_bus_stop_times'])}",
                  f"- Bus calendar.txt window: {x['bus_calendar_window'][0]} to {x['bus_calendar_window'][1]} "
                  f"(spec active window {x['spec_active_window'][0]} to {x['spec_active_window'][1]}; "
                  "calendar.txt bounds can include an outgoing/incoming regime, so this is context, not a pass/fail)", ""]
    out.write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--register", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    root = args.register.resolve().parent.parent.parent  # data/raw/source_register.csv -> root
    with open(args.register, newline="", encoding="utf-8") as f:
        register = list(csv.DictReader(f))
    archives = {a["snapshot_id"]: a for a in cfg["gtfs"]["archives"]}

    results = []
    for r in register:
        print(f"validating {r['snapshot_id']} ...", flush=True)
        if r["dataset_id"] == cfg["ridership"]["dataset_id"]:
            c, extra = validate_ridership(r, cfg, root)
            kind = "Ridership"
        else:
            c, extra = validate_gtfs(r, archives[r["snapshot_id"]], cfg, root)
            kind = "GTFS"
        results.append({"kind": kind, "source": r["snapshot_id"], "register": r, "checks": c.items, "extra": extra})
        fails = [i["check"] for i in c.items if i["status"] == FAIL]
        print(f"    {len(c.items)} checks, {len(fails)} FAIL {fails if fails else ''}")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "stage1_quality_checks.json").write_text(
        json.dumps([{k: v for k, v in x.items() if k != "register"} for x in results], indent=2, default=str), encoding="utf-8")
    write_report(args.out / "stage1_quality_report.md", register, results)
    print(f"wrote {args.out / 'stage1_quality_report.md'}")


if __name__ == "__main__":
    main()
