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

    s = f["stops"]; n0 = len(s)
    s["stop_lat"] = pd.to_numeric(s["stop_lat"], errors="coerce"); s["stop_lon"] = pd.to_numeric(s["stop_lon"], errors="coerce")
    s = s.dropna(subset=["stop_id", "stop_lat", "stop_lon"]).drop_duplicates("stop_id")
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
    return f, rep
