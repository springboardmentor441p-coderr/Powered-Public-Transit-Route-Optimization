"""Forecasting: learn from PAST monthly ridership to predict the NEXT 12 months, then feed the forecast to the optimiser.

Global direct multi-horizon gradient-boosting model (XGBoost) on all routes jointly. For origin month t and horizon h it predicts
log(y[t+h]) - mean(log y[t-2..t]) from momentum, year-on-year growth, last-year seasonal shape, city-level pooled signals,
calendar month and static route features. Evaluated by a strict time-based backtest (train on the past, predict the held-out final 12 months).
"""
import numpy as np, pandas as pd
from xgboost import XGBRegressor
from .config import *
from .features import label_routes

H, MIN_ORIGIN = 12, 14
TIER = {"small": 0, "medium": 1, "large": 2}

def _panel(history, routes):
    h = history.copy(); h["month"] = pd.PeriodIndex(h["month"].astype(str).str[:7], freq="M")
    P = h.pivot_table(index="route_uid", columns="month", values="boardings", aggfunc="mean").sort_index(axis=1)
    P = P[P.index.isin(routes.route_uid)]
    P = P.reindex(columns=pd.period_range(P.columns.min(), P.columns.max(), freq="M"))
    return P.T.interpolate(limit_direction="both").T.dropna().clip(lower=1.0)

def _static(routes, uids):
    r = routes.drop_duplicates("route_uid").set_index("route_uid").reindex(uids)
    S = pd.DataFrame({"len": r.route_length_km.values, "trips": np.log1p(r.trips_per_day.values), "shared": r.frac_stops_shared.values,
                      "proxy_lf": r.proxy_lf.values, "tier": r.city_tier.map(TIER).values})
    return S.fillna(S.median()), pd.factorize(r.city.values)[0]

def _rows(L, moy_t, S, cities, t, hs):
    ma3, ma12 = L[:, t - 2:t + 1].mean(1), L[:, t - 11:t + 1].mean(1)
    prev3, base = L[:, t - 5:t - 2].mean(1), L[:, t - 14:t - 11].mean(1)
    yoy, mom = ma3 - base, ma3 - prev3
    n = cities.max() + 1; cnt = np.bincount(cities, minlength=n)
    gm = lambda v: (np.bincount(cities, weights=v, minlength=n) / cnt)[cities]
    fr = []
    for h in hs:
        ly = L[:, t + h - 12]; sg = ly + yoy - ma3; tm = (moy_t - 1 + h) % 12
        f = pd.DataFrame(dict(h=h, ma3=ma3, yoy=yoy, mom=mom, lvl_trend=ma3 - ma12, rel=ly - base, sg=sg, csg=gm(sg), crel=gm(ly - base),
                              cyoy=gm(yoy), cmom=gm(mom), ms=np.sin(2 * np.pi * tm / 12), mc=np.cos(2 * np.pi * tm / 12)))
        fr.append(pd.concat([f, S], axis=1))
    return pd.concat(fr, ignore_index=True), np.tile(ma3, len(list(hs)))

def _dataset(L, moy, S, cities, e_max):
    Xs, ys = [], []
    for t in range(MIN_ORIGIN, e_max):
        hs = [h for h in range(1, H + 1) if t + h <= e_max]
        if not hs: continue
        X, ma3 = _rows(L, moy[t], S, cities, t, hs)
        Xs.append(X); ys.append(np.concatenate([L[:, t + h] for h in hs]) - ma3)
    return pd.concat(Xs, ignore_index=True), np.concatenate(ys)

def _fit(X, y):
    return XGBRegressor(n_estimators=300, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                        n_jobs=1, random_state=RANDOM_STATE, tree_method="hist").fit(X, y)

def _err(a, p):
    a, p = np.exp(a), np.exp(p); return dict(wape=float(np.abs(a - p).sum() / a.sum()), mape=float(np.mean(np.abs(a - p) / a)),
                                             bias=float((p.sum() - a.sum()) / a.sum()))

def train_forecaster(history, routes):
    P = _panel(history, routes); L = np.log(P.values); T = L.shape[1]; moy = np.array([m.month for m in P.columns])
    S, cities = _static(routes, P.index); out = dict(months=[str(m) for m in P.columns])
    if T < MIN_ORIGIN + H + 4: raise ValueError(f"Need at least {MIN_ORIGIN + H + 4} months of history, got {T}.")
    e = T - 1 - H                                                  # backtest: learn only from the past up to month e
    X, y = _dataset(L, moy, S, cities, e); m = _fit(X, y)
    Xt, ma3 = _rows(L, moy[e], S, cities, e, range(1, H + 1)); cols = list(Xt.columns)
    act = np.concatenate([L[:, e + h] for h in range(1, H + 1)]); pm = ma3 + m.predict(Xt[cols])
    snd = Xt.sg.values + ma3                                       # seasonal-naive + drift baseline
    sn = np.concatenate([L[:, e + h - 12] for h in range(1, H + 1)]); nv = ma3
    hh = Xt.h.values
    out["metrics"] = dict(train_months=int(e + 1), test_months=H, n_routes=int(L.shape[0]),
        model=_err(act, pm), seasonal_naive_drift=_err(act, snd), seasonal_naive=_err(act, sn), naive_last3=_err(act, nv),
        by_horizon={int(k): _err(act[hh == k], pm[hh == k]) for k in range(1, H + 1)})
    res = act - pm; out["q_lo"] = [float(np.quantile(res[hh == k], 0.1)) for k in range(1, H + 1)]
    out["q_hi"] = [float(np.quantile(res[hh == k], 0.9)) for k in range(1, H + 1)]
    out["metrics"]["interval80_coverage"] = float(np.mean([(res[hh == k] >= out["q_lo"][k - 1]) & (res[hh == k] <= out["q_hi"][k - 1]) for k in range(1, H + 1)]))
    ci = pd.DataFrame(dict(city=routes.drop_duplicates("route_uid").set_index("route_uid").reindex(P.index).city.values))
    bt = pd.DataFrame(dict(city=np.tile(ci.city.values, H), month=np.repeat([str(P.columns[e + h]) for h in range(1, H + 1)], L.shape[0]),
                           actual=np.exp(act), model=np.exp(pm), seasonal_naive_drift=np.exp(snd)))
    out["backtest_city"] = bt.groupby(["city", "month"], sort=False).sum().reset_index()
    X, y = _dataset(L, moy, S, cities, T - 1); out.update(model=_fit(X, y), cols=cols)   # final model uses ALL past data
    return out

def forecast_future(fc, history, routes):
    P = _panel(history, routes); L = np.log(P.values); T = L.shape[1]; moy = np.array([m.month for m in P.columns])
    S, cities = _static(routes, P.index); X, ma3 = _rows(L, moy[-1], S, cities, T - 1, range(1, H + 1))
    d = ma3 + fc["model"].predict(X[fc["cols"]]); hq = X.h.values.astype(int) - 1
    r = routes.drop_duplicates("route_uid").set_index("route_uid").reindex(P.index)
    return pd.DataFrame(dict(route_uid=np.tile(P.index, H), city=np.tile(r.city.values, H),
        month=np.repeat([str(P.columns[-1] + h) for h in range(1, H + 1)], len(P)), forecast=np.exp(d),
        lo=np.exp(d + np.array(fc["q_lo"])[hq]), hi=np.exp(d + np.array(fc["q_hi"])[hq])))

def attach_forecast(routes, history, fdf):
    P = _panel(history, routes); base3 = P.iloc[:, -3:].mean(axis=1)
    g = fdf.groupby("route_uid").forecast; peak = fdf.loc[g.idxmax()].set_index("route_uid").month
    r = routes.copy(); u = r.route_uid
    r["fc_base3"] = u.map(base3); r["fc_mult_avg"] = u.map(g.mean() / base3).fillna(1.0); r["fc_mult_peak"] = u.map(g.max() / base3).fillna(1.0)
    r["fc_growth_pct"] = (r.fc_mult_avg - 1) * 100; r["fc_peak_month"] = u.map(peak).fillna("")
    return r

def apply_scenario(routes, hourly, mode):
    """mode: today | avg (mean of next 12 months) | peak (busiest forecast month). Returns (routes, hourly) with demand re-scaled and classes re-derived."""
    if mode == "today" or "fc_mult_avg" not in routes: return routes, hourly
    mult = routes.set_index("route_uid")["fc_mult_avg" if mode == "avg" else "fc_mult_peak"]
    h = hourly.copy(); h["boardings"] *= h.route_uid.map(mult).fillna(1.0).values
    h["pax_per_trip"] = h.boardings / h.trips; h["load_factor"] = h.boardings * RIDE_FRAC / (h.trips * BUS_CAPACITY)
    wd = h[h.day_type == "weekday"].groupby("route_uid")
    pk = wd.load_factor.apply(lambda x: x.nlargest(3).mean()); tot = wd.boardings.sum(); av = tot * RIDE_FRAC / (wd.trips.sum() * BUS_CAPACITY)
    r = routes.copy(); r["peak_lf"] = r.route_uid.map(pk); r["avg_lf"] = r.route_uid.map(av); r["daily_boardings"] = r.route_uid.map(tot)
    r["pred_class"] = label_routes(r.peak_lf, r.avg_lf); return r, h
