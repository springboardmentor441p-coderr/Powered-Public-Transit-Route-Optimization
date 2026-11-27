# Backend: `backend/main.py`

All server-side code is in **one file**, `main.py`, split into numbered sections:

| § | Section | Key functions / classes |
|---|---|---|
| 1 | Configuration | paths, `SOURCES`, IST / New York time zones, capacities, thresholds, `ScoreWeights` |
| 2 | Data collection | `soql_fetch`, `collect_hourly_ridership`, `collect_schedules`, `collect_segment_speeds`, `collect_all` |
| 3 | Data cleaning | `clean_ridership`, `clean_schedule`, `clean_speeds`, `clean_wait`, `clean_evasion`, `clean_routes` |
| 4 | Feature engineering | `add_time_features`, `attach_service_features`, `add_performance_metrics`, `build_route_profiles` |
| 5 | Preprocessing | `time_split`, `ProfileEncoder`, `model_matrix`, `scale_for_clustering` |
| 6 | Clustering | `select_k`, `dbscan_eps`, `run_clustering` (KMeans + DBSCAN), `stop_overlap` |
| 7 | Classification & forecasting | `train_classifiers` (RF vs XGBoost), `train_forecasters` (RF vs XGBoost vs baseline) |
| 8 | Optimisation | `optimize_frequencies`, `route_recommendations`, `impact_summary`, `simulate_scenario` |
| 9 | Inference | `RouteRankerService`: `predict_day`, `rank_routes`, `explain`, `validate`, `find_routes_between` |
| 10 | GTFS analyser | `read_gtfs`, `route_profiles_from_gtfs`, `analyse_gtfs` |
| 11 | Diagrams | `architecture_diagram`, `pipeline_diagram`, `model_figures` |
| 12 | Training pipeline | `run_pipeline` |
| 13 | REST API (FastAPI) | `/api/health`, `/api/routes`, `/api/predict`, `/api/best-route`, `/api/ranking`, `/api/recommendations`, `/api/simulate` |
| 14 | CLI | `main()` |

## Run (from the project root)

```bash
python backend/main.py collect          # download / refresh MTA open data
python backend/main.py train            # clean -> features -> models -> artefacts (~15 min)
python backend/main.py serve            # REST API -> http://localhost:8000/docs
# or: uvicorn backend.main:app --port 8000
```

Outputs: `data/processed/*.parquet`, `models/*.joblib`, `reports/metrics/*.json`, `reports/figures/*.png`.
