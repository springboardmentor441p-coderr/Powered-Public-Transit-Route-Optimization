# Planning application

The primary application uses React, TypeScript and Vite with FastAPI and PostgreSQL. The selected study is New York. Executed analysis notebooks and the earlier Streamlit interface remain available.

## Local development

Install requirements-api.txt and the analysis requirements. Start PostgreSQL and set DATABASE_URL. Run python -m backend.import_data, then python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000. In frontend, run npm ci and npm run dev. Open http://127.0.0.1:5173. API documentation is available at http://127.0.0.1:8000/docs.

## Forecast experiment

scripts/daily_replay_experiment.py fits pooled Ridge and Random Forest pipelines and compares two seasonal baselines on identical rows. Training ends March 31, validation ends May 17 and testing covers Juneâ€“July 2026. The reporting policy releases observations after 14 complete intervening days. Lags 1, 7 and 14 remain unavailable. Seasonal features use exact 21, 28, 35 and 42-day lags, requiring at least two observations.

The validation-selected Random Forest achieved test MAE 501.37 versus seasonal_mean4 MAE 514.03 over 2,501 common observations. This is a retrospective reconstruction, with simulated historical cutoffs. A paired schedule-feature experiment is saved in notebook 13. On 2,281 common test rows, service-aware Random Forest MAE was 644.21 versus 649.98 for demand-only Random Forest and 524.77 for the seasonal mean. The shorter schedule-covered training population differs from the original demand experiment. This result does not justify model promotion. Operational acceptance has not been established.

See API_CONTRACT.md for endpoints and application semantics. End-to-end verification remains the completion gate for the new application.


## Planning workspace

The React workspace links version-labelled route maps to route selection, daily demand charts, route comparisons, readable forecast evidence and saved baseline/proposed scenario tables. Teal identifies the selected route and orange the comparison route. Street tiles use OpenStreetMap and require internet; route lines come from the local API. Geometry is snapshot context, not live vehicle position. Replay withholds geometry and profiles that were unavailable at its virtual date.

## Packaged application

The primary Dockerfile builds React and serves the built interface from FastAPI on port8000. compose.yaml starts PostgreSQL and imports the verified analysis bundle before starting the API. Set POSTGRES_PASSWORD in the environment, then run docker compose up --build. Existing processed source/model artifacts must be present; this does not download datasets automatically. The data/processed bind mount also holds immutable copied model bundles. PostgreSQL uses a persistent named volume.

The earlier Streamlit configuration is retained as Dockerfile.streamlit and compose.streamlit.yaml. Docker execution requires a runtime; configuration generation alone does not verify a container deployment.
