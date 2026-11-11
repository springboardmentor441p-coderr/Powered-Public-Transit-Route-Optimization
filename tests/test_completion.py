"""Importer, planning and independent-label boundaries; fixtures stay in tests."""
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard.data import table
from scripts.gtfs_import import inspect_gtfs, FeedError
from scripts.planning_proposals import allocate_service, save_proposal, load_proposals, candidate_actions, route_change_candidates
from scripts.load_classification import validate_labels, train_classifier

ROOT = Path(__file__).resolve().parents[1]


def feed(changes=None):
    files = {
        'agency.txt':'agency_timezone\nAmerica/New_York\n',
        'routes.txt':'route_id,route_type,route_long_name\nR,3,Test route\n',
        'trips.txt':'route_id,service_id,trip_id\nR,S,T\n',
        'stops.txt':'stop_id,stop_name,stop_lat,stop_lon\nA,First,40.7,-73.9\nB,Last,40.8,-73.9\n',
        'stop_times.txt':'trip_id,stop_id,stop_sequence,arrival_time,departure_time\nT,A,1,23:50:00,23:50:00\nT,B,2,24:20:00,24:20:00\n',
        'calendar_dates.txt':'service_id,date,exception_type\nS,20260914,1\n'}
    for key, value in (changes or {}).items():
        if value is None: files.pop(key, None)
        else: files[key] = value
    data = BytesIO()
    with ZipFile(data,'w') as archive:
        for key,value in files.items(): archive.writestr(key,value)
    return data.getvalue()


class ImportTests(unittest.TestCase):
    def test_exceptions_only_calendar_and_extended_hours(self):
        summary, routes, trips = inspect_gtfs(feed(), '2026-09-14')
        self.assertEqual(summary['active_services'],1)
        self.assertAlmostEqual(routes.service_hours.iloc[0],.5)
        self.assertEqual(routes.scheduled_or_expected_departures.iloc[0],1)
        self.assertFalse(summary['passenger_observations_imported'])
        _, no_service, _ = inspect_gtfs(feed(),'2026-09-15')
        self.assertEqual(no_service.scheduled_or_expected_departures.iloc[0],0)

    def test_calendar_removal(self):
        weekly='service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nS,1,1,1,1,1,1,1,20260101,20261231\n'
        _, rows, _ = inspect_gtfs(feed({'calendar.txt':weekly,'calendar_dates.txt':'service_id,date,exception_type\nS,20260914,2\n'}),'2026-09-14')
        self.assertEqual(rows.scheduled_or_expected_departures.iloc[0],0)

    def test_frequency_templates_are_not_counted_once(self):
        frequency='trip_id,start_time,end_time,headway_secs,exact_times\nT,08:00:00,09:05:00,1800,1\n'
        _, routes, _ = inspect_gtfs(feed({'frequencies.txt':frequency}),'2026-09-14')
        self.assertEqual(routes.scheduled_or_expected_departures.iloc[0],3)
        self.assertAlmostEqual(routes.service_hours.iloc[0],1.5)
        frequency=frequency.replace(',1\n',',0\n')
        _, routes, _ = inspect_gtfs(feed({'frequencies.txt':frequency}),'2026-09-14')
        self.assertAlmostEqual(routes.scheduled_or_expected_departures.iloc[0],65/30)
        self.assertTrue(routes.counts_include_expected_service.iloc[0])

    def test_missing_endpoint_withholds_hours_but_keeps_trip_count(self):
        event='trip_id,stop_id,stop_sequence,arrival_time,departure_time\nT,A,1,08:00:00,08:00:00\nT,B,2,,\n'
        summary, routes, _ = inspect_gtfs(feed({'stop_times.txt':event}),'2026-09-14')
        self.assertEqual(routes.scheduled_or_expected_departures.iloc[0],1)
        self.assertTrue(pd.isna(routes.service_hours.iloc[0]))
        self.assertEqual(summary['bus_templates_with_unavailable_duration'],1)

    def test_bad_keys_references_times_and_unsafe_members_block(self):
        for changes in [
            {'../routes.txt':'x'},
            {'trips.txt':'route_id,service_id,trip_id\nUNKNOWN,S,T\n'},
            {'stop_times.txt':'trip_id,stop_id,stop_sequence,arrival_time,departure_time\nT,A,1,08:99:00,08:99:00\n'},
            {'calendar_dates.txt':None},
            {'calendar_dates.txt':'service_id,date,exception_type\nS,20260914,1\nS,20260914,2\n'}]:
            with self.subTest(changes=list(changes)):
                with self.assertRaises(FeedError): inspect_gtfs(feed(changes),'2026-09-14')
        with self.assertRaises(FeedError): inspect_gtfs(feed(),'2026-09-14',max_expanded_bytes=1)


class PlanningTests(unittest.TestCase):
    def test_zero_budget_identity_and_source_gate(self):
        result, excluded, summary = allocate_service(table('baselines'),'Weekday',0,.2)
        np.testing.assert_allclose(result.mean_departures,result.scenario_mean_departures)
        self.assertEqual(list(excluded.bus_route),['M98'])
        self.assertEqual(summary['spent_added_bus_hours'],0)

    def test_budget_cap_and_equal_spend_comparison(self):
        result, excluded, summary = allocate_service(table('baselines'),'Weekday',50,.2)
        self.assertLessEqual(result.delta_mean_bus_hours.sum(),50+1e-8)
        self.assertTrue(result.scenario_mean_departures.ge(result.mean_departures-1e-8).all())
        self.assertTrue(result.scenario_mean_departures.le(result.mean_departures*1.2+1e-8).all())
        self.assertLessEqual(summary['allocation_objective'],summary['equal_spend_uniform_objective']+1e-5)
        self.assertFalse(summary['passenger_benefit_measured'])

    def test_simple_analytic_optimum(self):
        rows=pd.DataFrame({'bus_route':['A','B'],'day_type':['Weekday']*2,'baseline_eligible':[True]*2,
                           'baseline_status':['eligible']*2,'mean_boardings':[100.,200.],
                           'mean_departures':[10.,10.],'mean_bus_hours':[10.,10.],
                           'observation_dates_sha256':['same']*2})
        result,_,_=allocate_service(rows,'Weekday',10.,1.)
        np.testing.assert_allclose(result.scenario_mean_departures,[10.,20.],atol=1e-7)
        rows.loc[1,'observation_dates_sha256']='different'
        with self.assertRaises(ValueError):allocate_service(rows,'Weekday',10.,1.)

    def test_proposals_are_append_only_and_detect_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            a=save_proposal(folder,'Test proposal',{'frequency_factor':1.2},{'scenario':pd.DataFrame({'value':[2]})})
            b=save_proposal(folder,'Test proposal',{}, {'scenario':pd.DataFrame({'value':[3]})})
            self.assertNotEqual(a,b)
            self.assertTrue(all(r['integrity_valid'] for r in load_proposals(folder)))
            (Path(folder)/a/'scenario.csv').write_text('value\n99\n')
            self.assertFalse(next(r for r in load_proposals(folder) if r['id']==a)['integrity_valid'])

    def test_review_actions_never_validate_mergers(self):
        actions=candidate_actions(table('review'),table('signals'),table('overlap'))
        self.assertEqual(len(actions),41)
        self.assertTrue(actions.merge_or_split_status.str.startswith('not_validated').all())
        self.assertIn('Resolve',actions.set_index('bus_route').loc['M98','proposed_review_action'])

    def test_hypotheses_keep_thresholds_and_coverage_checks(self):
        results=route_change_candidates(table('overlap'),table('groups'))
        self.assertGreater(len(results),0)
        self.assertTrue(results.recommendation_status.str.startswith('hypothesis_for_review').all())
        self.assertTrue(results.required_validation.str.len().gt(20).all())
        self.assertTrue(route_change_candidates(table('overlap'),table('groups'),minimum_jaccard=2,minimum_patterns=999999).empty)

    def test_malformed_saved_metadata_is_withheld(self):
        with tempfile.TemporaryDirectory() as folder:
            identifier=save_proposal(folder,'Metadata test',{}, {'scenario':pd.DataFrame({'value':[1]})})
            (Path(folder)/identifier/'proposal.json').write_text('not JSON')
            records=load_proposals(folder)
            self.assertFalse(records[0]['integrity_valid'])


class LoadLabelTests(unittest.TestCase):
    def test_derived_or_missing_labels_are_rejected(self):
        invalid=pd.DataFrame({'bus_route':['M1'],'payment_date':['2026-01-01'],'performance_label':['overcrowded'],
                              'label_basis':['trip_frequency_rule'],'source_reference':['GTFS']})
        with self.assertRaisesRegex(ValueError,'independent'):validate_labels(invalid)
        with self.assertRaises(ValueError):validate_labels(pd.DataFrame())

    def test_chronological_classifier_and_target_feature_exclusion(self):
        # Explicit unit-test fixture; never used in study outputs or performance claims.
        dates=pd.date_range('2025-01-01',periods=60)
        labels=pd.DataFrame({'bus_route':['fixture']*60,'payment_date':dates,
             'performance_label':['balanced','overcrowded']*30,
             'label_basis':['independent_observed_load_assessment']*60,'source_reference':['unit-test fixture']*60})
        features=pd.DataFrame({'bus_route':['fixture']*60,'payment_date':dates,
             'lag_14d':np.arange(60),'lag_21d':np.arange(60),'lag_28d':np.arange(60),
             'day_of_week':dates.dayofweek,'month':dates.month,'analysis_boardings':999})
        _,report,outputs=train_classifier(features,labels)
        self.assertLess(report['training_end'],report['test_start'])
        self.assertNotIn('analysis_boardings',report['features'])
        self.assertFalse(report['operationally_accepted'])
        self.assertEqual(len(outputs),12)


class CompletionPageTests(unittest.TestCase):
    def test_new_pages_and_saved_proposal_roundtrip(self):
        app=AppTest.from_file(str(ROOT/'streamlit_app.py'),default_timeout=90).run()
        for name in ['Route comparison','Budget allocation','GTFS import','Observed-load classification','Planning proposals']:
            app.radio(key='workspace').set_value(name).run()
            self.assertFalse(app.exception,[e.message for e in app.exception])
            self.assertFalse(app.error,[e.value for e in app.error])
        # Keep interaction fixtures outside the actual proposal collection.
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder, patch('dashboard.planning_views.SAVED',Path(folder)):
            next(b for b in app.button if b.label=='Save proposal').click().run()
            self.assertFalse(app.exception,[e.message for e in app.exception])
            self.assertTrue(any('Proposal saved' in e.value for e in app.success))
            self.assertEqual(len(load_proposals(folder)),1)


if __name__=='__main__': unittest.main()
