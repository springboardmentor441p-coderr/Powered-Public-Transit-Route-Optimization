# Explainable historical route review

[Notebook 10](../notebooks/new_york/10_explainable_route_review.ipynb) creates a reproducible
review table with reasons, paired denominators, dates, sample sizes and quality states.
It evaluates all 41 routes, including those with unavailable evidence or no triggered rule.
**This is historical screening, not an efficiency rating, crowding classifier or service decision.**

## What the current table contains

| Workflow state | Routes | Meaning |
|---|---:|---|
| Source clarification | 1 | Verify M98's positive-boardings/zero-scheduled-service cases first |
| Planning review | 22 | At least one explicit historical rule triggered without that source blocker |
| No rule triggered | 18 | Supported comparisons did not trigger these particular rules |
| Insufficient evidence | 0 | No route is wholly unsupported; individual unavailable evaluations remain visible |

The common period is **6 July–27 September 2026**, with **78 eligible dates and 3,198
route/date observations**. All routes use the same dates. Of 246 rule evaluations, 242 are
eligible and four are unavailable. There are **48 triggered evaluations** across 22 routes.
This is a different window and rule set from the original EDA review list; counts should not
be interpreted as an improvement over that earlier list.

M98 has 15 published boardings across three Saturdays and four boardings on one Sunday
with known zero scheduled service. Those four route/date observations are retained for
source clarification; their affected comparisons are withheld. They do not establish missing
bus operations or justify a frequency increase.

## Explicit primary rules

All rates divide summed boardings by summed scheduled bus-hours on exactly the same rows.
Primary support requires 40 weekdays, 8 Saturdays or 8 Sundays, as applicable.

| Family | Reference | Trigger | Primary signals |
|---|---|---|---:|
| Relative service use | Eligible routes within the same day type; at least 10 peers | Lower/upper 10% tails, strictly below/above the median | 13 lower, 13 higher |
| Weekend intensity difference | Own weekday boarding/bus-hour rate | Weekend/weekday rate ≤0.8 or ≥1.25 | 18 lower, 4 higher |
| Weekday intensity change | Own first-six-week weekday rate; at least 20 weekdays in each half | Last/first rate ≤0.8 or ≥1.25 | 0 |

Tail rules select relative extremes by design, even when differences are ordinary.
Capacity, journey lengths, service purpose and passenger destinations are unobserved.
A lower rate does not establish unnecessary service; a higher rate does not establish crowding.
The absence of temporal signals at 1.25 is retained as a negative result.

These are illustrative analyst thresholds, not transport standards or significance tests.
No combined score is calculated. Source clarification precedes planning review; routes are
alphabetical within workflow states. Flag counts are descriptions, not priority weights.
Rows retain keyed links to all rule signals and source observations.

## Sensitivity

Nine settings cross tail quantiles 5%, 10%, 15% with reciprocal ratio bounds based on
1.15, 1.25, 1.50. Planning-queue membership varies from **9 to 31 routes**. The fixed primary
queue remains 22 routes; no alternative is selected to obtain a desired number of flags.

Eighty resamples draw six whole weeks within each six-week half, keeping route demand and
service paired. Profiles, peer thresholds and rules are recomputed every time. An original
signal's retention counts only eligible draws triggering the same direction. Ten signals
have retention below the descriptive 0.8 display threshold. These frequencies measure
within-window sensitivity; they do not establish the probability that service needs changing.

The evidence figure shows flags divided by eligible comparisons. Completely unavailable
cells are grey, preventing unavailable observations from appearing to be zero-signal evidence.

## Context and practical limits

Exploratory groups and membership-review flags from notebook 09 are context only. September
stop/exclusive-stop coverage and overlap identify questions to preserve when reviewing a route,
not opportunities for automatic mergers. Separately dated October forecast errors cover 14
additional target dates and retain experimental status. None of these fields affects a rule.

The review is historical, not a live service monitor. It does not estimate actual delays,
occupancy, fleet feasibility, operating costs, route-change benefits or demand response.
The subsequent [frequency-scenario component](SERVICE_SCENARIOS.md) uses a compatible baseline
and stated assumptions. The Streamlit interface remains separate.

## Products and reproduction

Fifteen tables are local under `data/processed/new_york/route_review/`, with an input/code/runtime
manifest. Six figures are local under `reports/route_review/figures/` and embedded in the notebook.
The complete route table, default planning queue, source queue and full rule table are separate
products so filtering cannot erase unavailable or nontriggered cases.

```powershell
python scripts/execute_notebooks.py notebooks/new_york/10_explainable_route_review.ipynb --kernel python3
python scripts/audit_route_review.py
python -m unittest discover -s tests -v
```

The independent audit rebuilds paired totals, rates, primary rules, all nine threshold settings
and all 80 stratified week resamples without importing the rule implementation. It checks
queue states, evidence links, forecast context, output hashes and earlier-artifact preservation.

The executed notebook contains **12 code cells, 33 saved outputs and six figures**.
The 60-test suite passes; focused rule tests also pass after the final explanation changes.
The audit verifies 21 products and **174 earlier artifacts unchanged**, including notebooks
01–09, forecast products and registrations. No source values, model decisions or service
changes are made by this milestone.
