# Integration walkthrough

This is the end-to-end path through RouteRanker: each pipeline stage, then the import, then every screen. Each step lists the command, what it produces, and what to check. The numbers are for data version `cta_ref__r20261113__gtfs8__to20260731`. Setup, if needed, is in [SETUP.md](SETUP.md). Commands are for Windows CMD from the repo root, with the venv active.

## Part A: the pipeline

### Stage 1: sources
```
python -I analytics\source\download_sources.py --config analytics\config\sources.json --raw data\raw
python -I analytics\source\build_register.py --config analytics\config\sources.json --raw data\raw --out reports
python -I analytics\source\validate_raw.py --config analytics\config\sources.json --register data\raw\source_register.csv --out reports
```
**Check** `reports/stage1_quality_report.md`:
- 9 register rows, and the 8 archives match the reference fingerprints;
- 1,124,170 ridership rows;
- the rows dated up to 31 Jul 2026 match the reference counts (1,120,604 records, 188 route identifiers, 36 genuine zeros);
- 3,566 rows from August 2026 are kept in the raw file and reported separately.

### Stage 2: daily reconstruction
```
python -I analytics\reconstruction\build_stage2.py --config analytics\config\sources.json --register data\raw\source_register.csv --out reports
```
**Check** `reports/stage2_quality_report.md`:
- **51 MATCH, 0 MISMATCH**;
- 28,398 scheduled route-days, of which 28,374 are matched;
- 424 have rides but no selected schedule, and 24 have a schedule but no ride record. Both lists are kept, never turned into zeros.

### Stage 3: feature contracts
```
python -I analytics\features\build_stage3.py --config analytics\config\sources.json --features analytics\config\features.json --register data\raw\source_register.csv --out reports
```
**Check** `reports/stage3_quality_report.md`:
- **50 MATCH, 0 MISMATCH**;
- issue time is the start of the day, with an assumed 1-day reporting delay;
- splits: train to 31 Mar 2026, validation April–May, test June–July.

### Stage 4: forecasting
```
set DV=data\processed\cta_ref__r20261113__gtfs8__to20260731
python -I analytics\models\train_stage4a.py --features %DV%\features__delay1d --models analytics\config\models.json --sources analytics\config\sources.json --artifacts artifacts\stage4a --out reports
```
**Check** `reports/stage4a_quality_report.md`:
- the six methods are scored on identical rows;
- `rf_demand` has the lowest validation MAE (345.47 vs 360.36 for the 4-week average, on 6,560 route-days);
- the artifacts are frozen before the test is scored;
- test: 398.01 vs 421.15 on 6,542 route-days.

Optional extra (Stage 4b, PyTorch): `train_stage4b.py`, with the full command in the README. **Check:** the best network (GRU, 364.86) beats neither the Random Forest nor the 4-week average, so serving is unchanged.

### Stage 5: groups and rankings
```
python -I analytics\groups\build_stage5.py --features %DV%\features__delay1d --groups analytics\config\groups.json --names analytics\config\group_names.json --sources analytics\config\sources.json --register data\raw\source_register.csv --artifacts artifacts\stage5 --out reports
python -I analytics\geometry\build_geometry.py --sources analytics\config\sources.json --register data\raw\source_register.csv --version-dir %DV%
```
**Check** `reports/stage5_quality_report.md`:
- 123 routes in k = 2 groups: 67 higher-demand, seven-day routes and 56 lower-demand routes. Silhouette 0.38, a near tie with k = 3.
- 5 routes are ungrouped, each with a reason.
- Full-window rankings: 125 / 92 / 86 routes ranked on weekdays / Saturdays / Sundays, and the rest are unranked with a reason.

## Part B: the database and the API

```
python -I backend\importer\import_data.py --create-schema
python -I backend\importer\import_stage7.py
python -I backend\replay\build_forecasts.py
python -I backend\importer\import_stage8.py
python -I backend\scenarios\save_examples.py
```
**Check:**
- `reports/stage6_import_report.md` shows every file hash checked and every count reconciled.
- `build_forecasts.py` prints that the stored forecasts reproduce Stage 4a's test MAE exactly (6,542 route-days). 14,036 rows are stored: 2 methods × 7,018 route-days.
- `save_examples.py` reports three examples, each "recomputed identically".

Start the API and the screens (README, [Setup](../README.md#setup-windows-from-a-fresh-clone)). Then open http://127.0.0.1:8000/api/health/database: it should answer `{"database":"routeranker"}`.

## Part C: the screens, in historical analysis
The top bar shows **Historical analysis**, with "Data to 31 Jul 2026".

| # | Screen | Do | Check |
|---|---|---|---|
| 1 | **Start** | read the question list and "The network over time" | the window is 23 Nov 2025 – 31 Jul 2026, with 125 routes on 251 dates; each question has a live one-line answer |
| 2 | **Closer look** | rank by rides per scheduled hour on weekdays, then switch to observed daily demand | 125 of 125 ranked on weekdays; the leaders change with the measure; the stability column compares the development period with the full window |
| 3 | **One route** | pick route 22 | ranks 11 / 6 / 24 of 125 on the three weekday measures; 251 of 251 scheduled days have a ride record; group 0 |
| 4 | **Alike** | read the scatter and the group spread | 2 groups (67 + 56), fitted on 23 Nov 2025 – 31 Mar 2026; 24 grouped routes sit inside the other group's range |
| 5 | **Shared stops** | choose "show" on the top pair | 703 pairs share at least one stop; routes 120 and 121 share 17 stops (Jaccard 0.810); the map names its geometry version |
| 6 | **Compare** | add 49 and X49 | both measured on the same 175 weekdays; every value can be clicked to show how it was made |
| 7 | **Scenarios** | open the saved "Route 49: 20 % more weekday trips, demand held fixed" (**do not Save**) | rides per scheduled hour 35.6 → 29.7, rank 58 → 86; every assumption is listed; "Recalculate and compare" gives an identical result |
| 8 | **Data** | scroll to the forecast model card | 10 methods; the Random Forest serves predictions; 345.5 vs 360.4 on validation and 398.0 vs 421.2 on test; the reused-holdout warning is shown |

## Part D: historical replay
1. Press **Historical replay** in the top bar. The bar reads "Replay day: 1 Jun 2026 · data revealed to 31 May 2026" and states the delay assumption.
2. Press **Next week**: "Replay day: 8 Jun 2026 · data revealed to 7 Jun 2026".
   - On **Replay**: 755 route-days revealed. Model 395.0 vs 409.5 for the 4-week average, 3.5 % lower, but the smaller miss on only 3 of 7 days.
   - Yesterday, route 22: forecast 12,344, actual 14,962.
3. **One route → 22** shows today's forecast (8 Jun): 14,558 predicted rides on 240 scheduled trips. Its actual reads "not revealed yet". Every forecast shows its model version, target date, issue time and status.
4. Visit **Start**, **Closer look**, **Alike** and **Data**. No date after the replay day appears. Rankings are recomputed from revealed rides only. The model card and the groups are hidden or frozen, with the reason.
5. Press **Jump to end**: "Replay complete · data revealed to 31 Jul 2026". The final score is 398.0 vs 421.2 on 6,542 route-days, with the model ahead on 29 of 61 days.
6. Press **Reset**, which makes a new paused session on 1 Jun and keeps the old one. Then switch back to **Historical analysis**. Don't leave **Play** running.

The spec's acceptance path (9.19.2) is: import, quality and coverage, a dated route, a ranking, a group, replay start/pause/advance/reset, a forecast against its revealed actual, and saving a scenario. Saving is part of that path. Do it on the test database, because a saved scenario can never be deleted. `scripts/scenario_check.mjs` does exactly this and refuses to run on the app database.

## Part E: automated proof of the same path
| What | Command | Result for this release |
|---|---|---|
| Pipeline + API | `python -m pytest` | see [the evaluation report](../reports/stage9_evaluation_report.md#8-tests) |
| Every screen reached by clicking | `node scripts\clickthrough.mjs` | 8 of 8 |
| Replay path, no later date on any screen | `node scripts\replay_check.mjs <folder>` (test database) | all checks pass at 1366 and 1920 px |
| Scenario path, including Save, in both modes | `node scripts\scenario_check.mjs <folder>` (test database) | all checks pass at 1366 and 1920 px |
