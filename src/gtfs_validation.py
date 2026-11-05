"""GTFS safety + validation: safe ZIP reading, structured validation report, service-day resolution (calendar + calendar_dates)."""
import datetime as dt, re, zipfile
from pathlib import PurePosixPath
import numpy as np, pandas as pd
from .config import INDIA_BBOX as B

GTFS_FILES = ["agency", "routes", "trips", "stop_times", "stops", "calendar", "calendar_dates", "frequencies", "shapes"]
REQUIRED = {"routes": ["route_id"], "trips": ["route_id", "service_id", "trip_id"],
            "stop_times": ["trip_id", "stop_id", "stop_sequence"], "stops": ["stop_id", "stop_lat", "stop_lon"]}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
LIMITS = dict(max_members=64, max_member_bytes=600 * 2**20, max_total_bytes=900 * 2**20, max_ratio=250, ratio_min_size=20 * 2**20)

class GTFSError(Exception):
    """Raised for unusable or unsafe input. `.report` (optional) carries the structured validation report."""
    def __init__(self, msg, report=None): super().__init__(msg); self.report = report

_ST_KEEP = {"trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"}
def _keep(name):
    return (lambda c: c.strip() in _ST_KEEP) if name == "stop_times" else None

def read_zip_safely(file_like, limits=None):
    """Read GTFS .txt members from a ZIP without extracting to disk. Rejects unsafe paths, archive bombs and too many members."""
    L = {**LIMITS, **(limits or {})}; feed = {}
    try: z = zipfile.ZipFile(file_like)
    except zipfile.BadZipFile: raise GTFSError("The file is not a valid ZIP archive.")
    with z:
        infos = z.infolist()
        if len(infos) > L["max_members"]: raise GTFSError(f"Archive has too many files ({len(infos)} > {L['max_members']}).")
        total = 0
        for i in infos:
            name = i.filename.replace("\\", "/"); p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or re.match(r"^[A-Za-z]:", name): raise GTFSError("Archive contains an unsafe file path and was rejected.")
            if i.is_dir(): continue
            total += i.file_size
            if i.file_size > L["max_member_bytes"] or total > L["max_total_bytes"]: raise GTFSError("Archive expands to more data than allowed.")
            if i.file_size > L["ratio_min_size"] and i.compress_size and i.file_size / i.compress_size > L["max_ratio"]:
                raise GTFSError("Archive has a suspicious compression ratio and was rejected.")
            if p.suffix.lower() != ".txt" or p.stem.lower() not in GTFS_FILES or p.stem.lower() in feed: continue
            if p.stem.lower() == "shapes":                       # geometry is not used; read only a few rows to note its presence
                with z.open(i) as fh: feed["shapes"] = pd.read_csv(fh, nrows=5, dtype=str)
                continue
            raw = z.read(i)
            try: df = pd.read_csv(pd.io.common.BytesIO(raw), dtype=str, skipinitialspace=True, low_memory=False, encoding="utf-8-sig", usecols=_keep(p.stem.lower()))
            except UnicodeDecodeError: df = pd.read_csv(pd.io.common.BytesIO(raw), dtype=str, skipinitialspace=True, low_memory=False, encoding="latin-1", usecols=_keep(p.stem.lower()))
            except Exception: raise GTFSError(f"{p.name} could not be parsed as CSV.")
            df.columns = [c.strip() for c in df.columns]; feed[p.stem.lower()] = df
    return feed

def to_seconds(s):
    """'HH:MM:SS' (hours may exceed 24) -> seconds; invalid -> NaN. Parses unique values only (fast on millions of rows)."""
    s = s.astype(str).str.strip(); u = pd.Series(s.dropna().unique())
    p = u.str.extract(r"^(\d{1,3}):([0-5]?\d):([0-5]?\d)$").apply(pd.to_numeric, errors="coerce")
    return s.map(dict(zip(u, p[0] * 3600 + p[1] * 60 + p[2])))

def _d(s): return pd.to_datetime(s.astype(str).str.strip(), format="%Y%m%d", errors="coerce")

def active_services(feed, day):
    """(active_service_ids, known_service_ids) for a calendar date, honouring calendar.txt validity ranges and calendar_dates.txt exceptions."""
    active, known = set(), set(); ts = pd.Timestamp(day)
    cal, cd = feed.get("calendar"), feed.get("calendar_dates")
    if cal is not None and len(cal):
        flag = pd.to_numeric(cal.get(DAYS[ts.weekday()], 0), errors="coerce").fillna(0) == 1
        ok = flag & (_d(cal.start_date) <= ts) & (_d(cal.end_date) >= ts)
        active |= set(cal.service_id[ok]); known |= set(cal.service_id)
    if cd is not None and len(cd):
        known |= set(cd.service_id); x = cd[cd.date.astype(str).str.strip() == ts.strftime("%Y%m%d")]
        et = pd.to_numeric(x.exception_type, errors="coerce")
        active |= set(x.service_id[et == 1]); active -= set(x.service_id[et == 2])
    return active, known

def reference_days(feed):
    """Pick a typical weekday (Tuesday) and weekend day (Sunday) inside the feed's validity window and the services active on each.
    Returns dict(weekday=set|None, weekend=set|None, known=set, notes=[...]). None = no calendar information: every service is assumed active."""
    cal, cd = feed.get("calendar"), feed.get("calendar_dates"); notes = []
    if "trips" in feed:                                    # only services used by the analysed trips define the validity window
        used = set(feed["trips"].service_id)
        cal = cal[cal.service_id.isin(used)] if cal is not None else None; cd = cd[cd.service_id.isin(used)] if cd is not None else None
        feed = {**feed, "calendar": cal, "calendar_dates": cd}
    lo = hi = None
    if cal is not None and len(cal): lo, hi = _d(cal.start_date).min(), _d(cal.end_date).max()
    elif cd is not None and len(cd): lo, hi = _d(cd.date).min(), _d(cd.date).max()
    if lo is None or pd.isna(lo) or pd.isna(hi):
        return dict(weekday=None, weekend=None, known=set(), ref_weekday=None, ref_weekend=None,
                    notes=["No usable calendar information: all services are assumed to run on every day."])
    mid = lo + (hi - lo) / 2; out = {"known": set(), "notes": notes}
    for key, wd in (("weekday", 1), ("weekend", 6)):
        best = None
        for k in range(0, 40):                                 # search outward from the middle of the validity window
            for sgn in (1, -1):
                d = mid + pd.Timedelta(days=7 * k * sgn); d = d + pd.Timedelta(days=(wd - d.weekday()))
                if lo <= d <= hi:
                    a, kn = active_services(feed, d)
                    if a: best = (d, a, kn); break
            if best: break
        if best: out[key], out["known"] = best[1], best[2] | out["known"]; out["ref_" + key] = best[0].strftime("%Y-%m-%d")
        else: out[key] = set(); out["ref_" + key] = None; notes.append(f"No service found on a typical {'Tuesday' if key == 'weekday' else 'Sunday'}.")
    notes.append(f"Typical weekday = {out.get('ref_weekday')}, typical weekend day (Sunday) = {out.get('ref_weekend')}; Saturdays are not analysed separately.")
    return out

def validate_feed(feed):
    """Structured validation. Returns dict(status, n_errors, n_warnings, issues=[{severity,code,file,message,count,fix,examples}], tables)."""
    issues = []
    def add(sev, code, file, msg, count=None, fix="", ex=None):
        issues.append(dict(severity=sev, code=code, file=file, message=msg, count=None if count is None else int(count), fix=fix, examples=[str(e) for e in (list(ex) if ex is not None else [])][:5]))
    for f, cols in REQUIRED.items():
        if f not in feed: add("error", "missing_file", f + ".txt", f"Required file {f}.txt is missing.", fix=f"Add {f}.txt to the ZIP (GTFS specification)."); continue
        if feed[f].empty: add("error", "empty_file", f + ".txt", f"{f}.txt has no rows.", fix="Provide a non-empty file.")
        miss = [c for c in cols if c not in feed[f].columns]
        if miss: add("error", "missing_columns", f + ".txt", f"Missing required column(s): {', '.join(miss)}.", fix="Add the columns listed in the GTFS reference.")
    if "calendar" not in feed and "calendar_dates" not in feed:
        add("warning", "no_calendar", "calendar.txt", "Neither calendar.txt nor calendar_dates.txt is present.", fix="Add a calendar so weekday/weekend service can be separated. All services are assumed to run every day.")
    if any(i["severity"] == "error" for i in issues): return _summ(issues, feed)
    R, T, S, ST = feed["routes"], feed["trips"], feed["stops"], feed["stop_times"]
    for name, df, key in (("routes", R, "route_id"), ("trips", T, "trip_id"), ("stops", S, "stop_id")):
        d = df[key].duplicated(); n = int(d.sum())
        if n: add("warning", "duplicate_id", name + ".txt", f"{n} duplicate {key} value(s); the first occurrence is kept.", n, "Make identifiers unique.", df[key][d].head())
    n = int(ST.duplicated(["trip_id", "stop_sequence"]).sum())
    if n: add("warning", "duplicate_stop_time", "stop_times.txt", f"{n} duplicated (trip_id, stop_sequence) rows removed.", n, "Remove duplicate rows.")
    for a, ak, b, bk, code in ((T, "route_id", R, "route_id", "trip_route_missing"), (ST, "trip_id", T, "trip_id", "stop_time_trip_missing"), (ST, "stop_id", S, "stop_id", "stop_time_stop_missing")):
        bad = ~a[ak].isin(b[bk]); n = int(bad.sum())
        if n: add("warning", code, "stop_times.txt" if a is ST else "trips.txt", f"{n} row(s) reference an unknown {ak}; they are dropped.", n, "Fix the references.", a[ak][bad].unique()[:5])
    n = int((~T.trip_id.isin(ST.trip_id)).sum())
    if n: add("warning", "trip_without_stop_times", "trips.txt", f"{n} trip(s) have no stop_times.", n, "Add stop_times or remove the trips.")
    n = int((~R.route_id.isin(T.route_id)).sum())
    if n: add("info", "route_without_trips", "routes.txt", f"{n} route(s) have no trips and are excluded.", n)
    lat, lon = pd.to_numeric(S.stop_lat, errors="coerce"), pd.to_numeric(S.stop_lon, errors="coerce")
    bad = lat.isna() | lon.isna() | ~lat.between(B["lat_min"], B["lat_max"]) | ~lon.between(B["lon_min"], B["lon_max"]) | ((lat == 0) & (lon == 0))
    if int(bad.sum()): add("warning", "bad_coordinates", "stops.txt", f"{int(bad.sum())} stop(s) have missing or out-of-India coordinates and are excluded.", int(bad.sum()), "Correct the coordinates.", S.stop_id[bad].head())
    for col in ("arrival_time", "departure_time"):
        if col in ST:
            raw = ST[col].astype(str).str.strip(); empty = ST[col].isna() | raw.eq("")
            sec = to_seconds(ST[col]); inv = int((sec.isna() & ~empty).sum()); mis = int(empty.sum())
            if inv: add("warning", "invalid_time", "stop_times.txt", f"{inv} malformed {col} value(s).", inv, "Use HH:MM:SS.")
            if mis: add("info" if mis < len(ST) * 0.5 else "warning", "missing_time", "stop_times.txt", f"{mis} empty {col} value(s) (interpolated within the trip).", mis)
            ov = int((sec >= 86400).sum())
            if ov: add("info", "after_midnight", "stop_times.txt", f"{ov} {col} value(s) are after 24:00 (valid GTFS); handled.", ov)
        else: add("warning", "missing_column", "stop_times.txt", f"Column {col} is absent.", fix="Provide times; otherwise timetable metrics are limited.")
    if "arrival_time" in ST:
        s2 = ST.assign(_t=to_seconds(ST.arrival_time.where(ST.arrival_time.notna(), ST.get("departure_time"))), _q=pd.to_numeric(ST.stop_sequence, errors="coerce")).sort_values(["trip_id", "_q"])
        back = (s2.trip_id.eq(s2.trip_id.shift()) & (s2._t < s2._t.shift())).sum()
        if int(back): add("warning", "time_goes_backwards", "stop_times.txt", f"{int(back)} stop time(s) are earlier than the previous stop of the same trip (repaired).", int(back), "Check the timetable export.")
    if "route_type" not in R: add("info", "no_route_type", "routes.txt", "route_type missing; all routes treated as buses.")
    else:
        nb = int((~pd.to_numeric(R.route_type, errors="coerce").fillna(3).isin([3]) & ~pd.to_numeric(R.route_type, errors="coerce").between(700, 799)).sum())
        if nb: add("info", "non_bus_routes", "routes.txt", f"{nb} non-bus route(s) (e.g. metro/rail) are excluded from bus analysis.", nb)
    if "calendar" in feed:
        c = feed["calendar"]; bad = (_d(c.start_date) > _d(c.end_date)).sum()
        if int(bad): add("warning", "calendar_range", "calendar.txt", f"{int(bad)} service(s) end before they start.", int(bad))
        unk = int((~T.service_id.isin(set(c.service_id) | set(feed.get("calendar_dates", pd.DataFrame({"service_id": []})).service_id))).sum())
        if unk: add("warning", "unknown_service", "trips.txt", f"{unk} trip(s) use a service_id absent from the calendar; they are assumed to run every day.", unk)
    for name, df, key in (("routes", R, "route_id"), ("trips", T, "service_id"), ("stops", S, "stop_id")):
        mk = df[key].astype(str).str.contains(r"[<>]", regex=True); n = int(mk.sum())
        if n: add("warning", "suspicious_markup", name + ".txt", f"{n} {key} value(s) contain HTML/script-like characters (shown only as escaped text).", n,
                  "Remove markup from identifiers.", df[key][mk].unique()[:3])
    if "frequencies" in feed: add("info", "frequencies_present", "frequencies.txt", "Frequency-based trips are expanded into explicit trips.")
    if "shapes" not in feed: add("info", "no_shapes", "shapes.txt", "No shapes.txt: route length is computed from stop-to-stop straight-line distance.")
    return _summ(issues, feed)

def _summ(issues, feed):
    ne, nw = sum(i["severity"] == "error" for i in issues), sum(i["severity"] == "warning" for i in issues)
    return dict(status="fail" if ne else ("warn" if nw else "pass"), n_errors=ne, n_warnings=nw, n_info=len(issues) - ne - nw,
                issues=issues, tables={k: int(len(v)) for k, v in feed.items()})
