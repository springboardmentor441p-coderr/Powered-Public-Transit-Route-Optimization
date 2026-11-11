# RouteRanker: New York bus demand and service analysis

Analyze **published route-level boarding estimates alongside date-matched bus schedules** to
identify demand patterns, shared corridors and questions for service planners. The current
deliverable covers collection, inspection, cleaning, feature engineering, exploratory data analysis,
retrospective daily demand forecasting, exploratory route grouping, explainable review evidence
and assumption-based frequency scenarios.

**Forecasting research milestone: complete for review; no operational model promoted.**
Read the [consolidated milestone decision](documentation/FORECAST_MILESTONE.md) for the
comparison, acceptance criteria, reproducibility handoff and pending prospective evidence.

The historical schedule case is the **Manhattan GTFS network**. Broader New York ridership and
the six current borough/company feeds provide source context. Historical demand and service
comparisons are limited to the Manhattan routes and dates supported by the selected archives.

## Planning application

The primary interface is React/TypeScript with FastAPI and PostgreSQL. Open the
[application guide](documentation/APPLICATION.md) for setup, the
[API contract](documentation/API_CONTRACT.md) for endpoints and the
[acceptance report](documentation/ACCEPTANCE.md) for verification and limitations.
Maps, paired route comparisons, named rankings, frozen daily forecasts, historical
replay and saved service scenarios form the planning workflow. Earlier Streamlit
work remains available as a separate analysis interface.

## Start with the notebooks

| Order | Notebook | What to inspect |
|---|---|---|
| 1 | [Data inspection](notebooks/new_york/01_data_inspection.ipynb) | Source identity, dimensions, types, missingness, keys, references, dates and time checks |
| 2 | [Data cleaning](notebooks/new_york/02_data_cleaning.ipynb) | Duplicate/conflict rules, quality flags, reconciliation, route crosswalk and retained observations |
| 3 | [Feature engineering](notebooks/new_york/03_feature_engineering.ipynb) | Exact-date lags, calendar-selected service, overnight alignment, durations, distances, headways and coverage |
| 4 | [Exploratory analysis](notebooks/new_york/04_exploratory_data_analysis.ipynb) | Demand curves, route/hour heatmaps, density maps, overlap, service-use comparisons and findings |
| 5 | [Demand forecasting](notebooks/new_york/05_demand_forecasting.ipynb) | Availability cutoffs, seasonal baselines, weekly chronological evaluation and an illustrative seven-day outlook |
| 6 | [Forecast validation](notebooks/new_york/06_forecast_validation.ipynb) | Publisher maturity evidence, interval calibration, later outcomes and prospective registration |
| 7 | [Forecast error analysis](notebooks/new_york/07_forecast_error_analysis.ipynb) | Route/weekday error attribution, interval misses and earlier development candidates |
| 8 | [Extended October validation](notebooks/new_york/08_october_validation.ipynb) | Additional mature outcomes, annual candidates, rolling residual ranges and an experimental preview profile |
| 9 | [Route profiles and clustering](notebooks/new_york/09_route_profiles_and_clustering.ipynb) | Common-date demand/service profiles, small KMeans partitions, density sensitivity and membership stability |
| 10 | [Explainable route review](notebooks/new_york/10_explainable_route_review.ipynb) | Explicit historical review signals, source clarification, thresholds, evidence links and resampling sensitivity |
| 11 | [Frequency scenarios](notebooks/new_york/11_service_frequency_scenarios.ipynb) | Paired daily-mean baselines, trip/hour arithmetic, explicit resource limits, independent demand assumptions and illustrative transfers |

Each notebook is the editable analysis, with questions, code, saved outputs and interpretation.
Small shared functions handle tested boundary cases. Saved outputs record the results;
fresh-kernel execution reproduces them from the documented source collection.

## What the data supports

- Published boarding estimates by route/date, with an observed route/hour pilot.
- Scheduled bus service, trip durations, shape lengths and stop coverage.
- Historically aligned **descriptive** boarding/service ratios, with explicit eligibility flags.
- Evidence for planner review, including sample sizes, source versions and coverage implications.
- Daily boarding forecasts evaluated against seasonal baselines under explicit publication-delay assumptions.
- Descriptive route groups with common observation dates, interpretable profiles and sensitivity flags.
- Historical review queues with explicit reasons, sample support, dates and source-quality gates.
- Frequency-scenario arithmetic with paired historical baselines, declared assumptions and resource-limit checks.

The source does **not** measure onboard occupancy, alightings, actual bus arrivals, delays,
vehicle capacity, passenger destinations or operating costs. Low boardings per scheduled hour
do not prove a route is unnecessary. Shared stops do not justify merging routes. No passengers,
crowding labels, prediction accuracy or operational savings are fabricated.

## Reproduce the analysis

Use Python 3.11 or newer in a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m ipykernel install --user --name routeranker --display-name "Python (RouteRanker)"
```

The command-line notebook runner uses the `python3` kernel. If that kernel points to a different
environment, register this virtual environment with `--name python3`, or run the notebooks in
VS Code with the `Python (RouteRanker)` kernel selected.

On an existing collection, run:

```powershell
python scripts/week1_inspection.py
python scripts/validate_historical_alignment.py
python scripts/execute_notebooks.py --kernel routeranker
python -m unittest discover -s tests -v
```

For a fresh collection, first run `python scripts/collect_new_york.py` and
`python scripts/collect_extension.py`. These download real public sources and record receipts.
Publisher data/current GTFS can change: a new download is a new source version, so counts may
differ. See [sources and reproduction](documentation/SOURCES.md). Do not mix new files with old
derived tables. The notebooks verify source and product fingerprints and fail on inconsistent inputs.

## Repository structure

```text
PROJECT.md                 project objective and entry point
streamlit_app.py            Streamlit application entry point
dashboard/                 verified data access, charts and planner-facing pages
documentation/             public methods, requirements and table definitions
notebooks/new_york/         eleven canonical analysis notebooks, including outputs
scripts/                   collection, audits, small shared functions and notebook runner
tests/                     meaningful calendar, time, duplicate and lag cases
data/raw/                  original downloads and receipts (local, ignored)
data/processed/new_york/    derived CSV tables and manifests (local, ignored)
reports/                   generated inspection, alignment and EDA evidence (local, ignored)
```

Generated tables and figures are saved locally; notebook outputs provide reviewable evidence in
the code repository. Downloaded datasets and generated artifacts are excluded from version control.
See the [README](README.md) for contribution guidelines.

## Requirements and next stage

See the [requirements matrix](documentation/REQUIREMENTS.md),
[methodology](documentation/METHODOLOGY.md), [data dictionary](documentation/DATA_DICTIONARY.md)
and [EDA findings](documentation/EDA_FINDINGS.md).

Forecasting closure is recorded in the [milestone decision](documentation/FORECAST_MILESTONE.md).
An isolated fresh-environment replay passed all 34 tests and regenerated 53 identical tables.
The seasonal mean remains the reference; prospective acceptance is pending.

The [extended October assessment](documentation/OCTOBER_VALIDATION.md) adds 574 newly scored
route/dates and a guarded experimental preview command. The seasonal mean is the preview default;
the earlier-selected anchored model is an optional challenger. Historical gains do not establish
operational acceptance, and unreliable ranges are withheld.

The [forecasting protocol and results](documentation/FORECASTING.md) describe the daily demand
experiments. Interval evaluation and later outcomes expose reliability limits; future registered
forecasts must be evaluated before deployment. The [error analysis](documentation/ERROR_ANALYSIS.md)
separates observed weaknesses from earlier development comparisons. The
[route-grouping assessment](documentation/ROUTE_GROUPING.md) adds an exploratory peer-comparison
layer without changing forecasts or assigning crowding labels. The
[explainable review workflow](documentation/ROUTE_REVIEW.md) retains every route and separates
source clarification from historical planning-review signals. The
[frequency-scenario component](documentation/SERVICE_SCENARIOS.md) compares assumed trip changes
and scheduled bus-hour requirements without generating timetables or claiming passenger benefits.
The [Streamlit workspace](documentation/DASHBOARD.md) connects the completed analysis through
eleven functional workspaces, interactive route/date filters, forecasts, evidence exports and live
scenario arithmetic. Start it with `python -m streamlit run streamlit_app.py` after installing
`requirements-dashboard.txt` and restoring the validated local artifacts. It binds to
http://127.0.0.1:8501 by default.

Future development includes publication-vintage validation and prospective evaluation.
FastAPI/PostgreSQL may support shared access and persistent scenario storage later.
Operational forecasting still requires verified publication timing and prospective acceptance.

The [delivery status](documentation/DELIVERY_STATUS.md) records the added GTFS upload,
paired comparison, saved proposals, budget-constrained proxy allocation, observed-load intake
and final report/presentation. The [walkthrough](documentation/DEMO_AND_DEPLOYMENT.md) demonstrates
the application end to end. Independent crowding labels and validated operational benefits
remain unavailable; the software does not manufacture those outcomes.

Work only on `Rohan-Rajbanshi`; never push to `main` or another collaborator's branch.
