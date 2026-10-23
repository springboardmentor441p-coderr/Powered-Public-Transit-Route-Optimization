"""RouteRanker API (FastAPI). Serves the ML pipeline to the React frontend and, in production, the built frontend itself.
Run:  uvicorn server.main:app --port 8000"""
import importlib.util, io, json, uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
import numpy as np, pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.config import *
from src import pipeline, data_loader
from src.forecast import apply_scenario
from src.optimizer import optimize, DEFAULTS

ST = dict(art=None, demo=None, metrics=None, sessions={}, cache={})
PKEYS = ["capacity", "target_lf", "min_tph", "max_tph", "merge_overlap", "split_km"]
DIST = ROOT / "frontend" / "dist"

def _gen():
    spec = importlib.util.spec_from_file_location("gen", ROOT / "data" / "generate_synthetic_gtfs.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

@asynccontextmanager
async def lifespan(app):
    if not ((OUT_DIR / "routes.csv").exists() and (MODEL_DIR / "routeranker_models.joblib").exists()):
        import train; train.main()                                   # first start on a fresh server
    ST["art"] = pipeline.load_art(); ST["demo"] = pipeline.load_results()
    ST["metrics"] = json.load(open(OUT_DIR / "metrics.json")); yield

app = FastAPI(title="RouteRanker API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)): return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.bool_): return bool(o)
    return o

def J(o): return JSONResponse(clean(o))
def rec(df, cols=None):
    d = df if cols is None else df[cols]; return json.loads(d.to_json(orient="records"))

def get_ctx(dataset: str = "demo", scenario: str = "today", capacity: int = DEFAULTS["capacity"], target_lf: float = DEFAULTS["target_lf"],
            min_tph: int = DEFAULTS["min_tph"], max_tph: int = DEFAULTS["max_tph"], merge_overlap: float = DEFAULTS["merge_overlap"],
            split_km: float = DEFAULTS["split_km"], cities: str = ""):
    base = ST["demo"] if dataset == "demo" else ST["sessions"].get(dataset)
    if base is None: raise HTTPException(404, "Unknown dataset (session expired?)")
    has_fc = "fc_mult_avg" in base["routes"]
    if scenario not in ("today", "avg", "peak"): raise HTTPException(400, "scenario must be today | avg | peak")
    scen = scenario if has_fc else "today"
    params = dict(capacity=capacity, target_lf=target_lf, min_tph=min_tph, max_tph=max_tph, merge_overlap=merge_overlap, split_km=split_km)
    key = (dataset, scen, *params.values())
    if key not in ST["cache"]:
        if len(ST["cache"]) > 30: ST["cache"].pop(next(iter(ST["cache"])))
        r, h = apply_scenario(base["routes"], base["hourly"], scen)
        recs, impact, ci, after = optimize(r, h, base["overlap_pairs"], params)
        ST["cache"][key] = dict(routes=r, hourly=h, recs=recs, impact=impact, ci=ci, after=after)
    c = ST["cache"][key]; allc = sorted(base["routes"].city.unique())
    sel = [x for x in cities.split(",") if x in allc] or allc
    return SimpleNamespace(base=base, params=params, scenario=scen, has_fc=has_fc, cities=sel, all_cities=allc, dataset=dataset, **c)

def inc(df, c): return df[df.city.isin(c.cities)]

# ---------------------------------------------------------------- meta
@app.get("/api/health")
def health(): return {"status": "ok", "ready": ST["demo"] is not None}

@app.get("/api/meta")
def meta(c=Depends(get_ctx)):
    m = ST["metrics"]
    return J(dict(
        datasets=[dict(id="demo", label="Demo – 23 Indian cities")] + [dict(id=k, label=v["label"]) for k, v in ST["sessions"].items()],
        cities=c.all_cities, selected=c.cities, has_forecast=c.has_fc, scenario=c.scenario, params=c.params, defaults={k: DEFAULTS[k] for k in PKEYS},
        ridership_source=str(c.base["routes"].ridership_source.iloc[0]), generator_cities=list(_gen().CITIES),
        model=dict(best=m["best"], classifier=m["classifier"], forecast=m.get("forecast"), clustering=m["clustering"], importance=m["feature_importance"])))

# ---------------------------------------------------------------- overview
@app.get("/api/overview")
def overview(c=Depends(get_ctx)):
    R = inc(c.routes, c); cls = R.groupby(["city", "pred_class"]).size().unstack(fill_value=0).reindex(columns=CLASSES, fill_value=0).reset_index()
    sc = R[["avg_lf", "peak_lf", "pred_class", "city", "route_short_name"]].rename(columns=dict(avg_lf="x", peak_lf="y", pred_class="cls", route_short_name="name"))
    return J(dict(kpis=dict(cities=len(c.cities), routes=len(R), **{k: int((R.pred_class == k).sum()) for k in CLASSES}),
                  by_city=rec(cls), scatter=rec(sc), top=rec(inc(c.recs, c).head(10), ["city", "route_short_name", "pred_class", "action", "detail", "structural_option"]),
                  thresholds=dict(over=OVER_PEAK_LF, under=UNDER_AVG_LF)))

# ---------------------------------------------------------------- EDA
@app.get("/api/eda")
def eda(city: str, c=Depends(get_ctx)):
    H, R = c.hourly, c.routes
    g = H[H.city == city].groupby(["hour", "day_type"]).boardings.sum().unstack(fill_value=0).reindex(range(24), fill_value=0).reset_index()
    p = inc(H[H.day_type == "weekday"], c).pivot_table(index="city", columns="hour", values="boardings", aggfunc="sum").reindex(columns=range(24)).fillna(0)
    p = p.div(p.sum(axis=1), axis=0)
    S = c.base["stops"]; S = S[S.city == city]
    pr = c.base["overlap_pairs"]; pr = pr[pr.city == city] if len(pr) else pr
    u = set(R[(R.city == city) & (R.label == "underutilized")].route_uid); nm = R.set_index("route_uid").route_short_name
    ov = pr[(pr.overlap_ratio >= 0.5) & (pr.route_a.isin(u) | pr.route_b.isin(u))].sort_values("overlap_ratio", ascending=False).head(30) if len(pr) else pr
    ov = ov.assign(route_a=ov.route_a.map(nm), route_b=ov.route_b.map(nm)) if len(ov) else ov
    return J(dict(hourly=rec(g), heat=dict(cities=list(p.index), hours=list(range(24)), z=p.values.round(4).tolist()),
                  stops=rec(S.rename(columns=dict(stop_lat="lat", stop_lon="lon", est_boardings_day="w", stop_name="name")), ["lat", "lon", "w", "name"]),
                  overlaps=rec(ov, ["route_a", "route_b", "shared_stops", "overlap_ratio", "jaccard"]) if len(ov) else []))

# ---------------------------------------------------------------- clusters / predictions
@app.get("/api/clusters")
def clusters(c=Depends(get_ctx)):
    R = inc(c.routes, c); R = R.assign(dbscan=np.where(R.dbscan_cluster == -1, "outlier", "cluster " + R.dbscan_cluster.astype(str)))
    prof = R.groupby("kmeans_cluster").agg(routes=("route_uid", "size"), boardings_day=("daily_boardings", "mean"), avg_lf=("avg_lf", "mean"),
                                           peak_lf=("peak_lf", "mean"), trips_day=("trips_per_day", "mean"), length_km=("route_length_km", "mean")).round(2).reset_index()
    pts = R[["pca1", "pca2", "kmeans_cluster", "dbscan", "city", "route_short_name"]].rename(columns=dict(route_short_name="name", kmeans_cluster="kmeans"))
    return J(dict(points=rec(pts), profiles=rec(prof), metrics=ST["metrics"]["clustering"]))

@app.get("/api/predictions")
def predictions(c=Depends(get_ctx)):
    R = inc(c.base["routes"], c); m = ST["metrics"]
    rows = R[["city", "route_short_name", "route_long_name", "pred_class", "confidence", "label", "peak_lf", "avg_lf", "trips_per_day", "route_length_km"]]
    return J(dict(models=m["classifier"], best=m["best"], classes=CLASSES, importance=m["feature_importance"], report=m["classification_report"], routes=rec(rows.round(3))))

# ---------------------------------------------------------------- forecast
@app.get("/api/forecast")
def forecast(city: str, route: str = "", c=Depends(get_ctx)):
    b = c.base
    if not c.has_fc or "forecast" not in b or "history" not in b: return J(dict(available=False))
    Hi, F = b["history"], b["forecast"]; fm = ST["metrics"].get("forecast")
    hc = Hi[Hi.city == city].groupby("month").boardings.sum().reset_index(); fc = F[F.city == city].groupby("month").forecast.sum().reset_index()
    bt = b.get("backtest_city"); bt = bt[bt.city == city][["month", "model", "actual"]] if bt is not None else pd.DataFrame()
    R = b["routes"]; Rc = R[R.city == city]
    uid = route if route in set(Rc.route_uid) else Rc.route_uid.iloc[0]
    q = R.copy(); q["class_now"] = q.pred_class
    risk = q[q.city.isin(c.cities)].sort_values("fc_growth_pct", ascending=False)
    n_risk = int(((q.class_peak == "overcrowded") & (q.class_now != "overcrowded") & q.city.isin(c.cities)).sum())
    return J(dict(available=True, metrics=fm, city_hist=rec(hc), city_fc=rec(fc), backtest=rec(bt) if len(bt) else [],
                  routes=rec(Rc[["route_uid", "route_short_name"]]), route=uid, route_hist=rec(Hi[Hi.route_uid == uid], ["month", "boardings"]),
                  route_fc=rec(F[F.route_uid == uid], ["month", "forecast", "lo", "hi"]), n_risk=n_risk,
                  risk=rec(risk.head(25), ["city", "route_short_name", "fc_growth_pct", "fc_peak_month", "class_now", "class_avg", "class_peak"])))

# ---------------------------------------------------------------- recommendations / impact
@app.get("/api/recommendations")
def recommendations(c=Depends(get_ctx)):
    r = inc(c.recs, c)
    cols = ["route_uid", "city", "route_short_name", "pred_class", "action", "detail", "structural_option", "trips_day_before", "trips_day_after",
            "peak_headway_before_min", "peak_headway_after_min", "delta_bus_km", "priority"]
    return J(dict(recs=rec(r.round(2), cols), actions=r.action.value_counts().to_dict(), n_merges=c.impact["n_merges"]))

@app.get("/api/route")
def route_detail(uid: str, c=Depends(get_ctx)):
    P = c.params; h = c.hourly[(c.hourly.route_uid == uid) & (c.hourly.day_type == "weekday")].sort_values("hour")
    if h.empty: raise HTTPException(404, "route not found")
    a = c.after[c.after.unit == uid].set_index("hour").after_trips
    need = np.ceil(h.boardings * RIDE_FRAC / (P["capacity"] * P["target_lf"]))
    d = pd.DataFrame(dict(hour=h.hour.values, current=h.trips.values, needed=need.values, boardings=h.boardings.round(0).values))
    d["recommended"] = d.hour.map(a) if len(a) else np.nan
    rs = c.base["route_stops"]; rs = rs[rs.route_uid == uid].sort_values("stop_sequence")
    r = c.recs[c.recs.route_uid == uid].iloc[0]
    return J(dict(hourly=rec(d), stops=rec(rs, ["stop_lat", "stop_lon"]), rec=rec(c.recs[c.recs.route_uid == uid].round(2))[0]))

@app.get("/api/impact")
def impact(c=Depends(get_ctx)):
    ci = c.ci[c.ci.city.isin(c.cities)]
    names = {"total_trips_day": "Trips / day", "bus_hours_day": "Bus-hours / day", "bus_km_day": "Bus-km / day", "n_routes_overcrowded": "Overcrowded routes",
             "n_routes_underutilized": "Under-used routes", "mean_peak_lf": "Mean peak load factor", "trip_share_nearly_empty": "Share of near-empty trips",
             "pax_share_in_overcrowded_hours": "Passengers in overcrowded hours", "avg_wait_min": "Avg passenger wait (min)", "mean_avg_lf": "Mean average load factor"}
    ratio = {"mean_peak_lf", "trip_share_nearly_empty", "pax_share_in_overcrowded_hours", "avg_wait_min", "mean_avg_lf"}
    rows = []
    for k, n in names.items():
        if k in ratio: b, a = (np.average(ci[f"{p}_{k}"], weights=ci[f"{p}_total_trips_day"]) for p in ("before", "after"))
        else: b, a = ci[f"before_{k}"].sum(), ci[f"after_{k}"].sum()
        rows.append(dict(key=k, metric=n, current=b, optimised=a, change_pct=(a - b) / b * 100 if b else 0))
    per = ci.assign(trips_saved=ci.before_total_trips_day - ci.after_total_trips_day)[["city", "before_n_routes_overcrowded", "after_n_routes_overcrowded", "before_total_trips_day", "after_total_trips_day", "trips_saved"]]
    return J(dict(rows=rows, per_city=rec(per), n_merges=c.impact["n_merges"]))

@app.get("/api/download/recommendations.csv")
def download(actions: str = "", c=Depends(get_ctx)):
    r = inc(c.recs, c); r = r[r.action.isin(actions.split(","))] if actions else r
    return Response(r.to_csv(index=False), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=route_recommendations.csv"})

# ---------------------------------------------------------------- bring your own data
def _store(label, res):
    sid = uuid.uuid4().hex[:8]
    if len(ST["sessions"]) >= 5: ST["sessions"].pop(next(iter(ST["sessions"])))
    ST["sessions"][sid] = {**res, "label": label}; return dict(dataset=sid, label=label, routes=len(res["routes"]), has_forecast="fc_mult_avg" in res["routes"])

@app.post("/api/upload")
async def upload(city: str = Form("MyCity"), gtfs: UploadFile = File(...), ridership: UploadFile | None = File(None), history: UploadFile | None = File(None)):
    try:
        feed = data_loader.read_feed_zip(io.BytesIO(await gtfs.read()))
        rid = pd.read_csv(io.BytesIO(await ridership.read())) if ridership and ridership.filename else None
        hist = pd.read_csv(io.BytesIO(await history.read())).assign(city=city) if history and history.filename else None
        res = pipeline.analyze(pipeline.build_bundle({city: (feed, rid)}, hist), ST["art"])
        return J(_store(f"Upload – {city}", res))
    except Exception as e: raise HTTPException(400, f"Could not process the feed: {e}")

class GenReq(BaseModel):
    city: str = "Pune"; seed: int = 123

@app.post("/api/generate")
def generate(req: GenReq):
    g = _gen()
    if req.city not in g.CITIES: raise HTTPException(400, "unknown city")
    feed, rid = g.generate_city(req.city, req.seed); hist = g.generate_history(rid, req.city, req.seed).assign(city=req.city)
    return J(_store(f"Synthetic – {req.city} (seed {req.seed})", pipeline.analyze(pipeline.build_bundle({req.city: (feed, rid)}, hist), ST["art"])))

@app.get("/api/sample/{name}")
def sample(name: str):
    f = ROOT / "sample_uploads" / Path(name).name
    if not f.exists(): raise HTTPException(404)
    return FileResponse(f, filename=f.name)

# ---------------------------------------------------------------- serve the React build
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
