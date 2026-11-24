# Missing‑Headway Cross‑Tabulation Correction

## Data verification
- Total original rows: **4611**
- Active filtered rows: **3934**
- Inactive rows: **677**
- Missing weekday headway (full dataset): **1546**
- Missing weekend headway (full dataset): **1546**
- Missing weekday headway (active dataset): **869**
- Missing weekend headway (active dataset): **869**

## Correct cross‑tab (active routes only)

| Trip‑count category | # routes | Missing weekday headway | Missing weekend headway | Non‑missing weekday headway | Non‑missing weekend headway |
|---------------------|----------|------------------------|-------------------------|----------------------------|-----------------------------|
| Missing trip count | nan | nan | nan | nan | nan |
| 0 trips | nan | nan | nan | nan | nan |
| 1 trip | 869.0 | 869.0 | 869.0 | 0.0 | 0.0 |
| 2-5 trips | 1547.0 | 0.0 | 0.0 | 1547.0 | 1547.0 |
| 6-10 trips | 623.0 | 0.0 | 0.0 | 623.0 | 623.0 |
| >10 trips | 895.0 | 0.0 | 0.0 | 895.0 | 895.0 |

## Totals check
- Sum of routes across categories: **3934.0** (should equal active rows **3934**)
- Sum of missing weekday headway counts: **869.0** (should equal active missing **869**)
- Sum of missing weekend headway counts: **869.0** (should equal active missing **869**)

## Explanation of previous discrepancy
The earlier cross‑tab used the *full* `route_cluster_assignments.csv` which contains all routes (active + inactive). Only the 3,934 active routes should be considered for the typology; the remaining 677 rows belong to inactive routes and were inadvertently retained, inflating the row count.
