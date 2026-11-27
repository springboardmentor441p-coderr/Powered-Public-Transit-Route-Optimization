# Frontend: `frontend/main.py`

The whole Streamlit dashboard is in **one file**, `main.py`:

* **Shared UI helpers:** theme/CSS, cached backend service, live **IST clock**, IST date/time picker
  (converted to the bus network's New York time), scoring-weight picker, route map.
* **11 pages**, one function each:

| Group | Page function | Page |
|---|---|---|
| Overview | `page_network_overview` | Network Overview |
| Overview | `page_best_route` | Best Route Today (Live): best route, why, validation |
| Analysis | `page_productivity_ranking` | Productivity Ranking |
| Analysis | `page_route_comparison` | Route Comparison |
| Analysis | `page_historical_replay` | Historical Replay |
| Analysis | `page_eda_insights` | EDA Insights |
| Optimisation | `page_scenario_simulator` | Scenario Simulator |
| Optimisation | `page_recommendations` | Optimisation Actions |
| Models & Data | `page_model_performance` | Model Performance |
| Models & Data | `page_data_coverage` | Data & Coverage (+ GTFS upload analyser) |
| Models & Data | `page_pipeline_architecture` | Pipeline & Architecture |

* **Entry point:** `run_app()` builds the grouped navigation.

The pages call the backend service layer in `backend/main.py` and read EDA outputs from `eda/`.

## Run (from the project root, after `python backend/main.py train` and `python eda/main.py`)

```bash
streamlit run frontend/main.py      # http://localhost:8501
```
