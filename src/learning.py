"""RouteRanker machine-learning core: LEARNS FROM REAL GTFS DATA.

What is learned (honest scope)
    Real GTFS contains schedules, not passengers. The model therefore learns how an operator ALLOCATES service:
    target = scheduled trips in a given route-hour, inputs = route geometry/network features (length, stops, connectivity, distance to core,
    overlap, hour of day...). It never sees the route's own timetable as an input, so predictions are "what comparable routes get".
    Routes far below/above that prediction are flagged as RELATIVELY under/over-served versus peers. This is a screening signal that needs
    ridership data to confirm; it is not a measurement of crowding.
Evaluation: leave-one-city-out (unseen cities), route-grouped CV, learning curve, comparison against baselines.
"""
import datetime as dt, hashlib, json, time
from pathlib import Path
import joblib, numpy as np, pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from . import gtfs_validation as gv
from .cleaning import clean_feed
from .features import trip_table, route_supply_features, stop_and_overlap_features
from .config import ROOT, MODEL_DIR

CORPUS_DIR = ROOT / "data" / "corpus"
MODEL_PATH = MODEL_DIR / "service_model.joblib"
CARD_PATH = MODEL_DIR / "model_card.json"
REGISTRY_PATH = MODEL_DIR / "registry.json"
SEED = 42
ROUTE_FEATURES = ["route_length_km", "n_stops", "avg_stop_spacing_km", "trip_duration_min", "avg_speed_kmph", "service_span_hr", "service_start_hr",
                  "frac_stops_shared", "hub_frac", "max_overlap", "mean_conn", "max_conn", "mean_dist_norm", "min_dist_norm", "other_service_log"]
ROW_FEATURES = ["hour", "hour_sin", "hour_cos", "rel_pos", "hrs_from_start", "hrs_to_end", "is_am_peak", "is_pm_peak"]
FEATURES = ROW_FEATURES + ROUTE_FEATURES
DAY_HOURS = (4, 23)                                                  # hours analysed (early-morning trips after midnight are excluded)

# ------------------------------------------------------------------------------------------------ features
def build_city_table(feed, city):
    """Raw GTFS dict -> (route-hour training table, route info table, validation report, cleaning report)."""
    val = gv.validate_feed(feed)
    if val["status"] == "fail":
        raise gv.GTFSError("The feed failed validation: " + "; ".join(i["message"] for i in val["issues"] if i["severity"] == "error"), val)
    feed, rep = clean_feed(feed)
    t, st = trip_table(feed)
    sup, supply = route_supply_features(t)
    ov, stops, pairs, rs = stop_and_overlap_features(feed, t, st, sup)
    r = feed["routes"][["route_id", "route_short_name", "route_long_name"]].merge(sup, on="route_id").merge(ov, on="route_id")
    med = max(float(stops.dist_center_km.median()), 0.5)
    rs2 = rs.merge(stops[["stop_id", "departures_day"]], on="stop_id").merge(sup[["route_id", "trips_per_day"]], on="route_id")
    rs2["other"] = (rs2.departures_day - rs2.trips_per_day).clip(lower=0)             # service of OTHER routes at the stop (own trips removed)
    g = rs2.groupby("route_id").agg(mean_conn=("n_routes", "mean"), max_conn=("n_routes", "max"), mean_dist=("dist_center_km", "mean"),
                                    min_dist=("dist_center_km", "min"), other_mean=("other", "mean"))
    r = r.merge(g, on="route_id")
    r["hub_frac"] = r.n_hub_stops / r.n_unique_stops.clip(lower=1)
    r["mean_dist_norm"], r["min_dist_norm"] = r.mean_dist / med, r.min_dist / med
    r["other_service_log"] = np.log1p(r.other_mean)
    r["city_log_routes"], r["city_log_stops"], r["city_radius_km"] = np.log(len(r)), np.log(len(stops)), med
    s = supply[supply.day_type == "weekday"]; s = s[s.hour.between(*DAY_HOURS)]
    first = s.groupby("route_id").hour.min(); last = s.groupby("route_id").hour.max()
    r = r[r.route_id.isin(first.index)].copy(); r["service_start_hr"] = r.route_id.map(first); r["service_end_hr"] = r.route_id.map(last)
    r["service_span_hr"] = r.service_end_hr - r.service_start_hr + 1
    rows = []
    for rid, a, b in zip(r.route_id, r.service_start_hr, r.service_end_hr): rows.append(pd.DataFrame({"route_id": rid, "hour": np.arange(a, b + 1)}))
    T = pd.concat(rows, ignore_index=True).merge(s[["route_id", "hour", "trips"]], on=["route_id", "hour"], how="left").fillna({"trips": 0})
    T = T.merge(r[["route_id"] + [c for c in ROUTE_FEATURES if c not in ROW_FEATURES] + ["service_end_hr"]], on="route_id")
    T["hour_sin"], T["hour_cos"] = np.sin(2 * np.pi * T.hour / 24), np.cos(2 * np.pi * T.hour / 24)
    T["hrs_from_start"], T["hrs_to_end"] = T.hour - T.service_start_hr, T.service_end_hr - T.hour
    T["rel_pos"] = T.hrs_from_start / T.service_span_hr.clip(lower=1)
    T["is_am_peak"], T["is_pm_peak"] = T.hour.between(7, 10).astype(int), T.hour.between(17, 20).astype(int)
    T["city"] = city; T["route_uid"] = city + "|" + T.route_id.astype(str)
    info = r[["route_id", "route_short_name", "route_long_name", "trips_per_day", "route_length_km", "n_stops"]].copy()
    info["city"] = city; info["route_uid"] = city + "|" + info.route_id.astype(str)
    return T.drop(columns=["service_end_hr"]), info, val, rep

def corpus_save(name, T, info, val, rep, source=""):
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    T.to_parquet(CORPUS_DIR / f"{name}.rows.parquet", index=False); info.to_parquet(CORPUS_DIR / f"{name}.routes.parquet", index=False)
    json.dump(dict(name=name, source=source, added=dt.datetime.now().isoformat(timespec="seconds"), routes=int(len(info)), rows=int(len(T)),
                   validation=dict(status=val["status"], errors=val["n_errors"], warnings=val["n_warnings"]),
                   rows_after=rep["rows_after"], discard_flags=rep["discard_flags"]), open(CORPUS_DIR / f"{name}.meta.json", "w"), indent=1)

def corpus_load(names=None):
    ms = sorted(CORPUS_DIR.glob("*.meta.json")); metas = [json.load(open(m)) for m in ms]
    if names: metas = [m for m in metas if m["name"] in names]
    if not metas: raise FileNotFoundError("The training corpus is empty. Add feeds with: python -m src.learn corpus --gtfs <zip> --name <City>")
    T = pd.concat([pd.read_parquet(CORPUS_DIR / f"{m['name']}.rows.parquet") for m in metas], ignore_index=True)
    I = pd.concat([pd.read_parquet(CORPUS_DIR / f"{m['name']}.routes.parquet") for m in metas], ignore_index=True)
    return add_scale(T), I, metas

# ------------------------------------------------------------------------------------------------ models
class HourMean(BaseEstimator, RegressorMixin):
    """Baseline 1: predict the average trips for that hour of day (ignores the route entirely)."""
    def fit(self, X, y): self.m_ = pd.Series(np.asarray(y)).groupby(X["hour"].values).mean(); self.g_ = float(np.mean(y)); return self
    def predict(self, X): return X["hour"].map(self.m_).fillna(self.g_).values

class Constant(BaseEstimator, RegressorMixin):
    """Baseline 0: always predict the training mean."""
    def fit(self, X, y): self.g_ = float(np.mean(y)); return self
    def predict(self, X): return np.full(len(X), self.g_)

def make_models():
    return {"baseline_mean": Constant(), "baseline_hour_mean": HourMean(),
            "poisson_linear": Pipeline([("s", StandardScaler()), ("m", PoissonRegressor(alpha=1e-2, max_iter=1000))]),
            "random_forest": RandomForestRegressor(120, max_depth=14, min_samples_leaf=10, max_features=0.6, n_jobs=-1, random_state=SEED),
            "gradient_boosting": HistGradientBoostingRegressor(loss="poisson", max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
                                                               l2_regularization=1.0, random_state=SEED)}

def add_scale(T):
    """City scale = the city's mean trips per route-hour. Models predict service RELATIVE to it, so operator fleet size is not something to guess."""
    T = T.copy(); T["city_scale"] = T.groupby("city").trips.transform("mean").clip(lower=0.05); return T

def _fit_predict(name, tr, te):
    m = make_models()[name]; m.fit(tr[FEATURES], tr.trips / tr.city_scale)
    return np.clip(m.predict(te[FEATURES]), 0, None) * te.city_scale.values, m

def score(y, p, groups=None):
    out = dict(mae=float(mean_absolute_error(y, p)), rmse=float(np.sqrt(mean_squared_error(y, p))), r2=float(r2_score(y, p)),
               poisson_deviance=float(mean_poisson_deviance(np.clip(y, 0, None) + 1e-9, np.clip(p, 1e-3, None))))
    if groups is not None:
        d = pd.DataFrame({"g": groups, "y": np.asarray(y), "p": p}).groupby("g").sum(); out["route_day_r2"] = float(r2_score(d.y, d.p))
        out["route_day_mae"] = float(mean_absolute_error(d.y, d.p))
    return out

def loco(T, names):
    """Leave-one-city-out: train on all other cities, test on the unseen city."""
    res = {n: {} for n in names}
    for c in sorted(T.city.unique()):
        tr, te = T[T.city != c], T[T.city == c]
        for n in names:
            p, _ = _fit_predict(n, tr, te); res[n][c] = score(te.trips, p, te.route_uid.values)
    return res

def grouped_cv(T, names, k=5):
    """Route-grouped K-fold: a route is never in train and test together. Returns metrics and out-of-fold predictions."""
    oof = {n: np.zeros(len(T)) for n in names}; folds = GroupKFold(min(k, T.route_uid.nunique()))
    for a, b in folds.split(T, groups=T.route_uid):
        for n in names:
            oof[n][b], _ = _fit_predict(n, T.iloc[a], T.iloc[b])
    return {n: score(T.trips, oof[n], T.route_uid.values) for n in names}, oof

def learning_curve(T, fracs=(0.02, 0.05, 0.1, 0.25, 0.5, 1.0), seeds=3, model="gradient_boosting"):
    """Does the model get better with more data? Fixed held-out routes; train on growing random subsets of the other routes."""
    rng = np.random.default_rng(SEED); uids = T.route_uid.unique(); rng.shuffle(uids)
    test_u = set(uids[: int(0.2 * len(uids))]); pool = np.array([u for u in uids if u not in test_u]); te = T[T.route_uid.isin(test_u)]
    base = score(te.trips, _fit_predict("baseline_hour_mean", T[~T.route_uid.isin(test_u)], te)[0])
    out = []
    for f in fracs:
        ms = []
        for s in range(seeds if f < 1 else 1):
            sub = np.random.default_rng(s).choice(pool, max(20, int(f * len(pool))), replace=False)
            tr = T[T.route_uid.isin(set(sub))]; p, _ = _fit_predict(model, tr, te); ms.append(score(te.trips, p))
        out.append(dict(frac=f, n_routes=int(max(20, int(f * len(pool)))), mae=float(np.mean([m["mae"] for m in ms])), mae_sd=float(np.std([m["mae"] for m in ms])),
                        r2=float(np.mean([m["r2"] for m in ms]))))
    return dict(points=out, baseline_hour_mean_mae=base["mae"], n_test_routes=len(test_u))

# ------------------------------------------------------------------------------------------------ peer gap
def peer_gap(T, info, pred, q=(0.05, 0.95)):
    """Route-level comparison: actual vs predicted (peer-expected) daily trips. Interval = empirical quantiles of out-of-fold log-ratios."""
    d = T.assign(pred=pred).groupby("route_uid").agg(actual_trips=("trips", "sum"), expected_trips=("pred", "sum")).reset_index()
    d = d[(d.actual_trips > 0) & (d.expected_trips > 0.5)]; d["log_ratio"] = np.log(d.actual_trips / d.expected_trips)
    lo, hi = np.quantile(d.log_ratio, q); d["ratio"] = np.exp(d.log_ratio)
    d["flag"] = np.where((d.log_ratio < min(lo, -np.log(2))), "relatively under-served vs peers",
                np.where(d.log_ratio > max(hi, np.log(2)), "relatively over-served vs peers", "in line with peers"))
    return d.merge(info, on="route_uid"), dict(q_lo=float(lo), q_hi=float(hi))

MIN_ROUTES_SELF = 200          # below this the model overfits (measured: 70 routes -> worse than baseline)

def fit_self(T, info, model="gradient_boosting", k=5):
    """LEARN FROM THIS FEED ONLY: train on the feed's own routes, predict held-out routes (route-grouped CV), compare with peers.
    Returns (route-level table, learning report incl. skill vs baseline)."""
    T = add_scale(T).reset_index(drop=True)
    if T.route_uid.nunique() < MIN_ROUTES_SELF:
        raise ValueError(f"Only {T.route_uid.nunique()} routes: too few to learn this network on its own (need at least {MIN_ROUTES_SELF}). Use mode='pooled'.")
    cv, oof = grouped_cv(T, ["baseline_hour_mean", model], k)
    gap, itv = peer_gap(T, info, oof[model]); skill = 1 - cv[model]["mae"] / cv["baseline_hour_mean"]["mae"]
    if skill < 0.10: gap["flag"] = "unreliable (model learned little from this feed)"
    return gap, dict(cv=cv, skill=float(skill), interval=itv, n_routes=int(T.route_uid.nunique()), reliable=bool(skill >= 0.10))

# ------------------------------------------------------------------------------------------------ training
def corpus_hash(T): return hashlib.sha1(pd.util.hash_pandas_object(T[["route_uid", "hour", "trips"]], index=False).values.tobytes()).hexdigest()[:10]

def train(names_models=("baseline_mean", "baseline_hour_mean", "poisson_linear", "random_forest", "gradient_boosting"), fast=False, log=print):
    """Learn from every feed in the corpus. Returns (artifact, card)."""
    t0 = time.time(); T, I, metas = corpus_load(); names = list(names_models); cities = sorted(T.city.unique())
    log(f"corpus: {len(cities)} cities, {I.route_uid.nunique()} routes, {len(T)} route-hours")
    cv, oof = grouped_cv(T, names); learners = [n for n in names if not n.startswith("baseline")]
    best = min(learners, key=lambda n: cv[n]["mae"]); log(f"route-grouped CV MAE: " + ", ".join(f"{n}={cv[n]['mae']:.3f}" for n in names) + f" -> best {best}")
    lo = loco(T, names) if len(cities) >= 2 else {}; log("leave-one-city-out done")
    model = make_models()[best].fit(T[FEATURES], T.trips / T.city_scale)
    _, interval = peer_gap(T, I, oof[best])
    within, gaps = {}, []
    for c in cities:                                                  # learn each city from its own network, test on its held-out routes
        Tc, Ic = T[T.city == c], I[I.city == c]
        if Tc.route_uid.nunique() >= L_MIN_SELF:
            g, rpt = fit_self(Tc, Ic); within[c] = dict(skill=rpt["skill"], reliable=rpt["reliable"], **{m: rpt["cv"][m] for m in rpt["cv"]}); gaps.append(g.assign(city=c))
    gap = pd.concat(gaps, ignore_index=True) if gaps else pd.DataFrame(columns=["flag"])
    # permutation importance on route-held-out rows
    rng = np.random.default_rng(SEED); u = T.route_uid.unique(); hold = set(rng.choice(u, int(0.2 * len(u)), replace=False))
    m2 = make_models()[best].fit(T[~T.route_uid.isin(hold)][FEATURES], (T.trips / T.city_scale)[~T.route_uid.isin(hold)]); H = T[T.route_uid.isin(hold)]
    H = H.sample(min(len(H), 12000), random_state=SEED)
    pi = permutation_importance(m2, H[FEATURES], H.trips / H.city_scale, n_repeats=3, random_state=SEED, scoring="neg_mean_absolute_error")
    imp = pd.Series(pi.importances_mean, index=FEATURES).sort_values(ascending=False)
    lc = None if fast else learning_curve(T)
    version = f"{dt.date.today():%Y%m%d}-{corpus_hash(T)}"
    card = dict(version=version, trained_at=dt.datetime.now().isoformat(timespec="seconds"), best_model=best, task="predict scheduled trips per route-hour from route/network features",
        target="trips relative to the city mean (predictions are multiplied back by the city scale)", features=FEATURES, trained_on=[dict(name=m["name"], routes=m["routes"], source=m.get("source", "")) for m in metas],
        n_routes=int(I.route_uid.nunique()), n_rows=int(len(T)), cv_grouped=cv, within_city=within, loco=lo, learning_curve=lc,
        permutation_importance={k: float(v) for k, v in imp.head(15).items()}, interval_log_ratio=interval,
        peer_gap_flag_counts=gap.flag.value_counts().to_dict(),
        data_honesty=dict(kind="real published GTFS schedules", passenger_data=False,
            limitation="Learns operator service allocation, not passenger demand. Flags are screening signals that require ridership data to confirm."),
        seconds=round(time.time() - t0, 1))
    art = dict(model=model, features=FEATURES, version=version, interval=interval, cities=cities, best=best, card_summary=dict(cv=cv[best], loco=lo.get(best, {})))
    return art, card, gap

# ------------------------------------------------------------------------------------------------ registry / persistence
def _registry():
    return json.load(open(REGISTRY_PATH)) if REGISTRY_PATH.exists() else []

def promote_or_reject(art, card, tol=0.05):
    """Champion/challenger: promote unless generalisation to previously evaluated cities got materially worse (> tol)."""
    reg = _registry(); new_lo = {c: v["mae"] for c, v in card["loco"].get(card["best_model"], {}).items()}
    decision, reason = True, "first model"
    if reg:
        old = reg[-1]; common = [c for c in old["loco_mae"] if c in new_lo]
        if common:
            o, n = np.mean([old["loco_mae"][c] for c in common]), np.mean([new_lo[c] for c in common])
            decision = n <= o * (1 + tol); reason = f"leave-one-city-out MAE on {len(common)} previously evaluated cities: {o:.3f} -> {n:.3f} (tolerance {tol:.0%})"
        else: reason = "no overlapping cities to compare; promoted"
    MODEL_DIR.mkdir(exist_ok=True, parents=True)
    reg.append(dict(version=card["version"], trained_at=card["trained_at"], cities=[t["name"] for t in card["trained_on"]], n_routes=card["n_routes"],
                    best=card["best_model"], cv_mae=card["cv_grouped"][card["best_model"]]["mae"], loco_mae=new_lo, promoted=bool(decision), reason=reason, within_city_skill={c: v["skill"] for c, v in card.get("within_city", {}).items()}))
    json.dump(reg, open(REGISTRY_PATH, "w"), indent=1)
    if decision:
        joblib.dump(art, MODEL_PATH); json.dump(card, open(CARD_PATH, "w"), indent=1)
    else: joblib.dump(art, MODEL_DIR / f"challenger_{card['version']}.joblib")
    return decision, reason

def load_model():
    if not MODEL_PATH.exists(): raise FileNotFoundError("No trained model yet. Run: python -m src.learn train")
    return joblib.load(MODEL_PATH)

L_MIN_SELF = MIN_ROUTES_SELF

def predict_feed(art, feed, city, mode="auto"):
    """Apply the learned model to any (new) GTFS feed -> route-level peer comparison. Schema is checked against the model's feature list."""
    T, info, val, rep = build_city_table(feed, city)
    if mode in ("auto", "self") and T.route_uid.nunique() >= MIN_ROUTES_SELF:
        gap, rpt = fit_self(T, info); gap["mode"] = "self-learned on this feed"; gap["model_skill"] = rpt["skill"]; return gap, val, dict(rep, learning=rpt)
    if mode == "self": raise ValueError(f"Too few routes to learn from this feed alone (need {MIN_ROUTES_SELF}).")
    missing = [f for f in art["features"] if f not in T.columns]
    if missing: raise ValueError(f"Feed features incompatible with model {art['version']}: missing {missing}")
    T = add_scale(T); pred = np.clip(art["model"].predict(T[art["features"]]), 0, None) * T.city_scale.values
    d = T.assign(pred=pred).groupby("route_uid").agg(actual_trips=("trips", "sum"), expected_trips=("pred", "sum")).reset_index()
    d = d[d.expected_trips > 0.5].assign(); d["ratio"] = d.actual_trips / d.expected_trips; lr = np.log(d.ratio.clip(lower=1e-3)); it = art["interval"]
    d["flag"] = np.where(lr < min(it["q_lo"], -np.log(2)), "relatively under-served vs peers", np.where(lr > max(it["q_hi"], np.log(2)), "relatively over-served vs peers", "in line with peers"))
    d["seen_in_training"] = city in art["cities"]; d["mode"] = "pooled model (weak across cities; treat as indicative)"
    return d.merge(info, on="route_uid"), val, rep
