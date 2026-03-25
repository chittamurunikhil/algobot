"""
Ensemble Voter — combines predictions from XGBoost, Random Forest, and LSTM
using weighted averaging for final signal generation.
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from ml.models import XGBoostModel, RandomForestModel, LSTMModel, BaseModel
from ml.features import engineer_features, get_feature_columns
from data.models import Signal


class EnsemblePredictor:
    """
    Weighted ensemble of XGBoost + Random Forest + LSTM.
    Weights are determined by individual model accuracy on validation set.
    """

    def __init__(self):
        self.models: Dict[str, BaseModel] = {
            "xgboost": XGBoostModel(),
            "random_forest": RandomForestModel(),
            "lstm": LSTMModel(sequence_length=20),
        }
        self.weights: Dict[str, float] = {
            "xgboost": 0.4,
            "random_forest": 0.3,
            "lstm": 0.3,
        }
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.is_trained = False
        self.training_accuracy = {}

    def train(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Train all models on feature-engineered data.
        Uses walk-forward split: 70% train, 15% val, 15% test.
        Returns accuracy dict per model.
        """
        # Feature engineering
        featured = engineer_features(df)
        self.feature_columns = get_feature_columns(featured)

        X = featured[self.feature_columns].values
        y = featured["target"].values

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Split: 70/15/15
        n = len(X_scaled)
        train_end = int(n * 0.7)
        val_end = int(n * 0.85)

        X_train, y_train = X_scaled[:train_end], y[:train_end]
        X_val, y_val = X_scaled[train_end:val_end], y[train_end:val_end]
        X_test, y_test = X_scaled[val_end:], y[val_end:]

        accuracies = {}

        # Train XGBoost
        try:
            self.models["xgboost"].train(X_train, y_train)
            preds = self.models["xgboost"].predict(X_val)
            acc = np.mean(preds == y_val) * 100
            accuracies["xgboost"] = acc
        except Exception as e:
            accuracies["xgboost"] = 50.0

        # Train Random Forest
        try:
            self.models["random_forest"].train(X_train, y_train)
            preds = self.models["random_forest"].predict(X_val)
            acc = np.mean(preds == y_val) * 100
            accuracies["random_forest"] = acc
        except Exception as e:
            accuracies["random_forest"] = 50.0

        # Train LSTM
        try:
            self.models["lstm"].train(X_train, y_train)
            preds = self.models["lstm"].predict(X_val)
            # LSTM predictions may be shorter due to sequence length
            trimmed_y = y_val[-len(preds):] if len(preds) < len(y_val) else y_val
            acc = np.mean(preds == trimmed_y) * 100 if len(preds) > 0 else 50.0
            accuracies["lstm"] = acc
        except Exception as e:
            accuracies["lstm"] = 50.0

        # Update weights based on accuracy
        total_acc = sum(accuracies.values())
        if total_acc > 0:
            for model_name in self.weights:
                self.weights[model_name] = accuracies.get(model_name, 50.0) / total_acc

        self.training_accuracy = accuracies
        self.is_trained = True

        # Test set accuracy
        test_pred, test_conf = self.predict(X_test)
        test_acc = np.mean(test_pred == y_test) * 100 if len(test_pred) > 0 else 50.0
        accuracies["ensemble_test"] = test_acc

        return accuracies

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Make ensemble prediction.
        Returns: (predictions array, confidence array)
        """
        if not self.is_trained:
            return np.zeros(len(X)), np.full(len(X), 50.0)

        # Collect weighted probabilities
        min_len = len(X)
        all_probs = {}

        for name, model in self.models.items():
            if model.is_trained:
                probs = model.predict_proba(X)
                if len(probs) < min_len:
                    min_len = len(probs)
                all_probs[name] = probs

        if not all_probs:
            return np.zeros(len(X)), np.full(len(X), 50.0)

        # Weighted average of probabilities
        ensemble_probs = np.zeros((min_len, 2))
        total_weight = 0.0
        for name, probs in all_probs.items():
            w = self.weights.get(name, 0.33)
            ensemble_probs += w * probs[-min_len:]
            total_weight += w

        if total_weight > 0:
            ensemble_probs /= total_weight

        predictions = (ensemble_probs[:, 1] > 0.5).astype(int)
        confidence = np.maximum(ensemble_probs[:, 0], ensemble_probs[:, 1]) * 100

        return predictions, confidence

    def predict_single(self, df: pd.DataFrame) -> Tuple[Signal, float]:
        """
        Make a prediction for the latest data point.
        Returns: (Signal, confidence %)
        """
        if not self.is_trained:
            return Signal.HOLD, 50.0

        featured = engineer_features(df)
        if featured.empty:
            return Signal.HOLD, 50.0

        X = featured[self.feature_columns].values
        X_scaled = self.scaler.transform(X)

        preds, confs = self.predict(X_scaled)

        if len(preds) == 0:
            return Signal.HOLD, 50.0

        latest_pred = preds[-1]
        latest_conf = confs[-1]

        if latest_pred == 1:
            signal = Signal.STRONG_BUY if latest_conf >= 80 else Signal.BUY
        else:
            signal = Signal.STRONG_SELL if latest_conf >= 80 else Signal.SELL

        return signal, latest_conf
