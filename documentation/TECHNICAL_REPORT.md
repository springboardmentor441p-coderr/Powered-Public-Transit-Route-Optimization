# RouteRanker: transit service planning prototype

Technical report - 8 November 2026

## 1. Purpose and delivered application

RouteRanker supports a planner preparing a service-review proposal: choose routes and a
period, inspect observed demand against matching published service, identify review
evidence, compare alternatives, and retain the assumptions for discussion.

The primary implementation uses 41 Manhattan routes. It is a historical decision-support
prototype with experimental forecasts. It does not represent 23 Indian-city implementations,
an operational dispatch system, a verified crowding detector, or measured intervention effects.

The application includes eleven workspaces: overview, route explorer, demand forecasts,
planning review, service scenarios, data coverage, route comparison, planning proposals,
budget allocation, GTFS import, and observed-load classification intake.

## 2. Evidence and source handling

The initial publisher boarding extraction contains 275,896 route/date rows across 450 route
codes, covering January 2025 through September 2026. The hourly extraction covers July
through September 2026. Boarding estimates count entries, not unique people or on-board loads.
The analytical cohort restricts historical comparisons to 41 exactly matched Manhattan routes.

Five dated Manhattan GTFS captures support historical alignment. Six current borough/company
feeds were also collected. Captures are selected as whole versions, never assembled by
falling back to another version for a missing route. Calendar exceptions and clock-date
exposure are accounted for. Archive gaps, partial calendars, DST and block-overlap contexts
can withhold comparison rows.

The eligible historical daily comparison contains 10,014 route/date records across 246
calendar dates. There are 86,486 eligible hourly comparisons. Maps and structural overlap
use the explicitly identified 3 September 2026 geometry snapshot.

Each original file is frozen with a URL, retrieval timestamp, byte count and SHA-256 receipt.
The dashboard pins 20 derived CSV tables and seven analytical documents/profiles. Missing
or changed artifacts block affected views. Uploaded files cannot replace this release.

Sources:
- MTA hourly boarding estimates: https://data.ny.gov/Transportation/MTA-Bus-Hourly-Ridership-Beginning-2025/gxb3-akrn
- MTA developer feeds: https://www.mta.info/developers
- Manhattan archive catalogue: https://mobilitydatabase.org/feeds/gtfs/mdb-513
- GTFS Schedule specification: https://gtfs.org/documentation/schedule/reference/

## 3. Inspection, cleaning, features and EDA

Notebooks 01-04 preserve executed outputs covering types, missingness, duplicate/conflicting
keys, memory, identifier references, calendar validity, GTFS time syntax, stop order, duration
validity, geographic checks, coverage, distributions, temporal curves and structural overlap.

Conflicting observations are quarantined rather than summed or guessed away. Genuine zero
observations remain distinct from missing values. Calendar-date lags do not shift across
missing dates. Ratios use paired sums with positive denominators.

Features include weekday/weekend categories, local hour, exact-date demand lags, seasonal
history, active scheduled departures, scheduled bus-hours, route structure and shared/exclusive
stop indicators. Same-day outcomes and their derived ratios are not predictors for the same
day's boarding target.

EDA demonstrates demand patterns and potential review questions. Shared stops alone do not
establish that passenger journeys can be merged, and low service frequency alone does not
establish underperformance.

## 4. Forecasting and classification boundaries

Notebooks 05-08 evaluate daily boarding forecasts using chronological comparisons against
seasonal baselines. Issue-time and maturity assumptions are explicit. Later captures expose
period-specific model weakness and interval undercoverage rather than erasing earlier results.

The additional October assessment contains 574 route/date targets across 41 routes on
1-4 and 12-21 October 2026. The seasonal mean reference MAE is 669.34 boardings, and the
earlier-selected anchored challenger MAE is 631.83, a 5.60% relative reduction. This is a
retrospective result, not proof of prospective reliability.

Reference nominal 80%/90% ranges covered 75.96%/87.11% of these outcomes. Challenger coverage
was 74.22%/84.49%, failing the declared display screen; challenger ranges are withheld.
No strategy has operational acceptance. Preserved pre-target November registrations remain
subject to the documented future evaluation policy.

The optional observed-load classifier requires independently observed balanced/overcrowded
route/date assessments with source references. It uses earlier-date demand lags and calendar
features, chronological 80/20 date separation, a most-frequent baseline and a Random Forest.
It saves the fitted preprocessing/model pipeline and held-out predictions only when suitable
labels are supplied. No independent load labels are currently installed, so no empirical
crowding-classification accuracy is claimed. Unit-test fixtures are isolated from study data.

## 5. Grouping and explainable review

Notebook 09 builds interpretable demand/service profiles on the same 78 dates for every route.
KMeans and DBSCAN experiments include scale, size, outlier and stability checks. The chosen
two-group description is strongly sensitive to representation choices, so every membership
remains exploratory and is not a performance class.

Notebook 10 evaluates 246 named rules: relative boarding/service use within day type,
weekend versus weekday contrast, and first-half versus last-half weekday contrast.
The review has 22 planning-review routes, 18 routes with no triggered rule, and M98 requiring
source clarification. There are 48 triggered signals. Four M98 dates have positive published
boardings but zero matched service; all its scenario baselines remain withheld.

Threshold sensitivity and whole-week resampling are retained. Ten signals are sensitive to
week sampling. Review order is a workflow, not a composite efficiency score. No-rule routes
are not labelled balanced. Forecast errors and group assignments do not decide the queue.

## 6. Alternatives and constrained allocation

Notebook 11 compares five frequency factors across 123 route/day-type baselines: 120 eligible
and three withheld. The 615 alternatives include controls and reductions; they are not a
single combined network plan. At fixed demand, trips and scheduled hours scale together.
Daily means remain fractional and do not define departure times.

For M34+ weekdays, a 20% increase changes mean departures from 172.16 to 206.59 and requires
12.45 additional scheduled bus-hours per day. It exceeds an illustrative ten-hour allowance.
Equal-hour transfer examples conserve paired scheduled hours but can change total departures.

The added allocation component solves a declared continuous convex problem:

Minimize sum over routes of D_i squared / N_i.

D_i is historical mean daily boardings held fixed; N_i is the proposed mean departure count.
Each N_i is bounded between baseline N_i and (1 + cap) times baseline N_i. The scheduled-hour
scaling coefficient is baseline hours / baseline departures, not a measured vehicle cycle.
Total added scheduled hours cannot exceed the declared budget. The exact shared date set
and all source gates must match before allocation.

The objective penalizes concentration in daily boarding intensity. It is a mathematical
planning proxy, not a standard crowding, waiting-time, access or welfare metric. Its direction
and assumptions are displayed. The bounded water-filling solution is checked against an
equal-spend feasible uniform-increase comparator and analytic test cases.

The weekday example allocates 50 extra scheduled hours across 40 eligible routes with a 20%
per-route cap and no cuts. The objective changes from 8,500,523.29 to 8,314,918.82 (2.18%),
versus 8,437,370.98 for an equal-spend uniform increase. These are objective-function changes,
not passenger benefits. M98 is excluded. Timetable, fleet, staffing and access feasibility
remain unassessed.

Merge/coordination hypotheses screen pairs with Jaccard at least 0.30 and at least ten shared
stop IDs. Split/variant hypotheses screen at least three stop patterns. These are pilot
investigation thresholds. Necessary short-turns or useful corridors can meet them. Each
candidate records its geometry version and required stop-order, walking-access, passenger-
journey and operational checks. No merge or split is certified by these screens.

## 7. Import and proposal workflows

The GTFS ZIP importer checks archive size/path constraints without extracting members, required
project columns, IDs and references, calendar additions/removals, exception-only calendars,
stop sequence keys, time syntax and ordering. Bus services are selected for a specific date.

Exact frequency templates use half-open departure windows. Non-exact headway service is
reported as expected counts, never precise departures. Trip counts survive incomplete durations
while affected route service-hours remain unavailable. Imported hours are service-day durations,
not interchangeable with the historical study's clock-date exposure.

A real-feed check on the 3 September capture inspected 1,174,914 stop events and selected
8,575 active bus trip templates for 14 September 2026, with no unavailable bus durations.
This verifies the importer on a real source in addition to small boundary fixtures.

Route comparison shows paired demand/service and shared/exclusive stops side by side.
Planning proposals retain a title, exact baseline, parameters, review evidence, required checks,
and calculated output. Append-only local bundles are fingerprinted; changed tables block export.
Saved assumptions are kept separate from observed facts and forecasts.

## 8. Architecture and reproducible handoff

Streamlit presents the verified analytical release and calls tested import, forecasting,
scenario and allocation functions. CSV/JSON artifacts retain explicit versions and hashes.
Scenario/proposal and optional classifier outputs are stored locally under data/app.
No database or separate frontend is required for this release.

The application technology remains Streamlit. FastAPI/PostgreSQL can support shared storage
and access later; neither is required for the original dashboard deliverable. Local append-only
proposal storage is not represented as a deployed PostgreSQL service.

Install requirements-dashboard.txt, restore the validated local artifacts, then run:
python -m streamlit run streamlit_app.py

The default host is 127.0.0.1. A Dockerfile and Compose configuration isolate read-only source
and analytical mounts, with separate writable preview/proposal/report locations. Docker
execution must be verified on a Docker-equipped host; the current host has no Docker runtime.
Shared deployment additionally needs authentication, backups, resource controls and monitoring.

The delivery includes the technical report, architecture description, walkthrough, test suite,
stakeholder presentation and explicit completion matrix. Original observations, executed
notebooks, saved models and prospective registrations are preserved.

## 9. Remaining evidence requirements

The 23-Indian-city geography is outside this New York implementation. Independent occupancy,
vehicle capacity or observed performance labels are required to demonstrate overcrowding
classification. No frequency-derived or synthetic labels substitute for this evidence.

Operational route changes require direction/time-specific passenger journeys, coverage/access
constraints, fleet/staff feasibility and an agency evaluation. Forecast acceptance requires
mature prospective outcomes and publication-vintage evidence. A better proxy score does not
close those requirements. These boundaries must remain visible in any project demonstration.
