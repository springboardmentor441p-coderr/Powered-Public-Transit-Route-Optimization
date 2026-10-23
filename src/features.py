"""Module 2b - Feature engineering: trip/route/stop features, demand estimation, labels."""
import numpy as np, pandas as pd
from .config import *
from .demand import hour_profile, stop_attraction

WD_COLS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

def haversine(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))

def trip_table(feed):
    """One row per trip: timing, length, day type, hour of day."""
    st = feed["stop_times"].merge(feed["stops"][["stop_id", "stop_lat", "stop_lon"]], on="stop_id")
    st = st.sort_values(["trip_id", "stop_sequence"])
    same = st.trip_id.eq(st.trip_id.shift())
    st["seg_km"] = np.where(same, haversine(st.stop_lat.shift(), st.stop_lon.shift(), st.stop_lat, st.stop_lon), 0.0)
    g = st.groupby("trip_id").agg(start_sec=("dep_sec", "first"), end_sec=("arr_sec", "last"),
                                  n_stops=("stop_id", "size"), dist_km=("seg_km", "sum")).reset_index()
    t = feed["trips"][["trip_id", "route_id", "service_id", "direction_id"]].merge(g, on="trip_id")
    cal = feed["calendar"].copy()
    cal["day_type"] = np.where(cal[WD_COLS].sum(axis=1) >= 3, "weekday", "weekend")
    t = t.merge(cal[["service_id", "day_type"]], on="service_id", how="left")
    t["day_type"] = t.day_type.fillna("weekday")
    t["duration_min"] = (t.end_sec - t.start_sec) / 60
    t["hour"] = (t.start_sec // 3600).astype(int) % 24
    return t, st

def route_supply_features(t):
    wd = t[t.day_type == "weekday"]
    hr = wd.groupby(["route_id", "hour"]).size().unstack(fill_value=0).reindex(columns=range(24), fill_value=0)
    gaps = (wd.sort_values(["route_id", "direction_id", "start_sec"])
              .assign(gap=lambda d: d.groupby(["route_id", "direction_id"]).start_sec.diff() / 60))
    gs = gaps.groupby("route_id").gap.agg(["mean", "std"])
    out = wd.groupby("route_id").agg(trips_per_day=("trip_id", "size"), route_length_km=("dist_km", "median"),
                                     n_stops=("n_stops", "median"), trip_duration_min=("duration_min", "median"),
                                     service_start_hr=("hour", "min"), service_end_hr=("hour", "max"))
    we = t[t.day_type == "weekend"].groupby("route_id").size().rename("weekend_trips")
    out = out.join(we).fillna({"weekend_trips": 0})
    out["weekend_ratio"] = out.weekend_trips / out.trips_per_day
    out["service_span_hr"] = out.service_end_hr - out.service_start_hr + 1
    out["avg_stop_spacing_km"] = out.route_length_km / (out.n_stops - 1).clip(lower=1)
    out["avg_speed_kmph"] = (out.route_length_km / (out.trip_duration_min / 60).clip(lower=0.05)).clip(upper=80)
    pk = hr[list(PEAK_HOURS)].where(hr[list(PEAK_HOURS)] > 0)
    op = hr[[h for h in range(24) if h not in PEAK_HOURS]]; op = op.where(op > 0)
    out["peak_trips_per_hr"] = pk.mean(axis=1).fillna(0); out["offpeak_trips_per_hr"] = op.mean(axis=1).fillna(0)
    out["headway_peak_min"] = 60 / out.peak_trips_per_hr.replace(0, np.nan)
    out["headway_offpeak_min"] = 60 / out.offpeak_trips_per_hr.replace(0, np.nan)
    out["headway_cv"] = (gs["std"] / gs["mean"]).reindex(out.index)
    out = out.fillna({"headway_peak_min": 120, "headway_offpeak_min": 120, "headway_cv": 0})
    sup = hr.stack().rename("trips").reset_index(); sup["day_type"] = "weekday"
    wk = t[t.day_type == "weekend"].groupby(["route_id", "hour"]).size().rename("trips").reset_index(); wk["day_type"] = "weekend"
    return out.reset_index(), pd.concat([sup, wk], ignore_index=True)[lambda d: d.trips > 0]

def stop_and_overlap_features(feed, t, st, routes):
    """Stop attraction, per-route stop-sharing / overlap, merge candidates."""
    rs = st.merge(feed["trips"][["trip_id", "route_id"]], on="trip_id")[["route_id", "stop_id"]].drop_duplicates()
    stops = feed["stops"][feed["stops"].stop_id.isin(rs.stop_id)].copy()
    clat, clon = stops.stop_lat.median(), stops.stop_lon.median()
    stops["dist_center_km"] = haversine(clat, clon, stops.stop_lat, stops.stop_lon)
    scale = max(1.02 * stops.dist_center_km.median(), 0.5)
    stops["attraction"] = stop_attraction(stops.dist_center_km, scale)
    stops["n_routes"] = stops.stop_id.map(rs.groupby("stop_id").route_id.nunique())
    wd_ids = t[t.day_type == "weekday"].trip_id
    stops["departures_day"] = stops.stop_id.map(st[st.trip_id.isin(wd_ids)].groupby("stop_id").size()).fillna(0)
    rs = rs.merge(stops[["stop_id", "attraction", "dist_center_km", "n_routes"]], on="stop_id")
    g = rs.groupby("route_id").agg(sum_attr=("attraction", "sum"), mean_stop_attr=("attraction", "mean"),
                                   mean_dist_center_km=("dist_center_km", "mean"), n_unique_stops=("stop_id", "size"),
                                   frac_stops_shared=("n_routes", lambda x: (x >= 2).mean()),
                                   n_hub_stops=("n_routes", lambda x: int((x >= 3).sum())))
    # pairwise overlap
    ids = sorted(rs.route_id.unique()); stop_ids = sorted(rs.stop_id.unique())
    ri = {r: i for i, r in enumerate(ids)}; si = {s: i for i, s in enumerate(stop_ids)}
    M = np.zeros((len(ids), len(stop_ids)), dtype=np.int32)
    M[rs.route_id.map(ri).values, rs.stop_id.map(si).values] = 1
    C = M @ M.T; n = np.diag(C)
    pairs = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if C[i, j] > 0:
                ratio = C[i, j] / min(n[i], n[j]); jac = C[i, j] / (n[i] + n[j] - C[i, j])
                if ratio >= 0.2: pairs.append((ids[i], ids[j], int(C[i, j]), ratio, jac))
    pairs = pd.DataFrame(pairs, columns=["route_a", "route_b", "shared_stops", "overlap_ratio", "jaccard"])
    mx = pd.concat([pairs.set_index("route_a").overlap_ratio, pairs.set_index("route_b").overlap_ratio]).groupby(level=0).max() if len(pairs) else pd.Series(dtype=float)
    g["max_overlap"] = mx.reindex(g.index).fillna(0)
    stops["stop_uid_dummy"] = 0
    return g.reset_index(), stops.drop(columns="stop_uid_dummy"), pairs, rs

def hourly_demand(routes, supply, ridership):
    """Boardings per route/day-type/hour: observed if supplied, else estimated by the demand proxy."""
    if ridership is not None and len(ridership):
        r = ridership.copy(); r["route_id"] = r.route_id.astype(str)
        h = supply.merge(r[["route_id", "day_type", "hour", "boardings"]], on=["route_id", "day_type", "hour"], how="left")
        h["boardings"] = h.boardings.fillna(0.0); src = "observed"
    else:
        rows = []
        pot = routes.set_index("route_id").sum_attr * DEMAND_K
        for dt, f in (("weekday", 1.0), ("weekend", 0.65)):
            prof = hour_profile(dt)
            s = supply[supply.day_type == dt].copy()
            share = s.hour.map(lambda x: prof[x])
            share = share / share.groupby(s.route_id).transform("sum")
            s["boardings"] = s.route_id.map(pot) * f * share; rows.append(s)
        h = pd.concat(rows); src = "estimated"
    h["pax_per_trip"] = h.boardings / h.trips
    h["load_factor"] = h.boardings * RIDE_FRAC / (h.trips * BUS_CAPACITY)
    h["ridership_source"] = src
    return h

def usage_features(h):
    wd = h[h.day_type == "weekday"]
    def agg(d):
        top3 = d.load_factor.nlargest(3).mean()
        tot = d.boardings.sum()
        return pd.Series(dict(
            daily_boardings=tot, peak_hour=int(d.loc[d.boardings.idxmax(), "hour"]), peak_boardings_hr=d.boardings.max(),
            peak_lf=top3, avg_lf=tot * RIDE_FRAC / (d.trips.sum() * BUS_CAPACITY),
            peak_ratio=d.boardings.max() / max(d.boardings.mean(), 1e-9),
            am_share=d[d.hour.between(6, 10)].boardings.sum() / max(tot, 1e-9),
            pm_share=d[d.hour.between(16, 20)].boardings.sum() / max(tot, 1e-9),
            midday_share=d[d.hour.between(11, 15)].boardings.sum() / max(tot, 1e-9)))
    return wd.groupby("route_id").apply(agg, include_groups=False).reset_index()

def label_routes(peak_lf, avg_lf, over=OVER_PEAK_LF, under=UNDER_AVG_LF):
    return np.where(peak_lf >= over, "overcrowded", np.where(avg_lf < under, "underutilized", "balanced"))

def build_city_dataset(feed, ridership, city):
    """Full per-city feature build. Returns dict of DataFrames with globally-unique ids."""
    from .cleaning import clean_feed
    feed, report = clean_feed(feed)
    t, st = trip_table(feed)
    sup_feat, supply = route_supply_features(t)
    ov_feat, stops, pairs, rs = stop_and_overlap_features(feed, t, st, sup_feat)
    routes = feed["routes"][["route_id", "route_short_name", "route_long_name"]].merge(sup_feat, on="route_id").merge(ov_feat, on="route_id")
    routes["demand_potential_day"] = routes.sum_attr * DEMAND_K
    routes["proxy_pax_per_trip"] = routes.demand_potential_day / routes.trips_per_day
    routes["proxy_lf"] = routes.proxy_pax_per_trip * RIDE_FRAC / BUS_CAPACITY
    px = usage_features(hourly_demand(routes, supply, None))        # structural demand proxy (never uses ridership)
    routes = routes.merge(px[["route_id", "peak_lf", "avg_lf", "peak_ratio"]].rename(columns={
        "peak_lf": "proxy_peak_lf", "avg_lf": "proxy_avg_lf", "peak_ratio": "proxy_peak_ratio"}), on="route_id")
    hourly = hourly_demand(routes, supply, ridership)
    routes = routes.merge(usage_features(hourly), on="route_id")
    routes["boardings_per_km"] = routes.daily_boardings / routes.route_length_km.clip(lower=0.5)
    routes["boardings_per_trip"] = routes.daily_boardings / routes.trips_per_day
    routes["label"] = label_routes(routes.peak_lf, routes.avg_lf)
    routes["ridership_source"] = hourly.ridership_source.iloc[0]
    routes["city"] = city
    # stop-level estimated usage: distribute each route's daily boardings over its stops by attraction
    rs = rs.merge(routes[["route_id", "daily_boardings"]], on="route_id")
    rs["share"] = rs.attraction / rs.groupby("route_id").attraction.transform("sum")
    stops["est_boardings_day"] = stops.stop_id.map((rs.daily_boardings * rs.share).groupby(rs.stop_id).sum()).fillna(0)
    # representative stop sequence per route (longest trip, direction 0 preferred)
    rep = t.sort_values(["route_id", "n_stops", "direction_id"], ascending=[True, False, True]).drop_duplicates("route_id")
    rstops = st[st.trip_id.isin(rep.trip_id)].merge(rep[["trip_id", "route_id"]], on="trip_id")[["route_id", "stop_sequence", "stop_id", "stop_lat", "stop_lon"]]
    # globally unique ids
    uid = lambda s: city + "|" + s.astype(str)
    routes.insert(0, "route_uid", uid(routes.route_id)); hourly["route_uid"] = uid(hourly.route_id)
    hourly["city"] = city; rstops["route_uid"] = uid(rstops.route_id); rstops["city"] = city
    stops["stop_uid"] = uid(stops.stop_id); stops["city"] = city
    if len(pairs):
        pairs["route_a"] = uid(pairs.route_a); pairs["route_b"] = uid(pairs.route_b)
    pairs["city"] = city
    n_routes = len(routes)
    routes["city_n_routes"] = n_routes
    routes["city_tier"] = "small" if n_routes < 25 else ("medium" if n_routes < 100 else "large")
    return dict(routes=routes, hourly=hourly, stops=stops, route_stops=rstops, overlap_pairs=pairs, cleaning=report)
