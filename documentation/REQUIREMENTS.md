# Requirements through EDA

This matrix defines the analytical scope, implementation evidence and acceptance criteria.
It distinguishes completed capabilities from outcomes that require additional observations
or later development.

| Requirement | Implementation/evidence | Status and qualification |
|---|---|---|
| Collect GTFS and load five essential tables | Collection scripts; notebook 01 | Complete for the selected New York feeds; historical comparisons cover Manhattan |
| Inspect types, missing values, duplicates, memory, keys and references | Notebook 01 and batch inspection reports for 11 feeds | Complete for project-required fields; not a full GTFS specification certification |
| Source register and original-file fingerprints | Receipts; notebook 02; `reports/eda/source_register.csv` | Complete; mutable URLs do not guarantee future identical downloads |
| Clean missing/conflicting/erroneous entries | Notebook 02 decisions, quarantine outputs, validity assertions | Complete for defined view; unverified source errors flagged, not guessed away |
| Hour, weekday/weekend and date features | Notebook 03 | Complete; weekdays are not inferred holiday labels |
| Measure route/hour demand | Publisher route-hour boarding estimates, July–September 2026 | Published aggregates available; stop/direction passenger allocations unavailable |
| Basic route profiles: length, duration, frequency, stops | Snapshot-specific trips and daily pattern profiles | Complete; distance is shape-polyline estimate, frequency is scheduled |
| Historical demand/service alignment | Latest whole archive, calendar exceptions, exact route-ID/date joins, clock-date integration | Complete for the explicitly eligible subset; archive gaps, partial calendars and DST context withheld |
| Identify high-demand periods and route usage patterns | Notebook 04 temporal curves and heatmaps | Complete for observed windows; traffic/delay measurements unavailable |
| Route density and geographic visualizations | Notebook 04 sampled geometry grid, stop density and route concentration | Complete descriptive mapping; no population/accessibility inference |
| Detect overlaps | Stop-set Jaccard, smaller-route overlap, exclusive stops and pair map | Complete as corridor-review evidence; no merge recommendation |
| Review relative service use | Date-counted relative boarding/service review list and sensitivity checks | Review priorities identified; verified underutilization requires costs, capacity and service purpose |
| Forecast daily demand against seasonal baselines | Exact-date candidate lags only | Later milestone; no trained or evaluated model |
| Clustering/classification | Interpretable structural/demand profiles only | Later milestone; true crowding classes unavailable |
| Streamlit interface | Planned analysis dashboard | Later milestone |
| Optimization benefit | No measured intervention outcome | Requires scenario assumptions and operational evaluation |

The completed scope covers reproducible collection, inspection, cleaning, feature engineering
and EDA for the selected data. Unresolved source-quality issues remain explicitly flagged.

## Acceptance checks

- Fresh-kernel execution succeeds in order; every code cell has visible saved output.
- Raw fingerprints remain unchanged; derived products have hashes, schemas and explicit grains.
- Duplicate keys/conflicts cannot silently inflate observations.
- Calendar additions/removals, no-fallback archive selection, midnight/DST handling and duration
  conservation have tests.
- Exact-date lags preserve missing history and actual zero values.
- Demand/service comparisons show dates, population, denominator and exclusion policy.
- Capabilities without sufficient evidence are marked unavailable or deferred.
