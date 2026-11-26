# Deployment Remediation Report — AI_RouteRanker (Render + Vercel)

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Audit Reference:** `reports/deployment/PRODUCTION_READINESS_AUDIT.md`  
**Date:** 2026-11-26  
**Status:** **CODE & CONFIG REMEDIATED — READY FOR RENDER PERSISTENT DISK PROVISIONING & DEPLOYMENT**

---

## 1. Files Changed & Exact Corrections

| File | Finding(s) | Exact Change |
| --- | --- | --- |
| `backend/requirements.txt` | `B-01` | Added `duckdb>=1.1.0`, `pandas>=2.2.0`, `numpy>=2.1.0`, and `pyarrow>=18.0.0` (verified installed versions: `duckdb 2.0.0`, `pandas 3.1.0`, `numpy 2.4.6`, `pyarrow 26.0.0`). |
| `.python-version` *(new)* | `W-04` | Created project-level Python version pin (`3.11.2`) for Render. |
| `backend/app/core/config.py` | `W-01`, `W-02`, `W-03` | Added `_parse_cors_origins` (`@field_validator("CORS_ORIGINS", mode="before")`) accepting both JSON arrays and comma-separated origin strings; added `_resolve_dependent_paths` (`@model_validator(mode="after")`) so overriding `DATA_DIR` / `ARTIFACTS_DIR` dynamically redirects `DUCKDB_PATH` and all 19 `artifacts/*` paths unless individually overridden; added `runtime_required_paths` property; preserved all local defaults (`ENVIRONMENT="development"`, `DEBUG=True`). |
| `backend/app/schemas/health.py` | `W-04` | Added `data_ready: bool` and `missing_artifacts_count: int` fields to `HealthCheckResponse`. |
| `backend/app/api/endpoints.py` | `W-04` | Updated `GET /api/health` to check `settings.runtime_required_paths` existence without reading data into memory. |
| `.env.example` | `W-01` | Updated `CORS_ORIGINS` template to JSON array format `["http://localhost:5173","http://127.0.0.1:5173"]`. |

---

## 2. Production Environment Variables (Render & Vercel)

### Render (FastAPI Web Service)
- **Build Command:** `pip install -r backend/requirements.txt`
- **Start Command:** `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`
- **Environment Variables:**
  - `ENVIRONMENT=production`
  - `DEBUG=false`
  - `CORS_ORIGINS=["https://<your-vercel-domain>.vercel.app"]`
  - `DATA_DIR=/var/data/processed`
  - `ARTIFACTS_DIR=/var/data/artifacts`
  - *(Optional individual overrides if needed: `DUCKDB_PATH`, `FEATURE_MASTER_PATH`, `RANKINGS_MASTER_PATH`, `EXPLANATIONS_PATH`, `SENSITIVITY_PATH`, `TRANSIT_HUB_RANKINGS_PATH`, `DBSCAN_ASSIGNMENTS_PATH`, `PHASE6_1_METADATA_PATH`, `TOP100_HUBS_CONFIG_A_PATH`, `CORRIDOR_CLUSTERS_PATH`, `BUFFER_SIMILARITY_PATH`, `JACCARD_SIMILARITY_PATH`, `SHARED_SEQUENCES_PATH`, `GEOMETRIES_META_PATH`, `CONNECTIVITY_MATRIX_PATH`, `RF_TIER1_VAL_PRED_PATH`, `RF_TIER1_TEST_PRED_PATH`, `RF_TIER1_AUG_PRED_PATH`, `RF_TIER2_VAL_PRED_PATH`, `RF_TIER2_TEST_PRED_PATH`, `RF_FINAL_METRICS_CSV_PATH`, `RF_CHAMPION_CONFIG_PATH`)*

### Vercel (React + Vite Frontend)
- **Root Directory:** `frontend`
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Environment Variable:** `VITE_API_BASE_URL=https://<your-render-service>.onrender.com`

---

## 3. Render Persistent Disk Directory Structure & Data-Copy Procedure

Provision a **≥ 2 GB** Render Persistent Disk mounted at `/var/data` (`964.33 MB` required). Upload the local files (without committing them to Git) into the exact layout below:

```text
/var/data/
├── processed/
│   └── ai_routeranker.duckdb                              (960.512 MB)
└── artifacts/
    ├── ranking_features/
    │   ├── route_ranker_feature_master.parquet            (0.060 MB)
    │   └── route_direction_connectivity_matrix.parquet    (0.007 MB)
    ├── ranking_results/
    │   ├── route_rankings_master.parquet                  (0.099 MB)
    │   ├── route_ranking_explanations.json                (0.760 MB)
    │   └── ranking_sensitivity_analysis.parquet           (0.007 MB)
    ├── clustering/
    │   ├── transit_hub_rankings.parquet                   (0.485 MB)
    │   ├── spatial_dbscan_assignments.parquet             (0.545 MB)
    │   ├── phase6_1_stage2_metadata.json                  (0.003 MB)
    │   └── top100_hubs_config_a.csv                       (0.009 MB)
    ├── route_clustering/
    │   ├── corridor_cluster_assignments.parquet           (0.020 MB)
    │   ├── buffer_overlap_similarity_matrix.parquet       (0.303 MB)
    │   ├── route_direction_jaccard_matrix.parquet         (0.183 MB)
    │   ├── shared_consecutive_stop_sequences.parquet      (0.040 MB)
    │   └── route_direction_geometries_metadata.parquet    (0.018 MB)
    └── random_forest/
        ├── tier1_val_predictions_tuned.parquet            (0.534 MB)
        ├── tier1_test_predictions_tuned.parquet           (0.470 MB)
        ├── tier1_august_predictions_tuned.parquet         (0.072 MB)
        ├── tier2_val_predictions_tuned.parquet            (0.061 MB)
        └── tier2_test_predictions_tuned.parquet           (0.138 MB)
```

*(Note: `reports/modeling/random_forest/final_model_evaluation_metrics.csv` and `random_forest_champion_config.json` are already tracked in Git on `naga-sai-m`.)*

### Data-Copy Procedure (Non-Destructive)
1. Attach a `2 GB` Persistent Disk at `/var/data` in the Render service dashboard.
2. Connect via Render Shell / SSH or `scp` from local machine (preserving all local files intact) and copy `data/processed/ai_routeranker.duckdb` → `/var/data/processed/ai_routeranker.duckdb` and `artifacts/*` → `/var/data/artifacts/`.
3. Set `DATA_DIR=/var/data/processed` and `ARTIFACTS_DIR=/var/data/artifacts` in Render environment variables and verify `GET /api/health` returns `"data_ready": true, "missing_artifacts_count": 0`.

---

## 4. Verification Commands & Results

- **`verify_deploy_config.py`:** Verified all runtime imports (`duckdb`, `pandas`, `numpy`, `pyarrow`, `fastapi`, `uvicorn`, `pydantic`, `pydantic_settings`, `sqlalchemy`, `httpx`), all `22` local runtime paths (`missing_artifacts_count=0`, `data_ready=true`), overridden `DATA_DIR=/var/data/processed` + `ARTIFACTS_DIR=/var/data/artifacts` resolution, and both JSON and CSV `CORS_ORIGINS` parsing.
- **`python -m unittest discover -s backend/tests -v`:** **60/60 passed** (`5.714s`) — includes `503` missing-artifact failure-mode checks and all Stage 1–2E API tests.
- **`python -m unittest discover tests`:** **205/205 passed** (`9.905s`).
- **Scope Preserved:** Zero frontend files modified, zero ML/ranking/data files modified, nothing committed, pushed, or deployed.

---

## 5. Remaining External / Operational Prerequisites
- **Render Persistent Disk Provisioning (`B-02` operational step):** Code/config now supports `/var/data` overrides cleanly, but the Render Persistent Disk itself must still be provisioned and populated with the `964.33 MB` files during actual Render setup.
- **GitHub Push (User Action):** Per restrictions, these remediation edits remain local in `D:\B.TECH_PROJECTS\AI_RouteRanker` and have not been committed or pushed to `naga-sai-m`.
