from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

NUMERIC_FEATURES = [
    "age",
    "height_cm",
    "weight_kg",
    "bmi",
    "sleep_hours",
    "daily_steps",
    "heart_rate",
    "calories_burned",
    "stress_level",
    "water_intake",
    "exercise_minutes",
    "protein_g",
    "carbs_g",
    "fats_g",
    "activity_ratio",
    "sleep_quality_score",
]

CATEGORICAL_FEATURES = [
    "gender",
    "food_preference",
    "diet_pattern",
    "fitness_goal",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES + ["conditions_count"]

CATEGORY_LABELS = ["Poor", "Average", "Good", "Excellent"]


@dataclass
class WellnessFeatures:
    values: dict[str, Any]


def calculate_bmi(height_cm: float, weight_kg: float) -> float:
    meters = max(float(height_cm) / 100.0, 0.5)
    return round(float(weight_kg) / (meters**2), 2)


def activity_ratio(daily_steps: float, exercise_minutes: float) -> float:
    steps_score = np.clip(float(daily_steps) / 10000.0, 0, 2)
    exercise_score = np.clip(float(exercise_minutes) / 60.0, 0, 2)
    return float(np.clip((steps_score + exercise_score) / 2.0, 0, 2))


def sleep_quality_score(sleep_hours: float, stress_level: float) -> float:
    sleep_alignment = np.clip(1 - abs(float(sleep_hours) - 8.0) / 5.0, 0, 1)
    stress_penalty = np.clip((10.0 - float(stress_level)) / 10.0, 0, 1)
    return float(np.clip(0.7 * sleep_alignment + 0.3 * stress_penalty, 0, 1))


def compute_wellness_score(record: dict[str, Any]) -> float:
    bmi = float(record["bmi"])
    bmi_score = np.clip(1 - abs(bmi - 22.0) / 18.0, 0, 1)
    sleep_score = np.clip(float(record["sleep_quality_score"]), 0, 1)
    activity_score = np.clip(float(record["activity_ratio"]) / 1.2, 0, 1)
    stress_score = np.clip((10 - float(record["stress_level"])) / 10, 0, 1)
    heart_score = np.clip(1 - abs(float(record["heart_rate"]) - 72) / 45, 0, 1)
    hydration_score = np.clip(float(record["water_intake"]) / 3.2, 0, 1)
    nutrition_score = np.clip(
        (
            min(float(record["protein_g"]) / 100.0, 1.0)
            + min(float(record["fats_g"]) / 70.0, 1.0)
            + min(float(record["carbs_g"]) / 250.0, 1.0)
        )
        / 3.0,
        0,
        1,
    )

    weighted = (
        0.2 * sleep_score
        + 0.2 * activity_score
        + 0.16 * stress_score
        + 0.12 * heart_score
        + 0.12 * hydration_score
        + 0.1 * bmi_score
        + 0.1 * nutrition_score
    )
    return float(np.clip(weighted * 100, 0, 100))


def categorize_wellness(score: float) -> str:
    if score < 40:
        return "Poor"
    if score < 60:
        return "Average"
    if score < 80:
        return "Good"
    return "Excellent"


def risk_level_from_score(score: float) -> str:
    if score >= 80:
        return "low"
    if score >= 65:
        return "moderate"
    if score >= 45:
        return "high"
    return "critical"


def normalize_gender(value: str) -> str:
    lowered = str(value).strip().lower()
    if lowered.startswith("m"):
        return "male"
    if lowered.startswith("f"):
        return "female"
    return "other"


def safe_macro(value: float | None, fallback: float) -> float:
    if value is None:
        return fallback
    return float(max(value, 0.0))


def build_feature_record(profile: dict[str, Any], daily: dict[str, Any], macro_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    macro_summary = macro_summary or {}
    bmi = calculate_bmi(float(profile["height_cm"]), float(profile["weight_kg"]))
    record = {
        "age": float(profile["age"]),
        "gender": normalize_gender(profile["gender"]),
        "height_cm": float(profile["height_cm"]),
        "weight_kg": float(profile["weight_kg"]),
        "bmi": bmi,
        "food_preference": str(profile["food_preference"]).lower(),
        "diet_pattern": str(profile["diet_pattern"]).lower(),
        "fitness_goal": str(profile["fitness_goal"]).lower(),
        "conditions_count": int(len(profile.get("pre_existing_conditions") or [])),
        "sleep_hours": float(daily["sleep_hours"]),
        "daily_steps": float(daily["daily_steps"]),
        "heart_rate": float(daily["heart_rate"]),
        "calories_burned": float(daily["calories_burned"]),
        "stress_level": float(daily["stress_level"]),
        "water_intake": float(daily["water_intake"]),
        "exercise_minutes": float(daily["exercise_minutes"]),
        "protein_g": safe_macro(macro_summary.get("protein_g"), 55.0),
        "carbs_g": safe_macro(macro_summary.get("carbs_g"), 210.0),
        "fats_g": safe_macro(macro_summary.get("fats_g"), 65.0),
    }
    record["activity_ratio"] = activity_ratio(record["daily_steps"], record["exercise_minutes"])
    record["sleep_quality_score"] = sleep_quality_score(record["sleep_hours"], record["stress_level"])
    record["bmi"] = calculate_bmi(record["height_cm"], record["weight_kg"])
    return record


def to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    for column in NUMERIC_FEATURES + ["conditions_count"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].fillna("unknown").astype(str).str.lower()
    return frame[FEATURE_COLUMNS].copy()
