# Bus Frequency Analysis & Schedule-Based Optimization Report

**Project:** RouteRanker - AI-Powered Public Transit Route Optimization  
**Module:** Task 2 - Bus Frequency Analysis & Optimization (Corrected & Validated)  
**Location:** Chennai, Tamil Nadu  
**Agency:** Metropolitan Transport Corporation (MTC), Chennai  
**Date:** 2026-11-08  

---

## 1. Executive Summary

This report delivers a verified, schedule-based frequency analysis and rule-based optimization for active bus routes of the Chennai Metropolitan Transport Corporation (MTC), derived from the official GTFS static timetable.

### Key Metrics Summary
- **Total active route variants analyzed:** 3,934 (out of 4,611 defined routes)
- **Total scheduled trips evaluated:** 47,047 (100.0% coverage across 6 mutually exclusive time bands)
- **Multi-trip routes with computable headway:** 3,065
- **Single-trip routes (undefined headway):** 869 (reported as NaN, documented limitation)
- **Route-level aggregation median headway:** **65.0 minutes** (mean: 143.9 min across 3,065 routes)
- **Pooled trip-interval median headway:** **20.0 minutes** (mean: 45.1 min across 42,108 intervals)
- **Peak intra-window median headway:** **31.5 minutes** (evaluated strictly within contiguous morning and evening peak windows)
- **Off-peak intra-window median headway:** **40.0 minutes** (evaluated strictly within early morning, midday, and night windows)
- **Routes with excessive gaps (> 60 min):** 2,431 (61.8%)
- **Routes with short operational span (< 6 hours):** 1,575 (40.0%)
- **Total bounded optimization recommendations:** 2,150 across 1,518 unique routes
- **Estimated additional trips for scenario benchmarks:** 14,486 trips (differentiated and bounded by active operational spans)

---

## 2. Dataset & Calendar Analysis

### Input Data Audit
| Table | File | Rows Verified | Key Attributes Evaluated |
|---|---|---|---|
| Routes | routes.txt | 4,611 | `route_id`, `route_short_name`, `route_long_name` |
| Trips | trips.txt | 47,047 | `trip_id`, `route_id`, `service_id`, `direction_id` |
| Stop Times | stop_times.txt | 1,360,443 | `trip_id`, `stop_sequence`, `departure_time` |
| Stops | stops.txt | 5,580 | `stop_id`, `stop_name`, coordinates |
| Calendar | calendar.txt | 6 | `service_id`, day-of-week binary service masks |
| Canonical Mapping | canonical_routes_mapping.csv | 675 | `canonical_route`, corridor clusters |

### Calendar & Service Pattern Findings
- **Regular Service (46,973 trips; 99.8% of network):** Operates all 7 days of the week (Monday through Sunday).
- **HSC Service (74 trips; 0.2% of network):** Operates **Monday through Saturday (inactive on Sundays)**. In `calendar.txt`, `saturday = 1` and `sunday = 0`.
- **Sunday Differential:** Scheduled network service is identical Monday through Saturday (47,047 daily trips), with Sunday having exactly 74 fewer scheduled trips (46,973 trips) due to inactive HSC school/college specials.

---

## 3. Headway Aggregation Levels & Intra-Window Methodology

### 3.1 Dual Aggregation Levels
1. **Route-Level Aggregation:** Computes the median headway for each route variant, then takes the median/mean across all 3,065 multi-trip routes. Each route variant receives equal weight regardless of trip volume.
   - **Median of route medians:** **65.0 minutes**
   - **Mean of route medians:** **143.9 minutes**
2. **Pooled Trip-Interval Level:** Pools all 42,108 consecutive departure intervals across all routes into a single network distribution. High-frequency trunk routes contribute proportionally more intervals.
   - **Pooled interval median:** **20.0 minutes**
   - **Pooled interval mean:** **45.1 minutes**

### 3.2 Intra-Window Peak vs Off-Peak Headways
To avoid distorted headways spanning disjoint periods (e.g. diffing across the 6-hour midday gap between morning and evening peaks), headways are calculated **strictly intra-window**:
- **Morning Peak (07:00-10:00) & Evening Peak (16:00-19:00):** Intra-window median headway of **31.5 minutes** (mean: 46.6 min across 1,276 routes with multi-trip peak service).
- **Off-Peak (Early Morning 05:00-07:00, Midday 10:00-16:00, Night 19:00-23:00):** Intra-window median headway of **40.0 minutes** (mean: 64.8 min across 2,287 routes with multi-trip off-peak service).

---

## 4. Route-Level Frequency & Top 10 Disambiguation

### 4.1 Headway Distribution by Category
| Headway Category | Route Count | Percentage |
|---|---|---|
| High Frequency (<=10 min) | 176 | 4.5% |
| Medium Frequency (10-20 min) | 361 | 9.2% |
| Moderate (20-30 min) | 395 | 10.0% |
| Low Frequency (30-60 min) | 578 | 14.7% |
| Very Low (>60 min) | 1,555 | 39.5% |
| Undefined (Single-trip) | 869 | 22.1% |

### 4.2 Top 10 Busiest Route Variants (Disambiguated by Route ID & Termini)
In Chennai MTC GTFS, each directional journey is assigned a unique `route_id`. Duplicate public short names (e.g., '500' and '3') represent separate directional variants:

| Route ID | Route Name | Direction / Termini | Total Trips | Weekday Trips | Weekend Trips | Median Headway |
|---|---|---|---|---|---|---|
| 20163 | 25 R | Anna Square TO Poonamalle | 210 | 210 | 210 | 5.0 min |
| 20167 | 25 R1 | Poonamalle TO Anna Square | 208 | 208 | 208 | 5.0 min |
| 24072 | 91 | Thiruvanmiyur TO Kilambakkam | 202 | 202 | 202 | 5.0 min |
| 24073 | 91 R | Kilambakkam TO Thiruvanmiyur | 202 | 202 | 202 | 5.0 min |
| 20578 | 57 R1 | Redhills TO Vallalar Nagar | 197 | 197 | 197 | 5.0 min |
| 22698 | 500 | Tambaram West TO Chengalpet | 186 | 186 | 186 | 5.0 min |
| 22699 | 500 | Chengalpet TO Tambaram West | 186 | 186 | 186 | 5.0 min |
| 24065 | 3 | Thiyagaraya Nagar TO Thiruvanmiyur | 185 | 185 | 185 | 5.0 min |
| 24066 | 3 | Thiruvanmiyur TO Thiyagaraya Nagar | 185 | 185 | 185 | 5.0 min |
| 22800 | 27B R | Anna Square TO M.G.R.Koyambedu | 181 | 181 | 181 | 5.0 min |

---

## 5. Time-of-Day Departure Profiles

The network departure profile is partitioned into 6 mutually exclusive, exhaustive time bands totaling **47,047 trips** (100.0% coverage):

| Time Period | Scheduled Departures | Share of Total |
|---|---|---|
| Early Morning (05-07) | 5,042 | 10.7% |
| Morning Peak (07-10) | 8,058 | 17.1% |
| Midday (10-16) | 16,859 | 35.8% |
| Evening Peak (16-19) | 8,264 | 17.6% |
| Night (19-23) | 7,293 | 15.5% |
| Late Night (23-05) | 1,531 | 3.3% |

---

## 6. Frequency Optimization Scenarios

### 6.1 Bounded Scenario Methodology
Recommendations are generated using transparent, rule-based comparison against standard urban transit planning service benchmarks:
- **Peak Target:** 15.0 minutes median headway
- **Off-Peak Target:** 25.0 minutes median headway
- **Operational Span Guardrail:** Rather than assuming a flat 6-hour expansion, the required trips are bounded to each route active operational span (S_active in hours):
- Formula: Needed Trips = ceil(S_active * 60 / Target_Headway), Additional Trips = max(0, Needed Trips - Current Trips)

> **Planning Disclaimer:** The headway targets applied are common transit planning benchmarks for high-density metropolitan systems, NOT official MTC regulatory standards. No passenger demand, vehicle allocation, or operational cost data was utilized. All estimates represent supply-side schedule scenario planning.

### 6.2 Top Bounded Scenario Candidates
| Route ID | Route Name | Evaluation Period | Observed Headway | Target Headway | Active Span | Est. Additional Trips |
|---|---|---|---|---|---|---|
| 15793 | 66M | Peak | 145.0 min | 15 min | 4.8h | +16 |
| 10672 | 104M | Peak | 147.5 min | 15 min | 4.9h | +16 |
| 11886 | 557 | Peak | 143.5 min | 15 min | 4.8h | +16 |
| 22111 | 38A R1 | Peak | 82.5 min | 15 min | 5.4h | +16 |
| 12756 | 76B | Off-Peak | 335.0 min | 25 min | 7.6h | +15 |
| 18463 | S23 | Off-Peak | 90.0 min | 25 min | 9.6h | +15 |
| 11529 | 500R | Peak | 142.5 min | 15 min | 4.8h | +15 |
| 3423 | S12 | Peak | 75.0 min | 15 min | 4.8h | +14 |
| 20972 | 56K R1 | Peak | 55.0 min | 15 min | 5.3h | +14 |
| 22779 | 583A R1 | Peak | 135.0 min | 15 min | 4.5h | +14 |

---

## 7. Documented Limitations

1. **Absence of Passenger Demand / Ridership Data:** No APC (Automated Passenger Counting), ticketing data, or crowding indicators exist in GTFS static files. High headway cannot definitively imply underserved ridership without boarding data.
2. **Missing Optional GTFS Files:** `calendar_dates.txt` (service exceptions/holidays) and `frequencies.txt` are absent from the dataset. All analysis is based on explicit `stop_times.txt` records.
3. **Static Schedule vs Operational Reality:** GTFS reflects published timetables. Delays, bus bunching, traffic congestion, and cancelled trips are not reflected.
4. **Direction Granularity:** In this feed, each `route_id` has a single uniform `direction_id`. Route variants represent one-way operational runs.
5. **Fleet & Depot Guardrails:** Fleet capacity constraints, depot locations, and driver scheduling limits are not modelled. Recommendations must be validated against MTC depot allocations.

---

## 8. Deliverables & Artifacts

| Deliverable Path | Description |
|---|---|
| `notebooks/08_bus_frequency_analysis.ipynb` | Executed end-to-end frequency analysis notebook |
| `reports/bus_frequency_analysis.csv` | Full route-level frequency metrics (3,934 routes) |
| `reports/bus_frequency_recommendations.csv` | Prioritized bounded scenario recommendations (2,150 entries) |
| `reports/figures/fig_weekday_weekend_frequency.png` | Weekday vs weekend service comparison |
| `reports/figures/fig_headway_distribution.png` | Network headway distribution histogram |
| `reports/figures/fig_time_of_day_frequency.png` | Departures across standard transit time bands |
| `reports/figures/fig_peak_offpeak_headway.png` | Peak vs off-peak intra-window headway boxplot |
| `reports/figures/fig_frequency_optimization_comparison.png` | Current vs scenario headway for top candidate routes |
