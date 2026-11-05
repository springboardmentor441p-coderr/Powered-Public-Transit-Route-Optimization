# Demo guide (10 minutes)
1. **The problem** (1 min): real GTFS has schedules, no passengers; show `real_data/SOURCES.md`.
2. **The notebook** (4 min): open `notebooks/RouteRanker_ML_Model.ipynb`: data -> features -> baselines -> per-city learning (held-out routes) -> learning curve -> honest unseen-city limit -> peer comparison.
3. **The saved model** (1 min): `models/service_model.joblib`, `model_card.json`; run `python -m src.learn predict --gtfs real_data\Pune_PMPML_gtfs.zip --name Pune`.
4. **The website** (3 min): `uvicorn server.main:app --port 8000` -> tab *Learned model*: metrics, learning curve, peer explorer (Pune, "under-served"), upload a feed in "Analyse your own feed".
5. **Learning from new data** (1 min): `python -m src.learn add --gtfs <new zip> --name <City>`; show `models/registry.json` promote/reject reason.
6. Close with the limitations slide (`docs/KNOWN_LIMITATIONS.md`).
