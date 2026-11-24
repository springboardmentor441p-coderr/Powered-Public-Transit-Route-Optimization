# Stage 8 scenarios report: service arithmetic, explicit demand stress, saved comparisons

Data version `cta_ref__r20261113__gtfs8__to20260731` · route groups `groups__dev20251123_20260331` (frozen) ·
saved examples in `reports/stage8_scenario_examples.json`

Spec stage table, row 8: *"Service arithmetic and explicit demand stress → Saved baseline/scenario comparison with
assumptions."* Every number below was read from the saved examples in the app database. Each was recomputed from
its stored inputs to an identical sha256 before this report was written.

## 1. What Stage 8 delivers

- **A scenario engine** (`backend/scenarios/`). A scenario has three parts:
  - **Baseline:** routes or a frozen route group, a period, a day type, and the demand (recorded rides; in replay, also the stored forecast for the replay day).
  - **Service changes:** scheduled trips and/or trip-hours, as a % or a new value per day.
  - **Optional demand assumption:** rides ± x % on the baseline routes or the whole network.

  The engine applies three rules:
  - **Demand is held fixed** unless the demand assumption says otherwise. Adding service never adds riders, and no elasticity is used.
  - **Trip-hours follow trips** at the baseline's mean duration per trip. That duration is stated and saved.
  - **Re-ranking uses Stage 5's own ranking function** (`rank_views`): the same 20-day gate, reasons and shared-rank ties as every other ranking.
- **Saved scenarios.**
  - A new table holds them, and the database refuses UPDATE and DELETE on it.
  - An edit is a new version in the same lineage.
  - Saving the identical scenario twice stores it once.
  - Recomputing uses the stored cutoff and versions and gives the same hash.
- **API:**
  - `POST /api/scenarios/calculate` and `POST /api/scenarios` (validate, calculate, save);
  - `GET /api/scenarios`, `GET /api/scenarios/{id}` and `GET /api/scenarios/{id}/recompute`.
  - In replay, the cutoff comes from the session, as on every other endpoint.
- **The Scenarios screen**, "What if we changed the service?":
  - a sentence builder and a separate, marked demand-assumption line;
  - computed insight sentences and an assumptions box;
  - a baseline → scenario table with rank changes, and a chart;
  - save, a saved list with "Recalculate and compare", and "Make a new version";
  - a "Create scenario" button on One route.
- **No clutter.** Automated checks never write to the app database.
  - pytest uses `routeranker_test`.
  - The browser checks refuse to run unless the API reports `routeranker_test`.
  - The app database holds exactly the 3 deliberate examples. Its 6 earlier replay sessions are unchanged.

## 2. Requirement → evidence

| # | Requirement (spec) | Evidence |
|---|---|---|
| S1 | Baseline: routes/group, period, day type; selected demand held fixed (9.15.1, sec. 6) | `service.calculate`; `test_api_scenarios.py::test_route_49_plus_20_percent_trips_matches_the_rankings_baseline` (baseline value and rank equal `/api/rankings`) |
| S1b | Forecast demand allowed; the original prediction is kept next to any stress (9.15.1, 9.15.2) | Replay only, "the stored forecast for the replay day"; `test_predicted_demand_uses_the_stored_forecast_and_keeps_it` (baseline = stored prediction, scenario = prediction × 1.2, forecast run and model version saved) |
| S2 | Trip-hours from a displayed duration per trip (9.15.1, 9.15.3) | Duration sentence in every saved scenario ("route 49: 85.8 minutes"); "Minutes per trip" column; `test_trip_hours_alone_keep_the_trips_and_imply_a_new_duration` |
| S3 | Conditional arithmetic, not proof of crowding, ridership gain or a feasible timetable; duration effects not modelled (9.15.1) | The interpretation and running-time sentences, saved with every scenario and shown in the assumptions box |
| S4 | Separate demand-stress control, labelled assumed demand, never a prediction (9.15.2, 9.13.3) | A marked "Scenario assumption" line on the screen; changed rides carry "assumed"; `test_a_minus_15_percent_demand_stress_scales_rides_by_exactly_0_85` |
| S5 | Save the scenario id, baseline data and forecast versions, route/date, changed values, units, duration and demand assumptions, outputs (9.15.2) | `scenarios` table columns; `test_save_is_immutable_idempotent_and_recomputes_to_the_same_hash` |
| S6 | Separate from observed tables and forecast evaluation (9.15.2, 9.20.4) | Own table; no other query reads it; calculation uses the read-only connection |
| S7 | Nonnegative trips; positive denominators; zero service → unavailable; hours only with a duration (9.15.3) | `test_invalid_inputs_are_refused_with_a_reason` (12 engine cases, 9 API cases); `test_minus_100_percent_gives_unavailable_ratios_not_zero`; `test_incomplete_durations_keep_hours_missing_and_refuse_an_hours_change` |
| S8 | No causal elasticity; demand fixed or explicit stress (9.15.3, sec. 6) | No elasticity input exists; an unknown field such as `elasticity` is refused (`test_an_unknown_field_is_refused`) |
| S9 | Preserve the baseline, identify changed parameters, keep assumptions, verify constraints (sec. 6, 9.19.1) | The baseline is returned beside the scenario on every row; `test_a_zero_percent_change_equals_the_baseline_exactly` (bit-identical) |
| S10 | 1001: schedule-based scenarios unavailable; no service ≠ 0 (9.6.4.2) | `test_route_1001_gets_no_service_change`; `test_a_structural_zero_is_not_scaled_by_a_percent_and_is_never_0`; example 3 below |
| S11 | Units and labels; observed / predicted / scenario told apart (9.16.1, 9.13.3) | Column heads "Recorded rides/day" or "Predicted rides/day", "Scheduled trips/day", "Scheduled trip-hours/day", "Rides per scheduled trip/hour"; chart key solid vs outlined |
| S12 | Re-rank by ratio of sums, per day type, 20-day gate, shared ties; groups frozen (9.7.1, 9.7.2, 9.12, 9.14.4) | `rank_views` extracted unchanged from Stage 5 (Stage 5 tests pass); `test_the_baseline_ranks_are_stage_5s_gate_and_ties`; group version saved with each scenario |
| S13 | Scenarios screen: table, deltas, saved assumptions; mode shown (9.16.2, 9.13.1) | `/scenarios`; "Service scenario: a hypothetical calculation…" label; `scenario_check.mjs` |
| S14 | "Create scenario" on route detail (9.16.3) | One route button → `/scenarios?routes=49` (checked by `scenario_check.mjs`) |
| S15 | Replay flow: +20 % trips under unchanged demand, save, advance (9.16.4) | `scenario_check.mjs` replay pass (save on 8 Jun, Next day, still listed, recomputes identically); `test_a_replay_save_is_hidden_from_earlier_sessions_and_recomputes_identically_later` |
| S16 | `POST /api/scenarios`; replay restrictions in backend queries (9.17.2, 9.17.3) | `routers/scenarios.py`; `test_replay_scenarios_use_revealed_rides_only_and_show_no_later_date` (raw JSON scan, later range refused, client cutoff refused) |
| S17 | Every scenario identifies its assumptions; reviewer can save one (9.19.2) | Assumptions saved word for word; Save on the screen |
| S18 | Saved scenario examples; illustrative scenarios are not measured benefits (9.18, 9.22.2) | `reports/stage8_scenario_examples.json` (3 examples); section 6 |
| U1 | Immutable; editing makes a new version; recompute → same hash | DB trigger (`test_update_and_delete_are_refused_by_the_database`); `test_editing_makes_a_new_version_and_leaves_the_first_unchanged`; no PUT/DELETE (405) |
| U2 | No clutter from automated checks | `GET /api/health/database`; `scenario_check.mjs` and `replay_check.mjs` refuse anything but `routeranker_test`; app database: 3 examples, 6 replay sessions (unchanged) |

## 3. Worked example 1: route 49, 20 % more weekday trips, demand held fixed

Saved as `scn_4f6653a10a53fb03`, result sha256 `6c33d568943f…`. Baseline: weekdays in the full matched window
(23 Nov 2025 – 31 Jul 2026), 175 observed days.

| Measure | Baseline | Scenario | Change |
|---|---:|---:|---:|
| Recorded rides/day | 13,766.5 | 13,766.5 | held fixed |
| Scheduled trips/day | 270.6 | 324.7 | +20.0 % |
| Mean duration per trip (assumed constant) | 85.8 min | 85.8 min | – |
| Scheduled trip-hours/day | 386.7 | 464.1 | +20.0 % |
| Rides per scheduled trip | 50.88 | 42.40 | −16.7 % |
| Rides per scheduled hour | 35.60 | 29.66 | −16.7 % |
| Rank on rides per scheduled hour (of 125) | 58 | 86 | 28 places down |

- **Why the ratios fall by exactly 1/6:** both denominators grow by a factor of 1.2 while the rides stay the same, and 1 − 1/1.2 = 16.7 %. This matches spec 9.15.1's illustration (50 → 60 trips at 40 minutes: 20.00 → 16.67 per trip, 30.00 → 25.00 per hour). The engine test reproduces those numbers.
- **The ripple effect:** 28 other routes move up one place each, because route 49 dropped below them.
- **The network:** across all 125 routes, rides per scheduled hour moves from 37.87 to 37.69 (−0.5 %).

## 4. Worked example 2: lower-demand route group, rides assumed 15 % lower on weekdays

Saved as `scn_223d8238cd634c20`, result sha256 `c2e0c1352ea9…`. Baseline: the frozen group "Lower-demand routes,
often with limited or no weekend service" (56 routes), weekdays, full matched window. No service change.

| Measure (the 56 routes) | Baseline | Scenario | Change |
|---|---:|---:|---:|
| Rides/day (sum of route means) | 72,323.1 | 61,474.6 | −15.0 % (assumed) |
| Scheduled trips/day | 4,698.0 | 4,698.0 | unchanged |
| Scheduled trip-hours/day | 2,501.1 | 2,501.1 | unchanged |
| Rides per scheduled trip | 15.39 | 13.09 | −15.0 % |
| Rides per scheduled hour | 28.92 | 24.58 | −15.0 % |

- **The stress factor is exact:** every route's rides are exactly 0.85 × the recorded value (checked on all 56).
- **Ranks:**
  - 32 of the 56 routes move down the network ranking, e.g. route 1 from 64 to 79 and route 7 from 61 to 78;
  - 68 routes outside the group move up as a result.
- **The network:** across all 125 routes, rides per scheduled hour falls from 37.87 to 37.20 (−1.8 %).
- **On screen,** the assumption is the marked "Scenario assumption" line, and every changed rides value says "assumed".

**The same group on Sundays and holidays** (checked in the browser, not saved as an example):
- 32 of the 56 routes have no scheduled Sunday service;
- they are listed once as "unavailable on both sides: no scheduled service on Sundays and holidays, so nothing to compare", not as 0;
- the other 24 routes go from 20.4 to 17.4 rides per scheduled hour.

## 5. Edge-case example 3: adding Sunday service where there is none

Saved as `scn_105335ff18ed69ac`. Route 1 has no scheduled Sunday/holiday service in the window: a structural zero.

- **A percentage change is refused.** There is nothing to scale.
- **An explicit 40 trips per day is accepted.** Scheduled trips/day becomes 40.0 (unavailable before).
- **Rides and both ratios stay "unavailable".** The reason given: "no recorded rides on days without service, so demand there is unknown".
- **Trip-hours stay unavailable.** The reason given: "trip-hours need a stated value per day where there was no service". No duration is invented.
- **Ranking:** the route stays unranked, and no other route's rank changes.

## 6. Tests

| Suite | Count | Result |
|---|---:|---|
| `backend/tests/test_scenario_engine.py` (arithmetic, no database) | 30 | pass |
| `backend/tests/test_scenario_schema.py` (immutability in SQL, test-only reset) | 4 | pass |
| `backend/tests/test_api_scenarios.py` (API, both modes, on `routeranker_test`) | 21 | pass |
| Stage 5 profile and integration tests after the `rank_views` extraction | 17 | pass |
| Full backend suite (all stages; 329 before Stage 8 + 55 new) | 384 | pass (31 min) |
| Frontend vitest (9 new in `lib/scenarios.test.ts`) | 116 | pass |
| `scenario_check.mjs` (Playwright, both modes, 1366 and 1920) | 40 checks | pass |
| `replay_check.mjs` (now including Scenarios) | 22 checks | pass |
| `clickthrough.mjs` (now including Scenarios) | 8 screens | pass |

Identities the tests check:
- 0 % = baseline, bit for bit;
- trips × 1.2 ⇒ rides per scheduled trip and per hour ÷ 1.2 (to 1e-12);
- a −15 % stress ⇒ rides × 0.85 exactly;
- −100 % ⇒ ratios unavailable, not 0.

In replay, every scenario response is scanned for any ISO date after the replay day, and none is found.

## 7. Honest limitations

- **No rider response to service changes.** Adding trips never adds riders, and removing them never loses any. A real frequency change would change demand, but a fitted association between trips and rides is not a causal effect (spec 9.15.3). So demand changes only through the explicit, labelled assumption.
- **Constant running time.** Each added trip is assumed to take the baseline's mean duration. Congestion, departure times and direction mix are not modelled.
- **Not an operating plan.** No vehicles, crews, budget, turnaround or minimum-service rules are checked. A scenario is not a feasible timetable, and route merge/split advice is out of scope.
- **Daily grain only.** There are no hourly or peak effects, and no crowding: the data has no occupancy.
- **Limits are design choices.** The input limits are my own, since the spec sets none: service −100 % to +200 %, 0–2,000 per day, demand −90 % to +100 %.
- **Forecast demand covers one day.** Predicted rides are used only for the replay day, so the 20-day period gate cannot apply. One-day rankings say so on screen.
- **Not evidence of benefit.** The examples are illustrative arithmetic on recorded data (spec 9.22.2). They are not measured operational results.
- **A constant sentence in a saved example.** The running-time sentence is saved with every scenario, including the demand-only example, where no trip changes. It is accurate but adds nothing there. The saved example keeps it, because saved scenarios are immutable.

## 8. Reproduce (CMD, from the repo root)

```
.venv\Scripts\activate
python -I backend\importer\import_stage8.py                         (adds the scenarios table; once)
python -I backend\scenarios\save_examples.py                        (saves the examples once; later runs only re-check)
python -m pytest backend\tests\test_scenario_engine.py backend\tests\test_scenario_schema.py backend\tests\test_api_scenarios.py
```

Browser check (on the test database only):
1. Start an API with `set ROUTERANKER_URL_VAR=TEST_DATABASE_URL` on port 8010.
2. Start Vite with `set ROUTERANKER_API=http://127.0.0.1:8010` on port 5180.
3. Run `set APP_URL=http://localhost:5180` then `node scripts\scenario_check.mjs <folder>` from `frontend`.
