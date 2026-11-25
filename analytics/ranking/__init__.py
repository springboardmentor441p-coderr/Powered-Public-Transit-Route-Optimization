"""
AI_RouteRanker - Multi-Criteria Route Ranking Engine
Module 5 Integration Package synthesizing spatial clustering, corridor metrics,
and machine learning demand forecasts for public transit route optimization.
"""

from analytics.ranking.config import RankerConfig
from analytics.ranking.hub_metrics import compute_route_hub_metrics, compute_pattern_hub_metrics
from analytics.ranking.corridor_metrics import compute_corridor_metrics
from analytics.ranking.demand_integrator import integrate_demand_predictions
from analytics.ranking.route_ranker_features import (
    synthesize_route_ranker_features,
    normalize_features,
    validate_feature_master,
)
from analytics.ranking.ranker_dataset_builder import RankerDatasetBuilder
from analytics.ranking.criteria_transformer import CriteriaTransformer
from analytics.ranking.mcdm_engine import MCDMEngine
from analytics.ranking.explainer import RouteRankerExplainer
from analytics.ranking.sensitivity import RankingSensitivityAnalyzer
from analytics.ranking.ranker_service import RouteRankerService

__all__ = [
    "RankerConfig",
    "compute_route_hub_metrics",
    "compute_pattern_hub_metrics",
    "compute_corridor_metrics",
    "integrate_demand_predictions",
    "synthesize_route_ranker_features",
    "normalize_features",
    "validate_feature_master",
    "RankerDatasetBuilder",
    "CriteriaTransformer",
    "MCDMEngine",
    "RouteRankerExplainer",
    "RankingSensitivityAnalyzer",
    "RouteRankerService",
]
