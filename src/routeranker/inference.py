"""Module 6a - Inference & route suggestion service.

``RouteRankerService`` is the single back-end object used by both the
Streamlit frontend and the FastAPI REST API. It loads the processed tables
and trained models once, and offers:

* ``predict_day``      - hourly forecast for every route on any date
* ``rank_routes``      - composite RouteRank score + ranking
* ``explain``          - natural-language "why is this the best route"
* ``validate``         - back-test of the recommendation on past same-weekdays
* ``find_routes_between`` - direct routes linking two stops/areas
* ``recommendations``  - optimisation actions for a date
"""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import cached_property

import joblib
import numpy as np
import pandas as pd

from . import config as C
from .feature_engineering import add_performance_metrics, add_time_features, attach_service_features
from .optimization import impact_summary, optimize_frequencies, route_recommendations
from .preprocessing import model_matrix
from .supervised import CLASS_TO_INT

STATIC_COLS = ["route_id", "length_mi", "n_stops", "reliability", "reliability_peak", "route_speed_mph",
               "route_type", "borough", "evasion_factor"]
COMPONENTS = ["productivity", "speed", "reliability", "frequency", "comfort"]
PRESETS = {
    "Balanced (default)": C.ScoreWeights(),
    "Rider - fast & comfortable": C.ScoreWeights(productivity=0.05, speed=0.30, reliability=0.25,
                                                frequency=0.20, comfort=0.20),
    "Planner - efficiency first": C.ScoreWeights(productivity=0.45, speed=0.10, reliability=0.15,
                                                frequency=0.10, comfort=0.20),
}


def now_ist() -> datetime:
    """Current date-time in IST (Asia/Kolkata)."""
    return datetime.now(C.IST)


def ist_to_transit(dt_ist: datetime) -> datetime:
    """Convert an IST datetime to the bus network's local time (America/New_York)."""
    if dt_ist.tzinfo is None:
        dt_ist = dt_ist.replace(tzinfo=C.IST)
    return dt_ist.astimezone(C.TRANSIT_TZ)


def transit_to_ist(dt_local) -> datetime:
    """Convert a bus-network local timestamp (America/New_York) to IST."""
    ts = pd.Timestamp(dt_local)
    if ts.tzinfo is None:
        ts = ts.tz_localize(C.TRANSIT_TZ, ambiguous="NaT", nonexistent="shift_forward")
    return ts.tz_convert(C.IST)


class RouteRankerService:
    """Loads artefacts produced by ``routeranker.pipeline`` and serves predictions."""

    def __init__(self):
        """Load processed tables, trained models, metrics and manifest from disk."""
        P = C.PROCESSED_DIR
        self.route_info = pd.read_parquet(P / "route_info.parquet")
        self.trips = pd.read_parquet(P / "trips.parquet")
        self.speeds = pd.read_parquet(P / "speeds_hourly.parquet")
        self.paths = pd.read_parquet(P / "paths.parquet")
        self.stops = pd.read_parquet(P / "stops.parquet")
        self.overlap = pd.read_parquet(P / "overlap.parquet")
        self.encoder = joblib.load(C.MODELS_DIR / "profile_encoder.joblib")
        self.forecaster = joblib.load(C.MODELS_DIR / "forecaster.joblib")
        self.classifier = joblib.load(C.MODELS_DIR / "classifier.joblib")
        self.metrics = json.loads((C.METRICS_DIR / "model_metrics.json").read_text())
        self.manifest = json.loads((C.METRICS_DIR / "pipeline_manifest.json").read_text())
        self.routes = sorted(self.route_info["route_id"])
        self._cache: dict = {}

    # ------------------------------------------------------------------ data
    @cached_property
    def history(self) -> pd.DataFrame:
        """Slim historical route-hour table (actuals) - loaded lazily."""
        return pd.read_parquet(C.PROCESSED_DIR / "route_hour.parquet")

    @property
    def data_start(self) -> pd.Timestamp:
        """First date of the historical ridership window."""
        return pd.Timestamp(self.manifest["data_start"])

    @property
    def data_end(self) -> pd.Timestamp:
        """Last date of the historical ridership window."""
        return pd.Timestamp(self.manifest["data_end"])

    def route_label(self, rid: str) -> str:
        """'ROUTE - Long name' label for drop-downs."""
        r = self.route_info.set_index("route_id")
        if rid in r.index and isinstance(r.at[rid, "route_long_name"], str):
            return f"{rid} - {r.at[rid, 'route_long_name']}"
        return rid

    # ------------------------------------------------------------ prediction
    def frame_for_date(self, d, routes: list[str] | None = None) -> pd.DataFrame:
        """Feature frame (route x 24 hours) for an arbitrary calendar date."""
        d = pd.Timestamp(d).normalize()
        rids = routes or self.routes
        f = pd.MultiIndex.from_product([rids, range(24)], names=["route_id", "hour"]).to_frame(index=False)
        f["ts"] = d + pd.to_timedelta(f["hour"], unit="h")
        f = add_time_features(f.drop(columns=["hour"]))
        static = self.route_info[STATIC_COLS]
        f = attach_service_features(f, self.trips, self.speeds, static)
        return f

    def predict_day(self, d, routes: list[str] | None = None) -> pd.DataFrame:
        """Hourly ridership forecast + KPIs + class probabilities for one date."""
        key = (str(pd.Timestamp(d).date()), tuple(routes) if routes else None)
        if key in self._cache:
            return self._cache[key].copy()
        f = self.frame_for_date(d, routes)
        enc, X = model_matrix(f, self.encoder)
        f = enc
        f["ridership"] = np.clip(np.expm1(self.forecaster.predict(X)), 0, None).astype("float32")
        f.loc[f["trips"] == 0, "ridership"] *= 0.15  # almost no boardings when no bus is scheduled
        f["transfers"] = 0.0
        f = add_performance_metrics(f)
        proba = self.classifier.predict_proba(X)
        for c, i in CLASS_TO_INT.items():
            f[f"p_{c.lower()}"] = proba[:, i]
        f["pred_class"] = np.array(C.CLASS_LABELS)[proba.argmax(1)]
        f.loc[f["trips"] == 0, "pred_class"] = "No service"
        # attach actuals when the date is inside the historical window
        d0 = pd.Timestamp(d).normalize()
        if self.data_start <= d0 <= self.data_end:
            h = self.history[self.history["date"] == d0][["route_id", "hour", "ridership", "occupancy", "perf_class"]]
            f = f.merge(h.rename(columns={"ridership": "ridership_actual", "occupancy": "occupancy_actual",
                                          "perf_class": "perf_class_actual"}), on=["route_id", "hour"], how="left")
        self._cache[key] = f
        return f.copy()

    # --------------------------------------------------------------- ranking
    @staticmethod
    def _aggregate(f: pd.DataFrame, hours: tuple[int, int], ridership_col: str = "ridership",
                   comfort_from: str = "proba") -> pd.DataFrame:
        """Aggregate route-hour predictions over an hour window into the five score components per route."""
        w = f[f["hour"].between(*hours) & (f["trips"] > 0)].copy()
        if w.empty:
            return pd.DataFrame()
        w["_rev"] = w["trips"] * w["trip_minutes"] / 60
        g = w.groupby("route_id")
        peak = w["is_peak"].mean() > 0.3
        agg = pd.DataFrame({
            "riders": g[ridership_col].sum(),
            "productivity": g[ridership_col].sum() / g["_rev"].sum(),
            "speed": g["speed_mph"].mean(),
            "reliability": g["reliability_peak" if peak else "reliability"].first(),
            "frequency": g["trips"].mean(),
            "mean_occupancy": g["occupancy"].mean(),
            "max_occupancy": g["occupancy"].max(),
            "avg_wait_min": g["avg_wait_min"].mean(),
            "trip_minutes": g["trip_minutes"].mean(),
            "length_mi": g["length_mi"].first(),
        })
        if comfort_from == "proba" and "p_overcrowded" in w:
            agg["comfort"] = 1 - g["p_overcrowded"].mean()
        else:
            agg["comfort"] = 1 - g["occupancy"].apply(lambda s: (s > C.OVERCROWDED_MIN).mean())
        return agg

    def rank_routes(self, f: pd.DataFrame, hours: tuple[int, int] = (6, 22), weights: C.ScoreWeights | None = None,
                    candidates: list[str] | None = None, ridership_col: str = "ridership",
                    comfort_from: str = "proba") -> pd.DataFrame:
        """Composite RouteRank score (0-100). Each component is converted to a
        percentile rank among the candidate routes and combined with the weights."""
        if candidates:
            f = f[f["route_id"].isin(candidates)]
        agg = self._aggregate(f, hours, ridership_col, comfort_from)
        if agg.empty:
            return agg
        w = (weights or C.ScoreWeights()).as_dict()
        for c in COMPONENTS:
            agg[f"{c}_pct"] = agg[c].rank(pct=True) * 100 if len(agg) > 1 else 100.0
        agg["score"] = sum(agg[f"{c}_pct"] * w[c] for c in COMPONENTS)
        agg = agg.sort_values("score", ascending=False)
        agg["rank"] = np.arange(1, len(agg) + 1)
        info = self.route_info.set_index("route_id")[["route_long_name", "route_type", "borough", "cluster_name"]]
        return agg.join(info).reset_index()

    def explain(self, ranking: pd.DataFrame, weights: C.ScoreWeights | None = None) -> list[str]:
        """Plain-language justification of the top-ranked route versus the others."""
        if ranking.empty:
            return ["No candidate route has service in the selected window."]
        top = ranking.iloc[0]
        others = ranking.iloc[1:]
        w = (weights or C.ScoreWeights()).as_dict()
        lines = [f"**{top['route_id']}** ranks #1 of {len(ranking)} candidate routes with a RouteRank score of "
                 f"**{top['score']:.1f}/100**" + (f", {top['score'] - others['score'].iloc[0]:.1f} points ahead of "
                                                  f"{others['route_id'].iloc[0]}." if len(others) else ".")]
        if others.empty:
            return lines
        med = others[COMPONENTS + ["mean_occupancy", "avg_wait_min"]].median()
        label = {"productivity": ("boardings per vehicle-hour", "{:.0f}"), "speed": ("mph average speed", "{:.1f}"),
                 "reliability": ("of buses on an acceptable headway", "{:.0%}"),
                 "frequency": ("buses per hour", "{:.1f}"),
                 "comfort": ("chance of NOT being overcrowded", "{:.0%}")}
        contrib = sorted(COMPONENTS, key=lambda c: -w[c] * top[f"{c}_pct"])
        for c in contrib:
            name, fmt = label[c]
            v, m = top[c], med[c]
            better = v >= m
            lines.append(f"{'✅' if better else '⚠️'} **{c.title()}** (weight {w[c]:.0%}): "
                         f"{fmt.format(v)} {name} vs median {fmt.format(m)} for the alternatives "
                         f"- better than {top[f'{c}_pct']:.0f}% of candidates.")
        lines.append(f"Expected average wait ≈ {top['avg_wait_min']:.1f} min and mean load ≈ "
                     f"{top['mean_occupancy']:.0%} of capacity (alternatives: {med['avg_wait_min']:.1f} min, "
                     f"{med['mean_occupancy']:.0%}).")
        return lines

    def validate(self, route: str, d, hours: tuple[int, int], candidates: list[str] | None,
                 weights: C.ScoreWeights | None = None, weeks: int = 6) -> pd.DataFrame:
        """Back-test: for the last ``weeks`` same-weekday dates in history, rank the candidates on
        ACTUAL ridership and report where the recommended route landed, plus forecast error."""
        d = pd.Timestamp(d).normalize()
        end = self.data_end.normalize()
        # most recent same-weekday date strictly before d that has actuals
        ref = d - pd.Timedelta(days=7) if d - pd.Timedelta(days=7) <= end else             end - pd.Timedelta(days=(end.dayofweek - d.dayofweek) % 7)
        dates = [ref - pd.Timedelta(days=7 * k) for k in range(weeks)]
        dates = [x for x in dates if self.data_start <= x <= end]
        rows = []
        for x in dates:
            hist = self.predict_day(x, None)
            if "ridership_actual" not in hist:
                continue
            hist = hist.dropna(subset=["ridership_actual"]).copy()
            pred_tot = hist.loc[hist["route_id"] == route].query("@hours[0] <= hour <= @hours[1]")["ridership"].sum()
            act = hist.copy()
            act["ridership"] = act["ridership_actual"]
            act = add_performance_metrics(act)
            r = self.rank_routes(act, hours, weights, candidates, comfort_from="actual")
            if r.empty or route not in set(r["route_id"]):
                continue
            me = r[r["route_id"] == route].iloc[0]
            act_tot = me["riders"]
            rows.append({"date": x.date(), "weekday": x.day_name(), "rank_on_actuals": int(me["rank"]),
                         "candidates": len(r), "actual_top_route": r.iloc[0]["route_id"],
                         "score_on_actuals": round(float(me["score"]), 1),
                         "predicted_riders": round(float(pred_tot)), "actual_riders": round(float(act_tot)),
                         "abs_pct_error": round(abs(pred_tot - act_tot) / max(act_tot, 1) * 100, 1)})
        return pd.DataFrame(rows)

    # ------------------------------------------------------------- journeys
    def search_stops(self, text: str, limit: int = 30) -> pd.DataFrame:
        """Find stops whose name contains ``text`` (case-insensitive)."""
        s = self.stops
        m = s[s["stop_name"].str.contains(text.upper().strip(), na=False, regex=False)]
        return m.drop_duplicates("stop_name").head(limit)

    def find_routes_between(self, origin: str, destination: str) -> pd.DataFrame:
        """Direct routes serving a stop matching ``origin`` and one matching ``destination``."""
        s = self.stops
        o = s[s["stop_name"].str.contains(origin.upper().strip(), na=False, regex=False)]
        t = s[s["stop_name"].str.contains(destination.upper().strip(), na=False, regex=False)]
        common = sorted(set(o["route_id"]) & set(t["route_id"]) & set(self.routes))
        rows = [{"route_id": r,
                 "origin_stop": o[o["route_id"] == r]["stop_name"].iloc[0],
                 "destination_stop": t[t["route_id"] == r]["stop_name"].iloc[0]} for r in common]
        return pd.DataFrame(rows)

    # -------------------------------------------------------- optimisation
    def recommendations(self, d) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
        """Hourly re-sizing + route-level actions + network impact for a date (forecast-based)."""
        f = self.predict_day(d)
        opt = optimize_frequencies(f)
        rec = route_recommendations(opt, self.route_info, self.overlap)
        return opt, rec, impact_summary(opt)
