# EDA findings and analysis status

These results describe the frozen local collection. The four executed notebooks provide the
calculations and charts; source updates can change fresh-download results.

| Evidence | Result |
|---|---:|
| Original source files with verified receipts | 57 |
| Collected route/date boarding observations | 275,896 |
| Collected route/hour boarding observations | 993,600 |
| Historical Manhattan routes in the versioned crosswalk | 41 |
| Positive-service daily comparisons after conservative checks | 10,014 across 246 dates |
| Eligible hourly comparisons in the July–September pilot | 86,486 |
| Unordered route pairs assessed | 820 |
| Pairs sharing at least one stop ID | 128 |
| Relative service-use review candidates | 13 route/day-type profiles |
| Exported EDA figures | 12 |

The broader daily collection spans **1 January 2025–30 September 2026**. The hourly collection
spans **1 July–30 September 2026**. Historical schedule comparisons cover only dates supported
by the five selected Manhattan archives, calendar completeness and quality screens.

## Findings that affect interpretation

1. **Weekday demand peaks around 08:00** in the median hourly Manhattan profile; weekends have
   a broader daytime pattern. These are published boarding patterns, not observed bus crowding.
2. **Nine SBS routes were recoverable through exact source route IDs.** Their display short names
   differ from ridership codes; an explicit crosswalk preserves all 41 routes without string guessing.
3. **An active calendar can be incomplete.** Three archive-boundary dates have only two active
   trips. Those contexts are flagged and excluded rather than treated as complete timetables.
4. **Seven dates require demand review.** Six dates have all-zero network totals, and one further
   date contains two unusually low observed hours. The cause is unverified; originals remain intact.
5. **High overlap does not imply replaceability.** M34+ and M34A+ share 22 stop IDs, with a Jaccard
   overlap of about 0.54, while retaining different stop coverage. The map and exclusive-stop counts
   are review evidence, not a merge recommendation.
6. **Low relative service use can coexist with distinctive coverage.** The review table includes
   sample sizes, dates and exclusive stops; it does not assign underutilized/overcrowded labels.
7. **Structural features can be redundant.** Length, scheduled duration and stop counts are strongly
   associated in this small network. Later modelling should avoid treating correlated metrics as
   independent evidence or using target-derived ratios as predictors for the same target.

## What is complete

The pipeline through **exploratory data analysis** is implemented: inspection, cleaning decisions,
versioned features, historical alignment, hourly usage analysis, geographic density, overlap,
quality sensitivity and documented findings. See the [requirements matrix](REQUIREMENTS.md)
for scope, acceptance checks and evidence limits.

## What follows

Define the forecast target, information release delay and chronological evaluation protocol before
model preparation. Then evaluate seasonal baselines, demand regression and interpretable route
grouping. The later interface remains **Streamlit**. Observed occupancy, actual delay, operating costs
and passenger destinations require additional data; no model or operational improvement is claimed here.
