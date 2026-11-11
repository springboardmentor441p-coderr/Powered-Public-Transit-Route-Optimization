# Analysis choices and limitations

## Population and measured quantities

The primary historical network is the Manhattan feed's trip-referenced bus routes. M100 is published
in the Bronx feed and is outside this historical schedule case. Route catalogues can contain records
without trips; catalogue counts are not active-route counts. The larger ridership collection remains
available for demand-only context.

MTA ridership is a publisher estimate based on electronic fare activity, potentially including
imputation. It is neither a count of unique people nor onboard occupancy. Transfers are already a
subset of the boarding estimates and are never added again. The raw fare-category sample is only
10,000 records; complete category-level validation is not claimed for the aggregate extracts.

## Cleaning

Original bytes and receipts are immutable. Exact duplicate rows may be removed; conflicting keys
are quarantined and stop the workflow. Missing/invalid numeric fields fail validation rather than
being zero-filled. No source time, coordinate or ridership value is heuristically corrected.

Network dates/hours with zero demand, or demand below 20% of a past same-weekday(/hour) comparison
mean, are flagged. At least two of the prior 7/14/21/28-day observations are required. These flags
do not establish a reporting outage. Published values remain present; conservative analysis masks
them, and EDA shows sensitivity to that decision. Ordinary zero route counts remain zero.
Dates containing flagged hourly observations are also withheld from the conservative daily view.
Outside the hourly pilot, that finer-grained screen is unavailable, not implicitly passed.

## Identity, calendars and clock dates

The crosswalk is exact GTFS `route_id` to publisher `bus_route`, validated as one-to-one within
each archive. SBS display names differ (`M15-SBS` versus `M15+`); the source route IDs already match.
This mapping is specific to this MTA collection. Route renaming/history beyond observed identifiers
is not inferred.

Select the latest captured **whole** archive on/before a service date, then apply feed validity,
weekly calendars and calendar exceptions. Never backfill a withdrawn/inactive route from another
snapshot. Capture dates are catalog observation dates, not verified agency publication times.
Missing historical schedules remain missing.
An active calendar can still be partial: an archive boundary with only two trips is not a complete
city timetable. Days below 20% of their same-snapshot/same-weekday median (at least two comparison
dates) are flagged for partial-calendar review; that day and its incoming overnight context are
withheld. This is a retrospective completeness screen, not an inferred correction or future feature.

GTFS times preserve extended hours. The original service date remains attached to pattern features.
For comparisons with payment dates, starts and scheduled operating intervals are assigned to actual
local clock hours through UTC using GTFS's local-noon-minus-12-elapsed-hours convention. The
sum of trip-hour contributions equals scheduled trip duration. Current and preceding calendar
context must be complete. Route/date vehicle-block conflicts and DST transition neighbourhoods
are withheld; the publisher's repeated-hour interpretation is not established.

The previous `reports/historical_alignment` results are the earlier conservative short-name,
service-date audit. New feature tables extend that method using exact route IDs and clock-date
integration. Both are preserved with different meanings; their row counts should not be substituted.

## Feature grains and interpretation

- Trip template: one snapshot/trip ID, with scheduled duration, stop visits, pattern and shape length.
- Pattern/service day: one date/route/direction/origin/ordered-stop-pattern, with departure gaps.
  Different patterns are not mixed into a single headway series. One departure has no headway;
  sample standard deviation requires at least two gaps.
- Clock date/hour: both directions' service combined, because demand has no observed direction.
- Route/day type: sums over eligible matched dates. Ratios divide **sums by sums**, not mean daily ratios.
- Structure: explicitly versioned September geometry; no claim that it describes every historical date.

Shape length sums haversine polyline segments. Shape jumps over 5 km and invalid/short shapes
are screened; this threshold is not proof of an error. Length is not independently routed road distance.
Headways and service hours are scheduled, not actual reliability measures.

Overlap uses unique stop IDs; nearby opposite-direction stops may have different IDs. Exclusive
stop counts refer only to the analyzed network. Approximate route-density cells count routes with
sampled shape points; sparse geometry can miss cells crossed between points.

## EDA and later modelling

Weekday/Saturday/Sunday are calendar categories. Agency exceptions control schedules, but holiday
and weather causes are not inferred from low counts. Review lists require at least 20 comparable
dates and use an illustrative within-day-type 10th percentile. Sensitivity at 10/20/30 dates is shown.
Neither relative service use nor overlap is an operational recommendation.

Exact-date lags of 1, 7, 14, 21 and 28 days are candidate retrospective features. Their creation does
not establish publication-time availability. Before modelling, agree the issue time/release delay,
choose chronological development/validation/test periods and recompute learned profiles within
training periods. Do not use target-derived ratios or review labels to predict that same target.
The EDA examines the full available window, so no part of it is claimed as an untouched final test.

The separate [route-grouping assessment](ROUTE_GROUPING.md) uses common eligible route/date
observations within the hourly pilot. It is retrospective unsupervised exploration. Inputs,
distance weights and group-count rules are explicit; scaling, feature and week sensitivities
remain attached to the resulting descriptions. These groups do not provide occupancy labels.

The separate [review workflow](ROUTE_REVIEW.md) evaluates explicit historical service-use,
weekend and temporal rules. Its reasons retain paired denominators, sample dates and thresholds.
Source clarification precedes planning review. Resampling and threshold frequencies are
sensitivity diagnostics, not probabilities that service needs changing. Cluster labels and
forecast errors are context only; no combined performance score is calculated.

The [scenario component](SERVICE_SCENARIOS.md) scales mean departures and clock-date service
hours by a declared factor on matched baseline observations. Unchanged aggregate service mix
is an assumption. Clock-date exposure divided by departures is not a measured vehicle cycle,
and fractional averages are not rounded into timetables. Independent demand multipliers are
not estimated responses to service. Resource-limit checks are arithmetic conditions only.

The inspection-through-EDA notebooks do not fit forecasting models. The separate
[forecasting protocol](FORECASTING.md) defines the subsequent modelling experiment,
availability assumptions and evaluation boundaries. Causal elasticity, actual delay,
crowding labels and optimization benefits remain unobserved.

## Primary references

- [MTA ridership dataset](https://data.ny.gov/Transportation/MTA-Bus-Hourly-Ridership-Beginning-2025/gxb3-akrn)
- [MTA schedule publication and borough boundaries](https://www.mta.info/developers)
- [GTFS schedule reference](https://gtfs.org/documentation/schedule/reference/)
- [Manhattan archive catalogue](https://mobilitydatabase.org/feeds/gtfs/mdb-513)
