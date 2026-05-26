from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import DailyLog, User
from ..schemas import DailyLogPatchRequest, DailyLogRequest, DailyLogResponse

router = APIRouter(prefix="/daily-logs", tags=["Daily Logs"])


def _to_response(log: DailyLog) -> DailyLogResponse:
    return DailyLogResponse.model_validate(log)


@router.post("", response_model=DailyLogResponse, status_code=status.HTTP_201_CREATED)
def upsert_daily_log(
    payload: DailyLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyLogResponse:
    row = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == current_user.id, DailyLog.log_date == payload.log_date)
        .first()
    )
    if row is None:
        row = DailyLog(user_id=current_user.id, **payload.model_dump())
        db.add(row)
    else:
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.patch("/{log_date}", response_model=DailyLogResponse)
def patch_daily_log(
    log_date: date,
    payload: DailyLogPatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyLogResponse:
    row = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == current_user.id, DailyLog.log_date == log_date)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily log not found.")

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided.")

    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.get("", response_model=list[DailyLogResponse])
def list_daily_logs(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DailyLogResponse]:
    query = db.query(DailyLog).filter(DailyLog.user_id == current_user.id)
    if start_date:
        query = query.filter(DailyLog.log_date >= start_date)
    if end_date:
        query = query.filter(DailyLog.log_date <= end_date)
    rows = query.order_by(DailyLog.log_date.desc()).limit(limit).all()
    return [_to_response(item) for item in rows]
