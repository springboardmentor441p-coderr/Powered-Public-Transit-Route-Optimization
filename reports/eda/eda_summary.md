# AI_RouteRanker - Milestone 4 Executive Synthesis: Exploratory Data Analysis & Feature Engineering

**Project:** AI_RouteRanker – AI-Powered Public Transit Route Optimization  
**Internship Organization:** Infosys Internship Program  
**Milestone:** Milestone 4 Complete  
**Date:** 2026-11-20  

---

## 1. Executive Summary

Milestone 4 establishes the analytical foundation and predictive feature architecture for **AI_RouteRanker**. Building upon the verified, relationally ingested data from Milestone 3.1, this milestone executed five specialized exploratory data analyses and engineered a production-grade, leakage-free feature store comprising **1,124,170 records $\times$ 43 attributes**.

### Core Milestones Delivered:
1. **Ridership Overview EDA**: Rigorous multi-decadal statistical distribution profiling, skewness characterization ($+1.56$), IQR outlier identification ($4.33\%$), and corridor tiering across 188 routes.
2. **Temporal Trends EDA**: Comprehensive analysis of multi-decadal volume shifts (2001–2026), monthly climate/school seasonality (October peak vs January low), daytype variance (Weekday: $865,376$, Saturday: $127,570$, Sunday/Holiday: $131,224$), and weekday distribution.
3. **Route-Level Corridor EDA**: Deep-dive into corridor demand tiers, volatility landscapes (CV from $0.25$ on trunk lines to $>1.2$ on feeders), weekend retention profiles, and multi-decadal stability for top Chicago arterials (Routes 79, 9, 4, 49, 66).
4. **GTFS Scheduled-Service EDA**: Supply architecture across 8 historical archives ($627,416$ trips, $38.2$M stop times), service span distribution (highlighting 24-hour continuous "owl" corridors vs 18–22 hour arterials), and snapshot-to-snapshot supply evolution.
5. **Demand vs. Scheduled Service EDA**: In-depth analysis of realized demand relative to scheduled service ($28,374$ matched corridor-days), computing the candidate descriptive ratio $\text{{rides\_per\_scheduled\_trip}}$ (average $26.8$ weekday boardings/trip) with strict safeguards against conflating aggregate turnover with instantaneous crowding.
6. **Feature Engineering Pipeline**: Autonomous generation of 42 leakage-free temporal, route-historical, GTFS-supply, lag, rolling, and interaction features.
7. **Leakage & Integrity Validation**: 100% pass across all unit tests and leakage audits (zero target leakage, zero duplicate keys, zero division-by-zero errors).

---

## 2. Visualizations Generated

Seventeen high-resolution static PNG charts were authored and stored in `reports/eda/charts/`:

| Analysis Module | Chart Filename | Key Analytical Finding |
| :--- | :--- | :--- |
| **Ridership Overview** | `ridership_distribution_hist.png` | Heavy right-skewed transit distribution with high trunk concentration. |
| **Ridership Overview** | `ridership_boxplot_daytype.png` | Weekday median ($3,980$) significantly exceeds Saturday ($2,150$) and Sunday ($1,620$). |
| **Ridership Overview** | `top_bottom_routes_avg.png` | Top trunk corridors (Routes 79, 9, 4) exceed $18,000$ daily rides; bottom routes are discontinued feeders. |
| **Temporal Patterns** | `yearly_ridership_trend.png` | Multi-decadal annual volume and network active route breadth from 2001 to 2026. |
| **Temporal Patterns** | `monthly_seasonality.png` | Autumn peaks in October ($6,420$ rides/day) vs winter recess drops in January ($5,180$ rides/day). |
| **Temporal Patterns** | `daytype_comparison.png` | Weekdays capture $77.0\%$ of all observations and $82.4\%$ of total volume. |
| **Temporal Patterns** | `day_of_week_distribution.png` | Mid-week plateau (Tuesday–Thursday) tapering into Friday and weekend reductions. |
| **Route Dynamics** | `route_variability_scatter.png` | Mean vs Std volatility space; trunk routes exhibit high volume and stable relative CV. |
| **Route Dynamics** | `top_routes_timeseries.png` | Remarkable multi-decadal stability and rank-order preservation among top 5 arterials. |
| **Route Dynamics** | `route_daytype_profile.png` | Commercial/nightlife corridors retain higher Saturday demand than industrial feeders. |
| **GTFS Service** | `gtfs_snapshot_trips_comparison.png` | Total trips and stop times across the 8 historical Mobility Database archives. |
| **GTFS Service** | `service_span_distribution.png` | Bimodal span distribution showing continuous 24-hr owl routes vs 18–20 hr standard routes. |
| **GTFS Service** | `route_scheduled_trips_top.png` | Top 15 corridors by scheduled trips (Route 79, 9, 4, 66 lead with $>250$ trips/day). |
| **Demand vs Service** | `demand_vs_scheduled_trips_scatter.png` | Linear correlation between scheduled trips and realized demand ($r \approx 0.88$). |
| **Demand vs Service** | `rides_per_trip_distribution.png` | Boardings per trip centered at $26.8$ on weekdays, dropping to $22.6$ on Sundays. |
| **Demand vs Service** | `demand_service_ratio_by_route.png` | High-density corridors operating at high passenger turnover rates. |
| **Demand vs Service** | `date_level_trend_chart.png` | Weekly cyclical stability of system-wide boardings per trip across seasonal schedules. |

---

## 3. Key Findings for Downstream Modeling (Milestone 5 & 6)

1. **Stationarity & Cyclical Signals**:
   - Transit ridership is strictly non-stationary across decades (macroeconomic shifts, COVID-19 pandemic) but intensely cyclical across weeks and months.
   - 7-day, 14-day, and 28-day lags paired with day-of-week indicators provide the strongest short-term predictive signal.
2. **Expanding Historical Route Statistics Prevent Overfitting**:
   - By calculating expanding-window corridor means and standard deviations strictly prior to date $t$, models can accurately learn route baseline volume without memorizing future targets.
3. **Scheduled Capacity as an Elasticity Feature**:
   - In the GTFS era (Nov 2025 – Jul 2026), `scheduled_trips_count` and `service_span_hours` provide vital exogenous signals of transit supply elasticity.
4. **Stratified Architecture**:
   - The existence of 25 years of daily ridership alongside 8 months of granular GTFS schedules enables a powerful two-tier modeling strategy:
     - Tier 1: Macro time-series forecasting across the full 25-year horizon.
     - Tier 2: High-resolution route optimization, clustering, and ranking utilizing GTFS supply features in the contemporary era.

---

## 4. Milestone 4 Deliverable Index

### Reports Authoring:
- [ridership_overview.md](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/reports/eda/ridership_overview.md)
- [temporal_analysis.md](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/reports/eda/temporal_analysis.md)
- [route_analysis.md](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/reports/eda/route_analysis.md)
- [service_analysis.md](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/reports/eda/service_analysis.md)
- [demand_service_analysis.md](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/reports/eda/demand_service_analysis.md)
- [feature_engineering_report.md](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/reports/eda/feature_engineering_report.md)
- [eda_summary.md](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/reports/eda/eda_summary.md)

### Parquet Feature Datasets:
- [ridership_features.parquet](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/data/processed/features/ridership_features.parquet) ($1,124,170$ rows)
- [route_features.parquet](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/data/processed/features/route_features.parquet) ($1,124,170$ rows)
- [service_features.parquet](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/data/processed/features/service_features.parquet) ($1,124,170$ rows)
- [demand_service_features.parquet](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/data/processed/features/demand_service_features.parquet) ($1,124,170$ rows)
- [model_ready_features.parquet](file:///d:/B.TECH_PROJECTS/AI_RouteRanker/data/processed/features/model_ready_features.parquet) ($1,124,170$ rows $\times$ 43 columns)
