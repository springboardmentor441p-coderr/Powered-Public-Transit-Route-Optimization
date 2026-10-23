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
