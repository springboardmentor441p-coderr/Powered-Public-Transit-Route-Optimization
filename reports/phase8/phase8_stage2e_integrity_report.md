# Phase 8, Stage 2E — Canonical Artifact Integrity Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Date:** 2026-11-25  

---

## 1. SHA-256 Verification Matrix

All 26 protected artifacts across Phase 5, Phase 6.1, Phase 6.2, Phase 6.3, Phase 7, and DuckDB matched their baseline SHA-256 hashes identically:

| Phase | Artifact | SHA-256 | Status |
| --- | --- | --- | :---: |
| Phase 5 | `tier1_random_forest.joblib` | `559936f8e200d67f29d56f6c40ad1748b15d012b25ca44ed6d1ce0d1120db3c9` | UNCHANGED |
| Phase 5 | `tier2_random_forest.joblib` | `d688a9e10b120f4998e8bff6dfd8ffca94c771db5db1947b0f71cd6360af9b2e` | UNCHANGED |
| Phase 5 | `tier1_random_forest_tuned.joblib` | `d73b79016012496809f9bc2dc3e05db686d5894f02a55d859a42f91052af1508` | UNCHANGED |
| Phase 5 | `tier2_random_forest_tuned.joblib` | `dafa999d181502d35098944c97009458f7f79bbefa3be0542e39b41b07ab40b5` | UNCHANGED |
| Phase 5 | `tier1_val_predictions_tuned.parquet` | `4214b9140711c2f1901acb2252b0d90ee25fe095bd240acc65ab4af2a5879f3e` | UNCHANGED |
| Phase 5 | `tier1_test_predictions_tuned.parquet` | `3d1a70b6d447544eb4d3f862a1fd9bcb490f28b2a8725e93ab1e76187402c9a2` | UNCHANGED |
| Phase 5 | `tier1_august_predictions_tuned.parquet` | `33c59e2e4438475dea175fbd39ede81e930eb953451fa35683a7c1fad5281e06` | UNCHANGED |
| Phase 5 | `tier2_val_predictions_tuned.parquet` | `f0f0bb8f4c86892b998e5cf30f9bb3feeaaaf7dd4873800133e3fd3cd5c2981e` | UNCHANGED |
| Phase 5 | `tier2_test_predictions_tuned.parquet` | `4b6825dedc8d601c831e4483e64ee896dc952fca71ff798dd007bc31427e72fb` | UNCHANGED |
| Phase 5 | `final_model_evaluation_metrics.csv` | `55dd8192df620d0e61d4d41255950db9335ddd6bce9939ddf0eeec424af5b2bd` | UNCHANGED |
| Phase 5 | `random_forest_champion_config.json` | `be420b65fcb92f08db72e0211137a97a519e49038eb7be37679070534549f740` | UNCHANGED |
| Phase 6.1 | `transit_hub_rankings.parquet` | `20e116891376696370c38c2dd919d8d59c95b981fb493270b29763adb2260aa7` | UNCHANGED |
| Phase 6.1 | `spatial_dbscan_assignments.parquet` | `3c7d40bcca545e142a69afd8b084166a372069a3f645360f76812fcdf9bab674` | UNCHANGED |
| Phase 6.1 | `phase6_1_stage2_metadata.json` | `4b4cd002a309538c0fe03eb7bd5e924cba5f00632198b57f15878085eb42f67f` | UNCHANGED |
| Phase 6.1 | `top100_hubs_config_a.csv` | `201682c6587678e2ef05fb6635e7ac7f16c1a2ed8c0f7d08aaf17671a9d1bc03` | UNCHANGED |
| Phase 6.2 | `corridor_cluster_assignments.parquet` | `7cd435ab1a6bd3e81cc0ebc2f3214723a8602b8240faa9a5ae882edd9d8625af` | UNCHANGED |
| Phase 6.2 | `buffer_overlap_similarity_matrix.parquet` | `bbf8a4371a5cca857f3a511b5aade91a4ac0792d1e27874c46f4d6ad09a190e4` | UNCHANGED |
| Phase 6.2 | `route_direction_jaccard_matrix.parquet` | `35a15c483a8e0e16f6c70aef698d9793b07b3aea8d12fdcdf283c7c3cc0d1b3e` | UNCHANGED |
| Phase 6.2 | `shared_consecutive_stop_sequences.parquet` | `dd7c031a0d4f1705065ec2226f79224083a60c4667b2aa38d4508fe7aba4e57f` | UNCHANGED |
| Phase 6.2 | `route_direction_geometries_metadata.parquet` | `e1089cc02e26045016b10bb7f9c3d16ba98a9c7a908275eee0aea8d5d4411d0c` | UNCHANGED |
| Phase 6.3 | `route_direction_connectivity_matrix.parquet` | `a13f84ea65404bb1fcd3ea856755a037f16f85a2c27498393d1f3adeb4d5b1cc` | UNCHANGED |
| Phase 6.3 | `route_ranker_feature_master.parquet` | `c26aa49a408b1d07c6a0e09f2b11879cf623a54da1c3625f1342b51d8937df85` | UNCHANGED |
| Phase 7 | `route_rankings_master.parquet` | `c440671d0b3888683969cb5fc11ccf7b581128a7296069019f76202b64f0093b` | UNCHANGED |
| Phase 7 | `route_ranking_explanations.json` | `56c29ef9c77b7517e8cb621a207600aa576148aef015a35a364da029a74a24b2` | UNCHANGED |
| Phase 7 | `ranking_sensitivity_analysis.parquet` | `fb41bcdf1e18da7978ae1666535d5868a92467143bd3d08b7ee5d71ef5d6790c` | UNCHANGED |
| DuckDB | `ai_routeranker.duckdb` | `ec0fd3626c6734fa2f96d6202a6d4966ae193598cc6e1ca84a828c295eee4209` | UNCHANGED |

## 2. Out-of-Scope & Methodology Confirmations
- No frontend modifications, no PostgreSQL activation/migration, no model retraining or tuning, no prediction regeneration, and no Phase 5/6/7 methodology changes occurred.
