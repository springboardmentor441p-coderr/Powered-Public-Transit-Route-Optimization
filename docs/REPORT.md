# RouteRanker – Technical Report

## 1. Problem and outcomes
Identify inefficient bus routes in Indian cities (over-crowded, under-used, overlapping), recommend corrective actions and let
planners explore them. Delivered: pipeline (Modules 1-6), Streamlit app (Module 7), tests, this report.

## 2. Data
23 cities (Delhi, Mumbai, Bengaluru, Hyderabad, Chennai, Kolkata, Pune, Ahmedabad, Jaipur, Lucknow, Surat, Kanpur, Nagpur, Indore, Bhopal,
Visakhapatnam, Patna, Vadodara, Coimbatore, Kochi, Chandigarh, Bhubaneswar, Thiruvananthapuram). Files: routes, trips, stop_times, stops, calendar.
**Honest note:** the Lepton feed is licensed, so the repository ships a generator producing GTFS-format feeds with realistic structure
(hub-and-spoke corridors, stop overlap, bi-modal demand, weekday/weekend service) and a hidden ridership file with route-level noise.
The code reads real GTFS unchanged. Final figures below are on this synthetic data: 512 routes, 3,609 stops.

## 3. Method
**Cleaning** – drops out-of-India/missing coordinates and duplicate ids, interpolates missing times, repairs non-monotonic times, removes orphan trips/routes (counts reported per city).

**Features** – trip level: duration, distance (haversine), start hour, weekday/weekend. Route level: length, stops, spacing, trips/day, peak/off-peak headway, headway CV, speed,
service span, weekend ratio, stop sharing, hub stops, maximum pairwise overlap. Stop level: attraction (distance to core), routes served, departures, estimated boardings.
Demand: observed `ridership.csv` if given, else proxy. Hourly table gives passengers per route-hour, trips, passengers/trip and **load factor** =
boardings × 0.45 (avg ride share) / (trips × 60 capacity). Peak LF = mean of top-3 hours; average LF = daily.

**Labels** – overcrowded if peak LF ≥ 1.2; underutilized if average LF < 0.30; else balanced (thresholds in `config.py`).

**Preprocessing** – log transform of skewed counts, standard scaling, one-hot city tier, label encoding of route/city IDs (bookkeeping only, never predictors),
stratified 80/20 split, and city-grouped splits.

**Models**
* Clustering on usage profiles: KMeans (k by silhouette, 3-8) and DBSCAN (eps = 90th pct of 5-NN distance); PCA for display; DBSCAN inference by nearest core sample.
* Classification of route class from **structural / supply-demand features only** (no observed load) → usable on cities without ridership. Random Forest vs XGBoost with class-balanced weights.
  Evaluation: city-grouped 5-fold CV (primary), stratified validation, and a hold-out of 3 unseen cities (Kochi, Indore, Nagpur).

**Optimiser** – per route-hour required trips = ⌈boardings × 0.45 / (60 × target LF)⌉. Overcrowded: raise to required (≤ 20 trips/h). Underutilized: lower to required but never below
2 trips/h. Merge: highly overlapping pairs (≥ 50 % stop overlap, Jaccard ≥ 0.3) of low-demand routes that one route can absorb with no extra trips. Split/short-turn flag: overcrowded routes ≥ 20 km with peak LF ≥ 1.3.
Impact is simulated by holding demand constant and re-computing load, waiting time and fleet effort.

## 4. Results (synthetic data)
| Model | CV acc. | CV macro-F1 | Val macro-F1 | Unseen-city macro-F1 |
|---|---|---|---|---|
| **Random Forest (selected)** | 0.678 | 0.676 | 0.684 | 0.654 |
| XGBoost | 0.654 | 0.649 | 0.642 | 0.636 |

Chance is 0.33. Errors are mostly between adjacent classes; direct over↔under confusion is 23 of 512 routes. Per-class F1: overcrowded 0.75, balanced 0.65, underutilized 0.62.
The ceiling is limited by route-level demand noise that structure cannot explain (by construction of the data). Top features: proxy peak LF, proxy pax/trip, proxy LF, headway CV, peak headway.

Clustering: k=3, silhouette 0.18 (weak, usage profiles form a continuum rather than tight groups); DBSCAN finds one dense cluster plus 3.5 % outliers, which are useful as "unusual routes" to review.

| Metric (weekday, 23 cities) | Current | Optimised |
|---|---|---|
| Overcrowded routes | 172 | 44 |
| Under-used routes | 133 | 49 |
| Mean peak load factor | 1.07 | 0.77 |
| Passengers in over-crowded hours | 8.6 % | 2.9 % |
| Near-empty trips | 46.3 % | 25.2 % |
| Avg passenger wait (min) | 5.49 | 5.20 |
| Trips / day | 61,643 | 51,297 (-16.8 %) |
| Bus-km / day | 994,716 | 880,348 (-11.5 %) |
Actions: 171 increase, 134 reduce, 4 merges (8 routes), 199 no change.

## 4b. Learning from the past to predict the future (forecasting)
Past data: 45 months (Jan 2023 – Sep 2026) of average-weekday boardings per route (trend, seasonality, AR noise, occasional level shifts).
Model: one global XGBoost regressor over all 512 routes, direct multi-horizon (h = 1..12). Target = log(y[t+h]) − mean(log y[t−2..t]). Features: momentum,
year-on-year growth, last-year seasonal shape, city-pooled growth/seasonality, target calendar month, static route features. 80 % interval from backtest residuals.
**Time-based backtest** (train on first 33 months only, predict the following 12 unseen months):

| Method | WAPE | MAPE |
|---|---|---|
| **XGBoost forecaster** | **4.0 %** | see metrics.json |
| Seasonal-naive + drift | 4.8 % | |
| Last-3-month average | 6.3 % | |
| Same month last year | 6.7 % | |

The final model is refit on all history and forecasts Oct 2026 – Sep 2027. Forecast demand re-scales each route's hourly boardings; classes are re-derived from
the future load factor and the optimiser re-plans service (planning horizon: today / 12-month average / busiest month). Unforeseeable events (new metro line, strikes) are not predictable; the intervals reflect only typical error.

## 4c. Web application architecture
React 18 + Vite frontend (Recharts charts, Leaflet/OpenStreetMap maps) talks to a FastAPI service wrapping the Python pipeline. Datasets live in memory
(the pre-computed 23-city demo plus up to 5 uploaded/generated sessions); optimisation results are cached per (dataset, scenario, settings). One container serves the built site and the API.
Automated checks: Python tests for pipeline, forecasting and API, and a frontend test that renders all tabs against the live API.

## 5. Limitations and deployment advice
* Results are on synthetic data; validate on real feeds and real ridership (APC/ticketing) before acting.
* Without ridership the labels derive from the proxy, so the classifier then mostly learns the proxy; supply boardings whenever possible.
* The simulation holds demand fixed (no induced demand / mode shift), uses one average capacity and ride fraction, ignores driver/depot constraints and weekend service.
* Recommendations are decision support for planners, not automatic schedules. Pilot on a few routes, monitor load factors, then retrain monthly.
* Possible extensions: segment-level loads, shapes.txt alignments, transfer-aware merging, cost model, time-series demand forecasting.

## 6. Reproduce
`pip install -r requirements.txt && python train.py && streamlit run app.py && pytest tests -q`
