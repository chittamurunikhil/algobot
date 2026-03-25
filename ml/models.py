"""
ML Model Wrappers — XGBoost, Random Forest, and LSTM for price direction prediction.
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional
import pickle
import os


class BaseModel:
    """Abstract base for ML models."""

    def __init__(self, name: str):
        self.name = name
        self.model = None
        self.is_trained = False

    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        raise NotImplementedError

    def predict(self, X: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.model, f)

    def load(self, path: str):
        with open(path, "rb") as f:
            self.model = pickle.load(f)
        self.is_trained = True


class XGBoostModel(BaseModel):
    """XGBoost classifier for price direction prediction."""

    def __init__(self):
        super().__init__("XGBoost")

    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        try:
            from xgboost import XGBClassifier
            self.model = XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                eval_metric="logloss",
            )
            self.model.fit(X_train, y_train)
            self.is_trained = True
        except ImportError:
            print("XGBoost not installed. Run: pip install xgboost")

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            return np.zeros(len(X))
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            return np.full((len(X), 2), 0.5)
        return self.model.predict_proba(X)


class RandomForestModel(BaseModel):
    """Random Forest classifier."""

    def __init__(self):
        super().__init__("RandomForest")

    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        from sklearn.ensemble import RandomForestClassifier
        self.model = RandomForestClassifier(
            n_estimators=150,
            max_depth=8,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train, y_train)
        self.is_trained = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            return np.zeros(len(X))
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            return np.full((len(X), 2), 0.5)
        return self.model.predict_proba(X)


class LSTMModel(BaseModel):
    """LSTM neural network for sequence-based prediction."""

    def __init__(self, sequence_length: int = 20):
        super().__init__("LSTM")
        self.sequence_length = sequence_length

    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        try:
            import tensorflow as tf
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout

            # Reshape for LSTM: (samples, timesteps, features)
            X_seq, y_seq = self._create_sequences(X_train, y_train)

            self.model = Sequential([
                LSTM(64, return_sequences=True, input_shape=(X_seq.shape[1], X_seq.shape[2])),
                Dropout(0.2),
                LSTM(32, return_sequences=False),
                Dropout(0.2),
                Dense(16, activation="relu"),
                Dense(1, activation="sigmoid"),
            ])

            self.model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
            self.model.fit(X_seq, y_seq, epochs=20, batch_size=32, verbose=0, validation_split=0.1)
            self.is_trained = True
        except ImportError:
            print("TensorFlow not installed. Run: pip install tensorflow")

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            return np.zeros(max(0, len(X) - self.sequence_length + 1))
        X_seq = self._create_prediction_sequences(X)
        preds = self.model.predict(X_seq, verbose=0)
        return (preds.flatten() > 0.5).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            n = max(0, len(X) - self.sequence_length + 1)
            return np.full((n, 2), 0.5)
        X_seq = self._create_prediction_sequences(X)
        preds = self.model.predict(X_seq, verbose=0).flatten()
        return np.column_stack([1 - preds, preds])

    def _create_sequences(self, X: np.ndarray, y: np.ndarray):
        X_seq, y_seq = [], []
        for i in range(self.sequence_length, len(X)):
            X_seq.append(X[i - self.sequence_length:i])
            y_seq.append(y[i])
        return np.array(X_seq), np.array(y_seq)

    def _create_prediction_sequences(self, X: np.ndarray):
        X_seq = []
        for i in range(self.sequence_length, len(X) + 1):
            X_seq.append(X[i - self.sequence_length:i])
        return np.array(X_seq) if X_seq else np.empty((0, self.sequence_length, X.shape[1]))

    def save(self, path: str):
        if self.model:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.model.save(path)

    def load(self, path: str):
        try:
            import tensorflow as tf
            self.model = tf.keras.models.load_model(path)
            self.is_trained = True
        except ImportError:
            pass
