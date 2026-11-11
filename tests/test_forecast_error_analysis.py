"""Candidate feature isolation, paired population and interval timing boundaries."""
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from forecasting import make_examples
from forecast_error_analysis import ratio_features,paired_errors,calibrate_signed,signed_intervals


class ErrorAnalysisTests(unittest.TestCase):
    def examples(self):
        dates = pd.date_range('2025-01-01','2025-05-31')
        daily = pd.DataFrame({'bus_route':'A','payment_date':dates,
                              'analysis_boardings':np.arange(len(dates),dtype=float)})
        return make_examples(daily,['A'],pd.date_range('2025-03-03','2025-05-19',freq='W-MON'),14)

    def test_candidate_features_ignore_actuals_and_keep_zero_scale_finite(self):
        rows = self.examples()
        rows.loc[rows.index[0],['seasonal_mean4','seasonal_latest','seasonal_std4']]=0.
        first, scale = ratio_features(rows)
        mutated = rows.assign(actual=999999.)
        second,_=ratio_features(mutated)
        pd.testing.assert_frame_equal(first,second)
        self.assertEqual(scale.iloc[0],100.)
        self.assertFalse(np.isinf(first.to_numpy()).any())
        self.assertNotIn('actual',first.columns)

    def test_pairing_rejects_missing_rows_and_different_targets(self):
        rows=self.examples().head(7)[['bus_route','payment_date','origin','actual']]
        a=rows.assign(model='a',prediction=10.)
        b=rows.assign(model='b',prediction=11.)
        self.assertEqual(len(paired_errors(pd.concat([a,b]),'a','b')),7)
        with self.assertRaises(ValueError):paired_errors(pd.concat([a,b.iloc[1:]]),'a','b')
        b.loc[b.index[0],'actual']+=1
        with self.assertRaises(ValueError):paired_errors(pd.concat([a,b]),'a','b')

    def test_signed_calibration_does_not_read_future_outcomes(self):
        rows=self.examples()
        pred=rows[['bus_route','payment_date','actual']].assign(prediction=20.)
        cutoff='2025-04-15'
        first=calibrate_signed(pred,rows,cutoff)
        pred.loc[pred.payment_date.gt(cutoff),'actual']=999999.
        self.assertEqual(first,calibrate_signed(pred,rows,cutoff))

    def test_signed_bounds_are_ordered_and_nested(self):
        rows=self.examples()
        pred=rows[['bus_route','payment_date','actual']].assign(prediction=20.)
        fitted=calibrate_signed(pred,rows,'2025-05-31')
        intervals=signed_intervals(pred,rows,fitted)
        self.assertTrue(intervals.lower.ge(0).all())
        self.assertTrue(intervals.upper.ge(intervals.lower).all())
        low=intervals.loc[intervals.level.eq(.8)].set_index(['bus_route','payment_date'])
        high=intervals.loc[intervals.level.eq(.9)].set_index(['bus_route','payment_date'])
        self.assertTrue(high.lower.le(low.lower).all())
        self.assertTrue(high.upper.ge(low.upper).all())


if __name__=='__main__':unittest.main()
