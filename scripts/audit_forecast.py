"""Independently audit frozen forecast products, timing boundaries and error stability."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import nbformat

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    folder = ROOT / 'data/processed/new_york/forecasting'
    manifest = json.loads((folder / 'forecast_manifest.json').read_text())
    summary = manifest['summary']
    for name, item in manifest['products'].items():
        assert digest(folder / f'{name}.csv') == item['sha256'], name
    for name, expected in manifest['source_hashes'].items():
        assert digest(folder.parent / name) == expected, name
    assert digest(folder / 'selected_model.pkl') == manifest['model_sha256']
    cleaning = json.loads((folder.parent / 'cleaning_manifest.json').read_text())
    for item in cleaning['source_files']:
        assert digest(ROOT / item['file']) == item['sha256'], item['file']

    daily = pd.read_csv(folder.parent / 'daily_clean.csv', dtype={'bus_route': 'string'},
                        parse_dates=['payment_date'])
    lookup = daily.set_index(['bus_route', 'payment_date']).analysis_boardings
    examples = pd.read_csv(folder / 'historical_examples.csv', dtype={'bus_route': 'string'},
        parse_dates=['origin', 'availability_cutoff', 'payment_date', 'max_history_date'])
    assert not examples.duplicated(['bus_route', 'payment_date']).any()
    delay = summary['assumed_publication_delay_days']
    np.testing.assert_array_equal(examples.availability_cutoff,
                                   examples.origin - pd.Timedelta(days=delay+1))
    assert examples.origin.dt.dayofweek.eq(0).all()
    assert ((examples.payment_date-examples.origin).dt.days+1).eq(examples.horizon).all()
    for i in range(2, 6):
        date = examples.payment_date - pd.Timedelta(days=7*i)
        assert date.le(examples.availability_cutoff).all()
        expected = lookup.reindex(pd.MultiIndex.from_arrays([examples.bus_route, date])).to_numpy()
        np.testing.assert_allclose(examples[f'weekly_lag_{i}'], expected, equal_nan=True)
    target = lookup.reindex(pd.MultiIndex.from_frame(examples[['bus_route', 'payment_date']])).to_numpy()
    np.testing.assert_allclose(examples.actual, target, equal_nan=True)
    lags = examples[[f'weekly_lag_{i}' for i in range(2,6)]]
    np.testing.assert_allclose(examples.seasonal_mean4, lags.mean(axis=1), equal_nan=True)
    np.testing.assert_allclose(examples.seasonal_latest, lags.bfill(axis=1).iloc[:,0], equal_nan=True)

    tables = {}
    independent_metrics = []
    for split in ['validation', 'test']:
        p = pd.read_csv(folder / f'{split}_predictions.csv', dtype={'bus_route': 'string'},
            parse_dates=['origin', 'availability_cutoff', 'payment_date', 'max_history_date'])
        assert not p.duplicated(['model', 'bus_route', 'payment_date']).any()
        assert np.isfinite(p.prediction).all() and p.prediction.ge(0).all()
        expected = examples.loc[examples.origin.isin(p.origin.unique()) &
                                examples.actual.notna() & examples.history_eligible]
        keys = ['bus_route', 'payment_date']
        for name, group in p.groupby('model'):
            joined = group.merge(expected, on=keys, suffixes=('', '_input'), validate='one_to_one')
            assert len(joined) == len(expected) == len(group)
            np.testing.assert_allclose(joined.actual, joined.actual_input)
            if name in ['seasonal_latest', 'seasonal_mean4']:
                np.testing.assert_allclose(joined.prediction, joined[name])
            error = group.prediction.to_numpy()-group.actual.to_numpy()
            independent_metrics.append({'split':split,'model':name,'rows':len(group),
                'mae':float(np.abs(error).mean()),'rmse':float(np.sqrt(np.mean(error**2))),
                'wape':float(np.abs(error).sum()/group.actual.sum()),'bias':float(error.mean())})
        audit = pd.read_csv(folder / f'{split}_origin_audit.csv',
            parse_dates=['origin','cutoff','last_training_target','first_test_date','last_test_date'])
        for row in audit.itertuples():
            train = examples.loc[examples.payment_date.le(row.cutoff) & examples.actual.notna()
                                 & examples.history_eligible]
            assert len(train) == row.train_rows
            assert train.payment_date.max() == row.last_training_target <= row.cutoff < row.first_test_date
        tables[split] = p
    independent = pd.DataFrame(independent_metrics)
    for split in ['validation','test']:
        recorded = pd.read_csv(folder / f'{split}_scores.csv').set_index('model')
        checked = independent.loc[independent.split.eq(split)].set_index('model')
        np.testing.assert_allclose(checked.loc[recorded.index,['mae','rmse','wape','bias']],
                                   recorded[['mae','rmse','wape','bias']], rtol=1e-12)
    validation = independent.loc[independent.split.eq('validation')].sort_values(['mae','model'])
    assert validation.iloc[0].model == summary['selected_model']
    assert tables['validation'].payment_date.max() < tables['test'].payment_date.min()

    test = tables['test']
    selected, baseline = summary['selected_model'], summary['best_validation_baseline']
    pair = test.loc[test.model.eq(selected)].merge(test.loc[test.model.eq(baseline)],
        on=['bus_route','payment_date','origin'],suffixes=('_model','_baseline'),validate='one_to_one')
    np.testing.assert_allclose(pair.actual_model,pair.actual_baseline)
    pair['model_error'] = (pair.prediction_model-pair.actual_model).abs()
    pair['baseline_error'] = (pair.prediction_baseline-pair.actual_model).abs()
    weekly = pair.groupby('origin').agg(model_error=('model_error','sum'),
        baseline_error=('baseline_error','sum'),rows=('model_error','size'))
    route = pair.groupby('bus_route')[['model_error','baseline_error']].mean()
    monthly = pair.assign(month=pair.payment_date.dt.to_period('M').astype(str)).groupby('month').agg(
        model_mae=('model_error','mean'),baseline_mae=('baseline_error','mean'),rows=('model_error','size'))
    # Resample whole issue weeks, preserving all routes/days within each sampled cluster.
    # Eight weeks and temporal dependence limit interpretation: this is exploratory stability only.
    rng = np.random.default_rng(42)
    indices = rng.integers(0,len(weekly),size=(10000,len(weekly)))
    improvement = 100*(1-weekly.model_error.to_numpy()[indices].sum(axis=1)/
                       weekly.baseline_error.to_numpy()[indices].sum(axis=1))
    quantiles = np.quantile(improvement,[.025,.975]).tolist()
    notebook = nbformat.read(ROOT/'notebooks/new_york/05_demand_forecasting.ipynb',as_version=4)
    nbformat.validate(notebook)
    code = [c for c in notebook.cells if c.cell_type=='code']
    assert [c.execution_count for c in code] == list(range(1,len(code)+1))
    for cell in code:
        assert cell.outputs and not cell.metadata.get('jupyter',{}).get('outputs_hidden',False)
        assert not cell.metadata.get('collapsed',False)
        assert all(o.output_type!='error' for o in cell.outputs)
    result = {'raw_files_verified':len(cleaning['source_files']),
        'forecast_products_verified':len(manifest['products']),
        'historical_feature_rows_checked':len(examples),'lag_values_checked':len(examples)*4,
        'metrics_recomputed_independently':independent.to_dict(orient='records'),
        'weeks_model_better':int(weekly.model_error.lt(weekly.baseline_error).sum()),'weeks':len(weekly),
        'routes_model_better':int(route.model_error.lt(route.baseline_error).sum()),'routes':len(route),
        'weekly_cluster_resampling_95pct_stability_range_percent':quantiles,
        'stability_replicates':10000,'stability_seed':42,
        'stability_is_not_prospective_or_formal_significance_evidence':True,
        'monthly_errors':monthly.reset_index().to_dict(orient='records'),
        'notebook_code_cells':len(code),'notebook_saved_outputs':sum(len(c.outputs) for c in code)}
    output = ROOT/'reports/forecasting'
    (output/'detailed_review.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    route.to_csv(output/'review_route_errors.csv')
    monthly.to_csv(output/'review_monthly_errors.csv')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    run()
