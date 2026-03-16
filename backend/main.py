from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from .data_processing import (
        DATASET_PATH,
        FEATURE_COLUMNS,
        PROJECT_ROOT,
        ensure_feature_frame,
        generate_synthetic_dataset,
        normalize_columns,
    )
    from .database import get_model_performance, get_prediction_history, init_db, save_model_performance, save_prediction
    from .model_training import ARTIFACTS_DIR, METRICS_PATH, train_models
    from .prediction_engine import PredictionEngine
except ImportError:  # pragma: no cover
    from data_processing import (  # type: ignore
        DATASET_PATH,
        FEATURE_COLUMNS,
        PROJECT_ROOT,
        ensure_feature_frame,
        generate_synthetic_dataset,
        normalize_columns,
    )
    from database import get_model_performance, get_prediction_history, init_db, save_model_performance, save_prediction  # type: ignore
    from model_training import ARTIFACTS_DIR, METRICS_PATH, train_models  # type: ignore
    from prediction_engine import PredictionEngine  # type: ignore

app = FastAPI(
    title="Human Digital Twin For Personal Wellness Optimization",
    version="1.0.0",
    description="Predict and visualize personal wellness using ML-driven digital twin modeling.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=ARTIFACTS_DIR), name="artifacts")

engine = PredictionEngine()


class HealthInput(BaseModel):
    age: int = Field(..., ge=10, le=100)
    gender: str = Field(..., min_length=1)
    sleep_hours: float = Field(..., ge=0, le=24)
    daily_steps: int = Field(..., ge=0, le=50000)
    heart_rate: int = Field(..., ge=30, le=220)
    calories_burned: int = Field(..., ge=500, le=10000)
    stress_level: int = Field(..., ge=1, le=10)
    water_intake: float = Field(..., ge=0, le=10)
    exercise_minutes: int = Field(..., ge=0, le=600)


class TrainModelRequest(BaseModel):
    dataset_path: str | None = None
    force_generate: bool = False
    records: int = Field(7000, ge=500, le=20000)
    lstm_epochs: int = Field(15, ge=5, le=100)


@app.on_event("startup")
def startup() -> None:
    init_db()
    if not DATASET_PATH.exists():
        generate_synthetic_dataset(DATASET_PATH, records=7000)


def _resolve_dataset_path(dataset_path: str | None) -> Path | None:
    if not dataset_path:
        return None
    candidate = Path(dataset_path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / "dataset" / candidate


def _ensure_trained_models() -> None:
    if engine.models_ready():
        return
    payload = train_models(dataset_path=DATASET_PATH, force_generate=False, records=7000, lstm_epochs=15)
    save_model_performance(payload)
    engine.reload_models()


def _load_uploaded_dataframe(upload: UploadFile, payload: bytes) -> pd.DataFrame:
    name = (upload.filename or "").lower()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(payload))
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(payload))
    raise HTTPException(status_code=400, detail="Unsupported file type. Upload CSV or Excel.")


def _dataset_insights(df: pd.DataFrame) -> dict[str, Any]:
    numeric = df.select_dtypes(include="number")
    correlations = {}
    if not numeric.empty:
        correlations = numeric.corr().fillna(0).round(3).to_dict()

    category_counts = (
        df["predicted_wellness_category"].value_counts().to_dict()
        if "predicted_wellness_category" in df.columns
        else {}
    )
    return {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "missing_values": df.isna().sum().to_dict(),
        "category_distribution": category_counts,
        "correlations": correlations,
        "score_summary": {
            "mean": round(float(df["predicted_wellness_score"].mean()), 2),
            "min": round(float(df["predicted_wellness_score"].min()), 2),
            "max": round(float(df["predicted_wellness_score"].max()), 2),
        }
        if "predicted_wellness_score" in df.columns
        else {},
    }


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "message": "Human Digital Twin backend is running",
        "docs": "/docs",
        "dataset_path": str(DATASET_PATH),
    }


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {"status": "ok", "models_ready": engine.models_ready()}


@app.post("/predict")
def predict(input_data: HealthInput) -> dict[str, Any]:
    _ensure_trained_models()
    prediction = engine.predict(input_data.model_dump())
    save_prediction(prediction, source="manual")
    return prediction


@app.post("/upload-data")
async def upload_data(file: UploadFile = File(...)) -> dict[str, Any]:
    _ensure_trained_models()
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    raw_df = _load_uploaded_dataframe(file, payload)
    raw_df = normalize_columns(raw_df)
    feature_df = ensure_feature_frame(raw_df)
    predictions = engine.batch_predict(feature_df)

    enriched = feature_df.copy()
    enriched["predicted_wellness_score"] = [p["wellness_score"] for p in predictions]
    enriched["predicted_wellness_category"] = [p["wellness_category"] for p in predictions]

    for item in predictions:
        save_prediction(item, source="upload")

    preview = enriched.head(250).to_dict(orient="records")
    chart_data = [
        {
            "sleep_hours": row["sleep_hours"],
            "stress_level": row["stress_level"],
            "daily_steps": row["daily_steps"],
            "heart_rate": row["heart_rate"],
            "wellness_score": row["predicted_wellness_score"],
            "wellness_category": row["predicted_wellness_category"],
        }
        for _, row in enriched.head(600).iterrows()
    ]

    return {
        "filename": file.filename,
        "processed_records": len(predictions),
        "insights": _dataset_insights(enriched),
        "preview_records": preview,
        "chart_data": chart_data,
    }


@app.post("/train-model")
def train_model(request: TrainModelRequest) -> dict[str, Any]:
    dataset_path = _resolve_dataset_path(request.dataset_path)
    result = train_models(
        dataset_path=dataset_path,
        force_generate=request.force_generate,
        records=request.records,
        lstm_epochs=request.lstm_epochs,
    )
    save_model_performance(result)
    engine.reload_models()
    return result


@app.get("/model-performance")
def model_performance() -> dict[str, Any]:
    db_metrics = get_model_performance()
    file_payload: dict[str, Any] = {}
    if METRICS_PATH.exists():
        with METRICS_PATH.open("r", encoding="utf-8") as file:
            file_payload = json.load(file)
    return {
        "performance": db_metrics,
        "latest_training_payload": file_payload,
    }


@app.get("/prediction-history")
def prediction_history(limit: int = Query(100, ge=1, le=1000)) -> dict[str, Any]:
    history = get_prediction_history(limit=limit)
    average_score = round(
        float(sum(item["wellness_score"] for item in history) / len(history)), 2
    ) if history else 0.0
    return {
        "count": len(history),
        "average_score": average_score,
        "history": history,
    }
