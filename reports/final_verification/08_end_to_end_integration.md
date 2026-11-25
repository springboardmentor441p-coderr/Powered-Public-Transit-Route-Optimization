# 08 — End-to-End Frontend–Backend Integration (Phase H)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Audit Date:** 2026-11-25  

---

## 1. Verified Live User Journeys (1–15)

| # | User Journey | Endpoint(s) | HTTP | UI Result | Verdict |
| --- | --- | --- | :---: | --- | :---: |
| 1 | Open dashboard → Overview KPIs | `/api/health`, `/routes`, `/rankings/{bus,rail}`, `/spatial/clusters/summary`, `/corridors/clusters`, `/ridership/routes/151/timeseries` | 200 | 6 KPIs + 3 Recharts charts | **PASS** |
| 2 | Open Routes → retrieve routes | `/api/v1/routes?limit=15&offset=0` | 200 | 1–15 of 133 rows | **PASS** |
| 3 | Search `"151"` | `/api/v1/routes?search=151&limit=15&offset=0` | 200 | Route `151` filtered cleanly | **PASS** |
| 4 | Change pagination Next/Prev | `/api/v1/routes?limit=15&offset=15` | 200 | 16–30 of 133 rows | **PASS** |
| 5 | Rankings → switch Bus/Rail/Unified | `/api/v1/rankings/{bus,rail,unified}` | 200 | All 3 tracks rendered (`L-01` transient 404 on switch) | **PASS** |
| 6 | Ranking explanation | `/api/v1/rankings/routes/{id}/explanation` | 200 | Pillar bar chart + narrative | **PASS** |
| 7 | Sensitivity scenarios | `/api/v1/rankings/sensitivity?track=...` | 200 | 28 Bus / 16 Rail / 16 Unified scenarios | **PASS** |
| 8 | Ridership history & Rail unavailable | `/api/v1/ridership/routes/{151,Red}/timeseries` | 200 | Monthly chart + Rail unavailable notice | **PASS** |
| 9 | Spatial hubs → Leaflet markers | `/api/v1/spatial/hubs/top?config=a&limit=100` | 200 | 100 map markers + table | **PASS** |
| 10 | Spatial DBSCAN `-1` filter | `/api/v1/spatial/hubs?dbscan_cluster=-1` | 200 | 18 noise stops filtered | **PASS** |
| 11 | Corridors → clusters & co-routing | `/api/v1/corridors/clusters`, `/routes/151/co-routing` | 200 | Separate Buffer/Jaccard/Sequences | **PASS** |
| 12 | Forecasting → historical eval | `/api/v1/forecasting/historical{/summary}` | 200 | Chart + summary + Tier 2 guard | **PASS** |
| 13 | Cross-page navigation | Multiple | 200 | Clean transitions, AbortController cleanup | **PASS** |
| 14 | Simulate backend stop (offline) | Vite proxy → `502` | 502 | Header `API Offline`, `Request Failed` + `Retry` | **PASS** |
| 15 | Restart backend → Retry & Reload | `/api/v1/*`, `/api/health` | 200 | `Retry` recovers KPIs/charts (`L-02` health needs reload); reload restores `API Online` | **PASS** |
