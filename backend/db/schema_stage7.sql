-- Stage 7 (replay): ADDITIVE tables only. Nothing in the Stage 6 schema is changed.
-- Applied by backend/importer/import_stage7.py on top of an imported data version.

-- ------------------------------------------------------------------ forecast targets
-- One row per route/day in the FORECAST-TIME schedule (spec 9.14.3): the latest archive captured strictly before the
-- target date. Only timetable facts known before the day are stored here; rides and lags are never stored, they are
-- recomputed from daily_ridership at forecast time, through the day before the target only.
CREATE TABLE forecast_targets (
    data_version        text NOT NULL REFERENCES dataset_versions (data_version),
    route               text NOT NULL,
    target_date         date NOT NULL,
    forecast_snapshot   text NOT NULL,                -- the archive the forecast may use (captured before the day)
    scheduled_trips     double precision NOT NULL,
    scheduled_hours     double precision,             -- NULL when trip durations are incomplete (never 0)
    sunday_like_day     boolean NOT NULL,             -- schedule-based, known before the day
    split               text NOT NULL CHECK (split IN ('train', 'validation', 'test')),
    PRIMARY KEY (data_version, route, target_date)
);
CREATE INDEX forecast_targets_by_date ON forecast_targets (data_version, target_date);

-- ------------------------------------------------------------------ forecast runs
-- A run = one frozen model + one data version + one information policy. Its forecasts are written once and shared
-- by every replay session on that run; the run id is derived from those versions, so it is the same every time.
CREATE TABLE forecast_runs (
    run_id              text PRIMARY KEY,
    data_version        text NOT NULL REFERENCES dataset_versions (data_version),
    model_version       text NOT NULL REFERENCES model_versions (model_version),
    model_sha256        char(64) NOT NULL,
    model_method        text NOT NULL,                -- rf_demand (the served model)
    baseline_method     text NOT NULL,                -- seasonal_mean (the 4-week average, for comparison only)
    reporting_delay_days integer NOT NULL CHECK (reporting_delay_days >= 1),
    issue_time_rule     text NOT NULL,
    first_target        date NOT NULL,
    last_target         date NOT NULL,
    code_commit         text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------ forecasts
-- Stored BEFORE the target day is revealed and never overwritten (spec 9.17.2): the key below makes a second write
-- of the same forecast impossible, and the writer refuses a recomputation that differs from the stored row.
CREATE TABLE forecasts (
    run_id              text NOT NULL REFERENCES forecast_runs (run_id),
    method              text NOT NULL,                -- rf_demand | seasonal_mean
    issue_date          date NOT NULL,                -- issued at the start of this day
    route               text NOT NULL,
    target_date         date NOT NULL,
    latest_ride_date    date NOT NULL,                -- the newest ride date the inputs could use (issue - delay)
    input_snapshot      text NOT NULL,                -- forecast-time schedule archive
    scheduled_trips     double precision NOT NULL,
    scheduled_hours     double precision,
    prediction          double precision,             -- rides/day; NULL when unavailable (never 0, never imputed)
    status              text NOT NULL CHECK (status IN ('forecast', 'unavailable')),
    withheld_reason     text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, method, issue_date, route, target_date),
    CHECK ((status = 'forecast') = (prediction IS NOT NULL)),
    CHECK ((status = 'unavailable') = (withheld_reason IS NOT NULL)),
    CHECK (latest_ride_date < issue_date),
    CHECK (prediction IS NULL OR prediction >= 0)
);
CREATE INDEX forecasts_by_target ON forecasts (run_id, target_date);

-- ------------------------------------------------------------------ replay sessions
-- The virtual clock (spec 9.14.4). virtual_date is "the start of day D"; rides through D minus the reporting delay are
-- revealed. A reset creates a NEW session (parent_session_id points back); sessions are never deleted.
CREATE TABLE replay_sessions (
    session_id          text PRIMARY KEY,
    parent_session_id   text REFERENCES replay_sessions (session_id),
    run_id              text NOT NULL REFERENCES forecast_runs (run_id),
    data_version        text NOT NULL REFERENCES dataset_versions (data_version),
    model_version       text NOT NULL REFERENCES model_versions (model_version),
    start_date          date NOT NULL,
    virtual_date        date NOT NULL,
    final_date          date NOT NULL,                -- last target day of the run
    reporting_delay_days integer NOT NULL,
    speed_seconds       double precision NOT NULL CHECK (speed_seconds > 0),
    status              text NOT NULL CHECK (status IN ('paused', 'playing', 'complete')),
    playing_since       timestamptz,                  -- set while playing: the server advances the clock from it
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (virtual_date >= start_date),
    CHECK (virtual_date <= final_date + reporting_delay_days)
);
