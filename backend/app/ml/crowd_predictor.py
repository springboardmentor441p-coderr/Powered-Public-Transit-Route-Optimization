"""AI Crowd & Passenger Demand Prediction Module for MetroFlow.
Trains and serves machine learning models to forecast passenger density,
peak-hour demand surges, and generate AI-driven train frequency recommendations.
"""

import os
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
import joblib

MODEL_DIR = Path(__file__).resolve().parent / "saved_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
DENSITY_MODEL_FILE = MODEL_DIR / "crowd_density_model.joblib"
DEMAND_MODEL_FILE = MODEL_DIR / "passenger_demand_model.joblib"

class CrowdPredictor:
    def __init__(self):
        self.density_model = None
        self.demand_model = None
        self._load_or_train()

    def _is_peak_hour(self, hour: int) -> int:
        # Peak metro transit hours: 07:00-10:00 and 17:00-20:00
        return 1 if (7 <= hour <= 10 or 17 <= hour <= 20) else 0

    def _generate_synthetic_training_dataset(self, n_samples: int = 5000):
        """Generate realistic transportation feature set for training."""
        np.random.seed(42)
        hours = np.random.randint(0, 24, size=n_samples)
        days = np.random.randint(0, 7, size=n_samples)  # 0=Monday, 6=Sunday
        is_peak = np.array([self._is_peak_hour(h) for h in hours])
        stop_seq = np.random.randint(1, 35, size=n_samples)
        route_type = np.random.choice([0, 1, 2, 3], size=n_samples)  # 1=Subway/Metro
        base_scheduled_freq = np.random.choice([4, 6, 10, 15, 20], size=n_samples)

        # Baseline density formula:
        # Higher in peak hours, weekdays (days 0-4), central stops (stop_seq 10-25)
        weekday_multiplier = np.where(days < 5, 1.3, 0.8)
        peak_adder = np.where(is_peak == 1, 40.0, 10.0)
        central_adder = np.where((stop_seq >= 8) & (stop_seq <= 22), 20.0, 5.0)
        noise = np.random.normal(0, 5, size=n_samples)

        density = np.clip(15.0 * weekday_multiplier + peak_adder + central_adder + noise, 5.0, 99.0)
        
        # Demand in footfall (passengers/hour per station)
        demand = np.clip(density * 45.0 + np.random.normal(0, 100, size=n_samples), 100.0, 5000.0)

        df = pd.DataFrame({
            "hour": hours,
            "day_of_week": days,
            "is_peak": is_peak,
            "stop_sequence": stop_seq,
            "route_type": route_type,
            "scheduled_frequency": base_scheduled_freq,
            "crowd_density": density,
            "passenger_demand": demand,
        })
        return df

    def train_and_save_models(self):
        """Train GradientBoosting and RandomForest regressors and save to disk."""
        df = self._generate_synthetic_training_dataset()
        features = ["hour", "day_of_week", "is_peak", "stop_sequence", "route_type", "scheduled_frequency"]
        X = df[features]
        y_density = df["crowd_density"]
        y_demand = df["passenger_demand"]

        # Train models
        self.density_model = GradientBoostingRegressor(n_estimators=80, max_depth=4, random_state=42)
        self.density_model.fit(X, y_density)

        self.demand_model = RandomForestRegressor(n_estimators=80, max_depth=5, random_state=42)
        self.demand_model.fit(X, y_demand)

        # Save
        joblib.dump(self.density_model, DENSITY_MODEL_FILE)
        joblib.dump(self.demand_model, DEMAND_MODEL_FILE)
        print("[INFO] AI Crowd and Demand models trained and saved successfully.")

    def _load_or_train(self):
        if DENSITY_MODEL_FILE.exists() and DEMAND_MODEL_FILE.exists():
            try:
                self.density_model = joblib.load(DENSITY_MODEL_FILE)
                self.demand_model = joblib.load(DEMAND_MODEL_FILE)
                print("[INFO] AI Models loaded from disk.")
                return
            except Exception:
                pass
        self.train_and_save_models()

    def predict_station_crowd(self, hour: int, day_of_week: int, stop_sequence: int = 12, route_type: int = 1, scheduled_frequency: int = 8):
        """Forecast crowd density (%) and classify congestion risk."""
        is_peak = self._is_peak_hour(hour)
        input_data = pd.DataFrame([{
            "hour": hour,
            "day_of_week": day_of_week,
            "is_peak": is_peak,
            "stop_sequence": stop_sequence,
            "route_type": route_type,
            "scheduled_frequency": scheduled_frequency
        }])

        pred_density = float(self.density_model.predict(input_data)[0])
        pred_demand = float(self.demand_model.predict(input_data)[0])

        pred_density = max(5.0, min(99.0, round(pred_density, 1)))
        pred_demand = max(50, round(pred_demand))

        if pred_density >= 85.0:
            risk = "CRITICAL"
            recommendation = "High overcrowding risk. Immediately deploy supplemental relief train units and enforce station platform metering."
        elif pred_density >= 70.0:
            risk = "HIGH"
            recommendation = "Peak demand detected. Reduce headway from scheduled interval down to 3-4 minutes."
        elif pred_density >= 45.0:
            risk = "MODERATE"
            recommendation = "Normal operating conditions. Maintain standard 6-8 minute headway."
        else:
            risk = "LOW"
            recommendation = "Off-peak lull. Energy-efficient scheduling (10-15 minute headway) recommended."

        return {
            "predicted_crowd_density_percent": pred_density,
            "predicted_passenger_demand_footfall": pred_demand,
            "congestion_risk": risk,
            "is_peak_hour": bool(is_peak),
            "recommendation": recommendation
        }

    def generate_route_24h_forecast(self, day_of_week: int = 1):
        """Generate 24-hour demand and density curve for operational planning."""
        curve = []
        for h in range(24):
            pred = self.predict_station_crowd(hour=h, day_of_week=day_of_week)
            curve.append({
                "hour": h,
                "time_slot": f"{h:02d}:00",
                "predicted_density_percent": pred["predicted_crowd_density_percent"],
                "predicted_passenger_demand": pred["predicted_passenger_demand_footfall"],
                "congestion_risk": pred["congestion_risk"],
                "is_peak": pred["is_peak_hour"]
            })
        return curve

# Global singleton
ai_crowd_predictor = CrowdPredictor()

