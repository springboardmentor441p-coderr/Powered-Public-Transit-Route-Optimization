"""AI Prediction service for crowd forecasting and demand prediction."""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID
import json
import os
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ridership import RidershipRecord
from app.models.congestion import CongestionEvent
from app.models.station import Station
from app.schemas.prediction import (
    CrowdPredictionRequest,
    CrowdPredictionResponse,
    CrowdPredictionPoint,
    DemandForecastResponse,
    DemandForecastPoint,
    TrafficPatternResponse,
    TrafficPatternPoint,
)


class PredictionService:
    """AI prediction service for crowd management."""

    MODEL_DIR = "/app/models"
    MODEL_VERSION = "1.0.0"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.crowd_model = None
        self.demand_model = None
        self.scaler = StandardScaler()
        self._ensure_model_dir()

    def _ensure_model_dir(self):
        """Ensure model directory exists."""
        os.makedirs(self.MODEL_DIR, exist_ok=True)

    def _load_or_train_crowd_model(self, station_id: UUID) -> Ridge:
        """Load or train crowd prediction model for a station."""
        model_path = os.path.join(self.MODEL_DIR, f"crowd_{station_id}.joblib")

        if os.path.exists(model_path):
            return joblib.load(model_path)

        # Train new model with synthetic data if no historical data
        model = Ridge(alpha=1.0)
        # In production, this would use actual historical data
        # For now, create a simple model
        X = np.random.randn(100, 5)  # features: hour, day_of_week, is_weekend, prev_entries, prev_exits
        y = np.random.randint(0, 500, 100)  # target: entries
        model.fit(X, y)
        joblib.dump(model, model_path)
        return model

    def _load_or_train_demand_model(self, line_id: Optional[UUID] = None) -> RandomForestRegressor:
        """Load or train demand forecasting model."""
        suffix = f"_{line_id}" if line_id else "_system"
        model_path = os.path.join(self.MODEL_DIR, f"demand{suffix}.joblib")

        if os.path.exists(model_path):
            return joblib.load(model_path)

        model = RandomForestRegressor(n_estimators=100, random_state=42)
        # Train with synthetic data
        X = np.random.randn(200, 7)  # features
        y = np.random.randint(1000, 10000, 200)  # target: daily demand
        model.fit(X, y)
        joblib.dump(model, model_path)
        return model

    async def predict_crowd(self, request: CrowdPredictionRequest) -> CrowdPredictionResponse:
        """Predict crowd for a station."""
        station = await self.db.get(Station, request.station_id)
        if not station:
            raise ValueError("Station not found")

        # Get historical data for feature engineering
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=30)

        result = await self.db.execute(
            select(RidershipRecord)
            .where(
                RidershipRecord.station_id == request.station_id,
                RidershipRecord.timestamp >= start_time,
                RidershipRecord.timestamp <= end_time,
            )
            .order_by(RidershipRecord.timestamp)
        )
        records = list(result.scalars().all())

        # Generate predictions
        predictions = []
        model = self._load_or_train_crowd_model(request.station_id)

        current_time = end_time
        for i in range(request.hours_ahead * (60 // request.interval_minutes)):
            # Create features
            hour = current_time.hour
            day_of_week = current_time.weekday()
            is_weekend = 1 if day_of_week >= 5 else 0

            # Use recent average as baseline
            recent_entries = [r.entry_count for r in records[-10:]] if records else [100]
            recent_exits = [r.exit_count for r in records[-10:]] if records else [100]

            features = np.array([[
                hour,
                day_of_week,
                is_weekend,
                np.mean(recent_entries),
                np.mean(recent_exits),
            ]])

            predicted_entries = max(0, int(model.predict(features)[0]))
            predicted_exits = max(0, int(predicted_entries * 0.9))  # rough estimate
            predicted_occupancy = predicted_entries + predicted_exits

            # Confidence intervals (simplified)
            std = max(10, predicted_entries * 0.15)
            confidence_lower = max(0, predicted_entries - int(1.96 * std))
            confidence_upper = predicted_entries + int(1.96 * std)

            predictions.append(CrowdPredictionPoint(
                timestamp=current_time,
                predicted_entries=predicted_entries,
                predicted_exits=predicted_exits,
                predicted_occupancy=predicted_occupancy,
                confidence_lower=confidence_lower,
                confidence_upper=confidence_upper,
            ))

            current_time += timedelta(minutes=request.interval_minutes)

        return CrowdPredictionResponse(
            station_id=request.station_id,
            station_name=station.name,
            predictions=predictions,
            model_version=self.MODEL_VERSION,
            generated_at=datetime.utcnow(),
        )

    async def forecast_demand(
        self,
        line_id: Optional[UUID] = None,
        station_id: Optional[UUID] = None,
        days: int = 7,
    ) -> DemandForecastResponse:
        """Forecast passenger demand."""
        model = self._load_or_train_demand_model(line_id)

        forecasts = []
        current_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        for i in range(days):
            date = current_date + timedelta(days=i)
            day_of_week = date.weekday()
            is_weekend = 1 if day_of_week >= 5 else 0
            is_holiday = 0  # Simplified

            features = np.array([[
                day_of_week,
                is_weekend,
                is_holiday,
                date.month,
                date.day,
                0,  # weather factor
                0,  # event factor
            ]])

            predicted = max(100, int(model.predict(features)[0]))
            std = predicted * 0.2

            forecasts.append(DemandForecastPoint(
                date=date,
                predicted_demand=predicted,
                confidence_lower=max(0, int(predicted - 1.96 * std)),
                confidence_upper=int(predicted + 1.96 * std),
                factors={
                    "day_of_week": day_of_week,
                    "is_weekend": bool(is_weekend),
                    "seasonal_factor": 1.0,
                },
            ))

        target_name = "system"
        if line_id:
            target_name = f"line_{line_id}"
        elif station_id:
            target_name = f"station_{station_id}"

        return DemandForecastResponse(
            line_id=line_id,
            station_id=station_id,
            forecasts=forecasts,
            model_version=self.MODEL_VERSION,
            generated_at=datetime.utcnow(),
        )

    async def analyze_traffic_patterns(self, station_id: UUID) -> TrafficPatternResponse:
        """Analyze traffic patterns for a station."""
        station = await self.db.get(Station, station_id)
        if not station:
            raise ValueError("Station not found")

        # Get 30 days of data
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=30)

        result = await self.db.execute(
            select(RidershipRecord)
            .where(
                RidershipRecord.station_id == station_id,
                RidershipRecord.timestamp >= start_time,
                RidershipRecord.timestamp <= end_time,
            )
        )
        records = list(result.scalars().all())

        if not records:
            # Return synthetic patterns
            patterns = []
            for hour in range(24):
                patterns.append(TrafficPatternPoint(
                    hour=hour,
                    day_of_week=0,
                    avg_entries=50 + 30 * np.sin(hour / 24 * 2 * np.pi),
                    avg_exits=45 + 25 * np.sin(hour / 24 * 2 * np.pi),
                    peak_factor=1.0 + 0.5 * np.sin(hour / 24 * 2 * np.pi),
                ))

            return TrafficPatternResponse(
                station_id=station_id,
                station_name=station.name,
                patterns=patterns,
                peak_hours=[7, 8, 17, 18],
                off_peak_hours=[10, 11, 13, 14],
                weekly_pattern={str(i): 1.0 for i in range(7)},
            )

        # Convert to DataFrame for analysis
        df = pd.DataFrame([
            {
                "hour": r.timestamp.hour,
                "day_of_week": r.timestamp.weekday(),
                "entries": r.entry_count,
                "exits": r.exit_count,
            }
            for r in records
        ])

        # Analyze hourly patterns
        hourly = df.groupby("hour").agg({
            "entries": "mean",
            "exits": "mean",
        }).reset_index()

        patterns = []
        max_entries = hourly["entries"].max()
        for _, row in hourly.iterrows():
            peak_factor = row["entries"] / max_entries if max_entries > 0 else 1.0
            patterns.append(TrafficPatternPoint(
                hour=int(row["hour"]),
                day_of_week=0,  # Average across days
                avg_entries=row["entries"],
                avg_exits=row["exits"],
                peak_factor=peak_factor,
            ))

        # Find peak hours (top 25%)
        threshold = hourly["entries"].quantile(0.75)
        peak_hours = hourly[hourly["entries"] >= threshold]["hour"].astype(int).tolist()
        off_peak_hours = hourly[hourly["entries"] <= hourly["entries"].quantile(0.25)]["hour"].astype(int).tolist()

        # Weekly pattern
        weekly = df.groupby("day_of_week")["entries"].mean()
        weekly_avg = weekly.mean()
        weekly_pattern = {
            str(day): weekly.get(day, weekly_avg) / weekly_avg
            for day in range(7)
        }

        return TrafficPatternResponse(
            station_id=station_id,
            station_name=station.name,
            patterns=patterns,
            peak_hours=peak_hours,
            off_peak_hours=off_peak_hours,
            weekly_pattern=weekly_pattern,
        )

    async def retrain_models(self, model_type: str = "all") -> Dict[str, Any]:
        """Retrain prediction models."""
        results = {}

        if model_type in ("crowd", "all"):
            # Retrain crowd models for all stations
            stations_result = await self.db.execute(select(Station).where(Station.is_active == True))
            stations = list(stations_result.scalars().all())

            for station in stations:
                model_path = os.path.join(self.MODEL_DIR, f"crowd_{station.id}.joblib")
                if os.path.exists(model_path):
                    os.remove(model_path)
                self._load_or_train_crowd_model(station.id)

            results["crowd"] = {"stations_retrained": len(stations)}

        if model_type in ("demand", "all"):
            model_path = os.path.join(self.MODEL_DIR, "demand_system.joblib")
            if os.path.exists(model_path):
                os.remove(model_path)
            self._load_or_train_demand_model()
            results["demand"] = {"retrained": True}

        return results