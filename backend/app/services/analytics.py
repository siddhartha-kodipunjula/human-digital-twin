from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..ml.feature_engineering import risk_level_from_score
from ..models import Prediction


def _prediction_frame(db: Session, user_id: str, days: int = 120) -> pd.DataFrame:
    since_date = date.today() - timedelta(days=days)
    rows = (
        db.query(Prediction)
        .filter(Prediction.user_id == user_id, Prediction.log_date >= since_date)
        .order_by(Prediction.log_date.asc())
        .all()
    )
    if not rows:
        return pd.DataFrame(columns=["log_date", "wellness_score", "sleep_hours", "exercise_minutes", "daily_steps"])

    payload = []
    for row in rows:
        snapshot = row.input_snapshot or {}
        payload.append(
            {
                "log_date": row.log_date,
                "wellness_score": float(row.wellness_score),
                "sleep_hours": float(snapshot.get("sleep_hours", np.nan)),
                "exercise_minutes": float(snapshot.get("exercise_minutes", np.nan)),
                "daily_steps": float(snapshot.get("daily_steps", np.nan)),
                "stress_level": float(snapshot.get("stress_level", np.nan)),
            }
        )
    frame = pd.DataFrame(payload)
    if not frame.empty:
        frame["log_date"] = pd.to_datetime(frame["log_date"], errors="coerce")
        frame = frame.dropna(subset=["log_date"]).sort_values("log_date")
    return frame


def _trend_points(frame: pd.DataFrame, freq: str) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    indexed = frame.set_index("log_date")
    if not isinstance(indexed.index, pd.DatetimeIndex):
        indexed.index = pd.to_datetime(indexed.index, errors="coerce")
        indexed = indexed[~indexed.index.isna()]
    grouped = indexed.resample(freq)["wellness_score"].mean().dropna().reset_index()
    return [
        {"period_start": row.log_date.date(), "average_score": round(float(row.wellness_score), 2)}
        for row in grouped.itertuples(index=False)
    ]


def _detect_anomalies(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if len(frame) < 8:
        return []
    scores = frame["wellness_score"].to_numpy(dtype=float)
    mean = float(scores.mean())
    std = float(scores.std())
    if std == 0:
        return []

    anomalies = []
    for row in frame.itertuples(index=False):
        z_score = (float(row.wellness_score) - mean) / std
        if z_score <= -1.8:
            anomalies.append(
                {
                    "date": row.log_date.date() if hasattr(row.log_date, "date") else row.log_date,
                    "score": round(float(row.wellness_score), 2),
                    "z_score": round(float(z_score), 2),
                    "reason": "Sudden wellness drop detected.",
                }
            )
    return anomalies


def _habit_impact(frame: pd.DataFrame) -> dict[str, float]:
    if len(frame) < 6:
        return {"sleep_impact_percent": 0.0, "exercise_impact_percent": 0.0, "steps_impact_percent": 0.0}

    correlations = {}
    for feature in ["sleep_hours", "exercise_minutes", "daily_steps", "stress_level"]:
        corr = frame[[feature, "wellness_score"]].corr(numeric_only=True).iloc[0, 1]
        if pd.isna(corr):
            corr = 0.0
        correlations[feature] = abs(float(corr))

    total = sum(correlations.values()) or 1.0
    impacts = {key: round((value / total) * 100, 2) for key, value in correlations.items()}
    return {
        "sleep_impact_percent": impacts["sleep_hours"],
        "exercise_impact_percent": impacts["exercise_minutes"],
        "steps_impact_percent": impacts["daily_steps"],
        "stress_impact_percent": impacts["stress_level"],
    }


def dashboard_overview(db: Session, user_id: str, forecast_points: list[dict[str, Any]]) -> dict[str, Any]:
    frame = _prediction_frame(db, user_id=user_id, days=180)
    latest = (
        db.query(Prediction)
        .filter(Prediction.user_id == user_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )

    current_score = float(latest.wellness_score) if latest else 0.0
    forecast_avg = (
        float(np.mean([point["forecast_score"] for point in forecast_points]))
        if forecast_points
        else current_score
    )

    return {
        "current_state": {
            "score": round(current_score, 2),
            "category": latest.wellness_category if latest else "Unknown",
            "risk_level": latest.risk_level if latest else "high",
            "as_of": latest.created_at if latest else None,
        },
        "predicted_state": {
            "next_7d_average_score": round(forecast_avg, 2),
            "projected_risk_level": risk_level_from_score(forecast_avg),
            "forecast_points": forecast_points,
        },
        "weekly_trend": _trend_points(frame, freq="W-MON"),
        "monthly_trend": _trend_points(frame, freq="MS"),
        "anomalies": _detect_anomalies(frame),
        "habit_impact": _habit_impact(frame),
    }
