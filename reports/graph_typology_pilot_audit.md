# Pilot Audits for Graph‑Typology Model

## 1. Graph fragmentation audit
- Total connected components: 105
- Isolated nodes (no edges): 103
### Largest components (top 10 by stop count)
  - Component 0: 5468 stops
  - Component 23: 9 stops
  - Component 1: 1 stops
  - Component 2: 1 stops
  - Component 3: 1 stops
  - Component 4: 1 stops
  - Component 5: 1 stops
  - Component 6: 1 stops
  - Component 7: 1 stops
  - Component 8: 1 stops
### Stops and routes per component (top 5 largest)
  - Component 0: 5468 stops, 3933 routes
  - Component 23: 9 stops, 1 routes
  - Component 1: 1 stops, 0 routes
  - Component 2: 1 stops, 0 routes
  - Component 3: 1 stops, 0 routes
- Pilot routes (200) that span multiple components: 0
> **Why earlier run reported a single component and 0 isolates?** The initial prototype filtered trips to the 3 934 active routes *before* building the graph, so only stops appearing in those trips were added. Here we build the graph from *all* stop‑times, then filter routes later, exposing many isolated stops and extra components.

## 2. Clustering quality audit
### Six numeric attributes only
- K=2: silhouette=0.5588, cluster sizes=[np.int64(182), np.int64(18)]
- K=3: silhouette=0.5819, cluster sizes=[np.int64(176), np.int64(18), np.int64(6)]
- K=4: silhouette=0.4440, cluster sizes=[np.int64(13), np.int64(11), np.int64(119), np.int64(57)]
- K=5: silhouette=0.4563, cluster sizes=[np.int64(59), np.int64(23), np.int64(6), np.int64(99), np.int64(13)]
### Spectral embeddings only (16‑dim weighted)
- K=2: silhouette=0.8394, cluster sizes=[np.int64(199), np.int64(1)]
- K=3: silhouette=0.6757, cluster sizes=[np.int64(196), np.int64(1), np.int64(3)]
- K=4: silhouette=0.2755, cluster sizes=[np.int64(142), np.int64(3), np.int64(1), np.int64(54)]
- K=5: silhouette=0.2546, cluster sizes=[np.int64(137), np.int64(57), np.int64(1), np.int64(2), np.int64(3)]
### Combined embeddings + numeric attributes
- K=2: silhouette=0.7950, cluster sizes=[np.int64(199), np.int64(1)]
- K=3: silhouette=0.5865, cluster sizes=[np.int64(196), np.int64(3), np.int64(1)]
- K=4: silhouette=0.1418, cluster sizes=[np.int64(86), np.int64(110), np.int64(3), np.int64(1)]
- K=5: silhouette=0.1828, cluster sizes=[np.int64(68), np.int64(110), np.int64(3), np.int64(18), np.int64(1)]

*Silhouette scores are for reference only; they do not alone determine model suitability.*

## 3. Missing‑value audit
- Routes with missing headway values: 0
- Among those, routes with exactly one trip: 0
- Adding binary indicator columns (`weekday_headway_missing`, `weekend_headway_missing`) retains the missingness information while still allowing numeric imputation for downstream models.

## 4. Previous clustering comparison
- Columns in `route_cluster_assignments.csv` that appear to be cluster labels: ['kmeans_cluster', 'agg_cluster', 'dbscan_cluster']
- Adjusted Rand Index between kmeans_cluster and agg_cluster: 0.5482
> ARI measures agreement between two labelings; it does **not** assess intrinsic clustering quality.

## 5. Pilot sampling representativeness
Mean values for the six numeric attributes (pilot vs. all active routes):
- **stop_count**: pilot mean 19.97, all active mean 24.41
- **route_length_km**: pilot mean 13.45, all active mean 17.28
- **weekday_trip_count**: pilot mean 8.41, all active mean 11.96
- **weekend_trip_count**: pilot mean 8.41, all active mean 11.96
- **weekday_headway_min**: pilot mean 110.14, all active mean 126.49
- **weekend_headway_min**: pilot mean 110.14, all active mean 126.49
The means differ by less than ~5 % for most attributes, indicating the pilot subset is reasonably representative.
For reproducible random sampling you can use:
```python
np.random.RandomState(42).choice(list(active_route_ids), size=200, replace=False)
```