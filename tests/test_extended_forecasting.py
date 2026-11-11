"""Annual availability and rolling calibration leakage invariants."""
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from forecasting import make_examples, issue_cutoff
from extended_forecasting import add_annual_history,rolling_intervals,point_forecast,preview_rows


class ExtendedForecastTests(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range('2025-01-01','2026-10-31')
        self.daily = pd.DataFrame({'bus_route':'A','payment_date':dates,
                                   'analysis_boardings':100.+np.arange(len(dates))%30})

    def test_future_values_cannot_change_annual_features(self):
        origin=pd.Timestamp('2026-09-07')
        before=add_annual_history(make_examples(self.daily,['A'],[origin],14),self.daily)
        altered=self.daily.copy()
        altered.loc[altered.payment_date.gt(issue_cutoff(origin,14)),'analysis_boardings']=999999.
        after=add_annual_history(make_examples(altered,['A'],[origin],14),altered)
        pd.testing.assert_frame_equal(before.drop(columns='actual'),after.drop(columns='actual'))

    def test_missing_annual_history_falls_back_without_zero_filling(self):
        recent=self.daily.loc[self.daily.payment_date.ge('2026-01-01')]
        rows=add_annual_history(make_examples(recent,['A'],['2026-09-07'],14),recent)
        self.assertFalse(rows.annual_eligible.any())
        np.testing.assert_allclose(rows.annual_scaled,rows.seasonal_mean4)

    def test_future_residuals_cannot_change_rolling_bounds(self):
        origins=pd.date_range('2026-05-04','2026-09-07',freq='W-MON')
        rows=make_examples(self.daily,['A'],origins,14)
        predictions=rows[['bus_route','origin','payment_date','actual']].assign(prediction=110.,model='a')
        target=pd.Timestamp('2026-09-07')
        before,_=rolling_intervals(predictions,[target],pd.Timestamp('2026-09-13'))
        altered=predictions.copy()
        altered.loc[altered.payment_date.gt(issue_cutoff(target,14)),'actual']=999999.
        after,_=rolling_intervals(altered,[target],pd.Timestamp('2026-09-13'))
        pd.testing.assert_frame_equal(before.drop(columns='actual'),after.drop(columns='actual'))

    def test_insufficient_prototype_history_is_withheld(self):
        rows=make_examples(self.daily,['A'],['2026-09-07'],14)
        rows.loc[0,'history_eligible']=False
        with self.assertRaises(ValueError):point_forecast(rows,'seasonal_mean4')

    def test_preview_rejects_unobserved_or_stale_snapshots(self):
        with self.assertRaises(ValueError):
            preview_rows(self.daily,['A'],'2026-10-10T12:00:00Z','2026-10-09T12:00:00Z','seasonal_mean4')
        with self.assertRaises(ValueError):
            preview_rows(self.daily,['A'],'2026-10-01T12:00:00Z','2027-01-01T12:00:00Z','seasonal_mean4')

    def test_preview_uses_actual_issue_cutoff_not_future_origin(self):
        rows=preview_rows(self.daily,['A'],'2026-10-01T12:00:00Z','2026-10-01T13:00:00Z',
                          'seasonal_mean4',target_start='2026-10-05')
        self.assertTrue(rows.availability_cutoff.eq(pd.Timestamp('2026-09-16')).all())
        self.assertTrue(rows.max_history_date.le(rows.availability_cutoff).all())
        self.assertEqual(len(rows),7)

    def test_cached_snapshot_cannot_age_unrevised_counts_into_maturity(self):
        rows=preview_rows(self.daily,['A'],'2026-10-01T12:00:00Z','2026-10-02T13:00:00Z',
                          'seasonal_mean4')
        self.assertTrue(rows.availability_cutoff.eq(pd.Timestamp('2026-09-16')).all())
        self.assertTrue(rows.actual.isna().all())


if __name__=='__main__':unittest.main()
