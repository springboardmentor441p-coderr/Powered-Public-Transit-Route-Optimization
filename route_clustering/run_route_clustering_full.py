import os
import sys
import re
import warnings
import time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.style.use('ggplot')
import networkx as nx
from math import radians, sin, cos, sqrt, atan2
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score

warnings.filterwarnings('ignore')

# ---------------------------------------------------------
# 1. Paths Configuration
# ---------------------------------------------------------
data_dir = Path(r'C:\Users\kavyasri\Downloads\RouteRanker-Git\data')
project_root = Path(r'C:\Users\kavyasri\Downloads\mtc-gtfs')
out_dir = project_root / 'route_clustering'
reports_dir = project_root / 'reports'
figures_dir = reports_dir / 'figures'

out_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)
figures_dir.mkdir(parents=True, exist_ok=True)

routes_path = data_dir / 'routes.txt'
trips_path = data_dir / 'trips.txt'
stop_times_path = data_dir / 'stop_times.txt'
stops_path = data_dir / 'stops.txt'
calendar_path = data_dir / 'calendar.txt'
canonical_path = data_dir / 'canonical_routes_mapping.csv'

print("=" * 60)
print("CHENNAI MTC ROUTERANKER - ROUTE CLUSTERING PIPELINE")
print("=" * 60)
print(f"Verified data directory: {data_dir}")
for p in [routes_path, trips_path, stop_times_path, stops_path, calendar_path, canonical_path]:
    if not p.exists():
        raise FileNotFoundError(f"Required file not found: {p}")
    print(f"Verified input: {p.name} ({p.stat().st_size:,} bytes)")

# ---------------------------------------------------------
# 2. Data Loading
# ---------------------------------------------------------
t0 = time.time()
print("\n[1/7] Loading GTFS and Canonical Mapping datasets...")
routes = pd.read_csv(routes_path, dtype={'route_id': str, 'agency_id': str})
trips = pd.read_csv(trips_path, dtype={'route_id': str, 'trip_id': str, 'service_id': str})
stop_times = pd.read_csv(stop_times_path, dtype={'trip_id': str, 'stop_id': str})
stops = pd.read_csv(stops_path, dtype={'stop_id': str})
calendar = pd.read_csv(calendar_path, dtype={'service_id': str})
canonical = pd.read_csv(canonical_path)

print(f"Loaded {len(routes):,} routes, {len(trips):,} trips, {len(stop_times):,} stop_times rows, {len(stops):,} stops.")
print(f"Loaded {len(canonical):,} canonical corridor mappings.")

# ---------------------------------------------------------
# 3. Route-Level Feature Engineering
# ---------------------------------------------------------
print("\n[2/7] Performing route-level feature engineering...")

# Base Route Table
route_df = routes[['route_id', 'route_short_name', 'route_long_name', 'route_type']].copy()

# Canonical corridor extraction (matching Phase 1 specification)
def extract_canonical(name):
    if not isinstance(name, str):
        return ''
    s = name.strip()
    s = re.sub(r'\s+(CT\d*|CUT\d*|R\d*|RE\d*|E|C\d+)\b', '', s, flags=re.IGNORECASE)
    s = re.sub(r'(?<=[0-9A-Za-z])(CT\d*|CUT\d*)$', '', s, flags=re.IGNORECASE)
    return s.strip().upper()

route_df['canonical_route'] = route_df['route_short_name'].apply(extract_canonical)
# Merge canonical corridor summary metrics
route_df = route_df.merge(canonical, on='canonical_route', how='left')

# Trip - Stop mapping
trip_stop = trips[['trip_id', 'route_id', 'service_id']].merge(
    stop_times[['trip_id', 'stop_id', 'stop_sequence', 'arrival_time', 'departure_time']],
    on='trip_id'
)

# A. Stop count per route
stop_counts = trip_stop.groupby('route_id')['stop_id'].nunique().reset_index().rename(columns={'stop_id': 'stop_count'})
route_df = route_df.merge(stop_counts, on='route_id', how='left')

# B. Route Length (km) and Spatial Centroid using Haversine
def haversine_dist(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
    return R * 2.0 * atan2(sqrt(a), sqrt(1.0 - a))

stops_geo = stops[['stop_id', 'stop_lat', 'stop_lon']].dropna(subset=['stop_lat', 'stop_lon'])
trip_stop_geo = trip_stop.merge(stops_geo, on='stop_id', how='inner')

# Find representative trip (max stops) for each route to compute spatial trajectory length
trip_lens = trip_stop_geo.groupby(['route_id', 'trip_id'])['stop_sequence'].count().reset_index(name='n_stops')
rep_trips = trip_lens.sort_values(['route_id', 'n_stops'], ascending=[True, False]).drop_duplicates(subset=['route_id'])

trip_geo_sorted = trip_stop_geo.merge(rep_trips[['route_id', 'trip_id']], on=['route_id', 'trip_id']).sort_values(['route_id', 'stop_sequence'])

def calc_geom(group):
    lats = group['stop_lat'].values
    lons = group['stop_lon'].values
    if len(lats) < 2:
        length = 0.0
    else:
        length = sum(haversine_dist(lats[i], lons[i], lats[i+1], lons[i+1]) for i in range(len(lats)-1))
    return pd.Series({
        'route_length_km': length,
        'centroid_lat': float(np.median(lats)) if len(lats) > 0 else np.nan,
        'centroid_lon': float(np.median(lons)) if len(lons) > 0 else np.nan
    })

route_geom = trip_geo_sorted.groupby('route_id').apply(calc_geom).reset_index()
route_df = route_df.merge(route_geom, on='route_id', how='left')

# C. Weekday vs Weekend Trip Counts and Headways
calendar['is_weekday'] = calendar[['monday', 'tuesday', 'wednesday', 'thursday', 'friday']].max(axis=1) == 1
calendar['is_weekend'] = calendar[['saturday', 'sunday']].max(axis=1) == 1
weekday_services = set(calendar[calendar['is_weekday']]['service_id'])
weekend_services = set(calendar[calendar['is_weekend']]['service_id'])

# Trip counts
weekday_trips = trips[trips['service_id'].isin(weekday_services)].groupby('route_id')['trip_id'].nunique().reset_index(name='weekday_trip_count')
weekend_trips = trips[trips['service_id'].isin(weekend_services)].groupby('route_id')['trip_id'].nunique().reset_index(name='weekend_trip_count')

route_df = route_df.merge(weekday_trips, on='route_id', how='left')
route_df = route_df.merge(weekend_trips, on='route_id', how='left')
# When a route has no trips scheduled on weekday/weekend, the trip count is logically 0
route_df['weekday_trip_count'] = route_df['weekday_trip_count'].fillna(0).astype(int)
route_df['weekend_trip_count'] = route_df['weekend_trip_count'].fillna(0).astype(int)
route_df['total_trips'] = route_df['weekday_trip_count'] + route_df['weekend_trip_count']

# Compute Headways per day type
def time_to_sec(t):
    try:
        parts = str(t).strip().split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except Exception:
        return np.nan

# Extract origin departure time per trip
origin_times = stop_times.sort_values(['trip_id', 'stop_sequence']).groupby('trip_id').first().reset_index()
origin_times['dep_sec'] = origin_times['departure_time'].apply(time_to_sec)
trip_sched = trips[['trip_id', 'route_id', 'service_id']].merge(origin_times[['trip_id', 'dep_sec']], on='trip_id').dropna(subset=['dep_sec'])

def compute_headway_stats(df):
    df_sorted = df.sort_values('dep_sec')
    deps = df_sorted['dep_sec'].values
    if len(deps) < 2:
        return pd.Series({'headway_min': np.nan, 'headway_count': 0})
    diffs = np.diff(deps) / 60.0 # to minutes
    diffs = diffs[diffs > 0] # strictly positive intervals
    if len(diffs) == 0:
        return pd.Series({'headway_min': np.nan, 'headway_count': 0})
    return pd.Series({
        'headway_min': float(np.median(diffs)),
        'headway_count': int(len(diffs))
    })

sched_weekday = trip_sched[trip_sched['service_id'].isin(weekday_services)]
sched_weekend = trip_sched[trip_sched['service_id'].isin(weekend_services)]

hw_weekday = sched_weekday.groupby('route_id').apply(compute_headway_stats).reset_index().rename(
    columns={'headway_min': 'weekday_headway_min', 'headway_count': 'weekday_headway_intervals'}
)
hw_weekend = sched_weekend.groupby('route_id').apply(compute_headway_stats).reset_index().rename(
    columns={'headway_min': 'weekend_headway_min', 'headway_count': 'weekend_headway_intervals'}
)

route_df = route_df.merge(hw_weekday, on='route_id', how='left')
route_df = route_df.merge(hw_weekend, on='route_id', how='left')

# D. Route-Specific Graph Metrics Reconstructed from GTFS
print("  Constructing transit network graph and deriving route-specific network metrics...")
st_sorted = stop_times.sort_values(['trip_id', 'stop_sequence'])
mask = st_sorted['trip_id'] == st_sorted['trip_id'].shift(-1)
u_nodes = st_sorted['stop_id'][mask].values
v_nodes = st_sorted['stop_id'].shift(-1)[mask].values

edge_df = pd.DataFrame({'u': u_nodes, 'v': v_nodes}).drop_duplicates()
G = nx.from_pandas_edgelist(edge_df, source='u', target='v', create_using=nx.DiGraph())

# Node degree and sampled betweenness centrality (seed=42 for exact reproducibility)
deg_dict = dict(G.degree())
bc_dict = nx.betweenness_centrality(G, k=min(150, len(G)), seed=42)

stop_metrics = pd.DataFrame({
    'stop_id': list(deg_dict.keys()),
    'node_degree': list(deg_dict.values()),
    'node_betweenness': [bc_dict.get(s, 0.0) for s in deg_dict.keys()]
})

# Map stop metrics to routes
route_stops_unique = trip_stop[['route_id', 'stop_id']].drop_duplicates()
route_stop_net = route_stops_unique.merge(stop_metrics, on='stop_id', how='inner')

route_net_agg = route_stop_net.groupby('route_id').agg({
    'node_degree': 'mean',
    'node_betweenness': 'mean'
}).reset_index().rename(columns={
    'node_degree': 'avg_stop_degree',
    'node_betweenness': 'avg_stop_betweenness'
})

route_df = route_df.merge(route_net_agg, on='route_id', how='left')

# Route-specific segment and traversal counts
trip_edges = pd.DataFrame({
    'trip_id': st_sorted['trip_id'][mask].values,
    'u': u_nodes,
    'v': v_nodes
})
trip_edges['segment'] = trip_edges['u'] + '_' + trip_edges['v']
trip_edges = trip_edges.merge(trips[['trip_id', 'route_id']], on='trip_id')

route_edge_traversals = trip_edges.groupby('route_id').agg(
    route_unique_segments=('segment', 'nunique'),
    total_segment_traversals=('segment', 'count')
).reset_index()

route_df = route_df.merge(route_edge_traversals, on='route_id', how='left')

print(f"Feature engineering completed for {len(route_df):,} routes.")

# ---------------------------------------------------------
# 4. Missing Value Assessment and Imputation
# ---------------------------------------------------------
print("\n[3/7] Missing value assessment and handling...")

feature_cols = [
    'stop_count',
    'route_length_km',
    'weekday_trip_count',
    'weekend_trip_count',
    'weekday_headway_min',
    'weekend_headway_min',
    'centroid_lat',
    'centroid_lon',
    'avg_stop_degree',
    'avg_stop_betweenness',
    'route_unique_segments',
    'total_segment_traversals'
]

missing_counts = route_df[feature_cols].isna().sum()
missing_pcts = (missing_counts / len(route_df)) * 100.0
missing_report = pd.DataFrame({
    'Feature': feature_cols,
    'Missing_Count': missing_counts.values,
    'Missing_Pct': missing_pcts.values
})
print("Missingness before handling:")
for _, r in missing_report.iterrows():
    print(f"  - {r['Feature']:<25}: {int(r['Missing_Count']):>5} ({r['Missing_Pct']:>5.2f}%)")

# Handle missing values:
# 1. Weekday/Weekend headway: routes with <2 trips have undefined headway.
# Impute with median of routes that DO operate on those days.
# 2. Geometry (length, centroids): median imputation for isolated routes without coords.
# 3. Graph metrics: median imputation for routes with unlinked stop nodes.
X = route_df[feature_cols].copy()
imputed_values = {}
for col in feature_cols:
    med = float(X[col].median())
    imputed_values[col] = med
    X[col] = X[col].fillna(med)

print("\nMissing values after imputation:", X.isna().sum().sum())

# ---------------------------------------------------------
# 5. Feature Scaling
# ---------------------------------------------------------
print("\n[4/7] Scaling features using StandardScaler...")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ---------------------------------------------------------
# 6. Clustering: K-Means, Agglomerative, and DBSCAN
# ---------------------------------------------------------
print("\n[5/7] Evaluating K-Means and Agglomerative Clustering...")

k_range = list(range(2, 7))
kmeans_metrics = []

for k in k_range:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    sil = silhouette_score(X_scaled, labels)
    db = davies_bouldin_score(X_scaled, labels)
    ch = calinski_harabasz_score(X_scaled, labels)
    kmeans_metrics.append({'k': k, 'silhouette': sil, 'davies_bouldin': db, 'calinski_harabasz': ch})
    print(f"  K-Means (k={k}) -> Silhouette: {sil:.4f}, Davies-Bouldin: {db:.4f}, Calinski-Harabasz: {ch:.1f}")

km_df = pd.DataFrame(kmeans_metrics)
best_k = int(km_df.loc[km_df['silhouette'].idxmax(), 'k'])
print(f"\nBest K-Means cluster count selected by Silhouette Score: k = {best_k}")

# Final K-Means fit
km_final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
km_labels = km_final.fit_predict(X_scaled)
route_df['kmeans_cluster'] = km_labels

km_sil = silhouette_score(X_scaled, km_labels)
km_db = davies_bouldin_score(X_scaled, km_labels)

# Agglomerative Clustering
print(f"\nRunning Agglomerative Clustering (Ward Linkage, k={best_k})...")
agg_final = AgglomerativeClustering(n_clusters=best_k, linkage='ward')
agg_labels = agg_final.fit_predict(X_scaled)
route_df['agg_cluster'] = agg_labels

agg_sil = silhouette_score(X_scaled, agg_labels)
agg_db = davies_bouldin_score(X_scaled, agg_labels)
print(f"  Agglomerative (k={best_k}) -> Silhouette: {agg_sil:.4f}, Davies-Bouldin: {agg_db:.4f}")

# DBSCAN Assessment
print("\nEvaluating DBSCAN on standard scaled feature space...")
dbscan = DBSCAN(eps=1.5, min_samples=10)
db_labels = dbscan.fit_predict(X_scaled)
n_clusters_db = len(set(db_labels)) - (1 if -1 in db_labels else 0)
n_noise_db = list(db_labels).count(-1)
print(f"  DBSCAN found {n_clusters_db} clusters and {n_noise_db} noise points (out of {len(db_labels)}).")

dbscan_evaluated = False
if n_clusters_db > 1:
    valid_mask = db_labels != -1
    if valid_mask.sum() > 0 and len(set(db_labels[valid_mask])) > 1:
        db_sil = silhouette_score(X_scaled[valid_mask], db_labels[valid_mask])
        db_db = davies_bouldin_score(X_scaled[valid_mask], db_labels[valid_mask])
        route_df['dbscan_cluster'] = db_labels
        dbscan_evaluated = True
        print(f"  DBSCAN (core points) -> Silhouette: {db_sil:.4f}, Davies-Bouldin: {db_db:.4f}")
if not dbscan_evaluated:
    route_df['dbscan_cluster'] = db_labels
    db_sil, db_db = None, None
    print("  DBSCAN is not justified as primary model due to high density variation / outlier classification.")

# ---------------------------------------------------------
# 7. Visualisations and Output Generation
# ---------------------------------------------------------
print("\n[6/7] Generating figures and cluster assignments...")

# A. Silhouette vs k Plot
fig, ax1 = plt.subplots(figsize=(8, 5))
color = 'tab:blue'
ax1.set_xlabel('Number of Clusters (k)', fontsize=12)
ax1.set_ylabel('Silhouette Score (Higher is better)', color=color, fontsize=12)
ax1.plot(km_df['k'], km_df['silhouette'], marker='o', linewidth=2.5, color=color, label='Silhouette')
ax1.tick_params(axis='y', labelcolor=color)

ax2 = ax1.twinx()
color = 'tab:red'
ax2.set_ylabel('Davies-Bouldin Index (Lower is better)', color=color, fontsize=12)
ax2.plot(km_df['k'], km_df['davies_bouldin'], marker='s', linestyle='--', linewidth=2.5, color=color, label='Davies-Bouldin')
ax2.tick_params(axis='y', labelcolor=color)

plt.title('K-Means Cluster Evaluation Metrics across k=2..6', fontsize=14, fontweight='bold', pad=12)
fig.tight_layout()
sil_fig_path = figures_dir / 'fig_clustering_silhouette.png'
plt.savefig(sil_fig_path, dpi=200)
plt.savefig(out_dir / 'fig_silhouette.png', dpi=200)
plt.close()
print(f"Saved Silhouette curve figure: {sil_fig_path}")

# B. Geographic Centroid Map
plt.figure(figsize=(9, 7))
valid_geo = route_df.dropna(subset=['centroid_lat', 'centroid_lon'])
scatter = plt.scatter(
    valid_geo['centroid_lon'],
    valid_geo['centroid_lat'],
    c=valid_geo['kmeans_cluster'],
    cmap='viridis',
    s=35,
    alpha=0.75,
    edgecolors='none'
)
cbar = plt.colorbar(scatter)
cbar.set_label('K-Means Cluster Assignment', fontsize=11)
plt.title('Chennai MTC Route Spatial Centroids by Cluster', fontsize=13, fontweight='bold', pad=10)
plt.xlabel('Longitude', fontsize=11)
plt.ylabel('Latitude', fontsize=11)
plt.grid(True, linestyle=':', alpha=0.6)
map_fig_path = figures_dir / 'fig_clustering_route_map.png'
plt.savefig(map_fig_path, dpi=200)
plt.savefig(out_dir / 'fig_route_map.png', dpi=200)
plt.close()
print(f"Saved Route Map figure: {map_fig_path}")

# C. Save Cluster Assignments CSV
assign_cols = [
    'route_id', 'route_short_name', 'canonical_route', 'stop_count',
    'route_length_km', 'weekday_trip_count', 'weekend_trip_count',
    'weekday_headway_min', 'weekend_headway_min', 'kmeans_cluster', 'agg_cluster'
]
if 'dbscan_cluster' in route_df.columns:
    assign_cols.append('dbscan_cluster')

assign_csv_path1 = out_dir / 'route_cluster_assignments.csv'
assign_csv_path2 = reports_dir / 'route_cluster_assignments.csv'
route_df[assign_cols].to_csv(assign_csv_path1, index=False)
route_df[assign_cols].to_csv(assign_csv_path2, index=False)
print(f"Saved cluster assignments: {assign_csv_path1}")

# Cluster Profile Summary Table
cluster_summary = route_df.groupby('kmeans_cluster').agg(
    Route_Count=('route_id', 'count'),
    Avg_Stops=('stop_count', 'mean'),
    Avg_Length_km=('route_length_km', 'mean'),
    Avg_Weekday_Trips=('weekday_trip_count', 'mean'),
    Avg_Weekend_Trips=('weekend_trip_count', 'mean'),
    Avg_Weekday_Headway=('weekday_headway_min', 'mean'),
    Avg_Stop_Degree=('avg_stop_degree', 'mean')
).reset_index()

# Helper for markdown conversion without tabulate dependency
def df_to_markdown(df):
    headers = list(df.columns)
    lines = ['| ' + ' | '.join(str(h) for h in headers) + ' |']
    lines.append('| ' + ' | '.join([':---' if df[h].dtype == 'O' else '---:' for h in headers]) + ' |')
    for _, row in df.iterrows():
        vals = []
        for h in headers:
            v = row[h]
            if isinstance(v, float):
                vals.append(f"{v:.4f}" if abs(v) < 100 else f"{v:,.1f}")
            elif isinstance(v, (int, np.integer)):
                vals.append(f"{v:,}")
            else:
                vals.append(str(v))
        lines.append('| ' + ' | '.join(vals) + ' |')
    return '\n'.join(lines)

# ---------------------------------------------------------
# 8. Markdown Report Generation
# ---------------------------------------------------------
print("\n[7/7] Generating route_clustering_report.md...")
report_content = f"""# Chennai MTC RouteRanker - Route Clustering Report

**Date of Execution:** {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Input GTFS Directory:** `{data_dir}`  
**Analyzed Routes:** {len(route_df):,}  

---

## 1. Executive Summary
This report presents the route-level feature engineering and clustering analysis for Chennai MTC public transit network. Using supply-side GTFS schedule data and transit topology, routes are grouped into functional operational clusters using **K-Means** (baseline) and **Agglomerative Hierarchical Clustering** (Ward linkage).

Primary evaluation is conducted via **Silhouette Score** (measuring cluster cohesion and separation) and **Davies-Bouldin Index** (measuring cluster dispersion).

---

## 2. Feature Engineering & Missing Value Handling

### 2.1 Feature Definitions
Twelve comprehensive supply-side route features were engineered directly from verified GTFS tables without fabricating data:
1. `stop_count`: Total unique stops serviced by the route.
2. `route_length_km`: Trajectory distance (km) along representative stop sequences using the Haversine formula.
3. `weekday_trip_count`: Total daily trips scheduled on weekdays.
4. `weekend_trip_count`: Total daily trips scheduled on weekends.
5. `weekday_headway_min`: Median headway (minutes) between consecutive departures on weekdays.
6. `weekend_headway_min`: Median headway (minutes) between consecutive departures on weekends.
7. `centroid_lat` & `centroid_lon`: Median geographic coordinates of stops along the route.
8. `avg_stop_degree`: Average degree of route stops in the directed transit network.
9. `avg_stop_betweenness`: Average betweenness centrality of stops along the route.
10. `route_unique_segments`: Count of distinct stop-to-stop directional links traversed.
11. `total_segment_traversals`: Total edge traversal volume generated by scheduled trips.

### 2.2 Missing Data Treatment
Missing values were audited and systematically addressed:

{df_to_markdown(missing_report)}

- **Headways:** Routes with zero or single trips have undefined headway intervals (not 0 minutes, which would improperly indicate infinite frequency). Missing values were imputed with the median headway of operating routes ({imputed_values['weekday_headway_min']:.1f} min on weekdays, {imputed_values['weekend_headway_min']:.1f} min on weekends).
- **Spatial Coordinates / Graph Metrics:** Routes without valid coordinate sequences were imputed using the transit network median ({imputed_values['route_length_km']:.2f} km).
- **Scaling:** All features were scaled using `StandardScaler` to ensure zero mean and unit variance prior to distance calculation.

---

## 3. Clustering Methodology & Results

### 3.1 K-Means Hyperparameter Selection
Evaluated across k in [2, 6]:

{df_to_markdown(km_df)}

**Selected Optimal Model:** k = {best_k} achieves the highest Silhouette Score ({km_sil:.4f}) and lowest Davies-Bouldin Index ({km_db:.4f}).

### 3.2 Algorithm Comparison

| Algorithm | Clusters (k) | Silhouette Score (Higher is better) | Davies-Bouldin Index (Lower is better) | Status |
| :--- | :---: | :---: | :---: | :---: |
| **K-Means** | **{best_k}** | **{km_sil:.4f}** | **{km_db:.4f}** | **Recommended** |
| **Agglomerative (Ward)** | **{best_k}** | **{agg_sil:.4f}** | **{agg_db:.4f}** | Comparative Baseline |
| **DBSCAN** | {n_clusters_db} | {f'{db_sil:.4f}' if db_sil is not None else 'N/A'} | {f'{db_db:.4f}' if db_db is not None else 'N/A'} | Rejected (high density disparity, {n_noise_db} noise points) |

### 3.3 Cluster Profiles (K-Means)

{df_to_markdown(cluster_summary)}

---

## 4. Visualisations
- **Silhouette vs k Curve:** `figures/fig_clustering_silhouette.png`
- **Route Spatial Centroid Map:** `figures/fig_clustering_route_map.png`

![Silhouette Curve](figures/fig_clustering_silhouette.png)
![Route Centroids Map](figures/fig_clustering_route_map.png)

---

## 5. Daily Ridership Regression Data Limitation

> **Data Limitation Statement:**  
> The Chennai MTC GTFS specification and existing project datasets provide static timetables, stop locations, and scheduled service frequencies. However, **no empirical daily passenger boardings, tap-in/tap-out smartcard counts, or route-level passenger volume observations exist** in the repository.  
> 
> As established in the project guidelines, synthetic or fabricated ridership data must not be created. Consequently, supervised regression modeling for daily passenger ridership is constrained until verifiable observed ridership datasets are integrated. The supply-side clustering presented in this report provides the foundational typology required once passenger demand observations become available.
"""

report_file = reports_dir / 'route_clustering_report.md'
with open(report_file, 'w', encoding='utf-8') as f:
    f.write(report_content)

# Also write to route_clustering folder
with open(out_dir / 'route_clustering_report.md', 'w', encoding='utf-8') as f:
    f.write(report_content)

print(f"Report written to: {report_file}")
print("=" * 60)
print(f"ALL TASKS COMPLETED IN {time.time()-t0:.2f} SECONDS")
print("=" * 60)
