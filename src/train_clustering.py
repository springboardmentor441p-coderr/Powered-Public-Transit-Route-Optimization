"""
Milestone 3 — Step 4: Route Clustering (src/train_clustering.py)

Fixed Setup & Group-Count Selection Rule (Written Before Running):
1. Outlier Removal Before Clustering:
   - On all 41 routes, `M35` (Randall's Island, 3-NN distance = 7.97) forms a singleton group of its
     own at every k in {2, 3, 4, 5, 6}, and the high silhouette score at k = 2 (0.6179) comes entirely
     from separating M35 from the other 40 routes. One route on its own is an outlier, not a group.
   - We therefore remove `M35` before clustering, report `M35` separately as "unlike every other route"
     with its exact unscaled numbers, and cluster the remaining 40 routes across k in {2, 3, 4, 5, 6}.
   - We also check `M98` (3-NN distance = 4.33, the second-furthest route): unlike `M35`, on the 40 routes
     `M98` stays inside the 7-route lower-volume/higher-variability group at k = 2, 3, and 4, and only
     becomes a singleton at k = 5 and k = 6. We keep `M98` in the 40-route clustering and list it
     explicitly as a member that does not fit its group's short-length pattern (15.56 km vs 4.06 km median).
2. Pre-Specified Rule for Choosing the Number of Groups (k) on the 40 Routes:
   - Choose the number of groups k in {2, 3, 4, 5, 6} that is most stable with 10 random starts per run
     (`n_init=10`, how KMeans normally runs) and leave-one-route-out (LOO) cross-validation (`ARI >= 0.90`),
     without creating 1-route singletons, unless its silhouette score is clearly lower than a competing k
     (or merges distinct operational regimes at k = 2 where single-start stability is weak).
   - Applying this rule selects **k = 3 groups on the 40 routes** (sizes 18, 15, 7):
     * k = 2 (sizes 23, 17) has the lowest silhouette score (0.2551) and poor 1-start stability (0.4416),
       merging the ~1,400 riders/day high-variability routes with the ~6,900 riders/day high-density routes.
     * **k = 3 (sizes 18, 15, 7)** achieves **0.9831 ARI with 10 starts**, **0.9126 LOO ARI**, the **highest
       1-start ARI (0.7522)**, higher silhouette (0.2682), and zero singletons.
     * k = 4, 5, 6 drop in 10-start stability (0.9084, 0.8307, 0.7497) and k = 5, 6 isolate `M98` as a singleton.
3. Weak Cluster Structure:
   - Silhouette scores of 0.255 to 0.297 across k = 2..6 mean the groups overlap substantially in the
     9-feature space. The 3 groups summarise routes into broad types; they are not sharp categories.
4. Measured-Feature Group Names & Non-Fitting Members:
   - Group 1 (n=18): Longer routes (median 12.6 km, about 7,000 weekday riders)
   - Group 2 (n=15): Short routes with the most riders per service-hour (median 4.2 km, 66 riders per service-hour at peak)
   - Group 3 (n=7): Short routes with fewer riders and less steady demand (median 4.1 km, about 1,400 weekday riders, variability 0.28)
   - Outlier (n=1, removed before clustering): M35 — Unlike every other route (~146 weekday riders, 1.67 weekend/weekday ratio, 21.7 km/h speed, 100% exclusive stops)
5. DBSCAN (min_samples = 3, sorted 3-NN distance elbow eps = 1.80):
   - Reported honestly: with 41 routes (or 40 excluding M35) and 9 features, there are too few points
     for density-based grouping, which is why DBSCAN marks 12 routes—including the busiest ones
     (M15+, M15, M60+, M104)—as noise.
"""

import sys
import zipfile
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Tuple

import folium
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_PROCESSED = ROOT / "data" / "processed"
GTFS_ZIP = ROOT / "data" / "raw" / "gtfs" / "manhattan" / "2026-04-09" / "original.zip"
MODELS_DIR = ROOT / "models"
TAB_DIR = ROOT / "reports" / "tables"
FIG_DIR = ROOT / "reports" / "figures"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

SELECTED_9_FEATURES = [
    "weekday_riders_log",
    "weekend_to_weekday_ratio",
    "morning_peak_share",
    "night_share",
    "peak_riders_per_service_hour",
    "route_length_km",
    "scheduled_speed_kmh",
    "demand_variability",
    "exclusive_stop_share",
]

GROUP_METADATA_K3_PLUS_M35 = {
    1: {
        "group_id": 1,
        "group_label": "Group 1: Longer routes (median 12.6 km, ~7,000 weekday riders)",
        "short_label": "Group 1: Longer routes, ~7,000 riders (n=18)",
        "color": "#1d4ed8",
        "marker": "o",
        "non_fitting_members": (
            "M12 (6.10 km, ~480 weekday riders/day) and M55 (8.16 km, ~1,210 riders/day) are shorter and carry "
            "far fewer riders than the 12.58 km / ~7,018-rider median, while M10 (8.36 km, ~1,943 riders/day) and "
            "M20 (8.30 km, ~1,813 riders/day) are mid-length routes under 2,000 riders/day; KMeans places them here "
            "because of their high weekend-to-weekday ratios (0.75–1.04) and late-night shares (11.9–15.4%)."
        ),
        "plain_description": (
            "Longer routes (median 12.58 km, scheduled speed 10.0 km/h) averaging about 7,018 weekday riders/day "
            "(log=8.86), with the highest weekend-to-weekday ratio (0.755) and night share (13.7%), moderate peak "
            "riders per service-hour (32.45), steady weekday demand (variability=0.175), and the lowest exclusive-stop "
            "share (44.7%). Exceptions inside this group: M12 (6.10 km, ~480 riders/day), M55 (8.16 km, ~1,210 riders/day), "
            "M10 (8.36 km, ~1,943 riders/day), and M20 (8.30 km, ~1,813 riders/day) have much lower ridership and shorter "
            "lengths, but group here due to their high weekend retention (0.75–1.04) and night shares."
        ),
    },
    2: {
        "group_id": 2,
        "group_label": "Group 2: Short routes with the most riders per service-hour (median 4.2 km, 66 peak riders/service-hr)",
        "short_label": "Group 2: Short routes, 66 peak riders/service-hr (n=15)",
        "color": "#059669",
        "marker": "s",
        "non_fitting_members": (
            "M15+ is a 13.86 km north–south Select Bus Service route (more than 3x the 4.24 km group median), yet it "
            "falls into this short-route group because its 94.2 peak riders per service-hour, ~26,160 weekday riders/day "
            "(log=10.17), low variability (0.141), and 0.583 weekend ratio match the short high-density corridors. "
            "M31 (7.09 km) and M57 (6.66 km) are also somewhat longer than the 4.24 km median."
        ),
        "plain_description": (
            "Short routes (median 4.24 km, scheduled speed 9.7 km/h) with the most riders per service-hour at peak "
            "(median 65.76 peak riders/service-hr, double Group 1), high weekday ridership (~6,871 riders/day, log=8.84), "
            "the lowest day-to-day demand variability (0.163), moderate weekend ratio (0.539), and 50.0% exclusive stops. "
            "Key exception: M15+ is 13.86 km long (a north–south route, not a short crosstown route), but lands here "
            "because of its 94.2 peak riders per service-hour and low variability (0.141)."
        ),
    },
    3: {
        "group_id": 3,
        "group_label": "Group 3: Short routes with fewer riders and less steady demand (median 4.1 km, ~1,400 riders, variability 0.28)",
        "short_label": "Group 3: Short routes, ~1,400 riders & higher CV (n=7)",
        "color": "#d97706",
        "marker": "^",
        "non_fitting_members": (
            "M98 is 15.56 km long (nearly 4x the 4.06 km group median) with 13.4 km/h speed, 0.00 weekend ratio "
            "(weekday peak-only service), and 0.525 demand variability; it stays in Group 3 at k=2..4 because of its "
            "low daily ridership (~356 riders/day, log=5.88) and 57.2% morning peak share, before splitting into a "
            "singleton at k=5 and k=6."
        ),
        "plain_description": (
            "Short routes (median 4.06 km, scheduled speed 9.8 km/h) with fewer weekday riders (~1,431 riders/day, "
            "log=7.27) and less steady demand (median variability=0.276), alongside the highest morning peak share "
            "(34.7% of daily riders in 07:00–09:59), lowest night share (7.6%) and weekend ratio (0.470), 36.08 peak "
            "riders per service-hour, and 69.1% exclusive stops. Key exception: M98 is 15.56 km long (at 13.4 km/h) "
            "with 0.00 weekend ratio, grouping here due to its low riders (~356/day) and 57.2% morning peak share."
        ),
    },
    0: {
        "group_id": 0,
        "group_label": "Outlier (Removed Before Clustering): M35 — Unlike every other route",
        "short_label": "Outlier (Removed): M35 (n=1)",
        "color": "#dc2626",
        "marker": "D",
        "non_fitting_members": "N/A — M35 is reported separately as a 1-route outlier (3-NN distance = 7.97) rather than a cluster.",
        "plain_description": (
            "Removed before clustering because one route on its own is an outlier, not a group: M35 (4.95 km across the "
            "RFK Bridge to Randall's Island) has the lowest weekday riders (~146/day in Jan–May, log=4.99), the only "
            "weekend-to-weekday ratio above 1.0 (1.666), the lowest peak riders per service-hour (4.42), the fastest "
            "scheduled speed (21.7 km/h vs 9.8 km/h network median), the highest demand variability (0.847), and "
            "100.0% exclusive stops."
        ),
    },
}


def canonicalize_labels(labels: np.ndarray, X_df: pd.DataFrame) -> np.ndarray:
    """
    Order cluster labels 1..k by descending cluster size, breaking ties by descending
    median weekday_riders_log so group numbering is deterministic and human-readable.
    """
    uniq = np.unique(labels)
    order_info = []
    for c in uniq:
        mask = labels == c
        cnt = int(mask.sum())
        med_riders = float(X_df.loc[mask, "weekday_riders_log"].median())
        order_info.append((c, cnt, med_riders))
    order_info.sort(key=lambda item: (-item[1], -item[2]))
    mapping = {old_c: new_idx + 1 for new_idx, (old_c, _, _) in enumerate(order_info)}
    return np.array([mapping[c] for c in labels], dtype=int)


def evaluate_kmeans_subset(
    X_df: pd.DataFrame,
    subset_name: str,
) -> Tuple[pd.DataFrame, Dict[int, np.ndarray], Dict[int, KMeans]]:
    """
    Evaluate KMeans for k in {2, 3, 4, 5, 6} on X_df:
    - Silhouette score and inertia on the reference fit (n_init=50, random_state=42)
    - Stability Check 1: 20 multi-start runs with n_init=10 (how KMeans normally runs) pairwise ARI
    - Stability Check 2: Leave-one-route-out (LOO, N runs of N-1 routes, n_init=10) ARI vs reference
    - Stability Check 3: 20 single-start runs with n_init=1 pairwise ARI
    """
    X = X_df[SELECTED_9_FEATURES].values
    n_routes = X.shape[0]
    rows = []
    ref_labels_by_k: Dict[int, np.ndarray] = {}
    ref_models_by_k: Dict[int, KMeans] = {}

    for k in range(2, 7):
        km_ref = KMeans(n_clusters=k, n_init=50, random_state=42)
        raw_ref = km_ref.fit_predict(X)
        labels_ref = canonicalize_labels(raw_ref, X_df)
        ref_labels_by_k[k] = labels_ref
        ref_models_by_k[k] = km_ref

        sil = float(silhouette_score(X, labels_ref))
        inertia = float(km_ref.inertia_)

        _, counts = np.unique(labels_ref, return_counts=True)
        sizes_str = ", ".join(str(int(c)) for c in sorted(counts, reverse=True))
        singleton_routes = [
            X_df.index[labels_ref == c].tolist()[0]
            for c in np.unique(labels_ref)
            if int((labels_ref == c).sum()) == 1
        ]
        singleton_str = ", ".join(singleton_routes) if singleton_routes else "none"

        # 20 multi-start runs (n_init=10, random_state=0..19) — primary KMeans stability check
        runs_10 = [
            KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(X)
            for seed in range(20)
        ]
        pairwise_10 = [
            adjusted_rand_score(runs_10[i], runs_10[j])
            for i, j in combinations(range(20), 2)
        ]

        # Leave-one-route-out (LOO) stability with n_init=10
        loo_aris = []
        for drop_idx in range(n_routes):
            mask = np.ones(n_routes, dtype=bool)
            mask[drop_idx] = False
            km_loo = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels_loo = km_loo.fit_predict(X[mask])
            loo_aris.append(adjusted_rand_score(labels_ref[mask], labels_loo))

        # 20 single-seed random starts (n_init=1, random_state=0..19)
        runs_1 = [
            KMeans(n_clusters=k, n_init=1, random_state=seed).fit_predict(X)
            for seed in range(20)
        ]
        pairwise_1 = [
            adjusted_rand_score(runs_1[i], runs_1[j])
            for i, j in combinations(range(20), 2)
        ]

        if n_routes == 40:
            selection_note = {
                2: "Coarse 2-group split (23 vs 17); lowest silhouette (0.2551) and weak 1-start ARI (0.4416); merges ~1,400 and ~6,900 rider routes",
                3: "Selected k=3 on 40 routes: 0.9831 ARI (10 starts), 0.9126 LOO ARI, highest 1-start ARI (0.7522), higher silhouette (0.2682), 0 singletons",
                4: "10-start ARI drops from 0.9831 to 0.9084 and 1-start ARI drops to 0.6331; splits 5 mid-length routes into a 4th group",
                5: "Isolates M98 as a 1-route singleton (15, 13, 6, 5, 1); 10-start ARI drops to 0.8307 and LOO ARI to 0.8654",
                6: "Over-segmented with M98 singleton (15, 10, 6, 5, 3, 1); 10-start ARI drops to 0.7497 and LOO ARI to 0.8444",
            }[k]
            is_sel = (k == 3)
        else:
            selection_note = (
                f"All 41 routes: M35 forms a 1-route singleton at every k (singletons: {singleton_str}); "
                f"k=2 silhouette (0.6179) is an artifact of 40 vs 1 M35 split"
            )
            is_sel = False

        rows.append({
            "route_set": subset_name,
            "n_routes_clustered": n_routes,
            "k": k,
            "silhouette_score": round(sil, 4),
            "inertia": round(inertia, 2),
            "cluster_sizes": sizes_str,
            "singletons": singleton_str,
            "ari_10starts_mean": round(float(np.mean(pairwise_10)), 4),
            "ari_10starts_std": round(float(np.std(pairwise_10)), 4),
            "ari_10starts_min": round(float(np.min(pairwise_10)), 4),
            "ari_loo_mean": round(float(np.mean(loo_aris)), 4),
            "ari_loo_std": round(float(np.std(loo_aris)), 4),
            "ari_loo_min": round(float(np.min(loo_aris)), 4),
            "ari_1start_mean": round(float(np.mean(pairwise_1)), 4),
            "ari_1start_std": round(float(np.std(pairwise_1)), 4),
            "is_selected_k": is_sel,
            "selection_note": selection_note,
        })

    return pd.DataFrame(rows), ref_labels_by_k, ref_models_by_k


def evaluate_dbscan_and_k_distance(
    X_all_df: pd.DataFrame,
    assigned_groups_41: np.ndarray,
    min_samples: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """
    Compute sorted 3-nearest-neighbor distances for DBSCAN (min_samples=3) and evaluate
    DBSCAN across eps in [1.20, 1.50, 1.80, 2.00, 2.20, 2.50], with eps=1.80 as the elbow.
    """
    X = X_all_df[SELECTED_9_FEATURES].values
    routes = X_all_df.index.tolist()

    nn = NearestNeighbors(n_neighbors=min_samples)
    nn.fit(X)
    dists, indices = nn.kneighbors(X)
    k_dist = dists[:, min_samples - 1]
    nearest_other_route = [routes[idx] for idx in indices[:, 1]]
    kth_neighbor_route = [routes[idx] for idx in indices[:, min_samples - 1]]

    kdist_df = pd.DataFrame({
        "route_id": routes,
        "knn_3_distance": np.round(k_dist, 4),
        "nearest_neighbor_route": nearest_other_route,
        "third_nn_route": kth_neighbor_route,
        "assigned_group": assigned_groups_41,
    }).sort_values("knn_3_distance", ascending=True).reset_index(drop=True)
    kdist_df["sorted_rank"] = np.arange(1, len(kdist_df) + 1)

    eps_grid = [1.20, 1.50, 1.80, 2.00, 2.20, 2.50]
    db_rows = []
    labels_at_180 = None

    for eps in eps_grid:
        db = DBSCAN(eps=eps, min_samples=min_samples)
        lbl = db.fit_predict(X)
        if np.isclose(eps, 1.80):
            labels_at_180 = lbl.copy()

        non_noise = lbl != -1
        n_noise = int((lbl == -1).sum())
        n_clusters = int(len(set(lbl)) - (1 if -1 in lbl else 0))

        if n_clusters >= 2 and non_noise.sum() > n_clusters:
            sil_nn = round(float(silhouette_score(X[non_noise], lbl[non_noise])), 4)
        else:
            sil_nn = np.nan

        if non_noise.sum() >= 2:
            ari_nn = round(float(adjusted_rand_score(assigned_groups_41[non_noise], lbl[non_noise])), 4)
        else:
            ari_nn = np.nan

        cluster_counts = [int((lbl == c).sum()) for c in sorted(set(lbl)) if c != -1]
        sizes_str = ", ".join(str(c) for c in sorted(cluster_counts, reverse=True)) if cluster_counts else "none"
        noise_routes = [routes[i] for i in range(len(routes)) if lbl[i] == -1]

        role_note = {
            1.20: "Too tight: 35/41 routes (85.4%) marked as noise; 9D space is too sparse for small radius",
            1.50: "Tight: 18/41 routes (43.9%) marked as noise; 3 small cores (sizes 9, 9, 5)",
            1.80: "Selected k-distance elbow (eps=1.80): 3 clusters (16, 10, 3) + 12 noise routes (29.3%, including busiest M15+, M15, M60+)",
            2.00: "Loose: main cores merge into one 27-route cluster (+ 4-route group); 10 noise routes (24.4%)",
            2.20: "Very loose: 32 routes merge into 1 cluster + 3-route group; 6 routes (14.6%) remain noise",
            2.50: "Over-merged: 35 routes collapse into a single cluster; 6 routes (14.6%) remain noise",
        }[eps]

        db_rows.append({
            "eps": eps,
            "min_samples": min_samples,
            "is_elbow_setting": np.isclose(eps, 1.80),
            "n_clusters": n_clusters,
            "n_clustered_routes": int(non_noise.sum()),
            "n_noise_routes": n_noise,
            "noise_pct": round(n_noise / len(routes) * 100.0, 2),
            "cluster_sizes": sizes_str,
            "silhouette_non_noise": sil_nn,
            "ari_vs_kmeans_non_noise": ari_nn,
            "noise_routes": ", ".join(noise_routes),
            "interpretation": role_note,
        })

    return pd.DataFrame(db_rows), kdist_df, labels_at_180


def load_representative_route_geometries(route_ids: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Extract representative stop-coordinate sequences for each of the 41 Manhattan routes
    from the primary GTFS feed (2026-04-09/original.zip) so we can plot geographic route maps coloured by group.
    """
    with zipfile.ZipFile(GTFS_ZIP) as z:
        trips = pd.read_csv(z.open("trips.txt"), dtype=str)
        stop_times = pd.read_csv(z.open("stop_times.txt"), dtype=str)
        stops = pd.read_csv(z.open("stops.txt"), dtype=str)

    stops["stop_lat"] = stops["stop_lat"].astype(float)
    stops["stop_lon"] = stops["stop_lon"].astype(float)
    stop_times["stop_sequence"] = stop_times["stop_sequence"].astype(int)

    trips_sub = trips[trips["route_id"].isin(route_ids)].copy()
    st_counts = stop_times.groupby("trip_id").size().rename("n_stops")
    trips_sub = trips_sub.merge(st_counts, on="trip_id", how="inner")

    rep_trips = (
        trips_sub.sort_values(["route_id", "n_stops", "trip_id"], ascending=[True, False, True])
        .groupby("route_id", as_index=False)
        .first()
    )

    rep_st = (
        stop_times[stop_times["trip_id"].isin(rep_trips["trip_id"])]
        .merge(rep_trips[["trip_id", "route_id"]], on="trip_id", how="inner")
        .merge(stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]], on="stop_id", how="inner")
        .sort_values(["route_id", "stop_sequence"])
    )

    geom_by_route: Dict[str, pd.DataFrame] = {}
    for rid, grp in rep_st.groupby("route_id"):
        geom_by_route[str(rid)] = grp[["stop_sequence", "stop_id", "stop_name", "stop_lat", "stop_lon"]].reset_index(drop=True)
    return geom_by_route


def build_clustering_figures_and_map(
    k_sel_40_df: pd.DataFrame,
    kdist_df: pd.DataFrame,
    assigned_df: pd.DataFrame,
    pca_40: PCA,
    geom_by_route: Dict[str, pd.DataFrame],
) -> None:
    """
    Generate:
    1. `reports/figures/m3_clustering_evaluation.png` (KMeans on 40 routes excluding M35 + DBSCAN k-distance plot)
    2. `reports/figures/m3_clustering_pca_and_map.png` (2D PCA scatter plot of 40 clustered routes + M35 inset & Manhattan map)
    3. `reports/figures/m3_route_clusters.html` (Interactive Folium map coloured by measured-feature group)
    """
    # ==========================================================================
    # FIGURE 1: KMEANS ON 40 ROUTES (EXCLUDING M35) & DBSCAN K-DISTANCE PLOT
    # ==========================================================================
    fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.3), dpi=150)

    ks = k_sel_40_df["k"].values
    ax1.plot(ks, k_sel_40_df["ari_10starts_mean"], marker="o", linewidth=2.2, color="#1d4ed8", label="20 Runs ARI (n_init=10, Standard KMeans)")
    ax1.plot(ks, k_sel_40_df["ari_loo_mean"], marker="s", linewidth=2.2, color="#059669", linestyle="--", label="Leave-One-Route-Out ARI (40 runs)")
    ax1.plot(ks, k_sel_40_df["ari_1start_mean"], marker="d", linewidth=1.8, color="#7c3aed", linestyle=":", label="20 Single-Start Runs ARI (n_init=1)")
    ax1.plot(ks, k_sel_40_df["silhouette_score"], marker="^", linewidth=2.2, color="#d97706", linestyle="-.", label="Silhouette Score (Weak: 0.255–0.297)")
    ax1.axvline(3, color="#dc2626", linestyle="--", linewidth=1.6, label="Selected k = 3 (10-Start ARI=0.983, LOO=0.913, Sil=0.268)")

    for _, row in k_sel_40_df.iterrows():
        k_val = int(row["k"])
        ax1.annotate(
            f"{row['ari_10starts_mean']:.3f}",
            (k_val, row["ari_10starts_mean"]),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            fontsize=7.6,
            fontweight="bold",
            color="#1e3a8a",
        )
        ax1.annotate(
            f"Sil={row['silhouette_score']:.3f}",
            (k_val, row["silhouette_score"]),
            textcoords="offset points",
            xytext=(0, -13),
            ha="center",
            fontsize=7.3,
            color="#92400e",
        )

    ax1.set_title("A. KMeans on 40 Routes (Excluding Outlier M35): Stability & Silhouette", fontsize=10.2, fontweight="bold", pad=8)
    ax1.set_xlabel("Number of Groups (k) on the 40 Non-Outlier Routes", fontsize=9.5)
    ax1.set_ylabel("Score / Adjusted Rand Index (ARI)", fontsize=9.5)
    ax1.set_xticks(ks)
    ax1.set_ylim(0.04, 1.08)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="lower left", fontsize=7.4)

    # Panel B: Sorted 3-NN distance plot for DBSCAN (min_samples = 3)
    ranks = kdist_df["sorted_rank"].values
    dists = kdist_df["knn_3_distance"].values
    ax2.plot(ranks, dists, marker="o", markersize=4.5, linewidth=1.8, color="#1e293b", label="Sorted 3-NN Distance (min_samples=3)")
    ax2.axhline(1.80, color="#dc2626", linestyle="--", linewidth=1.6, label="Elbow eps = 1.80 (29 routes in 3 clusters, 12 noise = 29.3%)")
    ax2.axhline(1.50, color="#94a3b8", linestyle=":", linewidth=1.2, label="Tighter eps = 1.50 (18/41 noise = 43.9%)")

    annot_offsets = {
        "M8": (-28, 7),
        "M15+": (-46, 4),
        "M106": (-48, 8),
        "M98": (-46, 5),
        "M35": (-52, -10),
    }
    for _, r in kdist_df.iterrows():
        rid = str(r["route_id"])
        if rid in annot_offsets:
            dx, dy = annot_offsets[rid]
            ax2.annotate(
                f"{rid} ({r['knn_3_distance']:.2f})",
                (r["sorted_rank"], r["knn_3_distance"]),
                textcoords="offset points",
                xytext=(dx, dy),
                fontsize=7.6,
                fontweight="bold",
                color="#dc2626",
            )

    ax2.set_title("B. Sorted 3-NN Distance Plot for DBSCAN (41 Routes in 9D Space)", fontsize=10.2, fontweight="bold", pad=8)
    ax2.set_xlabel("Routes Sorted by 3rd-Nearest-Neighbor Distance (Rank 1..41)", fontsize=9.5)
    ax2.set_ylabel("Euclidean Distance in 9-Feature Scaled Space", fontsize=9.5)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper left", fontsize=7.8)

    fig1.tight_layout()
    fig1.savefig(FIG_DIR / "m3_clustering_evaluation.png", dpi=150, bbox_inches="tight")
    plt.close(fig1)
    print("Saved Step 4 evaluation figure to reports/figures/m3_clustering_evaluation.png", flush=True)

    # ==========================================================================
    # FIGURE 2: PCA SCATTER PLOT (40 ROUTES + M35 NOTE) & GEOGRAPHIC ROUTE MAP
    # ==========================================================================
    fig2, (ax_pca, ax_map) = plt.subplots(
        1, 2, figsize=(14.4, 6.6), dpi=150, gridspec_kw={"width_ratios": [1.18, 1.0]}
    )

    var_pc1 = pca_40.explained_variance_ratio_[0] * 100.0
    var_pc2 = pca_40.explained_variance_ratio_[1] * 100.0

    # Plot the 40 clustered routes (groups 1, 2, 3) on the 40-route PCA axes so M35 doesn't squash them
    for gid in [1, 2, 3]:
        meta = GROUP_METADATA_K3_PLUS_M35[gid]
        sub = assigned_df[assigned_df["group_id"] == gid]
        ax_pca.scatter(
            sub["pc1_40"],
            sub["pc2_40"],
            c=meta["color"],
            marker=meta["marker"],
            s=74,
            alpha=0.9,
            edgecolors="#0f172a",
            linewidths=0.8,
            label=meta["short_label"],
            zorder=4,
        )
        sub_noise = sub[sub["dbscan_eps180_cluster"] == -1]
        if len(sub_noise) > 0:
            ax_pca.scatter(
                sub_noise["pc1_40"],
                sub_noise["pc2_40"],
                facecolors="none",
                edgecolors="#dc2626",
                s=138,
                linewidths=1.1,
                linestyle="--",
                zorder=3,
            )

    for idx_r, r in assigned_df[assigned_df["group_id"] > 0].iterrows():
        dx = 5
        dy = 4 if (idx_r % 2 == 0) else -9
        if r["route_id"] == "M98":
            dx, dy = -30, 6
        ax_pca.annotate(
            r["route_id"],
            (r["pc1_40"], r["pc2_40"]),
            textcoords="offset points",
            xytext=(dx, dy),
            fontsize=7.2,
            fontweight="bold",
            color=GROUP_METADATA_K3_PLUS_M35[int(r["group_id"])]["color"],
        )

    ax_pca.scatter(
        [], [], facecolors="none", edgecolors="#dc2626", s=110, linewidths=1.1,
        linestyle="--", label="DBSCAN Noise @ eps=1.80 (11 of 40 + M35)"
    )
    # Note M35 outlier in a callout box in the empty bottom-left corner of the PCA plot
    m35_row = assigned_df[assigned_df["route_id"] == "M35"].iloc[0]
    ax_pca.text(
        0.02,
        0.03,
        f"Outlier Removed Before Clustering: M35\n"
        f"(projected at PC1={m35_row['pc1_40']:+.1f}, PC2={m35_row['pc2_40']:+.1f}; "
        f"~146 riders/day, 21.7 km/h, 1.67 wknd ratio)",
        transform=ax_pca.transAxes,
        ha="left",
        va="bottom",
        fontsize=7.3,
        color="#991b1b",
        bbox=dict(boxstyle="round,pad=0.35", fc="#fef2f2", ec="#dc2626", alpha=0.92),
        zorder=6,
    )

    ax_pca.axhline(0, color="#cbd5e1", linewidth=0.9, zorder=1)
    ax_pca.axvline(0, color="#cbd5e1", linewidth=0.9, zorder=1)
    ax_pca.set_title(
        f"A. PCA Scatter Plot of 40 Clustered Routes (k = 3, Sil = 0.268)\n"
        f"(PC1 = {var_pc1:.1f}%, PC2 = {var_pc2:.1f}%, Total = {var_pc1 + var_pc2:.1f}% Variance; M35 Removed)",
        fontsize=10.0,
        fontweight="bold",
        pad=8,
    )
    ax_pca.set_xlabel(f"Principal Component 1 ({var_pc1:.1f}% Variance — Scale & All-Day Volume vs Morning Peak & Exclusivity)", fontsize=8.8)
    ax_pca.set_ylabel(f"Principal Component 2 ({var_pc2:.1f}% Variance — Route Length & Weekend Retention vs Peak Riders/Service-Hr)", fontsize=8.8)
    ax_pca.set_ylim(-4.5, 3.4)
    ax_pca.grid(True, alpha=0.25)
    ax_pca.legend(loc="upper left", fontsize=7.4)

    # Panel B: Static Geographic Map of Manhattan Bus Routes Coloured by Group (3 Groups + Outlier M35)
    for gid in [1, 2, 3, 0]:
        meta = GROUP_METADATA_K3_PLUS_M35[gid]
        sub_routes = assigned_df[assigned_df["group_id"] == gid]["route_id"].tolist()
        first_plotted = False
        for rid in sub_routes:
            if rid not in geom_by_route:
                continue
            gdf = geom_by_route[rid]
            lw = 2.6 if gid in (3, 0) else 1.5
            alpha = 0.88 if gid in (3, 0) else 0.65
            ax_map.plot(
                gdf["stop_lon"].values,
                gdf["stop_lat"].values,
                color=meta["color"],
                linewidth=lw,
                alpha=alpha,
                label=meta["short_label"] if not first_plotted else None,
                zorder=3 + (4 if gid == 0 else gid),
            )
            first_plotted = True

            if rid in ("M15+", "M4", "M101", "M14A+", "M34+", "M79+", "M86+", "M22", "M50", "M98", "M35"):
                mid_idx = len(gdf) // 2
                ax_map.annotate(
                    rid,
                    (gdf["stop_lon"].iloc[mid_idx], gdf["stop_lat"].iloc[mid_idx]),
                    fontsize=7.0,
                    fontweight="bold",
                    color="#0f172a",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=meta["color"], alpha=0.82, lw=0.8),
                    zorder=10,
                )

    ax_map.set_title(
        "B. Manhattan Route Map Coloured by Group\n(40 Clustered Routes in 3 Groups + Outlier M35)",
        fontsize=10.0,
        fontweight="bold",
        pad=8,
    )
    ax_map.set_xlabel("Longitude", fontsize=9.0)
    ax_map.set_ylabel("Latitude", fontsize=9.0)
    ax_map.set_aspect(1.32)
    ax_map.grid(True, alpha=0.25)
    ax_map.legend(loc="upper left", fontsize=7.4)

    fig2.tight_layout()
    fig2.savefig(FIG_DIR / "m3_clustering_pca_and_map.png", dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print("Saved Step 4 PCA + Map figure to reports/figures/m3_clustering_pca_and_map.png", flush=True)

    # ==========================================================================
    # INTERACTIVE FOLIUM MAP: reports/figures/m3_route_clusters.html
    # ==========================================================================
    fmap = folium.Map(location=[40.783, -73.965], zoom_start=12, tiles="OpenStreetMap")

    fg_by_group = {}
    for gid in [1, 2, 3, 0]:
        meta = GROUP_METADATA_K3_PLUS_M35[gid]
        fg = folium.FeatureGroup(name=meta["group_label"], show=True)
        fg_by_group[gid] = fg
        fmap.add_child(fg)

    for _, r in assigned_df.iterrows():
        rid = str(r["route_id"])
        gid = int(r["group_id"])
        meta = GROUP_METADATA_K3_PLUS_M35[gid]
        if rid not in geom_by_route:
            continue
        gdf = geom_by_route[rid]
        coords = list(zip(gdf["stop_lat"].astype(float), gdf["stop_lon"].astype(float)))
        weekday_riders_est = np.expm1(float(r["weekday_riders_log"]))
        tooltip_html = (
            f"<b>Route {rid}</b> — {meta['group_label']}<br>"
            f"Weekday Riders (est.): {weekday_riders_est:,.0f}/day (log={r['weekday_riders_log']:.2f})<br>"
            f"Peak Riders / Service-Hr: {r['peak_riders_per_service_hour']:.1f}<br>"
            f"Route Length: {r['route_length_km']:.2f} km | Speed: {r['scheduled_speed_kmh']:.1f} km/h<br>"
            f"Weekend/Weekday Ratio: {r['weekend_to_weekday_ratio']:.2f} | Variability (CV): {r['demand_variability']:.3f}<br>"
            f"Exclusive Stops: {r['exclusive_stop_share']*100:.1f}% | DBSCAN (eps=1.80): {r['dbscan_eps180_label']}"
        )
        folium.PolyLine(
            locations=coords,
            color=meta["color"],
            weight=4.5 if gid in (3, 0) else 3.2,
            opacity=0.82,
            tooltip=folium.Tooltip(tooltip_html),
        ).add_to(fg_by_group[gid])

    folium.LayerControl(collapsed=False).add_to(fmap)
    html_path = FIG_DIR / "m3_route_clusters.html"
    fmap.save(str(html_path))
    print(f"Saved interactive cluster map to {html_path.relative_to(ROOT)}", flush=True)


def run_step4_clustering() -> None:
    print("=" * 88, flush=True)
    print("MILESTONE 3 — STEP 4: ROUTE CLUSTERING (OUTLIER REMOVAL, KMEANS k=2..6, DBSCAN & PROFILES)", flush=True)
    print("=" * 88, flush=True)

    scaled_df = pd.read_parquet(DATA_PROCESSED / "clustering_features.parquet")
    if "route" in scaled_df.columns:
        scaled_df = scaled_df.set_index("route")
    unscaled_df = pd.read_csv(TAB_DIR / "m2_clustering_features_unscaled.csv").set_index("route")
    unscaled_df = unscaled_df.loc[scaled_df.index]

    print(f"Loaded scaled clustering matrix: {scaled_df.shape[0]} routes x {scaled_df.shape[1]} features", flush=True)

    # 1. Check all 41 routes first (showing why M35 is removed as a 1-route outlier at every k=2..6),
    #    then run the official selection on the 40 routes excluding M35.
    ksel_41_df, _, _ = evaluate_kmeans_subset(scaled_df, subset_name="All 41 routes (with M35)")
    scaled_40_df = scaled_df.drop(index=["M35"])
    ksel_40_df, ref_labels_40, ref_models_40 = evaluate_kmeans_subset(
        scaled_40_df, subset_name="40 routes (excluding M35 outlier)"
    )

    ksel_combined = pd.concat([ksel_40_df, ksel_41_df], ignore_index=True)
    ksel_path = TAB_DIR / "m3_clustering_k_selection.csv"
    ksel_combined.to_csv(ksel_path, index=False)

    print("\n--- Official KMeans Evaluation & Stability Checks on 40 Routes (Excluding Outlier M35) ---", flush=True)
    print(ksel_40_df.to_string(index=False), flush=True)
    print("\n--- Reference Check on All 41 Routes (Showing M35 Singleton at Every k=2..6) ---", flush=True)
    print(ksel_41_df[["k", "silhouette_score", "cluster_sizes", "singletons", "ari_10starts_mean", "ari_loo_mean", "ari_1start_mean"]].to_string(index=False), flush=True)

    # Selected k = 3 on the 40 routes (plus M35 as group_id = 0 outlier)
    k3_labels_40 = ref_labels_40[3]
    k3_model_40 = ref_models_40[3]
    label_map_40 = dict(zip(scaled_40_df.index, k3_labels_40))
    assigned_groups_41 = np.array([0 if r == "M35" else label_map_40[r] for r in scaled_df.index], dtype=int)

    # 2. Evaluate DBSCAN (min_samples = 3) with sorted 3-NN distance plot
    dbscan_df, kdist_df, db_labels_180 = evaluate_dbscan_and_k_distance(
        scaled_df, assigned_groups_41, min_samples=3
    )
    dbscan_path = TAB_DIR / "m3_clustering_dbscan_summary.csv"
    kdist_path = TAB_DIR / "m3_clustering_k_distance.csv"
    dbscan_df.to_csv(dbscan_path, index=False)
    kdist_df.to_csv(kdist_path, index=False)
    print("\n--- DBSCAN Sensitivity & Elbow Summary (min_samples = 3) ---", flush=True)
    print(dbscan_df.to_string(index=False), flush=True)

    # 3. 2D PCA projection fitted on the 40 clustered routes (and projecting all 41 routes onto it)
    pca_40 = PCA(n_components=2, random_state=42)
    pca_40.fit(scaled_40_df[SELECTED_9_FEATURES].values)
    coords_40_proj = pca_40.transform(scaled_df[SELECTED_9_FEATURES].values)

    db_label_names = {}
    for c in sorted(set(db_labels_180)):
        if c == -1:
            db_label_names[c] = "Noise (-1)"
        else:
            cnt = int((db_labels_180 == c).sum())
            if cnt >= 14:
                db_label_names[c] = f"Core Cluster {c}: Longer Route Core (n={cnt})"
            elif cnt >= 8:
                db_label_names[c] = f"Core Cluster {c}: Short High-Density Core (n={cnt})"
            else:
                db_label_names[c] = f"Core Cluster {c}: Short Lower-Rider Core (n={cnt})"

    # 4. Build route-level assignment table for all 41 routes (3 KMeans groups on 40 routes + M35 outlier)
    kdist_lookup = kdist_df.set_index("route_id")["knn_3_distance"].to_dict()
    assigned_rows = []
    for idx, rid in enumerate(scaled_df.index):
        gid = int(assigned_groups_41[idx])
        meta = GROUP_METADATA_K3_PLUS_M35[gid]
        db_c = int(db_labels_180[idx])
        u_row = unscaled_df.loc[rid]
        assigned_rows.append({
            "route_id": rid,
            "group_id": gid,
            "group_label": meta["group_label"],
            "is_outlier_removed_before_kmeans": rid == "M35",
            "dbscan_eps180_cluster": db_c,
            "dbscan_eps180_label": db_label_names[db_c],
            "knn_3_distance": round(float(kdist_lookup[rid]), 4),
            "pc1_40": round(float(coords_40_proj[idx, 0]), 4),
            "pc2_40": round(float(coords_40_proj[idx, 1]), 4),
            "weekday_riders_est": round(float(np.expm1(u_row["weekday_riders_log"])), 1),
            **{col: round(float(u_row[col]), 4) for col in SELECTED_9_FEATURES},
        })

    # Sort order: Groups 1, 2, 3, then Outlier 0 (M35)
    assigned_df = pd.DataFrame(assigned_rows)
    assigned_df["sort_order"] = assigned_df["group_id"].replace({0: 99})
    assigned_df = assigned_df.sort_values(["sort_order", "route_id"]).drop(columns=["sort_order"]).reset_index(drop=True)
    assigned_path = TAB_DIR / "m3_route_clusters_assigned.csv"
    assigned_df.to_csv(assigned_path, index=False)
    print(f"\nSaved 41-route cluster assignments to {assigned_path.relative_to(ROOT)}", flush=True)

    # 5. Build unscaled feature median profiles per group (3 KMeans groups on 40 routes + M35 outlier + 40-route median)
    profile_rows = []
    for gid in [1, 2, 3, 0]:
        meta = GROUP_METADATA_K3_PLUS_M35[gid]
        sub = assigned_df[assigned_df["group_id"] == gid]
        routes_list = ", ".join(sub["route_id"].tolist())
        meds = {col: round(float(sub[col].median()), 4) for col in SELECTED_9_FEATURES}
        profile_rows.append({
            "group_id": gid,
            "group_label": meta["group_label"],
            "n_routes": int(len(sub)),
            "routes": routes_list,
            "weekday_riders_median_est": round(float(np.expm1(meds["weekday_riders_log"])), 0),
            **meds,
            "non_fitting_members": meta["non_fitting_members"],
            "plain_description": meta["plain_description"],
        })

    # Add 40-route clustered median row
    sub_40 = assigned_df[assigned_df["group_id"] > 0]
    net40_meds = {col: round(float(sub_40[col].median()), 4) for col in SELECTED_9_FEATURES}
    profile_rows.append({
        "group_id": -1,
        "group_label": "All 40 Clustered Routes (Excluding M35 — Median)",
        "n_routes": int(len(sub_40)),
        "routes": "40 routes (all except M35)",
        "weekday_riders_median_est": round(float(np.expm1(net40_meds["weekday_riders_log"])), 0),
        **net40_meds,
        "non_fitting_members": "None (summary row across the 40 clustered routes).",
        "plain_description": "Median across the 40 Manhattan routes included in KMeans clustering (Jan–May 2026 training baseline).",
    })

    profile_df = pd.DataFrame(profile_rows)
    profile_path = TAB_DIR / "m3_cluster_group_profiles_unscaled.csv"
    profile_df.to_csv(profile_path, index=False)
    print("\n--- KMeans (k=3 on 40 Routes) + M35 Outlier Profiles from Unscaled Feature Medians ---", flush=True)
    print(
        profile_df[
            [
                "group_id",
                "group_label",
                "n_routes",
                "weekday_riders_median_est",
                "weekday_riders_log",
                "weekend_to_weekday_ratio",
                "morning_peak_share",
                "night_share",
                "peak_riders_per_service_hour",
                "route_length_km",
                "scheduled_speed_kmh",
                "demand_variability",
                "exclusive_stop_share",
            ]
        ].to_string(index=False),
        flush=True,
    )

    joblib.dump(
        {
            "outlier_removed_before_clustering": "M35",
            "selected_k_on_40_routes": 3,
            "kmeans_k3_40routes": k3_model_40,
            "pca_2d_40routes": pca_40,
            "selected_features": SELECTED_9_FEATURES,
            "route_ids_40": scaled_40_df.index.tolist(),
            "kmeans_k3_canonical_labels_40": k3_labels_40,
            "dbscan_eps180_labels_41": db_labels_180,
            "group_metadata": GROUP_METADATA_K3_PLUS_M35,
        },
        MODELS_DIR / "route_clustering.joblib",
        compress=3,
    )
    print(f"Saved clustering model bundle to {MODELS_DIR / 'route_clustering.joblib'}", flush=True)

    geom_by_route = load_representative_route_geometries(scaled_df.index.tolist())
    build_clustering_figures_and_map(
        k_sel_40_df=ksel_40_df,
        kdist_df=kdist_df,
        assigned_df=assigned_df,
        pca_40=pca_40,
        geom_by_route=geom_by_route,
    )


if __name__ == "__main__":
    run_step4_clustering()
