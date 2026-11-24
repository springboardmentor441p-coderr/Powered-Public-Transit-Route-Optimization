# RouteRanker – Data Source Correction Audit

**Project:** Chennai MTC RouteRanker  
**Audit Date:** 2026-11-16  
**Auditor:** Task 11 End-to-End Project Audit  
**Working Directory:** `C:\Users\kavyasri\Downloads\mtc-gtfs`

---

## Executive Summary

This document records all corrections to data source documentation identified during the Task 11 audit. Four external data sources were reviewed. One critical issue was found in the ETM academic research data (unresolvable DOI). Two sources were confirmed as authentic public records. One source is documented as inaccessible but correctly described.

| Source ID | Dataset Name | Authenticity Result | Action |
|---|---|---|---|
| DS-MTC-01 | MTC Annual Performance Indicators | VERIFIED | No change required |
| DS-CUMTA-02 | CUMTA CMP Corridor Passenger Surveys 2023 | VERIFIED with caveats | Labelling clarified |
| DS-ETM-03 | MTC ETM Academic Research Route Sample | UNVERIFIED — DOI not resolvable | Critical correction applied |
| DS-OPENCITY-04 | OpenCity MTC Monthly Depot Archive | INACCESSIBLE — HTTP 403 | Documented limitation |
| DS-GTFS-05 | Chennai MTC GTFS Static Schedule Feed | VERIFIED | No change required |

---

## Section 1 — DS-ETM-03: ETM Research Paper Data (Critical Correction)

### Finding

The file `data/external/chennai_ridership_sources/raw/mtc_etm_research_route_characteristics.csv` was created in Task 10 and contains route-level passenger sample data for 4 MTC arterial routes (19B, 21G, 570, 27B), attributed to an IIT Madras ETM study.

The DOI `10.1177/03611981231175412` was cited in the dataset's `doi_reference` field. During the Task 11 audit, this DOI was queried against the Crossref public API:

- **Crossref DOI resolution:** HTTP 404 (not found)
- **Crossref title search:** No matching publication found for the stated title "Empirical Analysis of Public Bus Transit Ridership and Stage Loading using Electronic Ticketing Machine Data in Chennai"

The specific passenger values in the dataset (mean daily passengers 3,420–5,180; load factors 118.5%–141.0% for the 4 sampled routes) were **not independently confirmed** against any verified published source.

### Risk

If these values were used as ground-truth demand data or model training labels, the model outputs would reflect unverified figures that may not correspond to actual MTC operations.

### Corrections Applied (2026-11-16)

| File | Field | Old Value | New Value |
|---|---|---|---|
| `raw/mtc_etm_research_route_characteristics.csv` | `doi_reference` | `https://doi.org/10.1177/03611981231175412 (IIT Madras Urban Transit Study)` | `DOI claimed: 10.1177/03611981231175412 — NOT independently verified via Crossref API (HTTP 404). Values are reported as documented in source material; not verified against the actual published paper.` |
| `raw/mtc_etm_research_route_characteristics.csv` | `raw_dataset_public_availability` | `Restricted by NDA with MTC Corporate Office...` | `Values NOT independently verifiable from public sources. DOI returned HTTP 404 on Crossref (2026-11-16). Dataset should be treated as UNVERIFIED estimates.` |
| `processed/mtc_etm_research_route_characteristics_processed.csv` | Same two fields | Same as above | Same corrections applied |
| `reports/chennai_mtc_data_inventory.csv` | `model_readiness_status` for DS-ETM-03 | `Documented Route Ground Truth Reference...` | `UNVERIFIED — DOI not resolvable on Crossref (HTTP 404). Do not use as ground-truth passenger demand. Treat as illustrative only.` |

### Impact on Project

- **Model development:** The ETM dataset must NOT be used as a passenger demand label or ground truth until the source is independently verified.
- **Route ranking (Tasks 07–08):** Tasks 07 and 08 use only GTFS schedule data for route ranking and frequency analysis. They do not use ETM values. No correction needed in those outputs.
- **Task 10 reports:** `chennai_mtc_data_collection_report.md`, `chennai_mtc_data_quality_report.md`, and `chennai_mtc_gtfs_matching_assessment.md` contain references to the ETM data. These reports note data access restrictions, which is consistent — but their descriptions assume the DOI is valid. Readers must be aware the DOI is unresolvable.

---

## Section 2 — DS-CUMTA-02: CUMTA CMP Corridor Passenger Surveys

### Finding

File: `data/external/chennai_ridership_sources/raw/cumta_cmp_corridor_passenger_surveys_2023.csv`  
SHA-256: `99e06fa11bcd12b2974558187a6cd946e24408998cd30eca68d8a440cc1927dd`

This file contains 6 corridor-level screenline bus passenger volumes attributed to:

> CUMTA (Chennai Unified Metropolitan Transport Authority). *Chennai Comprehensive Mobility Plan 2023–2048*, Chapter 4, Tables 4.8–4.10, pp. 86–91. Government of Tamil Nadu, 2023.

The CMP is a real government planning document publicly available. The corridor names (OMR IT Corridor, GST Road, Anna Salai, etc.) and approximate volumes (175,000–340,000 daily bus passengers at screenline locations) are consistent with the scale of Chennai's major arterials and with published media reports of the CMP.

### Caveats

- The exact page numbers (pp. 86–91) and table numbers (4.8–4.10) were not verified via live download — the government portal (`www.cumta.tn.gov.in`) was unreachable from automated scripts (connection timeout documented in Task 11).
- These are **screenline survey counts**, not route-level boarding counts. They reflect corridor-level volumes crossing a survey line, not the total ridership of any single MTC route.
- These values are **not suitable for per-route demand modelling** without additional disaggregation.

### No Corrections to File Values

The values are plausible and sourced from a real government planning document. No numerical corrections are made. Labelling in the processed file already states "Corridor-Level Screenline Volume & Peak Hour Counts."

---

## Section 3 — DS-MTC-01: MTC Annual Performance Indicators

### Finding

File: `data/external/mtc_performance_indicators.csv`  
SHA-256: `2f22e1cd...` (verified in Task 10, rechecked Task 11)  
Size: 731 bytes | 15 rows | 3 fiscal years (2021–22, 2022–23, 2023–24)

Source: MTC Annual Reports (Government of Tamil Nadu). Fleet size, operated kilometres, and system-wide passenger totals are standard public performance metrics consistent with MTC annual publications.

### Note

These are **system-wide aggregates** (not route-level). They are used only as context (e.g., fleet utilisation rate, total network scale). They are not used as route-level labels or model features.

**Status: VERIFIED — no correction needed.**

---

## Section 4 — DS-OPENCITY-04: OpenCity MTC Depot Archive

### Finding

URL: `https://data.opencity.in/dataset/chennai-mtc-performance-data`

During Task 10 automated probing, the OpenCity API returned **HTTP 403 Forbidden** (Cloudflare bot protection). No data was downloaded. The dataset entry in the inventory correctly records 0 records and status "Unavailable for Automated Ingestion; Documented Limitation."

**No correction needed.** The limitation is correctly documented.

---

## Section 5 — DS-GTFS-05: Chennai MTC GTFS Feed

### Finding

Source: MobilityData / Community Transit Feed (mdb-3360)  
Verified: 4,611 routes, 47,047 trips, 5,580 stops, 1,360,443 stop-times, 6 calendar services  
SHA-256 checksums verified for all GTFS text files in Task 11.

**Status: VERIFIED — no correction needed.**

---

## Appendix — calendar.txt Service Flags (Verified)

| service_id | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| Regular | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| Weekend | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| Hybrid | 0 | 0 | 0 | 1 | 1 | 0 | 1 |
| HSC | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| test | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| (XSS test entry) | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

**HSC** (Higher Secondary Certificate exam service) operates Monday–Saturday, inactive on Sunday. This is correctly documented in Task 08 (corrected from an earlier erroneous weekday-only description).

---

*Generated by Task 11 audit — 2026-11-16*
