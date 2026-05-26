from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..ml.engine import WellnessPredictionEngine
from ..ml.feature_engineering import build_feature_record
from ..ml.recommendation import generate_recommendations
from ..models import DailyLog, Prediction, Profile, User
from ..schemas import (
    ForecastResponse,
    PredictionRequest,
    PredictionResponse,
    SimulationRequest,
)
from ..services.nutrition import get_daily_macro_summary

router = APIRouter(prefix="/predictions", tags=["Predictions"])
engine = WellnessPredictionEngine()


def _profile_or_400(db: Session, user_id: str) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create your profile before requesting predictions.",
        )
    return profile


def _resolve_daily_payload(db: Session, user_id: str, target_date: date | None, overrides: dict[str, Any]) -> tuple[dict[str, Any], date]:
    query = db.query(DailyLog).filter(DailyLog.user_id == user_id)
    if target_date:
        query = query.filter(DailyLog.log_date == target_date)
    row = query.order_by(DailyLog.log_date.desc()).first()

    if row is None:
        required = [
            "sleep_hours",
            "daily_steps",
            "heart_rate",
            "calories_burned",
            "stress_level",
            "water_intake",
            "exercise_minutes",
        ]
        missing = [field for field in required if overrides.get(field) is None]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing daily inputs: {missing}. Add a daily log or pass overrides.",
            )
        merged = {field: overrides[field] for field in required}
        return merged, (target_date or date.today())

    merged = {
        "sleep_hours": row.sleep_hours,
        "daily_steps": row.daily_steps,
        "heart_rate": row.heart_rate,
        "calories_burned": row.calories_burned,
        "stress_level": row.stress_level,
        "water_intake": row.water_intake,
        "exercise_minutes": row.exercise_minutes,
    }
    for key, value in overrides.items():
        if key in merged and value is not None:
            merged[key] = value
    return merged, row.log_date


def _history_scores(db: Session, user_id: str, limit: int = 30) -> list[float]:
    rows = (
        db.query(Prediction.wellness_score)
        .filter(Prediction.user_id == user_id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [float(row.wellness_score) for row in reversed(rows)]


def _save_prediction(
    db: Session,
    user_id: str,
    source: str,
    log_date: date,
    payload: dict[str, Any],
    recommendations: list[str],
    input_snapshot: dict[str, Any],
    scenario: dict[str, Any] | None = None,
) -> Prediction:
    row = Prediction(
        user_id=user_id,
        source=source,
        log_date=log_date,
        wellness_score=payload["wellness_score"],
        wellness_category=payload["wellness_category"],
        risk_level=payload["risk_level"],
        model_outputs=payload["model_outputs"],
        recommendation_items=recommendations,
        input_snapshot=input_snapshot,
        scenario=scenario,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _prediction_response(row: Prediction) -> PredictionResponse:
    digital_twin = {
        "health_status": row.wellness_category,
        "risk_indicator": row.risk_level,
        "visual_state": "stable" if row.risk_level in {"low", "moderate"} else "alert",
    }
    return PredictionResponse(
        id=row.id,
        source=row.source,
        created_at=row.created_at,
        log_date=row.log_date,
        wellness_score=row.wellness_score,
        wellness_category=row.wellness_category,
        risk_level=row.risk_level,  # type: ignore[arg-type]
        model_outputs=row.model_outputs,
        recommendations=row.recommendation_items,
        input_snapshot=row.input_snapshot,
        digital_twin=digital_twin,
    )


@router.post("/run", response_model=PredictionResponse)
def run_prediction(
    payload: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionResponse:
    profile = _profile_or_400(db, current_user.id)
    overrides = payload.overrides.model_dump()
    target_date = overrides.pop("log_date", None)
    daily, log_date = _resolve_daily_payload(db, current_user.id, target_date, overrides)

    macro_summary = get_daily_macro_summary(db, user_id=current_user.id, log_date=log_date)
    profile_payload = {
        "age": profile.age,
        "gender": profile.gender,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "food_preference": profile.food_preference,
        "diet_pattern": profile.diet_pattern,
        "pre_existing_conditions": profile.pre_existing_conditions,
        "fitness_goal": profile.fitness_goal,
    }
    feature_record = build_feature_record(profile_payload, daily, macro_summary=macro_summary)
    prediction_payload = engine.predict(db, feature_record)
    history_scores = _history_scores(db, user_id=current_user.id, limit=30)
    recommendations = generate_recommendations(profile_payload, daily, prediction_payload, history_scores)

    snapshot = {**feature_record, **daily}
    saved = _save_prediction(
        db=db,
        user_id=current_user.id,
        source=payload.source,
        log_date=log_date,
        payload=prediction_payload,
        recommendations=recommendations,
        input_snapshot=snapshot,
    )
    return _prediction_response(saved)


@router.post("/simulate", response_model=dict)
def simulate_prediction(
    payload: SimulationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    profile = _profile_or_400(db, current_user.id)
    scenario = payload.scenario.model_dump(exclude_none=True)
    scenario_date = payload.base_log_date or scenario.get("log_date")
    daily, log_date = _resolve_daily_payload(db, current_user.id, scenario_date, scenario)
    macro_summary = get_daily_macro_summary(db, user_id=current_user.id, log_date=log_date)

    profile_payload = {
        "age": profile.age,
        "gender": profile.gender,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "food_preference": profile.food_preference,
        "diet_pattern": profile.diet_pattern,
        "pre_existing_conditions": profile.pre_existing_conditions,
        "fitness_goal": profile.fitness_goal,
    }

    baseline_record = build_feature_record(profile_payload, daily, macro_summary=macro_summary)
    baseline_payload = engine.predict(db, baseline_record)

    simulated_daily = daily.copy()
    for key, value in scenario.items():
        if key in simulated_daily and value is not None:
            simulated_daily[key] = value
    simulated_record = build_feature_record(profile_payload, simulated_daily, macro_summary=macro_summary)
    simulated_payload = engine.predict(db, simulated_record)

    recommendations = generate_recommendations(profile_payload, simulated_daily, simulated_payload, _history_scores(db, current_user.id))
    saved = _save_prediction(
        db=db,
        user_id=current_user.id,
        source="simulation",
        log_date=log_date,
        payload=simulated_payload,
        recommendations=recommendations,
        input_snapshot=simulated_record,
        scenario=scenario,
    )

    return {
        "simulation": _prediction_response(saved).model_dump(),
        "baseline": baseline_payload,
        "delta_score": round(simulated_payload["wellness_score"] - baseline_payload["wellness_score"], 2),
        "scenario_applied": scenario,
    }


@router.get("/history", response_model=list[PredictionResponse])
def prediction_history(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PredictionResponse]:
    rows = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_prediction_response(row) for row in rows]


@router.get("/forecast", response_model=ForecastResponse)
def forecast(
    days: int = Query(default=7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForecastResponse:
    _ = current_user
    rows = (
        db.query(Prediction.wellness_score)
        .filter(Prediction.user_id == current_user.id)
        .order_by(Prediction.log_date.asc())
        .all()
    )
    history_scores = [float(row.wellness_score) for row in rows]
    points = engine.forecast(history_scores, days=days)
    return ForecastResponse(points=points)
