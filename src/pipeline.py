"""End-to-end orchestration: build -> train -> infer -> optimise -> save/load."""
import json
import joblib, numpy as np, pandas as pd
from .config import *
from .features import build_city_dataset
from .preprocessing import add_encodings
from .models import fit_clustering, train_classifiers, assign_clusters, predict_routes
from .optimizer import optimize
from .forecast import train_forecaster, forecast_future, attach_forecast, apply_scenario

KEYS = ["routes", "hourly", "stops", "route_stops", "overlap_pairs"]

def _hist(history):
    if history is None or len(history) == 0: return pd.DataFrame(columns=["route_uid", "city", "month", "boardings"])
    h = history.copy(); h["route_uid"] = h.city + "|" + h.route_id.astype(str) if "route_id" in h else h.route_uid
    return h[["route_uid", "city", "month", "boardings"]]

def build_bundle(datasets, history=None):
    """datasets: {city: (feed, ridership|None)}, history: past monthly ridership -> concatenated bundle of feature tables."""
    parts = [build_city_dataset(f, r, c) for c, (f, r) in datasets.items()]
    b = {k: pd.concat([p[k] for p in parts], ignore_index=True) for k in KEYS}
    b["cleaning"] = {p["routes"].city.iloc[0]: p["cleaning"] for p in parts}
    b["routes"] = add_encodings(b["routes"]); b["history"] = _hist(history); return b

def train(bundle, holdout_cities=("Kochi", "Indore", "Nagpur")):
    routes = bundle["routes"]
    hc = [c for c in holdout_cities if c in set(routes.city)]
    clf = train_classifiers(routes, hc)
    clu = fit_clustering(routes)
    art = dict(classifier=clf, cluster=clu)
    if len(bundle.get("history", [])): art["forecaster"] = train_forecaster(bundle["history"], routes)
    return art

def analyze(bundle, art, params=None, honest_pred=None):
    """Inference on a bundle (new or old data): cluster, predict class, optimise."""
    r = predict_routes(art["classifier"], bundle["routes"])
    if honest_pred is not None: r["pred_class"] = honest_pred.reindex(r.index).fillna(r.pred_class)
    r = assign_clusters(art["cluster"], r)
    out = {**bundle}
    if "forecaster" in art and len(bundle.get("history", [])):
        out["forecast"] = forecast_future(art["forecaster"], bundle["history"], r)
        r = attach_forecast(r, bundle["history"], out["forecast"])
        for mode in ("avg", "peak"):                                  # what each route becomes if nothing changes
            r[f"class_{mode}"] = r.route_uid.map(apply_scenario(r, bundle["hourly"], mode)[0].set_index("route_uid").pred_class)
    recs, impact, city_impact, after = optimize(r, bundle["hourly"], bundle["overlap_pairs"], params)
    return {**out, "routes": r, "recs": recs, "impact": impact, "city_impact": city_impact, "after_hourly": after}

def save_art(art, path=MODEL_DIR / "routeranker_models.joblib"):
    MODEL_DIR.mkdir(exist_ok=True, parents=True); joblib.dump(art, path)

def load_art(path=MODEL_DIR / "routeranker_models.joblib"): return joblib.load(path)

def save_results(res, out=OUT_DIR):
    out.mkdir(exist_ok=True, parents=True)
    for k in KEYS + ["recs", "city_impact", "after_hourly", "history", "forecast"]:
        if k in res: res[k].to_csv(out / f"{k}.csv", index=False)
    json.dump(res["impact"], open(out / "impact.json", "w"), indent=2, default=float)

def load_results(out=OUT_DIR):
    res = {k: pd.read_csv(out / f"{k}.csv") for k in KEYS + ["recs", "city_impact", "after_hourly"]}
    for k in ("history", "forecast", "backtest_city"):
        if (out / f"{k}.csv").exists(): res[k] = pd.read_csv(out / f"{k}.csv")
    res["impact"] = json.load(open(out / "impact.json")); res["overlap_pairs"] = res["overlap_pairs"].fillna({"city": ""})
    for c in ("structural_option", "merged_with"): res["recs"][c] = res["recs"][c].fillna("")
    return res
