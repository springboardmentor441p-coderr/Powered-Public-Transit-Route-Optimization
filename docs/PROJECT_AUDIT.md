# Project audit (RouteRanker)

Method: read all source, ran every test and both UIs, then ran the pipeline on two **real** operator feeds (Pune PMPML, Chennai MTC) to see what it does outside its synthetic comfort zone.
Severity: **C** critical (produces misleading results) · **H** high · **M** medium · **L** low.

## What actually works (verified)
GTFS (5 files) -> clean -> features -> RF/XGBoost/KMeans/DBSCAN -> frequency optimiser -> FastAPI -> React (8 tabs) and a Streamlit app; 9 Python tests and 1 frontend test pass.
Forecasting (XGBoost, chronological backtest) beats naive baselines on **synthetic** history. All of this is on generated data.

## Findings
| ID | Sev | Where | Evidence | Fix (phase) |
|---|---|---|---|---|
| A1 | **C** | `src/config.py:22` `DEMAND_K`; `src/features.py:94,132` | Demand proxy constants were tuned to the generator. Real feeds: 100 % of Pune routes "overcrowded", median peak load factor 19-26 (physical max ~1). | Explicit data modes A/B/C; no absolute loads without observed data; proxy mode reports a *relative index* with uncertainty (P2-P4) |
| A2 | **C** | `data/generate_synthetic_gtfs.py:17-18,72` | Generator imports the same `DEMAND_K` and attraction function that the "proxy" features use -> synthetic benchmark partly measures recovery of the generator's own formula. | Disclose; label synthetic as demonstration; benchmark on label-proxy semantics; report held-out-city results only (P3) |
| A3 | **C** | `src/optimizer.py` | Frequency is set to `required trips` for every flagged route, so before/after always "improves" (tests assert `after <= before`, a tautology). Real feeds: +470 % trips. | New candidate engine with constraints, rejection reasons, worsened-metric reporting, "insufficient data" outputs (P4) |
| A4 | **H** | `src/features.py:91` | Routes absent from a ridership file get `boardings=0` -> treated as empty -> "underutilised". Missing != zero. | Missing coverage -> NaN -> status "insufficient evidence" (P2) |
| A5 | **H** | `src/features.py` `trip_table` | Day type from `calendar.txt` weekday count only; `calendar_dates.txt` and `frequencies.txt` ignored; a service running all 7 days (Pune) is counted as weekday-only. | Reference-date service resolution incl. exceptions; frequency expansion (P2) |
| A6 | **H** | `src/models.py` classifier | Labels are rule-generated from the same load table; classifier features include a proxy of that table. No Dummy/Logistic baseline. Model applied to unseen cities regardless of distribution shift. | Label semantics disclosed; baselines added; ML classifier not applied to schedule-only/proxy datasets (P3) |
| A7 | **H** | `src/optimizer.py::_find_merges` | Merge test = stop overlap + load only; ignores direction, timetable, coverage loss, detours. | Feasibility checker (direction, timetable, coverage) + provisional status (P4) |
| A8 | **H** | `server/main.py:187-194` | `async def upload` does heavy sync pandas work (blocks event loop); no size limit; error text echoes exception (`{e}`); no job/progress model. | Background jobs, size caps, sanitised errors (P5/P6) |
| A9 | **H** | `src/data_loader.py::read_feed_zip` | No member-count, uncompressed-size or ratio limits (zip bomb); no member-name validation; whole files read into memory. | Safe zip reader with limits (P2/P6) |
| A10 | M | `server/main.py:34` | `allow_origins=["*"]`. | Configurable origins, default same-origin + dev (P6) |
| A11 | M | `src/cleaning.py` | Cleaning reports counts of removed rows but no before/after per table, no flag for substantial discard, original data not kept apart. | Row-count ledger + discard thresholds + validation report (P2) |
| A12 | M | `src/models.py::name_clusters` | Cluster names derived from load-factor thresholds, not cluster characteristics; silhouette 0.18. | Characteristic-based descriptions; stability metric (P3) |
| A13 | M | `src/forecast.py` | Only WAPE/MAPE/bias; no MAE/RMSE/MASE. | Add metrics + baselines (P3) |
| A14 | M | `app.py` | Streamlit duplicates orchestration and assumes demand columns exist (breaks without ridership). | Shared `src/service.py` used by both UIs (P5) |
| A15 | M | UI | No provenance badges, no validation view, no export of reports, labels "overcrowded" assert more than the data supports. | Provenance everywhere, category renaming, Data-quality/Export/Benchmark tabs (P5) |
| A16 | L | repo | `src/eda.py` figures and `folium`/`geopandas` listed but unused by the web app; stray `routeranker_explorer.html` removed earlier. | Documented as optional (P8) |
| A17 | L | `tests/` | No security, regression (stale results), reproducibility, mode or export tests. | Added (P7) |
| A18 | L | benchmark | No benchmark command. | `python -m src.benchmark` (P7) |

## Security review summary
Uploads: no size limits (A8), zip limits missing (A9), CORS wide (A10), tracebacks not leaked but `{e}` is (A8). Sessions are in-memory, keyed by random ids; **no authentication** exists (documented limitation).
