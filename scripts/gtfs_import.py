"""Bounded, non-extracting GTFS Schedule importer for bus-service inspection.

This validates fields needed by this application, not the entire GTFS specification.
Uploaded schedules never become passenger observations or overwrite frozen analysis.
"""
from io import BytesIO
import hashlib
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

DAYS = 'monday tuesday wednesday thursday friday saturday sunday'.split()
FIELDS = {
    'agency': ['agency_timezone'],
    'routes': ['route_id', 'route_type'],
    'trips': ['route_id', 'service_id', 'trip_id'],
    'stops': ['stop_id', 'stop_name', 'stop_lat', 'stop_lon'],
    'stop_times': ['trip_id', 'stop_id', 'stop_sequence', 'arrival_time', 'departure_time'],
    'calendar': ['service_id', *DAYS, 'start_date', 'end_date'],
    'calendar_dates': ['service_id', 'date', 'exception_type'],
    'frequencies': ['trip_id', 'start_time', 'end_time', 'headway_secs'],
}


class FeedError(ValueError):
    pass


def require(test, message):
    if not bool(test):
        raise FeedError(message)


def times(values):
    blank = values.isna() | values.eq('')
    require((blank | values.str.fullmatch(r'\d{1,3}:[0-5]\d:[0-5]\d').fillna(False)).all(), 'Invalid GTFS time syntax')
    parts = values.mask(blank).str.split(':', expand=True).reindex(columns=[0, 1, 2]).astype(float)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def dates(values):
    parsed = pd.to_datetime(values, format='%Y%m%d', errors='coerce')
    require(parsed.notna().all(), 'Invalid calendar date')
    return parsed


def inspect_gtfs(payload, service_date, max_upload_bytes=100_000_000, max_expanded_bytes=650_000_000):
    require(len(payload) <= max_upload_bytes, 'ZIP exceeds the 100 MB upload limit')
    try:
        archive = ZipFile(BytesIO(payload))
    except BadZipFile as exc:
        raise FeedError('Upload is not a readable ZIP archive') from exc
    with archive:
        files = {}
        require(len(archive.infolist()) <= 200, 'Too many ZIP members')
        require(sum(i.file_size for i in archive.infolist()) <= max_expanded_bytes, 'Expanded archive exceeds the inspection limit')
        for info in archive.infolist():
            path = PurePosixPath(info.filename.replace('\\', '/'))
            require(not path.is_absolute() and '..' not in path.parts and ':' not in info.filename,
                    'Unsafe archive member path')
            require(not info.flag_bits & 1, 'Encrypted ZIP members are unsupported')
            if info.is_dir() or path.name.startswith('.'):
                continue
            if path.suffix.lower() != '.txt':
                continue
            require(path.name not in files, 'Duplicate table names in ZIP')
            files[path.name] = info
        tables = {}
        for name, required in FIELDS.items():
            filename = name + '.txt'
            if filename not in files:
                require(name in ['calendar', 'calendar_dates', 'frequencies'], f'Missing {filename}')
                tables[name] = pd.DataFrame(columns=required)
                continue
            try:
                # Only project-required and small descriptive fields are materialized.
                allowed = set(required + ['route_short_name', 'route_long_name', 'direction_id', 'shape_id', 'exact_times'])
                frame = pd.read_csv(archive.open(files[filename]), dtype='string', encoding='utf-8-sig',
                                    usecols=lambda c: c in allowed)
            except (ValueError, UnicodeError, BadZipFile) as exc:
                raise FeedError(f'Cannot parse {filename}') from exc
            require(set(required) <= set(frame), f'Missing required columns in {filename}')
            for col in frame:
                frame[col] = frame[col].str.strip()
            tables[name] = frame
    agency, routes, trips, stops, events, calendar, exceptions, frequency = [tables[n] for n in FIELDS]
    require(not agency.empty and agency.agency_timezone.notna().all(), 'Agency timezone is required')
    for zone in agency.agency_timezone.unique():
        try:
            ZoneInfo(zone)
        except ZoneInfoNotFoundError as exc:
            raise FeedError('Unknown agency timezone') from exc
    for frame, key in [(routes, 'route_id'), (trips, 'trip_id'), (stops, 'stop_id'), (calendar, 'service_id')]:
        require(frame[key].notna().all() and frame[key].ne('').all() and not frame[key].duplicated().any(), f'Missing/duplicate {key}')
    require(set(trips.route_id) <= set(routes.route_id), 'Trips reference unknown routes')
    require(set(events.trip_id) <= set(trips.trip_id), 'Stop times reference unknown trips')
    require(set(events.stop_id) <= set(stops.stop_id), 'Stop times reference unknown stops')
    require(set(events.trip_id) == set(trips.trip_id), 'Trips without stop events')
    require(not calendar.empty or not exceptions.empty, 'A calendar or calendar_dates table is required')
    if len(calendar):
        calendar['start'] = dates(calendar.start_date)
        calendar['end'] = dates(calendar.end_date)
        require(calendar[DAYS].isin(['0', '1']).all().all(), 'Invalid calendar weekday flags')
        require(calendar.start.le(calendar.end).all(), 'Calendar start follows end date')
    if len(exceptions):
        exceptions['parsed_date'] = dates(exceptions.date)
        require(exceptions.exception_type.isin(['1', '2']).all(), 'Invalid exception type')
        require(not exceptions.duplicated(['service_id', 'date']).any(), 'Duplicate service/date exceptions')
    require(set(trips.service_id) <= set(calendar.service_id) | set(exceptions.service_id), 'Trips reference unknown services')
    date = pd.Timestamp(service_date).normalize()
    active = set()
    if len(calendar):
        active = set(calendar.loc[calendar.start.le(date) & calendar.end.ge(date) & calendar[DAYS[date.dayofweek]].eq('1'), 'service_id'])
    if len(exceptions):
        changes = exceptions.loc[exceptions.parsed_date.eq(date)]
        active -= set(changes.loc[changes.exception_type.eq('2'), 'service_id'])
        active |= set(changes.loc[changes.exception_type.eq('1'), 'service_id'])
    events['stop_sequence'] = pd.to_numeric(events.stop_sequence, errors='coerce')
    require(events.stop_sequence.notna().all() and events.stop_sequence.ge(0).all()
            and events.stop_sequence.eq(events.stop_sequence.round()).all(), 'Invalid stop sequence')
    require(not events.duplicated(['trip_id', 'stop_sequence']).any(), 'Duplicate trip/sequence keys')
    events['arrival'] = times(events.arrival_time)
    events['departure'] = times(events.departure_time)
    events = events.sort_values(['trip_id', 'stop_sequence'])
    require(not (events.departure < events.arrival).any(), 'Departure before arrival')
    previous = events.groupby('trip_id').departure.shift()
    require(not (events.arrival < previous).any(), 'Backward stop-time ordering')
    first = events.drop_duplicates('trip_id').set_index('trip_id')
    last = events.drop_duplicates('trip_id', keep='last').set_index('trip_id')
    profile = trips.copy().set_index('trip_id')
    profile['first_departure_seconds'] = first.departure
    profile['last_arrival_seconds'] = last.arrival
    profile['duration_hours'] = (profile.last_arrival_seconds - profile.first_departure_seconds) / 3600
    profile['duration_valid'] = profile.duration_hours.gt(0) & profile.duration_hours.notna()
    complete = events[['arrival', 'departure']].notna().all(axis=1).groupby(events.trip_id).all()
    profile['duration_valid'] &= complete
    profile['stop_visits'] = events.groupby('trip_id').size()
    profile['pattern'] = events.groupby('trip_id').stop_id.agg(lambda x: hashlib.sha256('\n'.join(x).encode()).hexdigest())
    profile['departure_count'] = 1.
    profile['count_kind'] = 'explicit_scheduled_trips'
    if len(frequency):
        require(set(frequency.trip_id) <= set(trips.trip_id), 'Frequency rows reference unknown trips')
        frequency['start'] = times(frequency.start_time)
        frequency['end'] = times(frequency.end_time)
        frequency['headway'] = pd.to_numeric(frequency.headway_secs, errors='coerce')
        require(frequency[['start', 'end', 'headway']].notna().all().all() and frequency.headway.gt(0).all()
                and frequency.headway.eq(frequency.headway.round()).all() and frequency.end.gt(frequency.start).all(), 'Invalid frequency window or headway')
        frequency['exact_times'] = frequency.get('exact_times', pd.Series('0', index=frequency.index)).fillna('0')
        require(frequency.exact_times.isin(['0', '1']).all(), 'Invalid exact_times')
        frequency = frequency.sort_values(['trip_id', 'start'])
        require(not frequency.start.lt(frequency.groupby('trip_id').end.shift()).any(), 'Overlapping frequency windows')
        frequency['count'] = np.where(frequency.exact_times.eq('1'), np.ceil((frequency.end-frequency.start)/frequency.headway),
                                      (frequency.end-frequency.start)/frequency.headway)
        counts = frequency.groupby('trip_id')['count'].sum()
        profile.loc[counts.index, 'departure_count'] = counts
        kind = frequency.groupby('trip_id').exact_times.agg(lambda x: 'exact_frequency_expansion' if x.eq('1').all() else 'expected_frequency_service')
        profile.loc[kind.index, 'count_kind'] = kind
    routes['route_type_number'] = pd.to_numeric(routes.route_type, errors='coerce')
    require(routes.route_type_number.notna().all(), 'Invalid route_type')
    buses = routes.loc[routes.route_type_number.eq(3) | routes.route_type_number.between(700, 799)].copy()
    selected = profile.loc[profile.route_id.isin(buses.route_id) & profile.service_id.isin(active)].reset_index()
    selected['valid_service_hours'] = (selected.duration_hours * selected.departure_count).where(selected.duration_valid)
    stats = selected.groupby('route_id').agg(scheduled_or_expected_departures=('departure_count', 'sum'),
        duration_valid=('duration_valid', 'all'), service_hours=('valid_service_hours', lambda x: x.sum(min_count=1)),
        trip_templates=('trip_id', 'size'), stop_patterns=('pattern', 'nunique'))
    stats['service_hours'] = stats.service_hours.where(stats.duration_valid)
    counts = buses.merge(stats, on='route_id', how='left')
    counts['scheduled_or_expected_departures'] = counts.scheduled_or_expected_departures.fillna(0)
    counts['active_service_date'] = date.strftime('%Y-%m-%d')
    counts['source_sha256'] = hashlib.sha256(payload).hexdigest()
    counts['counts_include_expected_service'] = counts.route_id.isin(selected.loc[selected.count_kind.eq('expected_frequency_service'), 'route_id'])
    stops['lat'] = pd.to_numeric(stops.stop_lat, errors='coerce')
    stops['lon'] = pd.to_numeric(stops.stop_lon, errors='coerce')
    invalid_coordinates = ~stops.lat.between(-90, 90) | ~stops.lon.between(-180, 180)
    summary = {'source_sha256': hashlib.sha256(payload).hexdigest(), 'service_date': date.strftime('%Y-%m-%d'),
               'routes': len(routes), 'bus_routes': len(buses), 'active_bus_templates': len(selected),
               'stop_events': len(events), 'stops': len(stops), 'active_services': len(active),
               'invalid_or_missing_stop_coordinates': int(invalid_coordinates.sum()),
               'bus_templates_with_unavailable_duration': int((~selected.duration_valid).sum()),
               'frequency_rows': len(frequency), 'timezones': list(agency.agency_timezone.unique()),
               'passenger_observations_imported': False, 'frozen_study_modified': False,
               'duration_scope': 'service-day template durations; not clock-date exposure',
               'validation_scope': 'application-required fields, not full GTFS certification'}
    return summary, counts, selected
