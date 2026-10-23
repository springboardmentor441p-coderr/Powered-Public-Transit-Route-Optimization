"""
Synthetic GTFS generator for 23 Indian cities.

The commercial Lepton Software feed cannot be redistributed, so this script builds
feeds with the *same file layout* (routes/trips/stop_times/stops/calendar) plus an
optional `ridership.csv` (boardings per route/day-type/hour). The loader in
src/data_loader.py reads real GTFS feeds identically.

Usage:  python data/generate_synthetic_gtfs.py [--out data/gtfs] [--seed 7]
        python data/generate_synthetic_gtfs.py --city Pune --zip sample_uploads
"""
import argparse, sys, zipfile
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import DEMAND_K, BUS_CAPACITY, RIDE_FRAC
from src.demand import hour_profile, stop_attraction

# city: (lat, lon, tier)  tier: 3 = metro, 2 = large, 1 = mid-size
CITIES = {
    "Delhi": (28.6139, 77.2090, 3), "Mumbai": (19.0760, 72.8777, 3), "Bengaluru": (12.9716, 77.5946, 3),
    "Hyderabad": (17.3850, 78.4867, 3), "Chennai": (13.0827, 80.2707, 3), "Kolkata": (22.5726, 88.3639, 3),
    "Pune": (18.5204, 73.8567, 2), "Ahmedabad": (23.0225, 72.5714, 2), "Jaipur": (26.9124, 75.7873, 2),
    "Lucknow": (26.8467, 80.9462, 2), "Surat": (21.1702, 72.8311, 2), "Kanpur": (26.4499, 80.3319, 2),
    "Nagpur": (21.1458, 79.0882, 2), "Indore": (22.7196, 75.8577, 2), "Bhopal": (23.2599, 77.4126, 2),
    "Visakhapatnam": (17.6868, 83.2185, 2), "Patna": (25.5941, 85.1376, 1), "Vadodara": (22.3072, 73.1812, 1),
    "Coimbatore": (11.0168, 76.9558, 1), "Kochi": (9.9312, 76.2673, 1), "Chandigarh": (30.7333, 76.7794, 1),
    "Bhubaneswar": (20.2961, 85.8245, 1), "Thiruvananthapuram": (8.5241, 76.9366, 1),
}
TIER = {3: dict(routes=30, stops=400, sigma=8.0), 2: dict(routes=22, stops=300, sigma=5.5),
        1: dict(routes=16, stops=220, sigma=4.0)}

def _fmt(sec):
    sec = np.asarray(sec, dtype=int)
    return pd.Series([f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}" for s in sec])

def generate_city(city, seed=7, n_routes=None):
    lat0, lon0, tier = CITIES[city]
    cfg = TIER[tier]; n_routes = n_routes or cfg["routes"]
    rng = np.random.default_rng(seed + sum(map(ord, city)))
    sigma = cfg["sigma"]; kx = 111.0 * np.cos(np.radians(lat0))
    xy = rng.normal(0, sigma, (cfg["stops"], 2))             # km east/north of centre
    xy[0] = 0
    stops = pd.DataFrame({
        "stop_id": [f"S{i:04d}" for i in range(len(xy))],
        "stop_name": [f"{city} Stop {i}" for i in range(len(xy))],
        "stop_lat": lat0 + xy[:, 1] / 111.0, "stop_lon": lon0 + xy[:, 0] / kx})
    dcen = np.hypot(xy[:, 0], xy[:, 1])
    attr = stop_attraction(dcen, 1.2 * sigma)
    central = np.argsort(dcen)[:15]

    routes, trips, st_parts, rid_rows = [], [], [], []
    tid = 0
    prof_wd, prof_we = hour_profile("weekday"), hour_profile("weekend")
    for r in range(n_routes):
        for _ in range(50):
            a = rng.choice(central) if rng.random() < 0.45 else rng.integers(len(xy))
            d = np.hypot(*(xy - xy[a]).T)
            cand = np.where((d > 5) & (d < 2.6 * sigma + 8))[0]
            if len(cand) == 0: continue
            b = rng.choice(cand)
            n_pts = int(np.clip(d[b] / 0.6, 8, 60))
            t = np.linspace(0, 1, n_pts)[:, None]
            pts = xy[a] + t * (xy[b] - xy[a]) + rng.normal(0, 0.35, (n_pts, 2))
            idx = [int(np.argmin(np.hypot(*(xy - p).T))) for p in pts]
            seq = list(dict.fromkeys(idx))
            if len(seq) >= 6: break
        else:
            continue
        seg = np.hypot(*np.diff(xy[seq], axis=0).T)
        potential = attr[seq].sum() * DEMAND_K * rng.lognormal(0, 0.35)       # hidden true demand/day
        balanced_trips = potential * RIDE_FRAC / (BUS_CAPACITY * 0.40)        # trips for avg LF ~ 0.4
        total_trips = int(np.clip(balanced_trips * rng.lognormal(0, 0.55), 10, 230))
        start_h, end_h = int(rng.choice([5, 6])), int(rng.choice([21, 22, 23]))
        speed = float(np.clip(rng.normal(17, 3) * (0.8 + 0.2 * min(1, np.mean(dcen[seq]) / sigma)), 10, 26))
        rid = f"R{r+1:03d}"
        routes.append(dict(route_id=rid, agency_id="STU", route_short_name=f"{city[:2].upper()}-{r+1}",
                           route_long_name=f"{stops.stop_name[seq[0]]} - {stops.stop_name[seq[-1]]}", route_type=3))
        arr_off = np.concatenate([[0], np.cumsum(seg / speed * 3600 + 25)])  # secs from first stop
        hrs = np.arange(start_h, end_h)
        w = np.where(np.isin(hrs, (7, 8, 9, 17, 18, 19)), 2.0, 1.0); w = w / w.sum()
        for service, mult in (("WD", 1.0), ("WE", 0.7)):
            per_hr = rng.multinomial(max(1, int(total_trips * mult)), w)
            for direction in (0, 1):
                order = seq if direction == 0 else seq[::-1]
                offs = arr_off if direction == 0 else arr_off[-1] - arr_off[::-1]
                deps = []
                for h, n in zip(hrs, per_hr):
                    n_dir = n // 2 + (n % 2 if direction == 0 else 0)
                    if n_dir: deps += list(h * 3600 + (np.arange(n_dir) + rng.random()) * 3600 / n_dir)
                for dep in deps:
                    tid += 1; trip_id = f"T{tid:06d}"
                    trips.append((rid, service, trip_id, direction))
                    st_parts.append(pd.DataFrame({
                        "trip_id": trip_id, "stop_sequence": np.arange(1, len(order) + 1),
                        "stop_id": stops.stop_id.values[order],
                        "arrival_time": _fmt(dep + offs).values, "departure_time": _fmt(dep + offs + 20).values}))
        for dt, prof in (("weekday", prof_wd), ("weekend", prof_we)):   # ground-truth ridership
            f = 1.0 if dt == "weekday" else 0.65
            for h in hrs:
                rid_rows.append((rid, dt, int(h), max(0, potential * f * prof[h] * rng.lognormal(0, 0.15))))
    cal = pd.DataFrame([
        dict(service_id="WD", monday=1, tuesday=1, wednesday=1, thursday=1, friday=1, saturday=0, sunday=0,
             start_date=20250101, end_date=20251231),
        dict(service_id="WE", monday=0, tuesday=0, wednesday=0, thursday=0, friday=0, saturday=1, sunday=1,
             start_date=20250101, end_date=20251231)])
    trips_df = pd.DataFrame(trips, columns=["route_id", "service_id", "trip_id", "direction_id"])
    rid_df = pd.DataFrame(rid_rows, columns=["route_id", "day_type", "hour", "boardings"])
    rid_df["boardings"] = rid_df.boardings.round(1)
    return dict(routes=pd.DataFrame(routes), trips=trips_df, stop_times=pd.concat(st_parts, ignore_index=True),
                stops=stops, calendar=cal), rid_df

def generate_history(rid, city, seed=7, n_months=45, end="2026-09"):
    """Monthly average-weekday boardings per route (past data): trend + seasonality + AR(1) noise + occasional level shifts.
    Normalised so the mean of the last 3 months equals the current ridership level in `rid`."""
    rng = np.random.default_rng(seed * 7 + sum(map(ord, city)) + 1)
    base = rid[rid.day_type == "weekday"].groupby("route_id").boardings.sum()
    months = pd.period_range(end=end, periods=n_months, freq="M"); T = n_months; t = np.arange(T)
    city_g, amp = rng.normal(0.045, 0.025), rng.uniform(0.7, 1.3)
    season = amp * np.array([-.01, -.02, 0, -.04, -.06, .02, -.05, -.04, .01, .05, .06, -.03])[months.month.values - 1]
    rows = []
    for r, b in base.items():
        g = city_g + rng.normal(0, 0.05)
        shift = np.zeros(T)
        if rng.random() < 0.05: shift[rng.integers(18, 38):] = rng.choice([-0.25, 0.2])
        e = np.zeros(T)
        for i in range(1, T): e[i] = 0.5 * e[i - 1] + rng.normal(0, 0.025)
        m = np.exp(g * (t - (T - 2)) / 12 + season * rng.uniform(0.7, 1.3) + shift + e); m /= m[-3:].mean()
        rows += list(zip([r] * T, months.strftime("%Y-%m"), np.round(b * m, 1)))
    return pd.DataFrame(rows, columns=["route_id", "month", "boardings"])

def write_city(city, root, seed=7, make_zip=None):
    feed, rid = generate_city(city, seed)
    d = Path(root) / city; d.mkdir(parents=True, exist_ok=True)
    for k, df in feed.items(): df.to_csv(d / f"{k}.txt", index=False)
    rid.to_csv(d / "ridership.csv", index=False)
    hist = generate_history(rid, city, seed); hist.to_csv(d / "ridership_history.csv", index=False)
    if make_zip:
        Path(make_zip).mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(Path(make_zip) / f"{city}_gtfs.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for k in feed: z.write(d / f"{k}.txt", f"{k}.txt")
        rid.to_csv(Path(make_zip) / f"{city}_ridership.csv", index=False); hist.to_csv(Path(make_zip) / f"{city}_history.csv", index=False)
    return feed

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "gtfs"))
    ap.add_argument("--seed", type=int, default=7); ap.add_argument("--city"); ap.add_argument("--zip")
    a = ap.parse_args()
    for c in ([a.city] if a.city else CITIES):
        f = write_city(c, a.out, a.seed, a.zip)
        print(f"{c:20s} routes={len(f['routes']):3d} trips={len(f['trips']):6d} stop_times={len(f['stop_times']):7d}")
