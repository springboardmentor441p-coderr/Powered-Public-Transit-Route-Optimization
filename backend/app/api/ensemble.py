# backend/app/api/ensemble.py
"""Ensemble prediction API.
Provides a single endpoint that returns the averaged crowd/demand prediction
from the GradientBoosting and LSTM models together with a 95 % confidence
interval.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..ml.ensemble import get_ensemble_predictor
from ..models import User
from .auth import get_current_user

router = APIRouter()

class EnsembleRequest(BaseModel):
    route_id: str
    hour: int  # 0‑23
    day_of_week: int  # 0=Mon … 6=Sun

class EnsembleResponse(BaseModel):
    predicted_value: float
    confidence_interval: tuple[float, float]

@router.post("/ensemble", response_model=EnsembleResponse)
def predict_ensemble(request: EnsembleRequest, current_user: User = Depends(get_current_user)):
    if not (0 <= request.hour <= 23):
        raise HTTPException(status_code=400, detail="Hour must be between 0 and 23")
    if not (0 <= request.day_of_week <= 6):
        raise HTTPException(status_code=400, detail="day_of_week must be between 0 (Mon) and 6 (Sun)")
    predictor = get_ensemble_predictor()
    pred, ci = predictor.predict(request.route_id, request.hour, request.day_of_week)
    return EnsembleResponse(predicted_value=pred, confidence_interval=ci)

