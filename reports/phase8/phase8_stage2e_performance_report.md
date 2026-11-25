# Phase 8, Stage 2E — Performance and Concurrency Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Methodology:** FastAPI `TestClient(app)` with all 6 repository `@lru_cache()` caches cleared before cold measurement, followed by 3-run warm averages and a 10-thread mixed cross-stage concurrency burst.  
**Date:** 2026-11-25  

---

## 1. Endpoint Latency Measurements

| Endpoint | Cold Cache (ms) | Warm Avg (ms) |
| --- | ---: | ---: |
| `GET /api/health` | 15.82 | 9.75 |
| `GET /api/v1/routes?limit=25` | 164.35 | 32.69 |
| `GET /api/v1/rankings/bus?limit=25` | 157.84 | 40.72 |
| `GET /api/v1/rankings/rail?limit=25` | 34.70 | 34.55 |
| `GET /api/v1/rankings/unified?limit=25` | 56.11 | 42.48 |
| `GET /api/v1/rankings/routes/151/explanation` | 20.98 | 16.11 |
| `GET /api/v1/rankings/sensitivity` | 54.64 | 40.67 |
| `GET /api/v1/ridership/routes/151/timeseries?granularity=monthly` | 106.62 | 68.93 |
| `GET /api/v1/spatial/hubs/top?config=a&limit=100` | 85.64 | 57.00 |
| `GET /api/v1/spatial/hubs?eligible_only=true&limit=25` | 260.96 | 79.53 |
| `GET /api/v1/spatial/clusters/summary` | 23.39 | 14.09 |
| `GET /api/v1/corridors/clusters?limit=25` | 115.16 | 72.80 |
| `GET /api/v1/corridors/routes/151/co-routing` | 187.49 | 84.95 |
| `GET /api/v1/forecasting/historical?tier=tier1&period=august_holdout&limit=50` | 58.99 | 33.91 |
| `GET /api/v1/forecasting/historical/summary` | 169.31 | 16.93 |

## 2. Concurrency & Memory
- **10-Thread Mixed Cross-Stage Concurrency:** `377.26 ms` total wall time (10/10 HTTP 200).
- **Traced Python Memory (`tracemalloc`):** `6.60 MB` current, `7.90 MB` peak.
- **Process RSS:** Unverified (`psutil` is not installed in the Python environment).

## 3. Comparison with Earlier Stage Reports
- Warm latencies across all 15 endpoints (`9.75 ms` – `84.95 ms`) align closely with earlier Stage 1–2D reports. Cold repository initialization (`23 ms` – `261 ms`) reflects one-time Parquet/DuckDB/JSON loading per repository; earlier Stage 2D cold-process measurements (`464.41 ms`) included first-time Python/PyArrow/FastAPI module imports.
