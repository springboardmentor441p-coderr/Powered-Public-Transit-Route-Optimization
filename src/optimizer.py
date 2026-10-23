"""Module 6 - Route optimisation: frequency adjustment, merging, splitting + before/after simulation."""
import numpy as np, pandas as pd
from .config import *

DEFAULTS = dict(capacity=BUS_CAPACITY, ride_frac=RIDE_FRAC, target_lf=TARGET_LF, min_tph=MIN_TRIPS_PER_HOUR,
                max_tph=20, merge_overlap=0.5, merge_jaccard=0.3, split_km=20.0, split_peak_lf=1.3)

def _lf(board, trips, P):
    return np.where(trips > 0, board * P["ride_frac"] / (np.maximum(trips, 1) * P["capacity"]), np.nan)

def _find_merges(routes, pairs, wd, P):
    """Greedy: highest-overlap pairs of low-demand routes that one route can absorb."""
    if pairs is None or len(pairs) == 0: return {}
    cls = routes.set_index("route_uid").pred_class; trips = routes.set_index("route_uid").trips_per_day
    bd = routes.set_index("route_uid").daily_boardings
    cand = pairs[(pairs.overlap_ratio >= P["merge_overlap"]) & (pairs.jaccard >= P["merge_jaccard"])].sort_values("overlap_ratio", ascending=False)
    used, merges = set(), {}
    for _, p in cand.iterrows():
        a, b = p.route_a, p.route_b
        if a in used or b in used or a not in cls.index or b not in cls.index: continue
        ok = (cls[a] == "underutilized" and cls[b] in ("underutilized", "balanced")) or (cls[b] == "underutilized" and cls[a] == "balanced")
        if not ok: continue
        prim, sec = (a, b) if trips[a] >= trips[b] else (b, a)
        need_day = np.ceil((bd[a] + bd[b]) * P["ride_frac"] / (P["capacity"] * P["target_lf"]))
        if need_day <= trips[prim]:                      # primary can carry both without extra trips
            merges[sec] = prim; used |= {a, b}
    return merges

def _metrics(h, trips_col, routes_info, P, unit_col="unit"):
    h = h.copy(); h["lf"] = _lf(h.boardings, h[trips_col], P); h = h[h[trips_col] > 0]
    pax = h.boardings.sum()
    per_unit = h.groupby(unit_col).agg(peak_lf=("lf", lambda x: x.nlargest(3).mean()), trips=(trips_col, "sum"), b=("boardings", "sum"))
    avg_lf = per_unit.b * P["ride_frac"] / (per_unit.trips * P["capacity"])
    info = routes_info.reindex(h[unit_col].unique())
    tr = h.groupby(unit_col)[trips_col].sum().reindex(info.index)
    return dict(
        total_trips_day=float(h[trips_col].sum()),
        bus_hours_day=float((tr * info.trip_duration_min / 60).sum()), bus_km_day=float((tr * info.route_length_km).sum()),
        pax_share_in_overcrowded_hours=float(h.boardings[h.lf > OVER_PEAK_LF].sum() / pax),
        trip_share_nearly_empty=float(h[trips_col][h.lf < UNDER_AVG_LF].sum() / h[trips_col].sum()),
        avg_wait_min=float((h.boardings * 30 / h[trips_col]).sum() / pax),
        mean_peak_lf=float(per_unit.peak_lf.mean()), mean_avg_lf=float(avg_lf.mean()),
        n_routes_overcrowded=int((per_unit.peak_lf >= OVER_PEAK_LF).sum()), n_routes_underutilized=int((avg_lf < UNDER_AVG_LF).sum()),
        n_services=int(len(per_unit)))

def optimize(routes, hourly, pairs=None, params=None):
    """routes needs `pred_class`. Returns (recommendations, impact_summary, city_impact, after_hourly)."""
    P = {**DEFAULTS, **(params or {})}
    wd = hourly[hourly.day_type == "weekday"].copy()
    wd["cls"] = wd.route_uid.map(routes.set_index("route_uid").pred_class)
    wd["required"] = np.ceil(wd.boardings * P["ride_frac"] / (P["capacity"] * P["target_lf"])).astype(int)
    wd["after_trips"] = wd.trips
    over, under = wd.cls == "overcrowded", wd.cls == "underutilized"
    wd.loc[over, "after_trips"] = np.minimum(np.maximum(wd.trips, wd.required), np.maximum(wd.trips, P["max_tph"]))
    wd.loc[under, "after_trips"] = np.maximum(np.minimum(wd.trips, wd.required), np.minimum(wd.trips, P["min_tph"]))
    merges = _find_merges(routes, pairs, wd, P)
    wd["unit"] = wd.route_uid.map(lambda u: merges.get(u, u))
    after = wd.groupby(["unit", "hour"]).agg(boardings=("boardings", "sum"), trips_before=("trips", "sum"),
                                              after_trips=("after_trips", "sum"), city=("city", "first")).reset_index()
    m_units = set(merges.values())
    if m_units:
        req = np.ceil(after.boardings * P["ride_frac"] / (P["capacity"] * P["target_lf"]))
        merged_trips = np.minimum(np.maximum(req, P["min_tph"]), after.trips_before)
        after["after_trips"] = np.where(after.unit.isin(m_units), merged_trips, after.after_trips)
    info = routes.set_index("route_uid")
    before_h = wd.assign(unit=wd.route_uid)
    before = _metrics(before_h, "trips", info, P); aft = _metrics(after, "after_trips", info, P)
    # per-city impact
    rows = []
    for c in sorted(wd.city.unique()):
        b = _metrics(before_h[before_h.city == c], "trips", info, P); a = _metrics(after[after.city == c], "after_trips", info, P)
        rows.append(dict(city=c, **{f"before_{k}": v for k, v in b.items()}, **{f"after_{k}": v for k, v in a.items()}))
    city_impact = pd.DataFrame(rows)
    # per-route recommendations
    pk = list(PEAK_HOURS)
    unit_after_day = after.groupby("unit").after_trips.sum()
    unit_peak_after = after[after.hour.isin(pk)].groupby("unit").after_trips.mean()
    peak_before = wd[wd.hour.isin(pk)].groupby("route_uid").trips.mean()
    recs = []
    for _, r in routes.iterrows():
        u = r.route_uid; sec = u in merges; prim = u in m_units
        tb = r.trips_per_day; ta = 0 if sec else float(unit_after_day.get(u, tb))
        pb = peak_before.get(u, 0); pa = 0 if sec else float(unit_peak_after.get(u, pb))
        hb, ha = (60 / pb if pb else np.nan), (60 / pa if pa else np.nan)
        extra = ""
        if sec:
            tgt = merges[u]; act = "Merge (retire)"
            det = f"Retire and merge into {info.loc[tgt, 'route_short_name']}; overlap is high and the combined demand fits existing capacity."
        elif prim:
            others = [info.loc[s, "route_short_name"] for s, p in merges.items() if p == u]
            act = "Merge (absorb)"; det = f"Absorb route {', '.join(others)}; trips/day {tb:.0f} -> {ta:.0f}."
        elif r.pred_class == "overcrowded" and ta > tb:
            act = "Increase frequency"; det = f"Peak headway {hb:.1f} -> {ha:.1f} min; +{ta - tb:.0f} trips/day to bring peak load toward {P['target_lf']:.0%} of capacity."
        elif r.pred_class == "underutilized" and ta < tb:
            act = "Reduce frequency"; det = f"Cut {tb - ta:.0f} trips/day (peak headway {hb:.1f} -> {ha:.1f} min); redeploy buses to crowded routes."
        else:
            act = "No change"; det = "Service level is consistent with demand."
        if r.pred_class == "overcrowded" and r.route_length_km >= P["split_km"] and r.peak_lf >= P["split_peak_lf"]:
            extra = f"Consider splitting into two short-turn services (route is {r.route_length_km:.0f} km long)."
        recs.append(dict(route_uid=u, city=r.city, route_short_name=r.route_short_name, route_long_name=r.route_long_name,
                         pred_class=r.pred_class, confidence=r.get("confidence", np.nan), peak_lf=r.peak_lf, avg_lf=r.avg_lf,
                         action=act, detail=det, structural_option=extra, trips_day_before=tb, trips_day_after=ta,
                         delta_trips=ta - tb, peak_headway_before_min=hb, peak_headway_after_min=ha,
                         delta_bus_km=(ta - tb) * r.route_length_km, merged_with=merges.get(u, ""),
                         priority=r.daily_boardings * abs(r.peak_lf - P["target_lf"])))
    recs = pd.DataFrame(recs).sort_values("priority", ascending=False).reset_index(drop=True)
    return recs, dict(before=before, after=aft, params=P, n_merges=len(merges)), city_impact, after
