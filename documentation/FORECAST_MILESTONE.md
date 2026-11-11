# Forecasting milestone decision

This records the frozen notebooks 05–07 checkpoint. The subsequent
[extended October assessment](OCTOBER_VALIDATION.md) adds further historical evidence and
an experimental preview interface without changing the original forecasts or acceptance policy.

**Research deliverable: complete for review. Operational deployment: not accepted.**

The completed work covers reproducible daily demand experiments, baseline comparisons, interval
calibration, error analysis, later-acquired outcomes and prospective registrations. It does not
establish a reliably superior operational model. **The four-week seasonal mean remains the
reference; no boosted or anchored candidate is promoted.**

This decision consolidates [notebook 05](../notebooks/new_york/05_demand_forecasting.ipynb),
[notebook 06](../notebooks/new_york/06_forecast_validation.ipynb) and
[notebook 07](../notebooks/new_york/07_forecast_error_analysis.ipynb). Together they retain
**36 executed code cells, 132 saved outputs and 11 figures**. The scope is a fixed cohort of
**41 Manhattan routes**, forecasting seven daily published boarding totals per route, combining
directions. Schedules support separate descriptive analysis; they are not forecast predictors.

## Consolidated evidence

Each row below is a separate same-population model/baseline comparison. Different dates, maturity
rules, models and calibration samples prevent pooling these scores or isolating one causal change.
MAE is boardings per route/day; positive improvement favors the candidate.

| Experiment | Scored target dates | Route/dates | Holdback | Candidate MAE | Baseline MAE | MAE improvement |
|---|---|---:|---:|---:|---:|---:|
| 05: 31-leaf model, retrospective test | 3 August–27 September 2026 | 2,255 | 7 days assumed | 615.06 | 630.78 | +2.49% |
| 06: 15-leaf model, maturity-aware evaluation | 7–27 September 2026 | 861 | 14 days | 903.44 | 1,008.43 | +10.41% |
| 06: preserved October forecast, later-acquired outcomes | 5–11 October 2026 | 287 | 7 days assumed | 1,038.44 | 682.40 | -52.17% |
| 07: anchored blend, earlier development assessment | 13 October–23 November 2025 | 1,722 | 14 days | 437.20 | 430.75 | -1.50% |

The initial test gain is not consistent across weeks/months. The later October outcome check favors
the baseline. The anchored blend improves on the direct model in its earlier replay, but does not
beat the baseline by the declared MAE criterion. Lower RMSE or near-zero aggregate bias does not
justify switching the criterion after assessment. Existing observations and candidates are retained.

### Uncertainty

| Interval experiment | Nominal 80% coverage | Nominal 90% coverage | Interpretation |
|---|---:|---:|---|
| 06: September 2026 symmetric bands | 45.53% | 62.83% | Substantial undercoverage |
| 07: earlier symmetric bands | 94.08% | 97.04% | Overcoverage; broad bands |
| 07: earlier asymmetric bands | 88.44% | 94.83% | Narrower, but still retrospective |

Interval calibration is implemented, but reliable prospective coverage is not established. The
earlier asymmetric result does not replace or repair the 2026 undercoverage. Routes and dates are
dependent, weekly models are refitted, and no distribution-free guarantee is asserted.

## Acceptance criteria and present decision

[Versioned review criteria](FORECAST_ACCEPTANCE.json) are defined on 5 November 2026, before the
registered November target dates. These are engineering thresholds for future matched comparisons,
not a transport-agency SLA, proof of passenger benefit or a rule retrofitted to pass past experiments.

| Review item | Future evidence required | Present status |
|---|---|---|
| Reproducibility | Exact input identities, all checks passing, saved outputs and isolated replay | Completed for the frozen collection |
| Prospective sample | At least 8 distinct mature weekly origins; at least 90% of expected matched route/dates | Pending; 1 origin registered, no scored outcomes |
| Challenger point forecasts | At least 5% pooled MAE improvement, no WAPE deterioration, wins on at least 75% of weeks | Not established |
| Aggregate bias | Absolute aggregate prediction error at most 5% of observed boardings; inspect route/week errors | Not established prospectively |
| Intervals | Each 80%/90% coverage within 5 percentage points of nominal; mean interval score no worse than baseline | Not established; material retrospective failure retained |
| Source availability | Observed input snapshots and forecast registration before targets; exact same scoring population | Registrations checked; older historical vintages unavailable |
| Operational use | Review all above evidence together; no automatic promotion | Not accepted |

The point-skill thresholds govern challenger promotion relative to the reference. A reference
baseline cannot demonstrate skill against itself; deploying it would need its own operational
suitability assessment, including acceptable absolute error and the uncertainty/data checks.

Do not remove difficult routes, zero targets or high-error weeks to satisfy a gate. Report quality
exclusions, coverage, sample sizes, intervals and per-route/per-week errors. A missing outcome is
pending, not zero. Wider intervals alone are not sufficient: interval score penalizes unnecessary
width and missed outcomes. Even passing these engineering gates would require a separate decision
about operational use; occupancy, delays and service-change benefits are outside this target.

## Reproducibility handoff

The exact recorded runtime is **CPython 3.11.9, Windows x64**, with the 51-package runtime closure
in [requirements-forecast.lock.txt](../requirements-forecast.lock.txt). The general
`requirements.txt` is convenient for development; the exact lock is the verification environment.

A full offline replay requires the frozen local collection, supplied separately from Git:

| Input path | Required content |
|---|---|
| `data/raw/new_york/` | Original downloads and receipts referenced by the cleaning manifest |
| `data/raw/new_york_monitoring/20261105T134740Z/` | Validated November snapshot and receipts |
| `data/processed/new_york/` | Cleaning/features and forecast products, manifests, model artifacts and original registrations |

The public notebooks and reports explain the work without running it. Git alone does not contain
the frozen input collection. Fresh downloads from mutable URLs may differ and are not equivalent
to restoring those originals. The replay does not refresh sources or issue replacement forecasts.

With the frozen inputs restored, run from the repository root using the recorded Python version:

```powershell
py -3.11 -m venv .venv-forecast
.\.venv-forecast\Scripts\python.exe -m pip install -r requirements-forecast.lock.txt
.\.venv-forecast\Scripts\python.exe scripts/reproduce_forecasting.py --python .\.venv-forecast\Scripts\python.exe
.\.venv-forecast\Scripts\python.exe scripts/forecast_milestone.py
```

The replay checks the exact package versions and Python patch version, creates an isolated copy
outside the repository, runs the full tests, re-executes notebooks 05–07 in fresh kernels and runs
all three independent forecast audits. It compares **53 generated tables** with the preserved
originals using strict numeric tolerances and verifies the original artifacts remain unchanged.
Existing registrations are copied and reused; the old forecasts are not reissued. Dependency
installation requires network access; analysis of the complete frozen collection is offline.

Logs and replay evidence are retained outside the working repository. A local summary is saved
as `reports/forecast_milestone/reproducibility.json`; the consolidated scorecard and milestone
decision are saved as `reports/forecast_milestone/milestone.json`. Notebook timestamps and Python
pickle layouts are not required to be byte-identical; source identity, predictions, metrics,
calibration, scoring populations and registrations are checked explicitly.

The 5 November verification used a fresh virtual environment with the exact 51-package lock.
All **34 tests passed with zero skips**, all three notebooks and independent audits completed,
and **all 53 regenerated tables were byte-identical** to the originals. The replay began with no
generated forecast tables. **68 original files remained unchanged**, including the notebooks,
forecast artifacts and registrations. This verifies the frozen forecasting pipeline on the tested
Windows/Python environment; it does not establish cross-platform or operational reliability.

## Pending prospective evidence

The registered boosted model and seasonal baseline each predict **287 route/dates for
9–15 November 2026**. Their registrations predate the target period, preserve source/model hashes,
and use only the snapshot already observed on 5 November. They remain unchanged.

There are zero mature prospective outcomes in that frozen snapshot. Under the 14-complete-day
maturity policy the full first window cannot mature before **30 November**, and publication may
be later. This is the earliest first-week result, not completion of the eight-origin review sample.
Additional origins would need separate forecasts registered before their targets; none are
fabricated, backdated or scheduled by this milestone closure.

When later observations are available, collect a new immutable snapshot and score each original
registration with `scripts/evaluate_prospective.py`. Preserve the snapshot used for assessment,
apply the declared quality/maturity rules, and report both candidates on identical eligible rows.
First-seen timestamps do not reconstruct older missing vintages or establish an exact publication
SLA. Research closure therefore retains the pending evaluation and the deployment decision above.
