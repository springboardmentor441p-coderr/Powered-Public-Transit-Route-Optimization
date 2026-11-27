"""Module 5a - Unsupervised route segmentation (KMeans + DBSCAN) and overlap detection."""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.neighbors import NearestNeighbors

from . import config as C
from .preprocessing import scale_for_clustering


def select_k(Xs: np.ndarray, k_range=range(2, 11)) -> pd.DataFrame:
    """Evaluate KMeans for several k with inertia (elbow), silhouette, Davies-Bouldin
    and Calinski-Harabasz scores."""
    rows = []
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=20, random_state=C.RANDOM_STATE).fit(Xs)
        rows.append({"k": k, "inertia": km.inertia_,
                     "silhouette": silhouette_score(Xs, km.labels_),
                     "davies_bouldin": davies_bouldin_score(Xs, km.labels_),
                     "calinski_harabasz": calinski_harabasz_score(Xs, km.labels_)})
    return pd.DataFrame(rows)


def choose_k(scores: pd.DataFrame, k_min: int = 4) -> int:
    """Best silhouette among k >= k_min (fewer than 4 segments is not actionable for planners)."""
    s = scores[scores["k"] >= k_min]
    return int(s.loc[s["silhouette"].idxmax(), "k"])


def dbscan_eps(Xs: np.ndarray, min_samples: int) -> float:
    """Pick eps from the k-distance curve (point of maximum curvature / 90th pct fallback)."""
    nn = NearestNeighbors(n_neighbors=min_samples).fit(Xs)
    d = np.sort(nn.kneighbors(Xs)[0][:, -1])
    # knee: max distance from the chord joining first and last points
    x = np.arange(len(d)); x1, y1, x2, y2 = 0, d[0], len(d) - 1, d[-1]
    dist = np.abs((y2 - y1) * x - (x2 - x1) * d + x2 * y1 - y2 * x1) / np.hypot(y2 - y1, x2 - x1)
    eps = float(d[int(dist.argmax())])
    return eps if eps > 0 else float(np.quantile(d, 0.9))


DESCRIPTORS = {  # feature: (word if above network median, word if below)
    "avg_daily_ridership": ("High-Volume", "Low-Volume"),
    "mean_occupancy": ("Crowded", "Spare-Capacity"),
    "productivity": ("High-Productivity", "Low-Productivity"),
    "am_peak_share": ("AM-Peak Commuter", "Off-Peak"),
    "weekend_ratio": ("All-Week", "Weekday-Focused"),
    "night_share": ("Night-Owl", "Daytime"),
    "mean_speed_mph": ("Fast", "Slow"),
    "length_mi": ("Long-Haul", "Short"),
    "reliability": ("Reliable", "Unreliable"),
}


def name_clusters(profiles: pd.DataFrame, label_col: str = "kmeans_cluster") -> dict[int, str]:
    """Human-readable cluster names: dominant route type (if >= 60 %) + the two
    features whose cluster median deviates most (in robust z-score) from the network."""
    feats = list(DESCRIPTORS)
    med = profiles[feats].median()
    iqr = (profiles[feats].quantile(0.75) - profiles[feats].quantile(0.25)).replace(0, 1)
    names, used = {}, {}
    for cid, grp in profiles.groupby(label_col):
        z = ((grp[feats].median() - med) / iqr).sort_values(key=np.abs, ascending=False)
        words = [DESCRIPTORS[f][0 if z[f] > 0 else 1] for f in z.index[:2]]
        rt = grp["route_type"].value_counts(normalize=True) if "route_type" in grp else pd.Series(dtype=float)
        prefix = (rt.index[0] if len(rt) and rt.iloc[0] >= 0.6 and rt.index[0] != "Local" else "")
        prefix = {"Select Bus Service": "SBS"}.get(prefix, prefix)
        n = " ".join(x for x in [prefix, " / ".join(words)] if x)
        used[n] = used.get(n, 0) + 1
        names[int(cid)] = n if used[n] == 1 else f"{n} ({used[n]})"
    return names


def run_clustering(profiles: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Fit KMeans (k by silhouette) and DBSCAN (eps by k-distance knee) on scaled
    route profiles. Adds cluster labels, names, DBSCAN outlier flag and 2-D PCA coords."""
    Xs, scaler = scale_for_clustering(profiles)
    scores = select_k(Xs)
    k = choose_k(scores)
    km = KMeans(n_clusters=k, n_init=50, random_state=C.RANDOM_STATE).fit(Xs)
    prof = profiles.copy()
    prof["kmeans_cluster"] = km.labels_

    min_samples = max(4, int(np.log(len(Xs))) + 1)
    eps = dbscan_eps(Xs, min_samples)
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(Xs)
    prof["dbscan_cluster"] = db.labels_
    prof["dbscan_outlier"] = (db.labels_ == -1).astype(int)

    pca = PCA(n_components=2, random_state=C.RANDOM_STATE).fit(Xs)
    pcs = pca.transform(Xs)
    prof["pc1"], prof["pc2"] = pcs[:, 0], pcs[:, 1]
    names = name_clusters(prof)
    prof["cluster_name"] = prof["kmeans_cluster"].map(names)

    n_db = len(set(db.labels_)) - (1 if -1 in db.labels_ else 0)
    metrics = {
        "k_selection": scores.round(4).to_dict(orient="records"),
        "kmeans": {"k": k, "silhouette": float(silhouette_score(Xs, km.labels_)),
                   "davies_bouldin": float(davies_bouldin_score(Xs, km.labels_)),
                   "calinski_harabasz": float(calinski_harabasz_score(Xs, km.labels_)),
                   "cluster_sizes": prof["kmeans_cluster"].value_counts().sort_index().to_dict(),
                   "cluster_names": names},
        "dbscan": {"eps": eps, "min_samples": min_samples, "n_clusters": n_db,
                   "n_outliers": int((db.labels_ == -1).sum()),
                   "silhouette_non_noise": float(silhouette_score(Xs[db.labels_ != -1], db.labels_[db.labels_ != -1]))
                   if n_db >= 2 else None},
        "pca_explained_variance": pca.explained_variance_ratio_.round(4).tolist(),
    }
    return prof, {"metrics": metrics, "kmeans": km, "dbscan": db, "scaler": scaler, "pca": pca}


def stop_overlap(stops: pd.DataFrame, routes: list[str], min_jaccard: float = 0.2) -> pd.DataFrame:
    """Pairwise stop-set Jaccard similarity between routes (overlap detection).

    Stops are matched by stop_id and by ~50 m rounded coordinates so that
    opposite-side stops of the same street corner count as shared.
    """
    s = stops[stops["route_id"].isin(routes)].copy()
    s["cell"] = (s["latitude"].round(3).astype(str) + "," + s["longitude"].round(3).astype(str))
    sets = s.groupby("route_id")["cell"].apply(set).to_dict()
    # inverted index to avoid O(n^2) over all pairs
    inv: dict[str, set] = {}
    for r, cells in sets.items():
        for c in cells:
            inv.setdefault(c, set()).add(r)
    pairs: dict[tuple, int] = {}
    for rs in inv.values():
        for a, b in itertools.combinations(sorted(rs), 2):
            pairs[(a, b)] = pairs.get((a, b), 0) + 1
    rows = []
    for (a, b), inter in pairs.items():
        union = len(sets[a]) + len(sets[b]) - inter
        j = inter / union if union else 0
        if j >= min_jaccard:
            rows.append({"route_a": a, "route_b": b, "shared_stops": inter, "jaccard": round(j, 3),
                         "share_of_a": round(inter / len(sets[a]), 3), "share_of_b": round(inter / len(sets[b]), 3)})
    return pd.DataFrame(rows).sort_values("jaccard", ascending=False) if rows else \
        pd.DataFrame(columns=["route_a", "route_b", "shared_stops", "jaccard", "share_of_a", "share_of_b"])
