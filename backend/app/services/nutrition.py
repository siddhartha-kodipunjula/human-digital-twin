from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..ml.recommendation import nutrition_recommendation
from ..models import FoodLog, Profile


def get_daily_macro_summary(db: Session, user_id: str, log_date: date) -> dict[str, Any]:
    totals = (
        db.query(
            func.coalesce(func.sum(FoodLog.calories), 0.0).label("calories"),
            func.coalesce(func.sum(FoodLog.protein_g), 0.0).label("protein_g"),
            func.coalesce(func.sum(FoodLog.carbs_g), 0.0).label("carbs_g"),
            func.coalesce(func.sum(FoodLog.fats_g), 0.0).label("fats_g"),
            func.coalesce(func.sum(FoodLog.fiber_g), 0.0).label("fiber_g"),
        )
        .filter(FoodLog.user_id == user_id, FoodLog.log_date == log_date)
        .first()
    )

    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    goal = profile.fitness_goal if profile else "maintenance"
    conditions = profile.pre_existing_conditions if profile else []

    protein = float(totals.protein_g if totals else 0.0)
    carbs = float(totals.carbs_g if totals else 0.0)
    fats = float(totals.fats_g if totals else 0.0)

    return {
        "log_date": log_date,
        "calories": round(float(totals.calories if totals else 0.0), 2),
        "protein_g": round(protein, 2),
        "carbs_g": round(carbs, 2),
        "fats_g": round(fats, 2),
        "fiber_g": round(float(totals.fiber_g if totals else 0.0), 2),
        "recommendation": nutrition_recommendation(goal, conditions, protein, carbs, fats),
    }
