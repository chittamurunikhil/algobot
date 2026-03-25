"""
Prompt templates for LLM-based stock explanation.
"""

STOCK_ANALYSIS_PROMPT = """You are an expert Indian stock market analyst. Analyze the following technical data for {symbol} ({segment} segment) and provide a clear, actionable explanation in plain English.

## Current Market Data
- **Last Traded Price (LTP):** ₹{ltp}
- **Segment:** {segment}

## Technical Indicators
### Volatility (MAD - Mean Absolute Deviation)
- MAD(5): ₹{mad_5}  | MAD(10): ₹{mad_10}  | MAD(20): ₹{mad_20}  | MAD(50): ₹{mad_50}

### Bollinger Bands (20-period, 2σ)
- Upper: ₹{bollinger_upper} | Mid: ₹{bollinger_mid} | Lower: ₹{bollinger_lower}
- %B: {bollinger_pct_b} | Bandwidth: {bollinger_width}

### Demand/Supply Zones
- Demand Zones: {demand_zones}
- Supply Zones: {supply_zones}

### Momentum & Trend
- RSI(14): {rsi}
- VWAP: ₹{vwap}
- EMA(9): ₹{ema_9} | EMA(21): ₹{ema_21}
- MACD Line: {macd_line} | Signal: {macd_signal} | Histogram: {macd_histogram}
- ATR(14): ₹{atr}
- Supertrend: ₹{supertrend} (Direction: {supertrend_dir})

### Signal Summary
- **Signal:** {signal}
- **Confidence:** {confidence}%
- **Reasons:** {reasons}

## Instructions
1. Summarize the current technical picture in 2-3 sentences
2. Explain what each key indicator is telling us
3. Provide a clear recommendation (buy/sell/hold) with entry/exit levels
4. Mention key risk factors
5. If this is an options/futures/commodity, factor in segment-specific considerations

Keep the explanation conversational but data-driven. Cite specific numbers.
"""

TEMPLATE_EXPLANATION = """
📊 **{symbol} Analysis** ({segment})

**Price:** ₹{ltp}

**Volatility:** MAD(20) = ₹{mad_20:.2f}, indicating {"high" if float('{mad_20}') > float('{ltp}') * 0.02 else "moderate"} volatility.

**Bollinger Bands:** Price is at %B = {bollinger_pct_b:.2f}. {"Price is near the lower band — potential oversold condition." if float('{bollinger_pct_b}') < 0.2 else "Price is near the upper band — potential overbought condition." if float('{bollinger_pct_b}') > 0.8 else "Price is within normal Bollinger range."}

**Momentum:** RSI = {rsi:.1f} ({"oversold" if float('{rsi}') < 30 else "overbought" if float('{rsi}') > 70 else "neutral"}). MACD histogram is {"positive ✅" if float('{macd_histogram}') > 0 else "negative ❌"}.

**Trend:** EMA(9) is {"above" if float('{ema_9}') > float('{ema_21}') else "below"} EMA(21) — {"bullish" if float('{ema_9}') > float('{ema_21}') else "bearish"} trend. Supertrend is {"bullish 📈" if '{supertrend_dir}' == '1' else "bearish 📉"}.

**Signal:** {signal} (Confidence: {confidence}%)
**Key Factors:** {reasons}
"""
