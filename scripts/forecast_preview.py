"""Produce a labelled experimental forecast from a validated snapshot; never overwrite registrations."""
import argparse
from datetime import datetime,timezone
import json
from importlib import metadata as package_metadata
from pathlib import Path

import pandas as pd

from forecasting import load_inputs,sha256,make_examples
from forecast_intervals import load_snapshot,monitoring_view
from extended_forecasting import preview_rows,rolling_intervals
from forecast_error_analysis import candidate_predictions

ROOT=Path(__file__).resolve().parents[1]


def run(snapshot=None, target_start=None, mode='reference'):
    folder=ROOT/'data/processed/new_york/october_validation'
    manifest=json.loads((folder/'october_manifest.json').read_text())
    profile=json.loads((folder/'experimental_profile.json').read_text())
    if profile!=manifest['experimental_profile'] or sha256(folder/'experimental_profile.json')!=manifest['experimental_profile_sha256']:
        raise ValueError('Experimental profile differs from validated manifest')
    if mode not in ['reference','challenger']:
        raise ValueError(mode)
    strategy=profile['reference_strategy'] if mode=='reference' else profile['challenger_strategy']
    snapshot=snapshot or manifest['summary']['snapshot']
    for name in ['context_predictions','warmup_predictions']:
        assert sha256(folder/f'{name}.csv')==manifest['products'][name]['sha256']
    original,routes=load_inputs(ROOT)
    latest,poll=load_snapshot(ROOT,snapshot)
    daily,_=monitoring_view(original,latest,routes)
    now=datetime.now(timezone.utc)
    rows=preview_rows(daily,routes,poll['observed_utc'],now,'seasonal_mean4',target_start)
    cutoff=rows.availability_cutoff.iloc[0]
    last_training_target=None
    if strategy in ['seasonal_mean4','seasonal_latest','annual_scaled','annual_blend_50']:
        rows['prediction']=rows[strategy]
    else:
        train_examples=make_examples(daily,routes,pd.date_range('2025-03-03',cutoff,freq='W-MON'),14)
        train=train_examples.loc[train_examples.payment_date.le(cutoff)&train_examples.actual.notna()&train_examples.history_eligible]
        rows['prediction']=candidate_predictions(train,rows,[strategy])[strategy]
        last_training_target=str(train.payment_date.max().date())
    rows['strategy']=strategy
    points=rows[['bus_route','payment_date','prediction','strategy','availability_cutoff',
                 'max_history_date','lead_days_from_issue','annual_eligible']].copy()
    points['mode']='experimental_preview'
    residuals=pd.concat([pd.read_csv(folder/f'{name}.csv',dtype={'bus_route':'string'},
        parse_dates=['origin','payment_date','availability_cutoff'])
        for name in ['warmup_predictions','context_predictions']],ignore_index=True)
    residuals=residuals.loc[residuals.model.eq(strategy)]
    target=rows[['bus_route','origin','payment_date','prediction','availability_cutoff']].copy()
    target['model']=strategy;target['actual']=float('nan')
    joined=pd.concat([residuals,target],ignore_index=True)
    intervals,calibration=rolling_intervals(joined,[rows.origin.iloc[0]],rows.payment_date.max())
    accepted_levels=[item['level'] for item in profile['strategies'][strategy]['intervals'] if item['within_5_percentage_points']]
    intervals=intervals.loc[intervals.level.isin(accepted_levels)].copy()
    if len(intervals):
        intervals['status']='empirical_experimental_range_not_prospectively_validated'
    stamp=now.strftime('%Y%m%dT%H%M%S%fZ')
    out=ROOT/'data/processed/new_york/forecast_previews'/stamp
    out.mkdir(parents=True,exist_ok=False)
    points.to_csv(out/'point_forecasts.csv',index=False)
    intervals.to_csv(out/'empirical_ranges.csv',index=False)
    calibration.to_csv(out/'calibration_audit.csv',index=False)
    metadata={'generated_utc':now.isoformat(),'snapshot':snapshot,'source_observed_utc':poll['observed_utc'],
        'snapshot_sha256':sha256(ROOT/snapshot/'route_days.csv'),'profile_sha256':sha256(folder/'experimental_profile.json'),
        'strategy':strategy,'preview_mode':mode,'first_target':str(rows.payment_date.min().date()),
        'last_target':str(rows.payment_date.max().date()),'point_rows':len(points),
        'maturity_cutoff':str(rows.availability_cutoff.iloc[0].date()),
        'range_levels_available':accepted_levels,'operationally_accepted':False,
        'registered_for_prospective_scoring':False,'point_sha256':sha256(out/'point_forecasts.csv'),
        'range_sha256':sha256(out/'empirical_ranges.csv'),
        'calibration_audit_sha256':sha256(out/'calibration_audit.csv'),
        'last_training_target':last_training_target,
        'upstream_hashes':{name:sha256(ROOT/'data/processed/new_york'/name)
            for name in ['daily_clean.csv','route_crosswalk.csv','cleaning_manifest.json']},
        'code_hashes':{name:sha256(ROOT/'scripts'/name)
            for name in ['forecast_preview.py','extended_forecasting.py','forecast_error_analysis.py','forecasting.py']},
        'runtime_versions':{name:package_metadata.version(name) for name in ['numpy','pandas','scikit-learn']},
        'range_policy':'Withhold levels failing the primary historical coverage screen; no future coverage guarantee'}
    (out/'preview_manifest.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    report=ROOT/'reports/october_validation'
    report.mkdir(parents=True,exist_ok=True)
    (report/'latest_preview.json').write_text(json.dumps(dict(metadata,output=out.relative_to(ROOT).as_posix()),indent=2),encoding='utf-8')
    print(json.dumps(dict(metadata,output=out.relative_to(ROOT).as_posix()),indent=2))
    return metadata


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',help='Validated monitoring snapshot relative to repository root')
    parser.add_argument('--target-start',help='Future target start, YYYY-MM-DD; default tomorrow')
    parser.add_argument('--mode',choices=['reference','challenger'],default='reference')
    args=parser.parse_args()
    run(args.snapshot,args.target_start,args.mode)
