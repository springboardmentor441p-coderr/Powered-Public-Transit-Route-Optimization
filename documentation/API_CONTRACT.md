# Application API

Run `python -m backend.import_data` once, then `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
Set `DATABASE_URL` to the local PostgreSQL connection string. API docs are at `/docs`.

All analysis endpoints accept `mode=historical|replay` and, in replay mode, `session_id`.
Replay cutoffs are enforced by the server. Missing values are JSON null, never zero substitutions.
List responses use `{items: [...], context: {...}}`. Dates use ISO YYYY-MM-DD.

| Endpoint | Inputs and response |
|---|---|
| GET /api/health | Database health and imported data version |
| GET /api/data/coverage | Version, source register, date ranges, counts, supported replay dates, reporting policy |
| GET /api/routes | items: route, name |
| GET /api/routes/{route}/history | start_date, end_date; items: date, rides, scheduled_trips, scheduled_hours, day_type, schedule_snapshot, eligible |
| GET /api/routes/{route}/geometry | Route paths and geometry_version; withheld when unavailable as of replay clock |
| GET /api/rankings | start_date, end_date, day_type=All/Weekday/Saturday/Sunday, minimum_days=20, metric=mean_daily_rides/rides_per_trip/rides_per_hour/forecast_rides_per_trip, descending=true; items: rank, route, name, value, eligible, observed_days, matched_days, reason, total_rides, total_trips, total_hours |
| GET /api/routes/compare | routes comma-separated, start_date, end_date, day_type; items with shared-date evidence and context |
| GET /api/route-groups | Group memberships and profile period, status; unavailable for future profile period |
| GET /api/models | Models, evaluation summary and supported serving dates |
| POST /api/replays | `{start_date:"2026-06-01",end_date:"2026-07-31",speed_seconds:5}`; returns session |
| GET /api/replays/{id} | session: id, virtual_date, start_date, end_date, state, speed_seconds, available_through, reporting_delay_days, model_version, data_version, parent_session_id |
| POST /api/replays/{id}/control | `{action:"start"|"pause"|"advance"|"reset",days:1,speed_seconds:5}`; reset returns new session preserving old history |
| POST /api/forecasts | `{route:"M34+",target_date:"2026-06-01",session_id:"..."}`; immutable saved forecast |
| GET /api/forecasts | session_id, optional route; items: id, route, target_date, issued_at, prediction, units, status, model_version, data_version, available_through, schedule_snapshot, scheduled_trips, scheduled_hours, fallback_reason, actual (null until released) |
| POST /api/scenarios | `{route:"M34+",date:"2026-06-01",proposed_trips:200,demand_source:"observed"|"forecast",forecast_id:null,session_id:null,demand_multiplier:1,title:"Frequency review"}`; saved immutable baseline/proposed/delta, provenance and assumptions |
| GET /api/scenarios | optional session_id; saved scenarios |

The replay uses a fixed, evaluated retrospective model bundle. New York observations are released after 14 complete intervening days: at virtual date D, observations through D minus 15 days are available. This is an explicit simulation policy, not verified publisher arrival history. Historical mode may show the full source period. Replay mode cannot.

The daily forecasting experiment selects the fitted pipeline on validation dates and records a content-derived model ID. The API verifies its SHA-256 before loading it. A validated seasonal reference is available when the fitted artifact fails availability or integrity checks; every such result is labelled `validated_fallback`. Two released seasonal observations are required for either path. Lags 1, 7 and 14 are missing under the release policy; exact lags 21, 28, 35 and 42 remain eligible. No replay request trains or changes the fitted artifact. `latest_available_ride_date` is the latest released observation, while `latest_input_ride_date` is the latest observation actually used in seasonal predictors.

The model freeze is a simulated historical cutoff. The experiment was reconstructed after its historical target period and is not a pre-registered prospective evaluation or operational acceptance. Test-period evaluation metrics are available in historical analysis and withheld inside replay responses.

Automatic replay time is computed from a persisted wall-clock anchor when the API is polled. A PostgreSQL row lock serializes concurrent controls and reads; each crossed virtual day receives immutable forecasts before its results are returned. Starting, pausing, advancing and changing speed preserve this order. Reset creates a child session and retains the prior session and its forecasts. Existing dataset versions are retained by the importer. The API does not modify source observations.

Ranked service ratios are ratios of sums over the same eligible route/date observations with positive scheduled-service denominators. Forecast service ratios need a positive, issue-time eligible schedule denominator. Scenarios allow zero proposed trips and return null ratios in that case. New York service hours use clock-date passenger-trip exposure, so the scenario explicitly fixes baseline hours per departure as a proportional exposure assumption. It does not present that ratio as a measured trip-cycle duration, a complete operating-cost or a vehicle requirement estimate.
