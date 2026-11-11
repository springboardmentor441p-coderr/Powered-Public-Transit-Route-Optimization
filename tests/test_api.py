"""PostgreSQL integration checks for release boundaries and immutable planning records.

Uses a temporary schema in the configured local database; source data is not modified.
Run: python -m unittest discover -s tests -p test_api.py -v
"""
from datetime import date, timedelta
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend.db import connection, database_url, initialize
from backend.main import app
from backend import forecast_provider


class PlanningAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = 'rr_test_' + uuid4().hex
        cls.previous_schema = os.environ.get('ROUTER_DB_SCHEMA')
        with psycopg.connect(database_url(), connect_timeout=5) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
        os.environ['ROUTER_DB_SCHEMA'] = cls.schema
        with connection() as conn:
            initialize(conn)
            conn.execute('INSERT INTO rr_dataset_versions VALUES (%s,now(),%s)',
                         ('fixture', Jsonb({'scope': 'isolated test fixture', 'routes': 2})))
            conn.execute("INSERT INTO rr_settings VALUES ('current_data_version','fixture')")
            conn.execute("INSERT INTO rr_routes VALUES ('fixture','M1','Fixture one'),('fixture','M2','Fixture two')")
            conn.execute('INSERT INTO rr_models VALUES (%s,%s,%s)',
                         (forecast_provider.MODEL_ID, 'fixture', Jsonb(forecast_provider.MODEL_METADATA)))
            start = date(2026, 1, 1)
            rows = []
            for route, count in [('M1', 100), ('M2', 200)]:
                for step in range(243):
                    day = start + timedelta(days=step)
                    day_type = 'Weekday' if day.weekday() < 5 else ('Saturday' if day.weekday() == 5 else 'Sunday')
                    rows.append(('fixture', route, day, count, count, day_type, 10, 20, True, True,
                                 'manhattan_20251230', 'manhattan_20251230', Jsonb({})))
            with conn.cursor() as cur:
                cur.executemany('INSERT INTO rr_daily VALUES (' + ','.join(['%s'] * 13) + ')', rows)
            conn.execute("INSERT INTO rr_profiles VALUES ('fixture','M1','future','2026-07-01','2026-07-31',%s)",
                         (Jsonb({'group_id': 0, 'grouping_status': 'exploratory_only'}),))
            conn.execute("INSERT INTO rr_geometry VALUES ('fixture','M1','future','2026-09-04',%s)", (Jsonb([]),))
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if cls.previous_schema is None:
            os.environ.pop('ROUTER_DB_SCHEMA', None)
        else:
            os.environ['ROUTER_DB_SCHEMA'] = cls.previous_schema
        assert cls.schema.startswith('rr_test_') and len(cls.schema) == 40
        with psycopg.connect(database_url(), connect_timeout=5) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))

    def session(self, **kwargs):
        response = self.client.post('/api/replays', json=kwargs)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_history_rankings_and_comparison_enforce_release(self):
        session = self.session()
        params = {'session_id': session['id'], 'start_date': '2026-05-01', 'end_date': '2026-07-31'}
        result = self.client.get('/api/routes/M1/history', params=params).json()
        self.assertEqual(max(x['date'] for x in result['items']), '2026-05-17')
        self.assertEqual(result['context']['mode'], 'replay')
        result = self.client.get('/api/rankings', params={**params, 'minimum_days': 1}).json()
        self.assertEqual({x['observed_days'] for x in result['items']}, {17})
        result = self.client.get('/api/routes/compare', params={**params, 'routes': 'M1,M2'}).json()
        self.assertEqual(result['context']['common_days'], 17)
        self.assertEqual(result['items'][0]['mean_daily_rides'], 100)

    def test_forecast_idempotency_and_delayed_actual(self):
        session = self.session()
        request = {'route': 'M1', 'target_date': '2026-06-01', 'session_id': session['id']}
        first = self.client.post('/api/forecasts', json=request).json()
        self.assertEqual(first['actual'], None)
        self.assertTrue(all(x['date'] <= '2026-05-17' for x in first['inputs']))
        second = self.client.post('/api/forecasts', json=request).json()
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['prediction'], second['prediction'])
        self.client.post(f"/api/replays/{session['id']}/control", json={'action': 'advance', 'days': 15})
        rows = self.client.get('/api/forecasts', params={'session_id': session['id'], 'route': 'M1'}).json()['items']
        revealed = next(x for x in rows if x['id'] == first['id'])
        self.assertEqual(revealed['actual'], 100)
        self.assertEqual(revealed['prediction'], first['prediction'])
        self.assertEqual(revealed['inputs_sha256'], first['inputs_sha256'])

    def test_future_profile_and_map_are_withheld(self):
        session = self.session()
        params = {'session_id': session['id']}
        self.assertEqual(self.client.get('/api/route-groups', params=params).json()['items'], [])
        self.assertEqual(self.client.get('/api/routes/M1/geometry', params=params).json()['status'], 'unavailable')
        self.assertTrue(self.client.get('/api/route-groups').json()['items'])

    def test_reset_preserves_audit_and_creates_new_identity(self):
        first = self.session()
        old = self.client.get('/api/forecasts', params={'session_id': first['id']}).json()['items']
        reset = self.client.post(f"/api/replays/{first['id']}/control", json={'action': 'reset'}).json()
        self.assertNotEqual(first['id'], reset['id'])
        self.assertEqual(reset['parent_session_id'], first['id'])
        self.assertEqual(reset['virtual_date'], '2026-06-01')
        retained = self.client.get('/api/forecasts', params={'session_id': first['id']}).json()['items']
        self.assertEqual([x['id'] for x in old], [x['id'] for x in retained])

    def test_running_clock_advances_and_pause_stops_it(self):
        session = self.session(speed_seconds=1)
        self.client.post(f"/api/replays/{session['id']}/control", json={'action': 'start'})
        with connection() as conn:
            conn.execute("UPDATE rr_replays SET wall_anchor=now()-interval '2.1 seconds' WHERE id=%s", (session['id'],))
        result = self.client.get(f"/api/replays/{session['id']}").json()
        self.assertGreaterEqual(result['virtual_date'], '2026-06-03')
        paused = self.client.post(f"/api/replays/{session['id']}/control", json={'action': 'pause'}).json()
        with connection() as conn:
            conn.execute("UPDATE rr_replays SET wall_anchor=now()-interval '10 seconds' WHERE id=%s", (session['id'],))
        self.assertEqual(self.client.get(f"/api/replays/{session['id']}").json()['virtual_date'], paused['virtual_date'])

    def test_unreleased_observation_scenario_rejected(self):
        session = self.session()
        request = {'route': 'M1', 'date': '2026-06-01', 'proposed_trips': 12, 'session_id': session['id']}
        self.assertEqual(self.client.post('/api/scenarios', json=request).status_code, 422)

    def test_zero_service_scenario_and_source_immutability(self):
        request = {'route': 'M1', 'date': '2026-06-01', 'proposed_trips': 0}
        response = self.client.post('/api/scenarios', json=request)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body['baseline']['scheduled_trips'], 10)
        self.assertEqual(body['proposed']['scheduled_hours'], 0)
        self.assertIsNone(body['proposed']['rides_per_trip'])
        self.assertIsNone(body['proposed']['rides_per_hour'])
        self.assertEqual(body['baseline']['rides'], body['proposed']['rides'])
        with connection() as conn:
            self.assertEqual(conn.execute("SELECT scheduled_trips FROM rr_daily WHERE data_version='fixture' AND route='M1' AND date='2026-06-01'").fetchone()['scheduled_trips'], 10)

    def test_forecast_scenario_uses_same_session_and_versions(self):
        session, other = self.session(), self.session()
        forecast = self.client.post('/api/forecasts', json={'route': 'M1', 'target_date': '2026-06-01', 'session_id': session['id']}).json()
        request = {'route': 'M1', 'date': '2026-06-01', 'proposed_trips': 12, 'demand_source': 'forecast',
                   'forecast_id': forecast['id'], 'session_id': session['id']}
        result = self.client.post('/api/scenarios', json=request)
        self.assertEqual(result.status_code, 201, result.text)
        body = result.json()
        self.assertEqual(body['forecast_id'], forecast['id'])
        self.assertEqual(body['model_version'], forecast['model_version'])
        self.assertEqual(body['proposed']['scheduled_hours'], 24)
        request['session_id'] = other['id']
        self.assertEqual(self.client.post('/api/scenarios', json=request).status_code, 422)

    def test_invalid_dates_counts_routes_and_future_forecast(self):
        self.assertEqual(self.client.post('/api/replays', json={'start_date': '2026-08-01'}).status_code, 422)
        self.assertEqual(self.client.get('/api/routes/missing/history').status_code, 404)
        self.assertEqual(self.client.get('/api/routes/compare', params={'routes': 'M1,M1'}).status_code, 422)
        self.assertEqual(self.client.get('/api/rankings', params={'minimum_days': 0}).status_code, 422)
        self.assertEqual(self.client.post('/api/scenarios', json={'route': 'M1', 'date': '2026-06-01', 'proposed_trips': -1}).status_code, 422)
        session = self.session()
        self.assertEqual(self.client.post('/api/forecasts', json={'route': 'M1', 'target_date': '2026-06-02', 'session_id': session['id']}).status_code, 422)

    def test_ratio_of_sums_and_minimum_days(self):
        params = {'start_date': '2026-06-01', 'end_date': '2026-06-05', 'minimum_days': 5, 'metric': 'rides_per_hour'}
        result = self.client.get('/api/rankings', params=params).json()
        self.assertEqual(result['items'][0]['route'], 'M2')
        self.assertEqual(result['items'][0]['value'], 10)
        params['minimum_days'] = 6
        self.assertFalse(any(x['eligible'] for x in self.client.get('/api/rankings', params=params).json()['items']))

    def test_positive_demand_zero_service_is_excluded_from_ratios(self):
        with connection() as conn:
            conn.execute("UPDATE rr_daily SET scheduled_trips=0,scheduled_hours=0 WHERE data_version='fixture' AND route='M2' AND date='2026-06-03'")
        params = {'start_date': '2026-06-01', 'end_date': '2026-06-05', 'minimum_days': 4, 'metric': 'rides_per_hour'}
        row = next(x for x in self.client.get('/api/rankings', params=params).json()['items'] if x['route'] == 'M2')
        self.assertEqual(row['observed_days'], 5)
        self.assertEqual(row['matched_days'], 4)
        self.assertEqual(row['value'], 10)
        with connection() as conn:
            conn.execute("UPDATE rr_daily SET scheduled_trips=10,scheduled_hours=20 WHERE data_version='fixture' AND route='M2' AND date='2026-06-03'")

    def test_capture_day_schedule_is_not_assumed_available_at_midnight(self):
        from backend.service import schedule_for
        with connection() as conn:
            conn.execute("UPDATE rr_daily SET schedule_snapshot='manhattan_20260601' WHERE data_version='fixture' AND route='M2' AND date='2026-06-01'")
            withheld = schedule_for(conn, 'fixture', 'M2', date(2026, 6, 1), date(2026, 6, 1))
            self.assertFalse(withheld['schedule_eligible'])
            self.assertIsNone(withheld['scheduled_trips'])
            conn.execute("UPDATE rr_daily SET schedule_snapshot='manhattan_20251230' WHERE data_version='fixture' AND route='M2' AND date='2026-06-01'")

    def test_model_evaluation_outcomes_not_exposed_inside_replay(self):
        session = self.session()
        rows = self.client.get('/api/models', params={'session_id': session['id']}).json()['items']
        self.assertEqual(len(rows), 1)
        self.assertNotIn('metrics', rows[0]['metadata'])

    def test_registered_model_identity_survives_default_provider_change(self):
        if forecast_provider.MODEL_ID == forecast_provider.REFERENCE_ID:
            self.skipTest('Fitted experiment bundle is not installed')
        with connection() as conn:
            model_id = forecast_provider.MODEL_ID
            first = forecast_provider.predict(conn, 'fixture', 'M1', date(2026, 6, 1), date(2026, 5, 17), model_id)
            with patch.object(forecast_provider, 'MODEL_ID', 'new_default_not_in_this_session'):
                second = forecast_provider.predict(conn, 'fixture', 'M1', date(2026, 6, 1), date(2026, 5, 17), model_id)
            self.assertEqual(first['prediction'], second['prediction'])
            self.assertEqual(second['status'], 'prediction')
            self.assertEqual(second['latest_available_ride_date'], date(2026, 5, 17))
            self.assertLess(second['latest_input_ride_date'], second['latest_available_ride_date'])

    def test_bad_fitted_artifact_returns_explicit_validated_fallback(self):
        if forecast_provider.MODEL_ID == forecast_provider.REFERENCE_ID:
            self.skipTest('Fitted experiment bundle is not installed')
        with connection() as conn, patch.object(forecast_provider, '_load_model', side_effect=ValueError('bad hash')):
            result = forecast_provider.predict(conn, 'fixture', 'M1', date(2026, 6, 1), date(2026, 5, 17), forecast_provider.MODEL_ID)
            self.assertEqual(result['status'], 'validated_fallback')
            self.assertEqual(result['prediction'], 100)
            self.assertTrue(result['fallback_reason'])


if __name__ == '__main__':
    unittest.main()
