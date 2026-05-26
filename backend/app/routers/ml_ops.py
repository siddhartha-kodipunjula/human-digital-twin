from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..ml.engine import WellnessPredictionEngine
from ..models import ModelMetric, User
from ..schemas import ModelMetricResponse, TrainModelsResponse

router = APIRouter(prefix="/ml", tags=["ML Operations"])
engine = WellnessPredictionEngine()


@router.post("/train", response_model=TrainModelsResponse)
def train_models(
    rows: int = Query(default=5500, ge=1000, le=30000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainModelsResponse:
    _ = current_user
    payload = engine.retrain(db, rows=rows)
    return TrainModelsResponse(**payload)


@router.get("/metrics", response_model=list[ModelMetricResponse])
def model_metrics(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ModelMetricResponse]:
    _ = current_user
    rows = db.query(ModelMetric).order_by(ModelMetric.trained_at.desc()).limit(limit).all()
    payload = [ModelMetricResponse.model_validate(row) for row in rows]
    if not any(item.model_name.lower() == "lstm" for item in payload):
        payload.append(
            ModelMetricResponse(
                model_name="lstm",
                version="pending",
                trained_at=datetime.now(timezone.utc),
                accuracy=None,
                precision=None,
                recall=None,
                f1_score=None,
                metadata_json={
                    "available": False,
                    "message": "LSTM metrics will appear after running /api/v1/ml/train.",
                },
            )
        )
    return payload
