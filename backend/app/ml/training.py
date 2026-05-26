from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DailyLog, FoodLog, ModelMetric, Profile
from .feature_engineering import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    build_feature_record,
    categorize_wellness,
    compute_wellness_score,
)
from .timeseries import TimeSeriesForecaster

try:
    from xgboost import XGBClassifier

    XGBOOST_AVAILABLE = True
except Exception:
    XGBOOST_AVAILABLE = False

try:
    from lightgbm import LGBMClassifier

    LIGHTGBM_AVAILABLE = True
except Exception:
    LIGHTGBM_AVAILABLE = False

try:
    from tensorflow.keras.layers import Dense, LSTM
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.utils import to_categorical

    TENSORFLOW_AVAILABLE = True
except Exception:
    TENSORFLOW_AVAILABLE = False


class WellnessModelTrainer:
    def __init__(self) -> None:
        settings.models_dir.mkdir(parents=True, exist_ok=True)
        settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.bundle_path = settings.models_dir / "wellness_platform_bundle.joblib"
        self.metrics_path = settings.artifacts_dir / "wellness_platform_model_metrics.json"
        self.classifier_lstm_path = settings.models_dir / "wellness_classifier_lstm.keras"
        self.forecast_model_path = settings.models_dir / "wellness_forecast_lstm.keras"
        self.forecast_fallback_path = settings.models_dir / "wellness_forecast_fallback.joblib"
        self.forecaster = TimeSeriesForecaster(self.forecast_model_path, self.forecast_fallback_path)

    def _generate_synthetic_dataset(self, rows: int = 5500, seed: int = 42) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        genders = np.array(["male", "female", "other"])
        food_preferences = np.array(["veg", "non-veg", "vegan"])
        diet_patterns = np.array(["balanced", "high_protein", "junk_heavy"])
        fitness_goals = np.array(["weight_loss", "muscle_gain", "maintenance"])

        df = pd.DataFrame(
            {
                "age": rng.integers(18, 75, size=rows),
                "gender": rng.choice(genders, size=rows, p=[0.47, 0.47, 0.06]),
                "height_cm": np.clip(rng.normal(168, 10, size=rows), 145, 205).round(1),
                "weight_kg": np.clip(rng.normal(72, 16, size=rows), 42, 150).round(1),
                "food_preference": rng.choice(food_preferences, size=rows, p=[0.4, 0.5, 0.1]),
                "diet_pattern": rng.choice(diet_patterns, size=rows, p=[0.55, 0.25, 0.2]),
                "fitness_goal": rng.choice(fitness_goals, size=rows, p=[0.38, 0.27, 0.35]),
                "conditions_count": rng.integers(0, 4, size=rows),
                "sleep_hours": np.clip(rng.normal(6.9, 1.2, size=rows), 3.0, 10.0).round(2),
                "daily_steps": rng.integers(800, 20000, size=rows),
                "heart_rate": rng.integers(52, 112, size=rows),
                "calories_burned": np.clip(rng.normal(2300, 520, size=rows), 1100, 4200).round(1),
                "stress_level": rng.integers(1, 11, size=rows),
                "water_intake": np.clip(rng.normal(2.3, 0.7, size=rows), 0.6, 5.5).round(2),
                "exercise_minutes": rng.integers(0, 140, size=rows),
                "protein_g": np.clip(rng.normal(78, 24, size=rows), 20, 190).round(1),
                "carbs_g": np.clip(rng.normal(230, 65, size=rows), 40, 450).round(1),
                "fats_g": np.clip(rng.normal(70, 22, size=rows), 15, 190).round(1),
            }
        )
        df["bmi"] = (df["weight_kg"] / ((df["height_cm"] / 100.0) ** 2)).round(2)
        df["activity_ratio"] = np.clip(((df["daily_steps"] / 10000.0) + (df["exercise_minutes"] / 60.0)) / 2.0, 0, 2)
        sleep_alignment = np.clip(1 - np.abs(df["sleep_hours"] - 8.0) / 5.0, 0, 1)
        stress_component = np.clip((10 - df["stress_level"]) / 10.0, 0, 1)
        df["sleep_quality_score"] = (0.7 * sleep_alignment + 0.3 * stress_component).clip(0, 1)

        noise = rng.normal(0, 4.0, size=rows)
        scores = []
        for idx, row in df.iterrows():
            score = compute_wellness_score(row.to_dict()) + float(noise[idx])
            scores.append(float(np.clip(score, 0, 100)))
        df["wellness_score"] = np.array(scores).round(2)
        df["wellness_category"] = df["wellness_score"].apply(categorize_wellness)
        return df

    def _dataset_from_db(self, db: Session) -> pd.DataFrame:
        logs = (
            db.query(DailyLog, Profile)
            .join(Profile, Profile.user_id == DailyLog.user_id)
            .order_by(DailyLog.log_date.asc())
            .all()
        )
        if not logs:
            return pd.DataFrame()

        rows: list[dict[str, Any]] = []
        for daily, profile in logs:
            macro = (
                db.query(
                    FoodLog.log_date,
                    FoodLog.user_id,
                    func.sum(FoodLog.protein_g).label("protein_g"),
                    func.sum(FoodLog.carbs_g).label("carbs_g"),
                    func.sum(FoodLog.fats_g).label("fats_g"),
                )
                .filter(FoodLog.user_id == daily.user_id, FoodLog.log_date == daily.log_date)
                .group_by(FoodLog.user_id, FoodLog.log_date)
                .first()
            )
            macro_summary = (
                {"protein_g": float(macro.protein_g), "carbs_g": float(macro.carbs_g), "fats_g": float(macro.fats_g)}
                if macro
                else {}
            )
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
            daily_payload = {
                "sleep_hours": daily.sleep_hours,
                "daily_steps": daily.daily_steps,
                "heart_rate": daily.heart_rate,
                "calories_burned": daily.calories_burned,
                "stress_level": daily.stress_level,
                "water_intake": daily.water_intake,
                "exercise_minutes": daily.exercise_minutes,
            }
            record = build_feature_record(profile_payload, daily_payload, macro_summary=macro_summary)
            score = compute_wellness_score(record)
            record["wellness_score"] = score
            record["wellness_category"] = categorize_wellness(score)
            rows.append(record)
        return pd.DataFrame(rows)

    @staticmethod
    def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
        return {
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            "precision": round(float(precision_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
            "recall": round(float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
            "f1_score": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        }

    @staticmethod
    def _to_dense(matrix: Any) -> np.ndarray:
        if sparse.issparse(matrix):
            return matrix.toarray()
        return np.asarray(matrix)

    def _preprocess(self, frame: pd.DataFrame) -> tuple[Any, LabelEncoder, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        features = frame[FEATURE_COLUMNS].copy()
        labels = frame["wellness_category"].astype(str)
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(labels)
        X_train, X_test, y_train, y_test = train_test_split(
            features,
            y,
            test_size=0.2,
            random_state=42,
            stratify=y,
        )

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "num",
                    Pipeline(
                        steps=[
                            ("imputer", SimpleImputer(strategy="median")),
                            ("scaler", StandardScaler()),
                        ]
                    ),
                    NUMERIC_FEATURES + ["conditions_count"],
                ),
                (
                    "cat",
                    Pipeline(
                        steps=[
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            ("encoder", OneHotEncoder(handle_unknown="ignore")),
                        ]
                    ),
                    CATEGORICAL_FEATURES,
                ),
            ]
        )
        X_train_transformed = preprocessor.fit_transform(X_train)
        X_test_transformed = preprocessor.transform(X_test)
        return preprocessor, label_encoder, self._to_dense(X_train_transformed), self._to_dense(X_test_transformed), y_train, y_test

    def _train_cluster_models(
        self,
        frame: pd.DataFrame,
        preprocessor: ColumnTransformer,
        y_encoded: np.ndarray,
    ) -> dict[str, Any]:
        cluster_fields = ["age", "bmi", "stress_level", "activity_ratio"]
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(frame[cluster_fields])
        transformed = self._to_dense(preprocessor.transform(frame[FEATURE_COLUMNS]))

        cluster_models: dict[int, RandomForestClassifier] = {}
        for cluster_id in sorted(set(cluster_labels)):
            idx = np.where(cluster_labels == cluster_id)[0]
            if len(idx) < 100:
                continue
            model = RandomForestClassifier(n_estimators=120, random_state=42, n_jobs=1)
            model.fit(transformed[idx], y_encoded[idx])
            cluster_models[int(cluster_id)] = model

        return {
            "kmeans": kmeans,
            "cluster_fields": cluster_fields,
            "models": cluster_models,
        }

    def _persist_metrics(self, db: Session, version: str, metrics: dict[str, Any]) -> None:
        for model_name, model_metrics in metrics.items():
            db.add(
                ModelMetric(
                    model_name=model_name,
                    version=version,
                    accuracy=model_metrics.get("accuracy"),
                    precision=model_metrics.get("precision"),
                    recall=model_metrics.get("recall"),
                    f1_score=model_metrics.get("f1_score"),
                    metadata_json=model_metrics,
                )
            )
        db.commit()

    def train(self, db: Session, rows: int = 5500) -> dict[str, Any]:
        synthetic = self._generate_synthetic_dataset(rows=rows)
        from_db = self._dataset_from_db(db)
        frame = pd.concat([synthetic, from_db], ignore_index=True) if not from_db.empty else synthetic

        preprocessor, label_encoder, X_train, X_test, y_train, y_test = self._preprocess(frame)
        models: dict[str, Any] = {}
        metrics: dict[str, Any] = {}
        notes: list[str] = []

        logistic = LogisticRegression(max_iter=2500)
        logistic.fit(X_train, y_train)
        logistic_pred = logistic.predict(X_test)
        models["logistic_regression"] = logistic
        metrics["logistic_regression"] = self._metrics(y_test, logistic_pred)

        random_forest = RandomForestClassifier(n_estimators=220, random_state=42, n_jobs=1)
        random_forest.fit(X_train, y_train)
        rf_pred = random_forest.predict(X_test)
        models["random_forest"] = random_forest
        metrics["random_forest"] = self._metrics(y_test, rf_pred)

        neural_network = MLPClassifier(hidden_layer_sizes=(128, 64), alpha=1e-4, max_iter=350, random_state=42)
        neural_network.fit(X_train, y_train)
        nn_pred = neural_network.predict(X_test)
        models["neural_network"] = neural_network
        metrics["neural_network"] = self._metrics(y_test, nn_pred)

        if XGBOOST_AVAILABLE:
            xgb = XGBClassifier(
                max_depth=6,
                n_estimators=180,
                learning_rate=0.06,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="multi:softprob",
                num_class=len(label_encoder.classes_),
                eval_metric="mlogloss",
                random_state=42,
            )
            xgb.fit(X_train, y_train)
            xgb_pred = xgb.predict(X_test)
            models["xgboost"] = xgb
            metrics["xgboost"] = self._metrics(y_test, xgb_pred)
        else:
            notes.append("xgboost is unavailable in this environment.")
            metrics["xgboost"] = {"accuracy": None, "precision": None, "recall": None, "f1_score": None, "available": False}

        if LIGHTGBM_AVAILABLE:
            lgbm = LGBMClassifier(
                n_estimators=220,
                learning_rate=0.07,
                num_leaves=40,
                random_state=42,
            )
            lgbm.fit(X_train, y_train)
            lgbm_pred = lgbm.predict(X_test)
            models["lightgbm"] = lgbm
            metrics["lightgbm"] = self._metrics(y_test, lgbm_pred)
        else:
            notes.append("lightgbm is unavailable in this environment.")
            metrics["lightgbm"] = {"accuracy": None, "precision": None, "recall": None, "f1_score": None, "available": False}

        if TENSORFLOW_AVAILABLE:
            num_classes = len(label_encoder.classes_)
            lstm_sample_limit = 2500
            if len(X_train) > lstm_sample_limit:
                sample_idx = np.random.default_rng(42).choice(len(X_train), size=lstm_sample_limit, replace=False)
                X_train_lstm_base = X_train[sample_idx]
                y_train_lstm = y_train[sample_idx]
                notes.append(f"LSTM trained on sampled subset ({lstm_sample_limit} rows) for faster iteration.")
            else:
                X_train_lstm_base = X_train
                y_train_lstm = y_train

            y_train_cat = to_categorical(y_train_lstm, num_classes=num_classes)
            X_train_lstm = X_train_lstm_base.astype(np.float32).reshape((X_train_lstm_base.shape[0], X_train_lstm_base.shape[1], 1))
            X_test_lstm = X_test.astype(np.float32).reshape((X_test.shape[0], X_test.shape[1], 1))

            lstm_classifier = Sequential(
                [
                    LSTM(48, input_shape=(X_train.shape[1], 1), return_sequences=False),
                    Dense(24, activation="relu"),
                    Dense(num_classes, activation="softmax"),
                ]
            )
            lstm_classifier.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
            history = lstm_classifier.fit(
                X_train_lstm,
                y_train_cat,
                epochs=6,
                batch_size=64,
                validation_split=0.12,
                verbose=0,
            )
            lstm_prob = lstm_classifier.predict(X_test_lstm, verbose=0)
            lstm_pred = np.argmax(lstm_prob, axis=1)
            lstm_metrics = self._metrics(y_test, lstm_pred)
            lstm_metrics["final_train_accuracy"] = round(float(history.history["accuracy"][-1]), 4)
            lstm_metrics["final_val_accuracy"] = round(float(history.history["val_accuracy"][-1]), 4)
            metrics["lstm"] = lstm_metrics
            lstm_classifier.save(self.classifier_lstm_path)
        else:
            notes.append("TensorFlow unavailable. LSTM classifier not trained.")
            metrics["lstm"] = {"accuracy": None, "precision": None, "recall": None, "f1_score": None, "available": False}

        y_full = label_encoder.transform(frame["wellness_category"].astype(str))
        clustering = self._train_cluster_models(frame, preprocessor, y_full)

        version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        bundle = {
            "version": version,
            "preprocessor": preprocessor,
            "label_encoder": label_encoder,
            "models": models,
            "feature_columns": FEATURE_COLUMNS,
            "clustered_personalization": clustering,
            "lstm_classifier_path": str(self.classifier_lstm_path),
        }
        joblib.dump(bundle, self.bundle_path)

        best_model = max(
            (
                (name, values.get("accuracy", -1.0))
                for name, values in metrics.items()
                if values.get("accuracy") is not None
            ),
            key=lambda item: item[1],
            default=("none", -1.0),
        )[0]

        forecast_training = self.forecaster.train(frame["wellness_score"].tolist())
        if not forecast_training.get("trained"):
            notes.append("LSTM forecaster skipped due to insufficient sequence data.")

        payload = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "version": version,
            "training_rows": int(len(frame)),
            "models": metrics,
            "best_model": best_model,
            "notes": notes,
        }
        with self.metrics_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        self._persist_metrics(db, version=version, metrics=metrics)
        return payload

    def load_bundle(self) -> dict[str, Any] | None:
        if not self.bundle_path.exists():
            return None
        return joblib.load(self.bundle_path)
