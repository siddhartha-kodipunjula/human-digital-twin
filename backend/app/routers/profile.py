from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..ml.feature_engineering import calculate_bmi
from ..models import Profile, User
from ..schemas import ProfileResponse, ProfileUpsertRequest

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfileResponse:
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return ProfileResponse.model_validate(profile)


@router.put("", response_model=ProfileResponse)
def upsert_profile(
    payload: ProfileUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    bmi = calculate_bmi(payload.height_cm, payload.weight_kg)
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    normalized_conditions = [item.strip().lower() for item in payload.pre_existing_conditions if item.strip()]
    if profile is None:
        profile = Profile(
            user_id=current_user.id,
            age=payload.age,
            gender=payload.gender,
            height_cm=payload.height_cm,
            weight_kg=payload.weight_kg,
            bmi=bmi,
            food_preference=payload.food_preference,
            diet_pattern=payload.diet_pattern,
            pre_existing_conditions=normalized_conditions,
            fitness_goal=payload.fitness_goal,
        )
        db.add(profile)
    else:
        profile.age = payload.age
        profile.gender = payload.gender
        profile.height_cm = payload.height_cm
        profile.weight_kg = payload.weight_kg
        profile.bmi = bmi
        profile.food_preference = payload.food_preference
        profile.diet_pattern = payload.diet_pattern
        profile.pre_existing_conditions = normalized_conditions
        profile.fitness_goal = payload.fitness_goal
    db.commit()
    db.refresh(profile)
    return ProfileResponse.model_validate(profile)
