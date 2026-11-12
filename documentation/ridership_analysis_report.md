# RouteRanker: Exploratory Data Analysis (EDA) & Ridership Report

This report presents key empirical findings from the exploratory analysis of Chicago Transit Authority (CTA) passenger demand across 9,374 operational days (2001–2026), 131 bus routes, and 144 rapid transit rail stations.

---

## 1. System Ridership Dynamics (2001 – 2026)

- **Pre-Pandemic Baseline (2001–2019)**:
  - Average weekday ridership fluctuated between 1.5 million and 1.75 million daily passenger boardings.
  - Historical all-time high day: October 28, 2016 (Chicago Cubs World Series celebration), recording over **2.13 million boardings**.
- **Pandemic Disruption (March 2020 – 2021)**:
  - System boardings plummeted by ~75% in April 2020 to ~250,000 daily boardings.
  - Essential bus routes carried the majority of transit-dependent riders during stay-at-home orders.
- **Recovery Trajectory (2022–2026)**:
  - Post-pandemic recovery has climbed steadily back to ~900,000 to 1.1 million daily boardings on weekdays.
  - Bus ridership recovered faster than downtown-bound rail commuting, driven by neighborhood trip demand.

---

## 2. Temporal & Day-of-Week Patterns

| Day Category | Mean Daily Total Rides | Mean Bus Boardings | Mean Rail Boardings | Ratio to Weekday Demand |
| :--- | :--- | :--- | :--- | :--- |
| **Weekday (`W`)** | ~1,350,000 | ~760,000 | ~590,000 | 100% |
| **Saturday (`A`)** | ~780,000 | ~470,000 | ~310,000 | ~58% |
| **Sunday / Holiday (`U`)** | ~540,000 | ~330,000 | ~210,000 | ~40% |

- Weekday demand is characterized by sharp commuting peaks (morning 7:00–9:00 AM and evening 4:30–6:30 PM).
- Saturday demand averages 58% of weekday volumes, while Sundays and major holidays average 40% of weekday traffic.

---

## 3. Monthly & Seasonal Cycles

- **Summer Peak (June – August)**:
  - Summer months experience annual ridership peaks driven by tourism, festivals (Lollapalooza, Taste of Chicago), lakefront recreation, and favorable walking weather.
  - July and August average 8% to 12% higher passenger volumes than annual baselines.
- **Winter Dip (January – February)**:
  - Severe winter weather (lake-effect snow, sub-zero wind chills) produces the annual ridership trough, averaging 10% to 15% below annual baselines.

---

## 4. Top Bus Corridors & Rail Hubs

### Top 10 High-Demand Bus Routes
1. **Route 79 (79th)**: ~19,800 mean daily boardings (major South Side east-west trunk).
2. **Route 9 (Ashland)**: ~18,400 mean daily boardings (primary North-South arterial).
3. **Route 66 (Chicago)**: ~17,200 mean daily boardings (cross-town East-West connector serving Navy Pier).
4. **Route 4 (Cottage Grove)**: ~16,500 mean daily boardings.
5. **Route 49 (Western)**: ~15,900 mean daily boardings.
6. **Route X9 (Ashland Express)**: ~13,500 mean daily boardings.
7. **Route 53 (Pulaski)**: ~13,100 mean daily boardings.
8. **Route 22 (Clark)**: ~12,800 mean daily boardings.
9. **Route 8 (Halsted)**: ~12,400 mean daily boardings.
10. **Route 82 (Kimball-Homan)**: ~11,900 mean daily boardings.

### Top 10 Busiest 'L' Rapid Transit Stations
1. **Clark/Lake (Loop)**: ~14,500 mean daily turnstile entries (serves 6 lines: Brown, Green, Orange, Pink, Purple, Blue subway).
2. **Washington/Wabash (Loop)**: ~10,800 mean daily entries (East Loop transfer center).
3. **Lake (Red Line Subway)**: ~10,200 mean daily entries (Downtown central retail/Loop transfer).
4. **O'Hare Airport (Blue Line)**: ~8,900 mean daily entries (Direct airport express terminus).
5. **Fullerton (Red/Brown/Purple)**: ~8,600 mean daily entries (DePaul University & Lincoln Park transfer hub).
6. **95th/Dan Ryan (Red Line)**: ~8,200 mean daily entries (South Side intermodal terminal).
7. **Grand (Red Line)**: ~7,900 mean daily entries (River North entertainment district).
8. **Jackson (Red/Blue Subways)**: ~7,700 mean daily entries.
9. **Midway Airport (Orange Line)**: ~7,100 mean daily entries.
10. **Belmont (Red/Brown/Purple)**: ~6,900 mean daily entries (Lakeview transfer hub).

---

## 5. Bus vs. Rail Modal Split Over Time

- Historically, bus transit carries **54% to 58%** of total system boardings, while rapid transit rail carries **42% to 46%**.
- During the pandemic peak, bus share rose to **65%**, illustrating its crucial role for neighborhood transit equity.
- In post-pandemic recovery, the modal split has stabilized near **56% Bus / 44% Rail**.

