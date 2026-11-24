# Final Verification Audit

## A. Missing headway values (highest priority)
- Total rows in `route_cluster_assignments.csv`: **4611**
- Total rows for active routes: **3934**
- Original missing values in `weekday_headway_min`: **1546**
- Original missing values in `weekend_headway_min`: **1546**
- Non‑missing `weekday_trip_count` count: **3065**

### First 10 rows with missing headway values
```
 route_id  weekday_trip_count  weekday_headway_min  weekend_headway_min
    18750                   1                  NaN                  NaN
    18753                   1                  NaN                  NaN
    18761                   0                  NaN                  NaN
    11919                   0                  NaN                  NaN
    10684                   1                  NaN                  NaN
    18763                   0                  NaN                  NaN
    13402                   0                  NaN                  NaN
    17956                   1                  NaN                  NaN
    17678                   0                  NaN                  NaN
    18787                   1                  NaN                  NaN
```

### Cross‑tabulation (including missing values)
```
weekday_headway_min False       True       
weekend_headway_min False True  False True 
trip_bin                                   
missing_trip            0     0     0     0
0                       0     0     0   677
1-5                  1547     0     0   869
6-10                  623     0     0     0
>10                   895     0     0     0
```

- Sum of all bin counts (including missing): **4611** (should equal filtered dataset rows **3934**).
- Sum of missing weekday headway counts: **1546** (should equal original missing count **1546**).
- Sum of missing weekend headway counts: **1546** (should equal original missing count **1546**).

#### Investigation of discrepancy (869 vs 1546)
- The earlier figure of 869 missing values originated from a filtered view that kept only rows where `route_id` was present in `bus_frequency_analysis.csv` (i.e., the active‑route subset).
- When the full `route_cluster_assignments.csv` is examined without that filter, the true missing count is 1,546.
- Therefore the discrepancy is due to the filtering step applied in previous audits, not a data‑source error.

## B. Graph construction comparison
- Edges only in the full graph: **0**
- Edges only in the active‑only graph: **0**
- Shared edges: **11139**

### Edge weight differences for shared edges
- All shared edges have identical weights in both graphs.

- Active‑route IDs used to build the active graph match the set from `bus_frequency_analysis.csv`: **True**
- Because both graphs use the complete set of stop nodes and the active‑only graph only removes edges belonging to inactive routes, the overall topology (node count, component count, isolates) remains the same.

## C. Route 1069
- Trip count for route **1069** in the full dataset: **0**
- Unique stop count for route **1069**: **0**
- Therefore route 1069 does **not** contribute to any singleton cluster; the earlier claim was based on an erroneous assumption.

## D. Sampling overlap
- Sample 42 (seed 42) contains **200** route IDs.
- Sample 24 (seed 24) contains **200** route IDs.
- Intersection size: **11**
- Because the overlap is small, ARI computed on these 11 routes cannot be taken as strong evidence of overall model instability.

## E. Recommendation
- Resolve the missing‑headway handling by retaining indicator columns and imputing only after downstream models have access to the flags.
- Re‑evaluate the suitability of spectral embedding after removing isolated components or switching to a more robust graph embedding method.
- Until those graph issues are addressed, a numeric‑only typology remains the most reliable option.
