# AI_RouteRanker — Stage 2B Audit Correction: Canonical Top-100 Tie-Breaking Report

**Project:** `D:\B.TECH_PROJECTS\AI_RouteRanker`  
**Milestone:** 8 — Module 6 Backend API Integration  
**Scope:** Resolving Stage 2B Independent Audit Low Finding L-01  
**Date:** 2026-11-25T19:08:00+05:30  
**Status:** COMPLETE & VERIFIED (Stage 2C Not Started)  

---

## 1. Root Cause

The Stage 2B independent audit (L-01) identified that `transit_hub_rankings.parquet` contains a 2-way tie at `rank_config_a == 100` (`score_config_a = 0.388844`):
- Stop `17046` (*Adams & Clark*, `rank_config_a = 100`)
- Stop `4732` (*Adams & State*, `rank_config_a = 100`)

Additionally, inspection of `top100_hubs_config_a.csv` revealed that tied groups throughout the top 100 (e.g., ranks 5, 12, 91, and 100) follow the canonical CSV's own row order rather than lexicographical `stop_id` sorting. Sorting by `[rank_config_a, "stop_id"]` in `SpatialService.get_top_hubs` therefore placed `"17046"` at position 100 instead of `"4732"`.

---

## 2. Correction Details

- **`backend/app/repositories/spatial_repository.py`**:
  - Added `top100_config_a_path` parameter (defaulting to `settings.TOP100_HUBS_CONFIG_A_PATH`).
  - Added `get_top100_config_a_order()` with `threading.Lock` double-checked lazy caching, reading only `stop_id` from `top100_hubs_config_a.csv` and mapping missing/corrupt CSV errors to `ArtifactUnavailableError` (HTTP 503).
- **`backend/app/services/spatial_service.py`**:
  - Updated `get_top_hubs(config, limit, offset)`:
    - For `config == "a"`: Joins `transit_hub_rankings.parquet` against the canonical ordered `stop_id` list from `top100_hubs_config_a.csv` and sorts strictly by canonical CSV row index (`_canonical_order`) before slicing `[offset : offset + limit]`.
    - For `config` in `{"b", "c"}` (where no separate canonical top-100 CSV exists): Preserves the verified deterministic `[rank_col, "stop_id"]` ascending sort `.head(100)`.

### Modified File Hashes

| File Path | Pre-Correction SHA-256 | Post-Correction SHA-256 |
| :--- | :--- | :--- |
| `backend/app/services/spatial_service.py` | `ea01fe00f71d67e58067442d2c35d017922f43de3cc5b6c672e672263658eba2` | `5715337eb690a6c8c444ffb6dcba1c518cac4104059fd0428bc5c5a00ff1c0ba` |
| `backend/app/repositories/spatial_repository.py` | `0b129b8b78cc3d1d4f86cb4db501ee806005e74c5f8e5c186ecb1c573ab21da6` | `2cfd1e81836be5812e8d697e1a6c942ea6dc28490b9743033e1e562cda8886b7` |

---

## 3. Canonical Ordering & Regression Test Results

Added `test_top_100_config_a_exact_canonical_tie_breaking_and_pagination` in `backend/tests/test_spatial_api.py`, verifying:
- `GET /api/v1/spatial/hubs/top?config=a&limit=100&offset=0` matches all 100 `stop_id`s in `top100_hubs_config_a.csv` in exact sequence.
- Stop `4732` is at index 99 (position 100), and Stop `17046` is excluded.
- Paginated slice (`offset=75, limit=25`) preserves the exact canonical sequence ending with Stop `4732`.
- Configs `b` and `c`, bounding-box filters, and DBSCAN cluster filters remain unchanged.

| Suite | Command | Result | Duration |
| :--- | :--- | :---: | :---: |
| **Backend Tests** | `python -m unittest discover -s backend/tests -v` | **36 / 36 PASS** | $1.937\text{s}$ |
| **Full Project Suite** | `python -m unittest discover tests` | **205 / 205 PASS** | $9.371\text{s}$ |

---

## 4. Artifact Integrity & Remaining Limitations

- All Phase 6.1 (`transit_hub_rankings.parquet`, `spatial_dbscan_assignments.parquet`, `phase6_1_stage2_metadata.json`, `top100_hubs_config_a.csv`), Phase 6.2, Phase 6.3, Phase 7, and DuckDB (`ec0fd362...`) SHA-256 hashes matched 100% bit-for-bit.
- **Remaining Limitation:** Canonical Phase 6.1 produced `top100_hubs_config_a.csv` only for configuration A; configurations B and C continue to use deterministic `[rank_col, "stop_id"]` tie-breaking.
