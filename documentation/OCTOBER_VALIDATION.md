# Extended October validation and experimental forecasting

The forecasting component is sufficient for a **labelled research preview and comparison feature**.
It supports a transparent seasonal reference and an optional earlier-selected fitted challenger,
with input guards and saved evidence. **Operational use remains unaccepted.** The existing
prospective review policy and November registrations are unchanged.

[Notebook 08](../notebooks/new_york/08_october_validation.ipynb) extends the frozen research
milestone; it does not replace the historical findings in notebooks 05–07.

## Fixed assessment design

- Selection uses eight origins, 2 March–20 April 2026, with targets ending 26 April.
- Candidate names, model settings, annual adjustments and interval settings are fixed before scoring.
- Warm-up out-of-sample residuals begin 22 June, after selection outcomes are mature.
- Context origins span 31 August–19 October; the last origin has only three mature target dates.
- The 5 November snapshot supplies outcomes through 27 October, but scoring stops at **21 October**
  under the 14-complete-day maturity policy.
- All mature October outcomes comprise **861 route/date observations**. Excluding the already-scored
  5–11 October window leaves **574 additional observations**: 1–4 and 12–21 October, across 41 routes.
- Every model uses the same primary population. Published zeros remain zeros and immature outcomes
  are not scored. Earlier outcomes may enter later fits only after the declared release/maturity cutoff.

The data was downloaded after the historical issue dates, some periods were already examined, and
historical publication vintages remain unavailable. This is retrospective validation, not prospective
evidence. The primary sample has only 14 target dates across parts of three issue weeks; correlated
route/date rows must not be treated as independent weeks of operational evidence.

## Candidate comparisons

The two added annual candidates align to the same weekday 364 days earlier. A ratio of sums over
up to 28 released recent dates and their prior-year matches adjusts route demand levels. At least
14 paired dates and a positive denominator are required; growth is constrained to 0.5–2.0.
Federal-holiday mismatches or unavailable annual history fall back to the weekly seasonal mean.
These are demand proxies, not proof that routes or agency calendars are unchanged.

The best earlier selection benchmark is **anchored_ratio_15**. The best deterministic proposal is
**annual_blend_50**, but that proposal subsequently loses to the fixed seasonal reference. It is
reported as a negative result and is not made the preview default.

| Fixed candidate | Additional October MAE | WAPE | Mean signed error |
|---|---:|---:|---:|
| Direct boosted model | 597.56 | 9.76% | -368.85 |
| Earlier-selected anchored ratio | 631.83 | 10.32% | -530.38 |
| Anchored 50/50 blend | 636.08 | 10.39% | -510.47 |
| Latest seasonal observation | 643.56 | 10.51% | -353.71 |
| Seasonal mean reference | 669.34 | 10.93% | -490.56 |
| Annual/weekly blend proposal | 697.33 | 11.39% | -607.06 |
| Scaled annual observation | 805.81 | 13.16% | -723.56 |

The earlier-selected anchored challenger reduces MAE by **5.60%** relative to the reference on
the additional sample. The direct model has the lowest October error, but is not selected after
looking at those outcomes. No parameters, weights or candidate choices are retuned on October.
The challenger still underpredicts in aggregate and does not satisfy the operational acceptance
policy merely by showing one historical gain.

## Rolling uncertainty

Residual quantiles use the most recent 56 **released** target dates, ending at each issue cutoff.
Signed errors are divided by max(issued point prediction, 100). Weekdays, Saturday and Sunday are
separate calibration groups, with global fallback below 100 observations. Lower/upper residual
ranks are fixed before evaluation and bounds are clipped at zero. Dependence, revision and shift
prevent a distribution-free guarantee.

| Strategy | Nominal level | Achieved primary coverage | Mean width | Preview treatment |
|---|---:|---:|---:|---|
| Seasonal mean reference | 80% | 75.96% | 2,286.71 | Empirical experimental range |
| Seasonal mean reference | 90% | 87.11% | 3,141.30 | Empirical experimental range |
| Anchored challenger | 80% | 74.22% | 1,865.92 | Withheld: outside 5-percentage-point screen |
| Anchored challenger | 90% | 84.49% | 2,562.23 | Withheld: outside 5-percentage-point screen |

The historical screen controls display, not operational acceptance. It does not guarantee future
coverage. Existing poor interval results remain visible. No bound is widened after observing these
assessment outcomes to manufacture a passing score. Point forecasts can be shown without a claimed
confidence range, with their experimental status explicit.

## Use the component

After restoring the frozen inputs and running notebook 08:

```powershell
python scripts/forecast_preview.py --mode reference
python scripts/forecast_preview.py --mode challenger
python scripts/audit_october_forecasting.py
```

The reference mode is the default. Both modes generate seven future daily route totals, starting
tomorrow unless a future `--target-start YYYY-MM-DD` within seven days is supplied. The actual
issue timestamp determines the maturity cutoff; a future target start cannot grant access to
later observations. The cutoff is also capped by the snapshot's observation date, so an unrevised
cached value cannot become mature merely because it is read later. The fitted challenger trains
only on released targets. Source timestamps,
data hashes, code hashes, package versions, strategy and forecast hashes are saved.

The component withholds forecasts for an unobserved snapshot, missing minimum seasonal history,
an invalid target date or mature history more than seven days stale. These guards are technical
research controls, not a publisher SLA. A stale frozen snapshot must be replaced by a separately
validated monitoring capture before creating a current preview.

Outputs are local under `data/processed/new_york/forecast_previews/<timestamp>/`: point forecasts,
any eligible empirical ranges, a calibration audit and metadata. The 5 November run generated
287 forecasts per mode for **6–12 November 2026**, with history bounded by 21 October. These are
experimental previews, not replacement registrations or measured prospective performance.

## Sufficiency decision

Completed capabilities are historical comparison, a reproducible forecast interface, source/maturity
guards, conservative range display, saved notebook outputs and independent metric/calibration checks.
All 41 tests pass, including future-data mutation, calibration cutoff, missing annual-history fallback,
stale-input rejection and actual-issue-cutoff checks.

This is sufficient to use forecasting in an explicitly experimental analysis prototype. It is not
sufficient to claim dependable operational accuracy, robust interval calibration, route efficiency,
occupancy or benefits from changing service. Keep the reference as default and the fitted strategy
as a challenger. The original November model/baseline registrations remain the authoritative future
comparison, and the prospective acceptance criteria are not waived.
