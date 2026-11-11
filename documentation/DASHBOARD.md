# Streamlit planning workspace

RouteRanker exposes the completed Manhattan analysis as a local, interactive Streamlit
application. It connects historical demand, matching schedules, experimental forecasts,
explainable review evidence, and frequency scenarios. It does not execute service changes.

## Start the application

From the repository root, with Python 3.11:

```powershell
python -m pip install -r requirements-dashboard.txt
python -m streamlit run streamlit_app.py
```

Open **http://127.0.0.1:8501**. The server binds to the local computer by default.
Stop it with Ctrl+C in the terminal. To use another port, add `--server.port 8502`.
The interface uses Streamlit directly; no separate frontend, API server, or database
is required for this local analytical release.

Dependencies are separated from the frozen forecasting environment. Streamlit 1.55.0 is
the tested application version. The existing forecasting lock file is unchanged.

## Local data prerequisites

The application uses real, previously validated analysis products. It does not substitute
demo rows when data is absent. Generated data remains excluded from Git.

- Restore the exact analytical bundle under `data/processed/new_york/`.
- Required artifacts are listed in `dashboard_data_manifest.json`: 20 CSV tables and
  seven analytical manifests/profiles, each with a SHA-256 fingerprint.
- Forecast previews additionally require their dated folders, the original validated
  monitoring capture, and upstream cleaned data referenced by each preview manifest.
- Generating a new preview requires the original cleaned cohort/history and validated
  notebook 08 products used by `scripts/forecast_preview.py`.
- With no saved previews, the forecast page explains their absence and offers guarded
  generation. Missing analytical inputs show a setup message, not fabricated results.

To rebuild from source, follow [source collection](SOURCES.md), historical alignment,
then notebooks 01–11 in their documented order. Downloading a mutable source again may
produce a different data version. Revalidate the upstream analysis before explicitly
refreshing the application catalog:

```powershell
python scripts/build_dashboard_manifest.py --refresh
```

This command checks the upstream product hashes and analysis lineage before pinning
files. It does not waive missing observations, source problems, or model acceptance.
The loader verifies file fingerprints before caching them; file replacement invalidates
the cache. The Data coverage page can check all pinned inputs.

## Pages and interactions

| Page | Functional controls and outputs |
|---|---|
| Overview | Fixed-cohort counts, common-date demand series, full review register, CSV export |
| Route explorer | Route/date/day-type filters; separate demand and scheduled-service series; hourly profile and sample sizes; route-variant map; overlap and exploratory group context; observation/geometry exports |
| Demand forecasts | Reference/challenger selection; dated issued previews; permitted empirical ranges; historical paired evaluation; route forecast and provenance downloads; guarded seven-day generation |
| Planning review | Status filters, route-specific reasons, dates, denominators, source issues, rule results and sensitivity; filtered queue and evidence exports |
| Service scenarios | Frequency and independent demand sliders, explicit resource limit or unspecified budget, retained-service floor, live calculations, paired bus-hour transfers, downloadable ZIP with assumptions and evidence |
| Data coverage | Source windows, archive count, excluded common dates, available/unavailable evidence, public source links, integrity check and manifest download |
| Route comparison | Paired route/day-type means, demand series, shared/exclusive stop context and two-route geometry |
| Planning proposals | Evidence-backed investigations, structural merge/split hypotheses, frequency alternatives, append-only save/reopen and package export |
| Budget allocation | Continuous constrained allocation of added scheduled hours, route caps, explicit objective and equal-spend comparison |
| GTFS import | Bounded upload, required-field/reference/calendar/time validation, explicit/expected frequency counts and isolated save/export |
| Observed-load classification | Independent-label contract, source gate and optional chronological classifier; no installed empirical load labels |

The selected route carries across pages. Overview and coverage always describe the full
41-route study. Explorer filters apply only to exploration; the review and scenario
baseline remains **6 July–27 September 2026**, with 78 shared eligible dates.
The map uses the **3 September 2026** geometry snapshot regardless of the date filter.
Basemap tiles require internet; geometry coordinates and downloads remain available locally.

## Interpretation and boundary behavior

- Boarding estimates are entries, not unique passengers, on-board loads, or crowding labels.
- Service rates use paired sums on the same eligible dates. Unmatched demand is excluded
  from the numerator, and missing service is not converted to zero.
- Empty filter selections have an explicit empty state. The explorer can display earlier
  demand while correctly reporting that no matching archived schedule is available.
- Source clarification overrides scenario eligibility. All M98 day-type projections
  remain withheld. Known historical observations stay visible.
- Review order describes workflow, not efficiency. No-rule routes are not labelled
  balanced; group membership is exploratory and not an input to a composite score.
- Scenario controls use the tested notebook 11 functions. Daily means remain fractional.
  Separate alternatives are not a combined network plan.
- A bus-hour transfer conserves paired scheduled hours, not departure counts or peak
  fleet. Source/date gates and retained-service limits remain active.
- Scenario exports contain the underlying baseline, exact-date fingerprint, parameters,
  arithmetic flags, and explicit unassessed feasibility. No CSV export changes source data.

## Forecast behavior

The seasonal mean is the default reference; the earlier-selected anchored model is
an experimental challenger. Neither has operational acceptance. Historical assessment
and issued previews occupy separate tabs.

Preview manifests record issue time, source observation time, maturity cutoff, strategy,
file fingerprints, and target window. The page distinguishes future, started, and fully
archived windows instead of displaying an old forecast as current. Point/range files,
upstream inputs, source capture, complete route/date coverage, and maturity bounds are
validated before display.

Reference empirical ranges passed the stated historical display screen; challenger ranges
are withheld. Displayed ranges do not guarantee future coverage. New generation invokes
the existing guarded pipeline with a future seven-day window. The validated source's
observation date caps maturity; waiting does not mature an unrevised cached snapshot.
Stale/missing history blocks generation and preserves earlier runs and registrations.

The app does not retrain on every interaction, download revised data automatically,
replace prospective registrations, or pair forecasts with an unrelated historical schedule.
See [forecast evaluation](OCTOBER_VALIDATION.md) and [scenario methods](SERVICE_SCENARIOS.md).

## Verification

```powershell
python -m unittest discover -s tests -v
```

Dashboard tests check six-page rendering, empty filters, unmatched schedule periods,
source withholding, changed scenario limits, unavailable ranges, forecast validation,
downloads, and missing-file handling. These use Streamlit's
[AppTest API](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

The 6 November application verification passed all **91 tests**, including 15 dashboard
checks. Browser navigation, map rendering, scenario ZIP download and input verification
passed with no JavaScript errors. A real application generation produced 287 reference
forecasts and 574 empirical-range rows for 7–13 November. All 320 pre-existing data and
notebook artifacts were unchanged.

For an optional browser check with the server already running:

```powershell
python -m pip install -r requirements-dashboard-test.txt
python -m playwright install chromium
python scripts/smoke_dashboard.py
```

The browser check visits all six pages, captures screenshots, opens the route map,
downloads and inspects a scenario ZIP, exercises integrity verification, and checks a
mobile viewport. Generated screenshots/reports stay local under `reports/dashboard/`.

## Deployment boundary

This is a functional local planning prototype using validated historical artifacts.
Shared operational deployment would additionally require access control, persistent
scenario storage, publication-vintage monitoring, prospectively accepted forecasts,
deployment monitoring and agency review. FastAPI/PostgreSQL can support those later
needs without replacing the Streamlit interface.
