# Baseline results (measured BEFORE the audit-driven changes)

Environment: Python 3.12, pandas 3.0, scikit-learn 1.8, 1 CPU core. Commands were run on the repository state at the start of this phase
(the only prior edits were the bus-only filter and vectorised overlap added while ingesting the real feeds).

| Check | Command | Result |
|---|---|---|
| Python tests | `python -m pytest tests -q` | **9 passed** in 101 s |
| Frontend integration test | `cd frontend && npx vitest run` (API running) | **1 passed** (renders 8 tabs) in 11.4 s |
| Synthetic pipeline | `python train.py` | ~36 s; RF unseen-city macro-F1 0.654; forecast WAPE 4.0 % |
| **Real feeds** (Pune PMPML 315 routes, Chennai MTC 3,934 bus routes) | `python scripts/analyze_real.py` | 80 s, **but results invalid** (below) |

## Real-feed baseline: evidence of misleading output
| Observation | Value |
|---|---|
| Pune routes labelled "overcrowded" | 315 of 315 |
| Chennai routes labelled "overcrowded" | 3,813 of 3,934 |
| Median "peak load factor" (impossible; 1.0 = full bus) | Chennai 19.3, Pune 25.7 (`outputs_real/routes.csv`) |
| Optimiser: trips/day before -> after (Pune+Chennai) | 57,175 -> 325,679 (**+470 %**) |
| Reported avg wait | 23.7 -> 1.9 min |

Cause: with no passenger counts the baseline pipeline silently fell back to a demand proxy whose constants (`DEMAND_K`, attraction decay) were tuned to the
synthetic generator, then reported absolute load factors and forced a recommendation for every route. The synthetic benchmark therefore did not generalise.
These numbers must never be presented as findings; they are retained only as the regression baseline for Phase 2-4 fixes.
