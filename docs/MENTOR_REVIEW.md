# Mentor review: CTA RouteRanker prototype

## What the prototype does

- Forecasts daily route boardings and compares demand-only and schedule-aware models with seasonal baselines.
- Separates daily rolling one-step scores from a recursive fixed-origin forecast. They represent different information available to the forecaster.
- Reviews saved model errors by route and day type through the local dashboard and API.
- Accepts a route-level forecast CSV and proposes an integer trip allocation that minimizes the maximum predicted boardings per scheduled trip, preserves the networkwide number of trips, and respects a user-selected per-route change bound.

The trip allocation is a screening scenario. It does not estimate passenger loads or crowding and is not an operational service recommendation.

## Decisions to confirm before presenting route changes

1. **Planning objective:** Is balancing predicted boardings per scheduled trip useful for the intended decision? Should the goal instead account for peak loads, passenger wait time, cost, reliability, or access?
2. **Trip definition:** Does a route-level daily trip count represent the resource that can actually be moved? What vehicle cycle, block, deadhead, operator, garage, and time-of-day constraints must be enforced?
3. **Service guardrails:** What minimum service, maximum change, accessibility, coverage, equity, and transfer-connection constraints must hold for every route?
4. **Demand input:** Which forecast product should feed a scenario, for what date and horizon? Are boardings and scheduled trips measured over the same service period?
5. **Data timing:** When are CTA ridership observations published, and when is each schedule feed available to planners? Is CTA day type known at the time a forecast would be issued?
6. **Evaluation:** Are the route/date joins, seasonal baselines, metrics, and chronological splits appropriate? What later period can be reserved for a final evaluation after decisions are frozen?
7. **CTA feed use:** Which developer license terms, API keys, retention rules, and attribution requirements apply to any future real-time integration?

## Current limitations recorded in the project

- August 2026 has already been inspected and is development evidence, not a fresh final holdout.
- The fixed-origin seasonal baseline beat both ML models for the recursive August horizon. The service-aware model had the lowest error in the daily rolling development folds.
- GTFS archives were uploaded as extracted directories, so their original ZIP hashes could not be verified.
- Daily route boardings and scheduled trips do not show within-day peaks, vehicle capacity, passenger loads, or route overlap.
- API and dashboard scenario inputs are review tools; their output must be checked against operational data and planning constraints.
