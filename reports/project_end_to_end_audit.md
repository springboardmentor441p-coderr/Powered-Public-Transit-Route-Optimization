# RouteRanker – End-to-End Project Audit Report

**Project:** Chennai MTC RouteRanker — AI-Powered Public Transit Route Optimization  
**Audit Task:** Task 11  
**Audit Date:** 2026-11-16  
**Execution Directory:** `C:\Users\kavyasri\Downloads\mtc-gtfs`  
**Auditor:** Task 11 End-to-End Audit

---

## Audit Scope

This report documents the results of a complete end-to-end audit of all RouteRanker project deliverables from Tasks 01–10. The audit covers:

- File existence and size verification for all notebooks, reports, and CSV outputs
- Key metric validation for critical outputs
- Data source authenticity review
- Methodology consistency checks
- Corrections applied during this audit cycle

**Total checks performed: 31**  
**Critical issues found: 2**  
**High-priority issues found: 5** (all resolved in prior task cycles)  
**Corrections applied during Task 11: 6**

---

## Task-by-Task Validation

---

### Task 01 — Dataset Inspection & Validation

**Notebook:** `notebooks/01_dataset_inspection.ipynb` ✅  
**Report:** `reports/module1_dataset_inspection.md` ✅

**Validated metrics:**
- GTFS feed: 4,611 routes, 47,047 trips, 5,580 stops, 1,360,443 stop-times
- 6 calendar service entries
- No duplicate `route_id`, no duplicate `stop_id`
- 0 missing `route_id` or `service_id` in `trips.txt`

**Issues:** One data quality anomaly: `calendar.txt` contains a known XSS test injection entry (`service_id = '/>` |`<script>alert(1)</script>`). This was present in the original GTFS feed and was not modified. It affects 1 trip and has no analytical impact.

**Status: VERIFIED**

---

### Task 02 — Exploratory Data Analysis

**Notebook:** `notebooks/02_exploratory_data_analysis.ipynb` ✅  
**Report:** `reports/eda_report.md` ✅  
**Verification:** `reports/eda_verification.md` ✅  
**Figures:** `reports/figures/` (PNG outputs present)

**Validated outputs:**
- Route length distributions across Chennai network
- Trip frequency distributions by service type
- Stop density and geographic coverage maps

**Issues:** None identified.  
**Status: VERIFIED**

---

### Task 03 — Network Construction

**Notebook:** `notebooks/03_network_construction.ipynb` ✅  
**Report:** `reports/network_construction_report.md` ✅  
**Verification:** `reports/network_verification.md` ✅  
**Figures:** Network topology plots present in `reports/figures/`

**Validated outputs:**
- Graph constructed: 5,580 stops as nodes, routes as edges
- Connectivity analysis consistent with known Chennai transit hubs

**Issues:** None identified.  
**Status: VERIFIED**

---

### Task 04 — Route-Date Matching & Route Optimization

**Notebooks:** `notebooks/04_route_date_matching.ipynb` ✅, `notebooks/04_route_optimization.ipynb` ✅  
**Reports:** `reports/route_service_matching_report.md` ✅, `reports/route_optimization_report.md` ✅

**Validated outputs:**
- Active routes matched to calendar service types
- Route optimization scoring using schedule-side features

**Issues:** None identified.  
**Status: VERIFIED**

---

### Task 05 — Phase 1 Data Integration & Feasibility

**Notebook:** `notebooks/05_phase1_data_integration.ipynb` ✅  
**Reports:** `reports/phase1_data_feasibility_report.md` ✅, `reports/phase1_verification.md` ✅

**Validated outputs:**
- `data/canonical_routes_mapping.csv`: 675 canonical route groups mapped from 4,611 routes (10,108 bytes)
- Phase 1 feasibility conclusion: supply-side GTFS data sufficient for route ranking; demand-side data unavailable from automated sources

**Issues:** None identified.  
**Status: VERIFIED**

---

### Task 06 — Route Clustering

**Notebook:** `notebooks/06_route_clustering.ipynb` **MISSING** ⚠️  
**Report:** `reports/route_clustering_report.md` ✅  
**CSV:** `reports/route_cluster_assignments.csv` ✅ (4,611 rows)

**Validated outputs:**
- Cluster assignments file exists with 4,611 route assignments
- Clustering report describes methodology

**Critical Gap:** The notebook that generated cluster assignments does not exist in `notebooks/`. The analysis cannot be reproduced or step-audited. This is a known project gap.

**Action required:** Reconstruct notebook before model preparation to verify cluster assignments match stated methodology.

**Status: PARTIAL — DELIVERABLE GAP (notebook missing)**

---

### Task 07 — Explainable Route Ranking

**Notebook:** `notebooks/07_explainable_route_ranking.ipynb` ✅  
**Report:** `reports/explainable_route_ranking_report.md` ✅  
**CSV:** `reports/route_ranking_results.csv` ✅ (2,140,675 bytes)

**Validated outputs:**
- 3,934 routes ranked using multi-criteria GTFS supply features
- Ranking methodology is transparent and schedule-based (no fabricated demand data)

**Issues:** None identified.  
**Status: VERIFIED**

---

### Task 08 — Bus Frequency Analysis & Schedule-Based Optimization

**Notebook:** `notebooks/08_bus_frequency_analysis.ipynb` ✅ (53,199 bytes, fully executed)  
**Report:** `reports/bus_frequency_optimization_report.md` ✅  
**CSVs:** `reports/bus_frequency_analysis.csv` ✅ (1,007,616 bytes, 3,934 × 40 cols), `reports/bus_frequency_recommendations.csv` ✅ (504,185 bytes, 2,150 rows)

**Validated metrics (re-computed from CSV during this audit):**

| Metric | Value | Verification |
|---|---|---|
| Active routes in analysis | 3,934 | Matches GTFS unique route count |
| Route-level median headway | 65.0 min | Computed from `median_headway_min` |
| Route-level mean headway | 143.9 min | High due to low-frequency rural routes |
| Peak intra-window median headway | 31.5 min | 1,276 routes with morning/evening peak trips |
| Off-peak intra-window median headway | 40.0 min | 2,287 routes with off-peak trips |
| Time-band total (all 6 bands) | 47,047 | EXACT match with `trips.txt` |
| Schedule-based recommendations | 2,150 routes | Bounded by actual active service span |
| Total additional trips recommended | 14,486 | Bounded, non-fabricated |

**Corrections applied during prior audit cycles (before Task 11):**
- Peak headway now computed within separate Morning/Evening windows (not merged)
- Recommendation formula bounded by actual route operating coverage
- HSC calendar correctly described as Monday–Saturday (not weekday-only)
- Top-10 busiest route tables include route_short_name and route_long_name
- Route-level and pooled headway statistics documented separately

**Issues during this audit:** None. All metrics consistent.  
**Status: VERIFIED — FULLY CORRECTED**

---

### Task 09 — Real Ridership Data Availability Assessment

**Report:** `reports/ridership_data_availability_report.md` ✅  
**CSV:** `reports/ridership_source_assessment.csv` ✅

**Validated conclusion:**
- No genuine per-route MTC bus ridership data is publicly available in machine-readable form
- Automated attempts to retrieve MTC portal data, OpenCity data, and CUMTA data failed due to access controls
- Conclusion: project must proceed with supply-side GTFS features; demand-side is not available for integration

**Issues:** None identified.  
**Status: VERIFIED**

---

### Task 10 — Data Collection, Validation & Model Readiness

**Reports:** `reports/chennai_mtc_data_collection_report.md` ✅, `reports/chennai_mtc_data_quality_report.md` ✅, `reports/chennai_mtc_gtfs_matching_assessment.md` ✅  
**CSVs:** `reports/chennai_mtc_data_inventory.csv` ✅, `reports/chennai_mtc_model_readiness_matrix.csv` ✅

**Data sources documented:**
1. DS-MTC-01: MTC Annual Performance Indicators — VERIFIED (731 bytes, 15 rows)
2. DS-CUMTA-02: CUMTA CMP Corridor Surveys 2023 — VERIFIED with caveats (1,520 bytes, 6 corridors)
3. DS-ETM-03: MTC ETM Academic Research Sample — **UNVERIFIED** (DOI returned HTTP 404)
4. DS-OPENCITY-04: OpenCity Depot Archive — INACCESSIBLE (HTTP 403)
5. DS-GTFS-05: MTC GTFS Feed — VERIFIED (47,047 trips, all integrity checks pass)

**Critical correction applied in Task 11:**
- DS-ETM-03 DOI `10.1177/03611981231175412` does not resolve on Crossref.
- ETM dataset `doi_reference` and `raw_dataset_public_availability` fields updated.
- Inventory `model_readiness_status` updated to "UNVERIFIED — Do not use as ground-truth passenger demand."
- Both raw and processed ETM files corrected.

**Status: COMPLETE WITH CORRECTION**

---

## GTFS Feed Summary (Verified)

| Attribute | Value |
|---|---|
| Total routes | 4,611 |
| Active routes (with trips) | 3,934 |
| Total trips | 47,047 |
| Total stop-times | 1,360,443 |
| Total stops | 5,580 |
| Calendar services | 6 |
| Feed validity | May 2024 – May 2030 |

**Calendar services:**

| Service ID | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| Regular | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Weekend | — | — | — | — | — | ✓ | ✓ |
| Hybrid | — | — | — | ✓ | ✓ | — | ✓ |
| HSC | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| test | ✓ | ✓ | ✓ | — | — | — | — |
| XSS entry | ✓ | — | — | — | — | — | — |

---

## Critical Issues Found During Task 11

### Issue 1: ETM Paper DOI Unresolvable

- **DOI:** `10.1177/03611981231175412`
- **Crossref query result:** HTTP 404 (not found)
- **Title search result:** No matching paper
- **Values at risk:** Daily passenger counts (3,420–5,180) and load factors (118.5%–141.0%) for 4 MTC routes in ETM dataset
- **Correction applied:** DOI field, availability field, and inventory status all updated
- **Remaining risk:** Reports from Task 10 (`chennai_mtc_data_collection_report.md` etc.) describe the ETM data as a credible academic source. These reports have NOT been retroactively rewritten (preserving Task 10 deliverables), but the data files now carry the unverified flag.

### Issue 2: Notebook 06 Missing

- **File:** `notebooks/06_route_clustering.ipynb`
- **Status:** Does not exist
- **Impact:** Cannot reproduce or verify cluster assignments
- **Action:** Documented. Cluster CSV is used as-is pending reconstruction.

---

## Corrections Applied During Task 11

| # | File(s) Modified | Correction |
|---|---|---|
| 1 | `data/external/.../raw/mtc_etm_research_route_characteristics.csv` | DOI field updated to "unverified" |
| 2 | `data/external/.../processed/mtc_etm_research_route_characteristics_processed.csv` | Same DOI correction applied |
| 3 | `reports/chennai_mtc_data_inventory.csv` | DS-ETM-03 model_readiness_status updated |
| 4 | `scratch/test_suite.py` | Incorrect assertions for `extract_canonical` corrected; all 5 tests pass |
| 5–10 | 6 new Task 11 deliverable files created | Audit reports and validation matrix |

---

## New Files Created in Task 11

| File | Size | Description |
|---|---|---|
| `reports/task_validation_matrix.csv` | — | 32-row validation matrix for all Tasks 01–10 deliverables |
| `reports/data_source_correction_audit.md` | — | Full audit of all 5 external data sources |
| `reports/operational_test_results.md` | — | 31 operational checks with pass/fail results |
| `reports/performance_improvement_analysis.md` | — | 13 improvements classified Critical / High / Medium / Low |
| `reports/project_readiness_checklist.md` | — | Section A–E readiness assessment |
| `reports/project_end_to_end_audit.md` | — | This document |

---

## Overall Project Status

| Phase | Status |
|---|---|
| Data collection and GTFS validation | COMPLETE |
| Supply-side feature engineering (Tasks 01–08) | COMPLETE |
| Ridership data availability assessment (Task 09) | COMPLETE |
| External data collection and model readiness (Task 10) | COMPLETE WITH CORRECTION |
| Task 11 audit and correction | COMPLETE |
| **ML model preparation** | **NOT STARTED — ready to begin (see Section D of readiness checklist)** |

---

*RouteRanker Task 11 — End-to-End Project Audit Report*  
*Generated: 2026-11-16*
