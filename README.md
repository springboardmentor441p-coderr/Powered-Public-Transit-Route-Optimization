# Chennai MTC RouteRanker

## 1. Overview
RouteRanker is a research‑grade, notebook‑driven framework for constructing, validating, and benchmarking **timetable‑aware public‑transit routing** on the Chennai Metropolitan Transport Corporation (MTC) bus network.  The pipeline operates entirely on the publicly available **community‑maintained Chennai GTFS feed** and incorporates official MTC performance‑indicator data for Phase 1 analysis.

---

## 2. Problem Statement & Objectives
| Challenge | Objective |
|-----------|-----------|
| **Schedule‑aware routing** | Implement a RAPTOR engine that respects GTFS service calendars (Monday‑Saturday vs. Sunday), handles post‑midnight times, and enforces a minimum transfer buffer of 180 seconds. |
| **Data consistency & explainability** | Verify that `route_id` and `service_id` references are internally consistent and produce transparent journey rankings (total duration vs. number of transfers). |

---

## 3. Dataset (repository‑relative paths)
| File | Description | Records |
|------|-------------|---------|
| `data/routes.txt` | Route metadata (IDs, short/long names, type) | 4,611 |
| `data/stops.txt` | Stop locations and names | 5,580 |
| `data/trips.txt` | Individual scheduled trips (vehicle runs) | 47,047 |
| `data/stop_times.txt` | Ordered stop events for each trip | 1,360,443 |
| `data/calendar.txt` | Service‑day definition (Mon‑Sat, Sun) per `service_id` | **6** data rows (7 lines including the header) |
| `data/agency.txt` | Agency information (MTC) | 1 |
| `data/feed_info.txt` | Feed metadata (version, timestamp) | 1 |
| `data/external/mtc_performance_indicators.csv` | Official MTC performance indicators (used in Phase 1) | 731 |

**GTFS source** – The feed is the **community‑maintained “Chennai GTFS”** dataset (e.g., hosted in the GTFS Data Archive).  It is derived from the schedule released by MTC but is not an official MTC publication.

**Dataset limitations**
- No route‑level passenger boarding or alighting counts are available.
- The feed does not contain a `shapes.txt` file, so precise bus‑track geometry is unavailable.

---

## 4. Project Modules (completed)
| Module | Notebook | Report | Summary |
|--------|----------|--------|---------|
| **1 – Dataset Inspection** | `notebooks/01_dataset_inspection.ipynb` | `reports/module1_dataset_inspection.md` | File‑level sanity checks, schema validation, basic counts. |
| **2 – Exploratory Data Analysis** | `notebooks/02_exploratory_data_analysis.ipynb` | `reports/eda_report.md`, `reports/eda_verification.md` | Trips‑per‑route distribution, stop‑degree analysis, temporal patterns. |
| **3 – Network Construction** | `notebooks/03_network_construction.ipynb` | `reports/network_construction_report.md`, `reports/network_verification.md` | Directed bus‑stop graph from consecutive stop pairs; component and degree statistics. |
| **4 – Route Optimization (RAPTOR)** | `notebooks/04_route_optimization.ipynb` | `reports/route_optimization_report.md` | Timetable‑aware RAPTOR implementation; scenario testing (direct, transfers, Sunday, post‑midnight, no‑route). |
| **5 – Phase 1 Data Integration** | `notebooks/05_phase1_data_integration.ipynb` | `reports/phase1_data_feasibility_report.md`, `reports/phase1_verification.md` | Integration of canonical‑route mapping, validation of proxy metrics, updated figures. |

### Additional Validation Notebook
| Artifact | Description |
|----------|-------------|
| `notebooks/04_route_date_matching.ipynb` | Validates that every `trip` references an existing `route_id` and `service_id`; classifies services by weekday/Sunday availability. |
| `reports/route_service_matching_report.md` | Summarises the validation results (zero missing IDs, service‑category breakdown). |

---

## 5. Phase 1 Findings (key points)
- **Canonical route mapping** resolved 675 defined routes, of which 654 are active base corridors after stripping operational suffixes.
- The macro‑level passenger‑per‑dispatch proxy (≈ 68.5 passengers per bus dispatch) is clearly documented as a system‑wide ratio, **not** a per‑trip occupancy measure.
- Updated figures (`fig15_route_hierarchy_resolution.png`, `fig16_scheduled_supply_guardrails.png`) reflect the corrected route hierarchy and supply‑guardrail analysis.

---

## 6. Technologies & Dependencies
| Category | Tools / Libraries |
|----------|-------------------|
| Language | Python 3.12 |
| Data manipulation | pandas |
| Graph analysis | NetworkX |
| Routing algorithm | Custom RAPTOR implementation (pure Python) |
| Visualization | matplotlib, seaborn |
| Notebook environment | Jupyter Notebook |
| Auxiliary scripts | `scratch/` utilities for figure generation and validation |

All required packages are listed in `requirements.txt` (generated from the notebooks).  The project runs on Windows, macOS, and Linux without requiring external services.

---

## 7. Repository Structure
```
mtc-gtfs/
│   README.md
│   requirements.txt (optional)
│
├─ data/
│   ├─ routes.txt
│   ├─ stops.txt
│   ├─ trips.txt
│   ├─ stop_times.txt
│   ├─ calendar.txt
│   ├─ agency.txt
│   ├─ feed_info.txt
│   └─ external/
│       └─ mtc_performance_indicators.csv
│
├─ notebooks/
│   ├─ 01_dataset_inspection.ipynb
│   ├─ 02_exploratory_data_analysis.ipynb
│   ├─ 03_network_construction.ipynb
│   ├─ 04_route_optimization.ipynb
│   ├─ 04_route_date_matching.ipynb
│   └─ 05_phase1_data_integration.ipynb
│
├─ reports/
│   ├─ module1_dataset_inspection.md
│   ├─ eda_report.md
│   ├─ eda_verification.md
│   ├─ network_construction_report.md
│   ├─ network_verification.md
│   ├─ route_optimization_report.md
│   ├─ route_service_matching_report.md
│   ├─ phase1_data_feasibility_report.md
│   └─ phase1_verification.md
│   └─ figures/ (generated PNGs)
│
└─ scratch/ (utility scripts)
```

---

## 8. Setup & Execution
1. **Clone the repository** (or download the ZIP) to a local directory.
2. **Create a Python virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   (If `requirements.txt` is absent, install the core libraries manually: `pandas`, `networkx`, `matplotlib`, `seaborn`, `jupyter`).
4. **Launch Jupyter Notebook** and open the notebooks in order:
   ```bash
   jupyter notebook
   ```
   Run each notebook from top to bottom; they read the GTFS files from the relative `data/` folder.
5. **Optional validation** – Execute `notebooks/04_route_date_matching.ipynb` to reproduce the route/service consistency check and generate `reports/route_service_matching_report.md`.

---

## 9. Key Verified Results
- **Total stops:** 5,580 (5,477 active in the directed graph).
- **Total trips:** 47,047.
- **Unique route patterns (RAPTOR):** 3,491.
- **Scenario 2 (multi‑leg journey) – fastest option:** 83 minutes, 2 transfers.
- **Scenario 3 (missed‑bus sensitivity) – verified itinerary:** 85 minutes, 2 transfers, with correctly modelled waiting times.
- **Calendar awareness:** Sunday‑only services are correctly excluded (e.g., `HSC` service on Route 45A).

---

## 10. Future Work (Phase 2 Overview)
- Acquire or estimate route‑level passenger boarding/alighting data.
- Incorporate `shapes.txt` (if/when made available) to enable geographic path analysis.
- Extend the RAPTOR implementation to consider real‑time GTFS‑Realtime feeds.
- Develop a ranking model that combines travel time, transfers, and passenger comfort metrics.

---

*All statements in this README are based on the verified contents of the repository as of 2026‑11‑06.*
```