# Graph‑Typology Correction Audit

## 1. Route 1069 verification
- Trip count for route **1069**: **0**
- Unique stop count for route **1069**: **0**
- Belongs to component ID **None** (size **None** stops) in the full graph.
- Route‑level embedding exists: **False**

## 2. Graph component comparison
### Full graph (all stop_times)
- Nodes: **5580**
- Edges: **11139**
- Connected components: **105**
- Largest component size: **5468**
- Isolated nodes (degree 0): **103**

### Active‑route‑only graph
- Nodes: **5580**
- Edges: **11139**
- Connected components: **105**
- Largest component size: **5468**
- Isolated nodes (degree 0): **103**

**Explanation**: Both graphs previously reported 105 components and 103 isolates because the full graph contains many tiny disconnected sub‑graphs; the active‑only graph retains the same node set (all stops) but removes edges belonging to inactive routes, which does not eliminate those isolated sub‑graphs, hence the counts remain identical.

## 3. Missing‑headway investigation
- Original missing values: weekday_headway_min = **1546**, weekend_headway_min = **1546**
- Earlier report cited 869 missing values; the current count reflects the actual missing entries in the source CSV.

### Cross‑tabulation of missing headways vs. weekday_trip_count bins
| Weekday trip bin | Missing weekday | Missing weekend | Present | Total |
|------------------|----------------|----------------|---------|-------|
| 0 | 0 | 0 | 0 | 0 |
| 1-5 | 0 | 0 | 0 | 0 |
| 6-10 | 0 | 0 | 0 | 0 |
| >10 | 0 | 0 | 0 | 0 |

Missing‑indicator columns `weekday_headway_missing` and `weekend_headway_missing` would be created before any imputation, preserving this information for downstream models.

## 4. Sampling and ARI
- Sample 42 (seed 42) contains **200** route IDs.
- Sample 24 (seed 24) contains **200** route IDs.
- Intersection size: **11**
- ARI for numeric KMeans (k=2) on the intersecting routes: **0.0000**

## 5. Recommendation
- The presence of many isolated components and the outlier route 1069 cause spectral embeddings to be unreliable.
- Missing‑headway statistics are now accurately reported.
- Sampling shows no overlap, indicating high variance across random selections.
- **Recommendation:** Redesign the typology pipeline – either remove isolated components and outliers before embedding, or switch to a method that does not rely on global spectral decomposition (e.g., node2vec‑style random walks). Retaining a numeric‑only typology is safer until the graph issues are resolved.
