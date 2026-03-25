"""
NLP Explanation Engine — Generates natural-language stock analysis.
Supports OpenAI, Gemini, and template-based (no API key needed) modes.
"""
from typing import Optional
from data.models import AnalysisResult
from config.settings import get_settings, LLMProvider


def explain_stock(result: AnalysisResult) -> str:
    """
    Generate a natural language explanation for an analysis result.
    Uses the configured LLM provider, falls back to template if unavailable.
    """
    settings = get_settings()

    if settings.llm_provider == LLMProvider.OPENAI and settings.openai_api_key:
        return _explain_openai(result, settings.openai_api_key)
    elif settings.llm_provider == LLMProvider.GEMINI and settings.gemini_api_key:
        return _explain_gemini(result, settings.gemini_api_key)
    else:
        return _explain_template(result)


def _explain_template(result: AnalysisResult) -> str:
    """Generate explanation using templates (no API key needed)."""
    lines = []
    symbol = result.symbol
    segment = result.segment.upper()

    lines.append(f"📊 **{symbol} — {segment} Analysis**\n")
    lines.append(f"**Last Traded Price:** ₹{result.ltp:,.2f}\n")

    # Volatility
    lines.append("### Volatility (MAD)")
    if result.mad_20 > result.ltp * 0.025:
        lines.append(f"⚠️ High volatility — MAD(20) = ₹{result.mad_20:.2f} ({result.mad_20/result.ltp*100:.1f}% of price). This stock is making large swings, suitable for margin trading spreads.")
    elif result.mad_20 > result.ltp * 0.01:
        lines.append(f"📈 Moderate volatility — MAD(20) = ₹{result.mad_20:.2f} ({result.mad_20/result.ltp*100:.1f}% of price). Normal trading conditions.")
    else:
        lines.append(f"😴 Low volatility — MAD(20) = ₹{result.mad_20:.2f} ({result.mad_20/result.ltp*100:.1f}% of price). Tight range, may break out soon.")
    lines.append("")

    # Bollinger Bands
    lines.append("### Bollinger Bands")
    bb_status = ""
    if result.bollinger_pct_b < 0:
        bb_status = "🔴 Price has broken BELOW the lower Bollinger Band — this is an extreme oversold condition. Watch for a potential reversal bounce."
    elif result.bollinger_pct_b < 0.2:
        bb_status = "🟡 Price is near the lower Bollinger Band — approaching oversold territory. Could be a buying opportunity if other indicators confirm."
    elif result.bollinger_pct_b > 1:
        bb_status = "🔴 Price has broken ABOVE the upper Bollinger Band — extreme overbought condition. Watch for a potential pullback."
    elif result.bollinger_pct_b > 0.8:
        bb_status = "🟡 Price is near the upper Bollinger Band — approaching overbought territory. Consider taking partial profits."
    else:
        bb_status = "🟢 Price is within normal Bollinger Band range."

    lines.append(f"Upper: ₹{result.bollinger_upper:,.2f} | Mid: ₹{result.bollinger_mid:,.2f} | Lower: ₹{result.bollinger_lower:,.2f}")
    lines.append(f"%B = {result.bollinger_pct_b:.2f} — {bb_status}")
    lines.append("")

    # Demand / Supply Zones
    lines.append("### Support & Resistance (Demand/Supply Zones)")
    if result.demand_zones:
        for z in result.demand_zones[:2]:
            lines.append(f"🟢 **Demand Zone:** ₹{z.price_low:,.2f} – ₹{z.price_high:,.2f} (Strength: {z.strength:.0f}%)")
    if result.supply_zones:
        for z in result.supply_zones[:2]:
            lines.append(f"🔴 **Supply Zone:** ₹{z.price_low:,.2f} – ₹{z.price_high:,.2f} (Strength: {z.strength:.0f}%)")
    if not result.demand_zones and not result.supply_zones:
        lines.append("No clear demand/supply zones detected in recent data.")
    lines.append("")

    # Momentum
    lines.append("### Momentum & Trend Indicators")
    rsi_label = "oversold 🟢" if result.rsi < 30 else "overbought 🔴" if result.rsi > 70 else "neutral"
    lines.append(f"- **RSI(14):** {result.rsi:.1f} — {rsi_label}")
    lines.append(f"- **VWAP:** ₹{result.vwap:,.2f} — Price is {'above' if result.ltp > result.vwap else 'below'} VWAP ({'bullish' if result.ltp > result.vwap else 'bearish'} intraday bias)")

    ema_trend = "bullish 📈" if result.ema_9 > result.ema_21 else "bearish 📉"
    lines.append(f"- **EMA(9/21):** {ema_trend} — EMA(9) = ₹{result.ema_9:,.2f}, EMA(21) = ₹{result.ema_21:,.2f}")

    macd_label = "positive momentum ✅" if result.macd_histogram > 0 else "negative momentum ❌"
    lines.append(f"- **MACD:** Histogram = {result.macd_histogram:.4f} — {macd_label}")

    st_label = "bullish 📈" if result.supertrend_direction == 1 else "bearish 📉"
    lines.append(f"- **Supertrend:** ₹{result.supertrend:,.2f} — {st_label}")
    lines.append(f"- **ATR(14):** ₹{result.atr:,.2f} — useful for stop-loss placement")
    lines.append("")

    # Segment-specific notes
    if result.segment in ("options", "derivatives"):
        lines.append("### Options/Derivatives Notes")
        if result.iv > 0:
            lines.append(f"- **Implied Volatility:** {result.iv:.1f}%")
        if result.open_interest > 0:
            lines.append(f"- **Open Interest:** {result.open_interest:,}")
        lines.append("")
    elif result.segment in ("futures", "commodities"):
        lines.append("### Futures/Commodities Notes")
        if result.open_interest > 0:
            lines.append(f"- **Open Interest:** {result.open_interest:,}")
        lines.append("")

    # Final Verdict
    lines.append("### 🎯 Verdict")
    signal_emoji = {"BUY": "🟢", "STRONG_BUY": "🟢🟢", "SELL": "🔴", "STRONG_SELL": "🔴🔴", "HOLD": "🟡"}
    emoji = signal_emoji.get(result.signal.value, "⚪")
    lines.append(f"**{emoji} {result.signal.value}** — Confidence: {result.confidence:.0f}%")
    lines.append(f"\n**Key Reasons:** {result.explanation}")

    # Trading suggestions
    if result.signal.value in ("BUY", "STRONG_BUY"):
        sl = result.ltp - (result.atr * 1.5) if result.atr > 0 else result.ltp * 0.98
        tp = result.ltp + (result.atr * 2.5) if result.atr > 0 else result.ltp * 1.03
        lines.append(f"\n**Suggested Entry:** ₹{result.ltp:,.2f}")
        lines.append(f"**Stop Loss:** ₹{sl:,.2f} | **Target:** ₹{tp:,.2f}")
    elif result.signal.value in ("SELL", "STRONG_SELL"):
        sl = result.ltp + (result.atr * 1.5) if result.atr > 0 else result.ltp * 1.02
        tp = result.ltp - (result.atr * 2.5) if result.atr > 0 else result.ltp * 0.97
        lines.append(f"\n**Suggested Short Entry:** ₹{result.ltp:,.2f}")
        lines.append(f"**Stop Loss:** ₹{sl:,.2f} | **Target:** ₹{tp:,.2f}")

    return "\n".join(lines)


def _explain_openai(result: AnalysisResult, api_key: str) -> str:
    """Generate explanation using OpenAI API."""
    try:
        from openai import OpenAI
        from nlp.prompts import STOCK_ANALYSIS_PROMPT

        client = OpenAI(api_key=api_key)
        prompt = _format_prompt(STOCK_ANALYSIS_PROMPT, result)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return _explain_template(result) + f"\n\n*LLM unavailable: {e}*"


def _explain_gemini(result: AnalysisResult, api_key: str) -> str:
    """Generate explanation using Google Gemini API."""
    try:
        import google.generativeai as genai
        from nlp.prompts import STOCK_ANALYSIS_PROMPT

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = _format_prompt(STOCK_ANALYSIS_PROMPT, result)

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return _explain_template(result) + f"\n\n*LLM unavailable: {e}*"


def _format_prompt(template: str, result: AnalysisResult) -> str:
    """Format the prompt template with analysis data."""
    demand_str = ", ".join(
        [f"₹{z.price_low}-{z.price_high} (str:{z.strength}%)" for z in result.demand_zones]
    ) if result.demand_zones else "None detected"

    supply_str = ", ".join(
        [f"₹{z.price_low}-{z.price_high} (str:{z.strength}%)" for z in result.supply_zones]
    ) if result.supply_zones else "None detected"

    return template.format(
        symbol=result.symbol,
        segment=result.segment,
        ltp=f"{result.ltp:.2f}",
        mad_5=f"{result.mad_5:.2f}",
        mad_10=f"{result.mad_10:.2f}",
        mad_20=f"{result.mad_20:.2f}",
        mad_50=f"{result.mad_50:.2f}",
        bollinger_upper=f"{result.bollinger_upper:.2f}",
        bollinger_mid=f"{result.bollinger_mid:.2f}",
        bollinger_lower=f"{result.bollinger_lower:.2f}",
        bollinger_pct_b=f"{result.bollinger_pct_b:.2f}",
        bollinger_width=f"{result.bollinger_width:.4f}",
        demand_zones=demand_str,
        supply_zones=supply_str,
        rsi=f"{result.rsi:.1f}",
        vwap=f"{result.vwap:.2f}",
        ema_9=f"{result.ema_9:.2f}",
        ema_21=f"{result.ema_21:.2f}",
        macd_line=f"{result.macd_line:.4f}",
        macd_signal=f"{result.macd_signal:.4f}",
        macd_histogram=f"{result.macd_histogram:.4f}",
        atr=f"{result.atr:.2f}",
        supertrend=f"{result.supertrend:.2f}",
        supertrend_dir="Bullish" if result.supertrend_direction == 1 else "Bearish",
        signal=result.signal.value,
        confidence=f"{result.confidence:.0f}",
        reasons=result.explanation,
    )
