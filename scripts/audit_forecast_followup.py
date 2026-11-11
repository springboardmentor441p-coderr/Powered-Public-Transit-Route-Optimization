"""Verify interval evaluation, preserved outcomes and pre-target forecast registrations."""
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import nbformat
from forecasting import load_inputs,make_examples,predict,sha256
from forecast_intervals import load_snapshot,monitoring_view

ROOT=Path(__file__).resolve().parents[1]


def run():
    folder=ROOT/'data/processed/new_york/forecasting_followup'
    manifest=json.loads((folder/'followup_manifest.json').read_text())
    summary=manifest['summary']
    for name,item in manifest['products'].items():
        assert sha256(folder/f'{name}.csv')==item['sha256'],name
    for name,expected in manifest['source_snapshot_hashes'].items():
        assert sha256(ROOT/name)==expected,name
    assert sha256(ROOT/'data/processed/new_york/forecasting/forecast_manifest.json')==manifest['original_forecast_manifest_sha256']
    original,routes=load_inputs(ROOT)
    latest,poll=load_snapshot(ROOT,summary['snapshot'])
    combined,network=monitoring_view(original,latest,routes)
    cal=pd.read_csv(folder/'calibration_predictions.csv',parse_dates=['payment_date','origin'])
    evaluation=pd.read_csv(folder/'evaluation_intervals.csv',parse_dates=['payment_date','origin','availability_cutoff'])
    assert cal.payment_date.max()==pd.Timestamp(summary['calibration_last_target'])
    assert cal.payment_date.max()<=evaluation.availability_cutoff.min()
    assert pd.Timestamp(summary['validation_last_target'])<=cal.origin.min()-pd.Timedelta(days=15)
    metrics=pd.read_csv(folder/'interval_coverage.csv').set_index('level')
    for level,part in evaluation.groupby('level'):
        assert not part.duplicated(['bus_route','payment_date']).any()
        actual=combined.set_index(['bus_route','payment_date']).analysis_boardings.reindex(
            pd.MultiIndex.from_frame(part[['bus_route','payment_date']])).to_numpy()
        np.testing.assert_allclose(actual,part.actual)
        coverage=((actual>=part.lower)&(actual<=part.upper)).mean()
        assert np.isclose(coverage,metrics.loc[level,'coverage'])
        assert np.isclose((part.upper-part.lower).mean(),metrics.loc[level,'mean_width'])
        assert part.lower.ge(0).all()
    low=evaluation.loc[evaluation.level.eq(.8)].set_index(['bus_route','payment_date'])
    high=evaluation.loc[evaluation.level.eq(.9)].set_index(['bus_route','payment_date'])
    assert high.lower.le(low.lower).all() and high.upper.ge(low.upper).all()
    later=pd.read_csv(folder/'later_outcome_predictions.csv',parse_dates=['payment_date'])
    recorded=pd.read_csv(folder/'later_outcome_scores.csv').set_index('model')
    for name,part in later.groupby('model'):
        actual=combined.set_index(['bus_route','payment_date']).analysis_boardings.reindex(
            pd.MultiIndex.from_frame(part[['bus_route','payment_date']])).to_numpy()
        np.testing.assert_allclose(actual,part.actual)
        assert np.isclose(np.abs(actual-part.prediction).mean(),recorded.loc[name,'mae'])
    registrations=[]
    for name in ['registration_pointer.json','baseline_registration_pointer.json']:
        pointer=json.loads((folder/name).read_text())
        path=ROOT/pointer['registration']
        info=json.loads((path/'registration.json').read_text())
        assert sha256(path/'forecasts.csv')==info['forecast_sha256']
        registered=pd.read_csv(path/'forecasts.csv',dtype={'bus_route':'string'},
            parse_dates=['payment_date','origin','availability_cutoff','max_history_date'])
        observed=pd.Timestamp(info['snapshot_observed_utc'])
        created=pd.Timestamp(info['registered_utc'])
        first_target=registered.payment_date.min().tz_localize('America/New_York')
        assert observed<=created<first_target
        assert registered.max_history_date.le(pd.Timestamp(info['source_available_cutoff'])).all()
        assert pd.Timestamp(info['training_last_target'])<=pd.Timestamp(info['source_available_cutoff'])
        features=make_examples(combined,routes,[registered.origin.iloc[0]],
            int((registered.origin.iloc[0]-registered.availability_cutoff.iloc[0]).days)-1)
        points=registered.drop_duplicates(['bus_route','payment_date'])
        if info.get('model_sha256'):
            assert sha256(path/'model.pkl')==info['model_sha256']
            with (path/'model.pkl').open('rb') as handle:estimator=pickle.load(handle)
            np.testing.assert_allclose(predict(estimator,features),points.prediction,rtol=1e-12)
        else:
            np.testing.assert_allclose(features[info['selected_model']],points.prediction,rtol=1e-12)
        assert len(points)==287 and len(registered)==574
        registrations.append({'model':info['selected_model'],'registered_utc':info['registered_utc'],
            'forecast_rows':len(points),'first_target':info['first_target'],'last_target':info['last_target'],
            'registered_before_targets':True,'forecast_and_model_fingerprints_verified':True})
    notebook=nbformat.read(ROOT/'notebooks/new_york/06_forecast_validation.ipynb',as_version=4)
    nbformat.validate(notebook)
    codes=[cell for cell in notebook.cells if cell.cell_type=='code']
    assert [c.execution_count for c in codes]==list(range(1,len(codes)+1))
    assert all(c.outputs and not any(o.output_type=='error' for o in c.outputs) for c in codes)
    result={'forecast_products_verified':len(manifest['products']),'calibration_rows':len(cal),
        'evaluation_route_dates':len(low),'coverage_recomputed':True,'later_outcome_metrics_recomputed':True,
        'registrations':registrations,'code_cells':len(codes),'saved_outputs':sum(len(c.outputs) for c in codes),
        'historical_original_experiment_preserved':True,'prospective_outcomes_pending':True}
    (ROOT/'reports/forecasting_intervals/audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':run()
