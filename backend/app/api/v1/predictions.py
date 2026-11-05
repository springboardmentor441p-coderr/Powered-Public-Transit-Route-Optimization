"""Prediction API routes."""
from typing: Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.prediction import PredictionService
from app.schemas.prediction import (
    CrowdPredictionRequest,
    CrowdPredictionResponse,
    DemandForecastResponse,
    TrafficPatternResponse,
    ModelRetrainRequest,
    ModelRetrainResponse,
)

router = APIRouter()


@router.post("/crowd", response_model=CrowdPredictionResponse)
async def predict_crowd(
    request: CrowdPredictionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Predict crowd for a station."""
    service = PredictionService(db)
    return await service.predict_crowd(request)


@router.get("/crowd/station/{station_id}", response_model=CrowdPredictionResponse)
async def get_crowd_prediction(
    station_id: UUID,
    hours_ahead: int = 24,
    interval_minutes: int = 15,
    db: AsyncSession = Depends(get_db),
):
    """Get crowd prediction for a station."""
    service = PredictionService(db)
    request = CrowdPredictionRequest(
        station_id=station_id,
        hours_ahead=hours_ahead,
        interval_minutes=interval_minutes,
    )
    return await service.predict_crowd(request)


@router.get("/demand", response_model=DemandForecastResponse)
async def forecast_demand(
    line_id: Optional[UUID] = None,
    station_id: Optional[UUID] = None,
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """Forecast passenger demand."""
    service = PredictionService(db)
    return await service.forecast_demand(line_id, station_id, days)


@router.get("/traffic/station/{station_id}", response_model=TrafficPatternResponse)
async def analyze_traffic_patterns(
    station_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Analyze traffic patterns for a station."""
    service = PredictionService(db)
    return await service.analyze_traffic_patterns(station_id)


@router.post("/retrain", response_model=ModelRetrainResponse)
async def retrain_models(
    request: ModelRetrainRequest,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Retrain prediction models."""
    service = PredictionService(db)
    results = await service.retrain_models(request.model_type)
    return ModelRetrainResponse(
        success=True,
        message=f"Models retrained: {request.model_type}",
        model_type=request.model_type,
        metrics=results,
    )