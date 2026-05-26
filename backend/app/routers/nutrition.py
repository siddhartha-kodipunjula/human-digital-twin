from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import FoodLog, User
from ..schemas import FoodLogRequest, FoodLogResponse, MacroSummaryResponse
from ..services.nutrition import get_daily_macro_summary

router = APIRouter(prefix="/nutrition", tags=["Nutrition"])


@router.post("/logs", response_model=FoodLogResponse, status_code=status.HTTP_201_CREATED)
def create_food_log(
    payload: FoodLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FoodLogResponse:
    row = FoodLog(user_id=current_user.id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return FoodLogResponse.model_validate(row)


@router.get("/logs", response_model=list[FoodLogResponse])
def list_food_logs(
    log_date: date | None = Query(default=None),
    limit: int = Query(default=120, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FoodLogResponse]:
    query = db.query(FoodLog).filter(FoodLog.user_id == current_user.id)
    if log_date is not None:
        query = query.filter(FoodLog.log_date == log_date)
    rows = query.order_by(FoodLog.log_date.desc(), FoodLog.id.desc()).limit(limit).all()
    return [FoodLogResponse.model_validate(row) for row in rows]


@router.get("/summary/{log_date}", response_model=MacroSummaryResponse)
def daily_macro_summary(
    log_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MacroSummaryResponse:
    payload = get_daily_macro_summary(db, user_id=current_user.id, log_date=log_date)
    return MacroSummaryResponse(**payload)
