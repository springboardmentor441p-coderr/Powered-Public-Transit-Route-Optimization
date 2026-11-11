"""Audit the earlier-development boundary, comparison metrics and preserved registrations."""
from pathlib import Path
import json

import nbformat
import numpy as np
import pandas as pd

from forecasting import load_inputs, make_examples, sha256

ROOT=Path(__file__).resolve().parents[1]


def run():
    folder=ROOT/'data/processed/new_york/forecast_error_analysis'
    manifest=json.loads((folder/'error_analysis_manifest.json').read_text())
    summary=manifest['summary']
    for name,item in manifest['products'].items():
        assert sha256(folder/f'{name}.csv')==item['sha256'],name
    for name,digest in manifest['protected_files'].items():
        assert sha256(ROOT/name)==digest,name
    original,routes=load_inputs(ROOT)
    daily=original.loc[original.payment_date.le('2025-11-23')]
    examples=make_examples(daily,routes,pd.date_range('2025-03-03','2025-11-17',freq='W-MON'),14)
    assert examples.payment_date.max().year==2025
    assert examples.max_history_date.le(examples.availability_cutoff).all()
    verified_metrics=0
    predictions={}
    for stage in ['selection','calibration','assessment']:
        rows=pd.read_csv(folder/f'development_{stage}_predictions.csv',dtype={'bus_route':'string'},
                         parse_dates=['payment_date','origin','availability_cutoff'])
        predictions[stage]=rows
        assert rows.payment_date.max()<pd.Timestamp('2026-01-01')
        assert not rows.duplicated(['model','bus_route','payment_date']).any()
        lookup=daily.set_index(['bus_route','payment_date']).analysis_boardings
        actual=lookup.reindex(pd.MultiIndex.from_frame(rows[['bus_route','payment_date']])).to_numpy()
        np.testing.assert_allclose(rows.actual,actual)
        expected=examples.loc[examples.origin.isin(rows.origin.unique()) & examples.actual.notna()
                              & examples.history_eligible]
        for name,part in rows.groupby('model'):
            joined=part.merge(expected,on=['bus_route','payment_date'],validate='one_to_one',suffixes=('','_source'))
            assert len(joined)==len(part)==len(expected)
            if name in ['seasonal_mean4','seasonal_latest']:
                np.testing.assert_allclose(joined.prediction,joined[name])
            if stage!='calibration':
                scores=pd.read_csv(folder/f'development_{stage}_scores.csv').set_index('model')
                error=part.prediction-part.actual
                np.testing.assert_allclose([error.abs().mean(),np.sqrt((error**2).mean()),
                    error.abs().sum()/part.actual.sum(),error.mean()],
                    scores.loc[name,['mae','rmse','wape','bias']].to_numpy(dtype=float),rtol=1e-12)
                verified_metrics+=4
        audit=pd.read_csv(folder/f'development_{stage}_audit.csv',parse_dates=['origin','cutoff','last_training_target'])
        for row in audit.itertuples():
            assert row.cutoff==row.origin-pd.Timedelta(days=15)
            training=examples.loc[examples.payment_date.le(row.cutoff)&examples.actual.notna()&examples.history_eligible]
            assert len(training)==row.train_rows
            assert training.payment_date.max()==row.last_training_target<=row.cutoff
    selection=pd.read_csv(folder/'development_selection_scores.csv').sort_values(['mae','model'])
    assert selection.iloc[0].model==summary['selected_candidate']
    assert predictions['selection'].payment_date.max()<=predictions['calibration'].availability_cutoff.min()
    assert predictions['calibration'].payment_date.max()<=predictions['assessment'].availability_cutoff.min()
    calibration=predictions['calibration'].merge(examples[['bus_route','payment_date','seasonal_mean4']],
        on=['bus_route','payment_date'],validate='one_to_one')
    signed_scores=np.sort(((calibration.actual-calibration.prediction)/calibration.seasonal_mean4.clip(lower=100)).to_numpy())
    for level,(lower,upper) in manifest['signed_calibration']['bounds'].items():
        p=float(level);n=len(signed_scores)
        np.testing.assert_allclose([lower,upper],[signed_scores[int(np.floor((n+1)*(1-p)/2))-1],
            signed_scores[int(np.ceil((n+1)*(1-(1-p)/2)))-1]])
    intervals=pd.read_csv(folder/'development_intervals.csv')
    scores=pd.read_csv(folder/'development_interval_coverage.csv').set_index(['interval_method','level'])
    for key,part in intervals.groupby(['interval_method','level']):
        assert not part.duplicated(['bus_route','payment_date']).any()
        assert part.lower.ge(0).all() and part.upper.ge(part.lower).all()
        coverage=part.actual.between(part.lower,part.upper).mean()
        width=part.upper-part.lower
        score=width+2/(1-part.level)*(part.lower-part.actual).clip(lower=0)+2/(1-part.level)*(part.actual-part.upper).clip(lower=0)
        np.testing.assert_allclose([coverage,width.mean(),score.mean()],
            scores.loc[key,['coverage','mean_width','mean_interval_score']].to_numpy(dtype=float),rtol=1e-12)
    notebook=nbformat.read(ROOT/'notebooks/new_york/07_forecast_error_analysis.ipynb',as_version=4)
    nbformat.validate(notebook)
    codes=[c for c in notebook.cells if c.cell_type=='code']
    assert [c.execution_count for c in codes]==list(range(1,len(codes)+1))
    for cell in codes:
        assert cell.outputs and not cell.metadata.get('jupyter',{}).get('outputs_hidden',False)
        assert not cell.metadata.get('collapsed',False)
        assert all(o.output_type!='error' for o in cell.outputs)
    result={'products_verified':len(manifest['products']),'prior_files_unchanged':len(manifest['protected_files']),
        'development_latest_target':str(examples.payment_date.max().date()),'no_2026_candidate_targets':True,
        'selection_and_calibration_maturity_boundaries_verified':True,'metrics_independently_recomputed':verified_metrics,
        'signed_quantiles_verified':True,'interval_coverage_width_and_score_verified':True,
        'selected_candidate':summary['selected_candidate'],'november_registrations_unchanged':True,
        'code_cells':len(codes),'saved_outputs':sum(len(c.outputs) for c in codes)}
    (ROOT/'reports/forecast_error_analysis/audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':run()
