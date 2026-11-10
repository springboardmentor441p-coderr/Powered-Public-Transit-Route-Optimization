"""Tests for Machine Learning Clustering and Evaluation."""

import unittest
from app.core.database import db
from ml.clustering import RouteClusteringPipeline
from ml.evaluation import ClusterEvaluator


class TestClustering(unittest.TestCase):
    """Test suite for K-Means, DBSCAN, PCA, and cluster evaluation."""

    @classmethod
    def setUpClass(cls):
        cls.df = db.get_table("route_features")
        cls.pipeline = RouteClusteringPipeline()

    def test_kmeans_clustering(self):
        clustered_df, profiles, metrics = self.pipeline.fit_kmeans(self.df, n_clusters=4)
        self.assertEqual(len(profiles), 4)
        self.assertIn("cluster_id", clustered_df.columns)
        self.assertIn("cluster_name", clustered_df.columns)
        self.assertIn("pca_x", clustered_df.columns)
        self.assertIn("pca_y", clustered_df.columns)
        self.assertGreater(metrics["inertia"], 0.0)

        for p in profiles:
            self.assertGreater(p.route_count, 0)
            self.assertTrue(len(p.name) > 0)
            self.assertGreaterEqual(p.avg_trips, 0.0)

    def test_dbscan_clustering(self):
        clustered_df, metrics = self.pipeline.fit_dbscan(self.df, eps=1.2, min_samples=5)
        self.assertIn("dbscan_cluster", clustered_df.columns)
        self.assertIn("noise_routes_count", metrics)

    def test_elbow_and_silhouette_evaluation(self):
        evaluator = ClusterEvaluator(k_range=(2, 4))
        result = evaluator.evaluate(self.df, sample_size=500)
        self.assertEqual(len(result.evaluation_points), 3)
        for point in result.evaluation_points:
            self.assertIn(point.k, [2, 3, 4])
            self.assertGreaterEqual(point.silhouette_score, -1.0)
            self.assertLessEqual(point.silhouette_score, 1.0)
        self.assertIn(result.recommended_k, [2, 3, 4])


if __name__ == "__main__":
    unittest.main()

