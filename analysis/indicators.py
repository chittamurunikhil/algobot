"""
Technical Analysis Indicators — MAD, Bollinger Bands, RSI, VWAP, EMA, MACD, ATR, Supertrend.
All functions accept pandas Series/DataFrame and return computed values.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


# ══════════════════════════════════════════════════════════════════════════════
# MAD — Mean Absolute Deviation
# ══════════════════════════════════════════════════════════════════════════════

def calculate_mad(series: pd.Series, windows: List[int] = None) -> Dict[str, pd.Series]:
    """
    Calculate Mean Absolute Deviation for multiple windows.
    MAD(n) = (1/n) × Σ|xi - x̄|
    
    Returns dict: {"mad_5": Series, "mad_10": Series, ...}
    """
    if windows is None:
        windows = [5, 10, 20, 50]

    result = {}
    for w in windows:
        rolling_mean = series.rolling(window=w).mean()
        mad = series.rolling(window=w).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
        )
        result[f"mad_{w}"] = mad

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Bollinger Bands
# ══════════════════════════════════════════════════════════════════════════════

def calculate_bollinger(series: pd.Series, period: int = 20,
                        std_dev: float = 2.0) -> Dict[str, pd.Series]:
    """
    Calculate Bollinger Bands.
    - Mid = SMA(period)
    - Upper = SMA + std_dev × σ
    - Lower = SMA - std_dev × σ
    - %B = (Price - Lower) / (Upper - Lower)
    - Bandwidth = (Upper - Lower) / Mid
    """
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()

    upper = sma + std_dev * std
    lower = sma - std_dev * std

    pct_b = (series - lower) / (upper - lower)
    bandwidth = (upper - lower) / sma

    return {
        "bollinger_upper": upper,
        "bollinger_mid": sma,
        "bollinger_lower": lower,
        "bollinger_pct_b": pct_b,
        "bollinger_width": bandwidth,
    }


# ══════════════════════════════════════════════════════════════════════════════
# RSI — Relative Strength Index
# ══════════════════════════════════════════════════════════════════════════════

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate RSI using exponential moving average method.
    RSI = 100 - 100 / (1 + RS)
    RS = Avg Gain / Avg Loss over `period`
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


# ══════════════════════════════════════════════════════════════════════════════
# VWAP — Volume Weighted Average Price
# ══════════════════════════════════════════════════════════════════════════════

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Calculate VWAP.
    VWAP = Σ(Typical Price × Volume) / Σ(Volume)
    Typical Price = (High + Low + Close) / 3
    
    Resets daily if index has date information.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    vwap = cumulative_tp_vol / cumulative_vol.replace(0, np.nan)
    return vwap


# ══════════════════════════════════════════════════════════════════════════════
# EMA — Exponential Moving Average
# ══════════════════════════════════════════════════════════════════════════════

def calculate_ema(series: pd.Series, spans: List[int] = None) -> Dict[str, pd.Series]:
    """
    Calculate EMAs for multiple spans.
    Returns dict: {"ema_9": Series, "ema_21": Series, ...}
    """
    if spans is None:
        spans = [9, 21]

    return {f"ema_{s}": series.ewm(span=s, adjust=False).mean() for s in spans}


# ══════════════════════════════════════════════════════════════════════════════
# MACD — Moving Average Convergence Divergence
# ══════════════════════════════════════════════════════════════════════════════

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26,
                   signal: int = 9) -> Dict[str, pd.Series]:
    """
    Calculate MACD.
    - MACD Line = EMA(fast) - EMA(slow)
    - Signal Line = EMA(MACD Line, signal)
    - Histogram = MACD - Signal
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return {
        "macd_line": macd_line,
        "macd_signal": signal_line,
        "macd_histogram": histogram,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ATR — Average True Range
# ══════════════════════════════════════════════════════════════════════════════

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate ATR.
    TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    ATR = EMA(TR, period)
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr


# ══════════════════════════════════════════════════════════════════════════════
# Supertrend
# ══════════════════════════════════════════════════════════════════════════════

def calculate_supertrend(df: pd.DataFrame, period: int = 10,
                         multiplier: float = 3.0) -> Dict[str, pd.Series]:
    """
    Calculate Supertrend indicator.
    Returns: {"supertrend": Series, "supertrend_direction": Series (1=up, -1=down)}
    """
    atr = calculate_atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2

    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)

    supertrend.iloc[0] = upper_band.iloc[0]
    direction.iloc[0] = 1

    for i in range(1, len(df)):
        if df["close"].iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]

        if direction.iloc[i] == 1:
            supertrend.iloc[i] = max(lower_band.iloc[i],
                                      supertrend.iloc[i - 1] if direction.iloc[i - 1] == 1 else lower_band.iloc[i])
        else:
            supertrend.iloc[i] = min(upper_band.iloc[i],
                                      supertrend.iloc[i - 1] if direction.iloc[i - 1] == -1 else upper_band.iloc[i])

    return {
        "supertrend": supertrend,
        "supertrend_direction": direction,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Run All Indicators
# ══════════════════════════════════════════════════════════════════════════════

def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all technical indicators and merge into a single DataFrame.
    Expects df with columns: open, high, low, close, volume.
    """
    result = df.copy()
    close = df["close"]

    # MAD
    mad_vals = calculate_mad(close)
    for k, v in mad_vals.items():
        result[k] = v

    # Bollinger Bands
    bb_vals = calculate_bollinger(close)
    for k, v in bb_vals.items():
        result[k] = v

    # RSI
    result["rsi"] = calculate_rsi(close)

    # VWAP
    result["vwap"] = calculate_vwap(df)

    # EMA
    ema_vals = calculate_ema(close)
    for k, v in ema_vals.items():
        result[k] = v

    # MACD
    macd_vals = calculate_macd(close)
    for k, v in macd_vals.items():
        result[k] = v

    # ATR
    result["atr"] = calculate_atr(df)

    # Supertrend
    st_vals = calculate_supertrend(df)
    for k, v in st_vals.items():
        result[k] = v

    return result
