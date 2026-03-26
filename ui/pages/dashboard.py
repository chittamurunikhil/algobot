"""
Dashboard Page — Main overview with P&L, active signals, and positions.
"""
import streamlit as st
import pandas as pd
from datetime import datetime


def render_dashboard(segment: str):
    """Render the main dashboard page."""
    from data.storage import get_db
    from data.market_feed import get_data_provider
    from analysis.signal_generator import generate_signals
    from trading.risk_manager import RiskManager

    db = get_db()
    provider = get_data_provider()

    st.markdown("## 📊 Dashboard")

    # ── P&L Summary Cards ──
    pnl = db.get_pnl_summary()
    risk = RiskManager()
    daily_stats = risk.get_daily_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pnl_color = "🟢" if pnl["today_pnl"] >= 0 else "🔴"
        st.metric("Today's P&L", f"₹{pnl['today_pnl']:,.2f}", delta=f"{pnl_color}")
    with col2:
        st.metric("Total P&L", f"₹{pnl['total_pnl']:,.2f}")
    with col3:
        st.metric("Win Rate", f"{pnl['win_rate']:.1f}%", delta=f"{pnl['win_count']}W / {pnl['loss_count']}L")
    with col4:
        st.metric("Commission Earned", f"₹{pnl['total_commission']:,.2f}")

    st.divider()

    # ── Risk Status ──
    col1, col2, col3 = st.columns(3)
    with col1:
        status = "✅ Trading Active" if daily_stats["can_trade"] else "⛔ Trading Paused"
        st.info(f"**Status:** {status}")
    with col2:
        st.info(f"**Open Positions:** {daily_stats['open_positions']} / {daily_stats['max_positions']}")
    with col3:
        st.info(f"**Loss Remaining:** ₹{daily_stats['loss_remaining']:,.2f}")

    st.divider()

    # ── Quick Scan — Top Stocks ──
    st.markdown("### 🔍 Quick Market Scan")
    
    # Try to load symbols from the first available watchlist
    all_wl = db.get_all_watchlists()
    if all_wl and all_wl[0].symbols:
        scan_symbols = all_wl[0].symbols[:10]  # Take top 10 from the first watchlist
        st.caption(f"Scanning top {len(scan_symbols)} stocks from watchlist '{all_wl[0].name}'")
    else:
        # Fallback if no watchlists exist
        scan_symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
        st.caption("Scanning default stocks (create a watchlist to customize)")

    results = []
    for sym in scan_symbols:
        try:
            df = provider.get_historical_data(sym, interval="5min", days=10)
            if not df.empty and len(df) >= 50:
                r = generate_signals(df, sym, segment)
                results.append({
                    "Symbol": sym,
                    "LTP": f"₹{r.ltp:,.2f}",
                    "Signal": r.signal.value,
                    "Confidence": f"{r.confidence:.0f}%",
                    "RSI": f"{r.rsi:.1f}",
                    "BB %B": f"{r.bollinger_pct_b:.2f}",
                    "Trend": "📈 Bullish" if r.supertrend_direction == 1 else "📉 Bearish",
                })
        except Exception:
            pass

    if results:
        scan_df = pd.DataFrame(results)
        st.dataframe(
            scan_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Signal": st.column_config.TextColumn("Signal", width="small"),
                "Confidence": st.column_config.TextColumn("Confidence", width="small"),
            },
        )
    else:
        st.info("No scan results available. Run a watchlist scan first.")

    st.divider()

    # ── Open Positions ──
    st.markdown("### 📋 Open Positions")
    open_trades = db.get_trades(status="OPEN")
    if open_trades:
        trade_data = []
        for t in open_trades:
            trade_data.append({
                "Symbol": t.symbol,
                "Side": t.side.value,
                "Mode": t.mode.upper(),
                "Entry": f"₹{t.entry_price:,.2f}",
                "SL": f"₹{t.stop_loss:,.2f}",
                "TP": f"₹{t.take_profit:,.2f}",
                "Qty": t.quantity,
                "Confidence": f"{t.confidence_score:.0f}%",
                "Opened": t.created_at.strftime("%H:%M:%S"),
            })
        st.dataframe(pd.DataFrame(trade_data), use_container_width=True, hide_index=True)
    else:
        st.info("No open positions.")

    # ── Recent Trades ──
    st.markdown("### 📜 Recent Trades")
    recent = db.get_trades(limit=10)
    closed_trades = [t for t in recent if t.status.value == "CLOSED"]
    if closed_trades:
        trade_data = []
        for t in closed_trades[:5]:
            pnl_emoji = "🟢" if t.pnl >= 0 else "🔴"
            trade_data.append({
                "Symbol": t.symbol,
                "Side": t.side.value,
                "Mode": t.mode.upper(),
                "Entry": f"₹{t.entry_price:,.2f}",
                "Exit": f"₹{t.exit_price:,.2f}" if t.exit_price else "—",
                "P&L": f"{pnl_emoji} ₹{t.pnl:,.2f}",
                "Date": t.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        st.dataframe(pd.DataFrame(trade_data), use_container_width=True, hide_index=True)
    else:
        st.info("No closed trades yet.")
