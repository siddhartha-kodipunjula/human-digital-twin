from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .data_processing import PROJECT_ROOT
except ImportError:  # pragma: no cover
    from data_processing import PROJECT_ROOT  # type: ignore

DB_PATH = PROJECT_ROOT / "backend" / "wellness.db"


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                input_json TEXT NOT NULL,
                wellness_score REAL NOT NULL,
                wellness_category TEXT NOT NULL,
                score_based_category TEXT NOT NULL,
                model_predictions_json TEXT,
                recommendations_json TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trained_at TEXT NOT NULL,
                model_name TEXT NOT NULL,
                accuracy REAL,
                precision REAL,
                recall REAL,
                f1_score REAL,
                confusion_matrix_json TEXT,
                notes TEXT
            )
            """
        )
        connection.commit()


def save_prediction(prediction: dict[str, Any], source: str = "manual") -> None:
    init_db()
    with _get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO prediction_history (
                created_at, source, input_json, wellness_score, wellness_category,
                score_based_category, model_predictions_json, recommendations_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                source,
                json.dumps(prediction.get("input", {})),
                float(prediction.get("wellness_score", 0.0)),
                prediction.get("wellness_category", "Unknown"),
                prediction.get("score_based_category", "Unknown"),
                json.dumps(prediction.get("model_predictions", {})),
                json.dumps(prediction.get("recommendations", [])),
            ),
        )
        connection.commit()


def get_prediction_history(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with _get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT *
            FROM prediction_history
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()

    history = []
    for row in rows:
        history.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "source": row["source"],
                "input": json.loads(row["input_json"]),
                "wellness_score": row["wellness_score"],
                "wellness_category": row["wellness_category"],
                "score_based_category": row["score_based_category"],
                "model_predictions": json.loads(row["model_predictions_json"] or "{}"),
                "recommendations": json.loads(row["recommendations_json"] or "[]"),
            }
        )
    return history


def save_model_performance(training_payload: dict[str, Any]) -> None:
    init_db()
    trained_at = training_payload.get("trained_at", datetime.now(timezone.utc).isoformat())
    metrics = training_payload.get("metrics", {})
    with _get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM model_performance")
        for model_name, values in metrics.items():
            cursor.execute(
                """
                INSERT INTO model_performance (
                    trained_at, model_name, accuracy, precision, recall, f1_score, confusion_matrix_json, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trained_at,
                    model_name,
                    values.get("accuracy"),
                    values.get("precision"),
                    values.get("recall"),
                    values.get("f1_score"),
                    json.dumps(values.get("confusion_matrix")),
                    values.get("error"),
                ),
            )
        connection.commit()


def get_model_performance() -> list[dict[str, Any]]:
    init_db()
    with _get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT *
            FROM model_performance
            ORDER BY accuracy DESC NULLS LAST, model_name ASC
            """
        )
        rows = cursor.fetchall()

    output = []
    for row in rows:
        output.append(
            {
                "trained_at": row["trained_at"],
                "model_name": row["model_name"],
                "accuracy": row["accuracy"],
                "precision": row["precision"],
                "recall": row["recall"],
                "f1_score": row["f1_score"],
                "confusion_matrix": json.loads(row["confusion_matrix_json"]) if row["confusion_matrix_json"] else None,
                "notes": row["notes"],
            }
        )
    return output
