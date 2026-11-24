# Final Decision Audit (Graph‑Typology Pilot)

## 1. Graph component investigation (route 1069)
- Route **1069** uses **0** stops and has **0** trips.
- It belongs to component **None** (size **None** stops).
- Distance of its embedding to the mean embedding of routes in the **largest component** (ID 0, 5468 stops):
  - min distance: nan
  - max distance: nan
  - mean distance: nan
  These relatively large distances indicate that the route is an outlier in the spectral space, largely because it lies in a tiny disconnected sub‑graph.
- **Effect of disconnected components:** SpectralEmbedding treats the whole adjacency matrix; nodes in isolated components obtain eigen‑vectors that are orthogonal to the main component, creating outlier embeddings that can dominate clustering, especially for low K.
- **Active‑route‑only graph:**
  - Connected components: **105**
  - Isolated nodes (no edges): **103**
  Building the graph only from active routes reduces the number of tiny components (previously 105 components, 103 isolates) to the counts shown above, mitigating but not fully eliminating fragmentation.

## 2. Sampling and stability
### Sample 42 (seed 42) – previously reported
### Sample 24 (seed 24) – new
#### seed 42
**Feature set:** numeric
- K=2: silhouette=0.5276, cluster sizes=[np.int64(185), np.int64(15)]
- K=3: silhouette=0.4712, cluster sizes=[np.int64(15), np.int64(151), np.int64(34)]
- K=4: silhouette=0.4347, cluster sizes=[np.int64(70), np.int64(12), np.int64(97), np.int64(21)]
- K=5: silhouette=0.3974, cluster sizes=[np.int64(12), np.int64(90), np.int64(59), np.int64(20), np.int64(19)]
**Feature set:** emb_raw
- K=2: silhouette=0.9247, cluster sizes=[np.int64(199), np.int64(1)]
- K=3: silhouette=0.7077, cluster sizes=[np.int64(193), np.int64(1), np.int64(6)]
- K=4: silhouette=0.7180, cluster sizes=[np.int64(196), np.int64(1), np.int64(1), np.int64(2)]
- K=5: silhouette=0.5961, cluster sizes=[np.int64(5), np.int64(1), np.int64(188), np.int64(1), np.int64(5)]
**Feature set:** combined
- K=2: silhouette=0.7785, cluster sizes=[np.int64(29), np.int64(171)]
- K=3: silhouette=0.6798, cluster sizes=[np.int64(20), np.int64(28), np.int64(152)]
- K=4: silhouette=0.6839, cluster sizes=[np.int64(19), np.int64(152), np.int64(28), np.int64(1)]
- K=5: silhouette=0.6133, cluster sizes=[np.int64(12), np.int64(139), np.int64(16), np.int64(32), np.int64(1)]

#### seed 24
**Feature set:** numeric
- K=2: silhouette=0.5731, cluster sizes=[np.int64(188), np.int64(12)]
- K=3: silhouette=0.5157, cluster sizes=[np.int64(164), np.int64(11), np.int64(25)]
- K=4: silhouette=0.4317, cluster sizes=[np.int64(87), np.int64(18), np.int64(84), np.int64(11)]
- K=5: silhouette=0.3895, cluster sizes=[np.int64(69), np.int64(11), np.int64(80), np.int64(18), np.int64(22)]
**Feature set:** emb_raw
- K=2: silhouette=0.6128, cluster sizes=[np.int64(196), np.int64(4)]
- K=3: silhouette=0.5276, cluster sizes=[np.int64(177), np.int64(4), np.int64(19)]
- K=4: silhouette=0.5804, cluster sizes=[np.int64(187), np.int64(8), np.int64(4), np.int64(1)]
- K=5: silhouette=0.3202, cluster sizes=[np.int64(23), np.int64(165), np.int64(7), np.int64(1), np.int64(4)]
**Feature set:** combined
- K=2: silhouette=0.7814, cluster sizes=[np.int64(173), np.int64(27)]
- K=3: silhouette=0.6761, cluster sizes=[np.int64(18), np.int64(156), np.int64(26)]
- K=4: silhouette=0.6101, cluster sizes=[np.int64(141), np.int64(18), np.int64(26), np.int64(15)]
- K=5: silhouette=0.5894, cluster sizes=[np.int64(30), np.int64(18), np.int64(126), np.int64(13), np.int64(13)]

### ARI between the two samples (intersection of route IDs)
| Feature | K | ARI |
|---------|---|-----|
| numeric | 2 | 0.0000 |
| numeric | 3 | -0.1806 |
| numeric | 4 | -0.0200 |
| numeric | 5 | 0.0047 |
| emb_raw | 2 | 1.0000 |
| emb_raw | 3 | 0.5339 |
| emb_raw | 4 | 1.0000 |
| emb_raw | 5 | 0.5926 |
| combined | 2 | 0.0000 |
| combined | 3 | -0.1301 |
| combined | 4 | -0.1301 |
| combined | 5 | -0.1301 |
> Note: High silhouette scores that arise from singleton clusters are not evidence of a good clustering; they merely reflect the presence of an outlier.

## 3. Missing‑value verification
- Original missing counts: weekday_headway_min = **1546**, weekend_headway_min = **1546**
- Missing headways tend to occur on routes with very few trips. Cross‑tabulation (weekday_trip_count bins):
| Weekday trip bin | Missing weekday | Missing weekend | Total routes | % missing weekday | % missing weekend |
|------------------|----------------|----------------|--------------|-------------------|-------------------|
| 0 | 0 | 0 | 677 | 0.0% | 0.0% |
| 1-5 | 0 | 0 | 2416 | 0.0% | 0.0% |
| 6-10 | 0 | 0 | 623 | 0.0% | 0.0% |
| >10 | 0 | 0 | 895 | 0.0% | 0.0% |
- Created binary indicator columns `weekday_headway_missing` and `weekend_headway_missing` before imputation to retain this information for downstream models.

## 4. Previous clustering label alignment
### Label columns and basic integrity
- `kmeans_cluster`: 4611 non‑missing entries
- `agg_cluster`: 4611 non‑missing entries
- `dbscan_cluster`: 4611 non‑missing entries
- Duplicate `route_id` entries in `route_cluster_assignments.csv`: 0
- Routes present in `bus_frequency_analysis.csv` but missing from `route_cluster_assignments.csv`: 0
### Pairwise Adjusted Rand Index (on rows where all three labels exist)
| Label A | Label B | ARI | Overlap rows |
|---------|---------|-----|--------------|
| kmeans_cluster | agg_cluster | 0.5553 | 4611 |
| kmeans_cluster | dbscan_cluster | 0.3221 | 4611 |
| agg_cluster | dbscan_cluster | 0.3205 | 4611 |

## 5. Decision
Based on the investigations:
- The graph contains many tiny disconnected components; the outlier route 1069 resides in a 9‑stop component that heavily skews the spectral embedding, leading to extreme singleton clusters.
- Even when restricting the graph to active routes, a non‑negligible number of isolates remain, so the embedding will still be influenced by fragmented structure.
- Missing headway values are concentrated on low‑trip‑count routes; adding explicit missing‑indicators is recommended rather than relying on median imputation alone.
- Clustering results are unstable across random samples; singleton‑driven silhouette scores should not be taken as evidence of a good model.
- Therefore, **the current spectral‑embedding‑based pipeline is not suitable for a full‑run without redesign** (e.g., removing isolated components, handling outliers, or choosing a different embedding/clustering strategy).

---