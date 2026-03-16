from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

try:
    from .data_processing import (
        CATEGORY_LABELS,
        DATASET_PATH,
        PROJECT_ROOT,
        generate_synthetic_dataset,
        load_dataset,
        prepare_training_data,
    )
except ImportError:  # pragma: no cover
    from data_processing import (  # type: ignore
        CATEGORY_LABELS,
        DATASET_PATH,
        PROJECT_ROOT,
        generate_synthetic_dataset,
        load_dataset,
        prepare_training_data,
    )

matplotlib.use("Agg")

try:
    from tensorflow.keras.layers import Dense, LSTM
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.utils import to_categorical

    TENSORFLOW_AVAILABLE = True
    TENSORFLOW_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - fallback for environments without tensorflow
    TENSORFLOW_AVAILABLE = False
    TENSORFLOW_IMPORT_ERROR = str(exc)

MODELS_DIR = PROJECT_ROOT / "models"
ARTIFACTS_DIR = PROJECT_ROOT / "backend" / "artifacts"

LOGISTIC_MODEL_PATH = MODELS_DIR / "logistic_regression.pkl"
RANDOM_FOREST_PATH = MODELS_DIR / "random_forest.pkl"
LSTM_PATH = MODELS_DIR / "lstm_model.h5"
PREPROCESSOR_PATH = MODELS_DIR / "preprocessor.pkl"
METRICS_PATH = ARTIFACTS_DIR / "model_metrics.json"


def _evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    matrix = confusion_matrix(y_true, y_pred, labels=list(range(len(CATEGORY_LABELS))))
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "confusion_matrix": matrix.tolist(),
    }


def _save_confusion_image(matrix: np.ndarray, title: str, output_path: Path) -> None:
    plt.figure(figsize=(6, 4))
    sns.heatmap(
        matrix,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=CATEGORY_LABELS,
        yticklabels=CATEGORY_LABELS,
    )
    plt.title(title)
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def _save_dataset_plots(df, output_dir: Path) -> None:
    corr_cols = ["age", "sleep_hours", "daily_steps", "heart_rate", "stress_level", "exercise_minutes", "wellness_score"]
    corr = df[corr_cols].corr(numeric_only=True)

    plt.figure(figsize=(8, 6))
    sns.heatmap(corr, annot=True, cmap="coolwarm", fmt=".2f", square=False)
    plt.title("Feature Correlation Heatmap")
    plt.tight_layout()
    plt.savefig(output_dir / "feature_correlation_heatmap.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 5))
    sns.histplot(df["wellness_score"], bins=25, kde=True, color="#0ea5e9")
    plt.title("Wellness Score Distribution")
    plt.xlabel("Wellness Score")
    plt.tight_layout()
    plt.savefig(output_dir / "wellness_score_distribution.png", dpi=160)
    plt.close()


def train_models(
    dataset_path: Path | None = None,
    force_generate: bool = False,
    records: int = 7000,
    random_state: int = 42,
    lstm_epochs: int = 15,
) -> dict[str, Any]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    target_dataset_path = dataset_path or DATASET_PATH
    if force_generate or not target_dataset_path.exists():
        generate_synthetic_dataset(target_dataset_path, records=records, seed=random_state)

    df = load_dataset(target_dataset_path, auto_generate=True, records=records)
    prepared = prepare_training_data(df, random_state=random_state)
    X_train = prepared["X_train"]
    X_test = prepared["X_test"]
    y_train = prepared["y_train"].to_numpy()
    y_test = prepared["y_test"].to_numpy()
    preprocessor = prepared["preprocessor"]

    joblib.dump(preprocessor, PREPROCESSOR_PATH)

    metrics: dict[str, Any] = {}
    plots: dict[str, str] = {}

    logistic = LogisticRegression(max_iter=2000, random_state=random_state)
    logistic.fit(X_train, y_train)
    logistic_pred = logistic.predict(X_test)
    logistic_metrics = _evaluate(y_test, logistic_pred)
    metrics["logistic_regression"] = logistic_metrics
    joblib.dump(logistic, LOGISTIC_MODEL_PATH)
    logistic_cm_path = ARTIFACTS_DIR / "logistic_confusion_matrix.png"
    _save_confusion_image(np.array(logistic_metrics["confusion_matrix"]), "Logistic Regression Confusion Matrix", logistic_cm_path)
    plots["logistic_confusion_matrix"] = str(logistic_cm_path)

    random_forest = RandomForestClassifier(n_estimators=100, random_state=random_state, n_jobs=1)
    random_forest.fit(X_train, y_train)
    rf_pred = random_forest.predict(X_test)
    rf_metrics = _evaluate(y_test, rf_pred)
    metrics["random_forest"] = rf_metrics
    joblib.dump(random_forest, RANDOM_FOREST_PATH)
    rf_cm_path = ARTIFACTS_DIR / "random_forest_confusion_matrix.png"
    _save_confusion_image(np.array(rf_metrics["confusion_matrix"]), "Random Forest Confusion Matrix", rf_cm_path)
    plots["random_forest_confusion_matrix"] = str(rf_cm_path)

    if TENSORFLOW_AVAILABLE:
        num_classes = len(CATEGORY_LABELS)
        y_train_cat = to_categorical(y_train, num_classes=num_classes)
        X_train_lstm = X_train.reshape((X_train.shape[0], X_train.shape[1], 1))
        X_test_lstm = X_test.reshape((X_test.shape[0], X_test.shape[1], 1))

        lstm_model = Sequential(
            [
                LSTM(48, input_shape=(X_train.shape[1], 1), return_sequences=False),
                Dense(24, activation="relu"),
                Dense(num_classes, activation="softmax"),
            ]
        )
        lstm_model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
        history = lstm_model.fit(
            X_train_lstm,
            y_train_cat,
            epochs=lstm_epochs,
            batch_size=64,
            validation_split=0.12,
            verbose=0,
        )
        lstm_prob = lstm_model.predict(X_test_lstm, verbose=0)
        lstm_pred = np.argmax(lstm_prob, axis=1)
        lstm_metrics = _evaluate(y_test, lstm_pred)
        lstm_metrics["final_train_accuracy"] = round(float(history.history["accuracy"][-1]), 4)
        lstm_metrics["final_val_accuracy"] = round(float(history.history["val_accuracy"][-1]), 4)
        metrics["lstm"] = lstm_metrics
        lstm_model.save(LSTM_PATH)

        lstm_cm_path = ARTIFACTS_DIR / "lstm_confusion_matrix.png"
        _save_confusion_image(np.array(lstm_metrics["confusion_matrix"]), "LSTM Confusion Matrix", lstm_cm_path)
        plots["lstm_confusion_matrix"] = str(lstm_cm_path)
    else:
        metrics["lstm"] = {
            "available": False,
            "error": f"TensorFlow unavailable: {TENSORFLOW_IMPORT_ERROR}",
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1_score": None,
            "confusion_matrix": None,
        }

    _save_dataset_plots(df.fillna(df.median(numeric_only=True)), ARTIFACTS_DIR)
    plots["feature_correlation_heatmap"] = str(ARTIFACTS_DIR / "feature_correlation_heatmap.png")
    plots["wellness_score_distribution"] = str(ARTIFACTS_DIR / "wellness_score_distribution.png")

    available_models = {
        name: values
        for name, values in metrics.items()
        if values.get("accuracy") is not None
    }
    best_model = max(available_models, key=lambda k: available_models[k]["accuracy"]) if available_models else "none"

    payload = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(target_dataset_path),
        "records_used": int(len(df)),
        "metrics": metrics,
        "best_model": best_model,
        "artifacts": plots,
    }
    with METRICS_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Human Digital Twin wellness models.")
    parser.add_argument("--dataset", type=str, default=None, help="Path to CSV/XLSX dataset.")
    parser.add_argument("--records", type=int, default=7000, help="Synthetic dataset size if generated.")
    parser.add_argument("--force-generate", action="store_true", help="Generate synthetic dataset before training.")
    parser.add_argument("--lstm-epochs", type=int, default=15, help="Epoch count for LSTM training.")
    args = parser.parse_args()

    dataset_path = Path(args.dataset) if args.dataset else None
    results = train_models(
        dataset_path=dataset_path,
        force_generate=args.force_generate,
        records=args.records,
        lstm_epochs=args.lstm_epochs,
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
