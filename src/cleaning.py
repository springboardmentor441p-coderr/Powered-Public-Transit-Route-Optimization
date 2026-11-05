<<<<<<< HEAD
"""Module 2a - Data cleaning: missing values, erroneous coordinates/times, duplicates."""
import numpy as np, pandas as pd
from .config import INDIA_BBOX as B

def to_seconds(s: pd.Series) -> pd.Series:
    """'HH:MM:SS' (HH may exceed 24) -> seconds; invalid -> NaN."""
    p = s.astype(str).str.strip().str.split(":", expand=True)
    if p.shape[1] < 3: return pd.Series(np.nan, index=s.index)
    p = p.apply(pd.to_numeric, errors="coerce")
    return p[0] * 3600 + p[1] * 60 + p[2]

def clean_feed(feed):
    """Return (clean_feed, report). Never mutates the input."""
    f = {k: v.copy() for k, v in feed.items()}; rep = {}
    for k in f: f[k].columns = [c.strip() for c in f[k].columns]
=======
"""Cleaning with a full row-count ledger. Never silently discards: every removal is recorded with its reason."""
import numpy as np, pandas as pd
from .config import INDIA_BBOX as B
from .gtfs_validation import to_seconds, GTFSError

MAX_EXPANDED_TRIPS = 400_000

def expand_frequencies(f, log):
    fr = f["frequencies"].copy(); st, tr = f["stop_times"], f["trips"]
    fr["s"], fr["e"], fr["h"] = to_seconds(fr.start_time), to_seconds(fr.end_time), pd.to_numeric(fr.headway_secs, errors="coerce")
    fr = fr.dropna(subset=["s", "e", "h"]); fr = fr[(fr.h > 0) & (fr.e > fr.s) & fr.trip_id.isin(tr.trip_id)]
    if int(((fr.e - fr.s) // fr.h + 1).sum()) > MAX_EXPANDED_TRIPS: raise GTFSError("frequencies.txt would expand to too many trips (> 400,000).")
    st = st.assign(_a=to_seconds(st.arrival_time), _d=to_seconds(st.departure_time)); first = st.groupby("trip_id")._d.min()
    tpl = tr.set_index("trip_id"); nt, ns = [], []
    for i, r in enumerate(fr.itertuples()):
        base = st[st.trip_id == r.trip_id]
        for k, s0 in enumerate(np.arange(r.s, r.e, r.h)):
            nid = f"{r.trip_id}#f{i}_{k}"; off = s0 - first[r.trip_id]
            nt.append(tpl.loc[[r.trip_id]].reset_index().assign(trip_id=nid))
            ns.append(base.assign(trip_id=nid, arrival_time=_hms(base._a + off), departure_time=_hms(base._d + off)))
    before = len(tr)
    tr = pd.concat([tr[~tr.trip_id.isin(fr.trip_id)]] + nt, ignore_index=True) if nt else tr
    st = pd.concat([st[~st.trip_id.isin(fr.trip_id)]] + ns, ignore_index=True) if ns else st
    log("expand_frequencies", "trips", before, len(tr), "frequency templates replaced by explicit trips (added rows, not removed)")
    f["trips"], f["stop_times"] = tr, st.drop(columns=["_a", "_d"], errors="ignore")

def _hms(sec):
    sec = sec.fillna(0).astype(int); return sec.map(lambda s: f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}")

def clean_feed(feed):
    """Return (clean_feed, report). Input is never mutated (the original upload is preserved by the caller)."""
    f = {k: v.copy() for k, v in feed.items()}; rep = dict(ledger=[], rows_before={k: int(len(v)) for k, v in f.items()})
    def log(step, table, before, after, reason): rep["ledger"].append(dict(step=step, table=table, before=int(before), after=int(after), removed=int(before - after), reason=reason))
    for k in f: f[k].columns = [c.strip() for c in f[k].columns]
    if "frequencies" in f: expand_frequencies(f, log)

    r0 = f["routes"]
    if "route_type" in r0:                                         # intended filtering, logged separately from data loss
        rt = pd.to_numeric(r0["route_type"], errors="coerce"); bus = r0[(rt == 3) | rt.between(700, 799) | rt.isna()]
        rep["non_bus_routes_removed"] = len(r0) - len(bus); log("bus_only_filter", "routes", len(r0), len(bus), "non-bus modes (metro/rail) excluded by design")
        n_t, n_s = len(f["trips"]), len(f["stop_times"]); f["routes"] = bus
        f["trips"] = f["trips"][f["trips"].route_id.isin(bus.route_id)]; f["stop_times"] = f["stop_times"][f["stop_times"].trip_id.isin(f["trips"].trip_id)]
        log("bus_only_filter", "trips", n_t, len(f["trips"]), "non-bus trips excluded by design"); log("bus_only_filter", "stop_times", n_s, len(f["stop_times"]), "non-bus stop_times excluded by design")
    rep["rows_after_filter"] = {k: int(len(f[k])) for k in ("routes", "trips", "stop_times", "stops")}
>>>>>>> 8eff1e4 (Fix import paths and resolve directory structure issues)

    s = f["stops"]; n0 = len(s)
    s["stop_lat"] = pd.to_numeric(s["stop_lat"], errors="coerce"); s["stop_lon"] = pd.to_numeric(s["stop_lon"], errors="coerce")
    s = s.dropna(subset=["stop_id", "stop_lat", "stop_lon"]).drop_duplicates("stop_id")
<<<<<<< HEAD
    ok = s.stop_lat.between(B["lat_min"], B["lat_max"]) & s.stop_lon.between(B["lon_min"], B["lon_max"])
    s = s[ok]; s["stop_name"] = s.get("stop_name", s.stop_id).fillna("Unnamed stop")
    rep["stops_removed_invalid_or_duplicate"] = n0 - len(s)

    st = f["stop_times"]; n0 = len(st)
    st = st.drop_duplicates(["trip_id", "stop_sequence"]).copy()
    st["stop_sequence"] = pd.to_numeric(st["stop_sequence"], errors="coerce")
    st = st.dropna(subset=["trip_id", "stop_id", "stop_sequence"])
    st = st[st.stop_id.isin(s.stop_id)]
    st["arr_sec"] = to_seconds(st["arrival_time"]); st["dep_sec"] = to_seconds(st["departure_time"])
    st["arr_sec"] = st["arr_sec"].fillna(st["dep_sec"]); st["dep_sec"] = st["dep_sec"].fillna(st["arr_sec"])
    st = st.sort_values(["trip_id", "stop_sequence"])
    miss = st.arr_sec.isna()
    rep["stop_times_missing_time_interpolated"] = int(miss.sum())
    if miss.any():
        st["arr_sec"] = st.groupby("trip_id")["arr_sec"].transform(lambda x: x.interpolate(limit_direction="both"))
        st["dep_sec"] = st["dep_sec"].fillna(st["arr_sec"])
    st = st.dropna(subset=["arr_sec"])
    # erroneous (time-travelling) entries -> enforce monotonic times within a trip
    before = st.arr_sec.copy()
    st["arr_sec"] = st.groupby("trip_id")["arr_sec"].cummax()
    st["dep_sec"] = np.maximum(st["dep_sec"], st["arr_sec"])
    rep["stop_times_non_monotonic_fixed"] = int((before != st.arr_sec).sum())
    cnt = st.groupby("trip_id")["stop_id"].transform("size")
    st = st[cnt >= 2]
    rep["stop_times_removed"] = n0 - len(st)

    t = f["trips"].drop_duplicates("trip_id"); n0 = len(t)
    t = t[t.trip_id.isin(st.trip_id) & t.route_id.isin(f["routes"].route_id)].copy()
    t["direction_id"] = pd.to_numeric(t.get("direction_id", 0), errors="coerce").fillna(0).astype(int)
    rep["trips_removed"] = n0 - len(t)
    st = st[st.trip_id.isin(t.trip_id)]

    r = f["routes"].drop_duplicates("route_id"); n0 = len(r)
    r = r[r.route_id.isin(t.route_id)].copy()
    for c in ("route_short_name", "route_long_name"):
        r[c] = r[c].fillna(r["route_id"]) if c in r else r["route_id"]
    rep["routes_removed_without_trips"] = n0 - len(r)

    cal = f["calendar"].copy()
    for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        cal[d] = pd.to_numeric(cal.get(d, 0), errors="coerce").fillna(0).astype(int)
    f.update(stops=s, stop_times=st, trips=t, routes=r, calendar=cal)
=======
    s = s[s.stop_lat.between(B["lat_min"], B["lat_max"]) & s.stop_lon.between(B["lon_min"], B["lon_max"]) & ~((s.stop_lat == 0) & (s.stop_lon == 0))]
    s["stop_name"] = s["stop_name"].fillna("Unnamed stop") if "stop_name" in s else s.stop_id
    rep["stops_removed_invalid_or_duplicate"] = n0 - len(s); log("clean_stops", "stops", n0, len(s), "missing/invalid/out-of-India coordinates or duplicate stop_id")

    st = f["stop_times"]; n0 = len(st)
    st = st.drop_duplicates(["trip_id", "stop_sequence"]); log("dedupe", "stop_times", n0, len(st), "duplicate (trip_id, stop_sequence)")
    n1 = len(st); st = st.assign(stop_sequence=pd.to_numeric(st["stop_sequence"], errors="coerce")).dropna(subset=["trip_id", "stop_id", "stop_sequence"])
    log("valid_keys", "stop_times", n1, len(st), "non-numeric stop_sequence or missing keys")
    n1 = len(st); st = st[st.stop_id.isin(s.stop_id)]; log("referential", "stop_times", n1, len(st), "references a removed/unknown stop")
    st = st.assign(arr_sec=to_seconds(st["arrival_time"]) if "arrival_time" in st else np.nan, dep_sec=to_seconds(st["departure_time"]) if "departure_time" in st else np.nan)
    st["arr_sec"] = st["arr_sec"].fillna(st["dep_sec"]); st["dep_sec"] = st["dep_sec"].fillna(st["arr_sec"])
    st = st.sort_values(["trip_id", "stop_sequence"]); miss = st.arr_sec.isna()
    rep["stop_times_missing_time_interpolated"] = int(miss.sum())
    if miss.any():
        st["arr_sec"] = st.groupby("trip_id")["arr_sec"].transform(lambda x: x.interpolate(limit_direction="both")); st["dep_sec"] = st["dep_sec"].fillna(st["arr_sec"])
    n1 = len(st); st = st.dropna(subset=["arr_sec"]); log("times", "stop_times", n1, len(st), "no usable time anywhere in the trip")
    before = st.arr_sec.copy(); st["arr_sec"] = st.groupby("trip_id")["arr_sec"].cummax(); st["dep_sec"] = np.maximum(st["dep_sec"], st["arr_sec"])
    rep["stop_times_non_monotonic_fixed"] = int((before != st.arr_sec).sum())
    n1 = len(st); st = st[st.groupby("trip_id")["stop_id"].transform("size") >= 2]; log("short_trips", "stop_times", n1, len(st), "trip has fewer than 2 valid stops")
    rep["stop_times_removed"] = rep["rows_after_filter"]["stop_times"] - len(st)

    t = f["trips"].drop_duplicates("trip_id"); n0 = len(f["trips"])
    t = t[t.trip_id.isin(st.trip_id) & t.route_id.isin(f["routes"].route_id)].copy()
    t["direction_id"] = pd.to_numeric(t.get("direction_id", 0), errors="coerce").fillna(0).astype(int)
    rep["trips_removed"] = n0 - len(t); log("referential", "trips", n0, len(t), "duplicate, no valid stop_times, or unknown route")
    st = st[st.trip_id.isin(t.trip_id)]
    r = f["routes"].drop_duplicates("route_id"); n0 = len(r); r = r[r.route_id.isin(t.route_id)].copy()
    for c in ("route_short_name", "route_long_name"): r[c] = r[c].fillna(r["route_id"]) if c in r else r["route_id"]
    rep["routes_removed_without_trips"] = n0 - len(r); log("referential", "routes", n0, len(r), "route has no valid trips")

    if "calendar" in f:
        cal = f["calendar"].copy()
        for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]: cal[d] = pd.to_numeric(cal.get(d, 0), errors="coerce").fillna(0).astype(int)
        f["calendar"] = cal
    f.update(stops=s, stop_times=st, trips=t, routes=r)
    rep["rows_after"] = {k: int(len(f[k])) for k in ("routes", "trips", "stop_times", "stops")}
    flags = []
    for k, b in rep["rows_after_filter"].items():
        frac = 1 - rep["rows_after"][k] / b if b else 0
        if frac > 0.10: flags.append(dict(table=k, fraction_removed=round(frac, 3), severity="error" if frac > 0.5 else "warning",
                                          message=f"{frac:.0%} of {k} rows were removed during cleaning; review the validation report before trusting results."))
    rep["discard_flags"] = flags
>>>>>>> 8eff1e4 (Fix import paths and resolve directory structure issues)
    return f, rep
