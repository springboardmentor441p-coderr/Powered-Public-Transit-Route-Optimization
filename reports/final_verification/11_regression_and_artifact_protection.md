# 11 — Cross-Milestone Regression & Artifact Protection Report (Phase K)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Audit Date:** 2026-11-25  

---

## 1. Protected Artifact SHA-256 Comparison

| Artifact | Current SHA-256 | Matches Baseline |
| --- | --- | :---: |
| `tier1_random_forest_tuned.joblib` | `d73b79016012496809f9bc2dc3e05db686d5894f02a55d859a42f91052af1508` | **YES** |
| `tier2_random_forest_tuned.joblib` | `dafa999d181502d35098944c97009458f7f79bbefa3be0542e39b41b07ab40b5` | **YES** |
| `tier1_val_predictions_tuned.parquet` | `4214b9140711c2f1901acb2252b0d90ee25fe095bd240acc65ab4af2a5879f3e` | **YES** |
| `tier1_test_predictions_tuned.parquet` | `3d1a70b6d447544eb4d3f862a1fd9bcb490f28b2a8725e93ab1e76187402c9a2` | **YES** |
| `tier1_august_predictions_tuned.parquet` | `33c59e2e4438475dea175fbd39ede81e930eb953451fa35683a7c1fad5281e06` | **YES** |
| `tier2_val_predictions_tuned.parquet` | `f0f0bb8f4c86892b998e5cf30f9bb3feeaaaf7dd4873800133e3fd3cd5c2981e` | **YES** |
| `tier2_test_predictions_tuned.parquet` | `4b6825dedc8d601c831e4483e64ee896dc952fca71ff798dd007bc31427e72fb` | **YES** |
| `transit_hub_rankings.parquet` | `20e116891376696370c38c2dd919d8d59c95b981fb493270b29763adb2260aa7` | **YES** |
| `corridor_cluster_assignments.parquet` | `7cd435ab1a6bd3e81cc0ebc2f3214723a8602b8240faa9a5ae882edd9d8625af` | **YES** |
| `route_ranker_feature_master.parquet` | `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85` | **YES** |
| `route_rankings_master.parquet` | `c440671d0b3888683969cb5fc11ccf7b581128a7296069019f76202b64f0093b` | **YES** |
| `ai_routeranker.duckdb` | `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209` | **YES** |

- Zero modifications to Milestone 5, 6, 7, or 8 outputs, DuckDB, or model binaries occurred during this audit.
