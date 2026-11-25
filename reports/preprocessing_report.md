# AI_RouteRanker - Milestone 3.1 Data Preprocessing & Relational GTFS Ingestion Report

**Project:** AI_RouteRanker – AI-Powered Public Transit Route Optimization  
**Internship Organization:** Infosys Internship Program  
**Pipeline Execution Date:** 2026-11-20  
**Storage Architecture:** Relational DuckDB (`data/processed/ai_routeranker.duckdb`) & Columnar Parquet (`data/processed/`)  

---

## 1. Executive Summary

Milestone 3.1 successfully implements an end-to-end, high-performance, reproducible data preprocessing and relational GTFS ingestion pipeline for the **AI_RouteRanker** platform. The pipeline processes two core foundational transit datasets:

1. **CTA Daily Bus Ridership**: 1,124,170 historical records spanning 25.6 years (2001-01-01 through 2026-08-31) across 188 historical bus routes.
2. **Historical GTFS Archives (Mobility Database mdb-389)**: Eight sequentially ingested snapshots spanning from November 2025 through July 2026, comprising **627,416 scheduled trips**, **38,238,809 stop times**, and **8,927,521 shape coordinates**.

### Key Milestones Achieved:
- **Zero Data Loss**: 1,124,170 clean ridership records ingested; 0 primary key collisions, 0 quarantined rows, 36 genuine zero-ride rows preserved.
- **100% Relational Integrity**: Full primary key uniqueness and foreign key integrity verified across all 8 independent GTFS snapshots.
- **Route Disambiguation**: 988 exact route-snapshot matches established. 516 historical discontinued routes identified and cataloged with zero ambiguous candidate collisions.
- **GTFS Calendar Engine**: Fully compliant evaluation of GTFS `calendar.txt` weekly operating rules and `calendar_dates.txt` exception overrides (1=Added, 2=Removed).
- **Historical Schedule Matching**: 28,798 route-date ridership records within GTFS coverage evaluated; **28,374 records (98.53%) successfully matched** to scheduled trip counts, stop visit intensities, and service span hours.
- **Resource Efficiency**: Entire 38.2M-row ingestion and integration executes in **under 2 minutes** on an 8 GB RAM laptop utilizing DuckDB's vectorized columnar engine with a 4 GB memory ceiling.

---

## 2. Ingestion & Preprocessing Architecture

The pipeline follows a multi-stage architecture designed for strict auditability, data provenance, and memory efficiency:

```
[Raw Sources]
  ├── data/raw/ridership/cta_ridership.csv (1,124,170 rows, SHA-256 verified)
  └── data/raw/gtfs/mdb-389-*/extracted/ (8 snapshots: routes, trips, stops, stop_times, calendar, shapes)
           │
           ▼
[Processing Engines: Python 3.11 + DuckDB Vectorized SQL]
  ├── ridership_pipeline.py  ──> Quarantining, Zero-Rides, Route String Normalization
  ├── gtfs_pipeline.py       ──> Relational Validation, Multi-Hour Time Normalization, Parquet Export
  ├── calendar_service.py    ──> Service ID Activation & Exception Override Matrix
  ├── route_mapper.py        ──> Ridership-to-GTFS Short Name Disambiguation
  └── integrated_pipeline.py ──> Five Consolidated Analytical Parquet Tables
           │
           ▼
[Processed Artifacts & Relational DB]
  ├── data/processed/ai_routeranker.duckdb (Schema: analytical)
  ├── data/processed/ridership/cta_ridership_clean.parquet (2.82 MB)
  ├── data/processed/gtfs/<snapshot_id>/*.parquet (8 snapshots, ~480 MB total)
  └── data/processed/integrated/*.parquet (5 integrated dimension & fact tables)
```

---

## 3. Data Cleansing & Quality Metrics

### 3.1 CTA Bus Ridership
- **Raw File**: `data/raw/ridership/cta_ridership.csv` (SHA-256: `92e8ac49be18bd689dcb4d42694c4be22248368a2bc23688a880d5d239f056d0`)
- **Total Records Ingested**: 1,124,170
- **Daytype Distribution**:
  - Weekday W: 865,376 (77.0%)
  - Saturday A: 127,570 (11.3%)
  - Sunday/Holiday U: 131,224 (11.7%)
  - Total: 1,124,170 records
- **Primary Key Integrity**: Unique constraint on `(route, date, daytype)` verified with 0 duplicates.
- **Route Preservation**: Route codes preserved strictly as `VARCHAR` to safeguard express/night prefixes (`X4`, `N5`) and leading zeros (`008`).
- **Data Cleansing Rules**:
  - Ride counts containing commas (e.g. `'6,217'`) stripped and parsed to 64-bit integers.
  - 36 records with genuine zero rides (e.g., severe weather service disruptions) explicitly retained as valid signals.
  - Date strings converted from `MM/DD/YYYY` to ISO standard `DATE`.
  - Quarantined records: 0.

### 3.2 Relational GTFS Ingestion Across 8 Snapshots

| Snapshot ID | Effective Window | Routes | Trips | Stops | Stop Times | Shapes | PK Integrity | FK Integrity |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `mdb-389-202511230128` | 2025-11-23 to 2025-12-18 | 131 | 94,594 | 11,155 | 5,800,712 | 1,115,940 | PASS | PASS |
| `mdb-389-202512190112` | 2025-12-19 to 2026-01-07 | 131 | 94,704 | 11,185 | 5,827,907 | 1,115,940 | PASS | PASS |
| `mdb-389-202601080131` | 2026-01-08 to 2026-02-09 | 131 | 49,936 | 11,130 | 2,996,069 | 1,115,940 | PASS | PASS |
| `mdb-389-202602100132` | 2026-02-10 to 2026-03-25 | 131 | 49,936 | 11,130 | 2,996,069 | 1,115,940 | PASS | PASS |
| `mdb-389-202603260020` | 2026-03-26 to 2026-04-23 | 131 | 94,496 | 11,184 | 5,838,352 | 1,115,940 | PASS | PASS |
| `mdb-389-202604240144` | 2026-04-24 to 2026-05-29 | 131 | 54,663 | 11,164 | 3,115,811 | 1,115,940 | PASS | PASS |
| `mdb-389-202605300003` | 2026-05-30 to 2026-07-10 | 133 | 94,420 | 11,177 | 5,829,073 | 1,115,940 | PASS | PASS |
| `mdb-389-202607110020` | 2026-07-11 to 2026-07-31 | 133 | 94,667 | 11,125 | 5,834,816 | 1,115,941 | PASS | PASS |
| **TOTALS** | **251 Operating Days** | **1,052** | **627,416** | **89,250** | **38,238,809** | **8,927,521** | **100% PASS** | **100% PASS** |

---

## 4. Route Identifier Disambiguation Matrix

A critical challenge in transit integration is matching historical ridership route labels with modern GTFS route feeds.
- Total distinct routes in historical ridership (2001-2026): **188 routes**
- Route-snapshot pairs evaluated (188 routes $\times$ 8 snapshots): **1,504 pairs**
- **Exact Matches (`exact_match`)**: **988 pairs** (Routes currently active in the 2025-2026 GTFS feeds matching `route_short_name`).
- **Unmatched Historical Routes (`unmatched`)**: **516 pairs** (Discontinued CTA routes from earlier decades, e.g., Route 10, 1001, 1002).
- **Ambiguous Matches (`ambiguous`)**: **0 pairs** (Zero multi-candidate route collisions).

---

## 5. Historical Schedule Matching Results

During the GTFS effective window (2025-11-23 to 2026-07-31), 28,798 daily route ridership records were matched against active GTFS schedules using calendar and calendar-dates rules:

| Snapshot Archive | Date Window | Total Records | Matched Records | Unmatched Records | Zero-Trip Days | Match Rate | Avg Daily Rides | Avg Scheduled Trips | Avg Service Span |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `mdb-389-202511230128` | 2025-11-23 to 2025-12-18 | 3,027 | 2,987 | 39 | 1 | 98.68% | 3,980.9 | 148.2 | 19.46 hrs |
| `mdb-389-202512190112` | 2025-12-19 to 2026-01-07 | 2,333 | 2,301 | 30 | 2 | 98.63% | 3,369.3 | 147.9 | 19.45 hrs |
| `mdb-389-202601080131` | 2026-01-08 to 2026-02-09 | 3,849 | 3,791 | 55 | 3 | 98.49% | 3,674.3 | 147.2 | 19.42 hrs |
| `mdb-389-202602100132` | 2026-02-10 to 2026-03-25 | 5,142 | 5,068 | 71 | 3 | 98.56% | 3,871.4 | 147.1 | 19.42 hrs |
| `mdb-389-202603260020` | 2026-03-26 to 2026-04-23 | 3,388 | 3,340 | 45 | 3 | 98.58% | 4,047.8 | 147.8 | 19.45 hrs |
| `mdb-389-202604240144` | 2026-04-24 to 2026-05-29 | 4,206 | 4,142 | 60 | 4 | 98.48% | 4,149.2 | 147.6 | 19.45 hrs |
| `mdb-389-202605300003` | 2026-05-30 to 2026-07-10 | 4,374 | 4,307 | 64 | 3 | 98.47% | 4,057.2 | 148.1 | 19.46 hrs |
| `mdb-389-202607110020` | 2026-07-11 to 2026-07-31 | 2,479 | 2,438 | 41 | 0 | 98.35% | 3,939.8 | 148.0 | 19.46 hrs |
| **AGGREGATE** | **2025-11-23 to 2026-07-31** | **28,798** | **28,374** | **405** | **19** | **98.53%** | **3,889.3** | **147.7** | **19.44 hrs** |

---

## 6. Output Artifacts & Deliverables

All integrated tables have been exported to compressed Parquet (`data/processed/integrated/`) and registered in DuckDB:

1. `data/processed/integrated/snapshot_metadata.parquet` (8 snapshots metadata & audit checksums)
2. `data/processed/integrated/route_mapping.parquet` (1,504 route-snapshot mapping rows)
3. `data/processed/integrated/gtfs_route_dim.parquet` (1,052 route dimension rows)
4. `data/processed/integrated/daily_ridership.parquet` (1,124,170 ridership rows with GTFS window linkage)
5. `data/processed/integrated/historical_schedule_match.parquet` (28,798 schedule-matched rows)

### Six Mandatory Audit Reports in `reports/`:
- `reports/preprocessing_report.md` (This document)
- `reports/ridership_quality_report.csv` (Ridership quality metrics and checksums)
- `reports/gtfs_ingestion_report.csv` (Detailed snapshot metrics and storage sizes)
- `reports/route_mapping_report.csv` (Complete route-to-GTFS mapping register)
- `reports/historical_schedule_matching_report.csv` (Schedule matching accuracy and operational span)
- `reports/data_dictionary.md` (Comprehensive field definitions and schema documentation)

---

## 7. Next Steps (Milestone 4 Readiness)
With Milestone 3.1 completed and verified:
- The data is clean, indexed, and structurally sound.
- Exploratory Data Analysis (EDA), feature engineering, and ridership forecasting can proceed on reliable, referentially integral foundations.
