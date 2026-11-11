"""Boundary cases that can distort route grouping or silently invent observations."""

import unittest
import numpy as np
import pandas as pd
from scripts.route_profiles import (align_labels, build_route_profiles,
                                    choose_cluster_count, common_profile_members)


class RouteProfileContracts(unittest.TestCase):
    def make_inputs(self):
        rows, hours = [], []
        for route in ['A', 'B']:
            for date in pd.date_range('2026-07-06', periods=7):
                rows.append(dict(bus_route=route, payment_date=date, analysis_boardings=24.,
                                 scheduled_departures=12., scheduled_service_hours=6.,
                                 schedule_comparison_eligible=True, source_snapshot='current',
                                 prior_source_snapshot='prior'))
                for hour in range(24):
                    hours.append(dict(bus_route=route, payment_date=date,
                                      local_hour=date + pd.Timedelta(hours=hour), analysis_boardings=1.))
        return pd.DataFrame(rows), pd.DataFrame(hours)

    def test_one_missing_hour_excludes_date_for_every_route(self):
        daily, hourly = self.make_inputs()
        hourly = hourly.drop(index=0)
        members, coverage = common_profile_members(daily, hourly, ['A', 'B'], '2026-07-06', '2026-07-12')
        self.assertEqual(members.payment_date.nunique(), 6)
        self.assertEqual(len(members), 12)
        self.assertFalse(coverage.iloc[0].included)

    def test_missing_demand_is_not_replaced_with_zero(self):
        daily, hourly = self.make_inputs()
        daily.loc[0, 'analysis_boardings'] = np.nan
        members, _ = common_profile_members(daily, hourly, ['A', 'B'], '2026-07-06', '2026-07-12')
        self.assertNotIn(pd.Timestamp('2026-07-06'), members.payment_date.tolist())

    def test_known_zero_service_survives_common_date_selection(self):
        daily, hourly = self.make_inputs()
        daily.loc[5, ['scheduled_departures', 'scheduled_service_hours']] = 0.
        members, coverage = common_profile_members(daily, hourly, ['A', 'B'], '2026-07-06', '2026-07-12')
        self.assertTrue(coverage.included.all())
        profiles = build_route_profiles(members, dict(Weekday=1, Saturday=1, Sunday=1))
        self.assertEqual(profiles.set_index('bus_route').loc['A', 'zero_service_dates'], 1)
        self.assertAlmostEqual(profiles.set_index('bus_route').loc['A', 'weekend_service_ratio'], .5)

    def test_mismatched_hourly_total_excludes_date(self):
        daily, hourly = self.make_inputs()
        hourly.loc[0, 'analysis_boardings'] = 7.
        members, coverage = common_profile_members(daily, hourly, ['A', 'B'], '2026-07-06', '2026-07-12')
        self.assertEqual(coverage.unreconciled_routes.sum(), 1)
        self.assertEqual(members.payment_date.nunique(), 6)

    def test_duplicate_keys_fail_before_aggregation(self):
        daily, hourly = self.make_inputs()
        with self.assertRaisesRegex(ValueError, 'Duplicate route/date'):
            common_profile_members(pd.concat([daily, daily.iloc[[0]]]), hourly,
                                   ['A', 'B'], '2026-07-06', '2026-07-12')

    def test_equal_weight_weekend_day_types_and_ratio_of_sums(self):
        daily, hourly = self.make_inputs()
        members, _ = common_profile_members(daily, hourly, ['A', 'B'], '2026-07-06', '2026-07-12')
        members.loc[members.day_type.eq('Saturday'), 'analysis_boardings'] = 48.
        members.loc[members.day_type.eq('Sunday'), 'analysis_boardings'] = 12.
        members = pd.concat([members, members.loc[members.day_type.eq('Saturday')]], ignore_index=True)
        profiles = build_route_profiles(members, dict(Weekday=1, Saturday=1, Sunday=1))
        np.testing.assert_allclose(profiles.weekend_boarding_ratio, 1.25)
        np.testing.assert_allclose(profiles.weekday_peak_share, .25)

    def test_zero_reference_cannot_become_infinite_feature(self):
        daily, hourly = self.make_inputs()
        members, _ = common_profile_members(daily, hourly, ['A', 'B'], '2026-07-06', '2026-07-12')
        members.loc[members.day_type.eq('Weekday'), 'scheduled_service_hours'] = 0.
        with self.assertRaisesRegex(ValueError, 'Weekday reference'):
            build_route_profiles(members, dict(Weekday=1, Saturday=1, Sunday=1))

    def test_small_groups_are_screened_and_near_ties_prefer_fewer_groups(self):
        scores = pd.DataFrame({'k': [2, 3, 4], 'silhouette': [.40, .41, .65],
                               'min_cluster_size': [10, 6, 1]})
        self.assertEqual(choose_cluster_count(scores), 2)

    def test_assignment_retention_is_invariant_to_group_numbering(self):
        reference = np.array([0, 0, 1, 1, 2, 2])
        candidate = np.array([2, 2, 0, 0, 1, 1])
        np.testing.assert_array_equal(align_labels(reference, candidate), reference)


if __name__ == '__main__':
    unittest.main()
