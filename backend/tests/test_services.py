"""Tests for Backend Business Logic Services."""

import unittest
from app.core.database import db
from app.services.analytics_service import AnalyticsService
from app.services.coverage_service import CoverageService
from app.services.dashboard_service import DashboardService
from app.services.data_service import DataService
from app.services.insights_service import InsightsService
from app.services.ml_service import MLService
from app.services.optimization_service import OptimizationService
from app.services.overlap_service import OverlapService
from app.services.route_service import RouteService
from app.schemas.optimization import OptimizationSimulateRequest
from app.schemas.ml import ClusterRequest


class TestServices(unittest.TestCase):
    """Test suite for RouteRanker business logic services."""

    @classmethod
    def setUpClass(cls):
        df = db.get_table("route_features")
        cls.sample_route_id = str(df.iloc[0]["route_id"])

    def test_route_service_list(self):
        res = RouteService.get_routes(page=1, page_size=10)
        self.assertGreater(res.total, 4000)
        self.assertEqual(len(res.items), 10)
        self.assertEqual(res.page, 1)

    def test_route_service_detail(self):
        res = RouteService.get_route_by_id(self.sample_route_id)
        self.assertIsNotNone(res)
        self.assertEqual(res.route_id, self.sample_route_id)
        self.assertGreater(res.total_trips, 0)

    def test_route_service_stops(self):
        res = RouteService.get_route_stops(self.sample_route_id)
        self.assertIsNotNone(res)
        self.assertGreater(res.total_stops_served, 0)

    def test_route_service_trips(self):
        res = RouteService.get_route_trips(self.sample_route_id, limit=10)
        self.assertIsNotNone(res)
        self.assertGreater(res.total_trips, 0)

    def test_route_service_schedule(self):
        res = RouteService.get_route_schedule(self.sample_route_id)
        self.assertIsNotNone(res)
        self.assertEqual(len(res.hourly_distribution), 24)

    def test_coverage_service_summary(self):
        res = CoverageService.get_coverage_summary()
        self.assertGreater(res.total_stops, 5000)
        self.assertGreater(res.total_transfer_hubs, 0)
        self.assertGreater(len(res.top_transfer_hubs), 0)

    def test_coverage_service_stops(self):
        res = CoverageService.get_coverage_stops(page=1, page_size=15, is_hub_only=True)
        self.assertEqual(len(res.items), 15)
        for s in res.items:
            self.assertTrue(s.is_transfer_hub)

    def test_overlap_service(self):
        pairs = OverlapService.get_top_overlaps(limit=10, min_overlap_pct=10.0)
        self.assertGreater(len(pairs), 0)
        first_pair = pairs[0]
        self.assertGreater(first_pair.shared_stops, 0)

        route_overlap = OverlapService.get_route_overlap(self.sample_route_id)
        self.assertIsNotNone(route_overlap)

    def test_analytics_service_frequency(self):
        res = AnalyticsService.get_frequency_analytics(page=1, page_size=20)
        self.assertEqual(len(res.items), 20)
        for item in res.items:
            self.assertGreater(item.total_trips, 0)

    def test_analytics_service_service_span(self):
        res = AnalyticsService.get_service_span_analytics()
        self.assertGreater(res.avg_route_span_hours, 0.0)
        self.assertEqual(len(res.network_trips_by_hour), 24)

    def test_dashboard_service(self):
        res = DashboardService.get_dashboard_summary()
        self.assertGreater(res.total_routes, 4000)
        self.assertGreater(res.total_stops, 5000)
        self.assertGreater(res.total_trips, 40000)
        self.assertEqual(len(res.top_frequent_routes), 5)

    def test_insights_service(self):
        res = InsightsService.generate_insights()
        self.assertIsNotNone(res.network_health_grade)
        self.assertGreater(len(res.insights), 0)

    def test_data_service(self):
        q = DataService.get_quality_report()
        self.assertGreaterEqual(q.quality_score, 90.0)
        self.assertGreaterEqual(q.sanitization_count, 1)

        s = DataService.get_data_status()
        self.assertEqual(s.status, "ready")

    def test_ml_service(self):
        req = ClusterRequest(n_clusters=4, algorithm="kmeans")
        res = MLService.cluster_routes(req)
        self.assertEqual(res.algorithm, "kmeans")
        self.assertEqual(len(res.profiles), 4)
        self.assertGreater(len(res.points), 4000)

    def test_optimization_service(self):
        req = OptimizationSimulateRequest(
            route_id=self.sample_route_id,
            frequency_multiplier=1.2,
        )
        res = OptimizationService.simulate(req)
        self.assertEqual(res.route_id, self.sample_route_id)
        self.assertGreater(res.simulated_trips, res.baseline_trips)


if __name__ == "__main__":
    unittest.main()
