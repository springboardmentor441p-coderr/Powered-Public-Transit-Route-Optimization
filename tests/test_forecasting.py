"""Availability and chronological boundary checks for demand forecasting."""
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from forecasting import issue_cutoff, make_examples, training_rows, metrics


class ForecastingTests(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range('2025-01-01', '2025-05-31')
        self.daily = pd.DataFrame({'payment_date': dates, 'bus_route': 'A',
                                   'analysis_boardings': np.arange(len(dates), dtype=float)})

    def test_future_changes_cannot_change_origin_features(self):
        origin = pd.Timestamp('2025-04-07')
        for delay in [0, 7, 14, 28]:
            with self.subTest(delay=delay):
                before = make_examples(self.daily, ['A'], [origin], delay)
                modified = self.daily.copy()
                modified.loc[modified.payment_date.gt(issue_cutoff(origin, delay)), 'analysis_boardings'] = 999999
                after = make_examples(modified, ['A'], [origin], delay)
                pd.testing.assert_frame_equal(before.drop(columns='actual'), after.drop(columns='actual'))
                self.assertTrue(before.max_history_date.le(before.availability_cutoff).all())

    def test_exact_dates_keep_absence_and_zero_distinct(self):
        date = pd.Timestamp('2025-03-24')
        self.daily.loc[self.daily.payment_date.eq(date), 'analysis_boardings'] = 0
        frame = make_examples(self.daily, ['A'], ['2025-04-07'])
        self.assertEqual(frame.iloc[0].weekly_lag_2, 0)
        missing = self.daily.loc[~self.daily.payment_date.eq(date)]
        other = make_examples(missing, ['A'], ['2025-04-07'])
        self.assertTrue(pd.isna(other.iloc[0].weekly_lag_2))

    def test_released_training_targets_only(self):
        frame = make_examples(self.daily, ['A'], pd.date_range('2025-02-03', '2025-05-05', freq='W-MON'))
        train = training_rows(frame, '2025-04-07', 7)
        self.assertLessEqual(train.payment_date.max(), pd.Timestamp('2025-03-30'))
        self.assertFalse(train.payment_date.ge(pd.Timestamp('2025-04-07')).any())

    def test_delay_changes_cutoff(self):
        self.assertEqual(issue_cutoff('2025-04-07', 28), pd.Timestamp('2025-03-09'))
        with self.assertRaises(ValueError):
            issue_cutoff('2025-04-07', -1)

    def test_wape_handles_real_zero_and_zero_denominator(self):
        data = pd.DataFrame({'model': ['a', 'a'], 'bus_route': ['A', 'A'],
                             'actual': [0., 10.], 'prediction': [2., 8.]})
        self.assertEqual(metrics(data).iloc[0].wape, .4)
        data.actual = 0
        self.assertIsNone(metrics(data).iloc[0].wape)


if __name__ == '__main__':
    unittest.main()
