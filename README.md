# RouteRanker

### Demand-informed bus-service planning for New York

RouteRanker is a planning decision-support prototype that combines published daily
bus boarding estimates with historically matched GTFS schedules. It helps a planner
inspect demand, compare routes, review daily forecasts and test service-frequency
changes with traceable assumptions.

The study focuses on **41 Manhattan routes**. The primary application uses
**React + TypeScript, FastAPI and PostgreSQL**. It is a tested research prototype;
operational forecasting acceptance and measured service benefits remain unverified.

## What the application does

- Displays version-labelled route maps and daily demand history.
- Compares routes using the same eligible dates and scheduled-service denominators.
- Ranks review priorities using named indicators and minimum sample sizes.
- Groups routes by interpretable profiles, with clustering sensitivity documented.
- Serves frozen daily forecasts with model versions and input provenance.
- Replays historical dates with controlled observation release and retained audit history.
- Saves baseline/proposed service scenarios, including forecast-linked demand and zero-service cases.

Maps show scheduled geometry. Replay is a historical demonstration, not a live
vehicle or passenger feed. Scenarios describe conditional arithmetic rather than
an executable timetable or automatic instruction to change service.

## Data and historical alignment

| Input | Use |
|---|---|
| [MTA Bus Hourly Ridership: Beginning 2025](https://data.ny.gov/Transportation/MTA-Bus-Hourly-Ridership-Beginning-2025/gxb3-akrn) | Published boarding estimates aggregated into daily route outcomes; hourly data used in exploration |
| [MTA GTFS schedules](https://www.mta.info/developers) | Routes, calendars, trips, stops, scheduled times and geometry |
| [Historical Manhattan feed archive](https://mobilitydatabase.org/feeds/gtfs/mdb-513) | Five dated snapshots for historical demand/service alignment |

The five selected captures are **30 December 2025, 27 March 2026, 9 April 2026,
24 June 2026 and 3 September 2026**. The validated crosswalk contains the same
41 public route identifiers in every snapshot. These are versions of one network,
not five different cities or five independent passenger datasets. An unchanged
route identifier does not establish an unchanged timetable or stop pattern.

One eligible snapshot is selected for each analysis date. Calendars, exceptions,
overnight service and quality gates determine the scheduled supply used in comparisons.
Missing observations remain missing; daily boardings do not establish simultaneous
occupancy, unique people or inbound/outbound passenger counts.

See [sources and reproduction](documentation/SOURCES.md),
[data dictionary](documentation/DATA_DICTIONARY.md) and
[methodology](documentation/METHODOLOGY.md).

## Analysis notebooks

Notebooks retain executed outputs, tables, figures and interpretations.

| Stage | Entry point |
|---|---|
| Inspection, cleaning, features and EDA | [01 Data inspection](notebooks/new_york/01_data_inspection.ipynb), [02 Cleaning](notebooks/new_york/02_data_cleaning.ipynb), [03 Features](notebooks/new_york/03_feature_engineering.ipynb), [04 EDA](notebooks/new_york/04_exploratory_data_analysis.ipynb) |
| Forecast development and validation | [05 Forecasting](notebooks/new_york/05_demand_forecasting.ipynb), [06 Validation](notebooks/new_york/06_forecast_validation.ipynb), [07 Error analysis](notebooks/new_york/07_forecast_error_analysis.ipynb), [08 October evaluation](notebooks/new_york/08_october_validation.ipynb) |
| Route grouping and review | [09 Route profiles](notebooks/new_york/09_route_profiles_and_clustering.ipynb), [10 Explained review](notebooks/new_york/10_explainable_route_review.ipynb) |
| Service scenarios | [11 Frequency scenarios](notebooks/new_york/11_service_frequency_scenarios.ipynb) |
| Daily replay forecasting | [12 Daily experiment](notebooks/new_york/12_daily_replay_forecasting.ipynb) |
| Schedule-feature comparison | [13 Paired experiment](notebooks/new_york/13_schedule_feature_comparison.ipynb) |

## Forecast results

The daily experiment selected Random Forest using validation data. On **2,501 common
June-July 2026 route/date test observations**, MAE was **501.37 boardings/day** versus
**514.03** for the seasonal mean baseline, a **2.46% improvement**. WAPE was **9.24%**
versus **9.47%**. WAPE is an aggregate error measure, not classification accuracy.

A separate, shorter schedule-covered experiment compared demand-only and service-aware
models on **2,281 common test observations**. Service-aware Random Forest MAE was
**644.21**, while the seasonal baseline achieved **524.77**. That candidate was not
promoted. The two experiments have different training and scoring populations.

These are retrospective results with simulated availability cutoffs. They do not
establish prospective or operational acceptance. Daily demand combines both directions.
Read the [forecast policy](documentation/FORECAST_ACCEPTANCE.json) and
[acceptance report](documentation/ACCEPTANCE.md) for the applicable gates.

## Run locally

**Prerequisites:** Python 3.11, Node.js 22, PostgreSQL and the validated local analysis
products. Data, fitted artifacts, credentials and runtime records are excluded from
Git. A fresh clone therefore requires restoring the validated bundle or reproducing
the collection and notebook workflow before database import.

From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-api.txt

# Create the router database in your PostgreSQL instance, then configure its connection.
$env:DATABASE_URL = "postgresql://<user>:<password>@127.0.0.1:5432/router"
python -m backend.import_data
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. API documentation is at **http://127.0.0.1:8000/docs**.

For packaged serving, run `npm run build` in `frontend`; FastAPI then serves the built
interface from its root URL. `compose.yaml` defines the React/API/PostgreSQL deployment;
it requires the processed bundle and a `POSTGRES_PASSWORD` environment variable.
**Container execution has not been verified on this development host.**

Full instructions: [application guide](documentation/APPLICATION.md),
[architecture](documentation/ARCHITECTURE.md) and [API contract](documentation/API_CONTRACT.md).
The earlier Streamlit interface remains available as a separate analysis workspace.

## Verification

The latest full suite passed **123 tests**. An isolated Python environment passed
**15 PostgreSQL API tests** and served the packaged interface. Browser checks covered
all eight screens, route-map selection, saved scenarios, forecast idempotency,
delayed actual reveal and reset history. These counts describe the recorded local run.

With the required data and services available:

```powershell
python -m unittest discover -s tests -v
python scripts/accept_application.py
python scripts/accept_planning_workspace.py
```

Browser checks additionally require the dependencies in `requirements-dashboard-test.txt`
and a Playwright Chromium installation. See [acceptance details](documentation/ACCEPTANCE.md).

## Scope and limitations

- Published boardings may include estimation and revisions; the reporting-delay policy is an explicit assumption.
- Scheduled supply is not actual completed service, vehicle assignments or measured delay.
- Clusters describe similarity and remain sensitive to modelling choices.
- Review indicators and service ratios do not prove overcrowding or justify service cuts.
- Scenarios hold stated demand/duration assumptions; fleet, crew, cost, transfer and accessibility constraints are not fully represented.
- Prospective model evaluation, planner review and independent-machine/container verification remain release conditions.

See [delivery status](documentation/DELIVERY_STATUS.md) and [product scope](documentation/PRODUCT_SCOPE.md).

---

## Contributing Guidelines (For Interns / Collaborators)

All interns added as collaborators to this repository must follow the branch workflow below. **Direct commits or pushes to the `main` branch are not allowed.**

> Note: `main` only contains the `LICENSE` and `README.md` — it is not used for active development. There is no need to pull the latest `main` into your branch at any point.
 



### 1. Branch Naming

- Every intern must create their own branch off `main`, named after themselves.
- Suggested naming convention: `firstname-lastname` (all lowercase, hyphen-separated).
  - Example: `john-doe`, `aisha-khan`

### 2. How to Create Your Branch

**Option A — Clone and push (recommended)**

```bash
# Clone the repository
git clone https://github.com/springboardmentor441p-coder/Powered-Public-Transit-Route-Optimization.git

# Move into the project folder
cd Powered-Public-Transit-Route-Optimization

# Create and switch to your own branch (off main)
git checkout -b your-name

# ... make your changes ...

# Stage, commit, and push your changes to YOUR branch only
git add .
git commit -m "Describe your change here"
git push origin your-name
```

**Option B — GitHub UI upload**

1. Go to the repository on GitHub.
2. Switch the branch dropdown from `main` to your own branch (create it first via **Branch: main → View all branches → New branch**, named after yourself).
3. Once on your branch, use **Add file → Upload files** to upload your code.
4. Commit directly to your branch (not `main`).

### 3. Rules

- ❌ Do **not** push or upload code directly to `main`.
- ❌ Do **not** push code to another intern's branch.
- ✅ Only push/upload code to the branch that carries your own name.
- Keep uploading/pushing your code to your branch regularly as you make progress. No pull requests are required — your branch itself is the deliverable.

### 4. Summary

| Action | Allowed? |
|---|---|
| Push to `main` directly | ❌ No |
| Create your own branch from `main` | ✅ Yes |
| Push/upload code to your own branch | ✅ Yes |
| Push/upload code to someone else's branch | ❌ No |
| Open a Pull Request | Not required |
