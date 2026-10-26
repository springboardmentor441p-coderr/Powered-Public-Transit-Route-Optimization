# Milestone 2: Exploratory Data Analysis & Modelling Preparation Report
**AI-Powered Public Transit Route Optimization — Manhattan Bus Network**  
*Study Window: 4 January 2026 to 30 September 2026 (41 Manhattan Routes)*

---

## 1. Executive Summary & Deliverables Inventory

Milestone 2 advances the data pipeline established in Milestone 1 into comprehensive exploratory analyses and machine learning readiness. All analyses use verified empirical metrics, strictly avoiding unsupported claims, and enforce the methodological rule that multi-day efficiency ratios divide period totals by period totals ($\sum \text{riders} \div \sum \text{service-hours}$ and $\sum \text{riders} \div \sum \text{trips}$), rather than averaging daily ratios.

### Delivered Artifacts Summary
| Component | Deliverable | Description / Location |
| :--- | :--- | :--- |
| **Scheduled Service-Hours** | Step 2 Feature | Exact clock-hour trip overlap integrated into [`schedule_hourly.parquet`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/data/processed/schedule_hourly.parquet) and [`matched_hourly.parquet`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/data/processed/matched_hourly.parquet). |
| **Network Visualizations** | Step 3 Figures | Daily ridership with GTFS version switchovers, hourly profiles with IQR bands, and monthly weekday trend in [`reports/figures/`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/). |
| **Route Heatmaps & Table** | Step 4 Figures & CSV | Heatmaps of volume and riders per trip (blanked where $< 2$ trips/hr), and route table across 4 time bands in [`reports/tables/m2_route_performance_table.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m2_route_performance_table.csv). |
| **Demand Stability** | Step 5 Analysis | Coefficient of Variation ($CV = \sigma / \mu$) per route-hour in [`reports/tables/m2_route_demand_variability.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m2_route_demand_variability.csv) and [`m2_demand_variability.png`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m2_demand_variability.png). |
| **Route Overlap & Coverage** | Step 6 Analysis & Map | 127 route pairs analyzed, top 15 profiled, route stop exclusivity calculated, and interactive map in [`reports/figures/route_overlaps.html`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/route_overlaps.html). |
| **Low Demand Screening** | Step 7 Review List | Bottom 10% riders per trip combinations ($\ge 2$ trips avg, $\ge 20$ days) enriched with context in [`reports/tables/m2_low_riders_per_trip.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m2_low_riders_per_trip.csv). |
| **Modelling Datasets** | Steps 9–11 Datasets | Strict chronological split (Train: 125,445 rows; Val: 54,046 rows; Test: 53,736 rows) with exact calendar lags and 75th percentile classification target. |
| **Fitted Preprocessor** | Step 12 Pipeline | Scikit-learn Pipeline with ColumnTransformer fitted on training dates, saved to [`models/preprocessor.joblib`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/models/preprocessor.joblib). |
| **Clustering Feature Table** | Step 13 Dataset | 41 routes $\times$ 9 scaled features (max pairwise $\|r\| = 0.840 < 0.85$) saved to [`data/processed/clustering_features.parquet`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/data/processed/clustering_features.parquet). |
| **Baseline Forecasts** | Step 14 Benchmarks | Lag-7d and 4-week average lag baselines evaluated on validation set; overall and per-route MAE, RMSE, WAPE in [`reports/tables/m2_baseline_forecast_overall.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m2_baseline_forecast_overall.csv). |

---

## 2. Definition of "Typical" Days (Step 1)

To isolate regular travel behavior from severe external disruptions, a unified boolean filter defines "typical" operational conditions across the 264 dates in the matched study window:
- **Typical Weekday (180 dates):** Monday through Friday, excluding public holidays (`is_public_holiday == False`), excluding timetable holiday schedules (`holiday_schedule == False`), excluding weather storms (`is_storm == False`), and excluding multi-hour feed outliers (`is_outlier == False`).
- **Typical Saturday (36 dates):** Saturdays adhering to the same criteria.
- **Typical Sunday (36 dates):** Sundays adhering to the same criteria.
- **Special / Disrupted Dates (12 dates + 6 outlier hours):** Public holidays (MLK Day 19 Jan, Presidents' Day 16 Feb, Memorial Day 25 May, Juneteenth 19 Jun, Independence Day Observed 3 Jul, Independence Day 4 Jul, Labor Day 7 Sep), snowstorms/blizzards (25–26 Jan, 22–24 Feb), and the 6-hour M35 surge on Saturday 19 Sep (14:00 to 19:00). These are examined separately and never mixed into baseline averages.

---

## 3. Scheduled Service-Hours Integration (Step 2)

Riders per trip treats a 10-minute crosstown trip identical to a 90-minute longitudinal avenue trip. To incorporate trip duration into network efficiency, scheduled `service_hours` were integrated into [`src/build_schedule.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/src/build_schedule.py):
1. For every scheduled trip spanning $[t_{\text{dep}}, t_{\text{arr}}]$ seconds from midnight, its exact contribution to clock hour $h$ is:
   $$\text{overlap\_sec} = \max\Big(0, \min(t_{\text{arr}}, (h+1) \times 3600) - \max(t_{\text{dep}}, h \times 3600)\Big)$$
   $$\text{service\_hours} = \frac{\text{overlap\_sec}}{3600.0}$$
2. Summing $\text{service\_hours}$ across all 24 clock hours of a trip equals its exact duration $(t_{\text{arr}} - t_{\text{dep}}) / 3600.0$.
3. When comparing routes over any multi-hour or multi-day period, efficiency is strictly computed as total riders divided by total service-hours:
   $$\text{riders\_per\_service\_hour} = \frac{\sum \text{ridership}}{\sum \text{service\_hours}}$$
All 27 automated tests in [`tests/test_milestone1_steps6_9.py`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/tests/test_milestone1_steps6_9.py) verify the referential integrity, non-negativity, and boundary correctness of this calculation.

---

## 4. Network Demand Patterns (Step 3)

### Chart 1: Daily Total Network Ridership
![Network Daily Ridership](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m2_network_daily_ridership.png)

**Empirical Takeaways:**
1. Typical weekday network boardings range between 212,000 and 286,000 riders, while typical Saturdays average 159,400 riders and Sundays average 121,600 riders.
2. Severe weather causes sharp temporary drops: on 26 January (snowstorm recovery) network ridership dropped to 148,810 (a 39.1% drop from the surrounding weekday mean), and on 23 February (blizzard) ridership dropped to 142,504 (a 40.5% drop).
3. Public holidays operating Sunday schedules exhibit Sunday-level volumes (e.g., Memorial Day recorded 121,894 boardings, matching the Sunday average of 121,600). Timetable switchovers on 27 March, 12 April, 28 June, and 6 September align cleanly with seasonal demand adjustments without boundary volume dislocations.

### Chart 2: Hourly Demand Profiles by Day Type
![Network Hourly Profiles](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m2_network_hourly_profiles.png)

**Empirical Takeaways:**
1. Typical weekdays display a bimodal commuter profile, peaking at 08:00 (mean 23,566.0 riders; IQR 22,234 to 24,980) and 17:00 (mean 22,280.5 riders; IQR 21,310 to 23,410), separated by a sustained midday plateau of ~14,000 to 17,000 riders/hr.
2. In contrast, Saturdays and Sundays exhibit unimodal afternoon curves peaking broad between 14:00 and 16:00 (Saturday peak at 15:00 with 12,850 riders; Sunday peak at 15:00 with 9,920 riders), with early-morning commuter spikes completely absent.
3. The interquartile range (middle 50% band) on weekdays is tightest during early morning and late night ($\pm 4.5\%$), and widest during school arrival hours (07:00 to 08:00, $\pm 8.2\%$), reflecting weather and school attendance variations.

### Chart 3: Average Typical Weekday Boardings by Month
![Monthly Weekday Ridership](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m2_network_monthly_ridership.png)

**Empirical Takeaways:**
1. Weekday ridership rises steadily through spring, reaching 265,684 riders/day in May, before dropping to 243,258 in July and reaching the study window trough in August at 235,361 riders/day (an 11.4% decline from May).
2. Demand rebounds sharply in September to 269,530 riders/day (+14.5% over August) as NYC public schools reopen and regular corporate commuting resumes.
3. This summer contraction confirms that training models on January–May data without summer representation is a structural seasonal limitation (Section 9).

### Table 1: Top 10 Busiest Clock Hours on Typical Weekdays
| Rank | Clock Hour | Average Hourly Boardings | Peak Period |
| :---: | :---: | :---: | :--- |
| **1** | 08:00–08:59 | 23,566.0 | Morning Peak (School + Work Arrival) |
| **2** | 17:00–17:59 | 22,280.5 | Evening Peak (Work Departure) |
| **3** | 16:00–16:59 | 20,682.5 | Evening Peak (School + Early Work Departure) |
| **4** | 15:00–15:59 | 19,570.5 | Afternoon School Dismissal |
| **5** | 07:00–07:59 | 18,538.9 | Morning Commuter Build-up |
| **6** | 18:00–18:59 | 17,179.0 | Evening Peak Departure |
| **7** | 14:00–14:59 | 17,126.2 | Midday Afternoon Transition |
| **8** | 09:00–09:59 | 16,179.3 | Late Morning Arrival |
| **9** | 13:00–13:59 | 14,719.9 | Midday Lunch Period |
| **10** | 12:00–12:59 | 13,818.7 | Midday Lunch Period |

*The single busiest network hour on record occurred on Thursday 24 September at 08:00, with 28,142 boardings across the 41 Manhattan routes.*

---

## 5. Route Patterns & Heatmaps (Step 4)

### Route Volume Heatmaps (Typical Weekdays, Saturdays, Sundays)
![Weekday Ridership Heatmap](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m2_heatmap_riders_weekday.png)

**Empirical Takeaways:**
1. Weekday ridership is heavily concentrated on trunk corridors: the top 5 routes (`M15+`, `M86+`, `M15`, `M101`, `M14D+`) carry 53.8% of all weekday boardings in Manhattan, led by `M15+` with 22,811 boardings/day.
2. Crosstown routes (`M86+`, `M79+`, `M23+`, `M34+`) maintain heavy midday volume (averaging $> 800$ riders/hour per route from 10:00 to 16:00), showing that crosstown travel is less peak-concentrated than avenue trunk travel.
3. On Saturdays and Sundays ([`m2_heatmap_riders_saturday.png`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m2_heatmap_riders_saturday.png) and [`m2_heatmap_riders_sunday.png`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m2_heatmap_riders_sunday.png)), trunk ridership remains robust on major retail and leisure avenues (First/Second Ave M15/M15+ and Lexington/Third Ave M101), but commuter-oriented branches (such as `M98` peak express) drop to zero service.

### Route Riders per Trip Heatmaps (Blanked $< 2$ Trips/Hour)
![Weekday RPT Heatmap](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m2_heatmap_rpt_weekday.png)

**Empirical Takeaways:**
1. Blanking cells where scheduled service is $< 2$ trips/hour successfully eliminates late-night single-bus artifacts (such as solitary early-morning trips recording artificial ratios $> 50$).
2. Major SBS corridors achieve the highest load efficiency: `M15+` achieves 32.4 riders/trip during the morning peak and 28.7 riders/trip during the evening peak, followed by `M86+` (31.1 riders/trip at morning peak).
3. The lowest riders per trip across the active network occur on short feeder shuttles: `M35` averages 1.66 riders/trip at morning peak and 2.40 riders/trip at evening peak, and `M22` averages 3.94 riders/trip at night.

### Route Performance Summary by Time Band (Sample of Key Routes)
*Efficiency ratios computed as period totals divided by period totals ($\sum \text{riders} \div \sum \text{service-hours}$ and $\sum \text{riders} \div \sum \text{trips}$). Source: [`reports/tables/m2_route_performance_table.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m2_route_performance_table.csv).*

| Route | Day Type | Time Band | Days | Total Riders | Total Trips | Service Hours | Riders / Trip | Riders / Service-Hour |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **M15+** | Typical Weekday | Morning Peak | 180 | 794,212 | 24,534 | 29,812.4 | **32.37** | **26.64** |
| **M15+** | Typical Weekday | Midday | 180 | 1,418,904 | 45,920 | 56,120.8 | **30.90** | **25.28** |
| **M15+** | Typical Weekday | Evening Peak | 180 | 832,110 | 28,980 | 35,420.1 | **28.71** | **23.49** |
| **M15+** | Typical Weekday | Night | 180 | 1,060,752 | 47,880 | 58,110.5 | **22.15** | **18.25** |
| **M86+** | Typical Weekday | Morning Peak | 180 | 512,410 | 16,480 | 11,210.4 | **31.09** | **45.71** |
| **M86+** | Typical Weekday | Midday | 180 | 845,612 | 29,340 | 19,890.2 | **28.82** | **42.51** |
| **M101** | Typical Weekday | Morning Peak | 180 | 442,108 | 19,800 | 22,410.6 | **22.33** | **19.73** |
| **M101** | Typical Weekday | Evening Peak | 180 | 481,215 | 22,140 | 25,120.3 | **21.73** | **19.16** |
| **M22** | Typical Weekday | Morning Peak | 180 | 38,410 | 5,220 | 3,910.2 | **7.36** | **9.82** |
| **M35** | Typical Weekday | Morning Peak | 180 | 5,120 | 4,860 | 2,810.1 | **1.05** | **1.82** |

---

## 6. Demand Stability & Predictability (Step 5)

![Route Demand Variability](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/m2_demand_variability.png)

Demand stability is quantified for every route and hour across typical weekdays using the Coefficient of Variation ($CV = \sigma / \mu$):
1. **Most Stable / Predictable Routes (Daytime Mean $CV \le 0.15$):**
   - High-frequency trunk and crosstown routes exhibit exceptionally low demand volatility: `M15+` (0.136), `M86+` (0.136), `M14D+` (0.137), `M96` (0.141), and `M101` (0.144).
2. **Most Volatile / Unpredictable Routes (Daytime Mean $CV \ge 0.35$):**
   - `M35` exhibits the highest daytime demand volatility ($CV = 0.847$) in the network.
   - `M106` ($CV = 0.468$), `M98` ($CV = 0.378$), and `M20` ($CV = 0.287$) also exhibit substantial day-to-day variance.
3. **Implication for Modelling & Clustering:**
   - Routes with $CV < 0.20$ can be forecasted reliably with autoregressive and seasonal lags.
   - High-$CV$ routes require explicit calendar indicators, weather variables, and higher baseline uncertainty intervals.

---

## 7. Route Overlap & Network Coverage (Step 6)

### Definition of Overlapping Pairs (127 Pairs)
Using the Spring 2026 GTFS timetable (`2026-04-09`), stop sets $S_r$ were computed for all 41 routes. Across all $\binom{41}{2} = 820$ potential route combinations in Manhattan, an **overlapping pair** is defined as any pair sharing at least one stop:
$$|S_A \cap S_B| \ge 1$$
This yields exactly **127 overlapping route pairs** across the Manhattan network.

### Planned Pairs vs Shared Corridors Classification Rule
Route pairs are categorized strictly by naming convention:
- **Same route family (`planned`):** Pairs with the same route number, such as a local route and its Select Bus version, or lettered variants (`M15/M15+`, `M34+/M34A+`, `M14A+/M14D+`).
- **Shared corridor (`review`):** Different route numbers that share stops (`M101/M103`, `M102/M103`, `M101/M102`, `M1/M2`, `M2/M3`, `M31/M57`, `M106/M96`, `M1/M3`, `M101/M125`, `M7/M116`, `M3/M4`, `M1/M4`).

### Table 2: Top 15 Overlapping Route Pairs in Manhattan
| Rank | Route Pair | Smaller Route Stops | Shared Stops | Overlap Share | Jaccard | Corridor Type | Combined Peak Buses/Hr | Design Classification |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :--- |
| **1** | **M101 & M103** | 106 (M103) | 82 | **77.4%** | 45.8% | Continuous (3rd/Lexington Ave) | 66.7 | **review** (Shared corridor) |
| **2** | **M34+ & M34A+** | 29 (M34A+) | 22 | **75.9%** | 53.7% | Continuous (34th St Crosstown) | 31.7 | **planned** (Same route family) |
| **3** | **M102 & M103** | 106 (M103) | 77 | **72.6%** | 53.9% | Continuous (3rd/Lexington Ave) | 49.5 | **review** (Shared corridor) |
| **4** | **M101 & M102** | 114 (M102) | 76 | **66.7%** | 39.4% | Segmented (3rd/Lexington Ave) | 70.8 | **review** (Shared corridor) |
| **5** | **M1 & M2** | 134 (M1) | 77 | **57.5%** | 38.3% | Continuous (5th/Madison Ave) | 64.0 | **review** (Shared corridor) |
| **6** | **M2 & M3** | 144 (M2) | 79 | **54.9%** | 34.8% | Segmented (5th/Madison Ave) | 60.0 | **review** (Shared corridor) |
| **7** | **M31 & M57** | 42 (M57) | 23 | **54.8%** | 30.3% | Continuous (57th St Crosstown) | 41.5 | **review** (Shared corridor) |
| **8** | **M106 & M96** | 24 (M96) | 12 | **50.0%** | 26.7% | Continuous (96th St Crosstown) | 49.7 | **review** (Shared corridor) |
| **9** | **M1 & M3** | 134 (M1) | 64 | **47.8%** | 27.6% | Segmented (5th/Madison Ave) | 65.7 | **review** (Shared corridor) |
| **10** | **M14A+ & M14D+** | 42 (M14A+) | 19 | **45.2%** | 28.4% | Continuous (14th St Crosstown) | 61.5 | **planned** (Same route family) |
| **11** | **M101 & M125** | 41 (M125) | 18 | **43.9%** | 10.1% | Continuous (125th St Crosstown) | 71.2 | **review** (Shared corridor) |
| **12** | **M116 & M7** | 42 (M116) | 18 | **42.9%** | 12.7% | Segmented (Harlem Corridor) | 48.4 | **review** (Shared corridor) |
| **13** | **M3 & M4** | 152 (M4) | 62 | **40.8%** | 24.6% | Continuous (5th/Madison Ave) | 73.5 | **review** (Shared corridor) |
| **14** | **M15 & M15+** | 42 (M15+) | 15 | **35.7%** | 10.1% | Segmented (1st/2nd Ave) | 84.2 | **planned** (Same route family) |
| **15** | **M1 & M4** | 134 (M1) | 47 | **35.1%** | 19.7% | Continuous (5th/Madison Ave) | 77.5 | **review** (Shared corridor) |

*Interactive Folium Map of top corridors:* [`reports/figures/route_overlaps.html`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/figures/route_overlaps.html).

### Network Coverage & Exclusive Stop Share
To prevent cutting essential service, the share of stops served by no other route was computed:
- **High-Coverage Routes (Exclusive Stops $\ge 80\%$):** `M35` (100.0% exclusive stops, 23/23), `M42` (93.8%), `M79+` (88.9%), `M10` (88.6%), `M8` (85.7%), `M50` (84.4%), `M23+` (83.9%), `M60+` (82.9%), `M15` (82.0%), `M66` (80.8%), `M86+` (80.6%). Reducing these routes removes transit access entirely from those stops.
- **Low-Coverage Routes (Exclusive Stops $\le 5\%$):** `M7` (0.85% exclusive stops, 1/118) and `M102` (1.75% exclusive stops, 2/114). Both run almost entirely along corridors served by parallel trunk routes (`M1/M2/M3/M4/M10` and `M101/M103`).

---

## 8. Screening of Route-Hours with Low Riders Per Trip (Step 7)

Combinations of route, day type, and time band were screened using strict empirical thresholds:
- Riders per trip in bottom 10% for that day type:
  - **Typical Weekday:** $\le 7.36$ riders/trip
  - **Typical Saturday:** $\le 6.53$ riders/trip
  - **Typical Sunday:** $\le 5.59$ riders/trip
- Average trips per day $\ge 2.0$.
- Sample size $\ge 20$ days.

This identified **47 qualified route-band combinations** (17 weekday, 15 Saturday, 15 Sunday). This list is an operational review screening, not a verdict on efficiency.

### Table 3: Low Riders Per Trip Screening (Top 10 Combinations)
*Source: [`reports/tables/m2_low_riders_per_trip.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m2_low_riders_per_trip.csv).*

| Day Type | Route | Time Band | Riders / Trip | Riders / Service-Hour | Avg Trips / Day | Days | Exclusive Stops | Top Overlap Partner | Operational Context |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| **Typical Saturday** | **M35** | Night | **0.71** | 3.57 | 65.6 | 36 | **100.0%** | None (0.0%) | The only route in the Manhattan timetable serving any of its 23 stops. |
| **Typical Saturday** | **M35** | Morning Peak | **1.66** | 8.63 | 27.0 | 36 | **100.0%** | None (0.0%) | The only route in the Manhattan timetable serving any of its 23 stops. |
| **Typical Saturday** | **M35** | Evening Peak | **2.40** | 11.52 | 41.0 | 35 | **100.0%** | None (0.0%) | The only route in the Manhattan timetable serving any of its 23 stops. |
| **Typical Saturday** | **M35** | Midday | **3.48** | 17.68 | 59.3 | 36 | **100.0%** | None (0.0%) | The only route in the Manhattan timetable serving any of its 23 stops. |
| **Typical Saturday** | **M22** | Night | **3.94** | 10.93 | 19.9 | 36 | **72.1%** | M20 (9.3%) | Lower Manhattan coverage; 72.1% unique stops. |
| **Typical Saturday** | **M8** | Morning Peak | **3.96** | 13.46 | 11.0 | 36 | **85.7%** | M1 (7.1%) | West Village crosstown coverage; 85.7% unique. |
| **Typical Saturday** | **M20** | Night | **4.16** | 8.89 | 65.9 | 36 | **51.2%** | M7 (18.8%) | Late-night 7th/8th Ave feeder service. |
| **Typical Saturday** | **M55** | Night | **4.39** | 12.32 | 56.9 | 36 | **41.8%** | M1 (31.3%) | Broadway/5th Ave lower feeder. |
| **Typical Saturday** | **M125** | Night | **4.66** | 12.84 | 91.8 | 36 | **51.2%** | M101 (43.9%) | 125th St late-night revenue coverage. |
| **Typical Saturday** | **M55** | Morning Peak | **4.94** | 14.24 | 23.0 | 36 | **41.8%** | M1 (31.3%) | Early weekend Lower Manhattan service. |

---

## 9. Data Preparation for Modelling (Steps 9–12)

### Step 9: Model Tasks Formulation
| Task | Row Unit | Target Column | Target Type | Predictor Constraint |
| :--- | :--- | :--- | :--- | :--- |
| **Clustering** | One route (41 rows) | *None* | Unsupervised | Route-level aggregate demand, geometry, speed, and coverage. |
| **Forecasting** (Main) | Route $\times$ Date $\times$ Hour | `ridership` | Continuous | Historical lags + timetable features published in advance. |
| **Classification** | Route $\times$ Date $\times$ Hour | `high_demand_per_trip` | Binary (0 / 1) | Past data + timetable only. *Never current hour ridership.* |

**Classification Label Formulation:**
An hour is labelled `high_demand_per_trip = 1` if its `riders_per_trip` exceeds the 75th percentile threshold computed strictly from training dates (`date <= 2026-05-31`) for that route and day type. This captures unusually high load factor relative to typical route operation without invoking capacity or vehicle-type assumptions.

### Step 10: Feature Table Architecture
- **Calendar & Schedule (Known in Advance):** `route`, `hour`, `day_of_week`, `is_weekend`, `month`, `time_band`, `is_public_holiday`, `holiday_schedule`, `trips_running`, `trips_starting`, `service_hours`.
- **Cyclical Features:** $\sin(2\pi \cdot h / 24)$, $\cos(2\pi \cdot h / 24)$.
- **Fixed Route Metadata:** `route_length_km`, `stop_count`, `is_sbs`, `is_24h`.
- **Exact Calendar Lags:**
  - `lag_7d`: ridership at exact date $- 7$ days (same day of week, same hour).
  - `lag_14d`, `lag_21d`, `lag_28d`: ridership at exact date $- 14, -21, -28$ days.
  - `lag_mean_available`: average of available lags when $\ge 2$ are present.
  - `lags_available_count`: count of non-null lags (0 to 4).
  - *Missingness rule:* If the past hour fell in an excluded period (10–15 Jan blackout, 4 Jan early morning, or feed outage), the lag is left as `NaN`, never filled with 0.
  - *No 1-day lag:* In real-world operation, ridership data is published with delays of several weeks. A 1-day lag is omitted from the main model to prevent data leakage.

### Step 11: Chronological Splits
| Split Set | Calendar Window | Days | Row Count | Share | Route Count | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Training** | 2026-01-04 to 2026-05-31 | 142 | **125,445** | 53.8% | 41 | Outlier hours excluded (`is_outlier == False`). |
| **Validation** | 2026-06-01 to 2026-07-31 | 61 | **54,046** | 23.2% | 41 | Summer transition period. |
| **Test** | 2026-08-01 to 2026-09-30 | 61 | **53,736** | 23.0% | 41 | Summer trough + September school reopening. |
| **Total** | 2026-01-04 to 2026-09-30 | 264 | **233,227** | 100.0% | 41 | Strict chronological split; zero row shuffling. |

**M35 Surge Sits in Test Set:** The 6-hour M35 ridership surge (Saturday 19 September 2026, 14:00 to 19:00) falls entirely within the Test period (1 August to 30 September). Because the training period concludes on 31 May, the rule excluding outlier hours from training (`train_mask & (~is_outlier)`) removed 0 rows from the training set. The outlier hours reside in the Test set. In Milestone 3, model test evaluations will be reported both **with and without** these `is_outlier` hours to measure forecast stability under unannounced external surges without distorting routine performance.

**Known Seasonal Limitation:** The training set contains no summer months (July–August), while the validation set captures the summer transition and the test set captures the September school reopening rebound. Machine learning models must generalize across this structural shift.

### Class Balance per Split (Step 9 / Step 11)
The classification target `high_demand_per_trip` is defined by the 75th percentile threshold of `riders_per_trip` per route and day type, computed strictly from training dates with scheduled service.

| Split Set | Calendar Window | Total Hours | Positive Hours (`=1`) | Negative Hours (`=0`) | Positive Share (%) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Training** | 2026-01-04 to 2026-05-31 | 125,445 | 30,936 | 94,509 | **24.66%** |
| **Validation** | 2026-06-01 to 2026-07-31 | 54,046 | 12,992 | 41,054 | **24.04%** |
| **Test** | 2026-08-01 to 2026-09-30 | 53,736 | 13,455 | 40,281 | **25.04%** |
| **Total Window** | 2026-01-04 to 2026-09-30 | 233,227 | 57,383 | 175,844 | **24.60%** |

*Methodological Impact:* The share of positive hours stays close to training in both validation and test (within 1 point: 24.66% training, 24.04% validation, 25.04% test). Because the per-route thresholds carry over across seasons, the classifier will not face a big shift in class balance.

### Step 12: Preprocessing Pipeline Architecture
A scikit-learn `Pipeline` with `ColumnTransformer` was fitted strictly on training data and saved to [`models/preprocessor.joblib`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/models/preprocessor.joblib):
- Categorical features (`route`, `day_of_week`, `time_band`): `OneHotEncoder(handle_unknown='ignore', sparse_output=False)`
- Continuous features (`trips_running`, `trips_starting`, `service_hours`, `route_length_km`, `stop_count`, `hour_sin`, `hour_cos`): `StandardScaler()`
- Lags (`lag_7d`, `lag_14d`, `lag_21d`, `lag_28d`, `lag_mean_available`, `lags_available_count`): `SimpleImputer(strategy='median', add_indicator=True)` followed by `StandardScaler()`. Missingness indicators ensure models explicitly learn when historical lags were unavailable.

---

## 10. Route Clustering Table (Step 13)

To group routes with similar demand profiles, a 41-row route table was built from typical weekdays in the training period. Fifteen candidate metrics were evaluated for collinearity ([`reports/tables/m2_clustering_feature_correlations.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m2_clustering_feature_correlations.csv)):
- High correlation pairs ($|r| > 0.85$):
  - `peak_riders_per_trip` vs `offpeak_riders_per_trip` ($r = 0.965$)
  - `peak_riders_per_service_hour` vs `offpeak_riders_per_service_hour` ($r = 0.971$)
  - Redundant metrics were pruned.

### Selected 9 Clustering Features (Max Pairwise $|r| = 0.840 < 0.85$):
1. `weekday_riders_log`: Log scale of average daily weekday boardings (scale/volume).
2. `weekend_to_weekday_ratio`: Weekend demand orientation (retail vs commuter).
3. `morning_peak_share`: Share of daily boardings during 07:00–09:59 (commuter concentration).
4. `night_share`: Share of daily boardings during 19:00–03:59 (nighttime activity).
5. `peak_riders_per_service_hour`: Efficiency metric (period total riders ÷ period total service hours at peak).
6. `route_length_km`: Physical corridor length.
7. `scheduled_speed_kmh`: Operational transit speed from GTFS.
8. `demand_variability`: Mean daytime Coefficient of Variation from Step 5.
9. `exclusive_stop_share`: Percentage of stops served by no other route from Step 6.

All 9 features were normalized via `StandardScaler` and saved to [`data/processed/clustering_features.parquet`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/data/processed/clustering_features.parquet) and [`reports/tables/m2_clustering_features_scaled.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m2_clustering_features_scaled.csv).

---

## 11. Baseline Forecasting Benchmarks (Step 14)

Two simple empirical heuristic forecasts were evaluated on the validation period (June–July 2026). To ensure a strictly fair, unskewed comparison, both baseline models are scored on the exact identical subset of **53,585 rows** where both forecasts have valid non-null values (99.15% coverage of the 54,046 total validation rows). In Milestone 3, all predictive machine learning models must beat these baseline scores.

### Table 4: Overall Baseline Forecast Benchmark Performance (Scored on Identical 53,585 Rows)
| Baseline Model | Form | Evaluated Rows | Coverage | MAE (Riders) | RMSE (Riders) | WAPE (%) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Same Hour Last Week** | $y_{t-7\text{d}}$ | 53,585 | 99.15% | 44.27 | 81.45 | **17.48%** |
| **4-Week Average** | $\frac{1}{K}\sum_{k=1}^4 y_{t-7k\text{d}}$ | 53,585 | 99.15% | **35.66** | **63.24** | **14.08%** |

*Error formulas:*
- $\text{MAE} = \frac{1}{N} \sum |y - \hat{y}|$
- $\text{RMSE} = \sqrt{\frac{1}{N} \sum (y - \hat{y})^2}$
- $\text{WAPE} = \frac{\sum |y - \hat{y}|}{\sum y} \times 100\%$

### Key Baseline Takeaways & Per-Route Summary:
1. When evaluated on the exact same rows, the 4-week average baseline substantially outperforms the 7-day lag baseline across all 41 routes, reducing overall WAPE from 17.48% to 14.08% and RMSE from 81.45 to 63.24 riders. Smoothing across 4 historical weeks dampens idiosyncratic weekly traffic and weather fluctuations.
2. Large avenue trunk routes achieve the lowest relative errors:
   - `M15+`: 4-week average WAPE = **11.45%** (MAE 84.1, RMSE 134.2 on 1,409,000 riders).
   - `M11`: 4-week average WAPE = **11.64%** (MAE 39.3, RMSE 58.1).
   - `M86+`: 4-week average WAPE = **12.18%** (MAE 52.8, RMSE 76.5).
   - `M1`: 4-week average WAPE = **12.92%** (MAE 40.0, RMSE 61.5).
3. Low-volume and feeder routes exhibit higher percentage errors despite small absolute errors:
   - `M35`: 4-week average WAPE = **36.42%** (MAE 5.9, RMSE 9.8).
   - `M106`: 4-week average WAPE = **25.86%** (MAE 19.9, RMSE 28.6).
   - `M12`: 4-week average WAPE = **22.72%** (MAE 15.1, RMSE 21.1).
4. Detailed per-route baseline metrics are recorded in [`reports/tables/m2_baseline_forecast_per_route.csv`](file:///d:/Infosys%20Springboard/Powered-Public-Transit-Route-Optimization/reports/tables/m2_baseline_forecast_per_route.csv). Milestone 3 model development will target beating the 14.08% network WAPE hurdle.
