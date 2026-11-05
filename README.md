<<<<<<< HEAD
# 🚌 RouteRanker – AI-powered public transit route optimisation (React + FastAPI)

Finds **overcrowded / under-used bus routes** in Indian cities, **forecasts the next 12 months of demand from past ridership**, and recommends
**more/fewer buses, merges and splits** with a before/after simulation, in a React website anyone can use.

```
React (Vite, Recharts, Leaflet)  ⇄  FastAPI (server/main.py)  ⇄  Python ML pipeline (src/)
```

## Run it
```bash
./start.sh            # Windows: start.bat   → open http://localhost:8000
```
The first start trains the models if needed (~1 min). `frontend/dist` (the built site) is included, so Node is **not** required to run it.

**Development (hot reload):**
```bash
uvicorn server.main:app --port 8000        # terminal 1: API
cd frontend && npm install && npm run dev  # terminal 2: http://localhost:5173 (proxies /api)
```
**Tests:** `pytest tests -q` (pipeline, forecasting, API) and, with the API running, `cd frontend && npm test` (renders every tab against live data).

## Put it online (one public link)
Docker is the simplest path; the image builds the React app and serves everything from one port.
* **Render / Railway / Fly.io:** connect the repo; Render reads `render.yaml`.
* **Hugging Face Spaces:** create a *Docker* Space, upload the folder, set `app_port: 8000` in the Space README.
* **Any VPS / cloud VM:** `docker build -t routeranker . && docker run -p 8000:8000 routeranker`
(Pre-trained `outputs/` + `models/` are in the repo, so the server is ready immediately.)

## What the website offers
Overview · Explore (hourly curves, city×hour heat-map, stop map, merge candidates) · Clusters (KMeans/DBSCAN) · Predictions (RF vs XGBoost, confusion matrix, importances) ·
**Forecast** (past → next 12 months, honest backtest, 80 % ranges, routes that will become overcrowded) · Recommendations (filter, CSV download, hourly plan + map per route) ·
Impact (current vs optimised) · **Your data** (upload a GTFS zip [+ passenger counts, + past monthly ridership] or generate a synthetic city).
Top bar: switch *Today / Next 12 months / Busiest month*; every recommendation is recomputed for that demand. Left panel: city filter and service settings.

## API (JSON; interactive docs at /docs)
`GET /api/meta · overview · eda?city= · clusters · predictions · forecast?city=&route= · recommendations · route?uid= · impact · download/recommendations.csv`
(all accept `dataset, scenario=today|avg|peak, capacity, target_lf, min_tph, max_tph, merge_overlap, split_km, cities=A,B`) · `POST /api/upload` · `POST /api/generate`.

## Data & honesty notes
* The Lepton GTFS feed is licensed, so `data/generate_synthetic_gtfs.py` builds feeds with the identical layout for the same 23 cities (512 routes, ~100k trips) plus ridership and 45 months of history. Put real feeds in `data/gtfs/<City>/` and run `python train.py` to use them.
* Without passenger counts GTFS cannot tell who rides, so demand is **estimated** from stop locations (the site says so). Provide `ridership.csv` (`route_id, day_type, hour, boardings`) and `ridership_history.csv` (`route_id, month, boardings`) for real conclusions.
* Forecast backtest (train on first 33 months, predict next 12): **WAPE 4.0 %** vs 4.8 % (best simple baseline) and 6.3 % (last 3 months). Route-status classifier on unseen cities: ~65 % accuracy (chance 33 %).
* Simulation assumes fixed demand, one bus size, no depot constraints. Decision support, not an automatic timetable.

## Layout
```
frontend/   React app (src/tabs/*, src/store.jsx, src/ui.jsx, tests/)      server/main.py   FastAPI
src/        data_loader · cleaning · features · eda · preprocessing · models · forecast · optimizer · pipeline
train.py    full pipeline → outputs/ + models/       app.py   legacy Streamlit dashboard (optional)
docs/REPORT.md   technical report                    tests/   pytest suite
```
=======
# 🚌 RouteRanker – a machine-learning model that learns from real transit data

RouteRanker **learns from real GTFS bus feeds** (Pune PMPML, Chennai MTC, Bengaluru BMTC – included, with sources), saves the trained model as a file,
shows every step in a **Jupyter notebook**, serves it through a **React website + FastAPI**, and can **learn again when you add a new city**.

## What the model learns (read this first)
Real feeds contain schedules, **not passenger counts**. So the model learns how each operator **allocates service**: trips per route-hour from route length,
stops, connectivity, position in the city, overlap and hour of day. Routes that get far fewer/more trips than comparable routes are flagged
*relatively under-/over-served versus peers*. It is a **screening signal**; it does not prove crowding. See `docs/ML_MODEL.md`.

| Measured on real data (routes the model never saw) | Baseline (hour average) | Learned model |
|---|---|---|
| Bengaluru, error in trips per route-hour | 1.59 | **1.06** |
| Chennai | 1.25 | **0.84** |
| Pune | 2.15 | **1.58** |
Honest limit: on a *completely unseen city* the pooled model transfers weakly (Pune is worse than baseline), so RouteRanker learns **from the feed you give it** (needs >= 200 routes) and says so.

## Files you get
| What | Where |
|---|---|
| Trained model (file) | `models/service_model.joblib`, `models/model_card.json` (metrics, features), `models/registry.json` (versions) |
| Notebook with all steps and outputs | `notebooks/RouteRanker_ML_Model.ipynb` |
| Real data + sources + checksums | `real_data/` (`SOURCES.md`, `SHA256SUMS.txt`); re-download with `scripts/fetch_real_data.py` |
| Learning code | `src/learning.py`, `src/learn.py`, `src/gtfs_validation.py`, `src/cleaning.py`, `src/features.py` |
| Website | `frontend/` (React) + `server/` (FastAPI) |

## Windows PowerShell (VS Code terminal)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 1) (optional) re-learn from the real feeds: build corpus, then train (about 6 minutes)
python -m src.learn corpus --gtfs real_data\Pune_PMPML_gtfs.zip --name Pune
python -m src.learn corpus --gtfs real_data\Chennai_MTC_gtfs.zip --name Chennai
python -m src.learn corpus --gtfs real_data\Bengaluru_BMTC_gtfs.zip --name Bengaluru
python -m src.learn train

# 2) apply the saved model to any GTFS zip
python -m src.learn predict --gtfs real_data\Pune_PMPML_gtfs.zip --name Pune --out peer_gap.csv

# 3) teach it a NEW city (retrains, champion/challenger decides whether to promote)
python -m src.learn add --gtfs C:\path\to\new_city_gtfs.zip --name Hyderabad

# 4) notebook
jupyter notebook notebooks\RouteRanker_ML_Model.ipynb

# 5) website (built site is included; Node is only needed to rebuild it)
uvicorn server.main:app --port 8000        # open http://localhost:8000  -> tab "Learned model"
$env:RR_ADMIN_TOKEN = "choose-a-secret"    # optional: enables "teach the model" in the website
```
Frontend development: `cd frontend; npm install; npm run dev` (API on port 8000). Tests: `python -m pytest tests -q` and, with the API running, `cd frontend; npm test`.

## Website tabs
**Learned model** (what was learned, metrics vs baselines, learning curve, peer comparison, analyse your own feed, teach the model, version history) plus the earlier tabs
(Overview, Explore, Clusters, Predictions, Forecast, Recommendations, Impact, Your data). **Note:** those earlier tabs run on *synthetic demonstration data*
(the demo dataset) and use a rule-labelled classifier and a demand proxy; do not read them as findings about real cities. Real-city results are in the Learned-model tab.

## Put it online
`docker build -t routeranker . && docker run -p 8000:8000 routeranker` (Render, Railway, Fly.io, Hugging Face Docker Space). Set `RR_CORS_ORIGINS`,
`RR_MAX_UPLOAD_MB` and (only if you want public learning, which is not recommended) `RR_ADMIN_TOKEN`. There is no user authentication.

## Security notes
Uploads are size-capped, must be ZIPs, are read in memory with zip-slip / archive-bomb / member-count limits, stored privately (`data/uploads/`, never served), and errors never expose paths or tracebacks.
Learning from uploaded data is disabled unless an admin token is set (otherwise visitors could poison the model).
>>>>>>> 8eff1e4 (Fix import paths and resolve directory structure issues)
