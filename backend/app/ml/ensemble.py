# backend/app/ml/ensemble.py
"""Ensemble model for crowd and demand prediction.

Provides a thin wrapper that loads two pre‑trained models – a GradientBoostingRegressor
and an LSTM – and returns the averaged prediction together with a confidence interval.

The models are stored under ``backend/app/ml/saved_models/`` as:
- ``gb_model.pkl`` – scikit‑learn GradientBoostingRegressor (pickle)
- ``lstm.h5``      – Keras LSTM model (HDF5)

Usage example::

    from app.ml.ensemble import EnsemblePredictor
    predictor = EnsemblePredictor()
    pred, conf = predictor.predict(route_id="R123", hour=14, day_of_week=2)

"""
import os
import pickle
import numpy as np
from typing import Tuple

import tensorflow as tf

BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")

class EnsemblePredictor:
    def __init__(self) -> None:
        # Load Gradient Boosting model
        gb_path = os.path.join(MODEL_DIR, "gb_model.pkl")
        with open(gb_path, "rb") as f:
            self.gb_model = pickle.load(f)
        # Load LSTM model
        lstm_path = os.path.join(MODEL_DIR, "lstm.h5")
        self.lstm_model = tf.keras.models.load_model(lstm_path)

    def _feature_vector(self, route_id: str, hour: int, day_of_week: int) -> np.ndarray:
        """Construct a simple feature vector.
        Real implementation would join route metadata, historical loads, etc.
        """
        # Convert route_id to an integer hash for demonstration
        route_hash = int.from_bytes(route_id.encode("utf-8"), "little") % 1000
        return np.array([route_hash, hour, day_of_week], dtype=float).reshape(1, -1)

    def _lstm_features(self, route_id: str, hour: int, day_of_week: int) -> np.ndarray:
        """Create a time‑series shape expected by the LSTM.
        Here we repeat the basic feature vector for the last 24 hours as a stub.
        """
        base = self._feature_vector(route_id, hour, day_of_week)
        # LSTM expects shape (batch, timesteps, features)
        return np.repeat(base[:, np.newaxis, :], repeats=24, axis=1)

    def predict(self, route_id: str, hour: int, day_of_week: int) -> Tuple[float, Tuple[float, float]]:
        """Return ensemble prediction and a 95 % confidence interval.

        The interval is approximated by the standard deviation of the two model
        predictions multiplied by 1.96 (normal distribution).
        """
        # Gradient Boosting prediction
        gb_feat = self._feature_vector(route_id, hour, day_of_week)
        # Use only the first feature (route hash) for the dummy GB model which expects 1D input
        gb_pred = float(self.gb_model.predict(gb_feat[:, :1])[0][0])
        # LSTM prediction – model outputs shape (batch, 1), not (batch, timesteps, features)
        lstm_input = self._lstm_features(route_id, hour, day_of_week)
        lstm_pred_seq = self.lstm_model.predict(lstm_input, verbose=0)
        lstm_pred = float(lstm_pred_seq[0, 0])
        # Ensemble average
        ensemble_pred = float((gb_pred + lstm_pred) / 2.0)
        # Confidence interval (simple std dev)
        std = np.std([gb_pred, lstm_pred])
        ci = (ensemble_pred - 1.96 * std, ensemble_pred + 1.96 * std)
        return ensemble_pred, ci

# Singleton for FastAPI dependency injection
_predictor = EnsemblePredictor()

def get_ensemble_predictor() -> EnsemblePredictor:
    return _predictor

