# Stage 7 replay report: session clock, stored forecasts and controlled reveal

Data version `cta_ref__r20261113__gtfs8__to20260731` · forecast run `run_389b917629f3a0a2` · model `stage4a-1.0.0`
(random forest on ride history, sha256 `7ca6be088104…`) · content sha256 of all stored forecasts `5d5bb651…`

Spec stage table, row 7: *"Session clock, forecast storage and controlled reveal → June–July updating demo with no
future-input access."* Every number in this report was read from the running API or the database for this data version.

## 1. What Stage 7 delivers

- **A replay clock owned by the server.** A session runs through 1 Jun – 31 Jul 2026, one virtual day at a time.
  - On replay day D, rides through D-1 are revealed (a stated one-day reporting delay).
  - The session is stored in PostgreSQL. A browser refresh returns to the same day, and no client can set the date.
- **Stored forecasts.**
  - For every scheduled route and day, the frozen model's forecast was issued at the start of that day from rides up to the day before. The 4-week-average baseline was stored on the same rows.
  - Each one is stored once and never rewritten: 14,036 rows, 2 methods × 7,018 route-days.
- **Controlled reveal.**
  - Every analysis endpoint takes its cutoff from the session when one is given, and refuses a cutoff from the client alongside it.
  - Today's forecast is visible before today's actual. An actual appears only after the clock passes its day.
- **Screens.**
  - A top-bar switch, "Historical analysis | Historical replay", with replay controls.
  - A new Replay screen, "How good were the forecasts, day by day?".
  - A forecast panel on One route.
  - Every existing screen works in replay without screen-specific changes.

## 2. Requirement → evidence

| # | Requirement (spec) | Evidence |
|---|---|---|
| R1 | Versioned session: id, data/model versions, virtual date, delay, speed, status (9.14.4, 9.17.2) | `replay_sessions` table; `POST /api/replays` returns run, model version and sha256, data version, delay, speed, status. `test_api_replays.py::test_create_defaults_to_1_june_with_versions_delay_and_cutoffs` |
| R2 | Start any day 1 Jun – 31 Jul, default 1 Jun; day D reveals D-1 (9.14.1, 9.10.4) | `clock.new_clock`; `test_replay_clock.py` (start, out-of-range refused); `test_api_replays.py` (default 1 Jun, revealed 31 May) |
| R3 | Start, pause, advance, reset, date selection, speed (9.14.1, 9.17.3); next week, jump to end | `POST /api/replays/{id}/control` actions; `test_replay_clock.py` (advance, next week, select date, playback steps, speed) |
| R4 | Pause stops; refresh restores; reset makes a new session and keeps the old (9.14.4, 9.17.3) | `test_replay_clock.py::test_playing_advances…_and_pause_stops_it`; `test_api_replays.py::test_reset_creates_a_new_session_and_keeps_the_old_one` |
| R5 | Stop at the final date, never wrap (9.14.4) | `test_replay_clock.py::test_a_session_never_moves_back_and_never_passes_the_end`, `test_playback_stops_at_completion`; the UI shows "Replay complete · data revealed to 31 Jul 2026" (Playwright) |
| R6 | Delay assumption stored and visible; only a 1-day delay accepted, with the reason (9.14.1, 9.16.1, 9.10.4) | Session field `delay_assumption` and note, shown in the replay bar; a 2-day delay → 422 "only a one-day reporting delay is supported…" (`test_bad_sessions_are_refused_with_a_reason`) |
| R7 | In replay every endpoint takes its cutoff from the session; a client cutoff is refused (9.17.3) | `db.request_cutoff`; `test_api_replay_mode.py::test_a_client_cutoff_with_a_session_is_refused`; later ranges clipped (`test_a_later_range_is_clipped_to_the_session`) |
| R8 | No date or count after the cutoff in any raw JSON (9.16.3) | `test_api_replay_mode.py::test_no_date_after_the_cutoff_in_any_replay_response`: 18 requests over coverage, routes, history (including from 2001), rankings (3 measures, overlap, development), compare (including same-days), groups, map lines, network trend, model card and forecasts |
| R9 | Features from rides through D-1 only, from the database, with Stage 3's single feature builder (9.14.2) | `forecasting.day_inputs` (`BETWEEN D-28 AND D-1` in SQL) + `build_features`; `test_replay_forecasts.py::test_replay_features_equal_stage3_for_every_june_july_day` (all 7,018 route-days identical) |
| R10 | Forecast timetable = latest captured strictly before D (9.14.3) | `test_every_forecast_uses_a_timetable_captured_before_its_day`: 0 rows with a later capture; 11 Jul uses `mdb-389-202605300003` with rides through 10 Jul |
| R11 | Frozen model, sha checked; each forecast carries its versions, issue time, latest ride date, snapshot, delay, units, status (9.14.1, 9.17.4) | `forecasting._pipeline` checks sha256 against the model manifest; `GET /api/forecasts` fields; `forecasts` table constraints |
| R12 | Unavailable with a reason, never imputed or 0; no unvalidated fallback (9.10.5, 9.17.4) | 476 route-days `unavailable` per method, each with "missing: …" in words (`test_unavailable_forecasts_have_a_reason_and_no_value`); `fallback_reason` is always null |
| R13 | 4-week-average baseline stored the same way | `forecasts.method = 'seasonal_mean'`, the same 6,542 forecast rows |
| R14 | Stored before reveal, never overwritten; retry returns stored rows (9.17.2, 9.19.1) | Primary key (run, method, issue, route, target); `ForecastConflict` on a differing recomputation (`test_a_stored_forecast_that_differs_is_refused_not_rewritten`); `test_a_retry_stores_nothing_and_rewrites_nothing` (POST twice, `created_at` unchanged) |
| R15 | Deterministic | Two builds give the same content hash `5d5bb651…` (`test_two_builds_give_the_same_hash`; `build_forecasts.py` run twice: 0 newly stored, 14,036 re-verified) |
| R16 | `POST/GET /api/forecasts` (9.17.3, 9.17.4) | `routers/forecasts.py`; POST refuses a day not yet reached in the session |
| R17 | Today's forecast before its actual; actual only after reveal; missing actuals excluded and counted (9.14.2) | `test_no_actual_for_a_day_not_yet_revealed`; review `coverage.route_days_without_actual` |
| R18 | Forecast vs actual per route; running MAE/WAPE, model against baseline on the same route-days | `GET /api/forecasts/review`; `test_after_a_week_the_running_error_equals_an_independent_sql_computation` |
| R19 | Forecast demand/service review (9.12): predicted rides alongside planned trips/hours | Review `rows` (predicted rides per scheduled trip and hour, ties share a rank); `test_the_review_ranks_predicted_rides_per_hour_and_lists_unavailable_rows_with_reasons`; "largest misses" kept separately with the 20-day gate |
| R20 | Rankings from revealed history only; same gate and ties; groups frozen (9.14.4) | `test_replay_rankings_use_revealed_history_only`; at 7 Jun: 123 of 125 routes ranked, period ending 7 Jun |
| R21 | Training cutoffs visible; later-measured scores hidden (9.14.1) | Replay screen: "trained on data to 31 Mar 2026, chosen on 1 Apr – 31 May 2026, frozen before June"; the model card stays hidden under the session cutoff |
| R22 | Mode switch and replay controls in the top bar (9.13.1, 9.16.1) | `ModeSwitch`, `ReplayBar`; Playwright checks the headline "Replay day: 1 Jun 2026 · data revealed to 31 May 2026" |
| R23 | Every existing screen works in replay with no later dates | `scripts/replay_check.mjs`: 8 screens + route 22 at 1366 and 1920, no date after the revealed day |
| R24 | Replay screen | `/replay`: insight, model facts, running-error chart, today's forecasts, yesterday vs actual, largest misses |
| R25 | One route forecast panel (9.16.3) | `ForecastPanel`: predicted rides, scheduled trips/hours, forecast rides per scheduled trip, issue context, chart with today marked "actual not yet revealed", Advance one day; historical mode shows a note |
| R26 | Every displayed forecast has model version, target date, issue context, status; observed vs predicted labelled (9.19.2, 9.16.1) | Panel and Replay screen texts; chart legends "Recorded rides" (solid), "Predicted rides (model)" (dashed), "4-week average" (dotted) |
| R27 | Leakage test (9.19.1) | `test_no_peeking_changing_every_later_ride_leaves_earlier_forecasts_bit_identical` (section 4) |
| R28 | Replay JSON scan; client cutoff refused | R7, R8 |
| R29 | Snapshot boundary | R10 |
| R30 | Determinism, no duplicates | R14, R15 |
| R31 | Consistency with Stage 4a | Section 5 |
| R32 | Playwright replay click-through with screenshots | Section 6 |
| R33 | Report, README, NOTES, mentor page | This report; README "Stage 7" commands and replay assumptions; NOTES Steps 88–95; the mentor page is kept privately |

## 3. Demo walkthrough (real numbers)

1. **Start a replay (default 1 Jun 2026).**
   - The bar reads "Replay day: 1 Jun 2026 · data revealed to 31 May 2026" and states the assumption.
   - Nothing is scored yet. Today's forecasts exist for **86 of 123** scheduled routes. The others are "unavailable – missing: rides 1 day earlier", because 31 May was a Sunday and many weekday routes have no Sunday record.
2. **Reveal a week (Next week).** The bar reads "Replay day: 8 Jun 2026 · data revealed to 7 Jun 2026".
   - **Running error:** over the **755** route-days revealed, the model's average miss is **395.0** rides per route-day against **409.5** for the 4-week average, **3.5 % lower** (WAPE 7.10 % vs 7.36 %).
   - **Day by day:** the model had the smaller miss on only **3 of 7** days (it won on 1 Jun, 579 vs 693, on 4 Jun and on 7 Jun, 408 vs 489; it lost on 2, 3, 5 and 6 Jun, by up to 40 rides on 2 Jun).
   - **Yesterday (7 Jun), route 22:** forecast 12,344 rides, 4-week average 11,806, actual 14,962 (a miss of +2,618).
   - **Today (8 Jun), route 22:** predicted 14,558 rides on 240 scheduled trips and 320.8 trip-hours (45.4 predicted rides per scheduled hour, #15 of today's review). Its actual reads "not revealed yet".
   - **Rankings:** weekday rides per scheduled hour, recomputed through 7 Jun: 123 of 125 routes ranked; routes 10 and 130 are listed unranked because they had no scheduled weekday service in the revealed period yet.
3. **Jump to end.** The bar reads "Replay complete · data revealed to 31 Jul 2026".
   - **Final:** on **6,542** route-days, the model's average miss is **398.0** against **421.2** (WAPE 7.67 % vs 8.12 %), 5.5 % lower.
   - **Daily wins:** even so, the model had the smaller miss on only **29 of 61** individual days.
   - **Largest misses:** all 125 routes are now ranked. The largest average misses are on the busiest routes: 9 (1,334.5 vs 1,245.0 for the 4-week average), 53 and 151.

## 4. The leakage test (no future-input access)

On the test database:
1. Every ride after 30 Jun was changed (rides × 3 + 7, all 3,597 rows).
2. All forecasts were deleted and rebuilt through 30 Jun.
3. The content hash of the rebuilt forecasts equals the original, bit for bit.

The same test shows it can fail. The forecasts for 2 Jul, whose inputs include changed July rides, move for more than 100 routes. The rides are then restored, and the full run hash is checked against the original.

## 5. Consistency check

The stored forecasts, scored over all of June–July on the route-days where both methods forecast and a ride was
recorded, reproduce Stage 4a's test scores exactly:

| | Route-days | Model MAE | 4-week-average MAE | Model WAPE | 4-week-average WAPE |
|---|---|---|---|---|---|
| Stored replay forecasts | 6,542 | 398.0115 | 421.1546 | 7.67 % | 8.12 % |
| Stage 4a test (`model_manifest.json`) | 6,542 | 398.0115 | 421.1546 | 7.67 % | 8.12 % |

So the day-by-day replay builds exactly the inputs the offline evaluation was scored on. A second check confirms this: the replay's features equal Stage 3's `feature_rows.csv` for every one of the 7,018 June–July route-days.

## 6. Tests

| Suite | Result |
|---|---|
| Backend `pytest` (routeranker_test) | 329 passed (277 from earlier stages + 52 new), 11 min |
| — of which Stage 7 | 52: 8 clock, 8 session, 23 replay-mode, 5 review, 8 forecast integrity |
| Frontend `vitest`, tsc, lint, build | 107 passed; clean |
| Historical click-through (7 screens) | 7 of 7 |
| Replay click-through (`replay_check.mjs`) | 20 of 20 checks at 1366 and 1920 px: start headline, next day, next week, 8 screens and route 22 with no date after the revealed day, jump to end |

## 7. Limitations

- **The one-day reporting delay is assumed, not verified.** The public CSV's real publication timing is unknown, so the replay shows what the model would do under that stated policy. It doesn't prove next-day data availability. Other delays are refused, because they need rebuilt features and a newly evaluated model.
- **The test period was looked at during development.** June–July 2026 is a reused holdout. The replay reproduces those scores; it doesn't make them an untouched final test.
- **There is no fallback forecast.** When a required input is missing (476 route-days, mostly the previous day's ride), the forecast is "unavailable". The 4-week average is stored for comparison but was never validated as a fallback.
- **Early days are noisy.** The model's advantage appears over many days (5.5 % lower over June–July), yet it wins on only 29 of 61 single days. In a 1 Jun session it is 3.5 % ahead after seven revealed days and 3.5 % behind after eight (415.5 vs 401.5). The running chart shows this rather than hiding it.
- **Forecasts are shared per run.** They are stored once per forecast run (model, data and delay versions), and sessions on that run share them. The spec's "session/issue/route/target" key is met through the session's run. A reset makes a new session on the same stored forecasts, which can't change, so the audit trail is unaffected.
- **Historical mode still shows everything.** That's allowed by the explicit mode switch (spec 9.16.3). The no-peeking guarantee applies to every request that carries a replay session.
- **Not covered yet.** Scenarios come in Stage 8. Playback uses polling (once a second while playing), not WebSockets, which the spec allows. The optional current-date display mapping isn't implemented.
