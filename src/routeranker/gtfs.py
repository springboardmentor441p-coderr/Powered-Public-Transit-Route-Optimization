"""GTFS feed analyser (supply-side) for user-uploaded feeds.

Works with any standard GTFS zip (e.g. Lepton Software feeds for Indian cities,
or MTA's own GTFS). Reads routes.txt, trips.txt, stop_times.txt, stops.txt,
calendar.txt (+ optional frequencies.txt / shapes.txt) and builds route
profiles (length, trips/hour, headway, scheduled speed, service span),
clusters them and flags overlapping / low-frequency routes.
"""
from __future__ import annotations

import io
import zipfile

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .clustering import dbscan_eps, stop_overlap

REQUIRED = ["routes.txt", "trips.txt", "stop_times.txt", "stops.txt"]
OPTIONAL = ["calendar.txt", "frequencies.txt", "shapes.txt"]


def read_gtfs(file_like) -> dict[str, pd.DataFrame]:
    """Load the GTFS tables from a zip file path/bytes into DataFrames."""
    if isinstance(file_like, (bytes, bytearray)):
        file_like = io.BytesIO(file_like)
    with zipfile.ZipFile(file_like) as z:
        names = {n.split("/")[-1]: n for n in z.namelist()}
        missing = [f for f in REQUIRED if f not in names]
        if missing:
            raise ValueError(f"GTFS feed is missing required files: {missing}")
        return {f[:-4]: pd.read_csv(z.open(names[f]), dtype=str, low_memory=False)
                for f in REQUIRED + OPTIONAL if f in names}


def gtfs_time_to_hours(s: pd.Series) -> pd.Series:
    """'25:10:00' -> 25.17 (GTFS allows times past midnight)."""
    p = s.fillna("").str.strip().str.split(":", expand=True)
    p = p.apply(pd.to_numeric, errors="coerce")
    return p[0] + p[1] / 60 + p[2].fillna(0) / 3600


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between coordinate arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def weekday_service_ids(g: dict) -> set | None:
    """Service ids active on a typical weekday (calendar.txt), or None if unknown."""
    cal = g.get("calendar")
    if cal is None or cal.empty:
        return None
    return set(cal.loc[cal["wednesday"] == "1", "service_id"])


def route_profiles_from_gtfs(g: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One row per route with supply-side features, plus trips per route per hour."""
    trips, st, stops, routes = g["trips"], g["stop_times"].copy(), g["stops"].copy(), g["routes"]
    svc = weekday_service_ids(g)
    if svc:
        trips = trips[trips["service_id"].isin(svc)]
    st = st[st["trip_id"].isin(trips["trip_id"])]
    st["t"] = gtfs_time_to_hours(st["departure_time"].where(st["departure_time"].notna(), st["arrival_time"]))
    st["stop_sequence"] = pd.to_numeric(st["stop_sequence"], errors="coerce")
    stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
    stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
    st = st.merge(stops[["stop_id", "stop_lat", "stop_lon", "stop_name"]], on="stop_id", how="left")
    st = st.sort_values(["trip_id", "stop_sequence"])
    st["seg_km"] = haversine_km(st["stop_lat"], st["stop_lon"],
                                st.groupby("trip_id")["stop_lat"].shift(-1),
                                st.groupby("trip_id")["stop_lon"].shift(-1))
    tr = st.groupby("trip_id").agg(start=("t", "min"), end=("t", "max"), km=("seg_km", "sum"),
                                   n_stops=("stop_id", "count")).reset_index()
    tr = tr.merge(trips[["trip_id", "route_id"]], on="trip_id")
    tr["dur_h"] = (tr["end"] - tr["start"]).clip(lower=1 / 60)
    tr["hour"] = (tr["start"] // 1 % 24).astype("Int64")

    g_r = tr.groupby("route_id")
    prof = pd.DataFrame({
        "trips_per_day": g_r.size(),
        "route_length_km": g_r["km"].median(),
        "n_stops": g_r["n_stops"].median(),
        "trip_duration_min": g_r["dur_h"].median() * 60,
        "first_departure_h": g_r["start"].min(),
        "last_departure_h": g_r["start"].max(),
    })
    prof["service_span_h"] = prof["last_departure_h"] - prof["first_departure_h"]
    prof["scheduled_speed_kmh"] = prof["route_length_km"] / (prof["trip_duration_min"] / 60)
    peak = tr[tr["hour"].isin([7, 8, 9, 17, 18, 19])].groupby("route_id").size() / 6
    prof["peak_trips_per_hour"] = peak.reindex(prof.index).fillna(0)
    prof["peak_headway_min"] = (60 / prof["peak_trips_per_hour"].replace(0, np.nan)).fillna(120).clip(upper=120)
    prof["stop_spacing_m"] = 1000 * prof["route_length_km"] / prof["n_stops"].clip(lower=2)
    prof = prof.replace([np.inf, -np.inf], np.nan).fillna(prof.median(numeric_only=True))
    names = routes.set_index("route_id")
    for c in ("route_short_name", "route_long_name"):
        if c in names:
            prof[c] = names[c].reindex(prof.index)
    tph = tr.groupby(["route_id", "hour"]).size().rename("trips").reset_index()
    return prof.reset_index(), tph


GTFS_CLUSTER_FEATURES = ["trips_per_day", "route_length_km", "n_stops", "trip_duration_min",
                         "service_span_h", "scheduled_speed_kmh", "peak_headway_min", "stop_spacing_m"]


def analyse_gtfs(file_like) -> dict:
    """Full upload analysis: profiles, KMeans/DBSCAN clusters, overlaps and flags."""
    g = read_gtfs(file_like)
    prof, tph = route_profiles_from_gtfs(g)
    X = StandardScaler().fit_transform(np.log1p(prof[GTFS_CLUSTER_FEATURES].clip(lower=0)))
    best_k, best_s = 2, -1
    for k in range(2, min(8, len(prof) - 1) + 1):
        lab = KMeans(k, n_init=10, random_state=42).fit_predict(X)
        s = silhouette_score(X, lab)
        if s > best_s:
            best_k, best_s = k, s
    prof["kmeans_cluster"] = KMeans(best_k, n_init=20, random_state=42).fit_predict(X) if len(prof) > 3 else 0
    ms = max(3, int(np.log(len(prof))) + 1)
    prof["dbscan_cluster"] = DBSCAN(eps=dbscan_eps(X, ms), min_samples=ms).fit_predict(X) if len(prof) > ms else 0

    stops = g["stops"].rename(columns={"stop_lat": "latitude", "stop_lon": "longitude"})
    stops["latitude"] = pd.to_numeric(stops["latitude"], errors="coerce")
    stops["longitude"] = pd.to_numeric(stops["longitude"], errors="coerce")
    rs = g["stop_times"][["trip_id", "stop_id"]].merge(g["trips"][["trip_id", "route_id"]]) \
        .drop_duplicates(["route_id", "stop_id"]).merge(stops[["stop_id", "latitude", "longitude", "stop_name"]])
    ov = stop_overlap(rs, prof["route_id"].tolist(), min_jaccard=0.3)

    q_low = prof["trips_per_day"].quantile(0.2)
    flags = []
    for _, r in prof.iterrows():
        f = []
        if r["trips_per_day"] <= q_low:
            f.append("Low frequency - consider merging or demand-responsive service")
        if r["peak_headway_min"] > 30:
            f.append("Peak headway > 30 min")
        if r["route_length_km"] > prof["route_length_km"].quantile(0.9):
            f.append("Very long - candidate for splitting")
        if r["scheduled_speed_kmh"] < prof["scheduled_speed_kmh"].quantile(0.1):
            f.append("Slow scheduled speed - bus-priority candidate")
        flags.append("; ".join(f) or "OK")
    prof["flags"] = flags
    return {"tables": {k: len(v) for k, v in g.items()}, "profiles": prof, "overlap": ov,
            "stops": rs, "k": best_k, "silhouette": best_s,
            "trips_per_hour": tph}
