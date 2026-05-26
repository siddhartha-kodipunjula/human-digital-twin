from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from .feature_engineering import categorize_wellness, compute_wellness_score, risk_level_from_score, to_dataframe
from .training import WellnessModelTrainer

try:
    from tensorflow.keras.models import load_model

    TENSORFLOW_AVAILABLE = True
except Exception:
    TENSORFLOW_AVAILABLE = False


class WellnessPredictionEngine:
    def __init__(self) -> None:
        self.trainer = WellnessModelTrainer()
        self.bundle: dict[str, Any] | None = self.trainer.load_bundle()
        self.lstm_classifier = self._load_lstm_classifier()

    def _load_lstm_classifier(self):
        if not TENSORFLOW_AVAILABLE:
            return None
        path = getattr(self.trainer, "classifier_lstm_path", None)
        if path is None or not path.exists():
            return None
        try:
            return load_model(path)
        except Exception:
            return None

    def ensure_models(self, db: Session) -> None:
        if self.bundle is None:
            self.trainer.train(db)
            self.bundle = self.trainer.load_bundle()
            self.lstm_classifier = self._load_lstm_classifier()

    def retrain(self, db: Session, rows: int = 5500) -> dict[str, Any]:
        result = self.trainer.train(db, rows=rows)
        self.bundle = self.trainer.load_bundle()
        self.lstm_classifier = self._load_lstm_classifier()
        return result

    def _predict_model_outputs(self, transformed: np.ndarray) -> dict[str, Any]:
        assert self.bundle is not None
        label_encoder = self.bundle["label_encoder"]
        models: dict[str, Any] = self.bundle["models"]

        probabilities: list[np.ndarray] = []
        per_model: dict[str, Any] = {}
        for name, model in models.items():
            proba = model.predict_proba(transformed)[0]
            pred_index = int(np.argmax(proba))
            pred_label = str(label_encoder.inverse_transform([pred_index])[0])
            per_model[name] = {
                "label": pred_label,
                "confidence": round(float(np.max(proba)), 4),
                "probabilities": {
                    str(label_encoder.inverse_transform([idx])[0]): round(float(prob), 4)
                    for idx, prob in enumerate(proba.tolist())
                },
            }
            probabilities.append(proba)

        if self.lstm_classifier is not None:
            lstm_input = transformed.astype(np.float32).reshape((transformed.shape[0], transformed.shape[1], 1))
            lstm_proba = np.asarray(self.lstm_classifier.predict(lstm_input, verbose=0))[0]
            lstm_idx = int(np.argmax(lstm_proba))
            lstm_label = str(label_encoder.inverse_transform([lstm_idx])[0])
            per_model["lstm"] = {
                "label": lstm_label,
                "confidence": round(float(np.max(lstm_proba)), 4),
                "probabilities": {
                    str(label_encoder.inverse_transform([idx])[0]): round(float(prob), 4)
                    for idx, prob in enumerate(lstm_proba.tolist())
                },
            }
            probabilities.append(lstm_proba)

        stacked = np.vstack(probabilities) if probabilities else np.zeros((1, len(label_encoder.classes_)))
        ensemble = np.mean(stacked, axis=0)
        winner_idx = int(np.argmax(ensemble))
        winner_label = str(label_encoder.inverse_transform([winner_idx])[0])
        per_model["ensemble"] = {
            "label": winner_label,
            "confidence": round(float(np.max(ensemble)), 4),
            "probabilities": {
                str(label_encoder.inverse_transform([idx])[0]): round(float(prob), 4)
                for idx, prob in enumerate(ensemble.tolist())
            },
        }
        return per_model

    def _apply_cluster_personalization(self, transformed: np.ndarray, raw_record: dict[str, Any]) -> dict[str, Any]:
        assert self.bundle is not None
        clustering = self.bundle.get("clustered_personalization", {})
        kmeans = clustering.get("kmeans")
        cluster_models = clustering.get("models", {})
        cluster_fields = clustering.get("cluster_fields", [])
        if not kmeans or not cluster_models:
            return {}

        cluster_input = np.array([[float(raw_record[field]) for field in cluster_fields]])
        cluster_id = int(kmeans.predict(cluster_input)[0])
        model = cluster_models.get(cluster_id)
        if model is None:
            return {"cluster_id": cluster_id, "label": None}

        label_encoder = self.bundle["label_encoder"]
        pred_idx = int(model.predict(transformed)[0])
        pred_label = str(label_encoder.inverse_transform([pred_idx])[0])
        return {"cluster_id": cluster_id, "label": pred_label}

    @staticmethod
    def _category_anchor_score(category: str) -> float:
        anchors = {"Poor": 35.0, "Average": 55.0, "Good": 75.0, "Excellent": 90.0}
        return anchors.get(category, 60.0)

    def predict(self, db: Session, feature_record: dict[str, Any]) -> dict[str, Any]:
        self.ensure_models(db)
        assert self.bundle is not None

        frame = to_dataframe([feature_record])
        preprocessor = self.bundle["preprocessor"]
        transformed = preprocessor.transform(frame)
        if hasattr(transformed, "toarray"):
            transformed = transformed.toarray()
        transformed = np.asarray(transformed)

        model_outputs = self._predict_model_outputs(transformed)
        personalized = self._apply_cluster_personalization(transformed, feature_record)
        if personalized:
            model_outputs["clustered_personalization"] = personalized

        ensemble_label = model_outputs["ensemble"]["label"]
        ensemble_confidence = float(model_outputs["ensemble"]["confidence"])
        base_score = compute_wellness_score(feature_record)
        anchor = self._category_anchor_score(ensemble_label)

        final_score = np.clip((0.55 * base_score) + (0.45 * anchor), 0, 100)
        if personalized.get("label") and personalized["label"] == ensemble_label:
            final_score = np.clip(final_score + 1.2, 0, 100)
        final_category = categorize_wellness(float(final_score))
        risk_level = risk_level_from_score(float(final_score))

        model_outputs["confidence"] = round(ensemble_confidence, 4)
        return {
            "wellness_score": round(float(final_score), 2),
            "wellness_category": final_category,
            "risk_level": risk_level,
            "model_outputs": model_outputs,
            "base_score": round(float(base_score), 2),
        }

    def forecast(self, history_scores: list[float], days: int = 7) -> list[dict[str, Any]]:
        forecast_scores = self.trainer.forecaster.forecast(history_scores, days=days)
        output = []
        for idx, score in enumerate(forecast_scores, start=1):
            target = date.today() + timedelta(days=idx)
            output.append(
                {
                    "day_offset": idx,
                    "target_date": target,
                    "forecast_score": round(float(score), 2),
                    "forecast_category": categorize_wellness(float(score)),
                }
            )
        return output
