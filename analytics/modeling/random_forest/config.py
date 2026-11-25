"""
AI_RouteRanker - Random Forest Configuration Module
Defines approved, fixed hyperparameter configurations and serialization
for Milestone 5.2 Phase 3.1 controlled initial experiments.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any
import json


@dataclass(frozen=True)
class RandomForestConfig:
    """Approved, immutable hyperparameter configuration for Phase 3.1."""

    n_estimators: int = 100
    max_depth: int = 12
    min_samples_leaf: int = 5
    random_state: int = 42
    n_jobs: int = 2
    max_features: float = 1.0
    bootstrap: bool = True
    criterion: str = "squared_error"

    def to_dict(self) -> Dict[str, Any]:
        """Returns hyperparameters as a dictionary for scikit-learn."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serializes configuration to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RandomForestConfig":
        """Recreates configuration from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
