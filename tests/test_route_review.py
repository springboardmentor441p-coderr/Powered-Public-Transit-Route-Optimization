"""Review-rule failures that could turn unavailable evidence into planning advice."""

import unittest
import numpy as np
import pandas as pd
from scripts.route_review import aggregate_review_profiles, evaluate_review_rules, make_review_queue


class ReviewContracts(unittest.TestCase):
    def members(self, same=False):
        rows = []
        for route_number in range(12):
            for date in pd.date_range("2026-07-06", "2026-09-27"):
                kind = "Saturday" if date.dayofweek == 5 else "Sunday" if date.dayofweek == 6 else "Weekday"
                rows.append({"bus_route": f"R{route_number:02d}", "payment_date": date,
                             "day_type": kind, "analysis_boardings": 100. if same else 10. * (route_number + 1),
                             "scheduled_service_hours": 10., "scheduled_departures": 20.})
        return pd.DataFrame(rows)

    def test_ratios_use_summed_pairs_not_mean_of_daily_ratios(self):
        frame = self.members()
        choose = frame.bus_route.eq("R00") & frame.day_type.eq("Weekday")
        frame.loc[choose, "analysis_boardings"] = 100.
        frame.loc[choose, "scheduled_service_hours"] = np.arange(1, choose.sum() + 1)
        profiles = aggregate_review_profiles(frame)
        row = profiles.loc[profiles.bus_route.eq("R00") & profiles.day_type.eq("Weekday")].iloc[0]
        expected = frame.loc[choose, "analysis_boardings"].sum() / frame.loc[choose, "scheduled_service_hours"].sum()
        self.assertAlmostEqual(row.boardings_per_bus_hour, expected)

    def test_tied_cohort_does_not_flag_every_route_as_both_extremes(self):
        _, rules = evaluate_review_rules(self.members(same=True))
        peer = rules.loc[rules.family.eq("relative_service_use")]
        self.assertTrue(peer.eligible.all())
        self.assertFalse(peer.triggered.any())

    def test_positive_boardings_with_zero_service_withholds_comparison(self):
        frame = self.members()
        frame.loc[0, "scheduled_service_hours"] = 0.
        profiles, rules = evaluate_review_rules(frame)
        row = profiles.loc[profiles.bus_route.eq("R00") & profiles.day_type.eq("Weekday")].iloc[0]
        self.assertEqual(row.evidence_status, "source_alignment_review")
        self.assertTrue(pd.isna(row.boardings_per_bus_hour))
        affected = rules.loc[rules.bus_route.eq("R00") & rules.family.eq("relative_service_use")
                             & rules.day_type.eq("Weekday")]
        self.assertTrue(affected.triggered.isna().all())

    def test_true_zero_boardings_do_not_become_missing(self):
        frame = self.members()
        frame.loc[frame.bus_route.eq("R00"), "analysis_boardings"] = 0.
        profiles, _ = evaluate_review_rules(frame)
        rows = profiles.loc[profiles.bus_route.eq("R00")]
        self.assertTrue(rows.service_comparison_eligible.all())
        self.assertTrue(rows.boardings_per_bus_hour.eq(0).all())

    def test_missing_period_is_unavailable_not_no_change(self):
        frame = self.members()
        frame = frame.loc[frame.payment_date.le("2026-08-16")]
        _, rules = evaluate_review_rules(frame, minimum_days={"Weekday": 10, "Saturday": 3, "Sunday": 3})
        temporal = rules.loc[rules.family.eq("weekday_intensity_change")]
        self.assertFalse(temporal.eligible.any())
        self.assertTrue(temporal.metric.isna().all())
        self.assertTrue(temporal.triggered.isna().all())

    def test_equal_demand_and_service_growth_does_not_imply_relative_pressure_growth(self):
        frame = self.members(same=True)
        late = frame.payment_date.ge("2026-08-17")
        frame.loc[late, ["analysis_boardings", "scheduled_service_hours"]] *= 2
        _, rules = evaluate_review_rules(frame)
        temporal = rules.loc[rules.family.eq("weekday_intensity_change")]
        np.testing.assert_allclose(temporal.metric, 1.)
        self.assertFalse(temporal.triggered.any())

    def test_too_few_comparable_routes_withholds_peer_rule(self):
        frame = self.members()
        _, rules = evaluate_review_rules(frame.loc[frame.bus_route.isin(["R00", "R01"])])
        peer = rules.loc[rules.family.eq("relative_service_use")]
        self.assertFalse(peer.eligible.any())
        self.assertTrue(peer.triggered.isna().all())

    def test_cluster_and_forecast_context_cannot_change_queue_decisions(self):
        frame = self.members()
        _, rules = evaluate_review_rules(frame)
        context = pd.DataFrame({"bus_route": sorted(frame.bus_route.unique()),
                                "positive_boardings_zero_service_dates": 0,
                                "group_id": "G01", "forecast_mae": 1.})
        first = make_review_queue(rules, context)
        context["group_id"], context["forecast_mae"] = "G99", 100000.
        second = make_review_queue(rules, context)
        pd.testing.assert_frame_equal(first[["bus_route", "review_state", "review_families"]],
                                      second[["bus_route", "review_state", "review_families"]])

    def test_source_clarification_precedes_planning_without_deleting_valid_rule_evidence(self):
        frame = self.members()
        _, rules = evaluate_review_rules(frame)
        context = pd.DataFrame({"bus_route": sorted(frame.bus_route.unique()),
                                "positive_boardings_zero_service_dates": 0})
        context.loc[context.bus_route.eq("R00"), "positive_boardings_zero_service_dates"] = 1
        queue = make_review_queue(rules, context)
        self.assertEqual(queue.iloc[0].bus_route, "R00")
        self.assertEqual(queue.iloc[0].review_state, "source_clarification")
        self.assertGreater(queue.iloc[0].flagged_evaluations, 0)
        self.assertFalse(queue.automated_service_change.any())

    def test_negative_or_missing_observations_fail_instead_of_imputing(self):
        frame = self.members()
        frame.loc[0, "analysis_boardings"] = np.nan
        with self.assertRaises(ValueError):
            aggregate_review_profiles(frame)


if __name__ == "__main__":
    unittest.main()
