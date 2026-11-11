# Product scope

RouteRanker is a bus-service planning decision-support prototype. Its intended user
is a transport planner reviewing demand and scheduled supply for a dated network.

The workflow is to inspect coverage, rank routes under a named indicator, compare
routes on matching dates, inspect similarity groups, forecast daily boardings and
save conditional service scenarios. Historical replay demonstrates controlled
updates through a visible virtual clock and explicit reporting-delay assumptions.

The primary implementation uses React and TypeScript, FastAPI and PostgreSQL.
New York is the selected case. Daily boardings are published estimates; service
denominators are scheduled supply. Changes in scenario ratios are arithmetic
under stated assumptions, rather than measured passenger benefits.

## Related real-world products

[Conveyal Analysis](https://conveyal.com/learn) provides transit scenario editing
and travel-time/accessibility comparisons. RouteRanker shares the planner-facing
comparison workflow. It does not currently calculate access to jobs, schools or
other opportunities through a multimodal routing engine.

[Optibus](https://www.optibus.com/) provides broader public-transport planning and
operations products. RouteRanker's demand/service review and frequency scenarios
represent a small planning-analysis subset. Vehicle duties, crew rosters, dispatch,
operating-cost optimization and executable timetable feasibility are outside the
implemented scope.

These are functional comparisons, not claims of feature parity or affiliation.
