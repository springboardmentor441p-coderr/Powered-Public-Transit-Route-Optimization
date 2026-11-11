"""Calibration boundary, quantile and interval invariants."""
import sys
import unittest
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime,timezone
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from forecast_intervals import calibrate,apply_intervals,interval_metrics,register_forecast,evaluate_registration


class IntervalTests(unittest.TestCase):
    def setUp(self):
        dates=pd.date_range('2026-01-01',periods=30)
        self.rows=pd.DataFrame({'bus_route':'A','payment_date':dates,
                               'actual':np.arange(30,dtype=float),'prediction':10.})
        self.examples=self.rows[['bus_route','payment_date']].assign(seasonal_mean4=10.)

    def test_future_outcomes_cannot_change_calibration(self):
        cutoff='2026-01-20'
        before=calibrate(self.rows,self.examples,cutoff)
        mutated=self.rows.copy()
        mutated.loc[mutated.payment_date.gt(cutoff),'actual']=999999
        self.assertEqual(before,calibrate(mutated,self.examples,cutoff))
        self.assertEqual(before['rows'],20)

    def test_insufficient_quantile_is_rejected(self):
        with self.assertRaises(ValueError):
            calibrate(self.rows.head(2),self.examples.head(2),'2026-01-30',levels=(.99,))

    def test_bounds_are_nonnegative_and_nested(self):
        calibration=calibrate(self.rows,self.examples,'2026-01-30')
        intervals=apply_intervals(self.rows,self.examples,calibration)
        self.assertTrue(intervals.lower.ge(0).all())
        self.assertTrue(intervals.lower.le(intervals.prediction).all())
        self.assertTrue(intervals.upper.ge(intervals.prediction).all())
        low=intervals.loc[intervals.level.eq(.8)].set_index('payment_date')
        high=intervals.loc[intervals.level.eq(.9)].set_index('payment_date')
        self.assertTrue(high.lower.le(low.lower).all())
        self.assertTrue(high.upper.ge(low.upper).all())

    def test_unknown_outcomes_are_not_scored(self):
        calibration=calibrate(self.rows,self.examples,'2026-01-30')
        intervals=apply_intervals(self.rows,self.examples,calibration)
        intervals.actual=np.nan
        self.assertTrue(interval_metrics(intervals).empty)

    def prospective_fixture(self):
        now=pd.Timestamp(datetime.now(timezone.utc))
        date=now.tz_convert('America/New_York').tz_localize(None).normalize()
        cutoff=date-pd.Timedelta(days=15)
        frame=pd.DataFrame({'bus_route':['A','A'],'payment_date':date+pd.Timedelta(days=7),
            'max_history_date':cutoff,'model':'seasonal_mean4','prediction':10.,
            'lower':5.,'upper':15.,'level':[.8,.9]})
        metadata={'maturity_days':14,'snapshot_observed_utc':now.isoformat(),
            'source_available_cutoff':str(cutoff.date()),'training_last_target':str(cutoff.date()),
            'selected_model':'seasonal_mean4','model_sha256':None}
        return frame,metadata,date

    def test_registration_rejects_unavailable_history(self):
        frame,metadata,date=self.prospective_fixture()
        frame.max_history_date=date
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):register_forecast(folder,frame,metadata)

    def test_registered_forecast_tampering_is_detected(self):
        frame,metadata,date=self.prospective_fixture()
        with tempfile.TemporaryDirectory() as folder:
            path,_=register_forecast(folder,frame,metadata)
            (path/'forecasts.csv').write_text('modified')
            with self.assertRaises(ValueError):evaluate_registration(folder,path.relative_to(folder),'unused')

    def test_prospective_outcomes_remain_pending_until_available(self):
        frame,metadata,date=self.prospective_fixture()
        observations=pd.DataFrame({'bus_route':['A'],'payment_date':[date-pd.Timedelta(days=20)],
                                   'published_boardings':[100.],'reported_hours':[24]})
        with tempfile.TemporaryDirectory() as folder:
            path,_=register_forecast(folder,frame,metadata)
            with patch('forecast_intervals.load_snapshot',return_value=(observations,{'observed_utc':metadata['snapshot_observed_utc']})):
                result=evaluate_registration(folder,path.relative_to(folder),'test-snapshot')
            self.assertEqual(result['status'],'pending')
            self.assertEqual(result['scored_route_dates'],0)
            self.assertEqual(result['point_metrics'],[])


if __name__=='__main__':
    unittest.main()
