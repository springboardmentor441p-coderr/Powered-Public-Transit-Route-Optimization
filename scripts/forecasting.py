"""Daily route-demand forecasting with explicit weekly issue dates and availability cutoffs."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

BASELINES = ['seasonal_latest', 'seasonal_mean4']
FEATURES = ['route_code', 'weekday', 'month', 'day_of_year_sin', 'day_of_year_cos',
            'horizon', 'trend_days', 'federal_holiday', 'seasonal_mean4',
            'seasonal_std4', 'seasonal_count', 'seasonal_latest',
            'weekly_lag_2', 'weekly_lag_3', 'weekly_lag_4', 'weekly_lag_5']
CONFIGS = {'boosted_15': 15, 'boosted_31': 31}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_inputs(root):
    folder = Path(root) / 'data/processed/new_york'
    manifest = json.loads((folder / 'cleaning_manifest.json').read_text())
    for name in ['daily_clean', 'route_crosswalk']:
        if sha256(folder / f'{name}.csv') != manifest['products'][name]['sha256']:
            raise ValueError(f'Source product fingerprint mismatch: {name}')
    daily = pd.read_csv(folder / 'daily_clean.csv', dtype={'bus_route': 'string'},
                        parse_dates=['payment_date'])
    routes = sorted(pd.read_csv(folder / 'route_crosswalk.csv', dtype='string').bus_route.unique())
    daily = daily.loc[daily.bus_route.isin(routes)].copy()
    if daily.duplicated(['bus_route', 'payment_date']).any():
        raise ValueError('Duplicate route/date observations')
    return daily, routes


def issue_cutoff(origin, delay_days=7):
    """Issue at 00:00 local time; exclude the preceding delay_days complete dates."""
    if delay_days < 0:
        raise ValueError('Negative publication delay')
    return pd.Timestamp(origin).normalize() - pd.Timedelta(days=delay_days + 1)


def make_examples(daily, routes, origins, delay_days=7):
    """Direct seven-day examples. All demand lookups precede each origin's cutoff."""
    from pandas.tseries.holiday import USFederalHolidayCalendar
    rows = []
    for origin in pd.DatetimeIndex(origins):
        cutoff = issue_cutoff(origin, delay_days)
        for horizon in range(1, 8):
            target = origin + pd.Timedelta(days=horizon - 1)
            lag_weeks = max(1, int(np.ceil((target - cutoff).days / 7)))
            for route in routes:
                rows.append((route, origin, cutoff, target, horizon, lag_weeks))
    frame = pd.DataFrame(rows, columns=['bus_route', 'origin', 'availability_cutoff',
                                      'payment_date', 'horizon', 'first_lag_weeks'])
    lookup = daily.set_index(['bus_route', 'payment_date']).analysis_boardings
    for i in range(4):
        dates = frame.payment_date - pd.to_timedelta((frame.first_lag_weeks + i) * 7, unit='D')
        assert dates.le(frame.availability_cutoff).all()
        frame[f'weekly_lag_{i+2}'] = lookup.reindex(
            pd.MultiIndex.from_arrays([frame.bus_route, dates])).to_numpy()
    lag_cols = [f'weekly_lag_{i}' for i in range(2, 6)]
    frame['max_history_date'] = frame.payment_date - pd.to_timedelta(frame.first_lag_weeks * 7, unit='D')
    frame['seasonal_latest'] = frame[lag_cols].bfill(axis=1).iloc[:, 0]
    frame['seasonal_mean4'] = frame[lag_cols].mean(axis=1)
    frame['seasonal_std4'] = frame[lag_cols].std(axis=1)
    frame['seasonal_count'] = frame[lag_cols].notna().sum(axis=1)
    frame['actual'] = lookup.reindex(pd.MultiIndex.from_frame(frame[['bus_route', 'payment_date']])).to_numpy()
    frame['route_code'] = frame.bus_route.map({r: i for i, r in enumerate(routes)}).astype(int)
    frame['weekday'] = frame.payment_date.dt.dayofweek
    frame['month'] = frame.payment_date.dt.month
    frame['trend_days'] = (frame.payment_date - pd.Timestamp('2025-01-01')).dt.days
    phase = 2 * np.pi * frame.payment_date.dt.dayofyear / 365.25
    frame['day_of_year_sin'], frame['day_of_year_cos'] = np.sin(phase), np.cos(phase)
    holidays = USFederalHolidayCalendar().holidays(frame.payment_date.min(), frame.payment_date.max())
    frame['federal_holiday'] = frame.payment_date.isin(holidays).astype(int)
    frame['history_eligible'] = frame.seasonal_count.ge(2)
    return frame


def fit_model(train, name):
    if name not in CONFIGS:
        raise ValueError(name)
    model = HistGradientBoostingRegressor(
        loss='poisson', max_iter=120, learning_rate=0.06,
        max_leaf_nodes=CONFIGS[name], min_samples_leaf=30,
        l2_regularization=1.0, categorical_features=[0],
        early_stopping=False, random_state=42)
    with threadpool_limits(limits=2):
        model.fit(train[FEATURES], train.actual)
    return model


def predict(model, rows):
    with threadpool_limits(limits=2):
        return model.predict(rows[FEATURES])


def training_rows(examples, origin, delay_days):
    cutoff = issue_cutoff(origin, delay_days)
    rows = examples.loc[examples.payment_date.le(cutoff) & examples.actual.notna()
                        & examples.history_eligible].copy()
    if rows.empty:
        raise ValueError('No eligible training observations')
    assert rows.payment_date.max() <= cutoff
    assert rows.max_history_date.le(rows.availability_cutoff).all()
    return rows


def backtest(examples, origins, names, delay_days=7):
    """Expanding training, weekly refits; each target appears once in a split."""
    results, audits = [], []
    for origin in pd.DatetimeIndex(origins):
        train = training_rows(examples, origin, delay_days)
        test = examples.loc[examples.origin.eq(origin) & examples.actual.notna()
                            & examples.history_eligible].copy()
        if test.empty:
            raise ValueError(f'Empty evaluation week: {origin}')
        audits.append({'origin': origin, 'cutoff': issue_cutoff(origin, delay_days),
                       'train_rows': len(train), 'last_training_target': train.payment_date.max(),
                       'test_rows': len(test), 'first_test_date': test.payment_date.min(),
                       'last_test_date': test.payment_date.max()})
        for name in names:
            out = test[['bus_route', 'origin', 'availability_cutoff', 'payment_date', 'horizon',
                        'max_history_date', 'actual']].copy()
            out['prediction'] = test[name].to_numpy() if name in BASELINES else predict(fit_model(train, name), test)
            out['model'] = name
            results.append(out)
        print(f'Origin {origin.date()}: {len(train):,} training / {len(test):,} scored rows', flush=True)
    return pd.concat(results, ignore_index=True), pd.DataFrame(audits)


def metrics(predictions, group_cols=('model',)):
    output = []
    for keys, part in predictions.groupby(list(group_cols), sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        error = part.prediction - part.actual
        denom = part.actual.sum()
        output.append(dict(zip(group_cols, keys), rows=len(part), routes=part.bus_route.nunique(),
                           mae=float(error.abs().mean()), rmse=float(np.sqrt(np.mean(error**2))),
                           wape=float(error.abs().sum()/denom) if denom else None,
                           bias=float(error.mean()), actual_total=float(denom)))
    return pd.DataFrame(output)
