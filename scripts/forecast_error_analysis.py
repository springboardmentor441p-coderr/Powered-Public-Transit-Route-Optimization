"""Paired forecast diagnostics and seasonal-anchored development candidates."""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from forecasting import BASELINES, fit_model, predict, training_rows, issue_cutoff

CANDIDATES = ['seasonal_latest', 'seasonal_mean4', 'boosted_15',
              'anchored_ratio_15', 'anchored_blend_50']
ANCHOR_FLOOR = 100.0
RATIO_FEATURES = ['route_code', 'weekday', 'month', 'day_of_year_sin',
                  'day_of_year_cos', 'federal_holiday', 'log_seasonal_scale',
                  'latest_ratio', 'seasonal_cv', 'lag_ratio_1', 'lag_ratio_2',
                  'lag_ratio_3', 'lag_ratio_4']


def ratio_features(rows):
    """Known-at-issue predictors; never inspect actual outcomes or fitted population statistics."""
    scale = rows.seasonal_mean4.clip(lower=ANCHOR_FLOOR)
    frame = rows[['route_code', 'weekday', 'month', 'day_of_year_sin',
                  'day_of_year_cos', 'federal_holiday']].copy()
    frame['log_seasonal_scale'] = np.log1p(scale)
    frame['latest_ratio'] = rows.seasonal_latest / scale
    frame['seasonal_cv'] = rows.seasonal_std4 / scale
    for i, name in enumerate(['weekly_lag_2', 'weekly_lag_3', 'weekly_lag_4', 'weekly_lag_5'], 1):
        frame[f'lag_ratio_{i}'] = rows[name] / scale
    return frame[RATIO_FEATURES], scale


def candidate_predictions(train, target, names):
    unknown = set(names) - set(CANDIDATES)
    if unknown:
        raise ValueError(f'Unknown candidates: {sorted(unknown)}')
    result = {name: target[name].to_numpy() for name in names if name in BASELINES}
    if 'boosted_15' in names:
        result['boosted_15'] = predict(fit_model(train, 'boosted_15'), target)
    if any(name.startswith('anchored_') for name in names):
        x_train, train_scale = ratio_features(train)
        x_target, target_scale = ratio_features(target)
        model = HistGradientBoostingRegressor(loss='poisson', max_iter=120,
            learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=30,
            l2_regularization=1., categorical_features=[0], early_stopping=False,
            random_state=42)
        with threadpool_limits(limits=2):
            model.fit(x_train, train.actual / train_scale)
            anchored = model.predict(x_target) * target_scale.to_numpy()
        if 'anchored_ratio_15' in names:
            result['anchored_ratio_15'] = anchored
        if 'anchored_blend_50' in names:
            result['anchored_blend_50'] = .5 * anchored + .5 * target.seasonal_mean4.to_numpy()
    for name, values in result.items():
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError(f'Invalid predictions: {name}')
    return result


def development_backtest(examples, origins, names=CANDIDATES, maturity_days=14):
    predictions, audits = [], []
    for origin in pd.DatetimeIndex(origins):
        train = training_rows(examples, origin, maturity_days)
        target = examples.loc[examples.origin.eq(origin) & examples.actual.notna()
                              & examples.history_eligible].copy()
        if target.empty:
            raise ValueError('Empty development evaluation origin')
        cutoff = issue_cutoff(origin, maturity_days)
        assert target.max_history_date.le(cutoff).all()
        values = candidate_predictions(train, target, names)
        for name in names:
            part = target[['bus_route', 'payment_date', 'origin', 'availability_cutoff',
                           'horizon', 'max_history_date', 'actual']].copy()
            part['prediction'], part['model'] = values[name], name
            predictions.append(part)
        audits.append({'origin': origin, 'cutoff': cutoff,
            'last_training_target': train.payment_date.max(), 'train_rows': len(train),
            'scored_rows_per_candidate': len(target)})
        print(f'{origin.date()}: {len(train):,} training / {len(target):,} scored rows', flush=True)
    return pd.concat(predictions, ignore_index=True), pd.DataFrame(audits)


def paired_errors(predictions, model, baseline):
    keys = ['bus_route', 'payment_date', 'origin']
    a = predictions.loc[predictions.model.eq(model), keys+['actual', 'prediction']]
    b = predictions.loc[predictions.model.eq(baseline), keys+['actual', 'prediction']]
    if a.duplicated(keys).any() or b.duplicated(keys).any():
        raise ValueError('Duplicate paired forecast keys')
    joined = a.merge(b, on=keys, suffixes=('_model', '_baseline'),
                     how='outer', validate='one_to_one', indicator=True)
    if not joined['_merge'].eq('both').all():
        raise ValueError('Model and baseline populations differ')
    if not np.allclose(joined.actual_model, joined.actual_baseline, equal_nan=False):
        raise ValueError('Paired forecasts disagree on observed targets')
    joined = joined.drop(columns=['_merge', 'actual_baseline']).rename(columns={'actual_model': 'actual'})
    joined['error_model'] = joined.prediction_model - joined.actual
    joined['error_baseline'] = joined.prediction_baseline - joined.actual
    joined['abs_error_model'], joined['abs_error_baseline'] = joined.error_model.abs(), joined.error_baseline.abs()
    joined['excess_absolute_error'] = joined.abs_error_model - joined.abs_error_baseline
    joined['weekday_number'] = joined.payment_date.dt.dayofweek
    joined['weekday'] = joined.payment_date.dt.day_name()
    return joined


def grouped_errors(pairs, by):
    result = pairs.groupby(by, observed=True).agg(rows=('actual', 'size'),
        actual_total=('actual', 'sum'), model_mae=('abs_error_model', 'mean'),
        baseline_mae=('abs_error_baseline', 'mean'), model_bias=('error_model', 'mean'),
        baseline_bias=('error_baseline', 'mean'),
        model_absolute_error=('abs_error_model', 'sum'),
        baseline_absolute_error=('abs_error_baseline', 'sum'),
        excess_absolute_error=('excess_absolute_error', 'sum'))
    result['model_wape'] = result.model_absolute_error / result.actual_total.replace(0, np.nan)
    result['baseline_wape'] = result.baseline_absolute_error / result.actual_total.replace(0, np.nan)
    return result.reset_index()


def calibrate_signed(predictions, examples, cutoff, levels=(.8, .9), floor=100.):
    """Asymmetric residual bands; outcome dates are bounded before quantiles are estimated."""
    if floor <= 0 or any(p <= 0 or p >= 1 for p in levels):
        raise ValueError('Invalid signed calibration settings')
    rows = predictions.loc[predictions.payment_date.le(pd.Timestamp(cutoff))].merge(
        examples[['bus_route', 'payment_date', 'seasonal_mean4']],
        on=['bus_route', 'payment_date'], validate='one_to_one')
    rows = rows.loc[rows.actual.notna() & rows.prediction.notna() & rows.seasonal_mean4.notna()]
    scores = np.sort(((rows.actual-rows.prediction)/rows.seasonal_mean4.clip(lower=floor)).to_numpy())
    if not len(scores) or not np.isfinite(scores).all():
        raise ValueError('No finite released residuals')
    bounds = {}
    for p in levels:
        lower_rank = int(np.floor((len(scores)+1)*(1-p)/2))
        upper_rank = int(np.ceil((len(scores)+1)*(1-(1-p)/2)))
        if lower_rank < 1 or upper_rank > len(scores):
            raise ValueError('Insufficient calibration rows for finite signed bounds')
        bounds[str(p)] = [float(scores[lower_rank-1]), float(scores[upper_rank-1])]
    return {'rows': len(rows), 'cutoff': str(pd.Timestamp(cutoff).date()),
            'last_target': str(rows.payment_date.max().date()), 'floor': floor,
            'bounds': bounds, 'coverage_guaranteed': False}


def signed_intervals(predictions, examples, calibration):
    frame = predictions.merge(examples[['bus_route', 'payment_date', 'seasonal_mean4']],
                               on=['bus_route', 'payment_date'], validate='one_to_one')
    scale = frame.seasonal_mean4.clip(lower=calibration['floor'])
    output = []
    for level, (lower, upper) in calibration['bounds'].items():
        part = frame.copy()
        part['level'] = float(level)
        part['lower'] = (part.prediction+lower*scale).clip(lower=0)
        part['upper'] = (part.prediction+upper*scale).clip(lower=0)
        output.append(part)
    return pd.concat(output, ignore_index=True)
