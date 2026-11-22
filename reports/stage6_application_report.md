# Stage 6 application report: RouteRanker screens and API

Data version `cta_ref__r20261113__gtfs8__to20260731` · branch `tayyaba-haroon` · code up to commit `f6107ec`

Every number in this report was read from the running API (the same endpoints the screens call) on this data
version. Nothing is typed in by hand on the screens: each sentence is built from API values when the page loads.

## 1. What Stage 6 delivers

- **A read-only API (FastAPI) over the imported PostgreSQL data.** It has nine endpoints: coverage, routes, route
  history, rankings (three measures plus the route overlap review), compare, route groups, map lines, network trend
  and the model card summary. Every response names its data version and the cutoff it applied.
- **Seven screens (React + TypeScript).** Start, Closer look, One route, Alike, Shared stops, Compare and Data. Each
  answers one planner question.
- **Shared rules across the whole app:**
  - A missing value is shown as "unavailable – reason", never as 0. A real 0, such as a route with no scheduled
    weekend service, is shown as 0 and labelled as such.
  - Colour means the route group and nothing else. Other differences (for example, two routes on one map) use line
    patterns with a key.
  - Every chart has one "How to read this" line.
  - Every number in a sentence or table can be clicked to see how it was made: the formula, the actual numerator and
    denominator, days counted, period, data version and the exact API request.
  - Visible text contains no API field names and no internal codes; a backend test scans for both.
- **Dev checks.** A Playwright script screenshots every page at 1366 px and 1920 px and flags console errors,
  sideways scrolling and clipped form fields. A second script reaches each screen by clicking (Start → Closer look →
  screen) and confirms the real content appears.

## 2. Screen walkthrough

### Start (`/`): "Where do I begin?"
- **What it shows:**
  - the five planner questions, each with a live one-line answer;
  - the network's recorded rides per day;
  - the dated map;
  - a route summary table.
- **Example:** from 23 Nov 2025 to 31 Jul 2026, the network carried 612,873 rides on an average weekday (175
  weekdays). An average Saturday carried 428,188 (70 % of a weekday), and an average Sunday or holiday 331,099 (54 %).
- **Endpoints:** `/api/data/coverage`, `/api/network/trend`, `/api/rankings` (weekday demand, rides per scheduled
  hour, overlap review), `/api/route-groups`, `/api/map/lines`, `/api/routes`.

### Closer look (`/closer-look`): "Which routes deserve a closer look?"
- **What it shows:**
  - the three rankings side by side: observed daily demand, rides per scheduled trip and rides per scheduled hour;
  - rank stability, comparing the development period (to 31 Mar 2026) with the full matched window;
  - a minimum-days control that accepts any whole number, with a "non-reference gate" label for anything other than
    20;
  - an optional peer group (ranks restart from 1 inside it);
  - a highest-first / lowest-first switch;
  - the unranked routes, each with its reason;
  - the route overlap review as a fourth view.
- **Example:**
  - On weekdays the measures disagree. The highest observed daily demand is route 9 (17,818 rides/day), while the
    highest rides per scheduled hour is route 134 (59.2). Only 1 of the top 10 routes by rides per scheduled hour is
    also in the top 10 by daily demand.
  - 9 of 123 routes keep exactly the same rank between the two periods, and 76 move 3 places or fewer.
  - On Saturdays, 92 routes are ranked and 33 are not: 30 have no scheduled Saturday service and 3 have fewer than 20
    observed days.
- **Endpoints:** `/api/rankings` (each measure, both periods, chosen day type, gate and group), `/api/route-groups`,
  `/api/routes`.

### One route (`/route/22`): "How is one route doing?"
- **What it shows:**
  - three ranks side by side, with stability;
  - recorded rides per day: the analysis window by default, with "Show full history since 2001";
  - a weekly rhythm grid;
  - the exact map lines (not simplified);
  - the route's group, and the routes that share its stops.
- **Example (route 22 Clark):**
  - On weekdays it ranks #11 by observed daily demand (13,694 rides/day), #6 by rides per scheduled trip (57.2) and
    #24 by rides per scheduled hour (42.7).
  - Its development-period ranks were #10, #4 and #24.
  - An average Saturday carries 103 % of an average weekday's rides and a Sunday or holiday 74 %.
  - All 251 of its scheduled days in the analysis window have a ridership record.
  - It is in Group 0, "Higher-demand, seven-day routes".
- **Endpoints:** `/api/routes/22/history`, `/api/rankings`, `/api/map/lines?routes=22&simplify_m=0`,
  `/api/rankings?metric=route_overlap_review`, `/api/route-groups`, `/api/routes`.

### Alike (`/alike`): "Which routes are alike?"
- **What it shows:**
  - a scatter of any two of seven profile measures, coloured by group. A route with a missing value is left off and
    named in a note with its reason. A route with no scheduled weekend service is plotted at 0.
  - each group's spread (lowest–median–highest) on every measure;
  - weekend service by group;
  - members and ungrouped routes, with reasons;
  - the method and the four caveats.
- **Example:**
  - 123 routes are in 2 groups, fitted on 23 Nov 2025 – 31 Mar 2026: Group 0, "higher-demand, seven-day routes" (67),
    and Group 1, "lower-demand routes, often with limited or no weekend service" (56). 5 routes are ungrouped, each
    with a reason.
  - On the default measures (average weekday rides against weekday rides per scheduled hour), 24 of the 123 grouped
    routes sit inside the other group's range. A group describes its typical member, not a hard boundary.
- **Endpoint:** `/api/route-groups`.

### Shared stops (`/shared-stops`): "Which routes share stops?"
- **What it shows:**
  - every pair of routes that share stops in a chosen timetable, with both overlap measures side by side (Jaccard,
    and the share of the smaller route) and each route's own stops;
  - a stop-share strip and a map for the selected pair;
  - the label "corridor review only: shared stop IDs are not merge/split evidence".
- **Example:**
  - In the timetable of 26 Mar – 23 Apr 2026, 703 route pairs share at least one stop.
  - The closest pair is 120 and 121: 17 shared stops out of 18 and 20, Jaccard 0.810, and 94 % of the smaller
    route's stops shared.
  - Only 7 of the top 10 pairs by Jaccard are also in the top 10 by share of the smaller route.
  - In 1 pair (49 and X49) every stop of the smaller route is also served by the other.
- **Endpoints:** `/api/rankings?metric=route_overlap_review`, `/api/map/lines?routes=…&geometry_version=…`,
  `/api/data/coverage` (timetable dates).

### Compare (`/compare?routes=49,X49`): "How do these routes differ?"
- **What it shows:**
  - 2 to 8 routes side by side, with each value's network rank;
  - a "same days only" switch that recomputes every value on the dates all chosen routes were observed;
  - a common-days warning when the routes were observed on different dates;
  - service and coverage gaps, and groups;
  - a map with one line pattern per route, and the shared stops among the chosen routes.
- **Example (49 and X49, weekdays, full matched window, 175 common days):**

  | Measure | 49 | X49 |
  |---|---|---|
  | Observed daily demand (rides/day) | 13,767 (#10) | 3,976 (#57) |
  | Rides per scheduled trip | 50.9 (#10) | 45.4 (#15) |
  | Rides per scheduled hour | 35.6 (#58) | 31.9 (#77) |
  | Scheduled trips per day | 271 | 87 |

  - X49 shares 71 stops with 49, and every X49 stop is also a 49 stop.
  - "Same days only" can change the answer. Comparing 10, 22, 49 and X49 on each route's own days, route 49 leads
    daily demand. On the 39 dates all four were observed, route 22 leads all three measures.
- **Endpoints:** `/api/routes/compare` (with `same_days=true` for the switch), `/api/routes`, `/api/data/coverage`.

### Data (`/data`): "Can I trust these numbers?"
- **What it shows:**
  - coverage;
  - missing data in both directions, with reasons;
  - the import checks;
  - the timetable archives;
  - a model card;
  - the sources (data version, commits, file hashes).
- **Example (coverage):**
  - Recorded rides run from 1 Jan 2001 to 31 Jul 2026, and dated schedules cover 23 Nov 2025 – 31 Jul 2026.
  - 99.9 % of scheduled route-days have a ridership record (28,374 of 28,398).
  - 424 route-days have rides but no schedule and 24 have a schedule but no rides; both kinds are shown as gaps.
  - All 9 import checks hold, and there are 8 timetable archives.
- **Example (model card):**
  - Ten methods were tried, all scored on exactly the same route-days (6,560 in validation, 6,542 in the test
    period).
  - The random forest on ride history serves predictions. Its average error is 345.5 rides per route-day on
    validation against 360.4 for the 4-week average (4.1 % lower), and 398.0 against 421.2 in the test period
    (5.5 % lower).
  - The best neural network (GRU, last 28 days) had a validation error of 364.9, so it beat neither the random forest
    nor the 4-week average.
- **Endpoints:** `/api/data/coverage`, `/api/models/summary`.

## 3. How the cutoff date is enforced

Every endpoint accepts an optional `cutoff` date. The rule lives in one place, `backend/app/db.py`:
`permitted_through(version, cutoff)` is the last service date a response may use. Every query filters
`service_date <= permitted_through` in SQL, so later rows are never read at all.

- **Periods are clipped.** With `cutoff=2026-05-31`, the full matched window becomes 23 Nov 2025 – 31 May 2026, and
  the response says `clipped_to_cutoff: true`.
- **A range that starts after the cutoff is refused.** The API answers HTTP 422 with "the requested range starts
  after the cutoff (2026-06-01 > 2026-05-31)", not an empty list.
- **Results built from later data are withheld, with the reason:**
  - route groups (fitted on data to 31 Mar 2026): "route groups were fitted on data after the cutoff, so they are
    not shown";
  - the model card (evaluated to 31 Jul 2026): "the models were evaluated on data after the cutoff, so their results
    are not shown".
- **Only earlier timetables can be chosen.** A timetable captured after the cutoff can't be used for maps or the
  overlap review.
- **The frontend never filters dates itself.** It only forwards the cutoff, and a test checks that every endpoint
  function forwards it. Stage 6 screens run without a cutoff (historical analysis); the replay screens that set one
  come later.
- **Tests:** backend tests scan whole responses for any ISO date after the cutoff, and check that a cutoff changes a
  ranking and matches an independent recomputation.

## 4. Tests

| Suite | Result |
|---|---|
| Backend (`pytest`, against a separate test database) | 277 passed |
| Frontend unit tests (`vitest`, 14 files) | 101 passed |
| TypeScript (`tsc -b`), lint (`oxlint`), production build | clean |
| Click-through check (Start → Closer look → each screen) | 7 of 7 screens pass |
| Layout screenshots, 9 pages at 1366 px and 1920 px | 18 of 18 with no console errors, sideways scrolling or clipped fields |

Notable tests:
- visible API texts contain no field names or spec numbers;
- every model-card number equals the committed model manifest;
- "same days only" values equal an independent SQL average;
- missing values are null with a reason, never 0;
- a cancelled or late answer can never become a screen's data;
- the natural route order (1, 2 … 8, 8A, 9, 12, then J14, N5, X49).

## 5. Limitations

- **The Data page was slow once.** Its top section took about 10 seconds to appear once in the project owner's
  browser, after clicking through from another screen. In repeated measurements the coverage request takes about
  0.6–1.5 s (11 KB), including with seven other requests running. The 10-second delay couldn't be reproduced.
  Two defects in how the screens accepted answers (a cancelled request read as an empty success, and late answers
  overwriting newer ones) were found and fixed, but they aren't proven to be the cause.
- **Two timetables.**
  - The shared-stops figures use the Stage 5 timetable of 26 Mar – 23 Apr 2026, the one the route overlap review
    was built on.
  - The maps use the latest timetable, 11 Jul – 31 Jul 2026.
  - Both are named on screen, but a reader comparing a map with the overlap table is looking at two different
    timetables.
- **49 and X49 overlap on the map.** They run along the same street, so their lines lie on top of each other and no
  line pattern can separate them there. The key and the shared-stops table make the relationship clear.
- **The test period was not untouched.** June–July 2026 was looked at while the forecasting method was being built,
  so its scores are a second check, not an untouched final test. The model card says so on screen.
- **Not in this stage.** Replay (viewing the app as of a past date) and Scenarios come in later stages. The top bar
  shows "Replay: not available yet".
- **Smaller points:**
  - the snug dropdown widths rely on a CSS feature that Firefox doesn't support, so dropdowns are wider there;
  - the route picker lists all 188 route numbers in the ridership data, including a few with rides but no timetable;
    their pages work and show the reasons.
