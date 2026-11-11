# Forecast error analysis and development decisions

See the [consolidated forecasting milestone](FORECAST_MILESTONE.md) for the final research
decision, cross-experiment scorecard, acceptance criteria and reproducibility handoff.

[Notebook 07](../notebooks/new_york/07_forecast_error_analysis.ipynb) examines existing errors
and tests an earlier development candidate. All calculations have saved outputs. Existing forecast
products, notebooks 05/06, and both November registrations remain unchanged and are fingerprinted.

## Observed errors

The experiments have different models, evaluation dates and availability rules, so their errors
are analyzed separately. They cannot isolate the causal effect of changing one modelling choice.

- In notebook 06's maturity-14 September window, the model beats its baseline on **36 of 41 routes**.
  The largest positive route losses include M125, M55, M72, M35 and M5; these are prediction
  comparisons, not evidence that those bus services are inefficient.
- The older, preserved October model underpredicts the total by **15.88%**. Its baseline also
  underpredicts, but performs better on that separate window. This does not establish that the
  newer registered model will behave the same way.
- On the newer September evaluation, average model bias is about **-1,114 boardings** on Thursday
  and **-930** on Friday, compared with **+248** on Sunday. Monday-only issue dates confound
  horizon and weekday; these are not isolated lead-time effects.
- **473 of 861** evaluation observations exceed the available seasonal mean by more than 10%.
  For the 229 observations exceeding it by more than 25%, model bias averages **-1,561 boardings**;
  the baseline also underpredicts. This ratio uses the actual outcome and is excluded from features.
  The plotted growth ratio and residual share the actual target, so their negative association is
  partly algebraic; it is not independent evidence of drift or a causal model-failure mechanism.
- Of the nominal 90% intervals, **28.69%** of outcomes lie above the upper bound and **8.48%**
  below the lower bound. The evaluation 90th percentile of scaled absolute error is **0.3723**,
  compared with **0.2148** during calibration. The older residual distribution did not describe
  the later one; the source does not establish why.

Available seasonal history can miss sudden demand changes, and direct tree predictions can shrink
large boarding totals. These are plausible modelling mechanisms, not verified explanations of
school, weather, route, fare or operational changes. Such causes require independent observations.

## Earlier development experiment

All revised-candidate input rows end **23 November 2025**. The later 2026 outcomes are used only
for the diagnostic sections; no 2026 observation enters candidate fitting, scoring or calibration.
The design was motivated by those already-observed errors, so this replay is retrospective
development and not independent confirmation. The fixed route cohort and revised source values
also do not reconstruct historical point-in-time knowledge.

| Stage | Weekly origins | Last target | Maturity boundary |
|---|---|---|---|
| Selection | 7 July–25 August 2025 | 31 August | Available by first calibration cutoff |
| Calibration | 15–22 September 2025 | 28 September | Available by first assessment cutoff |
| Assessment | 13 October–17 November 2025 | 23 November | Weekly refits use released targets only |

Every fit excludes 14 complete dates before issuance. Predictions use exact-date available lags,
and all candidates share the same scored population. The candidate family is fixed before selection:
two seasonal baselines, the existing 15-leaf direct model, an anchored ratio model and a fixed
50/50 ratio-model/seasonal-mean blend. Both tree models use 120 iterations, learning rate 0.06,
15 leaves, leaf minimum 30, L2 penalty 1, no random early stopping and seed 42.

The anchored model fits actual boardings divided by max(available seasonal mean, 100), then converts
back to boarding units. Its predictors are route/calendar variables, log scale and normalized lag
patterns. Targets never enter the predictors. The ratio loss changes the fitting emphasis across
route sizes; final selection and all reported scores use boarding units.

Selection chose **anchored_blend_50**, with MAE **389.41**, versus baseline **413.65**. That choice
was frozen before calibration or assessment.

| Later assessment candidate | MAE, boardings/route/day | RMSE | WAPE | Signed bias |
|---|---:|---:|---:|---:|
| Seasonal mean | 430.75 | 648.77 | 7.48% | +58.03 |
| Selected anchored blend | 437.20 | 638.62 | 7.59% | -2.08 |
| Direct boosted model | 522.95 | 785.54 | 9.08% | -168.31 |
| Anchored ratio model | 538.54 | 836.25 | 9.35% | -62.20 |
| Latest seasonal observation | 583.18 | 922.24 | 10.13% | -18.14 |

There are **1,722 route/date observations** across six assessment origins. The selected blend
reduces MAE by **16.39%** relative to the direct model, but is **1.50% worse than the baseline**.
Its near-zero aggregate bias can conceal offsetting errors. RMSE improves slightly over the baseline,
but MAE was the declared selection metric; the assessment does not justify changing the winner
criterion or promoting the blend. Baselines remain a serious reference for the application.

## Earlier interval comparison

Both methods use the same selected point predictor, the same **574** released calibration rows,
and a fixed 100-boarding normalization floor. Symmetric bands use absolute residual quantiles.
Asymmetric bands use separate signed-residual tail ranks, preserving calibration asymmetry.
No assessment outcome changes these bounds. Neither method has an exchangeability-based guarantee
for the dependent, repeatedly refitted route series.

| Method | Nominal level | Achieved coverage | Mean width | Mean interval score |
|---|---:|---:|---:|---:|
| Symmetric absolute | 80% | 94.08% | 2,979.20 | 3,106.86 |
| Asymmetric signed | 80% | 88.44% | 2,704.92 | 2,992.73 |
| Symmetric absolute | 90% | 97.04% | 4,063.71 | 4,185.43 |
| Asymmetric signed | 90% | 94.83% | 3,660.77 | 3,864.95 |

Signed 90% bands are about **9.91% narrower** and have a lower interval score in this replay.
Both methods overcover relative to the nominal levels here. This result does not repair or replace
the poor 2026 interval evaluation, and is not evidence of calibrated prospective coverage.

## Decisions

1. Preserve the original November model and baseline forecasts and evaluate both after maturity.
2. Keep the seasonal mean as a preferred simple reference; do not promote a complex candidate
   whose later MAE fails to beat it.
3. Treat seasonal anchoring and asymmetric residual bands as development candidates. Any further
   selection or route-specific switching must use already-released outcomes, with rules fixed before
   the next independently evaluated forecast period.
4. Acquire source vintages and independently verified route/calendar context before attributing
   demand changes to operational causes. Do not use realized growth as a predictor or switch rule.
5. Report route, weekday, issue-week, coverage and width diagnostics alongside aggregate scores.
   Forecasting does not supply occupancy, delay, route-efficiency labels or operational savings.

To reproduce after notebooks 05/06 have generated their frozen products:

```powershell
python scripts/execute_notebooks.py notebooks/new_york/07_forecast_error_analysis.ipynb
python scripts/audit_forecast_error_analysis.py
python -m unittest discover -s tests -v
```

Derived tables and the manifest are local in `data/processed/new_york/forecast_error_analysis/`;
six figures and a summary are in `reports/forecast_error_analysis/`. Downloaded data, local audits
and model registrations remain excluded from Git. The notebook provides the saved public evidence.
