"""Tests for API Routers and Endpoints."""

import unittest
from app.api.compat import HAS_FASTAPI
from app.api.health import get_health
from app.api.dashboard import get_dashboard_summary
from app.api.routes import list_routes, get_route, get_route_stops, get_route_trips, get_route_schedule
from app.api.coverage import get_coverage_summary, list_coverage_stops
from app.api.overlap import get_top_overlaps, get_route_overlap
from app.api.analytics import get_frequency_analytics, get_service_analytics
from app.api.ml import get_clusters, run_clustering
from app.api.optimization import simulate_schedule_scenario
from app.api.data import get_data_quality, get_data_status
from app.api.insights import get_insights
from app.schemas.optimization import OptimizationSimulateRequest
from app.schemas.ml import ClusterRequest
from app.core.database import db


class TestAPIEndpoints(unittest.TestCase):
    """Test suite for all required RouteRanker API endpoints."""

    @classmethod
    def setUpClass(cls):
        df = db.get_table("route_features")
        cls.sample_route_id = str(df.iloc[0]["route_id"])

    def test_health_endpoint(self):
        res = get_health()
        self.assertIn(res.status, ["healthy", "initializing"])

    def test_dashboard_endpoint(self):
        res = get_dashboard_summary()
        self.assertGreater(res.total_routes, 0)

    def test_routes_endpoints(self):
        # List
        routes_list = list_routes(page=1, page_size=5)
        self.assertEqual(len(routes_list.items), 5)
        # Detail
        detail = get_route(self.sample_route_id)
        self.assertEqual(detail.route_id, self.sample_route_id)
        # Stops
        stops = get_route_stops(self.sample_route_id)
        self.assertGreater(stops.total_stops_served, 0)
        # Trips
        trips = get_route_trips(self.sample_route_id, limit=5)
        self.assertGreater(trips.total_trips, 0)
        # Schedule
        sched = get_route_schedule(self.sample_route_id)
        self.assertEqual(len(sched.hourly_distribution), 24)

    def test_coverage_endpoints(self):
        summary = get_coverage_summary()
        self.assertGreater(summary.total_stops, 0)
        stops_page = list_coverage_stops(page=1, page_size=5)
        self.assertEqual(len(stops_page.items), 5)

    def test_overlap_endpoints(self):
        top_pairs = get_top_overlaps(limit=5)
        self.assertGreater(len(top_pairs), 0)
        route_overlap = get_route_overlap(self.sample_route_id)
        self.assertEqual(route_overlap.route_id, self.sample_route_id)

    def test_analytics_endpoints(self):
        freq = get_frequency_analytics(page=1, page_size=5)
        self.assertEqual(len(freq.items), 5)
        span = get_service_analytics()
        self.assertEqual(len(span.network_trips_by_hour), 24)

    def test_ml_endpoints(self):
        clusters = get_clusters()
        self.assertGreater(len(clusters.profiles), 0)
        req = ClusterRequest(n_clusters=3, algorithm="kmeans")
        run_res = run_clustering(req)
        self.assertEqual(len(run_res.profiles), 3)

    def test_optimization_endpoint(self):
        req = OptimizationSimulateRequest(
            route_id=self.sample_route_id,
            frequency_multiplier=1.1,
        )
        res = simulate_schedule_scenario(req)
        self.assertEqual(res.route_id, self.sample_route_id)

    def test_data_endpoints(self):
        q = get_data_quality()
        self.assertGreater(q.quality_score, 0.0)
        s = get_data_status()
        self.assertIn(s.status, ["ready", "processing_required"])

    def test_insights_endpoint(self):
        insights = get_insights()
        self.assertGreater(len(insights.insights), 0)


if __name__ == "__main__":
    unittest.main()

