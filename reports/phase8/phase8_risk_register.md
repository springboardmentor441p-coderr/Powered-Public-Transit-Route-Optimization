# AI_RouteRanker — Milestone 8: Backend API Integration
## Phase 8 Architectural Risk Register & Mitigation Strategy

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Backend API Integration  
**Document:** Technical Risk Assessment, Failure Mode Analysis & Security Guardrails  
**Author:** AI_RouteRanker Engineering & Analytics Team  
**Date:** 2026-11-25T17:31:00+05:30  
**Hardware Environment:** 8 GB RAM Developer Laptop (Strict Memory Guard)  
**Status:** APPROVED RISK REGISTER (PLANNING PHASE)  

---

## 1. Risk Assessment Matrix & Prioritization

The following matrix classifies technical risks identified during the Milestone 8 requirements discovery across Severity, Likelihood, Impact, and Mitigation Readiness:

| Risk ID | Risk Description | Severity | Likelihood | Impact Area | Risk Level |
| :---: | :--- | :---: | :---: | :--- | :---: |
| **R-01** | **Memory Exhaustion on 8 GB Laptop** | **CRITICAL** | Medium | System stability, OOM killer crash | **HIGH** |
| **R-02** | **DuckDB Read Concurrency & Lock Contention** | **HIGH** | Low | Query deadlocks, 500 errors | **MEDIUM** |
| **R-03** | **Parquet Schema Drift & Deserialization Errors** | **MEDIUM** | Low | Pydantic validation failures | **MEDIUM** |
| **R-04** | **Specialized Route Headway NaN Serialization Crash**| **HIGH** | Medium | Unhandled JSON NaN errors on Routes 10, 130, N5 | **MEDIUM** |
| **R-05** | **Path Traversal & Arbitrary File Access** | **CRITICAL** | Low | Security vulnerability, file disclosure | **LOW** |
| **R-06** | **CORS & Reverse Proxy Mismatches** | **MEDIUM** | Medium | Frontend dashboard connectivity failure | **MEDIUM** |
| **R-07** | **Accidental Mutation of Protected Baseline Assets** | **CRITICAL** | Low | Data corruption, invalidation of M5/6/7 | **LOW** |
| **R-08** | **Leakage of Internal System Paths & Tracebacks** | **MEDIUM** | Low | Information disclosure in API error responses | **LOW** |

---

## 2. In-Depth Risk Analysis & Prevention Protocols

### Risk R-01: Memory Exhaustion on 8 GB RAM Laptop
- **Root Cause:** Ingestion or reading of large tabular artifacts (e.g. 10k stop records or 1.12M ridership rows) into unconstrained in-memory dataframes simultaneously across multiple worker threads.
- **Preventive Controls:**
  1. *Strict Column Pruning:* The `ParquetRepository` specifies `columns=[...]` on every read, loading only the 3-5 necessary columns rather than the full 44 or 62 columns.
  2. *In-Memory Singletons:* Core route and ranking tables ($< 3.5\text{ MB}$ total) are loaded into memory exactly once at application startup. Subsequent requests read from RAM without allocating new heap memory.
  3. *DuckDB Memory Cap:* DuckDB queries enforce `PRAGMA max_memory='256MB'` and `PRAGMA threads=2`.
  4. *Circuit Breaker Middleware:* A lightweight middleware checks `psutil` or `ctypes` memory before processing heavy queries; if available RAM is $< 500\text{ MB}$, it sheds load with HTTP 503 rather than crashing the system.

---

### Risk R-02: DuckDB Concurrency & Database Locking
- **Root Cause:** By default, opening a DuckDB file without explicit read-only flags attempts to acquire a write lock, causing errors if another process has the database open.
- **Preventive Controls:**
  1. All backend connections MUST explicitly pass `read_only=True`:
     ```python
     duckdb.connect(str(settings.DUCKDB_PATH), read_only=True)
     ```
  2. In read-only mode, DuckDB allows unlimited concurrent read queries across threads without file locking.
  3. Strict zero-write policy enforced across all API endpoints.

---

### Risk R-03: Parquet Schema Drift & Pydantic Validation Failures
- **Root Cause:** Discrepancies between physical Parquet column naming (e.g. `corridor_duplication_index` vs `corridor_duplication_index_norm`) and Pydantic field schemas.
- **Preventive Controls:**
  1. All Pydantic models in `backend/app/schemas/` are constructed using the verified 62-column schema of `route_rankings_master.parquet` and 44-column schema of `route_ranker_feature_master.parquet`.
  2. Pydantic models utilize `model_config = ConfigDict(populate_by_name=True, extra="ignore")` to prevent crashes if extra columns exist.

---

### Risk R-04: Specialized Route Headway NaN Serialization Failures
- **Root Cause:** Python standard `json.dumps()` or Pydantic may serialize `float('nan')` to non-compliant JSON `NaN`, which causes JSON parsers in modern browsers to fail (`JSON.parse: Unexpected token N`).
- **Preventive Controls:**
  1. All Pydantic models define `am_headway_min` as `Optional[float] = None`.
  2. The service layer converts all `np.isnan(val)` occurrences to Python `None` prior to serialization, ensuring clean JSON `null` output in the HTTP payload.
  3. Automated regression tests explicitly test Routes 10, 130, and N5 to verify that `am_headway_min` is rendered as JSON `null` and that `is_headway_missing` is `true`.

---

### Risk R-05: Path Traversal & Arbitrary File Access Vulnerabilities
- **Root Cause:** Endpoints accepting path parameters (e.g. `GET /api/routes/{route_id}`) being exploited with directory traversal payloads like `../../etc/passwd` or `../artifacts/private`.
- **Preventive Controls:**
  1. Route IDs are strictly validated via regex: `^[a-zA-Z0-9_-]{1,10}$`. Any string containing `/`, `\`, or `.` is rejected immediately with HTTP 400 Bad Request.
  2. Route lookups query an in-memory dictionary or Pandas index, completely eliminating filesystem string concatenation for entity retrieval.

---

### Risk R-06: CORS & Reverse Proxy Mismatches
- **Root Cause:** The React development server on `http://localhost:5173` fails to connect to FastAPI on `http://127.0.0.1:8000` due to CORS origin headers or proxy path rewrites.
- **Preventive Controls:**
  1. FastAPI `CORSMiddleware` in `backend/app/main.py` explicitly allows `http://localhost:5173`, `http://127.0.0.1:5173`, and `http://localhost:3000`.
  2. Vite reverse proxy in `frontend/vite.config.ts` transparently forwards `/api` to `http://127.0.0.1:8000/api` with `changeOrigin: true`.
  3. Both direct CORS access and proxied relative path access will be supported and verified in tests.

---

### Risk R-07: Accidental Mutation of Protected Baseline Assets
- **Root Cause:** Inadvertent write calls, cache writes, or temporary test file generation inside protected directories (`data/`, `models/`, `artifacts/ranking_features/`, `artifacts/ranking_results/`).
- **Preventive Controls:**
  1. All file handles in repositories use read-only modes (`"rb"`, `"r"`).
  2. Automated test suites execute SHA-256 pre-flight and post-flight verification across all 23 protected baseline assets. Any hash deviation immediately fails the build.

---

### Risk R-08: Information Disclosure & Internal Path Leaks
- **Root Cause:** Uncaught Python exceptions returning raw stack traces containing absolute local filesystem paths (e.g. `D:\B.TECH_PROJECTS\...`) to client browsers.
- **Preventive Controls:**
  1. Global FastAPI exception handler intercepts all unhandled `Exception` instances.
  2. Internal tracebacks are logged to server console/file only; the client receives a sanitized RFC 7807 error response with a unique tracking error ID.
  3. `DEBUG` mode is configured to default to `False` in production settings.
