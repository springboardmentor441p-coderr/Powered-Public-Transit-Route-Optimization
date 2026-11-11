"""FastAPI endpoints for dated analysis, historical replay and service scenarios."""
from datetime import date
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psycopg
from pydantic import BaseModel, ConfigDict, Field

from backend.db import connection, current_version
from backend import service, forecast_provider

app = FastAPI(title='RouteRanker planning API', version='1.0.0',
              description='Historical evidence, controlled replay and explicit planning scenarios.')
app.add_middleware(CORSMiddleware, allow_origins=[
    'http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:4173', 'http://localhost:4173'],
    allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(request, exc):
    return JSONResponse(status_code=503, content={'detail': 'PostgreSQL is unavailable. Start the database and verify DATABASE_URL.'})


@app.exception_handler(psycopg.errors.UndefinedTable)
def database_not_imported(request, exc):
    return JSONResponse(status_code=503, content={'detail': 'Database not initialized. Run python -m backend.import_data.'})


@app.exception_handler(ValueError)
def invalid_state(request, exc):
    return JSONResponse(status_code=422, content={'detail': str(exc)})


Mode = Literal['historical', 'replay']
DayType = Literal['All', 'Weekday', 'Saturday', 'Sunday']


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class ReplayRequest(StrictRequest):
    start_date: date = forecast_provider.REPLAY_START
    end_date: date = forecast_provider.REPLAY_END
    speed_seconds: float = Field(default=5, ge=1, le=3600)


class ControlRequest(StrictRequest):
    action: Literal['start', 'pause', 'advance', 'reset']
    days: int = Field(default=1, ge=1, le=365)
    speed_seconds: float | None = Field(default=None, ge=1, le=3600)


class ForecastRequest(StrictRequest):
    route: str = Field(min_length=1, max_length=32)
    target_date: date
    session_id: str | None = None


class ScenarioRequest(StrictRequest):
    route: str = Field(min_length=1, max_length=32)
    date: date
    proposed_trips: float = Field(ge=0, le=100000)
    demand_source: Literal['observed', 'forecast'] = 'observed'
    forecast_id: str | None = None
    session_id: str | None = None
    demand_multiplier: float = Field(default=1, ge=0, le=10)
    title: str = Field(default='Service scenario', min_length=1, max_length=160)


@app.get('/api/health')
def health():
    with connection() as conn:
        return {'status': 'ok', 'database': 'PostgreSQL', 'data_version': current_version(conn)}


@app.get('/api/data/coverage')
def coverage(mode: Mode = 'historical', session_id: str | None = None):
    with connection() as conn:
        ctx = service.context(conn, mode, session_id)
        row = conn.execute('SELECT * FROM rr_dataset_versions WHERE id=%s', (ctx['data_version'],)).fetchone()
        return {**row['metadata'], 'data_version': row['id'], 'imported_at': row['imported_at'],
                'replay_start': forecast_provider.REPLAY_START, 'replay_end': forecast_provider.REPLAY_END,
                'context': ctx}


@app.get('/api/routes')
def routes(mode: Mode = 'historical', session_id: str | None = None):
    with connection() as conn:
        ctx = service.context(conn, mode, session_id)
        rows = conn.execute('SELECT route,name FROM rr_routes WHERE data_version=%s ORDER BY route', (ctx['data_version'],)).fetchall()
        return {'items': rows, 'context': ctx}


@app.get('/api/routes/compare')
def compare(routes: str, start_date: date = date(2026, 7, 6), end_date: date = date(2026, 9, 27),
            day_type: DayType = 'All', mode: Mode = 'historical', session_id: str | None = None):
    with connection() as conn:
        return service.compare(conn, [x.strip() for x in routes.split(',')], start_date, end_date, day_type,
                               service.context(conn, mode, session_id))


@app.get('/api/routes/{route}/history')
def route_history(route: str, start_date: date = date(2026, 1, 1), end_date: date = date(2026, 9, 30),
                  mode: Mode = 'historical', session_id: str | None = None):
    with connection() as conn:
        return service.history(conn, route, start_date, end_date, service.context(conn, mode, session_id))


@app.get('/api/routes/{route}/geometry')
def geometry(route: str, mode: Mode = 'historical', session_id: str | None = None):
    with connection() as conn:
        ctx = service.context(conn, mode, session_id)
        service.required_route(conn, ctx['data_version'], route)
        rows = conn.execute('SELECT * FROM rr_geometry WHERE data_version=%s AND route=%s ORDER BY available_from DESC',
                            (ctx['data_version'], route)).fetchall()
        if ctx['mode'] == 'replay':
            rows = [r for r in rows if r['available_from'] <= ctx['virtual_date']]
        if not rows:
            return {'route': route, 'paths': [], 'geometry_version': None, 'status': 'unavailable',
                    'reason': 'No imported geometry available at this issue date', 'context': ctx}
        return {**rows[0], 'status': 'available', 'context': ctx}


@app.get('/api/rankings')
def rankings(start_date: date = date(2026, 7, 6), end_date: date = date(2026, 9, 27),
             day_type: DayType = 'All', minimum_days: int = Query(20, ge=1, le=1096),
             metric: str = 'mean_daily_rides', descending: bool = True,
             mode: Mode = 'historical', session_id: str | None = None):
    with connection() as conn:
        return service.rankings(conn, start_date, end_date, day_type, minimum_days, metric, descending,
                                service.context(conn, mode, session_id))


@app.get('/api/route-groups')
def groups(mode: Mode = 'historical', session_id: str | None = None):
    with connection() as conn:
        ctx = service.context(conn, mode, session_id)
        rows = conn.execute('SELECT * FROM rr_profiles WHERE data_version=%s ORDER BY route,last_date DESC', (ctx['data_version'],)).fetchall()
        if ctx['available_through']:
            rows = [r for r in rows if r['last_date'] <= ctx['available_through']]
        # One explicitly versioned profile per route; prefer latest permissible period.
        selected = {}
        for row in rows:
            selected.setdefault(row['route'], {**row['payload'], 'route': row['route'], 'profile_version': row['profile_version'],
                                              'first_date': row['first_date'], 'last_date': row['last_date']})
        return {'items': list(selected.values()), 'context': {**ctx,
            'status': 'exploratory_only' if selected else 'unavailable',
            'reason': 'Groups describe profile similarity; no performance class' if selected else 'No profile period is fully released at the replay clock'}}


@app.get('/api/models')
def models(mode: Mode = 'historical', session_id: str | None = None):
    with connection() as conn:
        ctx = service.context(conn, mode, session_id)
        rows = conn.execute('SELECT * FROM rr_models WHERE data_version=%s ORDER BY id', (ctx['data_version'],)).fetchall()
        if ctx['mode'] == 'replay':
            rows = [r for r in rows if r['id'] == ctx['model_version']]
            for row in rows:
                row['metadata'] = {k: v for k, v in row['metadata'].items() if k != 'metrics'}
        return {'items': rows, 'context': ctx}


@app.post('/api/replays', status_code=201)
def new_replay(request: ReplayRequest):
    with connection() as conn:
        return service.create_replay(conn, request.start_date, request.end_date, request.speed_seconds)


@app.get('/api/replays/{session_id}')
def get_replay(session_id: str):
    with connection() as conn:
        return service.replay_public(service.replay(conn, session_id))


@app.post('/api/replays/{session_id}/control')
def replay_control(session_id: str, request: ControlRequest):
    with connection() as conn:
        return service.control_replay(conn, session_id, request.action, request.days, request.speed_seconds)


@app.post('/api/forecasts')
def forecast(request: ForecastRequest):
    with connection() as conn:
        ctx = service.context(conn, 'replay' if request.session_id else 'historical', request.session_id)
        if not forecast_provider.REPLAY_START <= request.target_date <= forecast_provider.REPLAY_END:
            raise HTTPException(422, 'Target outside this frozen model demonstration period')
        session = service.replay(conn, request.session_id, False) if request.session_id else None
        if session and request.target_date != session['virtual_date']:
            raise HTTPException(422, 'New replay forecasts must target the current virtual date')
        row = service.store_forecast(conn, ctx['data_version'], request.route, request.target_date, session)
        return service.public_forecast(conn, row, ctx)


@app.get('/api/forecasts')
def forecasts(session_id: str | None = None, route: str | None = None, mode: Mode = 'historical'):
    with connection() as conn:
        ctx = service.context(conn, mode, session_id)
        rows = conn.execute('''SELECT * FROM rr_forecasts WHERE data_version=%s
            AND session_key=%s AND (%s::text IS NULL OR route=%s)
            ORDER BY target_date DESC,route''', (ctx['data_version'], session_id or 'historical', route, route)).fetchall()
        if ctx['mode'] == 'replay':
            rows = [r for r in rows if r['target_date'] <= ctx['virtual_date']]
        return {'items': [service.public_forecast(conn, r, ctx) for r in rows], 'context': ctx}


@app.post('/api/scenarios', status_code=201)
def scenario(request: ScenarioRequest):
    with connection() as conn:
        ctx = service.context(conn, 'replay' if request.session_id else 'historical', request.session_id)
        return service.create_scenario(conn, request, ctx)


@app.get('/api/scenarios')
def scenarios(session_id: str | None = None, mode: Mode = 'historical'):
    with connection() as conn:
        ctx = service.context(conn, mode, session_id)
        if ctx['mode'] == 'replay':
            rows = conn.execute('''SELECT payload,created_at FROM rr_scenarios WHERE session_id=%s
                AND date<=%s ORDER BY created_at DESC''', (session_id, ctx['virtual_date'])).fetchall()
        else:
            rows = conn.execute('SELECT payload,created_at FROM rr_scenarios WHERE data_version=%s ORDER BY created_at DESC', (ctx['data_version'],)).fetchall()
        return {'items': [{**r['payload'], 'created_at': r['created_at']} for r in rows], 'context': ctx}


# A built frontend is served by the same origin in packaged deployments.
from pathlib import Path
from fastapi.staticfiles import StaticFiles
_frontend = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'
if _frontend.is_dir():
    app.mount('/', StaticFiles(directory=_frontend, html=True), name='planning_frontend')
