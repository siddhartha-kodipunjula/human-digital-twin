from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


Gender = Literal["male", "female", "other"]
FoodPreference = Literal["veg", "non-veg", "vegan"]
DietPattern = Literal["balanced", "high_protein", "junk_heavy"]
FitnessGoal = Literal["weight_loss", "muscle_gain", "maintenance"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]
RiskLevel = Literal["low", "moderate", "high", "critical"]


class MessageResponse(BaseModel):
    message: str


class UserSignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserPublic(BaseModel):
    id: str
    name: str
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserPublic


class ProfileUpsertRequest(BaseModel):
    age: int = Field(..., ge=10, le=100)
    gender: Gender
    height_cm: float = Field(..., ge=100, le=240)
    weight_kg: float = Field(..., ge=30, le=250)
    food_preference: FoodPreference
    diet_pattern: DietPattern
    pre_existing_conditions: list[str] = Field(default_factory=list, max_length=20)
    fitness_goal: FitnessGoal


class ProfileResponse(BaseModel):
    age: int
    gender: Gender
    height_cm: float
    weight_kg: float
    bmi: float
    food_preference: FoodPreference
    diet_pattern: DietPattern
    pre_existing_conditions: list[str]
    fitness_goal: FitnessGoal
    updated_at: datetime

    class Config:
        from_attributes = True


class DailyLogRequest(BaseModel):
    log_date: date = Field(default_factory=date.today)
    sleep_hours: float = Field(..., ge=0, le=24)
    daily_steps: int = Field(..., ge=0, le=100000)
    heart_rate: int = Field(..., ge=30, le=220)
    calories_burned: float = Field(..., ge=200, le=12000)
    stress_level: int = Field(..., ge=1, le=10)
    water_intake: float = Field(..., ge=0, le=15)
    exercise_minutes: int = Field(..., ge=0, le=600)


class DailyLogPatchRequest(BaseModel):
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    daily_steps: int | None = Field(default=None, ge=0, le=100000)
    heart_rate: int | None = Field(default=None, ge=30, le=220)
    calories_burned: float | None = Field(default=None, ge=200, le=12000)
    stress_level: int | None = Field(default=None, ge=1, le=10)
    water_intake: float | None = Field(default=None, ge=0, le=15)
    exercise_minutes: int | None = Field(default=None, ge=0, le=600)


class DailyLogResponse(BaseModel):
    id: int
    log_date: date
    sleep_hours: float
    daily_steps: int
    heart_rate: int
    calories_burned: float
    stress_level: int
    water_intake: float
    exercise_minutes: int
    updated_at: datetime

    class Config:
        from_attributes = True


class FoodLogRequest(BaseModel):
    log_date: date = Field(default_factory=date.today)
    meal_type: MealType
    food_name: str = Field(..., min_length=2, max_length=140)
    calories: float = Field(..., ge=0, le=5000)
    protein_g: float = Field(..., ge=0, le=300)
    carbs_g: float = Field(..., ge=0, le=500)
    fats_g: float = Field(..., ge=0, le=250)
    fiber_g: float = Field(0, ge=0, le=120)
    notes: str | None = Field(default=None, max_length=500)


class FoodLogResponse(BaseModel):
    id: int
    log_date: date
    meal_type: MealType
    food_name: str
    calories: float
    protein_g: float
    carbs_g: float
    fats_g: float
    fiber_g: float
    notes: str | None

    class Config:
        from_attributes = True


class MacroSummaryResponse(BaseModel):
    log_date: date
    calories: float
    protein_g: float
    carbs_g: float
    fats_g: float
    fiber_g: float
    recommendation: str


class PredictionInputOverride(BaseModel):
    log_date: date | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    daily_steps: int | None = Field(default=None, ge=0, le=100000)
    heart_rate: int | None = Field(default=None, ge=30, le=220)
    calories_burned: float | None = Field(default=None, ge=200, le=12000)
    stress_level: int | None = Field(default=None, ge=1, le=10)
    water_intake: float | None = Field(default=None, ge=0, le=15)
    exercise_minutes: int | None = Field(default=None, ge=0, le=600)


class PredictionRequest(BaseModel):
    source: Literal["manual", "daily_log", "upload", "simulation"] = "manual"
    overrides: PredictionInputOverride = Field(default_factory=PredictionInputOverride)


class SimulationRequest(BaseModel):
    base_log_date: date | None = None
    scenario: PredictionInputOverride


class PredictionResponse(BaseModel):
    id: int | None = None
    source: str
    created_at: datetime
    log_date: date
    wellness_score: float
    wellness_category: str
    risk_level: RiskLevel
    model_outputs: dict
    recommendations: list[str]
    input_snapshot: dict
    digital_twin: dict


class ForecastPoint(BaseModel):
    day_offset: int
    target_date: date
    forecast_score: float
    forecast_category: str


class ForecastResponse(BaseModel):
    points: list[ForecastPoint]


class ModelMetricResponse(BaseModel):
    model_name: str
    version: str
    trained_at: datetime
    accuracy: float | None
    precision: float | None
    recall: float | None
    f1_score: float | None
    metadata_json: dict

    class Config:
        from_attributes = True


class TrainModelsResponse(BaseModel):
    trained_at: datetime
    models: dict
    best_model: str
    training_rows: int
    notes: list[str]


class TrendPoint(BaseModel):
    period_start: date
    average_score: float


class AnomalyPoint(BaseModel):
    date: date
    score: float
    z_score: float
    reason: str


class DashboardOverviewResponse(BaseModel):
    current_state: dict
    predicted_state: dict
    weekly_trend: list[TrendPoint]
    monthly_trend: list[TrendPoint]
    anomalies: list[AnomalyPoint]
    habit_impact: dict
