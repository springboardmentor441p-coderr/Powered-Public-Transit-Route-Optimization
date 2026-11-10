# RouteRanker GTFS ingestion

This backend slice ingests the supplied GTFS ZIP, validates all supported GTFS
tables, and writes source-preserving Parquet tables plus JSON and Markdown data
quality reports. It does not infer route geometry or service exceptions, and it
does not create passenger, traffic, demand, or live vehicle data.

## Windows setup and run

Use Python 3.10 or newer. From the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .\backend
```

Run preprocessing from the project root:

```powershell
$env:PYTHONPATH = "backend\src"
python -m routeranker.ingestion.pipeline --archive data/raw/mtc-gtfs.zip --output data/processed/gtfs
```

Run unit tests:

```powershell
python -m unittest discover -s backend/tests -v
```

The pipeline does not overwrite the ZIP. Generated output defaults to
`data/processed/gtfs/`; rerunning updates generated Parquet and report files in
that output directory. Each Parquet table retains input columns as strings and
adds typed numeric convenience columns such as `stop_lat_value`,
`stop_sequence_value`, and schedule `*_seconds`. Calendar exceptions are
preserved when supplied. If `calendar_dates.txt` is absent, a schema-correct
empty Parquet table is emitted and the report records its absence.

The report treats structural/schema/relationship errors as a failed status,
and keeps quality warnings (blank fields, duplicates, unused records) visible
without dropping affected data. GTFS after-midnight times such as `25:10:00`
are retained and converted to seconds after the service-day start.

## Phase 2: exploratory data analysis

After Phase 1 has generated the Parquet tables, run the EDA from the project
root:

```powershell
$env:PYTHONPATH = "backend\src"
python -m routeranker.analysis.eda --input data/processed/gtfs --output data/processed/eda
```

The EDA reads the processed tables, lazily scans `stop_times.parquet`, and
writes route/stop summaries, weekday calendar counts, scheduled trip starts by
service hour, route/service/direction headway estimates, distinct route-stop
coverage, all shared route pairs with Jaccard similarity, three PNG charts,
and JSON/Markdown reports to `data/processed/eda/`.
Route coverage percentages use the count of distinct stops referenced by trips
as their denominator; they are stop-network coverage measures, not geographic
area coverage.

Headways are differences between consecutive scheduled first-stop departures
within a route, calendar service, and direction. Weekday counts apply the
calendar flags to trip templates. Since `calendar_dates.txt` and
`frequencies.txt` are absent, date exceptions and frequency-based service are
not included. All figures describe the timetable; they do not measure
passenger demand, actual service regularity, traffic, or occupancy.

## Phase 3: feature engineering

Run feature generation after Phase 1 and Phase 2:

```powershell
$env:PYTHONPATH = "backend\src"
python -m routeranker.features.engineering --archive data/raw/mtc-gtfs.zip --gtfs data/processed/gtfs --eda data/processed/eda --output data/processed/features
```

This writes raw and normalized route, stop, and route-pair feature tables in
both CSV and Parquet, plus a feature dictionary, normalization parameters, and
source-validation reports to `data/processed/features/`. The route peak
windows are 07:00-10:00 and 16:00-19:00 (first-stop departure time); they are
explicit analytical windows rather than official MTC peak classifications.
Peak/off-peak figures apply `calendar.txt` weekday flags to trip templates.

Normalized numeric features use median imputation followed by z-score scaling
with scikit-learn `StandardScaler`, fitted separately at route, stop, and
route-pair levels. Raw feature tables keep missing headways/spans as null and
retain unused routes/stops with zero counts. Normalization parameters are
saved in `normalization_parameters.json`.

## Phase 4: scheduled route clustering

Run K-Means and DBSCAN after Phase 3:

```powershell
$env:PYTHONPATH = "backend\src"
python -m routeranker.clustering.route_clusters --features data/processed/features --output data/processed/clustering --seed 42
```

The module validates the Phase 3 reports and raw/normalized route feature
alignment, profiles feature distributions and missingness, then fits its own
median imputer and z-score scaler on routes with scheduled trip records only.
It uses log1p for trip/stop/headway/span magnitudes, peak departure share,
shared-stop ratio, and varying missingness indicators. The Phase 3 normalized
table is inspected but not used for fitting because its scaler includes routes
with no scheduled trip records. Routes without trip records remain in
prediction tables with an explicit excluded status; missing headways stay
marked by an indicator after median imputation.

K-Means evaluates k=2..10 and selects the highest sampled silhouette. DBSCAN
tries radii based on nearest-neighbor distance quantiles, requiring at least
two non-noise clusters, a valid silhouette, and 10% inliers where possible.
Metrics, models, predictions, original-scale profiles, quality summaries, PCA
coordinates/chart, and a detailed report are written to
`data/processed/clustering/`. A fixed seed makes stochastic steps reproducible
for unchanged inputs and package versions. DBSCAN must be refit to cluster a
changed route population.

Clusters summarize schedule and stop-network similarities only. They are not
passenger-demand predictions, actual operating performance, or judgments of
route quality. Silhouette and Davies-Bouldin scores are internal diagnostics
without ground-truth labels. `calendar_dates.txt`, `frequencies.txt`, and
`shapes.txt` are absent, limiting exception-date, frequency-based, and
geometry-aware analysis.

Run all phase tests with:

```powershell
python -m unittest discover -s backend/tests -v
```

## Phase 5: FastAPI backend

### Install and start on Windows

From the project root, install the backend and its API dependencies:

```powershell
python -m pip install -e .\backend
python -m pip install -e ".\backend[dev]"
$env:PYTHONPATH = "backend\src"
python -m uvicorn routeranker.api.app:app --host 127.0.0.1 --port 8000
```

The first install line installs runtime dependencies; the second adds HTTPX for
the API test client. Alternatively, from the `backend` directory use
`python -m pip install -e ".[dev]"`. The server reads the existing processed
outputs from `data/processed/`; it does not launch preprocessing or retrain
models. Override the root with `ROUTERANKER_PROCESSED_DIR`. CORS allows only
`http://localhost:5173` and `http://127.0.0.1:5173` by default. Set
`ROUTERANKER_CORS_ORIGINS` to an explicit comma-separated list of local origins
when needed. API docs: `http://127.0.0.1:8000/docs`; ReDoc:
`http://127.0.0.1:8000/redoc`.

All endpoints are read-only and use the `/api/v1` prefix. Collection endpoints
support bounded `limit`/`offset` pagination. Missing phase outputs return HTTP
503 with `{"detail":"...","code":"dataset_unavailable"}`; unknown route or
stop IDs return 404. Query validation failures return 422. Example requests:

```text
GET /api/v1/routes?limit=25&offset=0&min_trips=10&max_headway_seconds=3600
GET /api/v1/routes/ROUTE_ID
GET /api/v1/routes/ROUTE_ID/features
GET /api/v1/routes/ROUTE_ID/clusters
GET /api/v1/routes/compare?route_ids=ROUTE_A&route_ids=ROUTE_B
GET /api/v1/stops?limit=50&min_routes=2
GET /api/v1/stops/STOP_ID
GET /api/v1/stops/STOP_ID/routes
GET /api/v1/stops/route-counts?limit=100
GET /api/v1/analytics/statistics
GET /api/v1/analytics/routes/statistics
GET /api/v1/analytics/stops/statistics
GET /api/v1/analytics/scheduled-trips/by-hour
GET /api/v1/analytics/headways?route_id=ROUTE_ID
GET /api/v1/analytics/route-similarity?route_id=ROUTE_ID&limit=20
GET /api/v1/analytics/clusters
GET /api/v1/ml/models
GET /api/v1/ml/assignments/ROUTE_ID
GET /api/v1/ml/clusters
GET /api/v1/ml/metrics
GET /health
```

For example, a paginated route collection has this shape (values below are
illustrative schema only; query the API for actual feed values):

```json
{"items":[{"route_id":"...","trip_count":null,"kmeans_cluster_id":null}],"total":0,"limit":25,"offset":0}
```

Other response shapes (field values are examples, not dataset statistics):

```text
GET /api/v1/routes/{route_id}
{"route_id":"<GTFS route_id>","route_short_name":"...","trip_count":null,"stop_count":null}

GET /api/v1/routes/{route_id}/features
{"route_id":"<GTFS route_id>","total_scheduled_trip_records":null,"average_first_stop_headway_seconds":null,"headway_missing":null}

GET /api/v1/routes/{route_id}/clusters
{"route_id":"<GTFS route_id>","kmeans_cluster_id":null,"dbscan_cluster_id":null,"fit_status":"clustered"}

GET /api/v1/routes/compare?route_ids={id_a}&route_ids={id_b}
{"routes":[{"route_id":"<GTFS route_id>"}],"compared_route_ids":["<id_a>","<id_b>"],"note":"..."}

GET /api/v1/stops/{stop_id}
{"stop_id":"<GTFS stop_id>","stop_name":"...","route_count":null,"trip_count":null}

GET /api/v1/stops/{stop_id}/routes
[{"route_id":"<GTFS route_id>","route_short_name":"...","route_long_name":"..."}]

GET /api/v1/analytics/statistics
{"gtfs_quality_status":"...","dataset_totals":{},"limitations":{},"interpretation":"Scheduled GTFS only."}

GET /api/v1/analytics/headways
{"groups_with_estimates":0,"groups_without_estimates":0,"median_of_group_medians_seconds":null,"note":"..."}

GET /api/v1/analytics/route-similarity
[{"route_id_a":"<GTFS route_id>","route_id_b":"<GTFS route_id>","shared_stop_count":0,"jaccard_similarity":0.0}]

GET /api/v1/ml/metrics
[{"algorithm":"KMeans","n_clusters":0,"silhouette_score":null,"noise_count":0,"inlier_count":0}]
```

`/api/v1/routes` filters are `q`, `min_trips`, `max_trips`, `min_stops`,
`min_headway_seconds`, `max_headway_seconds`, `algorithm` (`kmeans` or
`dbscan`), and `cluster_id`. Headway filters use Phase 3's route-level average
scheduled first-stop headway. `/api/v1/stops` supports `q` and `min_routes`.

Route and stop values come from Phase 1 GTFS tables and Phase 2 summaries;
route/stop analytical features and overlap values come from Phase 3; saved
cluster assignments, profiles, model files, and diagnostics come from Phase 4.
The API reads compact summaries and route-stop coverage rather than loading the
1.36-million-row stop-times table for endpoint requests. Process-level caching
avoids rereading the same artifact; restart the server after regenerating
processed outputs. The endpoint `/api/v1/ml/models` reads the saved joblib
artifacts once and returns their fit metadata. It does not retrain. Saved
assignments are returned as-is; DBSCAN cannot predict labels for unseen routes
and must be refit to changed data. K-Means metadata identifies its fitted
feature set, but the API does not offer a new-route prediction endpoint.

All schedule frequency/headway values describe the supplied GTFS timetable,
not passenger demand, actual waiting times, or delivered operations. The feed
does not provide `calendar_dates.txt`, `frequencies.txt`, or `shapes.txt`; these
limitations are exposed in overall statistics and remain applicable to API
responses.

## Current feed limitations

The generated Phase 4 joblib models were serialized with scikit-learn 1.5.0;
`backend/pyproject.toml` pins that exact runtime and limits NumPy to 1.x for
compatibility. Reinstall dependencies from the project file rather than
upgrading either library independently, since scikit-learn pickle compatibility
across versions is not guaranteed.

See `PROJECT_PLAN.md` for the initial archive inventory. `shapes.txt` and
`calendar_dates.txt` are absent from the supplied feed. The pipeline reports
those missing optional tables and does not invent geometries or exceptions.

## Phase 7 validation and runtime compatibility

The backend dev extra is `httpx>=0.27,<1.0`; install it with
`python -m pip install -e ".\backend[dev]"` from the project root. The current
workspace run had HTTPX absent, so four `TestClient` tests were skipped. Five
opt-in live HTTP integration tests passed against the actual processed feed.
In this environment, PyPI access was blocked and the dev extra could not be
installed; do not treat the skipped tests as passes.

The Phase 4 joblib artifacts were serialized with scikit-learn 1.5.0, which is
pinned in `pyproject.toml`. The active `.venv` contains 1.9.1: loading emits
`InconsistentVersionWarning`, and a real K-Means prediction fails because the
unpickled `SimpleImputer` lacks `_fill_dtype`. With Python 3.12/scikit-learn
1.5.0, model loading and inference were verified against the processed route
features: K-Means predictions and DBSCAN fitted labels each matched saved
assignments for 3,934 active routes. A separate deterministic end-to-end
clustering run with seed 42 also completed in a temporary output directory.
Recreate/install the backend environment from this package metadata before
deployment; do not load these artifacts under the mismatched runtime.

