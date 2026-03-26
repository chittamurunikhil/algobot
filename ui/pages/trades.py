"""
Trades Page — Trade history and journal with filters.
"""
import streamlit as st
import pandas as pd
from datetime import datetime


def render_trades(segment: str):
    """Render the trade history page."""
    from data.storage import get_db

    st.markdown("## 📜 Trade History & Journal")

    db = get_db()

    # ── Filters ──
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        filter_segment = st.selectbox("Segment", ["all", "delivery", "intraday", "options", "futures", "commodities", "derivatives"])
    with col2:
        filter_mode = st.selectbox("Trade Mode", ["all", "margin", "prediction"])
    with col3:
        filter_status = st.selectbox("Status", ["all", "OPEN", "CLOSED", "CANCELLED"])
    with col4:
        filter_limit = st.number_input("Show last N trades", min_value=10, max_value=500, value=50)

    # ── Fetch Trades ──
    trades = db.get_trades(
        segment=filter_segment if filter_segment != "all" else None,
        status=filter_status if filter_status != "all" else None,
        limit=filter_limit,
    )

    if filter_mode != "all":
        trades = [t for t in trades if t.mode == filter_mode]

    if not trades:
        st.info("No trades found matching the filters.")
        return

    # ── Summary Stats ──
    closed_trades = [t for t in trades if t.status.value == "CLOSED"]
    total_pnl = sum(t.pnl for t in closed_trades)
    total_commission = sum(t.commission for t in closed_trades)
    wins = len([t for t in closed_trades if t.pnl > 0])
    losses = len([t for t in closed_trades if t.pnl <= 0])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pnl_color = "normal" if total_pnl >= 0 else "inverse"
        st.metric("Total P&L", f"₹{total_pnl:,.2f}")
    with col2:
        st.metric("Total Commission", f"₹{total_commission:,.2f}")
    with col3:
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        st.metric("Win Rate", f"{win_rate:.1f}%")
    with col4:
        st.metric("Trades", f"{len(closed_trades)} closed, {len(trades) - len(closed_trades)} pending")

    st.divider()

    # ── OPEN POSITIONS MANAGEMENT ──
    from trading.order_manager import OrderManager
    from data.market_feed import get_data_provider
    om = OrderManager()
    provider = get_data_provider()

    open_trades = [t for t in trades if t.status.value == "OPEN"]
    if open_trades:
        st.markdown("### 🟢 Manage Active Positions")

        for t in open_trades:
            with st.expander(f"{t.symbol} | {t.mode.upper()} - {t.side.value} {t.quantity} @ ₹{t.entry_price:,.2f}"):
                cur_ltp = provider.get_ltp(t.symbol)
                unrealized_pnl = (cur_ltp - t.entry_price) * t.quantity if t.side.value == "BUY" else (t.entry_price - cur_ltp) * t.quantity
                unr_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"

                total_invested = t.entry_price * t.quantity
                current_value = cur_ltp * t.quantity

                st.write(
                    f"**LTP:** ₹{cur_ltp:,.2f} | "
                    f"**Invested:** ₹{total_invested:,.2f} | "
                    f"**Current Value:** ₹{current_value:,.2f} | "
                    f"**Unrealized P&L:** {unr_emoji} ₹{unrealized_pnl:,.2f}"
                )
                
                with st.form(f"edit_form_{t.id}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_sl = st.number_input("Stop Loss", value=float(t.stop_loss), step=0.5, key=f"sl_{t.id}")
                    with c2:
                        new_tp = st.number_input("Take Profit", value=float(t.take_profit), step=0.5, key=f"tp_{t.id}")
                        
                    if st.form_submit_button("💾 Update Parameters"):
                        t.stop_loss = new_sl
                        t.take_profit = new_tp
                        db.save_trade(t)
                        st.success("Updated successfully! The parameters have been saved.")
                        st.rerun()

                if st.button(f"🔴 Square Off {t.symbol} at Market (LTP: ₹{cur_ltp:,.2f})", key=f"close_{t.id}", type="primary", use_container_width=True):
                    om.close_order(t.id, cur_ltp)
                    st.success(f"Position closed at ₹{cur_ltp:,.2f}! You can refresh or view the ledger below.")
                    st.rerun()

        st.divider()

    st.markdown("### 📖 Trade Ledger")
    trade_data = []
    for t in trades:
        pnl_str = f"₹{t.pnl:,.2f}" if t.status.value == "CLOSED" else "—"
        pnl_emoji = "🟢" if t.pnl > 0 else "🔴" if t.pnl < 0 else ""

        invested = t.entry_price * t.quantity
        if t.status.value == "OPEN":
            cur_ltp = provider.get_ltp(t.symbol)
            current_value = cur_ltp * t.quantity
            current_val_str = f"₹{current_value:,.2f}"
        else:
            current_val_str = "—"

        trade_data.append({
            "Date": t.created_at.strftime("%Y-%m-%d %H:%M"),
            "Symbol": t.symbol,
            "Segment": t.segment.upper(),
            "Mode": t.mode.upper(),
            "Side": t.side.value,
            "Entry": f"₹{t.entry_price:,.2f}",
            "Exit": f"₹{t.exit_price:,.2f}" if t.exit_price else "—",
            "Qty": t.quantity,
            "Invested": f"₹{invested:,.2f}",
            "Current Value": current_val_str,
            "SL": f"₹{t.stop_loss:,.2f}" if t.stop_loss > 0 else "—",
            "TP": f"₹{t.take_profit:,.2f}" if t.take_profit > 0 else "—",
            "P&L": f"{pnl_emoji} {pnl_str}",
            "Status": t.status.value,
            "Confidence": f"{t.confidence_score:.0f}%",
        })

    st.dataframe(
        pd.DataFrame(trade_data),
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    # ── P&L Chart ──
    if closed_trades:
        st.markdown("### 📈 Cumulative P&L")
        pnl_series = pd.DataFrame({
            "Date": [t.closed_at or t.created_at for t in closed_trades],
            "P&L": [t.pnl for t in closed_trades],
        }).sort_values("Date")
        pnl_series["Cumulative P&L"] = pnl_series["P&L"].cumsum()

        st.line_chart(pnl_series.set_index("Date")["Cumulative P&L"])

    # ── Trade by Mode Distribution ──
    st.markdown("### 📊 Trade Distribution")
    col1, col2 = st.columns(2)

    with col1:
        mode_counts = pd.DataFrame(trades).groupby(
            pd.DataFrame([{"mode": t.mode} for t in trades])["mode"]
        ).size() if trades else pd.Series()
        if not mode_counts.empty:
            import plotly.express as px
            fig = px.pie(values=mode_counts.values, names=mode_counts.index,
                        title="By Trade Mode", hole=0.4)
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if closed_trades:
            margin_pnl = sum(t.pnl for t in closed_trades if t.mode == "margin")
            pred_pnl = sum(t.pnl for t in closed_trades if t.mode == "prediction")
            import plotly.graph_objects as go
            fig = go.Figure(go.Bar(
                x=["Margin", "Prediction"],
                y=[margin_pnl, pred_pnl],
                marker_color=["#4ecdc4", "#ff6b6b"],
            ))
            fig.update_layout(title="P&L by Mode", template="plotly_dark",
                            paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
