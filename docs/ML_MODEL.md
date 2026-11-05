# ML model: methodology and measured results

## Task
Predict the number of scheduled trips of a route in a given hour of a typical weekday (`trips`, count) from route and network features, **without** the route's own timetable as input.
Target is expressed relative to the city mean (`trips / city_scale`) so operator fleet size is not something to guess; predictions are scaled back.

## Data (real)
Pune PMPML (315 routes), Chennai MTC (3,918 bus routes after dropping metro/rail and invalid rows), Bengaluru BMTC (4,408 routes; unofficial, partial network). 77,247 route-hours.
Validation + cleaning ledger per feed: `data/corpus/*.meta.json`. Sources/licences: `real_data/SOURCES.md`.
Chennai's feed contains service ids with HTML/script text; validation flags it and the UI shows it only as escaped text.
Typical weekday = a Tuesday inside the validity window of the services actually used by the bus trips (calendar + calendar_dates honoured).

## Features (no target leakage)
Hour (cyclic), position in service day, peak flags; route length, stops, stop spacing, trip duration, speed, operating span; connectivity (routes per stop), shared-stop fraction,
hub fraction, maximum overlap; distance to city core (normalised); service of *other* routes at its stops. Removed on purpose: the route's own trips/headways and city-level descriptors
(with 3 cities they identify the city: measured to inflate within-corpus scores and hurt transfer).

## Models and baselines
Mean, hour-of-day mean (baselines), Poisson linear model, Random Forest, Gradient boosting (Poisson loss). Chosen by route-grouped CV MAE: gradient boosting.

## Evaluation (all produced by executed code; see notebook and `model_card.json`)
| Protocol | Result |
|---|---|
| Route-grouped 5-fold CV, pooled | MAE 1.042 (GBM) vs 1.474 (hour mean), 1.353 (Poisson linear), 1.075 (RF), 1.487 (mean) |
| **Within each city, held-out routes** | Bengaluru 1.064 vs 1.591 (R² 0.41); Chennai 0.843 vs 1.248 (R² 0.43); Pune 1.576 vs 2.151 (R² 0.36) |
| **Leave-one-city-out (unseen city)** | Bengaluru 1.443 vs 1.599; Chennai 1.088 vs 1.264; **Pune 2.963 vs 2.393 (worse)** |
| Learning curve (fixed held-out routes) | MAE 1.277 (138 training routes, R² -0.08) -> 1.021 (6,913 routes, R² 0.35); baseline 1.448 |
Most important features (permutation): operating span, other service at its stops, speed, distance to core, trip duration.

## Peer comparison
Out-of-fold predictions per city; a route is flagged only if its actual/expected daily trips ratio lies in the extreme 5% tail **and** differs by more than 2x. Result on the corpus:
433 relatively under-served, 433 relatively over-served, 7,775 in line (8,641 routes). Example: Pune route 337 runs 9 trips/day where comparable routes get about 50.
Reliability gate: if the model's skill on the feed is below 10%, flags are replaced by "unreliable". Feeds with fewer than 200 routes use the pooled model and are labelled weak.

## Learning from new data
`python -m src.learn add --gtfs new.zip --name City` -> validate -> clean -> add to corpus -> retrain -> champion/challenger: promote unless leave-one-city-out error on previously evaluated cities worsens by more than 5%. Every attempt is logged in `models/registry.json`.
