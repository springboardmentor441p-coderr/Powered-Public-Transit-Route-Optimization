"""Availability-safe annual baselines and rolling residual intervals for an experimental forecast."""
import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from forecasting import training_rows, issue_cutoff
from forecast_error_analysis import CANDIDATES as ORIGINAL_CANDIDATES, candidate_predictions

CANDIDATES = ORIGINAL_CANDIDATES + ['annual_scaled', 'annual_blend_50']
LEVELS = (.8, .9)
MATURITY = 14
CALIBRATION_DAYS = 56
SCALE_FLOOR = 100.


def add_annual_history(examples, daily):
    """Use 364-day weekday alignment and 28 released dates for ratio-of-sums adjustment."""
    rows = examples.copy()
    lookup = daily.set_index(['bus_route', 'payment_date']).analysis_boardings
    if not lookup.index.is_unique:
        raise ValueError('Duplicate source route/date keys')
    annual_date = rows.payment_date - pd.Timedelta(days=364)
    if annual_date.gt(rows.availability_cutoff).any():
        raise ValueError('Annual reference exceeds availability cutoff')
    rows['annual_reference_date'] = annual_date
    rows['annual_value'] = lookup.reindex(pd.MultiIndex.from_arrays([rows.bus_route, annual_date])).to_numpy()
    growth = []
    for (route, cutoff), part in rows.groupby(['bus_route', 'availability_cutoff'], sort=False):
        dates = pd.date_range(cutoff-pd.Timedelta(days=27), cutoff)
        recent = lookup.reindex(pd.MultiIndex.from_product([[route], dates])).to_numpy()
        old = lookup.reindex(pd.MultiIndex.from_product([[route], dates-pd.Timedelta(days=364)])).to_numpy()
        valid = np.isfinite(recent) & np.isfinite(old)
        count = int(valid.sum())
        denom = float(old[valid].sum())
        ratio = float(np.clip(recent[valid].sum()/denom, .5, 2.)) if count >= 14 and denom > 0 else np.nan
        growth.append({'bus_route': route, 'availability_cutoff': cutoff, 'annual_growth_ratio': ratio,
                       'annual_growth_pair_count': count})
    rows = rows.merge(pd.DataFrame(growth), on=['bus_route', 'availability_cutoff'], validate='many_to_one', sort=False)
    holidays = USFederalHolidayCalendar().holidays(annual_date.min(), rows.payment_date.max())
    same_holiday = rows.payment_date.isin(holidays).eq(rows.annual_reference_date.isin(holidays))
    rows['annual_eligible'] = rows.annual_value.notna() & rows.annual_growth_ratio.notna() & same_holiday
    estimate = rows.annual_value * rows.annual_growth_ratio
    rows['annual_scaled'] = estimate.where(rows.annual_eligible, rows.seasonal_mean4)
    rows['annual_blend_50'] = .5*rows.annual_scaled + .5*rows.seasonal_mean4
    return rows


def benchmark(examples, origins, names, asof_cutoff):
    output, audits = [], []
    for origin in pd.DatetimeIndex(origins):
        cutoff = issue_cutoff(origin, MATURITY)
        train = training_rows(examples, origin, MATURITY)
        target = examples.loc[examples.origin.eq(origin) & examples.actual.notna()
                              & examples.history_eligible & examples.payment_date.le(asof_cutoff)].copy()
        if target.empty:
            continue
        originals = [name for name in names if name in ORIGINAL_CANDIDATES]
        values = candidate_predictions(train, target, originals) if originals else {}
        for name in names:
            if name not in CANDIDATES:
                raise ValueError(name)
            prediction = target[name].to_numpy() if name.startswith('annual_') else values[name]
            if not np.isfinite(prediction).all() or (prediction < 0).any():
                raise ValueError('Invalid forecast values')
            part = target[['bus_route', 'origin', 'payment_date', 'availability_cutoff',
                           'max_history_date', 'horizon', 'actual']].copy()
            part['prediction'], part['model'] = prediction, name
            output.append(part)
        audits.append({'origin': origin, 'cutoff': cutoff, 'train_rows': len(train),
                       'last_training_target': train.payment_date.max(), 'target_rows': len(target),
                       'target_dates': target.payment_date.nunique(),
                       'complete_week': target.payment_date.nunique() == 7})
        print(f'{origin.date()}: {len(train):,} training / {len(target):,} scored rows', flush=True)
    return pd.concat(output, ignore_index=True), pd.DataFrame(audits)


def rolling_intervals(predictions, origins, score_cutoff):
    """Use only released prior out-of-sample residuals; fixed day-type groups and 56-date window."""
    intervals, audits = [], []
    for (model, origin), target in predictions.loc[predictions.origin.isin(origins) &
        predictions.payment_date.le(score_cutoff)].groupby(['model', 'origin'], sort=True):
        cutoff = issue_cutoff(origin, MATURITY)
        if 'availability_cutoff' in target:
            available = pd.DatetimeIndex(target.availability_cutoff.unique())
            if len(available) != 1 or available[0] > cutoff:
                raise ValueError('Invalid target availability cutoff')
            cutoff = available[0]
        pool = predictions.loc[predictions.model.eq(model) & predictions.payment_date.le(cutoff)
            & predictions.payment_date.ge(cutoff-pd.Timedelta(days=CALIBRATION_DAYS-1))].copy()
        if pool.empty:
            raise ValueError('No available rolling calibration residuals')
        # Weekdays form one group; Saturday and Sunday are separate.
        pool['day_group'] = np.where(pool.payment_date.dt.dayofweek < 5, 0,
                                    pool.payment_date.dt.dayofweek)
        for group, part in target.groupby(np.where(target.payment_date.dt.dayofweek < 5, 0,
                                                   target.payment_date.dt.dayofweek)):
            chosen = pool.loc[pool.day_group.eq(group)]
            fallback = len(chosen) < 100
            if fallback:
                chosen = pool
            scores = np.sort(((chosen.actual-chosen.prediction)/chosen.prediction.clip(lower=SCALE_FLOOR)).to_numpy())
            if not np.isfinite(scores).all():
                raise ValueError('Invalid residual values')
            for level in LEVELS:
                lo = int(np.floor((len(scores)+1)*(1-level)/2))
                hi = int(np.ceil((len(scores)+1)*(1-(1-level)/2)))
                if lo < 1 or hi > len(scores):
                    raise ValueError('Insufficient released calibration history')
                qlo, qhi = float(scores[lo-1]), float(scores[hi-1])
                out = part.copy()
                scale = out.prediction.clip(lower=SCALE_FLOOR)
                out['level'] = level
                out['lower'] = (out.prediction+qlo*scale).clip(lower=0)
                out['upper'] = (out.prediction+qhi*scale).clip(lower=0)
                intervals.append(out)
                audits.append({'model': model, 'origin': origin, 'level': level, 'day_group': int(group),
                    'available_cutoff': cutoff, 'calibration_rows': len(chosen),
                    'last_calibration_target': chosen.payment_date.max(),
                    'first_calibration_target': chosen.payment_date.min(),
                    'global_fallback': fallback, 'lower_quantile': qlo, 'upper_quantile': qhi})
    return pd.concat(intervals, ignore_index=True), pd.DataFrame(audits)


def point_forecast(rows, name):
    """Supported prototype strategies use validated deterministic historical baselines."""
    if name not in ['seasonal_mean4', 'seasonal_latest', 'annual_scaled', 'annual_blend_50']:
        raise ValueError('Prototype default must be a deterministic, inspectable baseline')
    if not rows.history_eligible.all() or rows[name].isna().any():
        raise ValueError('Insufficient history; forecast withheld')
    if rows.max_history_date.gt(rows.availability_cutoff).any():
        raise ValueError('History exceeds issue cutoff')
    return rows[name].to_numpy()


def preview_rows(daily, routes, source_observed_utc, issued_utc, strategy, target_start=None):
    """Seven future daily point estimates; reject unobserved, stale or insufficient input history."""
    from forecasting import make_examples
    observed, issued = pd.Timestamp(source_observed_utc), pd.Timestamp(issued_utc)
    if observed.tz is None or issued.tz is None or observed > issued:
        raise ValueError('Input snapshot must be observed before issue with timezone-aware timestamps')
    local_issue = issued.tz_convert('America/New_York').tz_localize(None).normalize()
    issue_cutoff_date = local_issue - pd.Timedelta(days=MATURITY+1)
    observed_date = observed.tz_convert('America/New_York').tz_localize(None).normalize()
    cutoff = min(issue_cutoff_date, observed_date-pd.Timedelta(days=MATURITY+1))
    complete = daily.loc[daily.payment_date.le(cutoff) & daily.analysis_boardings.notna()].groupby('payment_date').bus_route.nunique()
    complete = complete.loc[complete.eq(len(routes))]
    if complete.empty or (issue_cutoff_date-complete.index.max()).days > 7:
        raise ValueError('Mature input history is stale or incomplete; refresh data before forecasting')
    origin = pd.Timestamp(target_start).normalize() if target_start is not None else local_issue+pd.Timedelta(days=1)
    if origin <= local_issue or origin > local_issue+pd.Timedelta(days=7):
        raise ValueError('Target start must be a future date within seven days of issue')
    delay = (origin-cutoff).days-1
    rows = add_annual_history(make_examples(daily, routes, [origin], delay), daily)
    rows['prediction'] = point_forecast(rows, strategy)
    rows['strategy'] = strategy
    rows['lead_days_from_issue'] = (rows.payment_date-local_issue).dt.days
    rows['actual'] = np.nan
    return rows
