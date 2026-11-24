# RouteRanker – Performance Improvement Analysis

**Project:** Chennai MTC RouteRanker  
**Analysis Date:** 2026-11-16  
**Scope:** All improvements, corrections and enhancements identified from Tasks 01–11

---

## Classification Key

| Priority | Meaning |
|---|---|
| **CRITICAL** | Data integrity or correctness error that would affect model outputs or project conclusions |
| **HIGH** | Calculation error or significant methodology flaw that was fixed |
| **MEDIUM** | Implementation quality issue that reduces reproducibility or maintainability |
| **LOW** | Minor inconsistency or cosmetic issue |

---

## CRITICAL Improvements

### C-1: ETM Paper DOI Unresolvable (Task 10 → Task 11)

**Issue:** `data/external/chennai_ridership_sources/raw/mtc_etm_research_route_characteristics.csv` attributed passenger counts (3,420–5,180 daily passengers/route) to DOI `10.1177/03611981231175412`. Crossref API returned HTTP 404 for this DOI. Title search also found no match. The values cannot be independently verified.

**Risk:** If used as passenger demand labels or ground-truth for ML, the model learns from unconfirmed estimates.

**Fix Applied:** `doi_reference` and `raw_dataset_public_availability` fields updated in both raw and processed ETM CSVs. `model_readiness_status` in inventory updated to "UNVERIFIED — Do not use as ground-truth passenger demand."

**Status:** CORRECTED (2026-11-16)

---

### C-2: Missing Notebook 06 (Route Clustering)

**Issue:** `notebooks/06_route_clustering.ipynb` does not exist. The route clustering report and CSV (`route_cluster_assignments.csv`) exist, but the notebook that generated them is absent. The analysis cannot be reproduced or audited step by step.

**Risk:** Cannot verify that cluster assignments are consistent with stated methodology.

**Status:** DOCUMENTED as known gap. Notebook is not reconstructed in Task 11 (would require full re-execution without confirmed original code). Flagged for reconstruction before model preparation.

---

## HIGH Improvements

### H-1: Peak Headway Previously Computed Across Disjoint Windows (Task 08 Correction)

**Issue (before correction):** Initial Task 08 implementation computed headway intervals across all peak hours combined (07:00–10:00 and 16:00–19:00 merged), creating false large gaps across the midday period that inflated peak headway estimates.

**Fix Applied (Task 08 audit cycle):** Peak headways now computed separately for Morning Peak (07:00–10:00) and Evening Peak (16:00–19:00). Off-peak headways computed separately for Early Morning, Midday, and Night windows. No cross-window interval pollution.

**Before/After:**
- Peak median headway: previously overstated; corrected to **31.5 min** (intra-window)
- Off-peak median headway: corrected to **40.0 min** (intra-window)

**Status:** CORRECTED in Task 08 (re-executed notebook).

---

### H-2: Recommendation Formula Not Bounded by Active Service Span (Task 08 Correction)

**Issue (before correction):** The recommendation formula estimated additional trips needed as `active_coverage_hours / target_headway_hours`, but `active_coverage_hours` defaulted to the full time-window length (e.g., 6 hours for Morning Peak) even for routes that only operated for 1–2 hours within that window. This produced over-inflated additional trip counts.

**Fix Applied:** `active_coverage_hours` now computed from each route's actual first and last departure within the relevant window. Trip estimates are bounded by the route's real operating window.

**Status:** CORRECTED in Task 08 (re-executed notebook). Total additional trips = 14,486 (bounded).

---

### H-3: HSC Calendar Classification Error (Task 08 Correction)

**Issue (before correction):** HSC service was described as "weekday-only." `calendar.txt` shows HSC operates Monday–Saturday (sunday=0). Saturday is active.

**Fix Applied:** Report updated to correctly state "Monday–Saturday service, inactive on Sunday."

**Status:** CORRECTED in Task 08 report and notebook.

---

### H-4: Top-10 Busiest Route Table Missing Route Names (Task 08 Enhancement)

**Issue:** Initial busiest route table showed only `route_id` without `route_short_name` or `route_long_name`.

**Fix Applied:** Top-10 tables updated to include all three identifier columns.

**Status:** CORRECTED in Task 08.

---

### H-5: Route-Level vs Pooled Headway Statistics Not Separated (Task 08 Enhancement)

**Issue:** Earlier summary statistics mixed route-level aggregated medians with pooled raw interval medians, causing confusion between the two aggregation levels.

**Fix Applied:** Report now explicitly separates:
- **Route-level statistics** (median of each route's median headway): Network median = 65.0 min, mean = 143.9 min
- **Intra-window pooled statistics** (all departure intervals pooled): Peak 31.5 min, Off-peak 40.0 min, Overall pooled 20.0 min

**Status:** CORRECTED in Task 08 report.

---

## MEDIUM Improvements

### M-1: Hard-Coded Absolute Windows Paths in Builder Scripts

**Issue:** Many `scratch/` Python builder scripts contain hard-coded paths like `C:/Users/kavyasri/Downloads/mtc-gtfs`. If the project is moved or run on a different machine, all scripts fail without modification.

**Recommendation:** Use `pathlib.Path(__file__).parent.parent` or a config variable at the top of each script.

**Status:** DOCUMENTED. Not fixed in Task 11 (operational scripts are in `scratch/` and not production deliverables).

---

### M-2: No Test Suite Before Task 11

**Issue:** Tasks 01–10 had no automated function tests. Utility functions (`extract_canonical`, `parse_time_to_seconds`, `classify_time_band`) were tested only implicitly through notebook output inspection.

**Fix Applied:** `scratch/test_suite.py` created in Task 11 with 5 explicit unit tests covering all core utility functions. All 5 tests pass.

**Status:** COMPLETED (2026-11-16).

---

### M-3: CUMTA CMP Data Not Explicitly Labelled as Screenline Volumes

**Issue:** `cumta_cmp_corridor_passenger_surveys_2023.csv` contains corridor-level screenline passenger volumes (vehicles crossing a survey line), not route-level boarding counts. Using these as per-route demand figures would be methodologically incorrect.

**Fix Applied:** Labelling clarified in `data_source_correction_audit.md`. The processed file header already states "Corridor-Level Screenline Volume." No numerical change.

**Status:** DOCUMENTED.

---

### M-4: XSS Test Entry in calendar.txt Not Flagged

**Issue:** `calendar.txt` contains a row with `service_id = '/>` |`<script>alert(1)</script>`. This is likely a data quality test injection in the original GTFS feed. It affects 1 trip and has negligible analytical impact, but it was never flagged.

**Fix Applied:** Documented in `operational_test_results.md`. Original GTFS files are preserved unchanged (no modification to source data).

**Status:** DOCUMENTED.

---

## LOW Improvements

### L-1: CSV Column Naming Inconsistencies

Minor inconsistencies exist in column naming across tasks (e.g., `route_short_name` vs `short_name` in some intermediate files, `service_id` label variations). These do not affect final deliverable CSVs which follow a consistent schema.

**Status:** DOCUMENTED. No action taken (cosmetic, no impact on analysis).

---

### L-2: `eda_verification.md` and `network_verification.md` are Separate from Reports

Verification files exist separately from main reports. This is intentional for auditability but creates redundancy. No change needed.

**Status:** DOCUMENTED.

---

## Improvement Summary Table

| ID | Category | Description | Status |
|---|---|---|---|
| C-1 | CRITICAL | ETM DOI unresolvable; values unverified | CORRECTED |
| C-2 | CRITICAL | Notebook 06 missing | DOCUMENTED (gap) |
| H-1 | HIGH | Peak headway across disjoint windows | CORRECTED (Task 08) |
| H-2 | HIGH | Recommendation not bounded by active span | CORRECTED (Task 08) |
| H-3 | HIGH | HSC calendar Mon-Sat misclassified as weekday-only | CORRECTED (Task 08) |
| H-4 | HIGH | Top-10 table missing route names | CORRECTED (Task 08) |
| H-5 | HIGH | Route-level vs pooled stats mixed | CORRECTED (Task 08) |
| M-1 | MEDIUM | Hard-coded absolute paths in scripts | DOCUMENTED |
| M-2 | MEDIUM | No test suite before Task 11 | COMPLETED (Task 11) |
| M-3 | MEDIUM | CUMTA screenline volumes vs boardings | DOCUMENTED |
| M-4 | MEDIUM | XSS test entry in calendar.txt | DOCUMENTED |
| L-1 | LOW | CSV column naming inconsistencies | DOCUMENTED |
| L-2 | LOW | Separate verification files create redundancy | DOCUMENTED |

---

*Generated by Task 11 performance improvement analysis — 2026-11-16*
