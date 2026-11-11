"""Planning calculations, immutable forecasts and a transaction-locked replay clock."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import re
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from backend import forecast_provider
from backend.db import current_version


def json_value(value):
    return json.loads(json.dumps(value, default=lambda x: x.isoformat(), allow_nan=False))


def latest_cutoff(day, delay=14):
    return day - timedelta(days=delay + 1)


def now():
    return datetime.now(timezone.utc)


def required_route(conn, version, route):
    row = conn.execute('SELECT route,name FROM rr_routes WHERE data_version=%s AND route=%s', (version, route)).fetchone()
    if not row:
        raise HTTPException(404, 'Route not found in this dataset version')
    return row


def schedule_for(conn, version, route, target, issue_day=None):
    row = conn.execute('''SELECT scheduled_trips,scheduled_hours,schedule_snapshot,prior_snapshot,schedule_eligible
        FROM rr_daily WHERE data_version=%s AND route=%s AND date=%s''', (version, route, target)).fetchone()
    if not row:
        return {'scheduled_trips': None, 'scheduled_hours': None, 'schedule_snapshot': None,
                'prior_snapshot': None, 'schedule_eligible': False, 'schedule_reason': 'No selected daily schedule'}
    available = row['schedule_eligible']
    if issue_day:
        # Capture timestamps are not verified agency publication times. At 00:00,
        # a copy captured on the same calendar date is conservatively unavailable.
        for snapshot in (row['schedule_snapshot'], row['prior_snapshot']):
            match = re.search(r'(\d{8})$', snapshot or '')
            if not match or datetime.strptime(match[1], '%Y%m%d').date() >= issue_day:
                available = False
    row['schedule_reason'] = None if available else 'Schedule quality or issue-time availability gate'
    row['schedule_eligible'] = available
    if not available:
        row['scheduled_trips'] = row['scheduled_hours'] = None
    return row


def store_forecast(conn, version, route, target, session=None):
    required_route(conn, version, route)
    model_id = session['model_version'] if session else forecast_provider.MODEL_ID
    scope = session['id'] if session else 'historical'
    existing = conn.execute('''SELECT * FROM rr_forecasts WHERE session_key=%s AND route=%s
        AND target_date=%s AND model_version=%s''', (scope, route, target, model_id)).fetchone()
    if existing:
        return existing
    cutoff = latest_cutoff(target, session['reporting_delay_days'] if session else 14)
    result = forecast_provider.predict(conn, version, route, target, cutoff, model_id)
    schedule = schedule_for(conn, version, route, target, target)
    payload = json_value({**result, **schedule,
        'reporting_delay_policy': '14 complete intervening days; simulated historical release',
        'virtual_time': target,
        'input_provenance': {'observation_version': version, 'schedule_snapshot': schedule['schedule_snapshot'],
                             'prior_schedule_snapshot': schedule['prior_snapshot']},
        'retrospective_replay': True})
    payload['inputs_sha256'] = hashlib.sha256(json.dumps(payload.get('inputs', []), sort_keys=True).encode()).hexdigest()
    issue = datetime.combine(target, datetime.min.time(), ZoneInfo('America/New_York'))
    forecast_id = str(uuid4())
    conn.execute('''INSERT INTO rr_forecasts
        (id,session_key,session_id,route,target_date,issued_at,data_version,model_version,available_through,prediction,status,payload)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
        (forecast_id, scope, session['id'] if session else None, route, target, issue, version,
         model_id, cutoff, result['prediction'], result['status'], Jsonb(payload)))
    return conn.execute('''SELECT * FROM rr_forecasts WHERE session_key=%s AND route=%s
        AND target_date=%s AND model_version=%s''', (scope, route, target, model_id)).fetchone()


def day_forecasts(conn, session):
    routes = conn.execute('SELECT route FROM rr_routes WHERE data_version=%s ORDER BY route', (session['data_version'],)).fetchall()
    for row in routes:
        store_forecast(conn, session['data_version'], row['route'], session['virtual_date'], session)


def replay_public(session):
    return {**session, 'available_through': latest_cutoff(session['virtual_date'], session['reporting_delay_days']),
            'reporting_policy': '14 complete intervening days; simulated release, not verified publisher arrivals',
            'mode': 'replay'}


def replay(conn, session_id, tick=True):
    session = conn.execute('SELECT * FROM rr_replays WHERE id=%s FOR UPDATE', (session_id,)).fetchone()
    if not session:
        raise HTTPException(404, 'Replay session not found')
    if tick and session['state'] == 'running':
        elapsed = max(0, (now() - session['wall_anchor']).total_seconds())
        steps = min(int(elapsed / session['speed_seconds']), (session['end_date'] - session['virtual_date']).days)
        if steps:
            for _ in range(steps):
                session['virtual_date'] += timedelta(days=1)
                day_forecasts(conn, session)
            session['wall_anchor'] += timedelta(seconds=steps * session['speed_seconds'])
            if session['virtual_date'] >= session['end_date']:
                session['state'] = 'completed'
            conn.execute('UPDATE rr_replays SET virtual_date=%s,wall_anchor=%s,state=%s WHERE id=%s',
                         (session['virtual_date'], session['wall_anchor'], session['state'], session_id))
    return session


def create_replay(conn, start, end, speed, parent=None):
    if not forecast_provider.REPLAY_START <= start <= end <= forecast_provider.REPLAY_END:
        raise HTTPException(422, f'Supported replay dates: {forecast_provider.REPLAY_START} through {forecast_provider.REPLAY_END}')
    version = parent['data_version'] if parent else current_version(conn)
    model = parent['model_version'] if parent else forecast_provider.MODEL_ID
    session_id = str(uuid4())
    conn.execute('''INSERT INTO rr_replays
        (id,parent_session_id,data_version,model_version,start_date,end_date,virtual_date,state,speed_seconds,wall_anchor)
        VALUES (%s,%s,%s,%s,%s,%s,%s,'paused',%s,%s)''',
        (session_id, parent['id'] if parent else None, version, model, start, end, start, speed, now()))
    session = replay(conn, session_id, False)
    day_forecasts(conn, session)
    return replay_public(session)


def control_replay(conn, session_id, action, days=1, speed=None):
    session = replay(conn, session_id)
    if action == 'reset':
        conn.execute("UPDATE rr_replays SET state='paused' WHERE id=%s", (session_id,))
        return create_replay(conn, session['start_date'], session['end_date'], speed or session['speed_seconds'], session)
    if speed is not None:
        session['speed_seconds'] = speed
    if action == 'advance':
        for _ in range(min(days, (session['end_date'] - session['virtual_date']).days)):
            session['virtual_date'] += timedelta(days=1)
            day_forecasts(conn, session)
        session['state'] = 'paused'
    elif action == 'start':
        session['state'] = 'running'
    elif action == 'pause':
        session['state'] = 'paused'
    if session['virtual_date'] == session['end_date']:
        session['state'] = 'completed'
    session['wall_anchor'] = now()
    conn.execute('UPDATE rr_replays SET virtual_date=%s,state=%s,speed_seconds=%s,wall_anchor=%s WHERE id=%s',
                 (session['virtual_date'], session['state'], session['speed_seconds'], session['wall_anchor'], session_id))
    return replay_public(session)


def context(conn, mode='historical', session_id=None):
    if mode == 'replay' or session_id:
        if not session_id:
            raise HTTPException(422, 'A replay session is required')
        session = replay(conn, session_id)
        return {'mode': 'replay', 'session_id': session_id, 'data_version': session['data_version'],
                'virtual_date': session['virtual_date'], 'available_through': latest_cutoff(session['virtual_date'], session['reporting_delay_days']),
                'reporting_delay_days': session['reporting_delay_days'], 'model_version': session['model_version']}
    version = current_version(conn)
    return {'mode': 'historical', 'data_version': version, 'available_through': None,
            'observation_units': 'published daily boarding estimates',
            'service_units': 'clock-date scheduled departures and passenger-trip service hours'}


def period(start, end, ctx):
    if start > end or (end - start).days > 1096:
        raise HTTPException(422, 'Choose an ordered date range of at most three years')
    allowed = min(end, ctx['available_through']) if ctx['available_through'] else end
    return start, allowed


def history(conn, route, start, end, ctx):
    required_route(conn, ctx['data_version'], route)
    first, last = period(start, end, ctx)
    rows = conn.execute('''SELECT date,rides,day_type,scheduled_trips,scheduled_hours,
        schedule_snapshot,prior_snapshot,eligible,schedule_eligible,quality
        FROM rr_daily WHERE data_version=%s AND route=%s AND date BETWEEN %s AND %s ORDER BY date''',
        (ctx['data_version'], route, first, last)).fetchall()
    return {'items': rows, 'context': {**ctx, 'route': route, 'requested_start': start, 'requested_end': end,
                                      'effective_end': last, 'rows': len(rows)}}


METRICS = {
    'mean_daily_rides': ('Mean daily boardings', 'boardings/day'),
    'rides_per_trip': ('Boardings per scheduled departure', 'boardings/departure'),
    'rides_per_hour': ('Boardings per scheduled service hour', 'boardings/service-hour'),
    'forecast_rides_per_trip': ('Forecast boardings per scheduled departure', 'predicted boardings/departure'),
}


def rankings(conn, start, end, day_type, minimum_days, metric, descending, ctx):
    if metric not in METRICS:
        raise HTTPException(422, 'Unknown ranking metric')
    first, last = period(start, end, ctx)
    demand_only = metric == 'mean_daily_rides'
    rows = conn.execute('''SELECT r.route,r.name,
        count(d.date) FILTER(WHERE d.rides IS NOT NULL) AS observed_days,
        count(d.date) FILTER(WHERE d.rides IS NOT NULL AND d.eligible AND d.scheduled_trips>0 AND d.scheduled_hours>0) AS matched_days,
        avg(d.rides) AS mean_rides,
        sum(d.rides) FILTER(WHERE d.eligible AND d.scheduled_trips>0 AND d.scheduled_hours>0) AS total_rides,
        sum(d.scheduled_trips) FILTER(WHERE d.eligible AND d.scheduled_trips>0 AND d.scheduled_hours>0 AND d.rides IS NOT NULL) AS total_trips,
        sum(d.scheduled_hours) FILTER(WHERE d.eligible AND d.scheduled_trips>0 AND d.scheduled_hours>0 AND d.rides IS NOT NULL) AS total_hours,
        array_remove(array_agg(DISTINCT d.schedule_snapshot),NULL) AS schedule_snapshots
        FROM rr_routes r LEFT JOIN rr_daily d ON d.data_version=r.data_version AND d.route=r.route
          AND d.date BETWEEN %s AND %s AND (%s='All' OR d.day_type=%s)
        WHERE r.data_version=%s GROUP BY r.route,r.name ORDER BY r.route''',
        (first, last, day_type, day_type, ctx['data_version'])).fetchall()
    for row in rows:
        count = row['observed_days'] if demand_only else row['matched_days']
        row['value'] = None
        row['reason'] = 'Eligible under the selected metric and minimum date count'
        if count < minimum_days:
            row['reason'] = f'Only {count} eligible dates; at least {minimum_days} required'
        elif demand_only:
            row['value'] = row['mean_rides']
        elif metric == 'forecast_rides_per_trip':
            if ctx['mode'] != 'replay':
                row['reason'] = 'Choose replay mode for a dated forecast and its scheduled-service denominator'
            else:
                pred = conn.execute('''SELECT prediction,status,payload FROM rr_forecasts
                    WHERE session_id=%s AND route=%s AND target_date=%s''',
                    (ctx['session_id'], row['route'], ctx['virtual_date'])).fetchone()
                trips = pred['payload'].get('scheduled_trips') if pred else None
                if pred and pred['prediction'] is not None and trips and trips > 0:
                    row['value'] = pred['prediction'] / trips
                else:
                    row['reason'] = 'Forecast or positive issue-time eligible schedule unavailable'
        else:
            denominator = row['total_trips'] if metric == 'rides_per_trip' else row['total_hours']
            if denominator and denominator > 0 and row['total_rides'] is not None:
                row['value'] = row['total_rides'] / denominator
            else:
                row['reason'] = 'Positive matched scheduled-service denominator unavailable'
        row['eligible'] = row['value'] is not None
    rows.sort(key=lambda row: (not row['eligible'], (-1 if descending else 1) * (row['value'] or 0), row['route']))
    rank = 0
    for row in rows:
        if row['eligible']:
            rank += 1
            row['rank'] = rank
        else:
            row['rank'] = None
    return {'items': rows, 'context': {**ctx, 'start_date': first, 'end_date': last,
        'requested_end': end, 'day_type': day_type, 'minimum_days': minimum_days, 'metric': metric,
        'metric_name': METRICS[metric][0], 'units': METRICS[metric][1],
        'eligible_routes': rank, 'aggregation': 'Ratios of sums over the same eligible route/date records',
        'interpretation': 'Planning review indicator; not occupancy, efficiency or a service-cut recommendation'}}


def compare(conn, routes, start, end, day_type, ctx):
    if len(routes) < 2 or len(routes) > 6 or len(set(routes)) != len(routes):
        raise HTTPException(422, 'Select two to six distinct routes')
    for route in routes:
        required_route(conn, ctx['data_version'], route)
    first, last = period(start, end, ctx)
    records = conn.execute('''SELECT * FROM rr_daily WHERE data_version=%s AND route=ANY(%s)
        AND date BETWEEN %s AND %s AND (%s='All' OR day_type=%s) ORDER BY date''',
        (ctx['data_version'], routes, first, last, day_type, day_type)).fetchall()
    eligible = {route: {r['date'] for r in records if r['route'] == route and r['eligible']
                       and r['rides'] is not None and r['scheduled_trips'] is not None
                       and r['scheduled_trips'] > 0 and r['scheduled_hours'] is not None
                       and r['scheduled_hours'] > 0} for route in routes}
    shared = set.intersection(*eligible.values())
    items = []
    for route in routes:
        data = [r for r in records if r['route'] == route and r['date'] in shared]
        rides = sum(r['rides'] for r in data)
        trips = sum(r['scheduled_trips'] for r in data)
        hours = sum(r['scheduled_hours'] for r in data)
        items.append({**required_route(conn, ctx['data_version'], route), 'common_days': len(shared),
            'mean_daily_rides': rides / len(shared) if shared else None,
            'mean_daily_trips': trips / len(shared) if shared else None,
            'mean_daily_hours': hours / len(shared) if shared else None,
            'rides_per_trip': rides / trips if trips else None, 'rides_per_hour': rides / hours if hours else None,
            'schedule_snapshots': sorted({r['schedule_snapshot'] for r in data if r['schedule_snapshot']}),
            'eligible': bool(shared), 'reason': None if shared else 'No common eligible service dates'})
    return {'items': items, 'context': {**ctx, 'start_date': first, 'end_date': last, 'day_type': day_type,
        'common_days': len(shared), 'common_dates': sorted(shared),
        'comparison_basis': 'Intersection of eligible route/date observations across every selected route'}}


def public_forecast(conn, row, ctx):
    payload = row['payload']
    allowed = ctx['available_through']
    actual = None
    if allowed is None or row['target_date'] <= allowed:
        item = conn.execute('SELECT rides FROM rr_daily WHERE data_version=%s AND route=%s AND date=%s',
                            (row['data_version'], row['route'], row['target_date'])).fetchone()
        actual = item['rides'] if item else None
    return {**{k: v for k, v in row.items() if k not in ('payload', 'session_key')},
            **payload, 'actual': actual, 'actual_available': actual is not None,
            'actual_status': 'released' if actual is not None else 'not_released_or_unavailable'}


def create_scenario(conn, request, ctx):
    route, day = request.route, request.date
    required_route(conn, ctx['data_version'], route)
    if ctx['mode'] == 'replay' and day > ctx['virtual_date']:
        raise HTTPException(422, 'Scenario date cannot exceed the replay virtual date')
    schedule = schedule_for(conn, ctx['data_version'], route, day,
                            ctx['virtual_date'] if ctx['mode'] == 'replay' else None)
    trips, hours = schedule['scheduled_trips'], schedule['scheduled_hours']
    if not schedule['schedule_eligible'] or trips is None or hours is None or trips <= 0 or hours < 0:
        raise HTTPException(422, 'Baseline needs positive eligible scheduled trips and complete scheduled duration')
    forecast_id = None
    model_version = None
    if request.demand_source == 'observed':
        if ctx['available_through'] and day > ctx['available_through']:
            raise HTTPException(422, 'The scenario observation is not yet released in this replay')
        result = conn.execute('SELECT rides FROM rr_daily WHERE data_version=%s AND route=%s AND date=%s',
                              (ctx['data_version'], route, day)).fetchone()
        demand = result['rides'] if result else None
    else:
        if not request.forecast_id:
            raise HTTPException(422, 'Choose a saved forecast')
        result = conn.execute('SELECT * FROM rr_forecasts WHERE id=%s', (request.forecast_id,)).fetchone()
        if not result or result['route'] != route or result['target_date'] != day or result['data_version'] != ctx['data_version']:
            raise HTTPException(422, 'Forecast route, date or dataset does not match the scenario')
        if ctx['mode'] == 'replay' and result['session_id'] != ctx['session_id']:
            raise HTTPException(422, 'Use a forecast from this replay session')
        if ctx['mode'] == 'replay' and result['target_date'] > ctx['virtual_date']:
            raise HTTPException(422, 'Forecast is outside the replay clock')
        demand, forecast_id, model_version = result['prediction'], result['id'], result['model_version']
        # Use the exact issue-time schedule retained with the forecast.
        schedule = {k: result['payload'].get(k) for k in schedule}
        trips, hours = schedule['scheduled_trips'], schedule['scheduled_hours']
        if not schedule['schedule_eligible'] or trips is None or trips <= 0 or hours is None:
            raise HTTPException(422, 'Forecast has no eligible issue-time scheduled-service baseline')
    if demand is None:
        raise HTTPException(422, 'Baseline demand unavailable')
    mean_duration = hours / trips
    proposed_demand = demand * request.demand_multiplier
    proposed_hours = request.proposed_trips * mean_duration
    def values(d, n, h):
        return {'rides': d, 'scheduled_trips': n, 'scheduled_hours': h,
                'rides_per_trip': d / n if n > 0 else None, 'rides_per_hour': d / h if h > 0 else None}
    baseline, proposed = values(demand, trips, hours), values(proposed_demand, request.proposed_trips, proposed_hours)
    scenario_id = str(uuid4())
    payload = {'id': scenario_id, 'title': request.title, 'route': route, 'date': day.isoformat(),
        'mode': 'scenario', 'data_version': ctx['data_version'], 'forecast_id': forecast_id,
        'model_version': model_version, 'session_id': ctx.get('session_id'), 'demand_source': request.demand_source,
        'baseline': baseline, 'proposed': proposed,
        'delta': {k: proposed[k] - baseline[k] if proposed[k] is not None and baseline[k] is not None else None for k in baseline},
        'schedule_snapshot': schedule['schedule_snapshot'], 'prior_schedule_snapshot': schedule['prior_snapshot'],
        'assumed_hours_per_departure': mean_duration, 'demand_multiplier': request.demand_multiplier,
        'duration_assumption': 'Fixed clock-date service-hour exposure per departure (baseline hours/departures), not a measured trip cycle',
        'units': {'rides': 'daily boardings', 'scheduled_trips': 'clock-date scheduled departures',
                  'scheduled_hours': 'scheduled passenger-trip service hours'},
        'assumptions': ['Service-hour exposure per departure is held at baseline hours divided by departures; this is not a measured trip-cycle duration.',
            'Demand multiplier is an independent scenario assumption, not a model response to service.',
            'Zero proposed service has undefined boarding/service ratios.',
            'Fractional departures are scenario arithmetic, not an executable timetable.',
            'No measured passenger benefit, occupancy, operating-cost or fleet feasibility claim.'],
        'baseline_provenance': {'data_version': ctx['data_version'], 'route': route, 'date': day.isoformat(),
                                'forecast_id': forecast_id, 'model_version': model_version}}
    conn.execute('INSERT INTO rr_scenarios(id,session_id,data_version,route,date,payload) VALUES (%s,%s,%s,%s,%s,%s)',
                 (scenario_id, ctx.get('session_id'), ctx['data_version'], route, day, Jsonb(payload)))
    return payload
