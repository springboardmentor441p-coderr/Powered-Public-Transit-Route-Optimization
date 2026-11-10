# RouteRanker

RouteRanker is a Chennai Metropolitan Transport Corporation (MTC) transit analytics application. It presents schedule-derived GTFS analysis and deterministic timetable scenario estimates. It does not model or report passenger demand, ridership, occupancy, congestion, live vehicle locations, or observed real-world travel times.

## Architecture

- `frontend/` is a React 19, TypeScript, Vite application styled with Tailwind CSS. React Router connects the dashboard pages; Axios calls the API through Vite's `/api` development proxy. Recharts powers analytical charts and React Leaflet displays GTFS stop locations and approximate stop sequences. Lucide React provides interface icons.
- `backend/app/` is the FastAPI application, with API routers, Pydantic response/request schemas, and service-layer business logic.
- `backend/data_processing/` loads and validates the GTFS feed, normalizes extended GTFS times, creates processed analytical tables, and engineers schedule-derived route features.
- `backend/ml/` holds unsupervised route clustering, evaluation, and deterministic schedule scenario simulation.
- `data/raw/` holds source GTFS files. `data/processed/` contains the existing analytical artifacts and audit report. `data/models/` contains the existing clustering artifacts. These source data and model artifacts are retained as-is by the frontend work.

The API is served at `http://localhost:8000`; OpenAPI/Swagger documentation is at `http://localhost:8000/api/docs`. The Vite development server proxies API calls to that backend.

## Frontend pages

- **Overview Dashboard**: backend-provided network totals, route rankings, and service/stop distribution charts.
- **Route Explorer**: searchable and paginated route list, route details, ordered stops, an approximate stop-to-stop map, and scheduled departures.
- **Schedule Analytics**: service calendars and paginated route frequency/headway metrics, with local column sorting and the schedule-derived high-frequency filter.
- **Stop Coverage**: coverage summary, filtered map of up to 500 high-coverage stops, and the most connected stops.
- **Route Overlap**: Jaccard similarity threshold, network overlap ranking, and per-route comparison.
- **ML Clustering**: cached/current clustering profiles, evaluation charts, and route assignments; clustering can be run with a selected K.
- **Schedule Optimization**: route selection/search, frequency multiplier and stop-consolidation controls, and baseline-versus-simulated headway, duration, speed, trip, vehicle-hour, and fleet estimates.
- **Data Quality**: backend audit, sanitization events, validation issues, and processed-table status.

Navigation is responsive, and the pages expose loading, API error, and empty-data states where applicable. The route and stop maps use public OpenStreetMap tiles. A network connection is required to fetch those tiles.

## Backend API integration

The frontend pages call the existing `/api` endpoints: `/dashboard/summary`, `/routes`, `/routes/{route_id}`, route stops/trips/schedule, `/coverage/summary`, `/coverage/stops`, `/overlap`, `/analytics/frequency`, `/analytics/service`, `/ml/cluster`, `/ml/clusters`, `/optimization/simulate`, `/data/quality`, and `/data/status`. The API client also exposes health and insights calls for future presentation in the UI.

Vite maps `/api/*` to `http://localhost:8000/api/*` during development. The browser does not call backend services directly through duplicated data-processing code. Route pagination and search, coverage pagination, and overlap threshold values use the parameter names and units accepted by the current FastAPI implementation.

The optimization page submits `route_id`, `frequency_multiplier`, and `stop_consolidation_pct` to the existing deterministic simulator. Its outputs are clearly labeled hypothetical schedule-based estimates; fleet requirements depend on the modeled cycle time and recovery allowance.

## Installation and startup

Prerequisites: Python 3.12+ and Node.js/npm. Python 3.12 is recommended where binary package wheels are unavailable for newer Python releases.

Install backend dependencies:

```powershell
cd "RouteRanker\backend"
python -m pip install -r requirements.txt
```

Start the backend from `RouteRanker/backend`:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On startup, the backend checks processed data and existing model artifacts. It may run preprocessing or train baseline models if the required artifacts are absent; do not remove data or model artifacts unless that regeneration is intended.

Install and start the frontend in a second terminal:

```powershell
cd "RouteRanker\frontend"
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). API docs are available at `http://localhost:8000/api/docs`.

## Testing and validation

From the `RouteRanker` directory:

```powershell
python backend/run_tests.py
```

From `RouteRanker/frontend`:

```powershell
npm run build
npm run lint
npx playwright install chromium
npm run test:e2e
```

The backend suite reports 48 tests. Its preprocessing integration test writes to a temporary directory, leaving `data/processed/` untouched. The frontend build runs TypeScript project checks and Vite production bundling; Oxlint is the configured lint command. Playwright smoke tests require the backend running at `http://localhost:8000`; the test runner starts Vite automatically.

## Known limitations

- GTFS schedules are published timetable data, not evidence that trips ran as scheduled. The dashboard is not a real-time operations or ridership system.
- Stop-to-stop route lines are approximations because the available feed has no GTFS shapes data; they are not road paths.
- The coverage map requests a paginated subset (up to 500 stops per query) to keep rendering responsive.
- The optimization simulator's speed, duration, and peak fleet figures are scenario estimates driven by schedule features and assumptions, not measured operating results or procurement recommendations.
- Data quality endpoint results describe the current processed feed and can change when that feed is updated.
- Map tiles and externally hosted Leaflet marker assets require network access.
- Browser smoke tests cover the eight page routes, route detail search, the optimization submission flow, and mobile navigation. They are integration checks rather than exhaustive visual or component tests.

## Delivery status

Completed: the Vite starter view is replaced by routed dashboard navigation; all eight requested dashboard sections are connected; existing pages use the current backend APIs; simulator and data-quality views are implemented; API parameter mismatches and frontend TypeScript errors were corrected; page modules are lazy-loaded; preprocessing tests use disposable output; Playwright smoke tests cover navigation and core workflows.

Remaining: browser tests cover core integration paths but not exhaustive UI states or screenshot baselines. Maps require network access to tile and marker assets.
