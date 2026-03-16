from __future__ import annotations

from collections import Counter
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    from .data_processing import (
        FEATURE_COLUMNS,
        Preprocessor,
        PROJECT_ROOT,
        categorize_wellness,
        compute_wellness_score,
        ensure_feature_frame,
        transform_features,
    )
except ImportError:  # pragma: no cover
    from data_processing import (  # type: ignore
        FEATURE_COLUMNS,
        Preprocessor,
        PROJECT_ROOT,
        categorize_wellness,
        compute_wellness_score,
        ensure_feature_frame,
        transform_features,
    )

try:
    from tensorflow.keras.models import load_model

    TENSORFLOW_AVAILABLE = True
except Exception:  # pragma: no cover - fallback for environments without tensorflow
    TENSORFLOW_AVAILABLE = False

MODELS_DIR = PROJECT_ROOT / "models"
LOGISTIC_MODEL_PATH = MODELS_DIR / "logistic_regression.pkl"
RANDOM_FOREST_PATH = MODELS_DIR / "random_forest.pkl"
LSTM_MODEL_PATH = MODELS_DIR / "lstm_model.h5"
PREPROCESSOR_PATH = MODELS_DIR / "preprocessor.pkl"


def generate_recommendations(data: dict[str, Any], wellness_score: float, category: str) -> list[str]:
    recommendations: list[str] = []
    if float(data["sleep_hours"]) < 6:
        recommendations.append("Increase sleep duration to at least 7 hours with a fixed bedtime routine.")
    if float(data["stress_level"]) >= 7:
        recommendations.append("Practice 10-15 minutes of mindfulness, breathing, or meditation daily.")
    if float(data["daily_steps"]) < 5000:
        recommendations.append("Increase physical activity with small walking goals every 2-3 hours.")
    if float(data["water_intake"]) < 2.0:
        recommendations.append("Add hydration reminders and target 2.5-3 liters of water per day.")
    if float(data["exercise_minutes"]) < 25:
        recommendations.append("Aim for at least 30 minutes of moderate exercise on most days.")
    if float(data["heart_rate"]) > 95:
        recommendations.append("Your heart rate is elevated; add recovery breaks and consult a clinician if persistent.")
    if wellness_score < 55:
        recommendations.append("Prioritize one small habit upgrade each week and track progress consistently.")

    if not recommendations:
        recommendations.append("Great routine. Maintain consistency and consider progressive fitness goals.")
    recommendations.append(f"Current wellness category is {category}; reassess metrics every week.")
    return recommendations


class PredictionEngine:
    def __init__(self) -> None:
        self.preprocessor: Preprocessor | None = None
        self.logistic_model = None
        self.random_forest_model = None
        self.lstm_model = None
        self.reload_models()

    def reload_models(self) -> None:
        self.preprocessor = joblib.load(PREPROCESSOR_PATH) if PREPROCESSOR_PATH.exists() else None
        self.logistic_model = joblib.load(LOGISTIC_MODEL_PATH) if LOGISTIC_MODEL_PATH.exists() else None
        self.random_forest_model = joblib.load(RANDOM_FOREST_PATH) if RANDOM_FOREST_PATH.exists() else None
        if TENSORFLOW_AVAILABLE and LSTM_MODEL_PATH.exists():
            self.lstm_model = load_model(LSTM_MODEL_PATH)
        else:
            self.lstm_model = None

    def models_ready(self) -> bool:
        return (
            self.preprocessor is not None
            and self.logistic_model is not None
            and self.random_forest_model is not None
        )

    def _predict_with_models(self, X_scaled: np.ndarray) -> dict[str, str]:
        if not self.models_ready():
            return {}

        assert self.preprocessor is not None  # for type checkers
        inverse = self.preprocessor.category_inverse_map
        predictions: dict[str, str] = {}

        logistic_pred = int(self.logistic_model.predict(X_scaled)[0])
        predictions["logistic_regression"] = inverse[logistic_pred]

        rf_pred = int(self.random_forest_model.predict(X_scaled)[0])
        predictions["random_forest"] = inverse[rf_pred]

        if self.lstm_model is not None:
            X_lstm = X_scaled.reshape((X_scaled.shape[0], X_scaled.shape[1], 1))
            lstm_pred = int(np.argmax(self.lstm_model.predict(X_lstm, verbose=0), axis=1)[0])
            predictions["lstm"] = inverse[lstm_pred]

        return predictions

    def _sanitize_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        cleaned = ensure_feature_frame(frame.copy())
        medians = self.preprocessor.numeric_medians if self.preprocessor else {}
        fallback_defaults = {
            "age": 30,
            "sleep_hours": 7.0,
            "daily_steps": 6000,
            "heart_rate": 75,
            "calories_burned": 2200,
            "stress_level": 5,
            "water_intake": 2.2,
            "exercise_minutes": 30,
        }
        for column in [c for c in FEATURE_COLUMNS if c != "gender"]:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
            fill_value = medians.get(column, fallback_defaults[column])
            cleaned[column] = cleaned[column].fillna(fill_value)

        cleaned["gender"] = cleaned["gender"].fillna("Other")
        return cleaned

    @staticmethod
    def _majority_vote(predictions: dict[str, str], fallback: str) -> str:
        if not predictions:
            return fallback
        vote = Counter(predictions.values()).most_common(1)
        return vote[0][0] if vote else fallback

    def predict(self, record: dict[str, Any]) -> dict[str, Any]:
        input_df = self._sanitize_frame(pd.DataFrame([record]))
        score = compute_wellness_score(input_df.iloc[0], add_noise=False)
        score_category = categorize_wellness(score)

        if self.models_ready():
            assert self.preprocessor is not None
            X_scaled = transform_features(input_df, self.preprocessor)
            model_categories = self._predict_with_models(X_scaled)
            predicted_category = self._majority_vote(model_categories, score_category)
        else:
            model_categories = {}
            predicted_category = score_category

        recommendations = generate_recommendations(input_df.iloc[0].to_dict(), score, predicted_category)
        twin_status_color = "green" if predicted_category in ["Good", "Excellent"] else "yellow" if predicted_category == "Average" else "red"

        return {
            "input": input_df.iloc[0].to_dict(),
            "wellness_score": round(float(score), 2),
            "wellness_category": predicted_category,
            "score_based_category": score_category,
            "model_predictions": model_categories,
            "recommendations": recommendations,
            "twin_status_color": twin_status_color,
        }

    def batch_predict(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        frame = ensure_feature_frame(df)
        outputs: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            outputs.append(self.predict(row.to_dict()))
        return outputs
