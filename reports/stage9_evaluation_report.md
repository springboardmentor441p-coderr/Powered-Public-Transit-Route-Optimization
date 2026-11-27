# Stage 9 evaluation report: the whole project in one place

Data version `cta_ref__r20261113__gtfs8__to20260731` · serving model `stage4a-1.0.0` (Random Forest on ride history) · route groups `groups__dev20251123_20260331` · forecast run `run_389b917629f3a0a2`

Spec stage table, row 9: *"Setup, integration walkthrough, evaluation report and limitations → Fresh setup runs the documented replay."* This report brings together the evidence from Stages 1–8 and adds the Stage 9 checks.
- Every figure below was taken from a committed stage report, or re-read from the app database through a read-only connection, before this report was written. All 22 of 22 checks matched (section 9).
- Dataset reference counts and the illustrative scenarios are not forecast-accuracy results or measured operational benefits (spec 9.22.2).

## 1. Data quality
| Check | Result | Source |
|---|---|---|
| Source register | 9 files (1 ridership export, 8 GTFS archives) with URL, download time, size and sha256 | `reports/source_register.csv` |
| Fingerprints (spec 9.22.1) | all 8 archives match. The ridership export is a newer download (13 Nov 2026, publisher update 28 Oct 2026), so its checksum differs | Stage 1 §1 |
| Ridership content up to 31 Jul 2026 | 1,120,604 records, 188 route identifiers, 2001-01-01 to 2026-07-31, 36 genuine zeros: all equal to the reference counts | Stage 1 |
| Raw validation | 0 missing identifiers, 0 unparseable dates, 0 negative or fractional rides, 0 duplicates, 0 conflicting records | Stage 1 |
| Rows after the observation period | 3,566 rows (2026-08-01 to 2026-08-31), kept in the raw file and excluded from analysis | Stage 1 |
| Publication delay | the newest ride date was 74 days before the download (2026-08-31 → 2026-11-13) | Stage 1 + register |
| Daily reconstruction | 51 MATCH, 0 MISMATCH. 28,398 scheduled route-days, of which 28,374 are matched; 424 rides without a selected schedule; 24 schedules without a ride record (reported in both directions) | Stage 2 |
| Feature contracts | 50 MATCH, 0 MISMATCH. Exact-date lags; missing stays missing and a real 0 stays 0 | Stage 3 |
| Database import | every processed file's sha256 checked against its manifest before loading; counts reconciled | `reports/stage6_import_report.md` |

## 2. Forecasting results
The serving method was chosen on validation MAE, and every setting was fixed before the test period was scored once (spec 9.19.2).

| Period | Shared route-days | Random Forest (ride history) | 4-week average (best baseline) | Difference |
|---|---|---|---|---|
| Validation, 1 Apr – 31 May 2026 | 6,560 | MAE 345.47, WAPE 6.40 % | MAE 360.36, WAPE 6.67 % | 4.1 % lower |
| Test, 1 Jun – 31 Jul 2026 (reused holdout) | 6,542 | MAE 398.01, WAPE 7.67 % | MAE 421.15, WAPE 8.12 % | 5.5 % lower |

- **All ten methods** were scored on the same rows: two seasonal baselines, Ridge and Random Forest, each with and without schedule inputs, plus four neural networks. Ridge loses to the 4-week average on both periods. The best network (GRU, validation 364.86) beats neither the Random Forest nor the 4-week average, so serving is unchanged (Stage 4a §3/§5, Stage 4b).
- **Coverage.** 95.6 % of validation and 93.2 % of test route-days are forecast. The rest are withheld with the names of the missing inputs, mostly the previous day's ride. They are never imputed and never scored (Stage 4a).
- **Per route and day type.** Results are in `reports/stage4a_per_route_evaluation.csv` and Stage 4a §5. The two routes unseen in training (10 and 130) are forecast through the "unknown route" encoding, with much larger errors (route 10: test WAPE 26.6 %).
- **Artifacts.** The pipelines are frozen with sha256 values in `artifacts/stage4a/model_manifest.json`. Reloading the compressed files reproduces the validation predictions exactly.

## 3. Replay
| Check | Result | Source |
|---|---|---|
| Stored forecasts | 14,036 rows: 2 methods × 7,018 route-days, each issued at the start of its day from rides through the day before. 476 per method are "unavailable" with a reason | Stage 7, database |
| Consistency with the offline test | the stored forecasts score **398.0115 vs 421.1546** on the same 6,542 route-days: exactly Stage 4a's test scores | Stage 7 §5, re-computed for this report |
| Leakage test | every ride after 30 Jun is changed (× 3 + 7) and the forecasts are rebuilt. Forecasts through 30 Jun stay bit-identical by hash, and the 2 Jul forecasts, whose inputs changed, move for more than 100 routes | Stage 7 §4, `test_no_peeking_…` |
| No later data on any screen | 18 API requests scanned for any date after the session cutoff; every screen checked in the browser at 1366 and 1920 px | Stage 7, `replay_check.mjs` |
| Day by day | on 8 Jun: 755 route-days, 395.0 vs 409.5 (3.5 % lower), smaller miss on 3 of 7 days. At the end: 6,542 route-days, 398.0 vs 421.2, **29 of 61** days | Stage 7 §3, database |

## 4. Groups and rankings
- **Groups.** 123 routes in k = 2 groups: 67 "higher-demand, seven-day routes" and 56 "lower-demand routes, often with limited or no weekend service". They were fitted on the development period (23 Nov 2025 – 31 Mar 2026) and frozen.
  - The silhouette of 0.38 means moderate separation, and k = 2 vs 3 is a near tie (0.381 vs 0.383).
  - 5 routes are ungrouped, each with a reason (Stage 5).
- **Rankings.** There are three named indicators: observed daily demand, rides per scheduled trip and rides per scheduled hour.
  - The ranking gate is 20 observed days of the day type, and ties share a rank.
  - Full window: 125 / 92 / 86 routes are ranked on weekdays / Saturdays / Sundays. Every unranked route keeps its reason, for example "no scheduled service of this day type" (30 on Saturdays, 36 on Sundays).
  - The ranking and clustering gates are applied independently (spec 9.7.2).
- **Shared stops.** 703 route pairs share at least one stop in the 26 Mar – 23 Apr 2026 timetable. This is corridor review only, not evidence to merge or split routes.

## 5. Scenarios
| Example (saved in the app database, recomputed to identical hashes) | Result |
|---|---|
| Route 49, +20 % weekday trips, demand held fixed | trips/day 270.6 → 324.7; trip-hours/day 386.7 → 464.1 at 85.8 min per trip; rides per scheduled hour 35.60 → 29.66 and per trip 50.88 → 42.40 (both −16.7 %, i.e. 1 − 1/1.2); rank 58 → 86 of 125 |
| Lower-demand group, rides assumed −15 % on weekdays | rides/day 72,323.1 → 61,474.6 (exactly × 0.85 on every route); labelled as a scenario assumption, never a prediction |
| Route 1, 40 Sunday trips where none are scheduled | not scaled by a %; ratios stay "unavailable" because no rides were recorded without service |

- The 3 saved examples are in `reports/stage8_scenario_examples.json`.
- The test database reproduces the same scenario ids and result hashes (`backend/tests/test_save_examples.py`).

## 6. Requirement → evidence, all nine stages (spec 9.18)
| Stage | Completion evidence required | Evidence |
|---|---|---|
| 1. Source foundation | Source register and reproducible quality report | `reports/source_register.csv`, `reports/stage1_quality_report.md` |
| 2. Daily reconstruction | Matched/missing tables with explained coverage | `reports/stage2_quality_report.md` (51 MATCH, both unmatched directions listed with reasons) |
| 3. Feature contracts | Versioned feature schema and chronological counts | `reports/stage3_quality_report.md` (schema 1.1.0, split counts), `artifacts/stage4a/feature_contract.json` |
| 4. Forecast experiment | Same-row comparisons, route/day-type errors and saved pipeline | `reports/stage4a_quality_report.md`, `stage4a_per_route_evaluation.csv`, `artifacts/stage4a/model_manifest.json`; extra: `stage4b_quality_report.md` |
| 5. Route groups and ranking | Group explanations and eligible ranking table | `reports/stage5_quality_report.md`, `stage5_group_summary.csv`, `stage5_rankings.csv`, `artifacts/stage5/groups_manifest.json` |
| 6. Application foundation | Working dated analysis and comparisons | `reports/stage6_import_report.md`, `stage6_application_report.md`; screens Start to Data |
| 7. Replay | June–July updating demo with no future-input access | `reports/stage7_replay_report.md` (leakage test, exact consistency) |
| 8. Scenarios | Saved baseline/scenario comparison with assumptions | `reports/stage8_scenarios_report.md`, `stage8_scenario_examples.json` |
| 9. Delivery | Setup, integration walkthrough, evaluation report and limitations; fresh setup runs the documented replay | `README.md`, `docs/SETUP.md`, `docs/INTEGRATION_WALKTHROUGH.md`, this report (section 7: fresh setup) |

### Stage 9 requirements
| # | Requirement | Spec | Evidence |
|---|---|---|---|
| D1 | Setup documentation | 9.18 row 9 | README "Setup", `docs/SETUP.md` (step by step plus troubleshooting) |
| D2 | Integration walkthrough | 9.18 row 9; 9.19.2 | `docs/INTEGRATION_WALKTHROUGH.md` |
| D3 | Evaluation report: baselines, common-row errors, per-route results, coverage; serving method chosen on validation and frozen before final scoring | 9.18 row 9; 9.19.2 | sections 1–5 of this report |
| D4 | Limitations | 9.18 row 9; 9.2.2; 9.21 | section 10 of this report; README "Limitations and future work" |
| D5 | A fresh setup runs the documented replay | 9.18 row 9 | section 7 |
| D6 | Each stage validated against its completion criteria | 9.18 | the table above |
| D7 | Deliverables: source manifest, quality report, data dictionary, feature schema, model/evaluation artifacts, cluster summaries, API/frontend source, saved scenario examples, short demo script | 9.18 | `source_register.csv`; stage reports; `docs/DATA_DICTIONARY.md`; `feature_contract.json` and `feature_schema.json`; `artifacts/*/…manifest.json`; `stage5_group_summary.csv`; `backend/`, `frontend/`; `stage8_scenario_examples.json`; README "Usage: the 5-minute demo path" |
| D8 | Model cutoffs, replay assumptions and supported dates in the README | 9.18 | README "Supported dates, model cutoffs and assumptions" |
| D9 | Import, training, API and frontend commands in the README | 9.17.5 | README "Setup" and "Reproduce the pipeline" |
| D10 | Acceptance path: import, inspect quality/coverage, open a dated route, select a ranking, inspect a group, start/pause/advance/reset replay, compare a forecast with its revealed actual, save a scenario | 9.19.2 | `docs/INTEGRATION_WALKTHROUGH.md` parts B–D; automated in `clickthrough.mjs`, `replay_check.mjs` and `scenario_check.mjs` (saving on the test database) |
| D11 | Each forecast shows model version, target date, issue context and status; each comparison its period and schedule source; each map its geometry version; each scenario its assumptions | 9.19.2 | Stage 7 R26; the Compare and One route captions; map captions ("Geometry version mdb-389-…"); the Scenarios assumptions box (screenshots in `docs/screenshots/`) |
| D12 | Correctness cases | 9.19.1 | section 8 |
| D13 | Reference counts and illustrative scenarios aren't presented as accuracy or benefit | 9.22.2 | wording in this report, the README and the screens |

## 7. Fresh setup (spec 9.18 row 9)
The documented setup was followed from a brand-new clone of `tayyaba-haroon`, in a separate folder:
1. A new `.venv` was made and `pip install -r requirements.txt` run (`pip check`: no broken requirements), then `npm ci`.
2. The clone was given the pipeline outputs it would produce: `data/` as hard links to the existing raw and processed files (read only), and the gitignored fitted models in `artifacts/`. The pipeline stages were **not** re-run here. Their reports, hashes and checks stand from Stages 1–5. A full re-run takes hours (downloads, Random Forest and neural-network training).
3. `docs/SETUP.md` step 7 was run on `routeranker_test` (`--url-var TEST_DATABASE_URL`, with the report and export sent outside the clone).

**The first attempt failed, and that led to a fix.**
- On Windows, Git's `core.autocrlf=true` wrote CRLF line endings into the cloned `analytics/config/group_names.json`. Its sha256 no longer matched the Stage 5 manifest, and the import refused: "group_names.json: sha256 484564bfa228… differs from its manifest 7104d7cde764…". Nothing was written.
- A `.gitattributes` rule now keeps `analytics/config/*.json` at LF on every checkout. The committed files were already LF, so no content changed.
- Troubleshooting for this was added to `docs/SETUP.md`.

**The second, brand-new clone (after the fix):**

| Step | Result |
|---|---|
| `import_data.py --create-schema` | 9 of 9 import identities hold; every file hash checked (81 s) |
| `import_stage7.py` | 28,312 forecast targets |
| `build_forecasts.py` | 61 days, 14,036 forecasts stored, content sha256 `5d5bb651…` (the same as Stage 7); consistency on 6,542 route-days: 398.0115 vs 421.1546, equal to Stage 4a |
| `import_stage8.py`, `save_examples.py` | 3 examples saved, each recomputed identically, with the same scenario ids as the app database |
| API (8010, test database) + Vite (5180) from the clone | `GET /api/health/database` → `routeranker_test` |
| `replay_check.mjs` | 28 of 28 checks at 1366 and 1920 px: start on 1 Jun, Next day, Next week, 9 screens and route 22 with no date after the revealed day, Jump to end. Repeated 3 more times: 28 of 28 each time |
| `scenario_check.mjs` | 72 checks, 0 failures: saved examples, save / reopen / recalculate in both modes, no later date in replay |
| `clickthrough.mjs` | 8 of 8, four runs |

**Result:** a fresh setup runs the documented replay. The clone's working tree stayed clean, and the temporary servers and the clone were removed afterwards.

## 8. Correctness cases (spec 9.19.1) and tests
| Case | Test |
|---|---|
| A weekly service removed by exception type 2 is absent | `analytics/tests/test_schedule.py::test_exception_type_2_removes_weekly_service` |
| An added service appears once, even if the weekly mask includes it | `test_schedule.py::test_exception_type_1_adds_once_even_if_weekly_includes_it` |
| 25:10 stays on its service date | `test_schedule.py::test_time_after_midnight_stays_on_service_date` |
| Outgoing/incoming regimes counted only on active dates | `test_schedule.py::test_outgoing_and_incoming_regimes_counted_only_on_their_dates` |
| One snapshot per route/date; no per-route fallback | `test_schedule.py::test_one_snapshot_per_date_and_no_per_route_fallback` |
| Exact-date lags stay missing; real zeros stay zero | `test_features.py::test_friday_to_monday_one_day_lag_is_missing`, `::test_real_zero_stays_zero_and_counts_as_observation`; `test_matching.py::test_missing_rides_stay_missing_and_zero_stays_zero` |
| One seasonal lag doesn't become the four-week mean | `test_features.py::test_single_seasonal_lag_does_not_become_the_mean` |
| Preprocessing fits on training data only; unseen routes handled | `test_models.py::test_encoder_and_scaler_learn_only_from_training_rows` (unknown routes encoded as all zeros; routes 10 and 130 in Stage 4a §5) |
| A replay forecast can't use target-day or later rides | `backend/tests/test_replay_forecasts.py::test_no_peeking_changing_every_later_ride_leaves_earlier_forecasts_bit_identical`, `::test_replay_features_equal_stage3_for_every_june_july_day`; `test_api_replay_mode.py::test_no_date_after_the_cutoff_in_any_replay_response` |
| Snapshot selection respects issue time and capture-date boundaries | `test_features.py::test_archive_captured_on_target_date_is_rejected_for_forecasting`; `test_replay_forecasts.py::test_every_forecast_uses_a_timetable_captured_before_its_day` |
| Refresh/retry doesn't duplicate or rewrite forecasts | `test_replay_forecasts.py::test_a_retry_stores_nothing_and_rewrites_nothing`, `::test_a_stored_forecast_that_differs_is_refused_not_rewritten` |
| Scenarios preserve observations and source predictions; units correct | `test_api_scenarios.py::test_route_49_plus_20_percent_trips_matches_the_rankings_baseline`, `::test_predicted_demand_uses_the_stored_forecast_and_keeps_it`, `::test_editing_makes_a_new_version_and_leaves_the_first_unchanged`; `test_scenario_engine.py::test_spec_illustration_50_to_60_trips_at_40_minutes` |
| Ranking and clustering gates applied independently | `test_profiles.py::test_clustering_weekend_gate_passing_does_not_make_the_route_rankable` |
| Reconciliation reports both unmatched directions and the per-route coverage checks | `test_matching.py::test_reconciliation_reports_both_directions_with_identities`; Stage 2 §2 (9.6.4.1 rows MATCH) |

### Test results for this release (run once at the end of Stage 9)
| Suite | Result |
|---|---|
| Pipeline + API (`python -m pytest`, database tests on `routeranker_test`) | **389 passed**, 0 failed, 0 skipped (8 min 4 s): 384 from Stages 1–8 + 5 new for `save_examples.py` |
| Frontend unit tests (`npx vitest run`) | 117 passed (16 files) |
| Type check, lint, build (`npx tsc -b`, `npm run lint`, `npm run build`) | clean |
| Browser checks from the fresh clone (test database) | replay 28/28 (×4), scenarios 72 checks / 0 failures, click-through 8/8 (×4) |
| Number check (section 9) | 22 of 22 |

## 9. How the figures were checked
A read-only script compared every figure quoted in the README, the docs and this report with its source. The sources were the stage reports, `artifacts/stage4a/model_manifest.json`, `reports/source_register.csv`, `reports/stage8_scenario_examples.json`, and SQL over the app database: the stored forecasts joined to the recorded rides for the replay scores and daily wins, and the saved example ids and hashes. **22 of 22 matched.**

## 10. Limitations
- **The observations can't show crowding** (spec 9.2.2, 9.21.1). They are whole-day rides per route: no occupancy, alightings, directions, hours or trips actually run. Rides per scheduled trip or hour describes turnover against scheduled service, not load.
- **The reporting delay is assumed** (9.10.4, 9.21.4). The public export was 74 days behind when it was downloaded. The replay's one-day delay is a stated demonstration assumption, and other delays are refused, because they would need rebuilt features and a new evaluation.
- **The test period was reused.** June–July 2026 was looked at while the method was being developed. The replay reproduces those scores, but it doesn't make them an untouched final test.
- **The advantage is small and uneven.** The model is 5.5 % better over June–July but has the smaller miss on only 29 of 61 days. The two unseen routes have much larger errors.
- **There is no validated fallback.** Route-days missing a required input are "unavailable" (476 per method in the test period). The 4-week average is stored only for comparison.
- **Groups and rankings are review aids** (9.21.3). The groups separate moderately and k is a near tie. A ranking orders routes under one named measure and doesn't judge overall quality or justify a service cut. Shared stops are corridor evidence only.
- **Scenarios are conditional arithmetic** (9.15, 9.21.6). There is no rider response, elasticity, crowding or running-time model, and no constrained vehicle or crew optimization.
- **Current-date forecasting is out of scope** (9.21.5). The app forecasts historical days only. A live version would need a faster feed or a separately evaluated long-horizon model.
- **Single city.** There is no importer for other cities' data (9.20), no hourly data and no uncertainty intervals. None were invented.
