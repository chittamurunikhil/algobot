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

    from config.settings import update_settings
    
    with st.form("settings_form"):
        tab1, tab2, tab3, tab4 = st.tabs(["🏦 Broker", "🤖 AI/LLM", "⚠️ Risk Management", "📊 Preferences"])

        # ── Broker Settings ──
        with tab1:
            st.markdown("### Broker API Configuration")
            st.info("💡 Configure your broker API keys in the `.env` file for security. These menus change modes.")

            broker = st.selectbox("Active Broker", [b.value for b in BrokerName],
                                 index=[b.value for b in BrokerName].index(settings.broker_name.value))

            if broker == "zerodha":
                st.text_input("API Key", value="***" if settings.zerodha_api_key else "", disabled=True)
            elif broker == "angelone":
                st.text_input("API Key", value="***" if settings.angelone_api_key else "", disabled=True)
            elif broker == "upstox":
                st.text_input("API Key", value="***" if settings.upstox_api_key else "", disabled=True)

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
            elif llm == "gemini":
                st.text_input("Gemini API Key", value="***" if settings.gemini_api_key else "",
                             disabled=True, type="password")
            else:
                st.success("Template mode — no API key needed.")

        # ── Risk Management ──
        with tab3:
            st.markdown("### Risk Management Parameters")

            col1, col2 = st.columns(2)
            with col1:
                max_loss = st.number_input("Max Loss Per Trade (%)", value=settings.max_loss_per_trade_pct,
                               min_value=0.1, max_value=10.0, step=0.1)
                daily_limit = st.number_input("Daily Loss Limit (%)", value=settings.daily_loss_limit_pct,
                               min_value=0.5, max_value=20.0, step=0.5)
                max_pos = st.number_input("Max Open Positions", value=settings.max_open_positions,
                               min_value=1, max_value=50, step=1)
            with col2:
                pos_size = st.number_input("Position Size (%)", value=settings.position_size_pct,
                               min_value=0.5, max_value=20.0, step=0.5)
                trail_sl = st.number_input("Trailing SL (ATR Multiplier)", value=settings.trailing_stop_atr_multiplier,
                               min_value=0.5, max_value=5.0, step=0.1)
                min_spread = st.number_input("Margin Min Spread (%)", value=settings.margin_min_spread_pct,
                               min_value=0.1, max_value=5.0, step=0.1)

            min_conf = st.number_input("Prediction Min Confidence (%)", value=settings.prediction_min_confidence,
                           min_value=50.0, max_value=99.0, step=1.0)

        # ── Preferences ──
        with tab4:
            st.markdown("### Application Preferences")

            col1, col2 = st.columns(2)
            with col1:
                pref_seg = st.selectbox("Default Segment", [s.value for s in TradingSegment],
                            index=[s.value for s in TradingSegment].index(settings.default_segment.value))
            with col2:
                pref_mode = st.selectbox("Default Trade Mode", [m.value for m in TradeMode],
                            index=[m.value for m in TradeMode].index(settings.default_trade_mode.value))

            st.divider()

            st.markdown("### 🗄️ Database")
            st.code(f"Database path: {settings.db_path}")

            # Database stats
            pnl = db.get_pnl_summary()
            all_wl = db.get_all_watchlists()
            st.write(f"**Watchlists:** {len(all_wl)}")
            st.write(f"**Total Trades:** {pnl['total_trades']}")
            st.write(f"**Total P&L:** ₹{pnl['total_pnl']:,.2f}")
            
        submitted = st.form_submit_button("💾 Save Settings", type="primary")
        
        if submitted:
            updates = {
                "broker_name": broker,
                "paper_trading": paper_mode,
                "llm_provider": llm,
                "max_loss_per_trade_pct": max_loss,
                "daily_loss_limit_pct": daily_limit,
                "max_open_positions": max_pos,
                "position_size_pct": pos_size,
                "trailing_stop_atr_multiplier": trail_sl,
                "margin_min_spread_pct": min_spread,
                "prediction_min_confidence": min_conf,
                "default_segment": pref_seg,
                "default_trade_mode": pref_mode,
            }
            update_settings(updates)
            st.success("✅ Settings saved successfully! The app is now using the updated configuration.")
            st.rerun()
