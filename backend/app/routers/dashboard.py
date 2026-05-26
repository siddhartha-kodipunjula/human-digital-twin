from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..ml.engine import WellnessPredictionEngine
from ..models import Prediction, User
from ..schemas import DashboardOverviewResponse
from ..services.analytics import dashboard_overview

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
engine = WellnessPredictionEngine()


@router.get("/overview", response_model=DashboardOverviewResponse)
def overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOverviewResponse:
    rows = (
        db.query(Prediction.wellness_score)
        .filter(Prediction.user_id == current_user.id)
        .order_by(Prediction.log_date.asc())
        .all()
    )
    history_scores = [float(row.wellness_score) for row in rows]
    forecast_points = engine.forecast(history_scores, days=7)
    payload = dashboard_overview(db, user_id=current_user.id, forecast_points=forecast_points)
    return DashboardOverviewResponse(**payload)


@router.get("/anomalies")
def anomalies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    payload = dashboard_overview(db, user_id=current_user.id, forecast_points=[])
    return {"anomalies": payload["anomalies"]}


@router.get("/habit-impact")
def habit_impact(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    payload = dashboard_overview(db, user_id=current_user.id, forecast_points=[])
    return payload["habit_impact"]


@router.get("/trends")
def trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    payload = dashboard_overview(db, user_id=current_user.id, forecast_points=[])
    return {
        "weekly_trend": payload["weekly_trend"],
        "monthly_trend": payload["monthly_trend"],
    }
