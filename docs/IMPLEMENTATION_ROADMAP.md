# Implementation roadmap
| Phase | Scope | Exit criterion |
|---|---|---|
| 1 | Audit, baseline (done: `PROJECT_AUDIT.md`, `BASELINE_RESULTS.md`) | baseline recorded incl. real-feed failure |
| 2 | `src/gtfs_validation.py`, safe zip, calendar/exceptions/frequencies, row ledger, data modes A/B/C/S, provenance | real feeds validate; mode A has no fabricated demand |
| 3 | Baselines (Dummy/Logistic), forecast MAE/RMSE/WAPE/MASE, cluster stability, characteristic-based cluster descriptions | metrics from executed code |
| 4 | `src/engine.py` candidate engine (gaps, retime, provisional merge, reallocation, review flags) with constraints, objective, rejections; observed-load optimiser keeps coverage/direction checks | constraint checker reports 0 violations; worsened metrics shown |
| 5 | `src/service.py` shared core, FastAPI jobs/exports/provenance, React tabs, Streamlit on same core | both UIs run on same results |
| 6 | Upload limits, CORS, sanitised errors, logging, timings | security tests pass |
| 7 | Tests + `python -m src.benchmark` | all suites run, failures reported |
| 8 | Docs + PowerShell commands + demo guide | docs match code |
