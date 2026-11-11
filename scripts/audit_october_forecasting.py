"""Verify expanded scoring populations, released calibration and experimental preview artifacts."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import nbformat

from forecasting import sha256,load_inputs
from forecast_intervals import load_snapshot,monitoring_view

ROOT=Path(__file__).resolve().parents[1]


def run():
    folder=ROOT/'data/processed/new_york/october_validation'
    manifest=json.loads((folder/'october_manifest.json').read_text())
    for name,info in manifest['products'].items():
        assert sha256(folder/f'{name}.csv')==info['sha256'],name
    for name,digest in manifest['protected_files'].items():
        assert sha256(ROOT/name)==digest,name
    assert sha256(folder/'protocol.json')==manifest['protocol_sha256']
    profile=json.loads((folder/'experimental_profile.json').read_text())
    assert profile==manifest['experimental_profile']
    assert sha256(folder/'experimental_profile.json')==manifest['experimental_profile_sha256']
    source,summary=load_snapshot(ROOT,manifest['summary']['snapshot'])
    original,routes=load_inputs(ROOT)
    daily,_=monitoring_view(original,source,routes)
    lookup=daily.set_index(['bus_route','payment_date']).analysis_boardings
    primary=pd.read_csv(folder/'additional_october_predictions.csv',dtype={'bus_route':'string'},parse_dates=['payment_date','origin','availability_cutoff'])
    assert not primary.payment_date.between('2026-10-05','2026-10-11').any()
    assert primary.payment_date.max()==pd.Timestamp('2026-10-21')
    assert primary.groupby('model').size().eq(574).all()
    scored=pd.read_csv(folder/'additional_october_scores.csv').set_index('model')
    for name,part in primary.groupby('model'):
        actual=lookup.reindex(pd.MultiIndex.from_frame(part[['bus_route','payment_date']])).to_numpy()
        np.testing.assert_allclose(actual,part.actual)
        error=part.prediction-part.actual
        np.testing.assert_allclose([error.abs().mean(),np.sqrt((error**2).mean()),error.abs().sum()/part.actual.sum(),error.mean()],
            scored.loc[name,['mae','rmse','wape','bias']].to_numpy(dtype=float),rtol=1e-12)
        assert part.payment_date.nunique()==14
    selection=pd.read_csv(folder/'selection_scores.csv').sort_values(['mae','model'])
    assert selection.iloc[0].model==profile['challenger_strategy']
    for name in ['selection_audit','warmup_audit','context_audit']:
        audit=pd.read_csv(folder/f'{name}.csv',parse_dates=['origin','cutoff','last_training_target'])
        assert audit.last_training_target.le(audit.cutoff).all()
        assert audit.cutoff.eq(audit.origin-pd.Timedelta(days=15)).all()
    assert pd.Timestamp(manifest['summary']['selection_last_target'])<pd.Timestamp('2026-06-07')
    warmup=pd.read_csv(folder/'warmup_predictions.csv',parse_dates=['origin','payment_date'])
    context=pd.read_csv(folder/'context_predictions.csv',parse_dates=['origin','payment_date'])
    residuals=pd.concat([warmup,context.loc[context.model.isin(warmup.model.unique())]],ignore_index=True)
    audit=pd.read_csv(folder/'calibration_audit.csv',parse_dates=['origin','available_cutoff','first_calibration_target','last_calibration_target'])
    for row in audit.itertuples():
        pool=residuals.loc[residuals.model.eq(row.model)&residuals.payment_date.le(row.available_cutoff)
            &residuals.payment_date.ge(row.available_cutoff-pd.Timedelta(days=55))]
        if not row.global_fallback:
            day=np.where(pool.payment_date.dt.dayofweek<5,0,pool.payment_date.dt.dayofweek)
            pool=pool.loc[day==row.day_group]
        assert len(pool)==row.calibration_rows
        assert pool.payment_date.max()==row.last_calibration_target<=row.available_cutoff
        values=np.sort(((pool.actual-pool.prediction)/pool.prediction.clip(lower=100)).to_numpy())
        n=len(values)
        lo=int(np.floor((n+1)*(1-row.level)/2));hi=int(np.ceil((n+1)*(1-(1-row.level)/2)))
        np.testing.assert_allclose([values[lo-1],values[hi-1]],[row.lower_quantile,row.upper_quantile])
    ranges=pd.read_csv(folder/'additional_october_intervals.csv')
    coverage=pd.read_csv(folder/'interval_coverage.csv').set_index(['model','level'])
    for key,part in ranges.groupby(['model','level']):
        assert len(part)==574 and part.lower.ge(0).all() and part.upper.ge(part.lower).all()
        empirical=part.actual.between(part.lower,part.upper).mean()
        assert np.isclose(empirical,coverage.loc[key,'coverage'])
    previews={}
    for path in sorted((ROOT/'data/processed/new_york/forecast_previews').glob('*/preview_manifest.json')):
        info=json.loads(path.read_text())
        if 'code_hashes' in info and info['profile_sha256']==sha256(folder/'experimental_profile.json'):
            previews[info['preview_mode']]=(path.parent,info)
    assert set(previews)=={'reference','challenger'}
    for mode,(path,info) in previews.items():
        assert sha256(path/'point_forecasts.csv')==info['point_sha256']
        assert sha256(path/'empirical_ranges.csv')==info['range_sha256']
        assert sha256(path/'calibration_audit.csv')==info['calibration_audit_sha256']
        points=pd.read_csv(path/'point_forecasts.csv',parse_dates=['payment_date','availability_cutoff','max_history_date'])
        issue=pd.Timestamp(info['generated_utc'])
        assert pd.Timestamp(info['source_observed_utc'])<=issue<points.payment_date.min().tz_localize('America/New_York')
        assert len(points)==287 and points.prediction.ge(0).all()
        assert points.max_history_date.le(points.availability_cutoff).all()
        for name,digest in info['upstream_hashes'].items():assert sha256(ROOT/'data/processed/new_york'/name)==digest
        for name,digest in info['code_hashes'].items():assert sha256(ROOT/'scripts'/name)==digest
        empirical=pd.read_csv(path/'empirical_ranges.csv')
        assert set(empirical.level.unique())==set(info['range_levels_available'])
        if info['last_training_target']:
            assert pd.Timestamp(info['last_training_target'])<=points.availability_cutoff.iloc[0]
        assert not info['operationally_accepted'] and not info['registered_for_prospective_scoring']
    notebook=nbformat.read(ROOT/'notebooks/new_york/08_october_validation.ipynb',as_version=4)
    nbformat.validate(notebook)
    codes=[cell for cell in notebook.cells if cell.cell_type=='code']
    assert [cell.execution_count for cell in codes]==list(range(1,len(codes)+1))
    assert all(cell.outputs and not any(o.output_type=='error' for o in cell.outputs) for cell in codes)
    result={'products_verified':len(manifest['products']),'protected_original_files_unchanged':len(manifest['protected_files']),
        'primary_route_dates_per_candidate':574,'primary_target_dates':14,'prior_october_targets_excluded':True,
        'selection_before_assessment':True,'calibration_quantiles_independently_checked':len(audit),
        'preview_modes_verified':list(previews),'preview_rows_each':287,
        'code_cells':len(codes),'saved_outputs':sum(len(c.outputs) for c in codes),
        'operational_acceptance_claimed':False}
    (ROOT/'reports/october_validation/audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':run()
