# Application acceptance

Acceptance distinguishes tested behaviour from complete product scope and operational readiness.

## Verified behaviour

The 10 November full run passed 118 tests. The browser/API journey passed all eight
React screens with no JavaScript errors, repeated forecast requests returned the
same stored forecast, target actuals remained hidden until their release boundary,
zero proposed service returned undefined service ratios, and reset retained the
previous session. Evidence is saved locally under reports/application_acceptance.

Additional PostgreSQL cases cover immutable model selection, corrupt-artifact
fallback, invalid requests, same-session scenario linkage and issue-time schedule
capture boundaries. These tests use an isolated temporary schema.

## Reverification

The 11 November rerun passed 121 tests in 72.378 seconds; the frontend production
build also passed. The build reports a JavaScript chunk above 500 kB, which remains
a performance improvement opportunity rather than a failed build.
The fresh browser rerun passed all eight screens without JavaScript errors and
verified forecast idempotency, delayed actual reveal, zero-service scenario
arithmetic and reset history against the running PostgreSQL-backed API.

Run python -m unittest discover -s tests -v with PostgreSQL available. Start the API
and React development server, then run python scripts/accept_application.py.
Build the frontend with npm run build from frontend. Inspect test_results.txt,
test_run.json and browser_acceptance.json together with their timestamps; an
interrupted run must not inherit a successful status from an older report.

The browser test waits for request completion before advancing between replay
and forecasting. Database test setup uses a five-second connection timeout so
unavailable infrastructure fails promptly.

## Remaining release conditions

- Schedule-feature comparison completed in notebook 13; the candidate did not beat the seasonal baseline. The current replay model remains unchanged.
- React route maps, comparison geometry and scenario/forecast cards are implemented. Later-period geometry and clusters remain correctly withheld in replay.
- Validate the prepared React/API/PostgreSQL container configuration on a Docker-enabled host and complete independent-machine deployment verification.
- Continue user evaluation of the planning interface; evidence details remain expandable for audit.

Passing software tests does not establish forecast operational acceptance, observed
crowding, executable timetables or measured benefits from service changes.


## Planning workspace extension

The updated suite passed 123 tests. Browser checks passed eight screens and the replay/scenario journey. Historical maps rendered four selected-route variants and seven variants in the two-route comparison. A separate UI check covers selecting a route from the map and saving a zero-service scenario. See timestamped local evidence for the outcome.

Notebook13 contains executed schedule-feature comparison tables and a figure. Both contributing schedule captures must precede issue date; quality gates and common scoring populations are tested. The schedule-aware candidate did not outperform the seasonal baseline and was not promoted.

The primary Dockerfile/Compose configuration now packages React, FastAPI and PostgreSQL. Actual container execution and verification on another machine remain pending. A newly created Python environment is used for a separate setup check; this is narrower than independent-machine deployment acceptance.

The isolated Python environment successfully served the built React entry point and retrieved the persisted database version, 41 routes and model metadata. This checks local dependency isolation and packaged serving; it does not replace independent-machine/container verification.
