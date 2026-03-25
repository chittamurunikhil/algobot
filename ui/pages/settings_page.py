"""
Settings Page — Configuration UI for API keys, risk parameters, and preferences.
"""
import streamlit as st
from config.settings import get_settings, TradingSegment, TradeMode, BrokerName, LLMProvider


def render_settings():
    """Render the settings configuration page."""
    from data.storage import get_db

    st.markdown("## ⚙️ Settings & Configuration")

    settings = get_settings()
    db = get_db()

    tab1, tab2, tab3, tab4 = st.tabs(["🏦 Broker", "🤖 AI/LLM", "⚠️ Risk Management", "📊 Preferences"])

    # ── Broker Settings ──
    with tab1:
        st.markdown("### Broker API Configuration")
        st.info("💡 Configure your broker API keys in the `.env` file for security. These are read-only views.")

        broker = st.selectbox("Active Broker", [b.value for b in BrokerName],
                             index=[b.value for b in BrokerName].index(settings.broker_name.value))

        if broker == "zerodha":
            st.text_input("API Key", value="***" if settings.zerodha_api_key else "", disabled=True)
            st.text_input("API Secret", value="***" if settings.zerodha_api_secret else "", disabled=True, type="password")
        elif broker == "angelone":
            st.text_input("API Key", value="***" if settings.angelone_api_key else "", disabled=True)
            st.text_input("Client ID", value="***" if settings.angelone_client_id else "", disabled=True)
        elif broker == "upstox":
            st.text_input("API Key", value="***" if settings.upstox_api_key else "", disabled=True)
            st.text_input("API Secret", value="***" if settings.upstox_api_secret else "", disabled=True, type="password")

        paper_mode = st.toggle("📝 Paper Trading Mode", value=settings.paper_trading)
        if paper_mode:
            st.success("Paper trading active — no real money at risk")
        else:
            st.warning("⚠️ Live trading mode — real money will be used!")

    # ── LLM Settings ──
    with tab2:
        st.markdown("### AI / LLM Configuration")
        st.info("Used for natural language stock explanations. Template mode works without any API key.")

        llm = st.selectbox("LLM Provider", [p.value for p in LLMProvider],
                          index=[p.value for p in LLMProvider].index(settings.llm_provider.value))

        if llm == "openai":
            st.text_input("OpenAI API Key", value="***" if settings.openai_api_key else "",
                         disabled=True, type="password")
            st.caption("Model: gpt-4o-mini")
        elif llm == "gemini":
            st.text_input("Gemini API Key", value="***" if settings.gemini_api_key else "",
                         disabled=True, type="password")
            st.caption("Model: gemini-1.5-flash")
        else:
            st.success("Template mode — no API key needed. Uses built-in analysis templates.")

    # ── Risk Management ──
    with tab3:
        st.markdown("### Risk Management Parameters")

        col1, col2 = st.columns(2)
        with col1:
            st.number_input("Max Loss Per Trade (%)", value=settings.max_loss_per_trade_pct,
                           min_value=0.1, max_value=10.0, step=0.1, key="risk_max_loss")
            st.number_input("Daily Loss Limit (%)", value=settings.daily_loss_limit_pct,
                           min_value=0.5, max_value=20.0, step=0.5, key="risk_daily_limit")
            st.number_input("Max Open Positions", value=settings.max_open_positions,
                           min_value=1, max_value=50, step=1, key="risk_max_pos")
        with col2:
            st.number_input("Position Size (%)", value=settings.position_size_pct,
                           min_value=0.5, max_value=20.0, step=0.5, key="risk_pos_size")
            st.number_input("Trailing SL (ATR Multiplier)", value=settings.trailing_stop_atr_multiplier,
                           min_value=0.5, max_value=5.0, step=0.1, key="risk_trail_sl")
            st.number_input("Margin Min Spread (%)", value=settings.margin_min_spread_pct,
                           min_value=0.1, max_value=5.0, step=0.1, key="risk_min_spread")

        st.number_input("Prediction Min Confidence (%)", value=settings.prediction_min_confidence,
                       min_value=50.0, max_value=99.0, step=1.0, key="risk_min_conf")

        st.caption("💡 To persist these changes, update the `.env` file with the new values.")

    # ── Preferences ──
    with tab4:
        st.markdown("### Application Preferences")

        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Default Segment", [s.value for s in TradingSegment],
                        index=[s.value for s in TradingSegment].index(settings.default_segment.value),
                        key="pref_segment")
        with col2:
            st.selectbox("Default Trade Mode", [m.value for m in TradeMode],
                        index=[m.value for m in TradeMode].index(settings.default_trade_mode.value),
                        key="pref_mode")

        st.divider()

        st.markdown("### 🗄️ Database")
        st.code(f"Database path: {settings.db_path}")

        # Database stats
        pnl = db.get_pnl_summary()
        all_wl = db.get_all_watchlists()
        st.write(f"**Watchlists:** {len(all_wl)}")
        st.write(f"**Total Trades:** {pnl['total_trades']}")
        st.write(f"**Total P&L:** ₹{pnl['total_pnl']:,.2f}")
