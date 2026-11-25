# 02 — Backend & REST API Audit (Phase B)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Audit Date:** 2026-11-25  

---

## 1. Startup, Middleware & OpenAPI Discovery
- FastAPI started cleanly via `uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000` with zero exceptions.
- `GET /` (`200`), `GET /api/health` (`200`), `GET /openapi.json` (`200`), `GET /docs` (`200`), `GET /redoc` (`200`).
- Discovered **17 registered paths** (`/` + `/api/health` + 15 `/api/v1/*`) and **41 component schemas** directly from `/openapi.json`.

## 2. Endpoint Contract, Validation & Data Integrity Matrix
All 37 endpoint test cases (valid, missing optional, invalid params, out-of-range pagination, empty results, unknown IDs) returned their exact expected HTTP status codes (`200`/`400`/`404`/`422`) with structured JSON and zero path/traceback leakage:

| Endpoint Family | Valid | Invalid / Out-of-Range | Empty / Unavailable | Unknown ID | Underlying Source Verified |
| --- | :---: | :---: | :---: | :---: | --- |
| `/` & `/api/health` | 200 | — | — | — | App metadata & settings |
| `/api/v1/routes` & `/{route_id}` | 200 (133 routes) | 400 (`mode=invalid`), 422 (`limit=151`) | 200 (`search=ZZZZZ_NONE`) | 404 (`NOPE_999`) | `route_ranker_feature_master.parquet` |
| `/api/v1/rankings/{bus,rail,unified}` | 200 (125 / 8 / 133) | — | 200 (`min_rank=999`) | — | `route_rankings_master.parquet` |
| `/api/v1/rankings/routes/{id}/explanation` & `/sensitivity` | 200 (60 scenarios) | 400 (`track=BAD_TRACK`) | — | 404 (`NOPE_999`) | `route_ranking_explanations.json`, `ranking_sensitivity_analysis.parquet` |
| `/api/v1/ridership/routes/{id}/timeseries` | 200 (Bus `151`) | 400 (`start > end`) | 200 (Rail `Red`: `ridership_available=false`) | 404 (`NOPE_999`) | `ai_routeranker.duckdb` (`analytical.daily_ridership`) |
| `/api/v1/spatial/hubs{/top}` & `/clusters/summary` | 200 (Top-100, Stop `4732` #100) | 400 (`config=z`, invalid bbox) | — | — | `transit_hub_rankings.parquet`, `spatial_dbscan_assignments.parquet`, `top100_hubs_config_a.csv` |
| `/api/v1/corridors/clusters` & `/routes/{id}/co-routing` | 200 (261 patterns) | 400 (`cluster_type=bad`) | — | 404 (`NOPE_999`) | Phase 6.2 & 6.3 corridor Parquets |
| `/api/v1/forecasting/historical` & `/summary` | 200 (`historical_evaluation_only`, `future_forecasting_supported=false`) | 400 (`tier2+august_holdout`, whitespace `route_id`) | 200 (out-of-window) | — | 5 tuned RF Parquets, `final_model_evaluation_metrics.csv`, `random_forest_champion_config.json` |
