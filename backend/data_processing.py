from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "dataset" / "wellness_dataset.csv"

FEATURE_COLUMNS = [
    "age",
    "gender",
    "sleep_hours",
    "daily_steps",
    "heart_rate",
    "calories_burned",
    "stress_level",
    "water_intake",
    "exercise_minutes",
]

TARGET_COLUMN = "wellness_score"
CATEGORY_LABELS = ["Poor", "Average", "Good", "Excellent"]

_COLUMN_ALIASES = {
    "age": "age",
    "gender": "gender",
    "sleep_hours": "sleep_hours",
    "sleep hours": "sleep_hours",
    "daily_steps": "daily_steps",
    "daily steps": "daily_steps",
    "heart_rate": "heart_rate",
    "heart rate": "heart_rate",
    "calories_burned": "calories_burned",
    "calories burned": "calories_burned",
    "stress_level": "stress_level",
    "stress level": "stress_level",
    "water_intake": "water_intake",
    "water intake": "water_intake",
    "exercise_minutes": "exercise_minutes",
    "exercise minutes": "exercise_minutes",
    "wellness_score": "wellness_score",
    "wellness score": "wellness_score",
}


@dataclass
class Preprocessor:
    feature_columns: list[str]
    numeric_columns: list[str]
    gender_map: dict[str, int]
    gender_default: int
    numeric_medians: dict[str, float]
    scaler: StandardScaler
    category_map: dict[str, int]
    category_inverse_map: dict[int, str]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for column in df.columns:
        canonical = _COLUMN_ALIASES.get(str(column).strip().lower(), str(column).strip().lower())
        renamed[column] = canonical
    return df.rename(columns=renamed)


def _normalize_gender(value: Any) -> str:
    if pd.isna(value):
        return "Other"
    text = str(value).strip().lower()
    if text.startswith("m"):
        return "Male"
    if text.startswith("f"):
        return "Female"
    return "Other"


def categorize_wellness(score: float) -> str:
    if score < 40:
        return "Poor"
    if score < 60:
        return "Average"
    if score < 80:
        return "Good"
    return "Excellent"


def compute_wellness_score(record: dict[str, Any] | pd.Series, add_noise: bool = False) -> float:
    row = dict(record)
    sleep = np.clip(float(row["sleep_hours"]) / 8.0, 0, 1)
    steps = np.clip((float(row["daily_steps"]) - 1000) / 11000, 0, 1)
    heart = np.clip(1 - abs(float(row["heart_rate"]) - 70) / 40, 0, 1)
    calories = np.clip((float(row["calories_burned"]) - 1400) / 1800, 0, 1)
    stress_inverse = np.clip(1 - (float(row["stress_level"]) - 1) / 9, 0, 1)
    water = np.clip(float(row["water_intake"]) / 3.5, 0, 1)
    exercise = np.clip(float(row["exercise_minutes"]) / 60, 0, 1)
    age_factor = np.clip(1 - max(float(row["age"]) - 25, 0) / 70, 0.35, 1.0)

    weighted = (
        0.16 * sleep
        + 0.16 * steps
        + 0.1 * heart
        + 0.1 * calories
        + 0.18 * stress_inverse
        + 0.12 * water
        + 0.14 * exercise
        + 0.04 * age_factor
    )
    noise = np.random.normal(0, 4.0) if add_noise else 0.0
    return float(np.clip(weighted * 100 + noise, 0, 100))


def generate_synthetic_dataset(
    output_path: Path = DATASET_PATH, records: int = 7000, seed: int = 42
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "age": rng.integers(18, 75, size=records),
            "gender": rng.choice(["Male", "Female", "Other"], p=[0.47, 0.47, 0.06], size=records),
            "sleep_hours": np.clip(rng.normal(6.8, 1.3, size=records), 3.5, 10.0).round(1),
            "daily_steps": rng.integers(1200, 18000, size=records),
            "heart_rate": rng.integers(52, 110, size=records),
            "calories_burned": rng.integers(1400, 3600, size=records),
            "stress_level": rng.integers(1, 11, size=records),
            "water_intake": np.clip(rng.normal(2.1, 0.7, size=records), 0.7, 5.0).round(2),
            "exercise_minutes": rng.integers(0, 130, size=records),
        }
    )
    df[TARGET_COLUMN] = df.apply(lambda r: compute_wellness_score(r, add_noise=True), axis=1).round(2)

    # Inject sparse missing values so preprocessing has realistic behavior.
    for col in FEATURE_COLUMNS:
        missing_count = max(1, records // 80)  # ~1.25%
        idx = rng.choice(df.index, size=missing_count, replace=False)
        df.loc[idx, col] = np.nan

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


def load_dataset(path: Path | None = None, auto_generate: bool = True, records: int = 7000) -> pd.DataFrame:
    data_path = path or DATASET_PATH
    if not data_path.exists():
        if not auto_generate:
            raise FileNotFoundError(f"Dataset not found at {data_path}")
        generate_synthetic_dataset(data_path, records=records)

    if data_path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path)

    df = normalize_columns(df)
    missing = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required dataset columns: {missing}")
    return df


def ensure_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = normalize_columns(df.copy())
    missing = [c for c in FEATURE_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {missing}")
    return frame[FEATURE_COLUMNS].copy()


def _prepare_base_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], dict[str, float]]:
    frame = ensure_feature_frame(df)
    frame["gender"] = frame["gender"].apply(_normalize_gender)
    numeric_columns = [c for c in FEATURE_COLUMNS if c != "gender"]
    numeric_medians: dict[str, float] = {}

    for col in numeric_columns:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
        median_val = float(frame[col].median()) if not np.isnan(frame[col].median()) else 0.0
        numeric_medians[col] = median_val
        frame[col] = frame[col].fillna(median_val)

    mode_gender = frame["gender"].mode()
    default_gender = mode_gender.iloc[0] if not mode_gender.empty else "Other"
    frame["gender"] = frame["gender"].fillna(default_gender)
    return frame, numeric_columns, numeric_medians


def prepare_training_data(
    df: pd.DataFrame,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    frame, numeric_columns, numeric_medians = _prepare_base_features(df)
    frame[TARGET_COLUMN] = pd.to_numeric(df[TARGET_COLUMN], errors="coerce")
    score_median = float(frame[TARGET_COLUMN].median())
    frame[TARGET_COLUMN] = frame[TARGET_COLUMN].fillna(score_median).clip(0, 100)
    frame["wellness_category"] = frame[TARGET_COLUMN].apply(categorize_wellness)

    categories = CATEGORY_LABELS.copy()
    category_map = {label: idx for idx, label in enumerate(categories)}
    inverse_category_map = {idx: label for label, idx in category_map.items()}

    gender_values = sorted(frame["gender"].unique().tolist())
    if "Other" not in gender_values:
        gender_values.append("Other")
    gender_map = {value: idx for idx, value in enumerate(gender_values)}
    frame["gender"] = frame["gender"].map(lambda g: gender_map.get(g, gender_map["Other"]))

    X = frame[FEATURE_COLUMNS].copy()
    y = frame["wellness_category"].map(category_map).astype(int)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    preprocessor = Preprocessor(
        feature_columns=FEATURE_COLUMNS,
        numeric_columns=numeric_columns,
        gender_map=gender_map,
        gender_default=gender_map.get("Other", 0),
        numeric_medians=numeric_medians,
        scaler=scaler,
        category_map=category_map,
        category_inverse_map=inverse_category_map,
    )

    return {
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "preprocessor": preprocessor,
        "dataframe": frame,
    }


def transform_features(df: pd.DataFrame, preprocessor: Preprocessor) -> np.ndarray:
    frame = ensure_feature_frame(df)
    frame["gender"] = frame["gender"].apply(_normalize_gender)

    for col in preprocessor.numeric_columns:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame[col] = frame[col].fillna(preprocessor.numeric_medians[col])

    frame["gender"] = frame["gender"].map(lambda g: preprocessor.gender_map.get(g, preprocessor.gender_default))
    return preprocessor.scaler.transform(frame[preprocessor.feature_columns])
