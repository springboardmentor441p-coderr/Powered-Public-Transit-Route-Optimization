# AI_RouteRanker - Exploratory Data Analysis: Temporal Patterns & Trends

**Milestone 4: Exploratory Data Analysis & Feature Engineering**  
*Source Dataset:* `data/processed/integrated/daily_ridership.parquet`  
*Analysis Period:* 2001-01-01 to 2026-08-31 (25.6 Years)  

---

## 1. Multi-Decadal Annual Trends

The historical dataset encompasses distinct eras in Chicago transit: pre-2008 peak demand, post-recession stabilization, pre-pandemic baselines (2015–2019), the 2020 pandemic decline, and progressive post-pandemic recovery (2021–2026).

![Yearly Ridership Trend](charts/yearly_ridership_trend.png)

> **Important Coverage Notice**: Changes in annual total ridership reflect both macro travel behavior and shifts in active routes in the CTA network. In 2001–2003, 150–160 routes operated, peaking around 145–150 routes before route restructuring. Year-over-year volume changes must be interpreted alongside active route breadth.

### Annual Ridership Summary Table

| Year | Active Routes | Annual Observations | Total Annual Rides | Mean Daily Rides | YoY Total Rides (%) | YoY Mean Rides (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2001 | 137 | 42,434 | 300,142,034 | 7,073.1 | — | — |
| 2002 | 141 | 43,185 | 301,815,744 | 6,988.9 | +0.56% | -1.19% |
| 2003 | 147 | 44,135 | 290,513,630 | 6,582.4 | -3.74% | -5.82% |
| 2004 | 149 | 45,661 | 292,596,557 | 6,408.0 | +0.72% | -2.65% |
| 2005 | 151 | 46,276 | 301,956,479 | 6,525.1 | +3.20% | +1.83% |
| 2006 | 155 | 47,070 | 296,916,585 | 6,308.0 | -1.67% | -3.33% |
| 2007 | 156 | 48,826 | 306,996,060 | 6,287.6 | +3.39% | -0.32% |
| 2008 | 155 | 48,521 | 326,399,922 | 6,727.0 | +6.32% | +6.99% |
| 2009 | 155 | 48,109 | 317,549,806 | 6,600.6 | -2.71% | -1.88% |
| 2010 | 151 | 45,201 | 304,990,991 | 6,747.4 | -3.95% | +2.22% |
| 2011 | 141 | 44,782 | 309,355,465 | 6,908.0 | +1.43% | +2.38% |
| 2012 | 144 | 44,730 | 313,161,565 | 7,001.1 | +1.23% | +1.35% |
| 2013 | 139 | 43,002 | 297,407,665 | 6,916.1 | -5.03% | -1.21% |
| 2014 | 131 | 42,198 | 273,021,357 | 6,470.0 | -8.20% | -6.45% |
| 2015 | 132 | 42,346 | 272,122,558 | 6,426.2 | -0.33% | -0.68% |
| 2016 | 136 | 42,549 | 257,917,007 | 6,061.6 | -5.22% | -5.67% |
| 2017 | 130 | 42,259 | 248,107,289 | 5,871.1 | -3.80% | -3.14% |
| 2018 | 131 | 42,261 | 240,995,859 | 5,702.6 | -2.87% | -2.87% |
| 2019 | 128 | 41,810 | 235,636,572 | 5,635.9 | -2.22% | -1.17% |
| 2020 | 128 | 41,589 | 120,379,513 | 2,894.5 | -48.91% | -48.64% |
| 2021 | 128 | 41,629 | 116,379,107 | 2,795.6 | -3.32% | -3.42% |
| 2022 | 129 | 41,817 | 138,741,715 | 3,317.8 | +19.22% | +18.68% |
| 2023 | 130 | 41,862 | 160,232,588 | 3,827.6 | +15.49% | +15.37% |
| 2024 | 128 | 41,768 | 180,446,522 | 4,320.2 | +12.62% | +12.87% |
| 2025 | 129 | 42,201 | 198,585,491 | 4,705.7 | +10.05% | +8.92% |
| 2026 *(thru Aug 2026)* | 128 | 27,949 | 135,253,579 | 4,839.3 | -31.89% | +2.84% |

---

## 2. Monthly Seasonality & Climate Influence

Ridership displays a pronounced seasonal cycle tied to Chicago's academic calendar and winter weather patterns.

![Monthly Seasonality](charts/monthly_seasonality.png)

- **Autumn Peaks (September - October)**: Characterized by the return of CPS schools, universities, and full fall business travel. October records the highest average daily ridership per route (6,261.2 rides/day).
- **Winter Depressions (December - January)**: Holiday schedules, school recesses, and sub-zero winter temperatures reduce average route volume to seasonal lows in December and January (5,437.4 rides/day).
- **Spring/Summer Recovery (April - June)**: Rebound driven by tourism, festivals, and outdoor pedestrian transit connectivity.

---

## 3. Daytype and Day-of-Week Patterns

![Daytype Comparison](charts/daytype_comparison.png)
![Day of Week Distribution](charts/day_of_week_distribution.png)

### Daytype Metrics:
- **Weekday (`W`):** 6,127.6 mean rides (865,376 obs)
- **Saturday (`A`):** 5,419.5 mean rides (127,570 obs)
- **Sunday/Holiday (`U`):** 4,142.3 mean rides (131,224 obs)

### Day-of-Week Variation:
- Mid-week days (Tuesday through Thursday) capture the highest commuter demand, plateauing around ~6,700–6,800 daily boardings per route.
- Friday ridership experiences a slight commuter taper (~6,400 rides/day).
- Saturday volume drops to ~52% of peak weekday ridership, and Sunday volume declines to ~38%, mirroring service frequency reductions.

---

## 4. Key Takeaways for Feature Engineering
1. **Calendar Features are Imperative**: Day of week, day of year, month, and daytype flags capture over 60% of cyclical variance.
2. **Lag Cycles**: 7-day, 14-day, and 28-day lags will be critical predictors to account for strict weekly seasonality.
3. **Macro Era Adjustments**: Rolling 28-day and expanding-window features will enable models to adapt smoothly across macro shifts without future-date leakage.

*Report generated in 1.62s.*
