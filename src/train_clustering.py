"""
Milestone 3 — Step 4: Route Clustering (src/train_clustering.py)

Clusters the 41 Manhattan bus routes using the 9 scaled route features from
`data/processed/clustering_features.parquet` (fitted on Jan–May 2026 training data):
1. KMeans across k = 2..6 groups, recording:
   - Silhouette score and inertia
   - Stability Check 1: 20 random starts (n_init=1, random_state=0..19) pairwise Adjusted Rand Index (ARI),
     plus multi-start (n_init=10) pairwise ARI
   - Stability Check 2: Leave-one-route-out (LOO, 41 runs of 40 routes) Adjusted Rand Index (ARI)
     against the full 41-route clustering
2. Selects k = 4 using both stability checks and silhouette score:
   - Explains why k = 2 (40 vs 1 split on M35) has poor 20-start seed stability (ARI = 0.2804)
     and fails to separate the 40 main routes
   - Shows that k = 4 achieves the highest 20-random-start stability (ARI = 0.7513 at n_init=1,
     0.9543 at n_init=10), strong leave-one-route-out stability (ARI = 0.9370), higher silhouette
     than k = 3 (0.2617 vs 0.2489), and 4 operationally distinct route groups
3. DBSCAN (min_samples = 3) with eps chosen from the sorted 3-nearest-neighbor k-distance plot
   (elbow at eps = 1.80) and sensitivity evaluated across eps = 1.20..2.50
4. Plain-language group profiles from the unscaled feature medians (`m2_clustering_features_unscaled.csv`)
5. Visualizations:
   - `reports/figures/m3_clustering_evaluation.png` (KMeans silhouette + stability checks & DBSCAN k-distance plot)
   - `reports/figures/m3_clustering_pca_and_map.png` (2D PCA scatter plot + static Manhattan route map by group)
   - `reports/figures/m3_route_clusters.html` (interactive Folium map coloured by KMeans group)
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

GROUP_METADATA_K4 = {
    1: {
        "group_id": 1,
        "group_label": "Group 1: Long North–South Avenue Trunks",
        "short_label": "Group 1: N–S Avenue Trunks (n=18)",
        "color": "#1d4ed8",
        "marker": "o",
        "plain_description": (
            "Long north–south avenue trunk routes (median 12.58 km, scheduled speed 10.0 km/h) with high "
            "weekday demand (~7,018 riders/day, log=8.86), the strongest weekend retention (0.75 of weekday "
            "riders) and late-night share (13.7%), moderate peak load per service-hour (32.4 riders/service-hr), "
            "low day-to-day volatility (demand_variability=0.175), and the lowest exclusive-stop share (0.447, "
            "or 44.7%) because multiple trunk routes share major avenue corridors."
        ),
    },
    2: {
        "group_id": 2,
        "group_label": "Group 2: High-Load Crosstown & SBS Corridors",
        "short_label": "Group 2: Crosstown & SBS (n=15)",
        "color": "#059669",
        "marker": "s",
        "plain_description": (
            "Short, dense crosstown and Select Bus Service corridors (median 4.24 km) carrying high "
            "weekday volume (~6,871 riders/day, log=8.84) and the highest peak load in the network "
            "(median 65.8 riders/service-hr, double Group 1), with the steadiest weekday demand "
            "(demand_variability=0.163), moderate weekend retention (0.54), slow cross-street scheduled "
            "speed (9.7 km/h), and 0.500 (50.0%) exclusive-stop share."
        ),
    },
    3: {
        "group_id": 3,
        "group_label": "Group 3: Lower-Volume Local & Peak-Oriented Feeders",
        "short_label": "Group 3: Local & Peak Feeders (n=7)",
        "color": "#d97706",
        "marker": "^",
        "plain_description": (
            "Shorter, lower-volume local and commuter-oriented routes (median 4.06 km, ~1,431 weekday "
            "riders/day, log=7.27, speed 9.8 km/h) with the sharpest morning peak concentration (34.7% of "
            "daily riders in 07:00–09:59), the lowest night share (7.6%) and weekend ratio (0.47), higher "
            "day-to-day variability (demand_variability=0.276), and a high share of stops served by no "
            "other route (0.691, or 69.1%)."
        ),
    },
    4: {
        "group_id": 4,
        "group_label": "Group 4: Isolated Special-Purpose Route (M35)",
        "short_label": "Group 4: Special-Purpose M35 (n=1)",
        "color": "#dc2626",
        "marker": "D",
        "plain_description": (
            "Single outlier route (M35 to Randall's Island, 4.95 km) with the lowest weekday ridership "
            "(~146 riders/day in Jan–May, log=4.99), weekend demand exceeding weekday demand (ratio=1.67), "
            "the lowest peak riders per service-hour (4.42), the fastest scheduled bridge/island speed "
            "(21.7 km/h), the highest demand volatility (demand_variability=0.847), and 1.000 (100.0%) "
            "exclusive stops."
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
    # Sort by count descending, then median weekday_riders_log descending
    order_info.sort(key=lambda item: (-item[1], -item[2]))
    mapping = {old_c: new_idx + 1 for new_idx, (old_c, _, _) in enumerate(order_info)}
    return np.array([mapping[c] for c in labels], dtype=int)


def evaluate_kmeans_k2_to_k6(X_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[int, np.ndarray], Dict[int, KMeans]]:
    """
    Evaluate KMeans for k in {2, 3, 4, 5, 6}:
    - Silhouette score and inertia on the reference fit (n_init=50, random_state=42)
    - Stability Check 1: 20 random starts (n_init=1, random_state=0..19) pairwise Adjusted Rand Index,
      plus 20 random starts with n_init=10 pairwise ARI
    - Stability Check 2: Leave-one-route-out (LOO, 41 runs of 40 routes) Adjusted Rand Index
      against the full 41-route reference clustering
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

        # Cluster size string (sorted descending)
        _, counts = np.unique(labels_ref, return_counts=True)
        sizes_str = ", ".join(str(int(c)) for c in sorted(counts, reverse=True))

        # Stability Check 1A: 20 single-seed random starts (n_init=1, random_state=0..19)
        runs_1 = [
            KMeans(n_clusters=k, n_init=1, random_state=seed).fit_predict(X)
            for seed in range(20)
        ]
        pairwise_1 = [
            adjusted_rand_score(runs_1[i], runs_1[j])
            for i, j in combinations(range(20), 2)
        ]
        vs_ref_1 = [adjusted_rand_score(labels_ref, r) for r in runs_1]

        # Stability Check 1B: 20 multi-start runs (n_init=10, random_state=0..19)
        runs_10 = [
            KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(X)
            for seed in range(20)
        ]
        pairwise_10 = [
            adjusted_rand_score(runs_10[i], runs_10[j])
            for i, j in combinations(range(20), 2)
        ]

        # Stability Check 2: Leave-one-route-out (41 runs, each dropping 1 route)
        loo_aris = []
        for drop_idx in range(n_routes):
            mask = np.ones(n_routes, dtype=bool)
            mask[drop_idx] = False
            km_loo = KMeans(n_clusters=k, n_init=20, random_state=42)
            labels_loo = km_loo.fit_predict(X[mask])
            loo_aris.append(adjusted_rand_score(labels_ref[mask], labels_loo))

        selection_note = {
            2: "Isolates M35 only (40 vs 1); highest silhouette (0.618) but lowest 20-start ARI (0.280)",
            3: "Splits 40 routes into 2 broad groups + M35; lowest silhouette (0.249)",
            4: "Selected k=4: highest 20-start ARI (0.751), high LOO ARI (0.937), higher silhouette (0.262), 4 clear groups",
            5: "20-start stability drops sharply (ARI = 0.545) as crosstown/trunk boundary fragments",
            6: "Over-segmented (two singletons M35 & M98); LOO ARI drops to 0.891",
        }[k]

        rows.append({
            "k": k,
            "silhouette_score": round(sil, 4),
            "inertia": round(inertia, 2),
            "cluster_sizes": sizes_str,
            "ari_20starts_mean": round(float(np.mean(pairwise_1)), 4),
            "ari_20starts_std": round(float(np.std(pairwise_1)), 4),
            "ari_20starts_min": round(float(np.min(pairwise_1)), 4),
            "ari_20starts_vs_ref_mean": round(float(np.mean(vs_ref_1)), 4),
            "ari_20starts_ninit10_mean": round(float(np.mean(pairwise_10)), 4),
            "ari_loo_mean": round(float(np.mean(loo_aris)), 4),
            "ari_loo_std": round(float(np.std(loo_aris)), 4),
            "ari_loo_min": round(float(np.min(loo_aris)), 4),
            "is_selected_k": k == 4,
            "selection_note": selection_note,
        })

    return pd.DataFrame(rows), ref_labels_by_k, ref_models_by_k


def evaluate_dbscan_and_k_distance(
    X_df: pd.DataFrame,
    kmeans_k4_labels: np.ndarray,
    min_samples: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """
    Compute sorted 3-nearest-neighbor distances for DBSCAN (min_samples=3) and evaluate
    DBSCAN across eps in [1.20, 1.50, 1.80, 2.00, 2.20, 2.50], with eps=1.80 as the elbow.
    """
    X = X_df[SELECTED_9_FEATURES].values
    routes = X_df.index.tolist()

    nn = NearestNeighbors(n_neighbors=min_samples)
    nn.fit(X)
    dists, indices = nn.kneighbors(X)
    # dists[:, 0] is 0.0 (self); dists[:, min_samples - 1] is distance to the (min_samples-1)-th other neighbor
    k_dist = dists[:, min_samples - 1]
    nearest_other_route = [routes[idx] for idx in indices[:, 1]]
    kth_neighbor_route = [routes[idx] for idx in indices[:, min_samples - 1]]

    kdist_df = pd.DataFrame({
        "route_id": routes,
        "knn_3_distance": np.round(k_dist, 4),
        "nearest_neighbor_route": nearest_other_route,
        "third_nn_route": kth_neighbor_route,
        "kmeans_k4_group": kmeans_k4_labels,
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
            ari_nn = round(float(adjusted_rand_score(kmeans_k4_labels[non_noise], lbl[non_noise])), 4)
        else:
            ari_nn = np.nan

        cluster_counts = [int((lbl == c).sum()) for c in sorted(set(lbl)) if c != -1]
        sizes_str = ", ".join(str(c) for c in sorted(cluster_counts, reverse=True)) if cluster_counts else "none"
        noise_routes = [routes[i] for i in range(len(routes)) if lbl[i] == -1]

        role_note = {
            1.20: "Too tight: 35/41 routes (85.4%) flagged as noise; only 2 tiny 3-route cores survive",
            1.50: "Tight: 18/41 routes (43.9%) flagged as noise; 3 dense cores (sizes 9, 9, 5)",
            1.80: "Selected k-distance elbow (eps=1.80): 3 clusters (16 N–S, 10 crosstown, 3 feeders) + 12 noise routes (29.3%)",
            2.00: "Loose: N–S and crosstown cores merge into one 27-route super-cluster (+ 4-route group); 10 noise routes (24.4%)",
            2.20: "Very loose: 32 routes merge into 1 cluster + 3-route group; 6 outliers (14.6%) remain noise",
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
            "ari_vs_kmeans_k4_non_noise": ari_nn,
            "noise_routes": ", ".join(noise_routes),
            "interpretation": role_note,
        })

    return pd.DataFrame(db_rows), kdist_df, labels_at_180


def load_representative_route_geometries(route_ids: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Extract representative stop-coordinate sequences for each of the 41 Manhattan routes
    from the primary GTFS feed (2026-04-09/original.zip) so we can plot geographic route maps coloured by cluster.
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

    # Pick the trip with the most stops per route_id
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
    k_sel_df: pd.DataFrame,
    kdist_df: pd.DataFrame,
    assigned_df: pd.DataFrame,
    pca: PCA,
    geom_by_route: Dict[str, pd.DataFrame],
) -> None:
    """
    Generate:
    1. `reports/figures/m3_clustering_evaluation.png` (KMeans silhouette/stability & DBSCAN k-distance curve)
    2. `reports/figures/m3_clustering_pca_and_map.png` (2D PCA scatter plot & Manhattan geographic map coloured by group)
    3. `reports/figures/m3_route_clusters.html` (Interactive Folium map coloured by KMeans group)
    """
    # ==========================================================================
    # FIGURE 1: KMEANS SELECTION (SILHOUETTE + STABILITY) & DBSCAN K-DISTANCE
    # ==========================================================================
    fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2), dpi=150)

    ks = k_sel_df["k"].values
    ax1.plot(ks, k_sel_df["ari_20starts_mean"], marker="o", linewidth=2.2, color="#1d4ed8", label="20 Random Starts ARI (n_init=1)")
    ax1.plot(ks, k_sel_df["ari_loo_mean"], marker="s", linewidth=2.2, color="#059669", linestyle="--", label="Leave-One-Route-Out ARI (41 runs)")
    ax1.plot(ks, k_sel_df["silhouette_score"], marker="^", linewidth=2.2, color="#d97706", linestyle="-.", label="Silhouette Score")
    ax1.axvline(4, color="#dc2626", linestyle=":", linewidth=1.6, label="Selected k = 4 (Highest 20-Start ARI = 0.751)")

    for _, row in k_sel_df.iterrows():
        k_val = int(row["k"])
        ax1.annotate(
            f"{row['ari_20starts_mean']:.3f}",
            (k_val, row["ari_20starts_mean"]),
            textcoords="offset points",
            xytext=(0, 7),
            ha="center",
            fontsize=7.8,
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

    ax1.set_title("A. KMeans Number of Groups (k = 2..6): Silhouette & Stability", fontsize=10.5, fontweight="bold", pad=8)
    ax1.set_xlabel("Number of Clusters (k)", fontsize=9.5)
    ax1.set_ylabel("Score / Adjusted Rand Index (ARI)", fontsize=9.5)
    ax1.set_xticks(ks)
    ax1.set_ylim(0.06, 1.06)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="lower right", fontsize=7.8)

    # Panel B: Sorted 3-NN distance plot for DBSCAN (min_samples = 3)
    ranks = kdist_df["sorted_rank"].values
    dists = kdist_df["knn_3_distance"].values
    ax2.plot(ranks, dists, marker="o", markersize=4.5, linewidth=1.8, color="#1e293b", label="Sorted 3-NN Distance (min_samples=3)")
    ax2.axhline(1.80, color="#dc2626", linestyle="--", linewidth=1.6, label="Chosen Elbow eps = 1.80 (29 routes in 3 clusters, 12 noise)")
    ax2.axhline(1.50, color="#94a3b8", linestyle=":", linewidth=1.2, label="Tighter eps = 1.50 (18/41 noise = 43.9%)")

    # Annotate key outlier routes on the k-distance curve without overlapping
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

    ax2.set_title("B. Sorted 3-Nearest-Neighbor Distance Plot for DBSCAN", fontsize=10.5, fontweight="bold", pad=8)
    ax2.set_xlabel("Routes Sorted by 3rd-Nearest-Neighbor Distance (Rank 1..41)", fontsize=9.5)
    ax2.set_ylabel("Euclidean Distance in 9-Feature Scaled Space", fontsize=9.5)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper left", fontsize=8.0)

    fig1.tight_layout()
    fig1.savefig(FIG_DIR / "m3_clustering_evaluation.png", dpi=150, bbox_inches="tight")
    plt.close(fig1)
    print("Saved Step 4 evaluation figure to reports/figures/m3_clustering_evaluation.png", flush=True)

    # ==========================================================================
    # FIGURE 2: PCA SCATTER PLOT & STATIC GEOGRAPHIC MAP COLOURED BY GROUP
    # ==========================================================================
    fig2, (ax_pca, ax_map) = plt.subplots(
        1, 2, figsize=(14.2, 6.6), dpi=150, gridspec_kw={"width_ratios": [1.18, 1.0]}
    )

    var_pc1 = pca.explained_variance_ratio_[0] * 100.0
    var_pc2 = pca.explained_variance_ratio_[1] * 100.0

    for gid in [1, 2, 3, 4]:
        meta = GROUP_METADATA_K4[gid]
        sub = assigned_df[assigned_df["group_id"] == gid]
        ax_pca.scatter(
            sub["pc1"],
            sub["pc2"],
            c=meta["color"],
            marker=meta["marker"],
            s=72,
            alpha=0.9,
            edgecolors="#0f172a",
            linewidths=0.8,
            label=meta["short_label"],
            zorder=4,
        )
        # Highlight DBSCAN noise routes with a subtle outer ring
        sub_noise = sub[sub["dbscan_eps180_cluster"] == -1]
        if len(sub_noise) > 0:
            ax_pca.scatter(
                sub_noise["pc1"],
                sub_noise["pc2"],
                facecolors="none",
                edgecolors="#dc2626",
                s=135,
                linewidths=1.1,
                linestyle="--",
                zorder=3,
            )

    # Label all 41 routes on the PCA scatter plot
    for idx_r, r in assigned_df.iterrows():
        dx = 5
        dy = 4 if (idx_r % 2 == 0) else -9
        if r["route_id"] == "M35":
            dx, dy = -26, -12
        ax_pca.annotate(
            r["route_id"],
            (r["pc1"], r["pc2"]),
            textcoords="offset points",
            xytext=(dx, dy),
            fontsize=7.2,
            fontweight="bold",
            color=GROUP_METADATA_K4[int(r["group_id"])]["color"],
        )

    # Dummy entry for DBSCAN noise ring in legend
    ax_pca.scatter(
        [], [], facecolors="none", edgecolors="#dc2626", s=110, linewidths=1.1,
        linestyle="--", label="DBSCAN Noise @ eps=1.80 (n=12)"
    )

    ax_pca.axhline(0, color="#cbd5e1", linewidth=0.9, zorder=1)
    ax_pca.axvline(0, color="#cbd5e1", linewidth=0.9, zorder=1)
    ax_pca.set_title(
        f"A. PCA Scatter Plot of 41 Routes Coloured by KMeans Group\n"
        f"(PC1 = {var_pc1:.1f}%, PC2 = {var_pc2:.1f}%, Total = {var_pc1 + var_pc2:.1f}% Variance)",
        fontsize=10.2,
        fontweight="bold",
        pad=8,
    )
    ax_pca.set_xlabel(f"Principal Component 1 ({var_pc1:.1f}% Variance — Scale, Weekend & Night Activity vs Exclusivity)", fontsize=9.0)
    ax_pca.set_ylabel(f"Principal Component 2 ({var_pc2:.1f}% Variance — Speed & Volatility vs Peak Load Density)", fontsize=9.0)
    ax_pca.grid(True, alpha=0.25)
    ax_pca.legend(loc="upper left", fontsize=7.8)

    # Panel B: Static Geographic Map of Manhattan Bus Routes Coloured by Group
    for gid in [1, 2, 3, 4]:
        meta = GROUP_METADATA_K4[gid]
        sub_routes = assigned_df[assigned_df["group_id"] == gid]["route_id"].tolist()
        first_plotted = False
        for rid in sub_routes:
            if rid not in geom_by_route:
                continue
            gdf = geom_by_route[rid]
            lw = 2.6 if gid in (3, 4) else 1.5
            alpha = 0.88 if gid in (3, 4) else 0.65
            ax_map.plot(
                gdf["stop_lon"].values,
                gdf["stop_lat"].values,
                color=meta["color"],
                linewidth=lw,
                alpha=alpha,
                label=meta["short_label"] if not first_plotted else None,
                zorder=2 + gid,
            )
            first_plotted = True

            # Label representative routes on the map for clarity
            if rid in ("M15+", "M4", "M101", "M14A+", "M34+", "M79+", "M86+", "M22", "M50", "M98", "M35"):
                mid_idx = len(gdf) // 2
                ax_map.annotate(
                    rid,
                    (gdf["stop_lon"].iloc[mid_idx], gdf["stop_lat"].iloc[mid_idx]),
                    fontsize=7.0,
                    fontweight="bold",
                    color="#0f172a",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=meta["color"], alpha=0.8, lw=0.8),
                    zorder=10,
                )

    ax_map.set_title(
        "B. Manhattan Route Map Coloured by Group\n(41 Routes from GTFS Stop Sequences)",
        fontsize=10.2,
        fontweight="bold",
        pad=8,
    )
    ax_map.set_xlabel("Longitude", fontsize=9.0)
    ax_map.set_ylabel("Latitude", fontsize=9.0)
    ax_map.set_aspect(1.32)
    ax_map.grid(True, alpha=0.25)
    ax_map.legend(loc="upper left", fontsize=7.6)

    fig2.tight_layout()
    fig2.savefig(FIG_DIR / "m3_clustering_pca_and_map.png", dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print("Saved Step 4 PCA + Map figure to reports/figures/m3_clustering_pca_and_map.png", flush=True)

    # ==========================================================================
    # INTERACTIVE FOLIUM MAP: reports/figures/m3_route_clusters.html
    # ==========================================================================
    fmap = folium.Map(location=[40.783, -73.965], zoom_start=12, tiles="OpenStreetMap")

    fg_by_group = {}
    for gid in [1, 2, 3, 4]:
        meta = GROUP_METADATA_K4[gid]
        fg = folium.FeatureGroup(name=meta["group_label"], show=True)
        fg_by_group[gid] = fg
        fmap.add_child(fg)

    for _, r in assigned_df.iterrows():
        rid = str(r["route_id"])
        gid = int(r["group_id"])
        meta = GROUP_METADATA_K4[gid]
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
            f"Weekend/Weekday Ratio: {r['weekend_to_weekday_ratio']:.2f} | Exclusive Stops: {r['exclusive_stop_share']*100:.1f}%<br>"
            f"DBSCAN (eps=1.80): {r['dbscan_eps180_label']}"
        )
        folium.PolyLine(
            locations=coords,
            color=meta["color"],
            weight=4.5 if gid in (3, 4) else 3.2,
            opacity=0.82,
            tooltip=folium.Tooltip(tooltip_html),
        ).add_to(fg_by_group[gid])

    folium.LayerControl(collapsed=False).add_to(fmap)
    html_path = FIG_DIR / "m3_route_clusters.html"
    fmap.save(str(html_path))
    print(f"Saved interactive cluster map to {html_path.relative_to(ROOT)}", flush=True)


def run_step4_clustering() -> None:
    print("=" * 88, flush=True)
    print("MILESTONE 3 — STEP 4: ROUTE CLUSTERING (KMEANS, STABILITY, DBSCAN, PROFILES & MAPS)", flush=True)
    print("=" * 88, flush=True)

    scaled_df = pd.read_parquet(DATA_PROCESSED / "clustering_features.parquet")
    if "route" in scaled_df.columns:
        scaled_df = scaled_df.set_index("route")
    unscaled_df = pd.read_csv(TAB_DIR / "m2_clustering_features_unscaled.csv").set_index("route")
    unscaled_df = unscaled_df.loc[scaled_df.index]

    print(f"Loaded scaled clustering matrix: {scaled_df.shape[0]} routes x {scaled_df.shape[1]} features", flush=True)

    # 1. Evaluate KMeans across k = 2..6 with both stability checks
    k_sel_df, ref_labels_by_k, ref_models_by_k = evaluate_kmeans_k2_to_k6(scaled_df)
    ksel_path = TAB_DIR / "m3_clustering_k_selection.csv"
    k_sel_df.to_csv(ksel_path, index=False)
    print("\n--- KMeans Evaluation & Stability Checks (k = 2..6) ---", flush=True)
    print(k_sel_df.to_string(index=False), flush=True)

    # Chosen k = 4
    k4_labels = ref_labels_by_k[4]
    k4_model = ref_models_by_k[4]

    # 2. Evaluate DBSCAN (min_samples = 3) with sorted k-distance plot
    dbscan_df, kdist_df, db_labels_180 = evaluate_dbscan_and_k_distance(
        scaled_df, k4_labels, min_samples=3
    )
    dbscan_path = TAB_DIR / "m3_clustering_dbscan_summary.csv"
    kdist_path = TAB_DIR / "m3_clustering_k_distance.csv"
    dbscan_df.to_csv(dbscan_path, index=False)
    kdist_df.to_csv(kdist_path, index=False)
    print("\n--- DBSCAN Sensitivity & Elbow Summary (min_samples = 3) ---", flush=True)
    print(dbscan_df.to_string(index=False), flush=True)

    # 3. 2D PCA projection on the 9 scaled features
    pca = PCA(n_components=2, random_state=42)
    coords_2d = pca.fit_transform(scaled_df[SELECTED_9_FEATURES].values)

    # Map DBSCAN eps=1.80 cluster labels to descriptive text
    # Determine which DBSCAN cluster corresponds to N-S trunks, Crosstown, or Feeders
    db_label_names = {}
    for c in sorted(set(db_labels_180)):
        if c == -1:
            db_label_names[c] = "Noise (-1)"
        else:
            cnt = int((db_labels_180 == c).sum())
            if cnt >= 14:
                db_label_names[c] = f"Core Cluster {c}: N–S Avenue Core (n={cnt})"
            elif cnt >= 8:
                db_label_names[c] = f"Core Cluster {c}: Crosstown/SBS Core (n={cnt})"
            else:
                db_label_names[c] = f"Core Cluster {c}: Lower-Manhattan Feeders (n={cnt})"

    # 4. Build route-level assignment table combining KMeans (k=4), DBSCAN (eps=1.80), PCA, and unscaled features
    kdist_lookup = kdist_df.set_index("route_id")["knn_3_distance"].to_dict()
    assigned_rows = []
    for idx, rid in enumerate(scaled_df.index):
        gid = int(k4_labels[idx])
        meta = GROUP_METADATA_K4[gid]
        db_c = int(db_labels_180[idx])
        u_row = unscaled_df.loc[rid]
        assigned_rows.append({
            "route_id": rid,
            "group_id": gid,
            "group_label": meta["group_label"],
            "dbscan_eps180_cluster": db_c,
            "dbscan_eps180_label": db_label_names[db_c],
            "knn_3_distance": round(float(kdist_lookup[rid]), 4),
            "pc1": round(float(coords_2d[idx, 0]), 4),
            "pc2": round(float(coords_2d[idx, 1]), 4),
            "weekday_riders_est": round(float(np.expm1(u_row["weekday_riders_log"])), 1),
            **{col: round(float(u_row[col]), 4) for col in SELECTED_9_FEATURES},
        })

    assigned_df = pd.DataFrame(assigned_rows).sort_values(["group_id", "route_id"]).reset_index(drop=True)
    assigned_path = TAB_DIR / "m3_route_clusters_assigned.csv"
    assigned_df.to_csv(assigned_path, index=False)
    print(f"\nSaved 41-route cluster assignments to {assigned_path.relative_to(ROOT)}", flush=True)

    # 5. Build unscaled feature median profiles per KMeans group (k = 4) + All-41 network median
    profile_rows = []
    for gid in [1, 2, 3, 4]:
        meta = GROUP_METADATA_K4[gid]
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
            "plain_description": meta["plain_description"],
        })

    # Network-wide median row across all 41 routes for comparison
    net_meds = {col: round(float(assigned_df[col].median()), 4) for col in SELECTED_9_FEATURES}
    profile_rows.append({
        "group_id": 0,
        "group_label": "All 41 Manhattan Routes (Network Median)",
        "n_routes": int(len(assigned_df)),
        "routes": "All 41 routes",
        "weekday_riders_median_est": round(float(np.expm1(net_meds["weekday_riders_log"])), 0),
        **net_meds,
        "plain_description": "Network-wide median across all 41 Manhattan bus routes (Jan–May 2026 training baseline).",
    })

    profile_df = pd.DataFrame(profile_rows)
    profile_path = TAB_DIR / "m3_cluster_group_profiles_unscaled.csv"
    profile_df.to_csv(profile_path, index=False)
    print("\n--- KMeans (k=4) Group Profiles from Unscaled Feature Medians ---", flush=True)
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

    # Save clustering bundle to models/route_clustering.joblib
    joblib.dump(
        {
            "selected_k": 4,
            "kmeans_k4": k4_model,
            "pca_2d": pca,
            "selected_features": SELECTED_9_FEATURES,
            "route_ids": scaled_df.index.tolist(),
            "kmeans_k4_canonical_labels": k4_labels,
            "dbscan_eps180_labels": db_labels_180,
            "group_metadata": GROUP_METADATA_K4,
        },
        MODELS_DIR / "route_clustering.joblib",
        compress=3,
    )
    print(f"Saved clustering model bundle to {MODELS_DIR / 'route_clustering.joblib'}", flush=True)

    # 6. Build figures and interactive map
    geom_by_route = load_representative_route_geometries(scaled_df.index.tolist())
    build_clustering_figures_and_map(
        k_sel_df=k_sel_df,
        kdist_df=kdist_df,
        assigned_df=assigned_df,
        pca=pca,
        geom_by_route=geom_by_route,
    )


if __name__ == "__main__":
    run_step4_clustering()
