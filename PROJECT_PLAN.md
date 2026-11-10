# RouteRanker: dataset inspection and phased implementation plan

## Workspace state
Inspected workspace: `D:\infosys springboard\milestone 1\codex version`. At inspection time it contains `data/raw/mtc-gtfs.zip` (9,088,141 bytes) and no application source, dependency manifests, or other project files. The ZIP was inspected in place; it was not extracted or modified.

## Actual archive inventory
Counts below are data rows, excluding headers.

| File | Rows | Columns |
|---|---:|---|
| `agency.txt` | 1 | `agency_id`, `agency_name`, `agency_url`, `agency_timezone`, `agency_phone`, `agency_lang` |
| `calendar.txt` | 6 | `service_id`, seven weekday flags, `start_date`, `end_date` |
| `feed_info.txt` | 1 | `feed_publisher_name`, `feed_publisher_url`, `feed_lang`, `feed_start_date`, `feed_end_date`, `feed_version`, `feed_contact_email`, `feed_contact_url` |
| `routes.txt` | 4,611 | `route_id`, `route_short_name`, `route_long_name`, `route_type`, `agency_id` |
| `stop_times.txt` | 1,360,443 | `trip_id`, `arrival_time`, `departure_time`, `stop_id`, `stop_sequence` |
| `stops.txt` | 5,580 | `stop_id`, `stop_name`, `stop_lat`, `stop_lon` |
| `trips.txt` | 47,047 | `trip_id`, `route_id`, `service_id`, `direction_id` |

All seven files have headers. No `shapes.txt`, `calendar_dates.txt`, `frequencies.txt`, `transfers.txt`, fare files, or GTFS Realtime data are present. This prevents shape-based route geometry, service exception handling, frequency-based service interpretation, transfer analysis, fare analysis, and real-time claims. Stop points are available from `stops.txt`; connecting them in sequence would be an inferred straight-line visualization, not supplied route geometry.

## Validation results
- Primary identifiers in `agency.txt`, `routes.txt`, `stops.txt`, and `trips.txt` are nonblank and unique.
- All foreign-key checks passed for the inspected rows: route agency references (1 unique), trip route references (3,934 unique), trip service references (2 unique), stop-time trip references (47,047 unique), and stop-time stop references (5,477 unique).
- No blank values were found in the inspected core route fields, stop name/coordinates, trip route/service IDs, stop-time fields, or calendar fields. `trip_headsign` is absent from `trips.txt` entirely, so direction/headsign labels are unavailable.
- All stop coordinates parse as numbers and fall within latitude/longitude bounds.
- Stop sequences are unique and strictly increasing in input order per trip. Arrival and departure times parse as GTFS `HH:MM:SS`; no within-trip arrival-time regressions were found. Maximum hour observed is 25, which is valid GTFS after-midnight schedule notation.
- `trips.txt` uses 3,934 of 4,611 route IDs: 677 route records are not referenced by trips.
- Trips use 2 of the 6 calendar service IDs: 4 calendar rows are unused. Two used service IDs resolve correctly; the four others are not evidenced by trips.
- Stop times reference 5,477 of 5,580 stop IDs: 103 stop records are unused.
- `calendar.txt` dates span `20240501` through `20300501`; all six rows share that interval. `feed_info.txt` has blank feed start and end date fields, and version `0.1`.
- The service ID `'/><script>alert(1)</script>` is present in `calendar.txt`. It is currently unused by trips, but feed values must be treated as untrusted and escaped in any UI/API output. The `test ` service ID also has trailing whitespace.
- `route_type` is `3` for all 4,611 route rows. `direction_id` is `0` for 23,674 trips and `1` for 23,373 trips.

These are archive inspection results, not claims about current live service. Re-run validation on any replacement feed.

## Proposed architecture

```text
project root
├── AGENTS.md
├── PROJECT_PLAN.md
├── README.md
├── .gitignore
├── data/
│   ├── raw/                 # supplied GTFS ZIP; immutable input
│   └── processed/           # generated, reproducible outputs (ignored)
├── backend/
│   ├── pyproject.toml
│   ├── src/routeranker/
│   │   ├── config.py
│   │   ├── ingestion/        # archive reading, schema mapping
│   │   ├── validation/       # GTFS structural and relationship checks
│   │   ├── storage/          # DuckDB setup and staging
│   │   ├── analysis/         # route, stop, coverage, headway, overlap
│   │   ├── clustering/       # feature prep, K-Means, DBSCAN, evaluation
│   │   ├── scenarios/        # transparent schedule what-if calculations
│   │   └── api/              # FastAPI routes and response schemas
│   └── tests/
└── frontend/
    ├── package.json
    ├── src/
    │   ├── api/
    │   ├── components/
    │   ├── features/         # dashboard, routes, service, scenarios
    │   ├── pages/
    │   └── types/
    └── ...                  # Vite and Tailwind configuration
```

The archive remains the immutable source. Ingestion should stream archive tables into validated, typed DuckDB staging tables; analytics should expose documented derived measures to FastAPI; the React client should consume typed API responses. Keep clustering and schedule scenarios separate from descriptive metrics, with parameters and limitations returned alongside results. Do not draw route lines without actual shape data; stop maps may show supplied coordinates and clearly labeled point-to-point approximations if later approved.

## Phased implementation plan

1. **Foundation and reproducibility** — establish Python and frontend manifests, Windows setup/run documentation, configuration, `.gitignore`, and application skeleton. Keep source ZIP untouched.
2. **GTFS ingestion and validation** — read ZIP entries without destructive extraction, validate required schemas/types/keys/references, surface quality findings, and load reproducibly into DuckDB. Include regression fixtures for anomalies and boundary cases.
3. **Descriptive route and stop analytics** — define explicit inclusion rules for unused records; implement route/stop summaries and coverage measures based on supplied stop coordinates and observed trip-stop relationships.
4. **Scheduled service analytics** — analyze trip counts, stop sequences, timetable times, and headways only where the feed supports valid scheduled comparisons. Account for after-midnight times and disclose date/calendar coverage limitations.
5. **Route overlap** — calculate route stop-set Jaccard similarity, document direction/route grouping choices, and avoid interpreting similarity as congestion or passenger substitution.
6. **Route clustering** — construct documented route-level features from supported schedule and stop data; scale features appropriately; provide K-Means and DBSCAN with reproducible settings and cluster diagnostics. Avoid demand/traffic features.
7. **Explainable what-if scenarios** — expose editable assumptions and arithmetic for schedule changes (for example, hypothetical trips or headway adjustments). Label all outputs as scenarios, not predictions or operational recommendations.
8. **FastAPI and dashboard** — provide typed endpoints and a responsive React/TypeScript dashboard using Recharts and Leaflet. Use Leaflet for stop points; no fabricated shapes, live vehicles, ridership, occupancy, or traffic overlays.
9. **Documentation and release readiness** — document data provenance, limitations, Windows commands, API contracts, model interpretation, and reproducible validation. Verify the full workflow before calling the project runnable.

## Approval boundary (initial plan)
The initial inspection did not implement application modules. The user subsequently approved the ingestion/preprocessing implementation recorded below.

## Implementation status after approval
The GTFS ingestion/preprocessing slice is implemented under `backend/` and has been run against the supplied ZIP. It writes per-table Parquet files and JSON/Markdown quality reports under the ignored `data/processed/gtfs/` directory. See `backend/README.md` for commands and `backend/tests/` for tests.

This implementation uses Polars for CSV validation and Parquet output because it is available in the current Python environment; DuckDB is not installed here and network access prevented package installation. DuckDB remains the planned query layer for later analytics. No frontend, API, clustering, or schedule scenario modules have been started.

The feed’s four unused calendar services, 677 unreferenced route rows, 103 unreferenced stop rows, blank feed start/end dates, and absent `calendar_dates.txt`, `shapes.txt`, `frequencies.txt`, and `transfers.txt` remain data limitations. The source ZIP is unchanged.


## Phase 2 implementation status
The approved EDA implementation is in `backend/src/routeranker/analysis/eda.py`. It reads Phase 1 Parquet tables and writes route/stop summaries, weekday and hourly scheduled service counts, headway estimates, route-stop coverage, all route-pair shared-stop/Jaccard values, charts, and JSON/Markdown reports under `data/processed/eda/`. It uses Polars lazy scans because DuckDB remains unavailable in the current environment. No machine learning, frontend, API, or dashboard work has started.


## Phase 3 implementation status
The approved feature-engineering implementation is in `backend/src/routeranker/features/`. It produces raw and normalized route, stop, and route-pair features in CSV and Parquet, saves a feature dictionary and normalization parameters, and validates results against the source ZIP plus Phase 1/2 outputs. Outputs are under `data/processed/features/`. No machine learning, frontend, API, or dashboard code has been started.

## Phase 4 implementation status
The approved unsupervised clustering implementation is in `backend/src/routeranker/clustering/route_clusters.py`. It reads and validates Phase 3 route features, inspects quality and missingness, trains K-Means and DBSCAN on routes with scheduled trip records, profiles clusters using raw features, and saves predictions, diagnostics, PCA outputs, and a report under `data/processed/clustering/`.

## Phase 5 implementation status
The approved FastAPI layer is in `backend/src/routeranker/api/`. It provides read-only, cached access to Phase 1-4 processed tables, explicit response schemas, pagination, filters, error handling, and local-origin CORS configuration. API endpoint tests are present; their execution requires the FastAPI and HTTPX dependencies documented in `backend/pyproject.toml` and `backend/README.md`.


## Phase 6 implementation status
The approved React and TypeScript frontend is implemented under `frontend/`, with six pages backed by the running FastAPI service. It uses actual GTFS-derived API responses; stop coordinates are mapped as points only because `shapes.txt` is unavailable. TypeScript compilation and the Vite production build pass; Phase 7 also verifies live API integration and browser workflows.


## Phase 7 local validation update (2026-11-05)

Architecture remains the existing Python/FastAPI backend and React/TypeScript/Vite frontend. Phases 1 through 6 are implemented; Phase 7 local validation has been performed; the skipped tests and runtime mismatch below prevent production readiness. Public deployment has not been performed. See `README.md` and `backend/README.md` for setup, API documentation, startup, build, and test commands.

Validation against the current processed MTC artifacts: the full discovered backend suite ran 23 tests with 19 passing and 4 skipped because HTTPX is unavailable in the active Python 3.12 virtual environment. Five opt-in live API tests passed when the local API was running. Eight browser workflows passed, including route and stop workflows, cluster insights, empty search state, map coordinates, and API connection failure. The frontend strict TypeScript/Vite build passed. `npm ci --offline` restored lockfile dependencies; `npm audit --offline` reported 0 vulnerabilities using cached advisory data.

The model artifacts were serialized using scikit-learn 1.5.0. With the matching Python 3.12 installation, K-Means predictions and DBSCAN saved fit labels matched saved assignments for 3,934 active routes. The project virtual environment currently has scikit-learn 1.9.1 and fails K-Means prediction with these artifacts; package installation could not align it because PyPI access is blocked. `backend/pyproject.toml` pins 1.5.0 and NumPy below 2.0 for compatible installs. A deterministic actual-feature clustering run with seed 42 completed in a temporary output directory: K-Means selected 6 clusters (silhouette 0.3854); DBSCAN selected 4 clusters with 36 noise routes (silhouette 0.3891). It did not replace saved Phase 4 outputs. The four skipped in-process API tests require the declared HTTPX development extra. The cached npm audit result is not a substitute for a fresh online advisory check. Before deployment, install the pinned backend dependencies and HTTPX, rerun tests and a connected dependency audit, configure production CORS and URLs, and deploy only behind the intended HTTPS and process-management infrastructure.
