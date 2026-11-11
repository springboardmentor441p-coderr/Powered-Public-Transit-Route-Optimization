"""Validate the frozen analysis catalog and import it atomically into PostgreSQL.

Run from the project root: python -m backend.import_data
Existing dataset versions, forecasts, replay sessions and scenarios are retained.
"""
import hashlib
import json
from pathlib import Path
import shutil

import pandas as pd
from psycopg.types.json import Jsonb

from backend.db import connection, initialize
from backend.forecast_provider import ARTIFACTS, MODEL_ID, MODEL_METADATA

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if pd.isna(value):
        return None
    if hasattr(value, 'item'):
        return value.item()
    return value


def truth(value):
    return str(value).lower() == 'true'


def import_bundle(root=ROOT):
    root = Path(root)
    catalog_path = root / 'documentation/dashboard_data_manifest.json'
    catalog = json.loads(catalog_path.read_text())
    sources = []
    for section in ('tables', 'documents'):
        for name, spec in catalog[section].items():
            path = root / spec['path']
            if digest(path) != spec['sha256']:
                raise ValueError(f'Analysis fingerprint mismatch: {name}')
            sources.append({'name': name, 'path': spec['path'], 'sha256': spec['sha256'],
                            'byte_size': path.stat().st_size, 'rows': spec.get('rows')})

    def load(name):
        spec = catalog['tables'][name]
        result = pd.read_csv(root / spec['path'], low_memory=False)
        if len(result) != spec['rows'] or list(result.columns) != spec['columns']:
            raise ValueError(f'Analysis schema mismatch: {name}')
        return result

    daily, crosswalk = load('daily'), load('crosswalk')
    if daily.duplicated(['bus_route', 'payment_date']).any():
        raise ValueError('Duplicate route/date observation keys')
    if daily.analysis_boardings.dropna().lt(0).any():
        raise ValueError('Negative boardings')
    version = 'ny_' + digest(catalog_path)[:16]
    metadata = {'scope': catalog['scope'], 'sources': sources,
                'first_date': daily.payment_date.min(), 'last_date': daily.payment_date.max(),
                'observation_rows': len(daily), 'routes': int(daily.bus_route.nunique()),
                'eligible_schedule_rows': int(daily.comparison_eligible.map(truth).sum()),
                'geometry_version': catalog['geometry_snapshot'],
                'timezone': 'America/New_York', 'observation_units': 'published daily boarding estimates',
                'schedule_units': 'clock-date departures and passenger-trip service hours',
                'reporting_policy': '14 complete intervening days; simulated historical release, not verified arrival history',
                'source_register_document': 'documentation/SOURCES.md',
                'quality': {'missing_demand_rows': int(daily.analysis_boardings.isna().sum()),
                            'missing_schedule_rows': int(daily.scheduled_departures.isna().sum()),
                            'eligibility_note': 'Source-quality, calendar, DST and block-overlap gates remain enforced'}}
    names = crosswalk.sort_values('snapshot_id').drop_duplicates('bus_route', keep='last')
    groups, links, points = load('groups'), load('map_routes'), load('map_shapes')
    shapes = {str(key): frame.sort_values('shape_pt_sequence')[['shape_pt_lon', 'shape_pt_lat']].values.tolist()
              for key, frame in points.groupby('shape_id')}
    model_metadata = dict(MODEL_METADATA)
    if model_metadata.get('pipeline_file'):
        original_pipeline = ARTIFACTS / model_metadata['pipeline_file']
        expected = model_metadata['pipeline_sha256']
        if digest(original_pipeline) != expected:
            raise ValueError('Fitted pipeline fingerprint mismatch before import')
        archive = root / 'data/processed/new_york/application_models' / MODEL_ID
        archive.mkdir(parents=True, exist_ok=True)
        frozen_pipeline = archive / model_metadata['pipeline_file']
        if not frozen_pipeline.exists():
            shutil.copyfile(original_pipeline, frozen_pipeline)
        if digest(frozen_pipeline) != expected:
            raise ValueError('Previously frozen pipeline fingerprint mismatch')
        model_metadata['pipeline_path'] = frozen_pipeline.relative_to(root).as_posix()
    with connection() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(928624)')
        initialize(conn)
        existing = conn.execute('SELECT id FROM rr_dataset_versions WHERE id=%s', (version,)).fetchone()
        if not existing:
            conn.execute('INSERT INTO rr_dataset_versions(id,metadata) VALUES (%s,%s)', (version, Jsonb(metadata)))
            with conn.cursor() as cur:
                cur.executemany('INSERT INTO rr_routes VALUES (%s,%s,%s)',
                                [(version, row.bus_route, row.route_long_name) for row in names.itertuples()])
                values = []
                for row in daily.to_dict('records'):
                    quality = {key: truth(row[key]) for key in ['demand_review_required', 'dst_context_review',
                               'block_overlap_review', 'partial_calendar_review', 'hourly_coverage_review']}
                    values.append((version, row['bus_route'], row['payment_date'], clean(row['analysis_boardings']),
                        clean(row['published_boardings']), row['day_type'], clean(row['scheduled_departures']),
                        clean(row['scheduled_service_hours']), truth(row['comparison_eligible']),
                        truth(row['schedule_comparison_eligible']), clean(row['source_snapshot']),
                        clean(row['prior_source_snapshot']), Jsonb(quality)))
                cur.executemany('INSERT INTO rr_daily VALUES (' + ','.join(['%s'] * 13) + ')', values)
                cur.executemany('INSERT INTO rr_profiles VALUES (%s,%s,%s,%s,%s,%s)', [
                    (version, row['bus_route'], 'route_profiles_20260927', row['first_date'], row['last_date'], Jsonb(clean(row)))
                    for row in groups.to_dict('records')])
                cur.executemany('INSERT INTO rr_geometry VALUES (%s,%s,%s,%s,%s)', [
                    (version, route, catalog['geometry_snapshot'], '2026-09-04', Jsonb([
                        {'shape_id': str(s), 'coordinates': shapes[str(s)]} for s in frame.shape_id if str(s) in shapes]))
                    for route, frame in links.groupby('bus_route')])
        conn.execute('INSERT INTO rr_models(id,data_version,metadata) VALUES (%s,%s,%s) ON CONFLICT(id) DO NOTHING',
                     (MODEL_ID, version, Jsonb(model_metadata)))
        # Add immutable artifact location to an earlier import of the same verified model.
        if model_metadata.get('pipeline_path'):
            conn.execute("UPDATE rr_models SET metadata=metadata || %s WHERE id=%s AND NOT metadata ? 'pipeline_path'",
                         (Jsonb({'pipeline_path': model_metadata['pipeline_path']}), MODEL_ID))
        conn.execute("INSERT INTO rr_settings VALUES ('current_data_version',%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (version,))
    return {'data_version': version, 'already_imported': bool(existing), **metadata}


if __name__ == '__main__':
    result = import_bundle()
    print(json.dumps({k: v for k, v in result.items() if k != 'sources'}, indent=2))
