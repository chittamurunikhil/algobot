"""
Feature Engineering — transforms raw OHLCV + indicator data into ML-ready features.
"""
import pandas as pd
import numpy as np
from analysis.indicators import compute_all_indicators


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate 60+ features from OHLCV data for ML models.
    Returns DataFrame with all features and a 'target' column (1=up, 0=down).
    """
    # Compute all technical indicators first
    data = compute_all_indicators(df)

    # ── Price-derived features ──
    data["returns_1"] = data["close"].pct_change(1)
    data["returns_5"] = data["close"].pct_change(5)
    data["returns_10"] = data["close"].pct_change(10)
    data["returns_20"] = data["close"].pct_change(20)

    data["log_returns"] = np.log(data["close"] / data["close"].shift(1))

    data["high_low_range"] = (data["high"] - data["low"]) / data["close"]
    data["body_ratio"] = abs(data["close"] - data["open"]) / (data["high"] - data["low"]).replace(0, np.nan)
    data["upper_wick"] = (data["high"] - data[["open", "close"]].max(axis=1)) / data["close"]
    data["lower_wick"] = (data[["open", "close"]].min(axis=1) - data["low"]) / data["close"]

    # ── Volume features ──
    data["volume_sma_20"] = data["volume"].rolling(20).mean()
    data["volume_ratio"] = data["volume"] / data["volume_sma_20"].replace(0, np.nan)
    data["volume_change"] = data["volume"].pct_change()

    # ── Trend strength ──
    data["ema_9_21_spread"] = (data["ema_9"] - data["ema_21"]) / data["close"]
    data["price_vs_vwap"] = (data["close"] - data["vwap"]) / data["close"]
    data["price_vs_sma20"] = (data["close"] - data["bollinger_mid"]) / data["close"]

    # ── Volatility features ──
    data["volatility_5"] = data["returns_1"].rolling(5).std()
    data["volatility_20"] = data["returns_1"].rolling(20).std()
    data["volatility_ratio"] = data["volatility_5"] / data["volatility_20"].replace(0, np.nan)

    # ── Momentum features ──
    data["rsi_change"] = data["rsi"].diff()
    data["macd_change"] = data["macd_histogram"].diff()

    # ── Rolling statistics ──
    for w in [5, 10, 20]:
        data[f"close_max_{w}"] = data["close"].rolling(w).max()
        data[f"close_min_{w}"] = data["close"].rolling(w).min()
        data[f"position_in_range_{w}"] = (data["close"] - data[f"close_min_{w}"]) / (
            data[f"close_max_{w}"] - data[f"close_min_{w}"]
        ).replace(0, np.nan)

    # ── Target: next candle direction (1=up, 0=down) ──
    data["target"] = (data["close"].shift(-1) > data["close"]).astype(int)

    # Drop NaN rows
    data.dropna(inplace=True)

    return data


def get_feature_columns(df: pd.DataFrame) -> list:
    """Return list of feature column names (excluding target and raw OHLCV)."""
    exclude = {"open", "high", "low", "close", "volume", "target", "timestamp"}
    return [c for c in df.columns if c not in exclude]
