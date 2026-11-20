-- backend/db/schema.sql : Stage 6a persistent entities (spec 9.17.2)
-- Rules used throughout:
--   * every table is keyed by its version (data_version or group_version): two versions sit side by side
--   * a missing value is NULL, never 0; NOT NULL only where the source can never be missing
--   * CHECKs repeat the Stage 2/5 rules, so a bad row stops the import instead of slipping in
-- Stage 7 adds forecasts / replay_sessions, Stage 8 adds scenarios.

BEGIN;

-- ------------------------------------------------------------------ versions and sources
CREATE TABLE dataset_versions (
    data_version        text PRIMARY KEY,            -- cta_ref__r20261113__gtfs8__to20260731
    spec_version        text        NOT NULL,
    analysis_start      date        NOT NULL,         -- 2025-11-23
    analysis_end        date        NOT NULL,         -- 2026-07-31
    ridership_cutoff    date        NOT NULL,
    built_at            timestamptz NOT NULL,         -- manifest created_at
    built_git_commit    text        NOT NULL,
    manifest            jsonb       NOT NULL,         -- the whole Stage 2 manifest, unchanged
    imported_at         timestamptz NOT NULL DEFAULT now(),
    import_git_commit   text        NOT NULL,
    import_report       jsonb       NOT NULL,         -- counts, sha checks, excluded rows
    CHECK (analysis_start <= analysis_end)
);

CREATE TABLE source_files (                            -- the 9 rows of reports/source_register.csv
    data_version        text NOT NULL REFERENCES dataset_versions,
    snapshot_id         text NOT NULL,
    dataset_id          text NOT NULL,
    source_url          text NOT NULL,
    sha256              char(64) NOT NULL,
    byte_size           bigint NOT NULL CHECK (byte_size > 0),
    downloaded_at       timestamptz NOT NULL,
    row_count           bigint,                       -- NULL for GTFS zips (not a row file)
    expected_sha256     char(64),
    fingerprint_match   boolean NOT NULL,             -- ridership export: False, as recorded in Stage 1
    PRIMARY KEY (data_version, snapshot_id)
);

CREATE TABLE gtfs_snapshots (                          -- the 8 archives and the dates each one describes
    data_version        text NOT NULL,
    snapshot_id         text NOT NULL,
    captured_date       date NOT NULL,
    active_start        date NOT NULL,
    active_end          date NOT NULL,
    applied_start       date NOT NULL,
    applied_end         date NOT NULL,
    PRIMARY KEY (data_version, snapshot_id),
    FOREIGN KEY (data_version, snapshot_id) REFERENCES source_files,
    CHECK (applied_start <= applied_end)
);

-- ------------------------------------------------------------------ routes and geometry
CREATE TABLE routes (                                  -- bus routes in each archive's routes.txt
    data_version        text NOT NULL,
    geometry_version    text NOT NULL,                -- = snapshot_id of the archive
    route               text NOT NULL,                -- ridership-side key; text, so '007' stays '007'
    route_id            text NOT NULL,                -- GTFS route_id
    route_short_name    text,
    route_long_name     text,
    PRIMARY KEY (data_version, geometry_version, route),
    FOREIGN KEY (data_version, geometry_version) REFERENCES gtfs_snapshots
);

CREATE TABLE route_shapes (                            -- geometry/route_shapes.csv: "most common path per direction"
    data_version        text NOT NULL,
    geometry_version    text NOT NULL,
    route               text NOT NULL,
    direction_id        smallint NOT NULL CHECK (direction_id IN (0, 1)),
    direction_label     text NOT NULL,                -- GTFS trips.direction, e.g. 'North'
    shape_id            text NOT NULL,
    trip_days_using_shape integer NOT NULL,            -- the selection measure: active trips x applied days run
    active_trip_days    integer NOT NULL CHECK (active_trip_days >= trip_days_using_shape),
    trips_using_shape   integer NOT NULL CHECK (trips_using_shape > 0),
    active_trips        integer NOT NULL CHECK (active_trips >= trips_using_shape),
    tied_top_shapes     smallint NOT NULL CHECK (tied_top_shapes >= 1),   -- equal top trip-days; 1 = no tie
    point_count         integer NOT NULL CHECK (point_count >= 2),
    line_geojson        jsonb NOT NULL,               -- GeoJSON LineString, [lon, lat] order
    PRIMARY KEY (data_version, geometry_version, route, direction_id),
    FOREIGN KEY (data_version, geometry_version, route) REFERENCES routes,
    CHECK (trip_days_using_shape >= trips_using_shape),     -- every active trip runs on >= 1 applied day
    CHECK (jsonb_array_length(line_geojson -> 'coordinates') = point_count)
);

-- ------------------------------------------------------------------ observations and schedule
CREATE TABLE daily_ridership (                         -- full raw export, 2001-01-01 .. ridership_cutoff
    data_version        text NOT NULL REFERENCES dataset_versions,
    route               text NOT NULL,
    service_date        date NOT NULL,
    daytype             char(1) NOT NULL CHECK (daytype IN ('W', 'A', 'U')),
    rides               integer NOT NULL CHECK (rides >= 0),   -- a recorded 0 is a real 0
    source_snapshot_id  text NOT NULL,                -- which export the row came from
    PRIMARY KEY (data_version, route, service_date),
    FOREIGN KEY (data_version, source_snapshot_id) REFERENCES source_files
);

CREATE TABLE daily_schedule (                          -- expanded_scheduled_route_day_service.csv
    data_version            text NOT NULL,
    route                   text NOT NULL,
    service_date            date NOT NULL,
    snapshot_id             text NOT NULL,             -- exactly one selected archive per date
    route_id                text NOT NULL,
    scheduled_trips         integer NOT NULL CHECK (scheduled_trips >= 0),
    scheduled_service_hours double precision CHECK (scheduled_service_hours >= 0),  -- NULL = incomplete
    duration_complete       boolean NOT NULL,
    trips_missing_duration  integer NOT NULL CHECK (trips_missing_duration >= 0),
    PRIMARY KEY (data_version, route, service_date),
    FOREIGN KEY (data_version, snapshot_id) REFERENCES gtfs_snapshots,
    CHECK (duration_complete = (trips_missing_duration = 0)),
    -- two-way hours rule: complete <=> hours present, so a partial hours sum can never be stored
    CHECK (duration_complete = (scheduled_service_hours IS NOT NULL))
);

CREATE TABLE matched_utilization (                     -- expanded_matched_utilization.csv
    data_version             text NOT NULL,
    route                    text NOT NULL,
    service_date             date NOT NULL,
    daytype                  char(1) NOT NULL CHECK (daytype IN ('W', 'A', 'U')),
    rides                    integer NOT NULL CHECK (rides >= 0),
    snapshot_id              text NOT NULL,
    route_id                 text NOT NULL,
    scheduled_trips          integer NOT NULL CHECK (scheduled_trips > 0),
    scheduled_service_hours  double precision,
    duration_complete        boolean NOT NULL,
    trips_missing_duration   integer NOT NULL,
    rides_per_scheduled_trip double precision NOT NULL,
    rides_per_scheduled_hour double precision,         -- NULL exactly when hours are NULL
    PRIMARY KEY (data_version, route, service_date),
    FOREIGN KEY (data_version, route, service_date) REFERENCES daily_schedule,
    FOREIGN KEY (data_version, route, service_date) REFERENCES daily_ridership,
    CHECK ((rides_per_scheduled_hour IS NULL) = (scheduled_service_hours IS NULL))
);

CREATE TABLE ridership_without_schedule (              -- 424 rows: recorded rides, no selected service
    data_version         text NOT NULL,
    route                text NOT NULL,
    service_date         date NOT NULL,
    daytype              char(1) NOT NULL CHECK (daytype IN ('W', 'A', 'U')),
    rides                integer NOT NULL CHECK (rides >= 0),
    selected_snapshot_id text NOT NULL,
    unmatched_reason     text NOT NULL,
    identifier_absent_from_all_archives boolean NOT NULL,
    PRIMARY KEY (data_version, route, service_date),
    FOREIGN KEY (data_version, route, service_date) REFERENCES daily_ridership
);

CREATE TABLE schedule_without_ridership (              -- 24 rows: scheduled service, no ridership record
    data_version            text NOT NULL,
    route                   text NOT NULL,
    service_date            date NOT NULL,
    missing_reason          text NOT NULL,             -- the CSV's always-empty rides column is not stored
    PRIMARY KEY (data_version, route, service_date),
    FOREIGN KEY (data_version, route, service_date) REFERENCES daily_schedule
);

-- ------------------------------------------------------------------ Stage 5: groups, rankings, overlap
CREATE TABLE group_versions (
    group_version       text PRIMARY KEY,             -- cta_ref__.../groups__dev20251123_20260331
    data_version        text NOT NULL REFERENCES dataset_versions,
    artifact_version    text NOT NULL,                -- stage5-1.0.0
    artifact_sha256     char(64) NOT NULL,            -- route_groups.joblib
    profile_start       date NOT NULL,
    profile_end         date NOT NULL,
    k                   smallint NOT NULL CHECK (k >= 2),
    features            jsonb NOT NULL,               -- the 5 selected features
    group_names         jsonb NOT NULL,               -- {"0": "...", "1": "..."}
    caveats             jsonb NOT NULL CHECK (jsonb_array_length(caveats) > 0),
    default_overlap_version text NOT NULL,
    settings_sha256     char(64) NOT NULL,
    names_sha256        char(64) NOT NULL,
    manifest            jsonb NOT NULL,               -- whole groups_manifest.json (settings, runtime, k table)
    built_git_commit    text NOT NULL
);

CREATE TABLE utilization_profiles (                    -- expanded_utilization_profiles.csv (both periods)
    group_version       text NOT NULL REFERENCES group_versions,
    period_name         text NOT NULL,
    period_start        date NOT NULL,
    period_end          date NOT NULL,
    route               text NOT NULL,
    daytype             char(1) NOT NULL CHECK (daytype IN ('W', 'A', 'U')),
    observed_days       integer NOT NULL CHECK (observed_days >= 0),  -- 0 is a real count
    rides_sum           bigint,                        -- NULL when observed_days = 0
    scheduled_trips_sum bigint,
    scheduled_hours_sum double precision,
    incomplete_duration_days integer NOT NULL,
    scheduled_service_days   integer NOT NULL,
    mean_daily_rides         double precision,
    rides_per_scheduled_trip double precision,
    rides_per_scheduled_hour double precision,
    ranking_min_observed_days integer NOT NULL,
    observed_daily_demand_rank_eligible boolean NOT NULL,
    observed_daily_demand_rank_reason   text,
    observed_daily_demand_rank          integer,
    rides_per_trip_rank_eligible        boolean NOT NULL,
    rides_per_trip_rank_reason          text,
    rides_per_trip_rank                 integer,
    service_productivity_metric_rank_eligible boolean NOT NULL,
    service_productivity_metric_rank_reason   text,
    service_productivity_metric_rank          integer,
    PRIMARY KEY (group_version, period_name, route, daytype),
    CHECK ((observed_days = 0) = (rides_sum IS NULL)),
    -- eligible <=> ranked <=> no reason, for each of the three views
    CHECK (observed_daily_demand_rank_eligible = (observed_daily_demand_rank IS NOT NULL)
           AND observed_daily_demand_rank_eligible = (observed_daily_demand_rank_reason IS NULL)),
    CHECK (rides_per_trip_rank_eligible = (rides_per_trip_rank IS NOT NULL)
           AND rides_per_trip_rank_eligible = (rides_per_trip_rank_reason IS NULL)),
    CHECK (service_productivity_metric_rank_eligible = (service_productivity_metric_rank IS NOT NULL)
           AND service_productivity_metric_rank_eligible = (service_productivity_metric_rank_reason IS NULL))
);

CREATE TABLE route_profiles (                          -- route_profiles.csv, the 123 clustering profiles
    group_version       text NOT NULL REFERENCES group_versions,
    route               text NOT NULL,
    profile_start       date NOT NULL,
    profile_end         date NOT NULL,
    weekday_observed_days              integer NOT NULL,
    mean_weekday_rides                 double precision,
    weekday_rides_cv                   double precision,
    mean_weekday_scheduled_trips       double precision,
    weekday_incomplete_duration_days   integer NOT NULL,
    mean_weekday_trip_duration_minutes double precision,
    weekday_rides_per_scheduled_hour   double precision,
    saturday_observed_days             integer NOT NULL,
    saturday_scheduled_days            integer NOT NULL,
    saturday_service_status            text NOT NULL CHECK (saturday_service_status IN
                                         ('available', 'no_scheduled_service', 'insufficient_observations')),
    saturday_to_weekday_rides_ratio    double precision,   -- 0 = structural zero; NULL = unavailable
    sunday_holiday_observed_days       integer NOT NULL,
    sunday_holiday_scheduled_days      integer NOT NULL,
    sunday_holiday_service_status      text NOT NULL CHECK (sunday_holiday_service_status IN
                                         ('available', 'no_scheduled_service', 'insufficient_observations')),
    sunday_holiday_to_weekday_rides_ratio double precision,
    base_eligible       boolean NOT NULL,
    ungrouped_reason    text,
    PRIMARY KEY (group_version, route),
    CHECK (base_eligible = (ungrouped_reason IS NULL))
);

CREATE TABLE group_memberships (                       -- route_group_membership.csv: 128 rows, incl. ungrouped
    group_version       text NOT NULL REFERENCES group_versions,
    route               text NOT NULL,
    group_id            smallint,                      -- NULL = ungrouped
    reason              text NOT NULL,                 -- 'grouped' or why not
    group_name          text,
    PRIMARY KEY (group_version, route),
    CHECK ((group_id IS NULL) = (reason <> 'grouped')),
    CHECK ((group_id IS NULL) = (group_name IS NULL))
);

CREATE TABLE route_stop_coverage (                     -- route_stop_coverage.csv
    group_version          text NOT NULL REFERENCES group_versions,
    geometry_version       text NOT NULL,
    route                  text NOT NULL,
    served_stop_count      integer NOT NULL CHECK (served_stop_count > 0),
    served_stop_ids        text[] NOT NULL,            -- ';'-separated in the CSV; empty cell -> '{}'
    exclusive_stop_count   integer NOT NULL,
    exclusive_stop_ids     text[] NOT NULL,
    exclusive_stop_fraction double precision NOT NULL CHECK (exclusive_stop_fraction BETWEEN 0 AND 1),
    PRIMARY KEY (group_version, geometry_version, route),
    CHECK (cardinality(served_stop_ids) = served_stop_count),
    CHECK (cardinality(exclusive_stop_ids) = exclusive_stop_count),
    CHECK (NOT ('' = ANY (served_stop_ids)) AND NOT ('' = ANY (exclusive_stop_ids)))
);

CREATE TABLE route_stop_overlap (                      -- route_stop_overlap.csv
    group_version          text NOT NULL REFERENCES group_versions,
    geometry_version       text NOT NULL,
    route_a                text NOT NULL,
    route_b                text NOT NULL,
    route_a_stop_count     integer NOT NULL,
    route_b_stop_count     integer NOT NULL,
    shared_stop_count      integer NOT NULL CHECK (shared_stop_count > 0),
    shared_stop_ids        text[] NOT NULL,
    jaccard_stop_overlap   double precision NOT NULL CHECK (jaccard_stop_overlap > 0 AND jaccard_stop_overlap <= 1),
    smaller_route_stop_overlap double precision NOT NULL CHECK (smaller_route_stop_overlap > 0
                                                                AND smaller_route_stop_overlap <= 1),
    overlap_review_rank    integer NOT NULL CHECK (overlap_review_rank >= 1),
    interpretation         text NOT NULL,              -- "corridor review only: ..." on every row
    PRIMARY KEY (group_version, geometry_version, route_a, route_b),
    CHECK (route_a < route_b),
    CHECK (cardinality(shared_stop_ids) = shared_stop_count),
    CHECK (NOT ('' = ANY (shared_stop_ids))),
    FOREIGN KEY (group_version, geometry_version, route_a) REFERENCES route_stop_coverage,
    FOREIGN KEY (group_version, geometry_version, route_b) REFERENCES route_stop_coverage
);

-- ------------------------------------------------------------------ model metadata (used from Stage 7)
CREATE TABLE model_versions (                          -- metadata only; the .joblib stays in artifacts/
    model_version       text PRIMARY KEY,             -- artifact_version from model_manifest.json
    data_version        text NOT NULL,                -- features__delay1d sub-version, as in the manifest
    selected_method     text NOT NULL,                -- rf_demand
    pipeline_location   text NOT NULL,                -- artifacts/stage4a/models/rf_demand.joblib
    pipeline_sha256     char(64) NOT NULL,
    frozen_at           timestamptz NOT NULL,
    manifest            jsonb NOT NULL,               -- cutoffs, policies, feature contract, metrics
    built_git_commit    text NOT NULL
);

-- ------------------------------------------------------------------ indexes for the Stage 6 queries
CREATE INDEX daily_ridership_by_date     ON daily_ridership (data_version, service_date);
CREATE INDEX matched_by_date             ON matched_utilization (data_version, service_date);
CREATE INDEX overlap_by_version_rank     ON route_stop_overlap (group_version, geometry_version, overlap_review_rank);

COMMIT;
