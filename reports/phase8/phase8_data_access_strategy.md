# AI_RouteRanker — Milestone 8: Backend API Integration
## Phase 8 Data Access & Performance Optimization Strategy

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Document:** Data Access Strategy, Technology Trade-Offs & Memory Optimization  
**Author:** AI_RouteRanker Engineering & Analytics Team  
**Date:** 2026-11-25T17:28:00+05:30  
**Hardware Environment:** 8 GB RAM Developer Laptop (Strict Memory Guard)  
**Status:** APPROVED STRATEGY SPECIFICATION (PLANNING PHASE)  

---

## 1. Storage Technology Trade-Off Evaluation

To determine the most efficient, reliable, and resource-conservative data access layer for AI_RouteRanker, four distinct data serving options were evaluated against the system's operational constraints:

| Evaluation Criteria | PostgreSQL (Relational) | DuckDB (Embedded OLAP) | Direct Parquet (Columnar) | Precomputed JSON (Indexed) |
| :--- | :--- | :--- | :--- | :--- |
| **Current Availability** | Uninstantiated (No active daemon) | **100% Populated (1.12M rows)** | **100% Populated & Verified** | **100% Populated & Verified** |
| **Daemon Overhead** | High ($\sim 150 - 250\text{ MB}$ RAM) | **Zero (In-process library)** | **Zero (In-process reader)** | **Zero (In-process dict)** |
| **Query Latency** | $15 - 40\text{ ms}$ (Network socket) | **$5 - 20\text{ ms}$ (Vectorized)** | **$< 5\text{ ms}$ (Direct memory)**| **$< 1\text{ ms}$ (O(1) hash map)** |
| **Data Duplication Risk**| Severe (Requires ETL replication)| **Zero (Direct read on disk)** | **Zero (Direct read on disk)** | **Zero (Direct read on disk)** |
| **Memory Footprint** | External process burden | **Transient ($< 50\text{ MB}$ query)**| **Minimal ($< 2\text{ MB}$ cached)** | **Negligible ($< 5\text{ MB}$ cached)** |
| **Read-Only Safety** | Connection configuration | **Strict `read_only=True`** | **Strict File Read (`rb`)** | **Strict File Read (`r`)** |
| **Best-Fit Workload** | High-concurrency OLTP writes | Aggregated historical timeseries | Filtered tabular route rankings | Explanations & audit metadata |

### Architectural Decision: Hybrid File-First & Embedded Engine Strategy
1. **Direct Parquet Reading for Tabular Analytics:** Serves route directories, multi-criteria rankings, sensitivity scenarios, and corridor profiles directly from verified Parquet artifacts. The total size of all ranking Parquet files combined is under $1\text{ MB}$, making them ideal for ultra-fast, in-memory singleton caching.
2. **Read-Only DuckDB for Historical Timeseries:** Serves long-term ridership trends and stop-time aggregations from `data/processed/ai_routeranker.duckdb`. DuckDB's vectorized query engine aggregates 1.12 million rows in under $20\text{ ms}$ using parameterized SQL without loading the full table into application memory.
3. **Precomputed JSON for Explanations & Metadata:** Serves structured natural-language narratives and provenance metadata directly from precomputed JSON files, guaranteeing instant $O(1)$ response times.
4. **De-prioritization of PostgreSQL:** In accordance with user directives, PostgreSQL is not instantiated or written to during Phase 8. Avoiding PostgreSQL eliminates external database daemon dependencies and saves $\sim 200\text{ MB}$ of system RAM.

---

## 2. Artifact-to-Endpoint Serving Matrix

The following matrix documents the authoritative data source, access mechanism, caching policy, and expected latency for every API domain:

| API Group / Endpoint | Physical Data Source | Access Technology | Caching Policy | Target Response Latency |
| :--- | :--- | :--- | :--- | :---: |
| **`/api/routes`** | `artifacts/ranking_features/route_ranker_feature_master.parquet` | Pandas / PyArrow | In-Memory Singleton | $< 15\text{ ms}$ |
| **`/api/routes/{id}`** | `artifacts/ranking_features/route_ranker_feature_master.parquet` | Pandas / Index Lookup | In-Memory Singleton | $< 5\text{ ms}$ |
| **`/api/rankings/bus`** | `artifacts/ranking_results/route_rankings_master.parquet` | Pandas Column Filter (`track='BUS_PRIORITY'`) | In-Memory Singleton | $< 10\text{ ms}$ |
| **`/api/rankings/rail`**| `artifacts/ranking_results/route_rankings_master.parquet` | Pandas Column Filter (`track='RAIL_PRIORITY'`) | In-Memory Singleton | $< 5\text{ ms}$ |
| **`/api/rankings/unified`**| `artifacts/ranking_results/route_rankings_master.parquet` | Pandas Column Filter (`track='UNIFIED_SUPPLY'`) | In-Memory Singleton | $< 10\text{ ms}$ |
| **`/api/rankings/routes/{id}/explanation`**| `artifacts/ranking_results/route_ranking_explanations.json` | JSON Dict Lookup `(track, route_id)` | In-Memory Singleton | $< 2\text{ ms}$ |
| **`/api/rankings/sensitivity`**| `artifacts/ranking_results/ranking_sensitivity_analysis.parquet` | Pandas Read | In-Memory Singleton | $< 5\text{ ms}$ |
| **`/api/spatial/hubs/top`**| `artifacts/clustering/top100_hubs_config_a.csv` | Pandas CSV Read | In-Memory Singleton | $< 5\text{ ms}$ |
| **`/api/spatial/hubs`** | `artifacts/clustering/transit_hub_rankings.parquet` | PyArrow Columnar Stream | Lazy On-Demand Reader | $< 40\text{ ms}$ |
| **`/api/corridors/clusters`**| `artifacts/route_clustering/corridor_cluster_assignments.parquet`| Pandas Read | In-Memory Singleton | $< 10\text{ ms}$ |
| **`/api/forecasting/summary`**| `artifacts/random_forest/tier1_august_predictions_tuned.parquet` | Pandas Aggregation | LRU Cache (1 hour) | $< 15\text{ ms}$ |
| **`/api/ridership/routes/{id}/timeseries`**| `data/processed/ai_routeranker.duckdb` (`daily_ridership`) | DuckDB Parameterized SQL | Connection Pool + LRU | $< 25\text{ ms}$ |
| **`/api/metadata/phases`**| `artifacts/ranking_results/phase7_metadata.json` | JSON Read | In-Memory Singleton | $< 2\text{ ms}$ |

---

## 3. Memory Safety & Laptop Resource Guardrails

Executing on an 8 GB RAM laptop requires rigorous memory safety controls:

### 3.1 Resident Set Size (RSS) Budget
- **Operating System + Background Apps:** $\sim 5.5 - 6.0\text{ GB}$
- **Available Working Memory:** $\sim 2.0 - 2.5\text{ GB}$
- **FastAPI Backend Budget:** Maximum **$350\text{ MB}$ RSS**.
- **Memory Guard:** The backend will enforce a health-check circuit breaker: if available system memory falls below $500\text{ MB}$, non-essential heavy analytics queries return HTTP 503 to protect the operating system from thrashing.

### 3.2 In-Memory Singleton Lifecycle
Instead of re-reading Parquet files from disk on every HTTP request, immutable master tables are loaded into memory exactly once at application startup or upon first query (lazy initialization):
- `route_ranker_feature_master.parquet` (133 rows $\times$ 44 cols): **$0.45\text{ MB}$ RAM**
- `route_rankings_master.parquet` (266 rows $\times$ 62 cols): **$0.85\text{ MB}$ RAM**
- `route_ranking_explanations.json` (266 items): **$1.80\text{ MB}$ RAM**
- `ranking_sensitivity_analysis.parquet` (60 rows $\times$ 9 cols): **$0.05\text{ MB}$ RAM**
- `top100_hubs_config_a.csv` (100 rows $\times$ 14 cols): **$0.12\text{ MB}$ RAM**
- **Total In-Memory Working Set for Core Rankings:** **$< 3.5\text{ MB}$ RAM**.
This negligible memory footprint guarantees that 99% of frontend dashboard queries will be served from sub-millisecond RAM caches without touching the disk or threatening system memory.

### 3.3 DuckDB Read-Only Concurrency & Zero Data Duplication
- **Connection Management:** DuckDB connections are opened with `read_only=True`:
  ```python
  con = duckdb.connect(database="data/processed/ai_routeranker.duckdb", read_only=True)
  ```
- **Thread Safety:** DuckDB Python read-only connections are thread-safe and support concurrent query execution across multiple FastAPI worker threads without lock contention.
- **Memory Bounding:** DuckDB internal buffer cache is bounded to $256\text{ MB}$ via `PRAGMA max_memory='256MB'`, preventing analytical queries from consuming excessive system RAM.
- **Zero Duplication:** No ridership records are copied from DuckDB into PostgreSQL or redundant CSVs.
