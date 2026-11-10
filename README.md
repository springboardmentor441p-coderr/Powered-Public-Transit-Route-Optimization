# RouteRanker

RouteRanker is a modular analysis application for Chennai Metropolitan Transport Corporation (MTC) GTFS schedule data. It provides data validation and preprocessing, descriptive service analysis, route and stop features, unsupervised route clusters, a read-only FastAPI API, and a React analytics interface.

All service measures describe the supplied timetable. The feed does not contain passenger ridership, demand, occupancy, traffic, live vehicle positions, or actual travel times. Clusters summarize schedule-derived characteristics; they do not predict demand or judge route quality.

## Technology

- Data processing and analysis: Python, Pandas, NumPy, DuckDB, scikit-learn, PyArrow/Parquet
- API: FastAPI, Pydantic, Polars, Uvicorn
- Frontend: React, TypeScript, Vite, Tailwind CSS, Axios, React Router, Recharts, Leaflet, OpenStreetMap
- Tests: Python `unittest`, TypeScript/Vite production build, browser workflow smoke tests (Chrome or Edge)

## Architecture

```text
data/raw/mtc-gtfs.zip                 Original input feed (preserved)
data/processed/gtfs/                  Phase 1 validated typed GTFS tables
data/processed/eda/                   Phase 2 summaries, charts, reports
data/processed/features/              Phase 3 raw and normalized features
data/processed/clustering/            Phase 4 saved clusters, profiles, metrics
backend/src/routeranker/              Ingestion, analysis, features, ML, API modules
backend/tests/                        Unit and API integration tests
frontend/src/services/                Typed API client and response caching
frontend/src/pages/                   Overview, routes, stops, map, insights, comparison
frontend/scripts/e2e-smoke.mjs        Local browser workflow smoke test
```

The API reads the generated artifacts; it does not ingest the archive or retrain clustering models on requests. The frontend consumes the API and does not embed data fixtures.

## Dataset and limitations

The supplied archive is from [ChennaiGTFS](https://github.com/ungalsoththu/ChennaiGTFS). It contains scheduled GTFS data. `calendar_dates.txt`, `frequencies.txt`, and `shapes.txt` are unavailable in this feed. Accordingly, exception-date and frequency-based service are not represented, and the map shows only supplied stop coordinates. It does not draw or imply bus route geometry. See `data/processed/gtfs/data_quality_report.md` and the phase reports for feed-specific findings.

Do not interpret scheduled trips or estimated headways as actual delivered operations, passenger demand, or passenger waiting times. Route clusters are descriptive unsupervised groups, not efficiency or overcrowding classifications.

## Requirements

- Windows PowerShell instructions below; Python 3.12 is the verified runtime (Python 3.10+ is specified by backend packaging)
- Node.js 20.19+ and npm (the Vite 8 toolchain requires a current Node release)
- Phase 1–4 processed outputs in `data/processed/` for the API
- Chrome or Edge only for the optional browser workflow tests

## Backend setup and startup

From the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".\backend[dev]"
$env:PYTHONPATH = "backend\src"
python -m uvicorn routeranker.api.app:app --host 127.0.0.1 --port 8000
```

The default API URL is `http://127.0.0.1:8000`; Swagger UI is at `http://127.0.0.1:8000/docs`. `ROUTERANKER_PROCESSED_DIR` optionally points to another processed-artifact root. `ROUTERANKER_CORS_ORIGINS` is a comma-separated list of exact browser origins. By default, only `http://localhost:5173` and `http://127.0.0.1:5173` are allowed. The API is read-only.

For local deployment preparation, copy `backend/.env.example` only if using a dotenv loader of your choice; Uvicorn itself does not load `.env` automatically. Configure the variables in the process environment or service manager. Do not put secrets in frontend variables; Vite variables are public in browser bundles.

## Frontend setup and startup

In a second PowerShell window:

```powershell
Set-Location frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open `http://127.0.0.1:5173`. Set `VITE_API_BASE_URL` in `frontend/.env.local` if the API uses a different address; include the `/api/v1` suffix. For production builds, set this value before building or use `frontend/.env.production` based on `frontend/.env.production.example`.

## Testing and verification

Run backend unit and API client tests from the project root with the activated environment:

```powershell
$env:PYTHONPATH = "backend\src"
python -m unittest discover -s backend/tests -v
```

The live integration tests are opt-in and exercise the running API over HTTP:

```powershell
$env:ROUTERANKER_TEST_API_BASE_URL = "http://127.0.0.1:8000"
python -m unittest backend.tests.test_live_api_integration -v
```

Run frontend strict TypeScript compilation and production bundle:

```powershell
Set-Location frontend
npm ci
npm run build
```

The browser workflow test starts a temporary Vite server and Chrome/Edge; start the API first:

```powershell
npm run test:e2e
```

The test uses `VITE_API_BASE_URL` (default `http://127.0.0.1:8000/api/v1`). Set `CHROME_PATH` if the browser is installed in a nonstandard location. It exercises overview, route search/details/comparison, stop membership, model insights, stop mapping and an API failure state. It is a smoke test, not exhaustive cross-browser or accessibility coverage.

## Production build and restart

The backend pins scikit-learn to `1.5.0` and NumPy below `2.0` for the saved
Phase 4 joblib pipelines. Keep these versions aligned when installing or
rebuilding the backend environment; scikit-learn does not guarantee
cross-version pickle compatibility.

Build the static frontend after setting its API URL:

```powershell
Set-Location frontend
$env:VITE_API_BASE_URL = "https://api.example.com/api/v1"
npm ci
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

`frontend/dist/` is the generated static site. The preview server is for local verification, not a hardened production web server. Host the static files behind a TLS-enabled static host or reverse proxy, configure the API's `ROUTERANKER_CORS_ORIGINS` to the exact frontend origin, and expose Uvicorn behind a production ASGI process manager/reverse proxy. Keep both services private until infrastructure, TLS, monitoring, backups, and access policy are configured. For a rebuild/restart, install locked dependencies (`npm ci`), rebuild, replace the static `dist` artifact, and restart the backend process after changing server code or processed data.

Deployment options include an internal Windows server with IIS/reverse proxy, an organization-approved VM/container platform, or separate static hosting and managed backend hosting. Each requires a supported Python/Node build environment, access to the processed Parquet/model artifacts, explicit CORS, HTTPS, and a process/service restart strategy. No container image or cloud provider configuration is included, and this project has not been publicly deployed.

## Phase 7 local validation status

- Frontend: `npm ci --offline` succeeded from the lockfile/cache, TypeScript and Vite production build passed, and eight Chrome browser workflows passed against the local API. `npm audit --offline` reported zero vulnerabilities from cached advisory data; run a connected audit before release.
- Backend: 23 tests ran with 19 passing and four in-process API tests skipped because HTTPX is absent. The declared development extra includes HTTPX. Five live HTTP integration tests passed when the local API was started.
- Models: the saved Phase 4 artifacts use scikit-learn 1.5.0. On matching Python 3.12/scikit-learn 1.5.0, K-Means inference and DBSCAN saved labels matched all 3,934 active routes. A deterministic run of both clustering workflows on actual processed features completed (K-Means: 6 clusters; DBSCAN: 4 clusters, 36 noise rows). The active `.venv` has scikit-learn 1.9.1; K-Means prediction fails with an `AttributeError` after an incompatibility warning. `backend/pyproject.toml` pins 1.5.0, but network restrictions prevented installing that pin into `.venv`.

The project builds and local frontend/backend integration is verified. It is **not ready for production deployment** until the active backend environment is recreated/installed with the pinned scikit-learn version, HTTPX is installed and the four skipped tests pass, and a fresh online dependency audit and deployment-specific HTTPS/CORS/process configuration are completed. No public deployment has been performed.

## Known limitations

- Missing `calendar_dates.txt`, `frequencies.txt`, and `shapes.txt` limit service exception, frequency-based, and route geometry analysis.
- Schedule-derived values cannot establish actual service delivery, demand, congestion, travel time, or vehicle locations.
- K-Means and DBSCAN are fitted to this GTFS-derived route population. DBSCAN does not assign unseen routes without refitting; clustering quality metrics have no ground-truth labels.
- OpenStreetMap tile display depends on network access and tile service availability.
- Processed Parquet and model artifacts are local generated outputs and are ignored by Git; regenerate them from the preserved source archive using the documented backend phase commands if absent.
- Security review and local integration tests do not replace a formal penetration test, operational monitoring, or deployment-specific review.
