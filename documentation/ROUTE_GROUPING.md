# Exploratory route grouping

Route profiles and clustering are complete as an exploratory peer-comparison layer.
**The groups are representation-dependent and are not an established route taxonomy,
crowding classification or service recommendation.** Forecasting decisions and prospective
registrations remain unchanged.

[Notebook 09](../notebooks/new_york/09_route_profiles_and_clustering.ipynb) contains the
editable analysis, saved outputs, figures, interpretation and product-generation cells.

## Population and observations

The analysis covers all 41 routes in the historical Manhattan case, combining directions.
The fixed observation window is 6 July–27 September 2026, twelve complete calendar weeks
within the hourly boarding pilot. A common date must have every route, eligible historical
schedule context, known nonnegative service, available demand, 24 distinct valid clock hours
and reconciled hourly/daily boarding totals.

Of 84 calendar dates, **78 qualify: 57 weekdays, 11 Saturdays and 10 Sundays**, producing
**3,198 route/date members**. One demand-review date and five dates lacking complete schedule
eligibility are withheld for the whole network. The common-date policy loses some otherwise
usable individual-route observations but prevents different observation periods driving groups.

Known zero boardings and known zero service remain observations. M98 has positive published
boardings on some known-zero-service dates; a separate service-alignment flag retains that
unresolved question. It is not interpreted as missing bus operations or corrected automatically.

## Representation and model comparison

The five inputs are:

1. Log of one plus mean weekday boardings.
2. Equal-weight Saturday/Sunday mean boardings divided by weekday mean boardings.
3. Weekday boarding share in 07:00–10:00 and 16:00–19:00.
4. Log of one plus mean weekday scheduled bus-hours.
5. Equal-weight Saturday/Sunday scheduled bus-hours divided by weekday mean bus-hours.

Robust scaling centres each input at its median and scales by its interquartile range.
Multipliers of 1/√3 for the three demand dimensions and 1/√2 for the two service dimensions
give the blocks equal nominal squared weight. Correlations remain visible. Structural
September-snapshot features and boarding/service ratios are context, not duplicate model inputs.

KMeans compares k=2–5 with 30 initializations and seed 42. The predeclared rule chooses the
smallest k within 0.02 of the best silhouette among candidates with at least four routes per
group. These are pragmatic descriptive rules, not operational acceptance standards.

| k | Silhouette | Group sizes | Size screen |
|---:|---:|---|---|
| 2 | 0.501 | 6, 35 | Pass; selected |
| 3 | 0.312 | 1, 16, 24 | Fail |
| 4 | 0.404 | 1, 6, 6, 28 | Fail |
| 5 | 0.340 | 1, 1, 5, 14, 20 | Fail |

Group IDs are ordered by median weekday boardings for readability, not priority.

| Group | Routes | Median weekday boardings | Weekend demand / weekday | Median weekday bus-hours | Representative |
|---|---:|---:|---:|---:|---|
| G01 | 6 | 1,352 | 119% | 86.0 | M20 |
| G02 | 35 | 6,584 | 57% | 144.4 | M79+ |

These are medians of individual route features, not pooled network demand/service ratios.
The representative is the actual route closest to the fitted centre.

## Stability and the qualification that matters

All **80 whole-week bootstrap refits** succeed. Every refit resamples the shared calendar
weeks, recomputes profiles, refits the scaler and refits KMeans at the frozen k.
Median adjusted Rand index (ARI) against the primary partition is **0.877**. Independently
refitting the first and last six-week halves gives ARI **0.724**.

Six routes require membership review under retention below 0.8, distance margin below 0.1
or negative silhouette. Five belong to the smaller group, whose median silhouette is only
0.224 and median bootstrap retention 0.763. The larger group dominates the aggregate silhouette.
Retention is an aligned assignment frequency, not a probability that a label is correct.

**Time resampling does not resolve representation sensitivity.** Standard scaling gives ARI
**0.037** relative to the primary grouping. Demand-only features give ARI **0.216**, and
dropping either weekend ratio can change the result substantially. All five tested DBSCAN
settings find one dense group plus between 2 and 21 unassigned routes. Noise is not a bad-route
label, and assigned-only density silhouettes are not comparable to full-cohort KMeans scores.

Keep the grouping as an optional exploratory view alongside the original profiles and
sensitivity tables. Do not treat it as a stable natural classification, assign efficiency
labels from it or use it to trigger service changes.

## Products and verification

Local products are under `data/processed/new_york/route_clustering/`. They include 20 tables,
the fitted trusted local model, input/scaler/centre parameters, route/group descriptions,
date coverage and stability assignments. Seven figures are exported under
`reports/route_clustering/figures/` and embedded in the notebook.

The manifest records input/code/runtime identities and verifies earlier products and notebooks
remain unchanged. The independent audit reconciles source/member totals, profile arithmetic,
scaling, distances, assignments, metrics, all saved bootstrap partitions and sensitivity scores.

The verified fresh-kernel notebook has **13 executed code cells, 35 saved outputs and seven
figures**. All **50 tests pass**. The audit verifies 28 products and **144 earlier files unchanged**,
including the preceding notebooks, forecast products and prospective registrations.

```powershell
python scripts/execute_notebooks.py notebooks/new_york/09_route_profiles_and_clustering.ipynb --kernel python3
python scripts/audit_route_clustering.py
python -m unittest discover -s tests -v
```

The subsequent [review workflow](ROUTE_REVIEW.md) provides matched dates, sample sizes,
quality flags and independently stated reasons. Group IDs remain descriptive context.
The interface and scenario work are separate milestones.

Method references: [KMeans](https://scikit-learn.org/1.8/modules/generated/sklearn.cluster.KMeans.html),
[DBSCAN](https://scikit-learn.org/1.8/modules/generated/sklearn.cluster.DBSCAN.html),
[clustering evaluation](https://scikit-learn.org/1.8/modules/clustering.html#clustering-performance-evaluation).
