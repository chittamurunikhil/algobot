"""
Signal Generator — aggregates all technical indicators into a unified
BUY/SELL/HOLD signal with confidence score. Segment-aware.
"""
import pandas as pd
import numpy as np
from typing import Optional
from data.models import AnalysisResult, Signal, DemandSupplyZone
from analysis.indicators import compute_all_indicators
from analysis.demand_supply import find_demand_zones, find_supply_zones


def generate_signals(df: pd.DataFrame, symbol: str,
                     segment: str = "intraday") -> AnalysisResult:
    """
    Run full analysis on OHLCV data and produce an AnalysisResult.
    
    Signal logic (weighted scoring):
    - RSI oversold/overbought        : ±20 pts
    - Bollinger %B extremes          : ±15 pts
    - MACD crossover                 : ±15 pts
    - EMA crossover (9/21)           : ±15 pts
    - Supertrend direction           : ±15 pts
    - VWAP deviation                 : ±10 pts
    - Demand/Supply zone proximity   : ±10 pts
    
    Total: -100 to +100 → mapped to signal + confidence
    """
    if len(df) < 50:
        return AnalysisResult(symbol=symbol, segment=segment, explanation="Insufficient data for analysis")

    # Compute all indicators
    analyzed = compute_all_indicators(df)
    latest = analyzed.iloc[-1]
    prev = analyzed.iloc[-2] if len(analyzed) > 1 else latest

    # Demand / Supply zones
    demand_zones = find_demand_zones(df)
    supply_zones = find_supply_zones(df)

    # ── Scoring ──
    score = 0.0
    reasons = []

    # 1. RSI (±20)
    rsi = latest.get("rsi", 50)
    if rsi < 30:
        score += 20
        reasons.append(f"RSI oversold at {rsi:.1f}")
    elif rsi < 40:
        score += 10
        reasons.append(f"RSI approaching oversold at {rsi:.1f}")
    elif rsi > 70:
        score -= 20
        reasons.append(f"RSI overbought at {rsi:.1f}")
    elif rsi > 60:
        score -= 10
        reasons.append(f"RSI approaching overbought at {rsi:.1f}")

    # 2. Bollinger %B (±15)
    pct_b = latest.get("bollinger_pct_b", 0.5)
    if not np.isnan(pct_b):
        if pct_b < 0:
            score += 15
            reasons.append(f"Price below lower Bollinger Band (%B={pct_b:.2f})")
        elif pct_b < 0.2:
            score += 8
            reasons.append(f"Price near lower Bollinger Band (%B={pct_b:.2f})")
        elif pct_b > 1:
            score -= 15
            reasons.append(f"Price above upper Bollinger Band (%B={pct_b:.2f})")
        elif pct_b > 0.8:
            score -= 8
            reasons.append(f"Price near upper Bollinger Band (%B={pct_b:.2f})")

    # 3. MACD crossover (±15)
    macd_hist = latest.get("macd_histogram", 0)
    prev_macd_hist = prev.get("macd_histogram", 0)
    if not np.isnan(macd_hist) and not np.isnan(prev_macd_hist):
        if macd_hist > 0 and prev_macd_hist <= 0:
            score += 15
            reasons.append("MACD bullish crossover")
        elif macd_hist < 0 and prev_macd_hist >= 0:
            score -= 15
            reasons.append("MACD bearish crossover")
        elif macd_hist > 0:
            score += 5
            reasons.append("MACD positive")
        elif macd_hist < 0:
            score -= 5
            reasons.append("MACD negative")

    # 4. EMA crossover 9/21 (±15)
    ema_9 = latest.get("ema_9", 0)
    ema_21 = latest.get("ema_21", 0)
    prev_ema_9 = prev.get("ema_9", 0)
    prev_ema_21 = prev.get("ema_21", 0)
    if ema_9 and ema_21 and not np.isnan(ema_9) and not np.isnan(ema_21):
        if ema_9 > ema_21 and prev_ema_9 <= prev_ema_21:
            score += 15
            reasons.append("EMA 9/21 bullish crossover")
        elif ema_9 < ema_21 and prev_ema_9 >= prev_ema_21:
            score -= 15
            reasons.append("EMA 9/21 bearish crossover")
        elif ema_9 > ema_21:
            score += 5
            reasons.append("EMA 9 above EMA 21 (bullish trend)")
        else:
            score -= 5
            reasons.append("EMA 9 below EMA 21 (bearish trend)")

    # 5. Supertrend (±15)
    st_dir = latest.get("supertrend_direction", 0)
    prev_st_dir = prev.get("supertrend_direction", 0)
    if st_dir == 1:
        score += 10
        if prev_st_dir == -1:
            score += 5
            reasons.append("Supertrend flipped bullish")
        else:
            reasons.append("Supertrend bullish")
    elif st_dir == -1:
        score -= 10
        if prev_st_dir == 1:
            score -= 5
            reasons.append("Supertrend flipped bearish")
        else:
            reasons.append("Supertrend bearish")

    # 6. VWAP deviation (±10)
    vwap = latest.get("vwap", 0)
    close = latest["close"]
    if vwap and not np.isnan(vwap) and vwap > 0:
        vwap_dev = ((close - vwap) / vwap) * 100
        if vwap_dev < -1:
            score += 10
            reasons.append(f"Price {abs(vwap_dev):.1f}% below VWAP")
        elif vwap_dev > 1:
            score -= 10
            reasons.append(f"Price {vwap_dev:.1f}% above VWAP")

    # 7. Demand/Supply proximity (±10)
    if demand_zones:
        nearest_demand_high = max(z.price_high for z in demand_zones)
        if close <= nearest_demand_high * 1.005:
            score += 10
            reasons.append(f"Price near demand zone (₹{nearest_demand_high:.2f})")
    if supply_zones:
        nearest_supply_low = min(z.price_low for z in supply_zones)
        if close >= nearest_supply_low * 0.995:
            score -= 10
            reasons.append(f"Price near supply zone (₹{nearest_supply_low:.2f})")

    # ── Map score to signal ──
    confidence = min(abs(score), 100)

    if score >= 40:
        signal = Signal.STRONG_BUY
    elif score >= 15:
        signal = Signal.BUY
    elif score <= -40:
        signal = Signal.STRONG_SELL
    elif score <= -15:
        signal = Signal.SELL
    else:
        signal = Signal.HOLD

    # ── Build result ──
    result = AnalysisResult(
        symbol=symbol,
        segment=segment,
        ltp=close,
        # MAD
        mad_5=_safe(latest, "mad_5"),
        mad_10=_safe(latest, "mad_10"),
        mad_20=_safe(latest, "mad_20"),
        mad_50=_safe(latest, "mad_50"),
        # Bollinger
        bollinger_upper=_safe(latest, "bollinger_upper"),
        bollinger_mid=_safe(latest, "bollinger_mid"),
        bollinger_lower=_safe(latest, "bollinger_lower"),
        bollinger_width=_safe(latest, "bollinger_width"),
        bollinger_pct_b=_safe(latest, "bollinger_pct_b"),
        # Demand/Supply
        demand_zones=demand_zones,
        supply_zones=supply_zones,
        # Other indicators
        rsi=_safe(latest, "rsi"),
        vwap=_safe(latest, "vwap"),
        ema_9=_safe(latest, "ema_9"),
        ema_21=_safe(latest, "ema_21"),
        macd_line=_safe(latest, "macd_line"),
        macd_signal=_safe(latest, "macd_signal"),
        macd_histogram=_safe(latest, "macd_histogram"),
        atr=_safe(latest, "atr"),
        supertrend=_safe(latest, "supertrend"),
        supertrend_direction=int(st_dir) if not np.isnan(st_dir) else 1,
        # Signal
        signal=signal,
        confidence=confidence,
        explanation=" | ".join(reasons) if reasons else "No strong signals detected",
    )

    return result


def _safe(row, key, default=0.0):
    """Safely extract a value, replacing NaN with default."""
    val = row.get(key, default)
    if isinstance(val, float) and np.isnan(val):
        return default
    return round(float(val), 4) if isinstance(val, (int, float, np.floating)) else default
