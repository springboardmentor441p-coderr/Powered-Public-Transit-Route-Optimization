"""Empirical demand intervals and immutable registration of prospective forecasts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
from forecasting import sha256


def load_snapshot(root, relative):
    folder=Path(root)/relative
    manifest=json.loads((folder/'manifest.json').read_text())
    for receipt in manifest:
        assert sha256(Path(root)/receipt['local_path'])==receipt['sha256']
    summary=json.loads((folder/'poll_summary.json').read_text())
    if not summary.get('denominator_checks_passed'):
        raise ValueError('Unvalidated publisher snapshot')
    frame=pd.read_csv(folder/'route_days.csv',dtype={'bus_route':'string'},parse_dates=['payment_date'])
    if frame.duplicated(['bus_route','payment_date']).any():
        raise ValueError('Duplicate route/date snapshot values')
    return frame,summary


def monitoring_view(original, latest, routes):
    """Retain original masks; screen later observations within the same fixed route cohort."""
    frame=original[['bus_route','payment_date','published_boardings','analysis_boardings']].copy()
    fresh=latest[['bus_route','payment_date','published_boardings']].copy()
    fresh['analysis_boardings']=fresh.published_boardings.astype(float)
    # Original flagged observations stay masked even if they are in the overlap.
    old_masks=original.loc[original.analysis_boardings.isna(),['bus_route','payment_date']]
    fresh=fresh.merge(old_masks.assign(old_review=True),how='left',on=['bus_route','payment_date'],validate='one_to_one')
    fresh.loc[fresh.old_review.eq(True),'analysis_boardings']=np.nan
    frame=pd.concat([frame.assign(version=0),fresh[frame.columns].assign(version=1)],ignore_index=True)
    frame=frame.sort_values('version').drop_duplicates(['bus_route','payment_date'],keep='last').drop(columns='version')
    network=frame.groupby('payment_date').agg(total=('published_boardings','sum'),routes=('bus_route','nunique'))
    previous=pd.concat([network.total.reindex(network.index-pd.Timedelta(days=d)).set_axis(network.index)
                        for d in [7,14,21,28]],axis=1)
    past=previous.mean(axis=1)
    network['review']=network.routes.ne(len(routes)) | network.total.eq(0) | (
        previous.notna().sum(axis=1).ge(2) & past.gt(0) & network.total.lt(.2*past))
    bad_dates=network.index[network.review]
    frame.loc[frame.payment_date.isin(bad_dates),'analysis_boardings']=np.nan
    partial=latest.loc[latest.reported_hours.ne(24),['bus_route','payment_date']]
    frame=frame.merge(partial.assign(partial_source=True),how='left',on=['bus_route','payment_date'],validate='one_to_one')
    frame.loc[frame.partial_source.eq(True),'analysis_boardings']=np.nan
    return frame.drop(columns='partial_source').sort_values(['payment_date','bus_route']),network.reset_index()


def calibrate(predictions, examples, cutoff, levels=(.8,.9), scale_floor=100):
    """Freeze residual quantiles using released outcomes only; no coverage guarantee is assumed."""
    if not levels or any(level<=0 or level>=1 for level in levels) or scale_floor<=0:
        raise ValueError('Invalid calibration configuration')
    rows=predictions.loc[pd.to_datetime(predictions.payment_date).le(pd.Timestamp(cutoff))].copy()
    rows=rows.merge(examples[['bus_route','payment_date','seasonal_mean4']],
                    on=['bus_route','payment_date'],validate='one_to_one')
    rows=rows.loc[rows.actual.notna() & rows.prediction.notna() & rows.seasonal_mean4.notna()]
    if rows.empty:raise ValueError('No released calibration outcomes')
    scores=((rows.actual-rows.prediction).abs()/rows.seasonal_mean4.clip(lower=scale_floor)).sort_values().to_numpy()
    if not np.isfinite(scores).all():raise ValueError('Nonfinite calibration residual')
    quantiles={}
    for level in levels:
        rank=int(np.ceil((len(scores)+1)*level))
        if rank>len(scores):raise ValueError('Too few observations for a finite calibrated quantile')
        quantiles[str(level)]=float(scores[rank-1])
    return {'cutoff':str(pd.Timestamp(cutoff).date()),'rows':len(rows),'levels':quantiles,
            'scale_floor':scale_floor,'last_calibration_target':str(rows.payment_date.max().date()),
            'method':'absolute error scaled by available seasonal mean; finite-rank empirical quantile',
            'distribution_free_guarantee':False}


def apply_intervals(predictions, examples, calibration):
    frame=predictions.merge(examples[['bus_route','payment_date','seasonal_mean4']],
                            on=['bus_route','payment_date'],validate='one_to_one')
    scale=frame.seasonal_mean4.clip(lower=calibration['scale_floor'])
    results=[]
    for level,q in calibration['levels'].items():
        part=frame.copy()
        part['level']=float(level)
        part['lower']=(part.prediction-q*scale).clip(lower=0)
        part['upper']=part.prediction+q*scale
        results.append(part)
    return pd.concat(results,ignore_index=True)


def interval_metrics(rows, group_cols=('level',)):
    result=[]
    rows=rows.loc[rows.actual.notna()]
    for key,part in rows.groupby(list(group_cols)):
        keys=key if isinstance(key,tuple) else (key,)
        coverage=part.actual.between(part.lower,part.upper)
        width=part.upper-part.lower
        alpha=1-part.level
        score=width+2/alpha*(part.lower-part.actual).clip(lower=0)+2/alpha*(part.actual-part.upper).clip(lower=0)
        result.append(dict(zip(group_cols,keys),rows=len(part),coverage=float(coverage.mean()),
                           mean_width=float(width.mean()),mean_interval_score=float(score.mean())))
    return pd.DataFrame(result)


def register_forecast(root, predictions, metadata):
    """Register before any target date, preserving the exact forecast and provenance."""
    now=datetime.now(timezone.utc)
    local_date=pd.Timestamp(now).tz_convert('America/New_York').date()
    if predictions.empty or pd.to_datetime(predictions.payment_date).min().date()<=local_date:
        raise ValueError('Prospective registration requires future target dates')
    observed=pd.Timestamp(metadata['snapshot_observed_utc'])
    if observed>pd.Timestamp(now):
        raise ValueError('Source snapshot has not been observed yet')
    maturity_limit=observed.tz_convert('America/New_York').tz_localize(None).normalize()-pd.Timedelta(days=metadata['maturity_days']+1)
    cutoff=pd.Timestamp(metadata['source_available_cutoff'])
    if cutoff>maturity_limit or pd.Timestamp(metadata['training_last_target'])>cutoff:
        raise ValueError('Training cutoff violates source maturity policy')
    if pd.to_datetime(predictions.max_history_date).gt(cutoff).any():
        raise ValueError('Forecast features exceed available source cutoff')
    if predictions.duplicated(['bus_route','payment_date','level']).any():
        raise ValueError('Duplicate registered forecast interval')
    path=Path(root)/'data/processed/new_york/prospective_registry'/now.strftime('%Y%m%dT%H%M%S%fZ')
    path.mkdir(parents=True,exist_ok=False)
    predictions.to_csv(path/'forecasts.csv',index=False)
    if metadata.get('model_sha256'):
        source=Path(root)/metadata['model_file']
        if sha256(source)!=metadata['model_sha256']:
            raise ValueError('Model fingerprint differs from registration metadata')
        shutil.copy2(source,path/'model.pkl')
    metadata=dict(metadata,registered_utc=now.isoformat(),forecast_sha256=sha256(path/'forecasts.csv'),
                  first_target=str(pd.to_datetime(predictions.payment_date).min().date()),
                  last_target=str(pd.to_datetime(predictions.payment_date).max().date()),
                  prospective_scores_available=False)
    (path/'registration.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return path,metadata


def evaluate_registration(root, registration, snapshot):
    path=Path(root)/registration
    metadata=json.loads((path/'registration.json').read_text())
    if sha256(path/'forecasts.csv')!=metadata['forecast_sha256']:
        raise ValueError('Registered forecast was modified')
    if metadata.get('model_sha256') and sha256(path/'model.pkl')!=metadata['model_sha256']:
        raise ValueError('Registered model was modified')
    rows=pd.read_csv(path/'forecasts.csv',dtype={'bus_route':'string'},parse_dates=['payment_date'])
    latest,poll=load_snapshot(root,snapshot)
    cutoff=pd.Timestamp(poll['observed_utc']).tz_convert('America/New_York').tz_localize(None).normalize()-pd.Timedelta(days=metadata['maturity_days']+1)
    mature=latest.loc[latest.payment_date.le(cutoff) & latest.reported_hours.eq(24)].copy()
    # Do not turn absent or all-zero network outcomes into scored zero targets.
    count=rows.bus_route.nunique()
    network=mature.groupby('payment_date').agg(routes=('bus_route','nunique'),total=('published_boardings','sum'))
    history=pd.concat([network.total.reindex(network.index-pd.Timedelta(days=lag)).set_axis(network.index)
                       for lag in [7,14,21,28]],axis=1)
    low=history.notna().sum(axis=1).ge(2)&history.mean(axis=1).gt(0)&network.total.lt(.2*history.mean(axis=1))
    valid=network.index[network.routes.eq(count)&network.total.gt(0)&~low]
    mature=mature.loc[mature.payment_date.isin(valid)]
    matched=rows.drop(columns='actual',errors='ignore').merge(
        mature[['bus_route','payment_date','published_boardings']],on=['bus_route','payment_date'],how='left',validate='many_to_one')
    matched=matched.rename(columns={'published_boardings':'actual'})
    from forecasting import metrics
    points=matched.loc[matched.actual.notna()].drop_duplicates(['bus_route','payment_date'])
    result={'registration':path.relative_to(root).as_posix(),'snapshot':snapshot,
            'model':metadata['selected_model'],
            'first_target':metadata['first_target'],'last_target':metadata['last_target'],
            'mature_outcome_cutoff':str(cutoff.date()),'registered_route_dates':rows[['bus_route','payment_date']].drop_duplicates().shape[0],
            'scored_route_dates':matched.loc[matched.actual.notna(),['bus_route','payment_date']].drop_duplicates().shape[0],
            'status':'pending' if matched.actual.notna().sum()==0 else 'outcomes_available',
            'earliest_full_maturity_date':str((pd.Timestamp(metadata['last_target'])+pd.Timedelta(days=metadata['maturity_days']+1)).date()),
            'point_metrics':metrics(points).to_dict(orient='records') if len(points) else [],
            'interval_metrics':interval_metrics(matched).to_dict(orient='records')}
    report=Path(root)/'reports/forecasting_intervals'
    report.mkdir(parents=True,exist_ok=True)
    (report/'prospective_evaluation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (report/f'prospective_evaluation_{path.name}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
