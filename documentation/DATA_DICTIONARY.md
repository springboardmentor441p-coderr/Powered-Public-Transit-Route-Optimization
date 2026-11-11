# Analysis tables

Generated CSVs live under `data/processed/new_york/`; `reports/eda/feature_schema.csv` records
every feature column's type and missing count. Each manifest records product row counts,
columns and SHA-256 hashes. These files are local and reproducible from the notebooks.

| Table | Unique grain | Main purpose |
|---|---|---|
| `daily_clean` | bus_route, payment_date | Original daily published counts plus quality flags and conservative analysis values |
| `hourly_clean` | bus_route, local_hour | Original route-hour estimates, local date and hour review flag |
| `route_crosswalk` | snapshot_id, route_id | Exact publisher code mapping and SBS display-name evidence |
| `route_date_coverage` | bus_route | First/last date, observed/zero/review days, absent dates inside observed span |
| `network_date_quality` / `network_hour_quality` | date / local hour | Past-only quality-screen comparisons |
| `daily_demand_features` | bus_route, payment_date | Calendar and exact-date retrospective lag candidates |
| `trip_template_features` | snapshot_id, trip_id | Duration, shape length, stop count and ordered pattern |
| `shape_features` | snapshot_id, shape_id | Polyline length, point count and geometry review |
| `calendar_expansion` | date | Selected whole feed, active services/trips, unavailable reasons |
| `pattern_service_date_features` | service_date, bus_route, direction_id, origin_stop_id, pattern_id | Comparable departure series and shape/duration summaries |
| `schedule_clock_daily` | bus_route, payment_date | Calendar-complete reviewed scheduled departures and service hours |
| `schedule_clock_hourly` | bus_route, local_hour | Hourly scheduled supply, partial diagnostic values, sources and eligibility |
| `matched_daily_features` | bus_route, payment_date | Demand-only history left-joined with eligible historical supply |
| `matched_hourly_features` | bus_route, local_hour | Actual hourly estimates left-joined to clock-hour scheduled supply |
| `route_day_type_profiles` | bus_route, day_type | Ratios of sums, sample dates and descriptive variation |
| `route_structure` | snapshot_id, bus_route | Template-weighted lengths/durations and shared/exclusive stop coverage |
| `route_overlap` | snapshot_id, route_a, route_b | Every unordered pair, including zero overlap |
| `map_stops`, `map_shapes`, `map_route_shapes` | stop_id / shape_id+sequence / route+shape | September geometry and route associations |

## Important columns

| Column | Meaning and missing-value policy |
|---|---|
| `published_boardings`, `ridership` | Publisher boarding estimates; original zero values preserved |
| `published_transfers`, `transfers` | Already included boarding subset, not additional passengers |
| `analysis_boardings` | Source value except missing where the conservative quality screen requires review |
| `payment_date`, `local_hour` | Publisher local payment clock date/hour, America/New_York; naive storage matches source |
| `service_date` | GTFS calendar date, possibly different from an overnight trip's clock date |
| `scheduled_departures` | Calendar-selected trip starts on the stated date/hour, not actual operated trips |
| `scheduled_service_hours` | Sum of scheduled first-departure-to-final-arrival intervals overlapping the clock period |
| `partial_scheduled_*` | Diagnostic contribution sums, not validated service denominators |
| `schedule_comparison_eligible` | Complete calendar context, no partial-calendar or held-out DST/block issue |
| `partial_calendar_review` | Retrospective same-snapshot/weekday screen detects exceptionally low active trip counts |
| `hourly_quality_screen_available` | Date lies within the observed hourly pilot; other dates lack this finer screen |
| `comparison_eligible` | Schedule eligibility plus available conservative demand; positive denominator is also needed for ratios |
| `source_snapshot`, `prior_source_snapshot` | Selected archive names for current and preceding service dates |
| `lag_1d`, `lag_7d`, etc. | Exact-date prior conservative count; missing if absent or flagged; not guaranteed available operationally |
| `past_same_weekday_mean` | Mean of available 7/14/21/28-day lags, only with at least two values |
| `pattern_id` | Hash of ordered stop IDs, including repeated visits; local descriptive grouping |
| `headway_gap_count` | Number of within-pattern consecutive departure gaps, departures minus one |
| `departure_span_hours` | Last minus first departure for that pattern/service date; not overnight circular coverage |
| `shape_length_km` | Haversine sum along supplied ordered geometry; not bus odometer or independently routed distance |
| `boardings_per_scheduled_*` | Descriptive boarding/service ratio on compatible observations; not occupancy/load factor |
| `exclusive_stop_ids` | Stops used only by this route within the selected Manhattan network and archive |
| `jaccard` | Shared unique stop IDs divided by union |
| `smaller_route_overlap` | Shared unique stop IDs divided by the smaller stop-set size |

Count-based profiles use the same eligible dates for numerator and denominator. Structural
template means weight each scheduled template once within its archive; they are not weighted by
how often the calendar activates that template over a year.

## Forecasting products

Notebook 05 saves a separate `forecasting/` subdirectory under the processed data folder.
Its manifest records source hashes, feature order, category mapping, package versions and product hashes.

| Product | Grain / interpretation |
|---|---|
| `historical_examples` | Route/target date with weekly issue date, assumed availability cutoff and demand-history features |
| `validation_predictions`, `test_predictions` | Model/route/target date; actual published estimate and predicted boardings |
| `validation_scores`, `test_scores` | Model; MAE, RMSE, WAPE, signed bias and scored population |
| `test_route_metrics`, `test_horizon_metrics` | Model/route or model/horizon error diagnostics |
| `validation_origin_audit`, `test_origin_audit` | Weekly origin; training cutoff, training size and scored target span |
| `test_coverage` | Expected target rows, unavailable targets, insufficient-history exclusions and scored zeros |
| `delay_sensitivity_*` | Repeated evaluation with a 28-day assumed delay; scores use the common target population |
| `illustrative_forecast` | Route/date point forecast for 5–11 October 2026; no observed outcomes in this collection |

`prediction` is a nonnegative boarding estimate, not occupancy. `horizon=1` is the issue date.
`availability_cutoff` is the latest assumed available payment date; `max_history_date` bounds all
lag lookups. The default `weekly_lag_2` through `weekly_lag_5` use t−14/21/28/35-day values;
under delay sensitivity these column slots hold the four latest eligible same-weekday observations.
No observation is filled with zero. Missing targets are excluded from training and evaluation.

## Forecast validation and monitoring

Notebook 06 preserves notebook 05's outputs and creates `forecasting_followup/` tables with a
14-complete-day maturity policy. Its manifest identifies a separate monitoring snapshot and protocol.

| Product / folder | Meaning |
|---|---|
| `data/raw/new_york_monitoring/<timestamp>/` | Immutable publisher metadata, route/date export, separate denominator query and SHA-256 receipts |
| `revision_comparison.csv` in the snapshot | Exact overlapping route/date boarding totals compared with the original frozen collection |
| `forecasting_followup/calibration_predictions` | Out-of-sample calibration errors after the validation-based model selection period |
| `evaluation_intervals` | Model/route/date/nominal-level bounds evaluated on later released targets |
| `interval_coverage`, `route_interval_coverage`, `weekly_interval_coverage` | Achieved coverage, mean interval width and mean interval score |
| `later_outcome_predictions`, `later_outcome_scores` | Preserved October forecast scored using later-acquired mature outcomes |
| `prospective_intervals`, `baseline_prospective_intervals` | Future point predictions and empirical bounds for model and baseline |
| `prospective_registry/<timestamp>/` | Write-once forecasts and registration metadata; model artifact and hashes when applicable |

`level` is nominal interval coverage, not a validated guarantee. `lower` is clipped to zero;
`upper` is an empirical upper bound. Achieved coverage must be reported separately. Missing
future outcomes are pending and never converted to scored zero targets. The 14-day maturity
policy follows the publisher's warning but does not establish exact first-publication latency
or guarantee that later revisions cease.

## Forecast error analysis

Notebook 07 saves separate products under `forecast_error_analysis/`.

| Product | Meaning |
|---|---|
| `protocol_scores` | Original test, maturity-14 evaluation and October scores kept as distinct populations |
| `route_errors`, `october_route_errors` | Paired model/baseline route errors, signed bias, WAPE and excess absolute error |
| `weekday_errors`, `weekly_errors` | Paired errors by target weekday or weekly origin; weekday and horizon remain confounded |
| `realized_growth_errors` | Outcome-dependent diagnostic groups, excluded from prediction features |
| `interval_miss_directions`, `scaled_error_quantiles` | Upper/lower misses and calibration/evaluation error distribution summaries |
| `development_selection_*` | Predictions, scores and cutoff audits for July–August 2025 candidate selection |
| `development_calibration_*` | Released calibration predictions and cutoff audits for September 2025 |
| `development_assessment_*` | Later October–November 2025 predictions, scores and origin audits |
| `development_intervals`, `development_interval_coverage` | Symmetric and signed-residual intervals on the selected point candidate, with measured assessment coverage |

Positive `excess_absolute_error` means that the model loses to the baseline on the same observations.
`model_bias` is prediction minus actual. These columns describe forecast performance, not route
efficiency or occupancy. Anchored candidate ratios use a fixed 100-boarding scale floor and are
converted back to boarding units before scoring. No candidate in this replay replaces a registered
forecast. Its manifest checks the prior forecast artifacts and registration files remain unchanged.

## Extended October assessment and previews

Notebook 08 writes `october_validation/` with a fixed protocol, early selection, warm-up/context
predictions, distinct all-October/additional-October scorecards, rolling intervals and a calibration
audit. The primary additional sample excludes 5–11 October; it contains 574 route/dates across
14 dates. The complete mature October population has 861 observations.

`annual_scaled` uses a 364-day weekday reference adjusted by a released 28-date ratio of sums;
`annual_blend_50` averages that estimate with the weekly mean. Missing annual history and federal
holiday mismatches fall back to the weekly mean, with an explicit eligibility flag. No target
observation enters the ratio calculation.

`experimental_profile.json` distinguishes the retained reference, the earlier-selected challenger
and the rejected deterministic proposal. Preview folders are timestamped under
`forecast_previews/`; each contains point forecasts, eligible empirical ranges, calibration metadata
and source/code/runtime fingerprints. Empty range files mean uncertainty is withheld, not zero.
Preview forecasts are not substitutes for the original prospective registrations.

## Exploratory route grouping

Notebook 09 writes a separate `route_clustering/` folder. Profiles use common eligible dates
between 6 July and 27 September 2026. Demand and scheduled service are combined across directions.
Known zero service remains an observation; missing values are not imputed.

| Product | Grain / interpretation |
|---|---|
| `date_coverage` | Calendar date; expected/eligible routes, exclusion diagnostics and common-date decision |
| `profile_members` | Route/date; matched boardings, service, six-hour peak boardings and archive identities |
| `route_profiles` | Route; day-type support, means, ratios and separately versioned structural context |
| `feature_definitions`, `feature_correlations` | Distance-input definitions, block multipliers and correlations |
| `scaled_features`, `scaler_parameters`, `cluster_centres` | Route/input or group/input; exact fitted distance representation |
| `kmeans_candidates` | Candidate k; silhouette, inertia, smallest/largest group and selection |
| `dbscan_scores`, `dbscan_assignments` | Density-parameter setting or setting/route; noise retained as unassigned |
| `route_assignments`, `group_summary` | Route or group; descriptive membership, representative routes and diagnostics |
| `bootstrap_scores`, `bootstrap_assignments`, `coassignment` | Whole-week refit, refit/route or route pair; stability diagnostics |
| `sensitivity_scores`, `sensitivity_assignments` | Representation variant or variant/route; fixed-k comparisons |
| `temporal_scores`, `temporal_assignments` | Six-week period or period/route; independently refitted partitions |

Weekend ratios average the Saturday and Sunday means before dividing by the weekday mean.
`weekday_peak_share` uses 07:00–10:00 and 16:00–19:00 as half-open clock-hour intervals.
`centroid_margin` is (second-nearest minus nearest distance) / second-nearest distance.
`bootstrap_retention` aligns arbitrary group IDs to maximize overlap; it is not a probability
of correctness. `group_membership_review` flags retention below 0.8, margin below 0.1,
negative silhouette or insufficient valid bootstrap refits. These thresholds are descriptive
review rules, not operational acceptance criteria.

`service_alignment_review` records positive boardings on a known-zero-service date. The
source cause is unresolved. `group_id` is ordered by group median weekday demand for readability,
not performance. The saved trusted local model and manifest record the population, code, runtime
and source/output hashes. Group IDs are not efficiency, crowding or intervention labels.

## Explainable historical review

Notebook 10 writes `route_review/` for the same July–September common-date observation window.
The routes and directions are unchanged; all three rule families retain unavailable evaluations.

| Product | Grain / interpretation |
|---|---|
| `route_day_type_evidence` | Route/day type; paired totals, dates, rates, support and source-alignment eligibility |
| `rule_evaluations` | Route/family/day type; every available, unavailable, triggered and nontriggered case |
| `review_signals` | Triggered route/family/day type; full evidence and sensitivity diagnostics |
| `route_review_table` | Route; workflow state, reasons, keyed evidence IDs, dates and descriptive context |
| `planning_review_queue`, `source_clarification_queue` | Filtered route tables; different follow-up purposes |
| `source_issue_dates`, `source_issue_summary` | Route/date or route/day type; positive boardings with zero scheduled service |
| `route_context` | Route; exploratory group, September coverage/overlap and separately dated forecast diagnostics |
| `forecast_context` | Route/strategy; retrospective errors on the 14 additional October target dates |
| `threshold_sensitivity_summary`, `threshold_evaluations` | Setting/family or setting/route/family/day type |
| `bootstrap_runs`, `bootstrap_evaluations` | Stratified whole-week resample or resample/route/family/day type |
| `signal_diagnostics` | Original signal; same-direction counts among eligible alternative evaluations |

`review_order` is a workflow display order: source clarification, insufficient evidence,
planning review, no rule triggered. Alphabetical order breaks ties. It is not route performance.
`review_evidence_ids` link to rule signals; `source_evidence_ids` link to source issue dates.

`metric` is boardings/bus-hour for relative service use and a ratio of two rates for the
weekend/temporal families. `numerator_boardings` and `denominator_bus_hours` retain the paired
totals. Reference dates/counts and reference totals accompany same-route comparisons; a peer
median has no single reference numerator/denominator. Unavailable `triggered` values remain
missing, rather than false. A genuine zero boarding rate can be available.

`bootstrap_retention` is the fraction of eligible resamples triggering the same original
direction; fewer than 60 eligible resamples makes it unavailable. `threshold_retention` uses
the nine declared threshold settings. Neither is a probability of correctness. Flag counts
are not added into a score. Later October forecast errors and September structural context
are explicitly dated and cannot affect review decisions.

## Historical frequency scenarios

Notebook 11 writes `service_scenarios/`. Baselines preserve the paired July–September
observations and review period. A route with unresolved source clarification is withheld
for every day type, including a day type whose own paired totals are otherwise positive.

| Product | Grain / interpretation |
|---|---|
| `scenario_baselines` | Route/day type; paired totals, daily means, exact date-set hash, source state and eligibility |
| `frequency_comparisons` | Route/day type/frequency factor; fixed-demand alternatives under the stated resource limit |
| `case_summary` | Day type/frequency factor/arithmetic status; counts of alternative cases, not a combined proposal |
| `focus_comparison` | Frequency factor for the fixed illustrative route/day type |
| `budget_sensitivity` | Budget label/frequency factor for the fixed example; unspecified budgets retained explicitly |
| `demand_sensitivity` | Independent assumed demand factor/frequency factor for the fixed example |
| `transfer_comparisons` | Transfer case/route; donor and recipient arithmetic on exactly the same observation dates |
| `transfer_summary` | Transfer case; summed bus-hour conservation, departure difference and limit status |
| `transfer_corridor_context` | Snapshot/route pair; shared and pair-specific stop IDs, without merger inference |
| `constraint_examples` | Example/route/day type; source withholding, floor failure and unspecified-budget cases |

`mean_departures` and `mean_bus_hours` are means over paired clock dates. Scenario quantities
prefixed `scenario_` are assumptions/calculations, not additional observations. Departures
and service hours scale together; demand is fixed or independently multiplied. This does not
estimate elasticity, onboard occupancy, actual delay or measured benefit.

`retention_limit_pass` checks the stated fraction of average departures. `added_hours_limit_pass`
is missing when no limit is supplied, and both flags are missing for source-withheld cases.
`arithmetic_status` distinguishes those cases and failed limits. Every row retains
`timetable_feasibility=not_assessed` and `automatic_service_change=False`.

Percentage intensity change is unavailable for a genuine zero-demand baseline; its absolute
scenario intensity remains zero. Unavailable projections are missing rather than zero.
Transfer bus-hour sums are conserved under the assumptions, while departure totals can differ.
