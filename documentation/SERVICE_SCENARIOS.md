# Historical frequency-scenario arithmetic

[Notebook 11](../notebooks/new_york/11_service_frequency_scenarios.ipynb) compares assumed
average daily departure changes with scheduled bus-hour requirements and boarding intensity.
It is a reusable planning-prototype component. **The alternatives are not timetables,
operational recommendations or measured improvements.**

## Paired baseline and source gates

The baseline uses the same 41 routes, 78 common eligible dates and 3,198 route/date observations
as the historical review, from 6 July–27 September 2026. Daily demand, trip starts and scheduled
clock-date service hours are paired before aggregation. Every route/day type retains its
actual date set, sample size, source snapshots and review period.

There are **123 route/day-type baselines: 120 eligible and three withheld**. M98 remains
withheld for all day types because its route-level source clarification is unresolved.
Known historical facts remain visible, but projections and limit flags stay missing.
The review period and source-issue counts must match the baseline observations exactly.

## Arithmetic and units

Let D, N and H be baseline daily means for published boardings, departures and scheduled
bus-hours. For frequency factor f and independently assumed demand factor g:

    scenario departures = f × N
    scenario bus-hours = f × H
    scenario boardings = g × D
    scenario boardings per departure = (g × D) / (f × N)

Scaling trips and hours together assumes an unchanged aggregate service mix. Clock-date
service exposure includes contributions from overnight service, so H/N is not a measured
trip duration or vehicle round-trip cycle. Fractional daily means are preserved; no individual
departure times or integer timetable are generated.

A +20% departure case with fixed demand mechanically lowers boardings per departure by
16.67%. It does not demonstrate reduced crowding or that the assumed passenger total could
actually be served. Demand sensitivity ±10% is an independent analyst assumption, not a
learned response to service. Future forecasts are not paired with historical schedules.

## Alternative cases and illustrative limits

Five factors, 0.8, 0.9, 1.0, 1.1 and 1.2, produce **615 alternative frequency cases**.
The primary limit is ten additional scheduled bus-hours per average day, with at least
80% of baseline mean departures retained. Both limits are illustrative choices, not agency
budgets, accessibility guarantees or transport standards.

| Arithmetic status | Alternative cases |
|---|---:|
| Within the declared limits | 441 |
| Exceeds the added-hours limit | 159 |
| Source-withheld | 15 |

The first count includes unchanged and reduced-service cases; it is not a count of beneficial
or operationally feasible plans. Rows are alternatives and must not be summed into a single
network proposal. Cuts can harm access despite satisfying the arithmetic floor.

For the fixed M34+ weekday example, +20% departures changes the daily mean from **172.16 to
206.59**, adds **12.45 scheduled bus-hours**, and exceeds the illustrative ten-hour limit.
The +10% case adds 6.23 hours. Four budget settings, including unspecified, are retained.
An unspecified budget is not a passing check. A separate −25% case demonstrates failure
of the retained-service floor.

## Fixed-hour transfer illustration

The manually specified pair M34+/M34A+ is evaluated with a zero-transfer control and a
five-bus-hour transfer in each direction. Both baselines use exactly the same weekday dates;
their date-set hashes must match. Each route's assumed demand is unchanged.

All three cases retain **130.349 scheduled bus-hours per average weekday** in total.
Departure totals change by about −1.608 or +1.608 for the two directions, demonstrating why
equal trip counts cannot be substituted for equal-hour accounting.

September geometry records 22 shared stop IDs and 12/7 pair-specific stop IDs. This is
context, not evidence that transfers preserve passenger journeys. No merger, rerouting,
vehicle-block, layover, deadhead, staffing or peak-fleet assessment is performed.

## Verification and reuse

The notebook has **12 executed code cells, 27 saved outputs and five figures**. All **76 tests
pass**, including date/source gates, genuine zeros, fractional means, invalid factors,
budget/floor handling and transfer conservation. The independent audit checks paired totals,
all scenario formulas and statuses, 666 saved scenario rows, all three transfer cases and
**197 earlier artifacts unchanged**.

Ten CSV tables and a manifest are local under `data/processed/new_york/service_scenarios/`.
Five standalone figures are under `reports/service_scenarios/figures/`. Source/code/runtime
and output fingerprints support a reproducible handoff. No forecast is promoted or service applied.

```powershell
python scripts/execute_notebooks.py notebooks/new_york/11_service_frequency_scenarios.ipynb --kernel python3
python scripts/audit_service_scenarios.py
python -m unittest discover -s tests -v
```

The [Streamlit interface](DASHBOARD.md) exposes these calculations with baseline dates, demand
assumptions, declared limits, source withholding and unassessed feasibility beside the
comparison. Operational scheduling and measured passenger benefits require additional work.
