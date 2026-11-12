"""
RouteRanker: Route Profiling & Unsupervised K-Means Clustering
Implements Technical Specification v3.8 Section 9:
- One row per eligible CTA bus route over documented development period (through 2026-05-31)
- Configurable eligibility gates: >=20 weekdays, >=8 Saturdays, >=8 Sundays/holidays
- Compact, interpretable candidate features in original units:
  * mean_weekday_rides
  * cv_weekday_rides (coefficient of variation)
  * sat_to_wkday_ratio
  * sun_to_wkday_ratio
- Robust Lloyd's K-Means with k-means++ seeding in pure NumPy (bypassing native OS DLL lockouts)
- Comprehensive cluster diagnostics: centroids in original units, sizes, stability, and human-interpretable group names.
"""

import os
import json
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
MODELS_DIR = os.path.join(BASE_DIR, "models")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

class PureKMeans:
    """Standard Lloyd's K-Means with k-means++ initialization."""
    def __init__(self, n_clusters=4, max_iter=300, random_state=42):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.random_state = random_state
        self.cluster_centers_ = None
        self.labels_ = None

    def fit(self, X):
        np.random.seed(self.random_state)
        n_samples, n_features = X.shape
        centers = [X[np.random.choice(n_samples)]]
        for _ in range(1, self.n_clusters):
            dists = np.min([np.sum((X - c)**2, axis=1) for c in centers], axis=0)
            probs = dists / (dists.sum() + 1e-10)
            next_idx = np.random.choice(n_samples, p=probs)
            centers.append(X[next_idx])
        self.cluster_centers_ = np.array(centers)

        for _ in range(self.max_iter):
            dists = np.array([np.sum((X - c)**2, axis=1) for c in self.cluster_centers_])
            labels = np.argmin(dists, axis=0)
            new_centers = np.array([
                X[labels == k].mean(axis=0) if np.sum(labels == k) > 0 else self.cluster_centers_[k]
                for k in range(self.n_clusters)
            ])
            if np.allclose(self.cluster_centers_, new_centers, atol=1e-5):
                break
            self.cluster_centers_ = new_centers
        self.labels_ = labels
        return self

    def predict(self, X):
        dists = np.array([np.sum((X - c)**2, axis=1) for c in self.cluster_centers_])
        return np.argmin(dists, axis=0)

def silhouette_score_numpy(X, labels):
    n = len(X)
    unique_labels = np.unique(labels)
    k = len(unique_labels)
    if k <= 1 or k >= n:
        return 0.0
    s_vals = []
    for i in range(n):
        same_c = (labels == labels[i])
        if np.sum(same_c) <= 1:
            s_vals.append(0.0)
            continue
        a_i = np.mean([np.linalg.norm(X[i] - X[j]) for j in range(n) if same_c[j] and j != i])
        b_i = np.min([
            np.mean([np.linalg.norm(X[i] - X[j]) for j in range(n) if labels[j] == other_c])
            for other_c in unique_labels if other_c != labels[i]
        ])
        s_vals.append((b_i - a_i) / max(a_i, b_i))
    return float(np.mean(s_vals))

class RouteClusteringService:
    def __init__(self, dev_cutoff="2026-05-31", min_weekday=20, min_sat=8, min_sun=8):
        self.dev_cutoff = dev_cutoff
        self.min_weekday = min_weekday
        self.min_sat = min_sat
        self.min_sun = min_sun
        self.artifact_path = os.path.join(MODELS_DIR, "cta_route_clusters_kmeans.joblib")
        self.profiles_path = os.path.join(PROCESSED_DIR, "route_clustering_profiles.csv")
        self._artifact = None

    def train_and_save(self, n_clusters=4):
        bus_csv = os.path.join(RAW_DIR, "cta_ridership_bus_routes_daily.csv")
        df = pd.read_csv(bus_csv)
        df["date_dt"] = pd.to_datetime(df["date"])
        
        # Development period cutoff
        dev_df = df[df["date_dt"] <= self.dev_cutoff]
        
        # Route names metadata from GTFS if available
        gtfs_routes_path = os.path.join(RAW_DIR, "gtfs", "routes.txt")
        route_names = {}
        if os.path.exists(gtfs_routes_path):
            r_df = pd.read_csv(gtfs_routes_path)
            for _, r in r_df.iterrows():
                route_names[str(r["route_id"])] = str(r.get("route_long_name", f"Route {r['route_id']}"))

        profiles = []
        ungrouped_routes = []

        for r, grp in dev_df.groupby("route"):
            r_str = str(r)
            wkday = grp[grp["daytype"] == "W"]["rides"]
            sat = grp[grp["daytype"] == "A"]["rides"]
            sun = grp[grp["daytype"] == "U"]["rides"]
            
            n_wk = len(wkday)
            n_sat = len(sat)
            n_sun = len(sun)
            
            if n_wk >= self.min_weekday and n_sat >= self.min_sat and n_sun >= self.min_sun:
                mean_wk = float(wkday.mean())
                cv_wk = float(wkday.std() / mean_wk) if mean_wk > 0 else 0.0
                sat_ratio = float(sat.mean() / mean_wk) if mean_wk > 0 else 0.0
                sun_ratio = float(sun.mean() / mean_wk) if mean_wk > 0 else 0.0
                
                profiles.append({
                    "route_id": r_str,
                    "route_name": route_names.get(r_str, f"Route {r_str}"),
                    "n_weekday": n_wk,
                    "n_sat": n_sat,
                    "n_sun": n_sun,
                    "mean_weekday_rides": round(mean_wk, 1),
                    "cv_weekday_rides": round(cv_wk, 4),
                    "sat_to_wkday_ratio": round(sat_ratio, 4),
                    "sun_to_wkday_ratio": round(sun_ratio, 4)
                })
            else:
                ungrouped_routes.append({
                    "route_id": r_str,
                    "route_name": route_names.get(r_str, f"Route {r_str}"),
                    "n_weekday": n_wk,
                    "n_sat": n_sat,
                    "n_sun": n_sun,
                    "reason": f"Insufficient observations (W={n_wk}/{self.min_weekday}, Sat={n_sat}/{self.min_sat}, Sun={n_sun}/{self.min_sun})"
                })

        pdf = pd.DataFrame(profiles)
        
        # Feature columns
        feat_cols = ["mean_weekday_rides", "cv_weekday_rides", "sat_to_wkday_ratio", "sun_to_wkday_ratio"]
        X = pdf[feat_cols].values
        
        # Robust Standardization
        means = X.mean(axis=0)
        stds = X.std(axis=0) + 1e-10
        X_scaled = (X - means) / stds

        # Train model
        model = PureKMeans(n_clusters=n_clusters, random_state=42).fit(X_scaled)
        pdf["cluster_id"] = model.labels_
        
        sil = silhouette_score_numpy(X_scaled, model.labels_)

        # Interpret centroids in original units
        cluster_summaries = {}
        cluster_names = {}
        for k in range(n_clusters):
            c_sub = pdf[pdf["cluster_id"] == k]
            avg_wk = float(c_sub["mean_weekday_rides"].mean())
            avg_cv = float(c_sub["cv_weekday_rides"].mean())
            avg_sat = float(c_sub["sat_to_wkday_ratio"].mean())
            avg_sun = float(c_sub["sun_to_wkday_ratio"].mean())
            
            # Meaningful human-interpretable cluster names
            if avg_wk > 12000:
                c_name = "Major High-Volume Trunk Arterial"
                c_desc = "Top-tier ridership corridors operating with dense all-day demand (e.g. 79th, Ashland, Chicago, Western)."
            elif avg_sat > 0.85 or avg_sun > 0.80:
                c_name = "Weekend-Resilient & Leisure Corridor"
                c_desc = "Corridors with elevated weekend-to-weekday retention, connecting commercial, lakefront, and community hubs."
            elif avg_cv > 0.35:
                c_name = "Peak-Commuter & Variable Feeder"
                c_desc = "Routes exhibiting high weekday day-to-day variance, serving concentrated rush-hour university or industrial trips."
            else:
                c_name = "Steady Community & Neighborhood Cross-Town"
                c_desc = "Stable moderate-volume neighborhood connectivity routes with consistent weekday baseline ridership."

            cluster_names[k] = c_name
            cluster_summaries[k] = {
                "cluster_id": k,
                "cluster_name": c_name,
                "description": c_desc,
                "route_count": len(c_sub),
                "mean_weekday_rides": round(avg_wk, 1),
                "mean_cv_weekday": round(avg_cv, 4),
                "mean_sat_ratio": round(avg_sat, 4),
                "mean_sun_ratio": round(avg_sun, 4),
                "sample_routes": c_sub["route_id"].tolist()[:6]
            }

        pdf["cluster_name"] = pdf["cluster_id"].map(cluster_names)
        pdf.to_csv(self.profiles_path, index=False)

        artifact = {
            "model_type": "PureKMeans_NumPy",
            "artifact_version": "3.8.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_clusters": n_clusters,
            "feature_columns": feat_cols,
            "feature_means": means.tolist(),
            "feature_stds": stds.tolist(),
            "cluster_centers_scaled": model.cluster_centers_.tolist(),
            "silhouette_score": round(sil, 4),
            "eligible_route_count": len(pdf),
            "ungrouped_route_count": len(ungrouped_routes),
            "cluster_summaries": cluster_summaries,
            "routes_membership": pdf[["route_id", "route_name", "cluster_id", "cluster_name", "mean_weekday_rides", "cv_weekday_rides", "sat_to_wkday_ratio", "sun_to_wkday_ratio"]].to_dict(orient="records"),
            "ungrouped_routes": ungrouped_routes
        }

        joblib.dump(artifact, self.artifact_path)
        self._artifact = artifact
        print(f"K-Means Route Clustering trained and saved to {self.artifact_path}. Silhouette={sil:.4f}")
        return artifact

    def get_cluster_data(self):
        if self._artifact is None:
            if os.path.exists(self.artifact_path):
                self._artifact = joblib.load(self.artifact_path)
            else:
                self._artifact = self.train_and_save(n_clusters=4)
        return self._artifact

route_clustering_service = RouteClusteringService()

if __name__ == "__main__":
    route_clustering_service.train_and_save(n_clusters=4)
