"""
AI_RouteRanker - Phase 6.1 Spatial Stop & Route Clustering Package
Exposes modules for spatial projection, route-attributed demand aggregation,
two-tier stop clustering (DBSCAN + KMeans), and rigorous evaluation metrics.
"""

from .spatial_projection import SpatialProjector
from .demand_aggregator import (
    DemandAggregator,
    CANONICAL_SNAPSHOT_ID,
    REPRESENTATIVE_DATE,
    TIER2_TRAIN_START,
    TIER2_TRAIN_END,
    HEADWAY_WINDOWS,
)
from .stop_clustering import StopClusterer
from .evaluator import ClusteringEvaluator

__all__ = [
    "SpatialProjector",
    "DemandAggregator",
    "CANONICAL_SNAPSHOT_ID",
    "REPRESENTATIVE_DATE",
    "TIER2_TRAIN_START",
    "TIER2_TRAIN_END",
    "HEADWAY_WINDOWS",
    "StopClusterer",
    "ClusteringEvaluator",
]
