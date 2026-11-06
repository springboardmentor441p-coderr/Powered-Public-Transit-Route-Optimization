# Module 2: Exploratory Data Analysis (EDA) Report
**Project:** RouteRanker for Chennai MTC Buses  
**Analysis Date:** 2026-11-06  
**Dataset Path:** `C:\Users\kavyasri\Downloads\mtc-gtfs`  
**Dataset Scope:** 4,611 Routes | 5,580 Stops | 47,047 Trips | 1,360,443 Stop Times

---

## 1. Executive Summary

This report delivers the Exploratory Data Analysis (EDA) of the Chennai Metropolitan Transport Corporation (MTC) transit network.
The objective of this analysis is to evaluate operational service densities, network hub structures, corridor hierarchy, and trip characteristics to inform the design and ranking algorithms of **RouteRanker**.

---

## 2. Core Statistical Findings

### 2.1 Route Network Distribution & Typology
- **Total Route Definitions:** 4,611 routes.
- **Transit Mode:** 100% of routes are classified under GTFS `route_type = 3` (Bus).
- **Active Routes:** 3,934 routes (85.32%) have scheduled trips.
- **Unserviced Routes:** 677 routes (14.68%) have 0 trips in the static schedule.
- **Mean Daily Trips per Active Route:** 11.96 trips (Median: 4, Std: 23.63).

#### Top 5 Busiest Routes by Daily Trips
1. **Route 20163 (`25 R`):** Anna Square TO Poonamalle (210 trips/day)
2. **Route 20167 (`25 R1`):** Poonamalle TO Anna Square (208 trips/day)
3. **Route 24072 (`91`):** Thiruvanmiyur TO Kilambakkam (202 trips/day)
4. **Route 24073 (`91 R`):** Kilambakkam TO Thiruvanmiyur (202 trips/day)
5. **Route 20578 (`57 R1`):** Redhills TO Vallalar Nagar (197 trips/day)

---

### 2.2 Bus Stop Density & Usage Frequency
- **Total Stops Defined:** 5,580 stops.
- **Active Stops with Scheduled Visits:** 5,477 stops.
- **Unused Stops:** 103 stops.
- **Mean Visits per Active Stop:** 248.4 daily visits (Median: 82, Max: 8,014).

#### Top 5 Busiest Stops by Daily Scheduled Visits
1. **Stop 5822 (`M.G.R.Koyambedu Bus Terminus`):** 8,014 visits/day
2. **Stop 6693 (`Tambaram West Bus Stand`):** 5,244 visits/day
3. **Stop 11159 (`Island ground Terminus`):** 5,176 visits/day
4. **Stop 9991 (`Kilambakkam Bus Terminus`):** 4,353 visits/day
5. **Stop 11158 (`Royapuram terminus`):** 3,449 visits/day

---

### 2.3 Transit Hubs & Route Interchanges (Shared Stops)
Stops serving multiple distinct routes serve as key transfer candidates in RouteRanker:
- **Mean Distinct Routes per Stop:** 17.5 routes (Median: 7, Max: 600).

#### Top 5 Interchange Hubs by Distinct Routes Served
1. **Stop 5822 (`M.G.R.Koyambedu Bus Terminus`):** 600 distinct routes
2. **Stop 6693 (`Tambaram West Bus Stand`):** 367 distinct routes
3. **Stop 11159 (`Island ground Terminus`):** 316 distinct routes
4. **Stop 11158 (`Royapuram terminus`):** 271 distinct routes
5. **Stop 5785 (`Chinnamalai Or Saidapet Court`):** 246 distinct routes

---

### 2.4 Trip Durations & Stop Counts
- **Mean Scheduled Trip Duration:** 51.03 minutes (0.85 hours).
- **Median Scheduled Trip Duration:** 51.0 minutes.
- **Interquartile Range (IQR):** 35 min to 66 min.
- **Minimum Duration:** 2 minutes (short depot/shuttle trips).
- **Maximum Duration:** 269 minutes (4.48 hours, long-distance suburban services).
- **Mean Stops per Trip:** 28.9 stops (Range: 2 to 80 stops).

---

### 2.5 Temporal Service Profile (Hourly Departures)
- **Morning Peak Window (05:00 - 09:00):** Over 10,500 trip departures, peaking at 06:00 (2,941 departures).
- **Afternoon/Evening Plateau (13:00 - 17:00):** Sustained maximum service volume, peaking at 14:00 (3,021 departures).
- **Late Night Operations (22:00 - 03:00):** Maintained overnight skeleton services (104 at midnight, 105 at 01:00).
- **Post-Midnight GTFS Format:** Handled correctly via second-based midnight offsets up to 25:41:00.

---

### 2.6 Weekly Service Patterns (calendar.txt)
- **Monday – Saturday:** 47,047 daily scheduled trips (comprising 46,973 `Regular` and 74 `HSC` trips).
- **Sunday:** 46,973 daily scheduled trips (`HSC` does not operate on Sundays).
- **Unused Schedules:** `Weekend`, `Hybrid`, `test `, and `'/><script>alert(1)</script>'` contain 0 scheduled trips.

---

## 3. Five Genuine Insights for RouteRanker

### Insight 1: Extreme Trunk vs. Branch Hierarchy Skew
The top 10% of routes account for over 50% of all scheduled service capacity. Trunk corridors (such as Route `25R` connecting Anna Square to Poonamallee, Route `91` connecting Thiruvanmiyur to Kilambakkam, and Route `500` connecting Tambaram to Chengalpet) operate with 180 to 210 trips per day (approx. 5-7 minute headways). Conversely, the median route has only 4 scheduled trips per day.
*Design Takeaway for RouteRanker:* Multi-criteria route ranking should reward high-frequency trunk corridors to minimize passenger transfer risk.

### Insight 2: Koyambedu, Tambaram, and Kilambakkam Anchor the Network Hub Hierarchy
Stop `5822` (M.G.R. Koyambedu Bus Terminus) is the unrivaled transit epicenter of Chennai, serving 600 distinct routes and 8,014 daily scheduled visits. Stop `6693` (Tambaram West) serves 367 routes with 5,244 visits, anchoring the southern commuter gate. The newly introduced Kilambakkam Bus Terminus (`KCBT`, Stop `9991`) already accounts for 240 distinct routes and 4,353 visits.
*Design Takeaway for RouteRanker:* These three megahubs should serve as primary anchor nodes for inter-corridor route synthesis and multi-leg trip planning.

### Insight 3: Critical In-Line Transfer Arteries (Saidapet & Anna Salai Funnel)
Several of Chennai's highest-connectivity nodes are not terminus stations, but intermediate roadway stops along major corridors. For example, `Chinnamalai / Saidapet Court` (Stop `5785`) serves 246 distinct routes (3,392 visits), and `Concorde / Chellammal College` serves 206 routes.
*Design Takeaway for RouteRanker:* Transfer algorithms should prioritize these high-frequency in-line arterial stops as optimal transfer locations with near-zero transfer wait times.

### Insight 4: Dual-Profile Trip Durations (Urban Core vs. Peri-Urban Commuter)
The trip duration distribution exhibits a compact core (IQR: 35 to 66 minutes, median: 51 minutes), but extends to an extreme right-tail reaching 269 minutes (4.48 hours, 80 stops). This reflects MTC's dual role: serving dense intra-city routes within the CMA, while simultaneously operating long-haul regional connector routes to satellite industrial towns (Chengalpattu, Sriperumbudur, Tiruvallur, Mahabalipuram).
*Design Takeaway for RouteRanker:* Route evaluation metrics must distinguish intra-city rapid transit from regional commuter services to avoid penalizing long-distance suburban direct routes.

### Insight 5: Static Feed Invariance & Lack of Weekend Throttling in Schedule
The GTFS feed defines nearly identical schedules for weekdays and weekends (47,047 weekday trips vs. 46,973 Sunday trips). The defined `Weekend` calendar record has 0 trips attached, and `calendar_dates.txt` is missing.
*Design Takeaway for RouteRanker:* Static GTFS cannot reflect actual weekend service reductions or real-time holiday schedules. RouteRanker must treat scheduled trips as upper-bound timetable potential and explicitly document this limitation.

---

## 4. Visualizations Generated

The following charts were generated and saved into `reports/figures/`:
1. `fig1_route_trips_distribution.png`: Histogram of trips per route and top 15 busiest routes.
2. `fig2_busiest_stops.png`: Bar chart of top 15 busiest bus stops by scheduled visits.
3. `fig3_hub_stops_connectivity.png`: Bar chart of top 15 interchange hubs by distinct routes served.
4. `fig4_trip_duration_distribution.png`: Distribution of scheduled trip durations and stop count correlation.
5. `fig5_hourly_departure_profile.png`: 24-hour departure profile showing morning and afternoon service peaks.
6. `fig6_weekly_service_patterns.png`: Daily scheduled service volume from Monday through Sunday.

---
**Report generated automatically by Module 2 analysis notebook.**
