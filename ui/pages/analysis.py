"""
Analysis Page — Deep-dive single stock analysis with chart + NLP explanation.
"""
import streamlit as st
import pandas as pd


def render_analysis(segment: str):
    """Render the stock analysis page."""
    from data.market_feed import get_data_provider
    from analysis.signal_generator import generate_signals
    from nlp.explainer import explain_stock
    from ui.components.charts import create_candlestick_chart
    from trading.margin_trader import MarginTrader
    from trading.prediction_trader import PredictionTrader

    st.markdown("## 🔬 Stock Analysis")

    provider = get_data_provider()

    # ── Stock Input ──
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        symbol = st.text_input(
            "Enter Stock/Index Symbol",
            value="RELIANCE",
            placeholder="e.g., RELIANCE, NIFTY, GOLD",
            key="analysis_symbol",
        ).upper().strip()
    with col2:
        interval = st.selectbox("Interval", ["1min", "5min", "15min", "30min", "1h"], index=1)
    with col3:
        days = st.selectbox("Period (days)", [5, 10, 15, 30, 60, 90], index=3)

    if not symbol:
        st.info("Enter a stock symbol to begin analysis.")
        return

    # ── Get Data & Analyze ──
    with st.spinner(f"Analyzing {symbol}..."):
        df = provider.get_historical_data(symbol, interval=interval, days=days)

        if df.empty or len(df) < 50:
            st.error(f"Insufficient data for {symbol}. Need at least 50 candles.")
            return

        result = generate_signals(df, symbol, segment)

    with st.spinner(f"Running ML ensemble predictions for {symbol}..."):
        from ml.ensemble import EnsemblePredictor
        ensemble = EnsemblePredictor()
        try:
            if len(df) >= 100:
                ensemble.train(df)
            ml_signal, ml_confidence = ensemble.predict_single(df)
            ml_direction = ml_signal.value.replace("STRONG_", "") if ml_signal.value != "HOLD" else "HOLD"
        except Exception as e:
            ml_confidence = 0.0
            ml_direction = "HOLD"

    # ── Signal Banner ──
    signal_colors = {
        "STRONG_BUY": ("🟢🟢", "background-color: #1b5e20; padding: 15px; border-radius: 10px;"),
        "BUY": ("🟢", "background-color: #2e7d32; padding: 15px; border-radius: 10px;"),
        "HOLD": ("🟡", "background-color: #f57f17; padding: 15px; border-radius: 10px;"),
        "SELL": ("🔴", "background-color: #c62828; padding: 15px; border-radius: 10px;"),
        "STRONG_SELL": ("🔴🔴", "background-color: #b71c1c; padding: 15px; border-radius: 10px;"),
    }
    emoji, style = signal_colors.get(result.signal.value, ("⚪", ""))

    st.markdown(
        f"""<div style="{style}; color: white; text-align: center; margin-bottom: 20px;">
        <h2 style="margin:0;">{emoji} {result.signal.value} — {symbol}</h2>
        <p style="margin:5px 0;">LTP: ₹{result.ltp:,.2f} | Confidence: {result.confidence:.0f}% | Segment: {segment.upper()}</p>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Indicator Cards ──
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("RSI (14)", f"{result.rsi:.1f}",
                   delta="Oversold" if result.rsi < 30 else "Overbought" if result.rsi > 70 else "Neutral")
    with col2:
        st.metric("Bollinger %B", f"{result.bollinger_pct_b:.2f}",
                   delta="Below Band" if result.bollinger_pct_b < 0 else "Above Band" if result.bollinger_pct_b > 1 else "Normal")
    with col3:
        st.metric("MACD Hist", f"{result.macd_histogram:.4f}",
                   delta="Bullish" if result.macd_histogram > 0 else "Bearish")
    with col4:
        st.metric("Supertrend", "📈 Bullish" if result.supertrend_direction == 1 else "📉 Bearish")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("ATR (14)", f"₹{result.atr:,.2f}")
    with col2:
        st.metric("VWAP", f"₹{result.vwap:,.2f}")
    with col3:
        st.metric("MAD (20)", f"₹{result.mad_20:,.2f}")
    with col4:
        st.metric("EMA 9/21", f"{'Bullish' if result.ema_9 > result.ema_21 else 'Bearish'}")

    st.divider()

    # ── Chart ──
    st.markdown("### 📈 Interactive Chart")
    fig = create_candlestick_chart(df, symbol, analysis=result)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Trading Opportunities ──
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 💰 Margin Trade Opportunity")
        margin = MarginTrader()
        opp = margin.evaluate_opportunity(result)
        if opp["opportunity"]:
            st.success(f"✅ Spread: {opp['spread_pct']:.2f}%")
            
            # Allow user to edit order constraints
            default_sl = margin.risk_manager.calculate_stop_loss(opp["buy_price"], result.atr, "BUY")
            default_qty = margin.risk_manager.calculate_position_size(opp["buy_price"], default_sl)
            
            scol1, scol2 = st.columns(2)
            with scol1:
                margin_buy = st.number_input("Entry Price (₹)", min_value=0.1, value=float(opp["buy_price"]), step=0.5, key="margin_buy")
                margin_qty = st.number_input("Total Quantity", min_value=1, value=max(1, default_qty), step=1, key="margin_qty")
            with scol2:
                margin_sell = st.number_input("Target Sell (₹)", min_value=0.1, value=float(opp["sell_price"]), step=0.5, key="margin_sell")
                margin_sl = st.number_input("Stoploss (₹)", min_value=0.1, value=float(default_sl), step=0.5, key="margin_sl")

            est_profit = (margin_sell - margin_buy) * margin_qty
            total_required = margin_buy * margin_qty
            
            st.write(
                f"**Total Amount Required:** ₹{total_required:,.2f} | "
                f"**Est. Profit:** ₹{est_profit:,.2f}"
            )

            if st.button("Execute Margin Trade", key="exec_margin"):
                result_exec = margin.execute_margin_trade(
                    result, 
                    quantity=margin_qty, 
                    stop_loss=margin_sl,
                    buy_price=margin_buy,
                    sell_price=margin_sell
                )
                if result_exec["success"]:
                    st.success(f"✅ Order placed! Est. profit: ₹{result_exec['estimated_profit']:,.2f}")
                else:
                    st.error(f"❌ {result_exec['reason']}")
        else:
            st.warning(f"❌ {opp['reason']} (Spread: {opp['spread_pct']:.2f}%)")

    with col2:
        st.markdown("### 🎯 Prediction Trade Opportunity")
        predictor = PredictionTrader()
        pred_opp = predictor.evaluate_opportunity(result, ml_confidence, ml_direction)
        if pred_opp["opportunity"]:
            st.success(f"✅ {pred_opp['direction']} — Confidence: {pred_opp['combined_confidence']:.0f}%")
            st.write(f"**Entry:** ₹{pred_opp['entry_price']:,.2f}")
            st.write(f"**Stop Loss:** ₹{pred_opp['stop_loss']:,.2f}")
            st.write(f"**Take Profit:** ₹{pred_opp['take_profit']:,.2f}")
            if st.button("Execute Prediction Trade", key="exec_pred"):
                result_exec = predictor.execute_prediction_trade(result, ml_confidence, ml_direction)
                if result_exec["success"]:
                    st.success(f"✅ Order placed! R:R = {result_exec['risk_reward']:.1f}x")
                else:
                    st.error(f"❌ {result_exec['reason']}")
        else:
            reason_msg = pred_opp['reason']
            # Fallback for displaying the combined confidence if blocking
            conf = pred_opp.get('combined_confidence', 0)
            st.warning(f"❌ {reason_msg} (Conf: {conf:.0f}%)")

    st.divider()

    # ── NLP Explanation ──
    st.markdown("### 🤖 AI Analysis Report")
    with st.spinner("Generating analysis..."):
        explanation = explain_stock(result)
    st.markdown(explanation)

    # ── Raw Indicator Data ──
    with st.expander("📊 Raw Indicator Values"):
        raw_data = {
            "Indicator": [
                "LTP", "MAD(5)", "MAD(10)", "MAD(20)", "MAD(50)",
                "BB Upper", "BB Mid", "BB Lower", "BB %B", "BB Width",
                "RSI(14)", "VWAP", "EMA(9)", "EMA(21)",
                "MACD Line", "MACD Signal", "MACD Hist",
                "ATR(14)", "Supertrend",
            ],
            "Value": [
                f"₹{result.ltp:,.2f}", f"₹{result.mad_5:,.4f}", f"₹{result.mad_10:,.4f}",
                f"₹{result.mad_20:,.4f}", f"₹{result.mad_50:,.4f}",
                f"₹{result.bollinger_upper:,.2f}", f"₹{result.bollinger_mid:,.2f}",
                f"₹{result.bollinger_lower:,.2f}", f"{result.bollinger_pct_b:.4f}",
                f"{result.bollinger_width:.4f}",
                f"{result.rsi:.2f}", f"₹{result.vwap:,.2f}",
                f"₹{result.ema_9:,.2f}", f"₹{result.ema_21:,.2f}",
                f"{result.macd_line:.4f}", f"{result.macd_signal:.4f}", f"{result.macd_histogram:.4f}",
                f"₹{result.atr:,.2f}", f"₹{result.supertrend:,.2f}",
            ],
        }
        st.dataframe(pd.DataFrame(raw_data), use_container_width=True, hide_index=True)
