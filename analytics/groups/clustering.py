"""Stage 5, Step 48: KMeans route groups (spec 9.11.3), fitted on development profiles only.

Pipeline (saved as one object, so later assignments use exactly the same state):
  ServiceAwareMedianImputer  fills only truly missing values; a weekend ratio's median comes only from routes
                             whose status is 'available' (structural zeros and missing values excluded); a
                             structural zero is a known 0 and is never filled
  StandardScaler             fitted on development profiles
  KMeans                     n_init and random_state from groups.json
Every fit/predict runs with one thread (threadpool_limits), so KMeans's parallel loop cannot change the order in
which partial sums are added. Cluster numbers are not an order of efficiency; names come only after inspection.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from analytics.groups.profiles import OK_STATUS, WEEKEND, transformed

RATIO_STATUS = {f"{n}_to_weekday_rides_ratio": f"{n}_service_status" for n in WEEKEND.values()}
NOT_IN_DEV = "no matched days in the development profile period"
RIDERSHIP_ONLY = "no matched schedule in the ridership window (ridership-only identifier)"


class ServiceAwareMedianImputer(BaseEstimator, TransformerMixin):
    """Median imputation that ignores structural zeros. Input: a DataFrame with `features` (+ status columns)."""

    def __init__(self, features: list[str] | None = None):
        self.features = features

    def fit(self, X: pd.DataFrame, y=None):
        medians = {}
        for f in self.features:
            v = X[f]
            if f in RATIO_STATUS:
                v = v[X[RATIO_STATUS[f]].eq(OK_STATUS)]  # only routes that HAVE that service and enough days
            v = v.dropna()
            if v.empty:
                raise ValueError(f"no observed value to fit the median of {f}")
            medians[f] = float(v.median())
        self.medians_ = medians
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        out = X[self.features].astype(float).copy()
        for f in self.features:
            out[f] = out[f].fillna(self.medians_[f])  # NaN only; a structural 0 is a value and stays 0
        return out.to_numpy()


def model_frame(profiles: pd.DataFrame, features: list[str], cfg: dict) -> pd.DataFrame:
    x = transformed(profiles, cfg)[features]
    status = [s for f, s in RATIO_STATUS.items() if f in features]
    out = pd.concat([x, profiles[status]], axis=1)
    out.index = pd.Index(profiles["route"].astype(str).to_numpy(), name="route")  # route-keyed: halves align by route
    if not out.index.is_unique:
        raise ValueError("one profile per route required")
    return out


def make_pipeline(features: list[str], k: int, seed: int, cfg: dict) -> Pipeline:
    return Pipeline([("impute", ServiceAwareMedianImputer(features)), ("scale", StandardScaler()),
                     ("kmeans", KMeans(n_clusters=k, n_init=int(cfg["clustering"]["kmeans"]["n_init"]),
                                       random_state=seed))])


def fit(frame: pd.DataFrame, features: list[str], k: int, seed: int, cfg: dict) -> Pipeline:
    with threadpool_limits(limits=1):
        return make_pipeline(features, k, seed, cfg).fit(frame)


def predict(pipe: Pipeline, frame: pd.DataFrame) -> np.ndarray:
    with threadpool_limits(limits=1):
        return pipe.predict(frame)


def evaluate_k(frame: pd.DataFrame, features: list[str], cfg: dict, halves: list[pd.DataFrame]) -> pd.DataFrame:
    """frame: base-eligible development profiles (model_frame); halves: the same for each half-period."""
    c = cfg["clustering"]
    lo, hi = c["kmeans"]["k_range"]
    rows = []
    for k in range(lo, hi + 1):
        pipe = fit(frame, features, k, int(cfg["seed"]), cfg)
        labels = pipe.named_steps["kmeans"].labels_
        sizes = np.bincount(labels, minlength=k)
        scaled = pipe[:-1].transform(frame)
        repeats = [adjusted_rand_score(labels, fit(frame, features, k, s, cfg).named_steps["kmeans"].labels_)
                   for s in c["kmeans"]["stability_seeds"]]
        h1, h2 = halves
        common = h1.index.intersection(h2.index)
        l1 = predict(fit(h1.loc[common], features, k, int(cfg["seed"]), cfg), h1.loc[common])
        l2 = predict(fit(h2.loc[common], features, k, int(cfg["seed"]), cfg), h2.loc[common])
        rows.append({"k": k, "group_sizes": sizes.tolist(), "smallest_group": int(sizes.min()),
                     "passes_size_gate": bool(sizes.min() >= c["min_group_routes"]),
                     "silhouette": float(silhouette_score(scaled, labels)),
                     "stability_ari_mean": float(np.mean(repeats)), "stability_ari_min": float(np.min(repeats)),
                     "period_halves_ari": float(adjusted_rand_score(l1, l2)), "period_halves_routes": int(len(common))})
    return pd.DataFrame(rows)


def choose_k(table: pd.DataFrame, cfg: dict) -> int | None:
    passing = table[table["passes_size_gate"]]
    if passing.empty:
        return None
    best = passing["silhouette"].max()
    return int(passing.loc[passing["silhouette"] >= best - cfg["clustering"]["silhouette_tolerance"], "k"].min())


def membership(profiles: pd.DataFrame, labels: pd.Series | None, all_routes: list[str],
               ridership_only: set[str]) -> pd.DataFrame:
    """One row per route in the ridership window: a group number or 'ungrouped' with a reason."""
    p = profiles.set_index("route")
    rows = []
    for r in sorted(set(all_routes)):
        if labels is not None and r in labels.index:
            rows.append({"route": r, "group": str(int(labels[r])), "reason": "grouped"})
        elif r in p.index and not bool(p.loc[r, "base_eligible"]):
            rows.append({"route": r, "group": "ungrouped", "reason": p.loc[r, "ungrouped_reason"]})
        elif r in p.index:
            rows.append({"route": r, "group": "ungrouped", "reason": "no group count passed the size gate"})
        elif r in ridership_only:
            rows.append({"route": r, "group": "ungrouped", "reason": RIDERSHIP_ONLY})
        else:
            rows.append({"route": r, "group": "ungrouped", "reason": NOT_IN_DEV})
    return pd.DataFrame(rows)


def group_summary(profiles: pd.DataFrame, labels: pd.Series, cfg: dict) -> pd.DataFrame:
    """Original-unit summaries of ALL candidates (not only the selected ones), per group."""
    cand = cfg["clustering"]["candidates_in_priority_order"]
    p = profiles.set_index("route").loc[labels.index].assign(group=labels.astype(int))
    rows = []
    for gid, g in p.groupby("group"):
        row = {"group": int(gid), "routes": int(len(g)), "route_list": ", ".join(sorted(g.index))}
        for f in cand:
            row.update({f"{f}_median": float(g[f].median()), f"{f}_mean": float(g[f].mean()),
                        f"{f}_min": float(g[f].min()), f"{f}_max": float(g[f].max())})
        for n in WEEKEND.values():
            for s, cnt in g[f"{n}_service_status"].value_counts().items():
                row[f"{n}_{s}"] = int(cnt)
        rows.append(row)
    out = pd.DataFrame(rows)
    counts = [f"{n}_{s}" for n in WEEKEND.values() for s in ("available", "no_scheduled_service",
                                                               "insufficient_observations")]
    for c in counts:  # a status absent from a group is a count of 0 (a real count, not a missing value)
        out[c] = out[c].fillna(0).astype(int) if c in out else 0
    return out


def centroids_original_units(pipe: Pipeline, features: list[str], cfg: dict) -> pd.DataFrame:
    centers = pipe.named_steps["scale"].inverse_transform(pipe.named_steps["kmeans"].cluster_centers_)
    out = pd.DataFrame(centers, columns=features)
    for f in cfg["clustering"]["log1p_features"]:
        if f in out:
            out[f] = np.expm1(out[f])
    return out.rename_axis("group").reset_index()


def assign_group(pipe: Pipeline, later_profiles: pd.DataFrame, features: list[str], cfg: dict) -> pd.DataFrame:
    """Assign later-period profiles to the FROZEN groups (never refits). Base-gate failures stay ungrouped."""
    ok = later_profiles["base_eligible"].astype(bool)
    out = later_profiles[["route"]].copy()
    # a reason column that is all-missing would be stored as numbers; keep it text so reasons can be written
    out["group"], out["reason"] = "ungrouped", later_profiles["ungrouped_reason"].astype(object)
    if ok.any():
        frame = model_frame(later_profiles[ok], features, cfg)
        out.loc[ok, "group"] = [str(int(g)) for g in predict(pipe, frame)]
        out.loc[ok, "reason"] = "assigned with the frozen development-period pipeline"
    return out
