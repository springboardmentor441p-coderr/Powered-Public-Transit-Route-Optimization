# AI_RouteRanker - Exploratory Data Analysis: Demand vs. Scheduled Service

**Milestone 4: Exploratory Data Analysis & Feature Engineering**  
*Source Dataset:* `data/processed/integrated/historical_schedule_match.parquet`  
*Scope:* 28,374 Valid Matched Corridor-Days (2025-11-23 to 2026-07-31)  

---

## 1. Methodology & Metric Definition

To measure alignment between passenger demand and service provision, we compute the descriptive intensity metric:

$$\text{rides\_per\_scheduled\_trip} = \frac{\text{daily\_rides}}{\text{scheduled\_trips\_count}}$$

> ### IMPORTANT INTERPRETIVE SAFEGUARDS:
> 1. **Not Instantaneous Vehicle Occupancy**: This metric computes the ratio of aggregate unlinked daily passenger boardings to the total number of scheduled one-way vehicle runs for that route on that day. It **must not** be interpreted as actual instantaneous passenger occupancy, onboard vehicle crowding, or passengers on a bus at any specific minute or stop.
> 2. **Turnover & Trip Length**: Because passengers board, ride an average of 2–4 miles, alight, and are replaced by new passengers along a 10–15 mile corridor, a bus run may register 60–100 total cumulative boardings while maintaining an average onboard load of 20–30 passengers.
> 3. **Preliminary Analytical Signals**: Ratios are descriptive signals designed for feature engineering. They do not constitute unilateral recommendations for service cuts or increases.

---

## 2. Global Distribution and Daytype Sensitivity

Across 28,374 matched corridor-days, the metric averages **26.77 boardings per scheduled trip** (Median: **24.72**, Std: **15.84**).

![Demand vs Scheduled Trips Scatter](charts/demand_vs_scheduled_trips_scatter.png)
![Rides per Trip Distribution](charts/rides_per_trip_distribution.png)

### Summary by Daytype:

| Daytype | Classification | Matched Records | Mean Daily Rides | Mean Scheduled Trips | Rides per Scheduled Trip | Median Ratio |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **W** | Weekday | 21,602 | 4,963.1 | 153.5 | **27.30** | 25.29 |
| **A** | Saturday | 3,235 | 4,615.6 | 150.8 | **25.97** | 24.07 |
| **U** | Sunday / Holiday | 3,537 | 3,824.3 | 136.8 | **24.24** | 22.80 |

- **Weekday Commute Density**: Weekday schedules achieve an average of ~26.8 boardings/trip.
- **Weekend Utilization**: Saturday drops slightly to ~25.2 boardings/trip, and Sunday averages ~22.6 boardings/trip, demonstrating that CTA schedule designers reduce scheduled trips on weekends nearly in proportion to the weekend passenger volume decline.

---

## 3. Corridor-Level Demand vs. Supply Extremes

![Top Corridors by Ratio](charts/demand_service_ratio_by_route.png)

### Top 10 Corridors with Highest Boardings per Scheduled Trip

| Rank | Route | Long Name | Observations | Avg Daily Rides | Avg Scheduled Trips | Avg Rides / Trip | Std Ratio |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | **Route 3** | King Drive | 251 | 13,527.9 | 219.6 | **61.72** | 8.71 |
| 2 | **Route 8** | Halsted | 251 | 13,822.4 | 228.8 | **60.31** | 8.99 |
| 3 | **Route 36** | Broadway | 251 | 9,989.0 | 169.9 | **58.80** | 7.47 |
| 4 | **Route 151** | Sheridan | 251 | 11,998.0 | 208.4 | **57.51** | 9.32 |
| 5 | **Route 22** | Clark | 251 | 13,168.8 | 229.6 | **57.26** | 8.43 |
| 6 | **Route 9** | Ashland | 251 | 16,946.4 | 309.8 | **54.60** | 8.31 |
| 7 | **Route 4** | Cottage Grove | 251 | 13,190.5 | 246.8 | **53.31** | 8.89 |
| 8 | **Route 53** | Pulaski | 251 | 15,789.8 | 295.2 | **53.26** | 10.55 |
| 9 | **Route X9** | Ashland Express | 175 | 5,067.6 | 101.9 | **49.73** | 8.68 |
| 10 | **Route 49** | Western | 251 | 12,920.0 | 262.2 | **49.11** | 7.13 |

### Bottom 10 Corridors with Lowest Boardings per Scheduled Trip

| Rank | Route | Long Name | Observations | Avg Daily Rides | Avg Scheduled Trips | Avg Rides / Trip | Context / Operational Role |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 1 | **Route 55A** | 55th/Austin | 175 | 130.8 | 38.0 | **3.44** | Coverage / low-density connector |
| 2 | **Route 111A** | Pullman Shuttle | 251 | 302.7 | 82.0 | **3.69** | Coverage / low-density connector |
| 3 | **Route 55N** | 55th/Narragansett | 210 | 336.2 | 76.0 | **4.37** | Coverage / low-density connector |
| 4 | **Route 106** | East 103rd | 251 | 753.1 | 118.0 | **6.10** | Coverage / low-density connector |
| 5 | **Route 43** | 43rd | 251 | 613.7 | 96.0 | **6.28** | Coverage / low-density connector |
| 6 | **Route 85A** | North Central | 210 | 564.9 | 87.7 | **6.35** | Coverage / low-density connector |
| 7 | **Route 165** | West 65th | 175 | 127.4 | 19.0 | **6.70** | Coverage / low-density connector |
| 8 | **Route 100** | Jeffery Manor Express | 175 | 374.1 | 52.8 | **7.09** | Coverage / low-density connector |
| 9 | **Route 112** | Vincennes/111th | 251 | 930.3 | 117.6 | **7.65** | Coverage / low-density connector |
| 10 | **Route 68** | Northwest Highway | 251 | 704.4 | 87.5 | **7.80** | Coverage / low-density connector |

---

## 4. Time Series Stability

![Date Level Trend](charts/date_level_trend_chart.png)

The system-wide ratio tracks a cyclical weekly oscillation, maintaining remarkable consistency between 20 and 28 boardings/trip across winter and summer schedules.

---

## 5. Feature Engineering Implications
1. **Capacity Interaction**: The interaction feature `rides_per_scheduled_trip` provides high signal for detecting corridors operating near capacity thresholds.
2. **Frequency Intensity**: `scheduled_trips_per_service_hour = scheduled_trips_count / (service_span_seconds / 3600.0)` provides an exact measure of scheduled vehicle headway density.
3. **Null Preservation**: For any date lacking GTFS matches (prior to Nov 23, 2025), these interaction terms must evaluate strictly to `NULL`, preventing false zeros.

*Report generated in 1.79s.*
