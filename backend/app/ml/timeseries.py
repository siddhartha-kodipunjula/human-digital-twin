from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

try:
    from tensorflow.keras.layers import Dense, LSTM
    from tensorflow.keras.models import Sequential, load_model

    TENSORFLOW_AVAILABLE = True
except Exception:
    TENSORFLOW_AVAILABLE = False


@dataclass
class ForecastArtifacts:
    sequence_length: int = 7
    horizon: int = 7


class TimeSeriesForecaster:
    def __init__(self, model_path: Path, fallback_path: Path, config: ForecastArtifacts | None = None) -> None:
        self.model_path = model_path
        self.fallback_path = fallback_path
        self.config = config or ForecastArtifacts()
        self.model = None
        self.fallback = None
        self._load()

    def _load(self) -> None:
        if TENSORFLOW_AVAILABLE and self.model_path.exists():
            self.model = load_model(self.model_path)
        if self.fallback_path.exists():
            self.fallback = joblib.load(self.fallback_path)

    def train(self, scores: list[float]) -> dict:
        values = np.array(scores, dtype=float)
        if len(values) < self.config.sequence_length + 5:
            return {"trained": False, "reason": "not_enough_data"}

        X, y = [], []
        for idx in range(len(values) - self.config.sequence_length):
            X.append(values[idx : idx + self.config.sequence_length])
            y.append(values[idx + self.config.sequence_length])
        X_arr = np.array(X)
        y_arr = np.array(y)

        if TENSORFLOW_AVAILABLE:
            model = Sequential(
                [
                    LSTM(32, input_shape=(self.config.sequence_length, 1), return_sequences=False),
                    Dense(16, activation="relu"),
                    Dense(1, activation="linear"),
                ]
            )
            model.compile(optimizer="adam", loss="mse")
            model.fit(
                X_arr.reshape((X_arr.shape[0], X_arr.shape[1], 1)),
                y_arr,
                epochs=12,
                batch_size=32,
                verbose=0,
            )
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            model.save(self.model_path)
            self.model = model
            return {"trained": True, "backend": "tensorflow_lstm"}

        # Fallback trend model: simple weighted moving average parameters.
        weighted = {"weights": [0.12, 0.13, 0.14, 0.15, 0.15, 0.15, 0.16]}
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(weighted, self.fallback_path)
        self.fallback = weighted
        return {"trained": True, "backend": "weighted_average"}

    def forecast(self, history_scores: list[float], days: int = 7) -> list[float]:
        if not history_scores:
            return [55.0 for _ in range(days)]

        seq_len = self.config.sequence_length
        history = [float(v) for v in history_scores]
        while len(history) < seq_len:
            history.insert(0, history[0])

        forecast: list[float] = []
        for _ in range(days):
            window = np.array(history[-seq_len:], dtype=float)
            if self.model is not None and TENSORFLOW_AVAILABLE:
                pred = float(
                    self.model.predict(window.reshape((1, seq_len, 1)), verbose=0)[0][0]
                )
            else:
                weights = (
                    np.array(self.fallback.get("weights"))
                    if isinstance(self.fallback, dict)
                    else np.array([0.12, 0.13, 0.14, 0.15, 0.15, 0.15, 0.16])
                )
                pred = float(np.dot(window, weights))
            pred = float(np.clip(pred, 0, 100))
            forecast.append(round(pred, 2))
            history.append(pred)
        return forecast
