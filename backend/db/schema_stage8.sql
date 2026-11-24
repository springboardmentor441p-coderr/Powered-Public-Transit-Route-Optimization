-- Stage 8 (scenarios): ADDITIVE only. Nothing in the Stage 6 or Stage 7 schema is changed.
-- Applied by backend/importer/import_stage8.py on top of an imported data version with the Stage 7 tables.
--
-- A scenario is a conditional calculation under saved assumptions (spec 9.15, 9.17.2). It is kept apart from the
-- observed tables and from forecast evaluation: nothing here is read by any ranking, history or forecast query.
-- Rows are IMMUTABLE: an edit is a new row (version + 1, same lineage), and the trigger below refuses UPDATE and
-- DELETE, so a saved scenario can never change after it was saved.
CREATE TABLE scenarios (
    scenario_id         text PRIMARY KEY,                 -- "scn_" + sha256 of the saved content (same save = same id)
    lineage_id          text NOT NULL,                    -- the first version's id; shared by every later version
    version             integer NOT NULL CHECK (version >= 1),
    parent_scenario_id  text REFERENCES scenarios (scenario_id),
    name                text NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
    origin              text NOT NULL CHECK (origin IN ('planner', 'example')),  -- 'example': the saved examples
    mode                text NOT NULL CHECK (mode IN ('historical_analysis', 'historical_replay')),
    session_id          text REFERENCES replay_sessions (session_id),          -- replay only
    virtual_date        date,                                                    -- replay only: the replay day
    cutoff              date NOT NULL,                    -- the last service date the calculation used
    data_version        text NOT NULL REFERENCES dataset_versions (data_version),
    group_version       text,                             -- the frozen route groups used (NULL if not shown)
    forecast_run_id     text REFERENCES forecast_runs (run_id),                 -- predicted demand only
    model_version       text,                                                    -- predicted demand only
    baseline            jsonb NOT NULL,                   -- period, day type, routes or group, demand basis
    inputs              jsonb NOT NULL,                   -- the service changes and demand stress, with units
    assumptions         jsonb NOT NULL,                   -- the same, in plain words
    result              jsonb NOT NULL,                   -- the calculated comparison
    result_sha256       char(64) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (lineage_id, version),
    CHECK ((mode = 'historical_replay') = (session_id IS NOT NULL)),
    CHECK ((version = 1) = (parent_scenario_id IS NULL)),
    CHECK ((forecast_run_id IS NULL) = (model_version IS NULL))
);
CREATE INDEX scenarios_by_cutoff ON scenarios (data_version, cutoff);

CREATE FUNCTION scenarios_are_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'saved scenarios are immutable: save a new version instead of changing or deleting one';
END $$;

CREATE TRIGGER scenarios_no_update_or_delete BEFORE UPDATE OR DELETE ON scenarios
    FOR EACH ROW EXECUTE FUNCTION scenarios_are_immutable();
