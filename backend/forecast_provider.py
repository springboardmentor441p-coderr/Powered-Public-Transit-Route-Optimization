"""Availability-safe seasonal reference. A frozen fitted provider may implement this interface."""
from datetime import date, timedelta
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

REFERENCE_ID = 'seasonal_mean4_daily_replay_v1'
MODEL_ID = REFERENCE_ID
REPLAY_START = date(2026, 6, 1)
REPLAY_END = date(2026, 7, 31)
REPORTING_DELAY_DAYS = 14
MODEL_METADATA = {
    'name': 'Four-week seasonal mean', 'algorithm': 'seasonal_reference',
    'status': 'retrospective_reference_not_operationally_accepted',
    'train_end': None, 'frozen_before': '2026-06-01',
    'model_selection': 'Fixed seasonal reference; no parameter training during replay',
    'replay_start': REPLAY_START.isoformat(), 'replay_end': REPLAY_END.isoformat(),
    'reporting_delay_days': REPORTING_DELAY_DAYS,
    'features': ['exact_weekday_lag_21', 'exact_weekday_lag_28', 'exact_weekday_lag_35', 'exact_weekday_lag_42'],
    'minimum_seasonal_observations': 2,
    'uncertainty_intervals': 'Not supplied by this daily replay provider',
}

ARTIFACTS = Path(__file__).resolve().parents[1] / 'data/processed/new_york/daily_replay_experiment'
if (ARTIFACTS / 'manifest.json').exists():
    _manifest_bytes = (ARTIFACTS / 'manifest.json').read_bytes()
    _manifest = json.loads(_manifest_bytes)
    _selected = _manifest['selected_by_validation']
    if _selected in ('random_forest', 'ridge'):
        MODEL_ID = f"daily_{_selected}_{hashlib.sha256(_manifest_bytes).hexdigest()[:12]}"
        MODEL_METADATA = {**_manifest, 'name': f"Daily {_selected.replace('_', ' ')}",
            'algorithm': _selected, 'manifest_sha256': hashlib.sha256(_manifest_bytes).hexdigest(),
            'pipeline_file': f'{_selected}.joblib',
            'pipeline_sha256': _manifest['products'][f'{_selected}.joblib'],
            'status': 'retrospective_evaluation_not_operationally_accepted',
            'freeze_interpretation': 'Simulated historical cutoff; experiment constructed after the target period',
            'fallback': 'seasonal_mean4 with at least two released seasonal observations',
            'uncertainty_intervals': 'Not supplied; daily replay intervals have not been evaluated'}


@lru_cache(maxsize=4)
def _load_model(path, modified, size, expected):
    content = Path(path).read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError('Fitted pipeline fingerprint mismatch')
    model = joblib.load(path)
    # Small request-time batches are faster without creating worker pools per call.
    if hasattr(model[-1], 'n_jobs'):
        model[-1].n_jobs = 1
    return model


def predict(conn, data_version, route, target_date, available_through, model_version=MODEL_ID):
    """Only retrieve released source rows; do not query target rides."""
    registered = conn.execute('SELECT metadata FROM rr_models WHERE id=%s', (model_version,)).fetchone()
    metadata = registered['metadata'] if registered else {}
    if model_version != REFERENCE_ID and metadata.get('algorithm') not in ('random_forest', 'ridge'):
        return {'prediction': None, 'status': 'unavailable', 'fallback_reason': 'Model provider unavailable',
                'inputs': [], 'latest_available_ride_date': None}
    dates = [target_date - timedelta(days=n) for n in (21, 28, 35, 42)]
    dates = [d for d in dates if d <= available_through]
    rows = conn.execute('''SELECT date,rides FROM rr_daily
        WHERE data_version=%s AND route=%s AND date=ANY(%s) AND date<=%s AND rides IS NOT NULL
        ORDER BY date''', (data_version, route, dates, available_through)).fetchall()
    latest = conn.execute('''SELECT max(date) AS date FROM rr_daily WHERE data_version=%s
        AND route=%s AND date<=%s AND rides IS NOT NULL''',
        (data_version, route, available_through)).fetchone()['date']
    available = len(rows) >= 2
    result = {'prediction': sum(x['rides'] for x in rows) / len(rows) if available else None,
            'status': 'prediction' if available else 'unavailable',
            'fallback_reason': None if available else 'Fewer than two released seasonal observations',
            'inputs': [{'date': x['date'].isoformat(), 'rides': x['rides']} for x in rows],
            'latest_available_ride_date': latest,
            'latest_input_ride_date': max((x['date'] for x in rows), default=None),
            'units': 'published daily boarding estimates'}
    if model_version == REFERENCE_ID or not available:
        return result
    values = {item['date']: item['rides'] for item in rows}
    example = {'bus_route': route, 'day_of_week': target_date.weekday(), 'month': target_date.month,
               'is_weekend': int(target_date.weekday() >= 5), 'seasonal_count': len(rows),
               'seasonal_mean': result['prediction']}
    for lag in (1, 7, 14, 21, 28, 35, 42):
        lookup = target_date - timedelta(days=lag)
        example[f'lag_{lag}'] = values.get(lookup, np.nan) if lookup <= available_through else np.nan
    try:
        path = (Path(__file__).resolve().parents[1] / metadata['pipeline_path']) if metadata.get('pipeline_path') else ARTIFACTS / metadata['pipeline_file']
        stat = path.stat()
        model = _load_model(str(path), stat.st_mtime_ns, stat.st_size, metadata['pipeline_sha256'])
        frame = pd.DataFrame([example])[['bus_route'] + metadata['features']]
        result['prediction'] = max(0.0, float(model.predict(frame)[0]))
        result['feature_values'] = {key: None if pd.isna(value) else value for key, value in example.items()}
        result['pipeline_sha256'] = metadata['pipeline_sha256']
    except (OSError, ValueError) as exc:
        result['status'] = 'validated_fallback'
        result['fallback_reason'] = f'Frozen fitted pipeline unavailable or failed integrity validation: {type(exc).__name__}'
        result['served_algorithm'] = 'seasonal_mean4'
    return result
