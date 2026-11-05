"""Train API routes."""
from typing: Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.train import TrainService
from app.schemas.train import TrainCreate, TrainUpdate, TrainResponse

router = APIRouter()


@router.post("", response_model=TrainResponse, status_code=status.HTTP_201_CREATED)
async def create_train(
    train_data: TrainCreate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new train."""
    service = TrainService(db)

    # Check if train number exists
    existing = await service.get_train_by_number(train_data.train_number)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Train number already exists",
        )

    train = await service.create_train(train_data)
    return TrainResponse.model_validate(train)


@router.get("", response_model=List[TrainResponse])
async def list_trains(
    line_id: Optional[UUID] = None,
    status: Optional[str] = None,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List trains with optional filtering."""
    service = TrainService(db)

    # Parse status if provided
    train_status = None
    if status:
        from app.models.train import TrainStatus
        try:
            train_status = TrainStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    trains = await service.list_trains(line_id, train_status, active_only, skip, limit)
    return [TrainResponse.model_validate(t) for t in trains]


@router.get("/{train_id}", response_model=TrainResponse)
async def get_train(
    train_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get train by ID."""
    service = TrainService(db)
    train = await service.get_train(train_id)
    if not train:
        raise HTTPException(status_code=404, detail="Train not found")
    return TrainResponse.model_validate(train)


@router.put("/{train_id}", response_model=TrainResponse)
async def update_train(
    train_id: UUID,
    train_data: TrainUpdate,
    current_user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    """Update train."""
    service = TrainService(db)
    train = await service.update_train(train_id, train_data)
    if not train:
        raise HTTPException(status_code=404, detail="Train not found")
    return TrainResponse.model_validate(train)


@router.delete("/{train_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_train(
    train_id: UUID,
    current_user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Delete train."""
    service = TrainService(db)
    success = await service.delete_train(train_id)
    if not success:
        raise HTTPException(status_code=404, detail="Train not found")