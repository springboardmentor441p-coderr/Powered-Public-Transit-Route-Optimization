# RouteRanker: New York bus demand and service analysis

Analyze **published route-level boarding estimates alongside date-matched bus schedules** to
identify demand patterns, shared corridors and questions for service planners. The current
deliverable covers collection, inspection, cleaning, feature engineering and exploratory data analysis.

The historical schedule case is the **Manhattan GTFS network**. Broader New York ridership and
the six current borough/company feeds provide source context. Historical demand and service
comparisons are limited to the Manhattan routes and dates supported by the selected archives.

## Start with the notebooks

| Order | Notebook | What to inspect |
|---|---|---|
| 1 | [Data inspection](notebooks/new_york/01_data_inspection.ipynb) | Source identity, dimensions, types, missingness, keys, references, dates and time checks |
| 2 | [Data cleaning](notebooks/new_york/02_data_cleaning.ipynb) | Duplicate/conflict rules, quality flags, reconciliation, route crosswalk and retained observations |
| 3 | [Feature engineering](notebooks/new_york/03_feature_engineering.ipynb) | Exact-date lags, calendar-selected service, overnight alignment, durations, distances, headways and coverage |
| 4 | [Exploratory analysis](notebooks/new_york/04_exploratory_data_analysis.ipynb) | Demand curves, route/hour heatmaps, density maps, overlap, service-use comparisons and findings |

Each notebook is the editable analysis, with questions, code, saved outputs and interpretation.
Small shared functions handle tested boundary cases. Saved outputs record the results;
fresh-kernel execution reproduces them from the documented source collection.

## What the data supports

- Published boarding estimates by route/date, with an observed route/hour pilot.
- Scheduled bus service, trip durations, shape lengths and stop coverage.
- Historically aligned **descriptive** boarding/service ratios, with explicit eligibility flags.
- Evidence for planner review, including sample sizes, source versions and coverage implications.

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
documentation/             public methods, requirements and table definitions
notebooks/new_york/         four canonical analysis notebooks, including outputs
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

Future development includes chronological training preparation, seasonal baselines, regression,
interpretable clustering, reviewed scenarios and a **Streamlit** dashboard. FastAPI/PostgreSQL
may support that later application. Publication delays and evaluation assumptions must be resolved
before an operational forecasting claim. No frontend or model is part of this deliverable.

Work only on `Rohan-Rajbanshi`; never push to `main` or another collaborator's branch.
