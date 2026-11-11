# Analysis, forecasting and route-grouping requirements

This matrix defines the analytical scope, implementation evidence and acceptance criteria.
It distinguishes completed capabilities from outcomes that require additional observations
or later development.

| Requirement | Implementation/evidence | Status and qualification |
|---|---|---|
| Collect GTFS and load five essential tables | Collection scripts; notebook 01 | Complete for the selected New York feeds; historical comparisons cover Manhattan |
| Inspect types, missing values, duplicates, memory, keys and references | Notebook 01 and batch inspection reports for 11 feeds | Complete for project-required fields; not a full GTFS specification certification |
| Source register and original-file fingerprints | Receipts; notebook 02; `reports/eda/source_register.csv` | Complete; mutable URLs do not guarantee future identical downloads |
| Clean missing/conflicting/erroneous entries | Notebook 02 decisions, quarantine outputs, validity assertions | Complete for defined view; unverified source errors flagged, not guessed away |
| Hour, weekday/weekend and date features | Notebook 03 | Complete; weekdays are not inferred holiday labels |
| Measure route/hour demand | Publisher route-hour boarding estimates, July–September 2026 | Published aggregates available; stop/direction passenger allocations unavailable |
| Basic route profiles: length, duration, frequency, stops | Snapshot-specific trips and daily pattern profiles | Complete; distance is shape-polyline estimate, frequency is scheduled |
| Historical demand/service alignment | Latest whole archive, calendar exceptions, exact route-ID/date joins, clock-date integration | Complete for the explicitly eligible subset; archive gaps, partial calendars and DST context withheld |
| Identify high-demand periods and route usage patterns | Notebook 04 temporal curves and heatmaps | Complete for observed windows; traffic/delay measurements unavailable |
| Route density and geographic visualizations | Notebook 04 sampled geometry grid, stop density and route concentration | Complete descriptive mapping; no population/accessibility inference |
| Detect overlaps | Stop-set Jaccard, smaller-route overlap, exclusive stops and pair map | Complete as corridor-review evidence; no merge recommendation |
| Review relative service use | Date-counted relative boarding/service review list and sensitivity checks | Review priorities identified; verified underutilization requires costs, capacity and service purpose |
| Forecast daily demand against seasonal baselines | Notebook 05: seasonal baselines, Poisson gradient boosting, weekly chronological evaluation | Retrospective experiment; publication delay is assumed and point-in-time vintages are unavailable |
| Validate uncertainty and later outcomes | Notebook 06: maturity policy, separate interval calibration, later-acquired outcome scoring | Implemented; undercoverage and later-period model weakness are reported |
| Evaluate forecasts issued before target dates | Immutable model and baseline registrations for 9–15 November 2026 | Registered; mature prospective outcomes pending |
| Investigate model and interval weaknesses | Notebook 07: paired route/weekday/week diagnostics and a 2025 candidate replay | Retrospective development; existing registrations preserved |
| Consolidate and close forecasting research | [Milestone decision](FORECAST_MILESTONE.md), acceptance policy and isolated replay | Complete for review; operational use not accepted; prospective evidence pending |
| Extend historical assessment and provide a forecast component | [October validation](OCTOBER_VALIDATION.md), notebook 08 and guarded preview command | Sufficient for labelled experimental comparison; operational acceptance unchanged |
| Group routes by interpretable demand/service characteristics | Notebook 09; [route grouping](ROUTE_GROUPING.md); KMeans, density and stability diagnostics | Exploratory descriptive grouping; representation and temporal sensitivity retained |
| Produce explainable route-review evidence | Notebook 10; [review workflow](ROUTE_REVIEW.md); reasons, denominators, support, dates and sensitivity | Complete for the frozen historical window; no performance score or automated service recommendation |
| Compare frequency-change scenarios | Notebook 11; [scenario arithmetic](SERVICE_SCENARIOS.md); paired baseline, resource limits and illustrative transfers | Complete as assumed mean-daily arithmetic; timetable, fleet and passenger outcomes unassessed |
| Classify routes as balanced/overcrowded | Independent-label intake, chronological Random Forest/baseline evaluation and fitted pipeline persistence | Software ready; observed labels unavailable, so no empirical classifier result claimed |
| Streamlit interface | [Six-page planning workspace](DASHBOARD.md), route/date filters, verified forecasts, review evidence, interactive scenarios and downloads | Complete local analytical prototype; operational deployment and shared persistence remain separate |
| Optimization benefit | No measured intervention outcome | Requires scenario assumptions and operational evaluation |
| Upload GTFS through the dashboard | Isolated bounded ZIP importer, calendar/frequency handling and exports | Implemented and checked against a real archived feed |
| Compare routes and save proposals | Paired comparison, local append-only assumptions/evidence bundles | Implemented; shared database deployment remains separate |
| Allocate added service under a budget | Convex continuous allocation, per-route bounds and equal-spend comparator | Implemented explicit proxy optimization; not a timetable or measured welfare improvement |
| Final report, architecture and presentation | Technical report, architecture, eight-slide deck and walkthrough | Delivered; see [delivery status](DELIVERY_STATUS.md) for empirical and deployment gaps |

The completed scope covers reproducible collection, inspection, cleaning, feature engineering
and EDA for the selected data, followed by retrospective forecasting, exploratory grouping,
an explainable historical review workflow, assumption-based frequency scenarios and a functional
Streamlit planning workspace.
Unresolved source-quality and publication-vintage issues remain explicitly flagged.

## Acceptance checks

- Fresh-kernel execution succeeds in order; every code cell has visible saved output.
- Raw fingerprints remain unchanged; derived products have hashes, schemas and explicit grains.
- Duplicate keys/conflicts cannot silently inflate observations.
- Calendar additions/removals, no-fallback archive selection, midnight/DST handling and duration
  conservation have tests.
- Exact-date lags preserve missing history and actual zero values.
- Demand/service comparisons show dates, population, denominator and exclusion policy.
- Capabilities without sufficient evidence are marked unavailable or deferred.
