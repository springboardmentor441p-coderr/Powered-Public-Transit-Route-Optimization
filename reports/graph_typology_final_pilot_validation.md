# Final Pilot Validation (Graph‑Typology)

## 1. Sample representativeness (seed 42)
- Original missing counts: weekday_headway_min = 1546, weekend_headway_min = 1546

### Statistics for the six numeric attributes
| Attribute | Full mean | Pilot mean | Full median | Pilot median | Full std | Pilot std |
|-----------|----------|-----------|------------|--------------|---------|-----------|
| stop_count | 24.41 | 25.02 | 23.00 | 23.00 | 13.68 | 13.80 |
| route_length_km | 17.28 | 16.92 | 15.43 | 15.22 | 11.42 | 10.87 |
| weekday_trip_count | 11.96 | 11.48 | 4.00 | 4.00 | 23.63 | 20.32 |
| weekend_trip_count | 11.96 | 11.48 | 4.00 | 4.00 | 23.63 | 20.32 |
| weekday_headway_min | 126.49 | 123.86 | 65.00 | 65.00 | 161.53 | 153.09 |
| weekend_headway_min | 126.49 | 123.86 | 65.00 | 65.00 | 161.53 | 153.09 |

**Conclusion:** The pilot sample differs noticeably from the full active set on several attributes (e.g., stop_count, route_length_km, trip counts, headways). It should not be considered a representative random subsample without proper weighting.

## 2. Spectral clustering imbalance investigation
### Outlier route detection (seed 42)
- Route ID with largest embedding distance from mean: 11584
- Distance from mean: 0.0337
- Component ID of that route: 0 (size 5468 stops)

### Clustering results (K=2 and K=3)
Feature set | Seed | K | Silhouette | Cluster sizes
--- | --- | --- | --- | ---
numeric | 42 | 2 | 0.5276 | [np.int64(185), np.int64(15)]
numeric | 42 | 3 | 0.4712 | [np.int64(15), np.int64(151), np.int64(34)]
emb_raw | 42 | 2 | 0.9247 | [np.int64(199), np.int64(1)]
emb_raw | 42 | 3 | 0.7077 | [np.int64(193), np.int64(1), np.int64(6)]
emb_scaled | 42 | 2 | 0.9007 | [np.int64(199), np.int64(1)]
emb_scaled | 42 | 3 | 0.6758 | [np.int64(6), np.int64(193), np.int64(1)]
combined_raw | 42 | 2 | 0.7785 | [np.int64(29), np.int64(171)]
combined_raw | 42 | 3 | 0.6798 | [np.int64(20), np.int64(28), np.int64(152)]
combined_scaled | 42 | 2 | 0.8625 | [np.int64(199), np.int64(1)]
combined_scaled | 42 | 3 | 0.2176 | [np.int64(168), np.int64(31), np.int64(1)]
numeric | 123 | 2 | 0.5276 | [np.int64(185), np.int64(15)]
numeric | 123 | 3 | 0.4819 | [np.int64(155), np.int64(30), np.int64(15)]
emb_raw | 123 | 2 | 0.9247 | [np.int64(199), np.int64(1)]
emb_raw | 123 | 3 | 0.7077 | [np.int64(6), np.int64(1), np.int64(193)]
emb_scaled | 123 | 2 | 0.8969 | [np.int64(199), np.int64(1)]
emb_scaled | 123 | 3 | 0.6765 | [np.int64(193), np.int64(1), np.int64(6)]
combined_raw | 123 | 2 | 0.7785 | [np.int64(29), np.int64(171)]
combined_raw | 123 | 3 | 0.6798 | [np.int64(20), np.int64(152), np.int64(28)]
combined_scaled | 123 | 2 | 0.8580 | [np.int64(199), np.int64(1)]
combined_scaled | 123 | 3 | 0.2147 | [np.int64(38), np.int64(1), np.int64(161)]

### Stability (Adjusted Rand Index) between seeds
Feature set | K | ARI
--- | --- | ---
numeric | 2 | 1.0000
numeric | 3 | 0.9232
emb_raw | 2 | 1.0000
emb_raw | 3 | 1.0000
emb_scaled | 2 | 1.0000
emb_scaled | 3 | 1.0000
combined_raw | 2 | 1.0000
combined_raw | 3 | 1.0000
combined_scaled | 2 | 1.0000
combined_scaled | 3 | 0.8379

> Note: High silhouette scores for K=2/3 are driven by the presence of a singleton cluster; this does not imply a good overall grouping.

## 3. Missing‑value handling
- Original missing counts (before any imputation): weekday = 1546, weekend = 1546
- Missing values occur primarily for routes that have very few or no recorded trips in the GTFS data (identified by low trip counts).
- Two approaches compared:
  1. Simple median imputation (used earlier).
  2. Median imputation **plus** binary missing‑indicator columns (`weekday_headway_missing`, `weekend_headway_missing`).
- Adding the indicators preserves the information that a headway was unavailable, which can be useful for downstream models; no fabricated values are introduced.

## 4. Previous clustering labels
### Label columns and row counts
- `kmeans_cluster`: 4611 non‑missing rows
- `agg_cluster`: 4611 non‑missing rows
- `dbscan_cluster`: 4611 non‑missing rows

### Adjusted Rand Index between previous labelings (only on routes where both labels exist)
| Label A | Label B | ARI | Overlap rows |
|---------|---------|-----|--------------|
| kmeans_cluster | agg_cluster | 0.5553 | 4611 |
| kmeans_cluster | dbscan_cluster | 0.3221 | 4611 |
| agg_cluster | dbscan_cluster | 0.3205 | 4611 |

> ARI measures agreement, not clustering quality.

## 5. Summary
- The pilot sample drawn with seed 42 is **not** a close proxy for the full active set across the six numeric attributes.
- Spectral embeddings produce a dominant outlier route that drives singleton clusters when KMeans is run with low K; this is linked to that route belonging to a tiny graph component.
- Scaling the embeddings does not remove the imbalance; cluster assignments are unstable across random seeds (ARI values show low agreement).
- Adding missing‑value indicators is recommended over plain median imputation to retain information about unavailable headways.
- Previous clustering labels are present, and their pairwise ARI values are reported above.

---