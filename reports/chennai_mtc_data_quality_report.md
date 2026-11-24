# Chennai MTC Data Quality & Validation Report

**Project:** RouteRanker – AI-Powered Public Transit Route Optimization  
**Module:** Task 10 – Data Collection, Validation & Model Readiness  
**Location:** Chennai Metropolitan Area, Tamil Nadu  
**Agency:** Metropolitan Transport Corporation (Chennai) Ltd. (MTC)  
**Execution Date:** November 16, 2026  
**Status:** Validated Data Quality Audit  

---

## 1. Executive Summary

This report delivers a thorough data quality, schema validation, missing value audit, and duplicate inspection across all genuine datasets archived under `data/external/chennai_ridership_sources/`.

### Quality Audit Highlights:
- **Zero Missing Critical Identifiers:** All processed tables maintain complete schemas with zero missing values in primary key fields.
- **Zero Duplicate Rows:** Record-level deduplication confirmed no duplicate rows across processed datasets.
- **Strict Data Integrity:** Numerical metrics (e.g. daily passengers, modal share %, load factors) strictly conform to verified official ranges.
- **Supply vs. Demand Boundary:** The separation between scheduled bus dispatches (supply) and realized passenger boardings (demand) has been audited and enforced.

---

## 2. Dataset Quality Inspections

### 2.1 Dataset: MTC Key Performance Indicators
- **Files Inspected:**
  - Raw: `data/external/chennai_ridership_sources/raw/mtc_performance_indicators_official.csv`
  - Processed: `data/external/chennai_ridership_sources/processed/mtc_performance_indicators_processed.csv`
- **Schema & Records:**
  - Raw: 15 rows × 6 columns (`sl_no`, `item`, `unit`, `2024_2025`, `2025_2026`, `2026_2027_oct`).
  - Processed (Long Format): 45 rows × 6 columns (`sl_no`, `item`, `unit`, `period`, `value`, `period_label`).
- **Data Types & Value Ranges:**
  - `sl_no`: Integer (1 to 15).
  - `item`: String (15 unique indicators).
  - `unit`: Categorical string (`count`, `years`, `lakh_km`, `km`, `percentage`, `lakh_passengers`, `rate`, `ratio`).
  - `value`: Float. Range spans from 0.001 (breakdown rate per 10,000 km) to 291,961.0 (tyre life in km).
- **Missing Value Audit:**
  - Missing count: 0 of 45 entries (0.0%).
- **Duplicate Audit:**
  - 0 duplicate rows.
- **Physical Feasibility Checks:**
  - Total fleet increases monotonically: 3,407 $\rightarrow$ 4,060 $\rightarrow$ 4,206 buses.
  - Passenger daily volume: 32.24 Lakhs $\rightarrow$ 34.00 Lakhs $\rightarrow$ 34.40 Lakhs/day.
  - Occupancy ratio remains within realistic transit bounds: 68.39% to 77.34%.
  - Fleet utilization remains within realistic operational limits: 83.77% to 84.85%.

---

### 2.2 Dataset: CUMTA CMP Corridor Passenger Loading Surveys
- **Files Inspected:**
  - Raw: `data/external/chennai_ridership_sources/raw/cumta_cmp_corridor_passenger_surveys_2023.csv`
  - Processed: `data/external/chennai_ridership_sources/processed/cumta_cmp_corridor_passenger_surveys_processed.csv`
- **Schema & Records:**
  - 6 rows × 9 columns (`corridor_id`, `corridor_name`, `survey_location`, `survey_year`, `daily_bus_passenger_volume_surveyed`, `peak_hour_bus_passenger_volume`, `peak_hour_bus_modal_share_pct`, `primary_mtc_routes_observed`, `data_source_reference`).
- **Data Types & Value Ranges:**
  - `corridor_id`: Primary key string (`CORR-01` to `CORR-06`).
  - `survey_year`: Integer (2023).
  - `daily_bus_passenger_volume_surveyed`: Integer (175,000 to 340,000 passengers/day). Highest along GST Road (340,000), lowest along GNT Road (175,000).
  - `peak_hour_bus_passenger_volume`: Integer (15,400 to 28,200 passengers/hour).
  - `peak_hour_bus_modal_share_pct`: Float (31.8% to 43.1%). Highest along Jawaharlal Nehru 100 Feet Road (43.1%), lowest along OMR (31.8%, reflecting high personal two-wheeler and cab presence).
- **Missing Value Audit:**
  - Missing count: 0 of 54 cell values (0.0%).
- **Duplicate Audit:**
  - 0 duplicate rows; 6 unique corridors.
- **Validation against Transport Engineering Benchmarks:**
  - Peak-to-daily ratios: $\frac{\text{Peak Hour Volume}}{\text{Daily Volume}}$ ranges from 8.29% to 9.00%, perfectly matching standard urban transport planning expectations for Indian metropolitan screenlines (typically 8% to 10% peak hour concentration).

---

### 2.3 Dataset: MTC ETM Academic Research Route Sample Characteristics
- **Files Inspected:**
  - Raw: `data/external/chennai_ridership_sources/raw/mtc_etm_research_route_characteristics.csv`
  - Processed: `data/external/chennai_ridership_sources/processed/mtc_etm_research_route_characteristics_processed.csv`
- **Schema & Records:**
  - 4 rows × 14 columns.
- **Data Types & Value Ranges:**
  - `route_short_name`: Categorical string (`19B`, `21G`, `570`, `27B`).
  - `documented_daily_trips_sampled`: Integer (48 to 64 trips/day).
  - `mean_daily_passengers_sampled`: Integer (3,420 to 5,180 passengers/day).
  - `mean_passengers_per_trip`: Float (71.25 to 87.32 passengers/trip).
  - `peak_hour_load_factor_pct`: Float (118.5% to 141.0%). Load factor $>100\%$ confirms observed standee overcrowding on trunk lines during peak commute hours.
- **Missing Value Audit:**
  - Missing count: 0 of 56 cell values (0.0%).
- **Duplicate Audit:**
  - 0 duplicate rows; 4 distinct routes.

---

## 3. Data Transformation & Traceability Documentation

Every step taken to transform raw inputs into model-ready analytical representations has been documented:

| Processing Step | Input Dataset | Operation Performed | Output Dataset | Verification Status |
|---|---|---|---|---|
| **P-01: Performance Normalization** | Raw MTC Performance CSV | Melted wide fiscal-year columns into normalized time-series rows; standardized numeric types and added clean labels | `mtc_performance_indicators_processed.csv` | Passed (SHA-256 verified) |
| **P-02: Screenline Synthesis** | CUMTA CMP Report Ch. 4 | Extracted screenline passenger loading volumes and modal split percentages across 6 major arterial corridors | `cumta_cmp_corridor_passenger_surveys_processed.csv` | Passed (Traceable to pp. 86–91) |
| **P-03: Research Sample Structuring** | IIT Madras ETM Study | Structured documented route sample metrics, load factors, and provenance paths for routes 19B, 21G, 570, 27B | `mtc_etm_research_route_characteristics_processed.csv` | Passed (Traceable to DOI reference) |

---

## 4. Assessment of Prohibited Data Manipulations

To guarantee that the RouteRanker project strictly adheres to academic rigor and mentor guidelines, the following negative constraints were verified:

1. **No Synthetic Passenger Imputation:**  
   No algorithm was run to fill the 3,930 missing route ridership values with pseudo-random or regression-imputed counts.
2. **No Route-Level Disaggregation of System Totals:**  
   The system-wide average of 34.40 Lakh passengers/day was **not** divided across the 3,934 routes (which would have yielded an artificial flat average of ~874 passengers/route-day).
3. **No Cross-City or Cross-Mode Data Blending:**  
   No ridership figures from Bengaluru (BMTC), Delhi (DTC), or Chennai Metro Rail Limited (CMRL) were substituted for Chennai bus ridership.
