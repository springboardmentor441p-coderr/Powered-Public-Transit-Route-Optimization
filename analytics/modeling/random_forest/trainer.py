"""
AI_RouteRanker - Random Forest Trainer Module
Trains scikit-learn RandomForestRegressor on approved training partitions.
Implements memory-efficient fitting, execution timing, metadata tracking,
and artifact serialization.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import time
import os
import gc
import logging
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from .config import RandomForestConfig
from analytics.modeling.feature_builder import ModelingDataset

logger = logging.getLogger(__name__)


@dataclass
class TrainedRFModel:
    """Encapsulates a fitted Random Forest model and associated training metadata."""
    model: RandomForestRegressor
    tier: int
    feature_names: List[str]
    config: RandomForestConfig
    training_rows: int
    feature_count: int
    training_duration_seconds: float
    training_timestamp: str

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Generates predictions using the fitted estimator."""
        if isinstance(X, pd.DataFrame):
            # Ensure feature ordering matches training matrix exactly
            missing_cols = set(self.feature_names) - set(X.columns)
            if missing_cols:
                raise ValueError(f"Input feature matrix is missing {len(missing_cols)} expected features: {missing_cols}")
            X_mat = X[self.feature_names].to_numpy(dtype=np.float32)
        else:
            X_mat = np.asarray(X, dtype=np.float32)

        return self.model.predict(X_mat)

    def save(self, filepath: str) -> str:
        """Serializes model artifact to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        artifact_data = {
            "model": self.model,
            "tier": self.tier,
            "feature_names": self.feature_names,
            "config": self.config.to_dict(),
            "training_rows": self.training_rows,
            "feature_count": self.feature_count,
            "training_duration_seconds": self.training_duration_seconds,
            "training_timestamp": self.training_timestamp,
        }
        joblib.dump(artifact_data, filepath, compress=3)
        logger.info("Saved Tier %d model artifact to %s", self.tier, filepath)
        return filepath

    @classmethod
    def load(cls, filepath: str) -> "TrainedRFModel":
        """Loads serialized model artifact from disk."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model artifact not found at {filepath}")
        artifact_data = joblib.load(filepath)
        config = RandomForestConfig.from_dict(artifact_data["config"])
        return cls(
            model=artifact_data["model"],
            tier=artifact_data["tier"],
            feature_names=artifact_data["feature_names"],
            config=config,
            training_rows=artifact_data["training_rows"],
            feature_count=artifact_data["feature_count"],
            training_duration_seconds=artifact_data["training_duration_seconds"],
            training_timestamp=artifact_data["training_timestamp"],
        )


class RandomForestTrainer:
    """Manages training lifecycle for Random Forest models with memory safeguards."""

    @classmethod
    def train(
        cls,
        dataset: ModelingDataset,
        config: Optional[RandomForestConfig] = None,
    ) -> TrainedRFModel:
        """
        Trains RandomForestRegressor on the provided training partition.

        Args:
            dataset: ModelingDataset containing feature matrix X, target y, and metadata.
            config: Approved RandomForestConfig (defaults to Phase 3.1 standard config).

        Returns:
            TrainedRFModel container.
        """
        cfg = config or RandomForestConfig()
        logger.info(
            "Initializing Tier %d Random Forest training on %d rows with %d features...",
            dataset.tier,
            len(dataset.X),
            dataset.X.shape[1],
        )

        rf = RandomForestRegressor(
            n_estimators=cfg.n_estimators,
            max_depth=cfg.max_depth,
            min_samples_leaf=cfg.min_samples_leaf,
            random_state=cfg.random_state,
            n_jobs=cfg.n_jobs,
            max_features=cfg.max_features,
            bootstrap=cfg.bootstrap,
            criterion=cfg.criterion,
        )

        # Ensure float32 representation for memory efficiency
        X_train = dataset.X.to_numpy(dtype=np.float32)
        y_train = dataset.y.to_numpy(dtype=np.float32)

        start_time = time.perf_counter()
        rf.fit(X_train, y_train)
        duration = time.perf_counter() - start_time

        logger.info(
            "Completed Tier %d Random Forest training in %.2f seconds (%.2f min).",
            dataset.tier,
            duration,
            duration / 60.0,
        )

        trained_model = TrainedRFModel(
            model=rf,
            tier=dataset.tier,
            feature_names=dataset.feature_names,
            config=cfg,
            training_rows=len(dataset.X),
            feature_count=dataset.X.shape[1],
            training_duration_seconds=round(duration, 2),
            training_timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        )

        # Force garbage collection to free intermediate memory
        del X_train, y_train
        gc.collect()

        return trained_model
