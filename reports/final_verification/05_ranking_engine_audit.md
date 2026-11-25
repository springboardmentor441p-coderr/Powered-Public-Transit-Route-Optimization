# 05 — Ranking Engine Verification Audit (Phase E)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Canonical Sources:** `artifacts/ranking_results/route_rankings_master.parquet`, `route_ranking_explanations.json`, `ranking_sensitivity_analysis.parquet`  
**Audit Date:** 2026-11-25  

---

## 1. Track Populations Verified
- `BUS_PRIORITY` (Track 1): `125` routes (Rank #1: Route `151`, `overall_score = 0.6363`, `topsis_score = 0.6111`).
- `RAIL_PRIORITY` (Track 2): `8` rail lines (Rank #1: `Red`, `overall_score = 0.8458`, demand pillar `0.0`).
- `UNIFIED_SUPPLY` (Track 3): `133` routes (`125` bus + `8` rail, Rank #1: `Red`, Rank #2: `79`).

## 2. Independent Score & Dynamic Weight Masking Reconciliation
- **Route `151` (complete criteria):** Sum of `effective_weights` = `1.000000`; sum of `contributions` = `0.636319` matching `overall_score = 0.63631855...`.
- **Route `10` (missing AM headway):** `is_headway_missing = True`, `valid_weight_coverage = 0.90`, remaining `effective_weights` re-normalized to `1.000000`.
- **Sensitivity Analysis:** `60` total scenarios (`28` Bus, `16` Rail, `16` Unified) verified via `/api/v1/rankings/sensitivity`.
