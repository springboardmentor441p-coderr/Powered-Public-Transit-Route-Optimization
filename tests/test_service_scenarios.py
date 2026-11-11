"""Protect scenario units, conservation and unavailable-source gates."""

import unittest
import numpy as np
import pandas as pd
from scripts.service_scenarios import build_scenario_baselines, compare_frequency, transfer_bus_hours


class ScenarioContracts(unittest.TestCase):
    def inputs(self):
        rows = []
        for route, hours, boardings in [("A", 10., 100.), ("B", 20., 200.)]:
            for date in pd.date_range("2026-07-06", "2026-09-27"):
                kind = "Saturday" if date.dayofweek == 5 else "Sunday" if date.dayofweek == 6 else "Weekday"
                rows.append(dict(bus_route=route, payment_date=date, day_type=kind,
                                 scheduled_departures=30., scheduled_service_hours=hours,
                                 analysis_boardings=boardings, source_snapshot="frozen",
                                 prior_source_snapshot="frozen"))
        members = pd.DataFrame(rows)
        review = pd.DataFrame(dict(bus_route=["A", "B"], review_state=["planning_review", "no_rule_triggered"],
                                   positive_boardings_zero_service_dates=[0, 0],
                                   review_period_start=["2026-07-06"] * 2,
                                   review_period_end=["2026-09-27"] * 2))
        return members, review

    def baseline(self):
        return build_scenario_baselines(*self.inputs())

    def test_identity_preserves_paired_totals_and_daily_means(self):
        result = compare_frequency(self.baseline(), 1., max_added_bus_hours=0)
        np.testing.assert_allclose(result.scenario_mean_departures, result.mean_departures)
        np.testing.assert_allclose(result.scenario_mean_bus_hours, result.mean_bus_hours)
        np.testing.assert_allclose(result.scenario_mean_boardings, result.mean_boardings)
        np.testing.assert_allclose(result.delta_mean_bus_hours, 0.)
        self.assertTrue(result.timetable_feasibility.eq("not_assessed").all())
        self.assertFalse(result.automatic_service_change.any())

    def test_more_departures_at_fixed_demand_is_arithmetic_not_new_boardings(self):
        result = compare_frequency(self.baseline(), 1.2)
        np.testing.assert_allclose(result.scenario_mean_boardings, result.mean_boardings)
        np.testing.assert_allclose(result.scenario_mean_bus_hours / result.mean_bus_hours, 1.2)
        np.testing.assert_allclose(result.change_boardings_per_departure_fraction, -1 / 6)

    def test_zero_demand_remains_zero_and_percentage_change_is_undefined(self):
        members, review = self.inputs()
        members.loc[members.bus_route.eq("A"), "analysis_boardings"] = 0.
        base = build_scenario_baselines(members, review)
        result = compare_frequency(base.loc[base.bus_route.eq("A")], 1.2)
        self.assertTrue(result.baseline_eligible.all())
        self.assertTrue(result.scenario_boardings_per_departure.eq(0).all())
        self.assertTrue(result.change_boardings_per_departure_fraction.isna().all())

    def test_fractional_daily_mean_is_not_rounded_into_a_timetable(self):
        members, review = self.inputs()
        mask = members.bus_route.eq("A")
        members.loc[mask, "scheduled_departures"] = np.arange(mask.sum()) % 2 + 3
        base = build_scenario_baselines(members, review)
        result = compare_frequency(base.loc[base.bus_route.eq("A")], 1.1)
        np.testing.assert_allclose(result.scenario_mean_departures, result.mean_departures * 1.1)
        self.assertTrue((result.scenario_mean_departures % 1 != 0).any())

    def test_positive_boardings_with_zero_service_blocks_every_day_type_for_route(self):
        members, review = self.inputs()
        members.loc[0, "scheduled_service_hours"] = 0.
        review.loc[review.bus_route.eq("A"), ["review_state", "positive_boardings_zero_service_dates"]] = ["source_clarification", 1]
        base = build_scenario_baselines(members, review)
        result = compare_frequency(base.loc[base.bus_route.eq("A")], 1.2, max_added_bus_hours=10)
        self.assertTrue(result.arithmetic_status.eq("withheld").all())
        self.assertTrue(result.scenario_mean_departures.isna().all())
        self.assertTrue(result.added_hours_limit_pass.isna().all())
        self.assertTrue(result.mean_departures.notna().all())

    def test_source_counts_cannot_be_stale_relative_to_member_observations(self):
        members, review = self.inputs()
        members.loc[0, "scheduled_service_hours"] = 0.
        with self.assertRaisesRegex(ValueError, "source-issue counts"):
            build_scenario_baselines(members, review)

    def test_review_period_cannot_be_borrowed_for_a_different_baseline(self):
        members, review = self.inputs()
        review["review_period_end"] = "2026-10-31"
        with self.assertRaisesRegex(ValueError, "periods must match"):
            build_scenario_baselines(members, review)

    def test_missing_observations_are_rejected_instead_of_zero_filled(self):
        members, review = self.inputs()
        members.loc[0, "analysis_boardings"] = np.nan
        with self.assertRaises(ValueError):
            build_scenario_baselines(members, review)

    def test_different_route_date_populations_are_rejected(self):
        members, review = self.inputs()
        with self.assertRaisesRegex(ValueError, "same baseline observation dates"):
            build_scenario_baselines(members.iloc[1:], review)

    def test_invalid_factors_and_limits_are_rejected(self):
        base = self.baseline()
        for value in [0., -.1, np.nan, np.inf, True]:
            with self.subTest(factor=value), self.assertRaises(ValueError):
                compare_frequency(base, value)
        with self.assertRaises(ValueError):
            compare_frequency(base, 1., demand_factor=-1.)
        with self.assertRaises(ValueError):
            compare_frequency(base, 1., max_added_bus_hours=-1.)
        with self.assertRaises(ValueError):
            compare_frequency(base, 1., minimum_retained_fraction=1.1)

    def test_budget_and_retention_failures_do_not_claim_operational_feasibility(self):
        base = self.baseline()
        expensive = compare_frequency(base, 1.2, max_added_bus_hours=1.)
        self.assertTrue(expensive.arithmetic_status.eq("exceeds_added_hours_limit").all())
        cut = compare_frequency(base, .75)
        self.assertTrue(cut.arithmetic_status.eq("below_retained_service_limit").all())
        unspecified = compare_frequency(base, 1.)
        self.assertTrue(unspecified.added_hours_limit_pass.isna().all())
        self.assertTrue(expensive.timetable_feasibility.eq("not_assessed").all())

    def test_independent_demand_sensitivity_is_not_automatically_service_response(self):
        result = compare_frequency(self.baseline(), 1.2, demand_factor=1.1)
        np.testing.assert_allclose(result.scenario_boardings_per_departure / result.boardings_per_departure,
                                   1.1 / 1.2)
        self.assertTrue(result.demand_assumption.str.contains("not estimated response").all())

    def test_transfer_conserves_bus_hours_while_trip_count_can_change(self):
        rows, summary = transfer_bus_hours(self.baseline(), "A", "B", "Weekday", 2.)
        self.assertAlmostEqual(summary["net_mean_bus_hours_change"], 0.)
        self.assertNotAlmostEqual(summary["net_mean_departures_change"], 0.)
        self.assertAlmostEqual(summary["baseline_total_mean_boardings"], summary["scenario_total_mean_boardings"])
        self.assertTrue(summary["retention_limits_pass"])
        self.assertFalse(summary["automatic_service_change"])
        np.testing.assert_allclose(rows.scenario_mean_bus_hours, [8., 22.])

    def test_transfer_requires_identical_observation_dates(self):
        base = self.baseline()
        base.loc[base.bus_route.eq("B"), "observation_dates_sha256"] = "different_dates"
        with self.assertRaisesRegex(ValueError, "same matched observation dates"):
            transfer_bus_hours(base, "A", "B", "Weekday", 1.)

    def test_transfer_cannot_remove_all_donor_service_or_use_same_route(self):
        base = self.baseline()
        with self.assertRaises(ValueError):
            transfer_bus_hours(base, "A", "B", "Weekday", 10.)
        with self.assertRaises(ValueError):
            transfer_bus_hours(base, "A", "A", "Weekday", 1.)

    def test_baseline_rates_are_ratios_of_sums(self):
        members, review = self.inputs()
        mask = members.bus_route.eq("A") & members.day_type.eq("Weekday")
        members.loc[mask, "scheduled_service_hours"] = np.arange(1, mask.sum() + 1)
        base = build_scenario_baselines(members, review).set_index(["bus_route", "day_type"])
        expected = members.loc[mask, "analysis_boardings"].sum() / members.loc[mask, "scheduled_service_hours"].sum()
        self.assertAlmostEqual(base.loc[("A", "Weekday"), "boardings_per_bus_hour"], expected)


if __name__ == "__main__":
    unittest.main()
