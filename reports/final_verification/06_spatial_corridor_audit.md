# 06 — Spatial & Corridor Verification Audit (Phase F)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Audit Date:** 2026-11-25  

---

## 1. Spatial Hub & DBSCAN Verification
- **Canonical Top-100 (`config=a`):** `100` hubs returned with `0` invalid coordinates (`-90 <= lat <= 90`, `-180 <= lon <= 180`), and canonical tie-breaking preserved (Stop `4732` at Rank #100).
- **DBSCAN Clustering & Noise:** `11,020` boarding stops input, `117` clusters, `10,583` hub-eligible stops, and `18` noise stops (`dbscan_cluster = -1`) verified via `/spatial/clusters/summary` and `/spatial/hubs?dbscan_cluster=-1`.
- **Leaflet Map Consistency:** `SpatialPage` plots only stops with `coordinates_available === true` and non-null `lat`/`lon`, with explicit demand-proxy and non-equity disclaimers.

## 2. Corridor Topology & Co-Routing Verification
- **Cluster Assignments:** `261` route-direction patterns verified for both `buffer` and `frechet` clustering (`k=3,4,5`).
- **Co-Routing Separation:** Route `151` (`2` directional patterns: `151__dir_0`, `151__dir_1`) exposes **Buffer Overlap Peers**, **Stop Jaccard Peers**, and **Shared Consecutive Stop Sequences** as strictly separate structures without fabricating a combined similarity score.
