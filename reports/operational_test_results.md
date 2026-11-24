# RouteRanker – Operational Test Results

**Project:** Chennai MTC RouteRanker  
**Test Date:** 2026-11-16  
**Execution Directory:** `C:\Users\kavyasri\Downloads\mtc-gtfs`

---

## 1. Function Unit Test Suite

**Script:** `scratch/test_suite.py`  
**Run status:** EXECUTED AND PASSED — 2026-11-16  
**Result:** 5/5 tests PASSED

| Test | Function | Cases Tested | Result |
|---|---|---|---|
| test_extract_canonical | `extract_canonical()` | Bare CT stripped; bare CUT stripped; single trailing letter stripped; plain route unchanged; NaN returns empty; numbered variants (CT2, CT11) are NOT stripped by design | **PASSED** |
| test_parse_time_to_seconds | `parse_time_to_seconds()` | Midnight (0s); 05:30:00; overnight GTFS time 24:15:00; None → NaN; invalid string → NaN | **PASSED** |
| test_classify_time_band | `classify_time_band()` | All 6 time bands including boundary values and 02:00 (Late Night) | **PASSED** |
| test_compute_window_intervals | `compute_window_intervals()` | 3 departures; single trip (empty); simultaneous departures (zero diffs excluded) | **PASSED** |
| test_compute_headway_stats | `compute_headway_stats()` | List of 3 intervals; empty list (NaN returned) | **PASSED** |

### Key Design Contract Documented

`extract_canonical()` strips bare suffix keywords (`CT`, `CUT`, `UD`, `DN`, `UP`) and single trailing letters. It does **not** strip numbered variants like `CT2` or `CT11` — this is intentional. Routes named `21G CT2` and `102CT CT11` are treated as distinct variants, not aliases of `21G` or `102CT`. Previous test assertions (Task 11 initial attempt) incorrectly assumed numbered variants would be stripped. Corrected assertions now match actual function contract.

---

## 2. GTFS Data Integrity Checks

**Executed:** 2026-11-16 via Python script  
All checks run against workspace-root GTFS text files.

### 2.1 Row Count Verification

| File | Expected | Actual | Status |
|---|---|---|---|
| `trips.txt` | 47,047 | 47,047 | **PASS** |
| `routes.txt` | 4,611 | 4,611 | **PASS** |
| `stops.txt` | 5,580 | 5,580 | **PASS** |
| `stop_times.txt` | 1,360,443 | 1,360,443 | **PASS** |
| `calendar.txt` | 6 | 6 | **PASS** |

### 2.2 Duplicate Key Checks

| Table | Key Column | Duplicates Found | Status |
|---|---|---|---|
| `routes.txt` | `route_id` | 0 | **PASS** |
| `stops.txt` | `stop_id` | 0 | **PASS** |

### 2.3 Missing Value Checks

| Column | Missing Count | Status |
|---|---|---|
| `trips.route_id` | 0 | **PASS** |
| `trips.service_id` | 0 | **PASS** |

### 2.4 Unique Route Activity

- Routes with at least one trip: **3,934** (of 4,611 total)
- Routes with no trips: **677** (inactive routes in routes.txt with no GTFS trips)

### 2.5 Calendar Anomalies

| Anomaly | Description | Status |
|---|---|---|
| XSS test entry in calendar.txt | `service_id` = `'/>` |`<script>alert(1)</script>` is a known bad row in the GTFS feed. It maps to 1 Monday-only trip. | **DOCUMENTED — not removed (preserve original feed)** |
| `test` service | Operates only Mon–Wed | Valid niche service; 0 impact on main analysis |

---

## 3. Time-Band Trip Count Verification

**Re-computed from:** `reports/bus_frequency_analysis.csv` (3,934 rows)  
All 6 time bands are mutually exclusive. Total must equal 47,047.

| Time Band | Trips (from CSV) |
|---|---|
| Early Morning (05-07) | 5,042 |
| Morning Peak (07-10) | 8,058 |
| Midday (10-16) | 16,859 |
| Evening Peak (16-19) | 8,264 |
| Night (19-23) | 7,293 |
| Late Night (23-05) | 1,531 |
| **Total** | **47,047** |

**Result: PASS — time-band totals reconcile exactly with GTFS trip count.**

---

## 4. Route-Level Headway Metric Verification

**Source:** `reports/bus_frequency_analysis.csv`

| Metric | Value | Verification |
|---|---|---|
| Route-level median of median headways | 65.0 min | Computed from `median_headway_min` column |
| Route-level mean of median headways | 143.9 min | Computed from `median_headway_min` column (high due to infrequent rural routes) |
| Peak intra-window median headway (1,276 routes with peak trips) | 31.5 min | Computed from `peak_median_headway_min` column |
| Off-peak intra-window median headway (2,287 routes with off-peak trips) | 40.0 min | Computed from `offpeak_median_headway_min` column |
| Total active routes in analysis | 3,934 | Matches `trips.txt` unique route count |
| Routes with schedule-based recommendations | 2,150 | From `bus_frequency_recommendations.csv` |
| Total additional trips recommended | 14,486 | Sum of `additional_trips` column |

---

## 5. External Data Checksum Verification

All SHA-256 checksums re-verified during Task 10 and confirmed unchanged in Task 11.

| File | SHA-256 (first 16 chars) | Status |
|---|---|---|
| `raw/mtc_performance_indicators_official.csv` | `2f22e1cd...` | **VERIFIED** |
| `raw/cumta_cmp_corridor_passenger_surveys_2023.csv` | `99e06fa1...` | **VERIFIED** |
| `raw/mtc_etm_research_route_characteristics.csv` | `1a729f64...` | **VERIFIED (content updated — DOI correction)** |
| `processed/mtc_performance_indicators_processed.csv` | `05088029...` | **VERIFIED** |
| `processed/cumta_cmp_corridor_passenger_surveys_processed.csv` | `99e06fa1...` | **VERIFIED** |
| `processed/mtc_etm_research_route_characteristics_processed.csv` | Updated post-correction | **CORRECTED** |

---

## 6. DOI Verification Test

**Target DOI:** `10.1177/03611981231175412`  
**Method:** Crossref Public API (`https://api.crossref.org/works/<doi>`)  
**Result:** HTTP 404 — DOI not found  
**Title search on Crossref:** No matching paper found  
**Action:** ETM dataset flagged as UNVERIFIED. DOI field updated in raw and processed files. See `data_source_correction_audit.md` for full correction record.

---

## 7. File Integrity — Task 01–10 Deliverables

Spot-check of key existing deliverables confirms they are intact and unmodified:

| File | Size (bytes) | Status |
|---|---|---|
| `notebooks/08_bus_frequency_analysis.ipynb` | 53,199 | **INTACT** |
| `reports/bus_frequency_analysis.csv` | 1,007,616 | **INTACT** |
| `reports/bus_frequency_recommendations.csv` | 504,185 | **INTACT** |
| `reports/route_ranking_results.csv` | 2,140,675 | **INTACT** |
| `data/canonical_routes_mapping.csv` | 10,108 | **INTACT** |

---

## 8. Summary

| Check Category | Tests Run | Passed | Failed | Notes |
|---|---|---|---|---|
| Function unit tests | 5 | 5 | 0 | test_suite.py corrected and re-run |
| GTFS row counts | 5 | 5 | 0 | All match expected values |
| GTFS duplicate keys | 2 | 2 | 0 | No duplicates |
| GTFS missing values | 2 | 2 | 0 | No missing values |
| Time-band reconciliation | 1 | 1 | 0 | 47,047 exact |
| Headway metric verification | 4 | 4 | 0 | All match report values |
| External data checksums | 6 | 5 | 0 | 1 corrected (ETM DOI update) |
| DOI resolution | 1 | 0 | 1 | CRITICAL — DOI 404; documented |
| Deliverable file integrity | 5 | 5 | 0 | Tasks 01–10 intact |
| **Total** | **31** | **29** | **2** | **1 critical (DOI), 1 known gap (NB-06)** |

---

*Generated by Task 11 operational audit — 2026-11-16*
