"""
Watchlists Page — CRUD for 10 watchlists with batch scanning.
"""
import streamlit as st
import pandas as pd


def render_watchlists(segment: str):
    """Render the watchlist management page."""
    from watchlist.manager import WatchlistManager
    from watchlist.scanner import scan_watchlist

    st.markdown("## 📋 Watchlist Manager")

    wm = WatchlistManager()
    all_wl = wm.get_all_watchlists()

    # ── Sidebar: Create Watchlist ──
    with st.expander("➕ Create New Watchlist", expanded=len(all_wl) == 0):
        col1, col2 = st.columns(2)
        with col1:
            new_id = st.number_input("Watchlist ID (1–10)", min_value=1, max_value=10, value=len(all_wl) + 1)
        with col2:
            new_name = st.text_input("Watchlist Name", placeholder="e.g., Nifty 50 Picks")
        if st.button("Create Watchlist", key="create_wl"):
            if new_name:
                try:
                    wm.create_watchlist(new_id, new_name, segment)
                    st.success(f"✅ Created Watchlist {new_id}: '{new_name}'")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            else:
                st.warning("Please enter a name.")

    if not all_wl:
        st.info("No watchlists created yet. Create one above to get started!")
        return

    st.divider()

    # ── Watchlist Tabs ──
    tab_labels = [f"#{wl.id} {wl.name} ({wl.count})" for wl in all_wl]
    tabs = st.tabs(tab_labels)

    for i, tab in enumerate(tabs):
        wl = all_wl[i]
        with tab:
            # ── Header ──
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                with st.form(f"rename_form_{wl.id}", border=False):
                    rename_cols = st.columns([4, 1])
                    with rename_cols[0]:
                        new_name = st.text_input("Rename Watchlist", value=wl.name, key=f"rename_{wl.id}", label_visibility="collapsed")
                    with rename_cols[1]:
                        if st.form_submit_button("Rename ✏️"):
                            if new_name and new_name != wl.name:
                                wm.update_watchlist_name(wl.id, new_name)
                                st.success(f"Watchlist renamed to {new_name}")
                                st.rerun()

                st.caption(f"Segment: {wl.segment} | {wl.count} / 200 symbols | Updated: {wl.updated_at.strftime('%Y-%m-%d %H:%M')}")
            with col2:
                if st.button("🔍 Scan All", key=f"scan_{wl.id}"):
                    with st.spinner(f"Scanning {wl.count} stocks..."):
                        results = scan_watchlist(wl.symbols, segment)
                        st.session_state[f"scan_results_{wl.id}"] = results
            with col3:
                if st.button("🗑️ Delete", key=f"del_wl_{wl.id}"):
                    wm.delete_watchlist(wl.id)
                    st.success(f"Deleted Watchlist #{wl.id}")
                    st.rerun()

            # ── Add Symbols ──
            col1, col2 = st.columns([3, 1])
            with col1:
                new_symbols = st.text_input(
                    "Add symbols (comma-separated)",
                    placeholder="RELIANCE, TCS, INFY, HDFCBANK",
                    key=f"add_sym_{wl.id}",
                )
            with col2:
                st.write("")
                st.write("")
                if st.button("Add", key=f"add_btn_{wl.id}"):
                    if new_symbols:
                        syms = [s.strip().upper() for s in new_symbols.split(",") if s.strip()]
                        try:
                            wm.add_symbols_bulk(wl.id, syms)
                            st.success(f"Added {len(syms)} symbols")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

            # ── Import/Export ──
            col1, col2 = st.columns(2)
            with col1:
                uploaded = st.file_uploader("Import CSV", type=["csv", "txt"], key=f"import_{wl.id}")
                if uploaded:
                    content = uploaded.read().decode("utf-8")
                    wm.import_csv(wl.id, content)
                    st.success("Imported symbols from CSV")
                    st.rerun()
            with col2:
                if wl.symbols:
                    csv_data = wm.export_csv(wl.id)
                    st.download_button(
                        "📥 Export CSV", csv_data,
                        file_name=f"watchlist_{wl.id}_{wl.name}.csv",
                        key=f"export_{wl.id}",
                    )

            # ── Symbol Grid ──
            if wl.symbols:
                st.markdown("#### Symbols")
                # Display in a grid of chips
                cols = st.columns(10)
                for j, sym in enumerate(wl.symbols):
                    with cols[j % 10]:
                        if st.button(f"❌ {sym}", key=f"rm_{wl.id}_{sym}", help=f"Remove {sym}"):
                            wm.remove_symbol(wl.id, sym)
                            st.rerun()
            else:
                st.info("No symbols in this watchlist. Add some above!")

            # ── Scan Results ──
            scan_key = f"scan_results_{wl.id}"
            if scan_key in st.session_state:
                st.markdown("#### 🔍 Scan Results")
                results = st.session_state[scan_key]
                scan_data = []
                for r in results:
                    signal_emoji = {"STRONG_BUY": "🟢🟢", "BUY": "🟢", "HOLD": "🟡", "SELL": "🔴", "STRONG_SELL": "🔴🔴"}
                    scan_data.append({
                        "Symbol": r.symbol,
                        "Signal": f"{signal_emoji.get(r.signal.value, '')} {r.signal.value}",
                        "Confidence": f"{r.confidence:.0f}%",
                        "LTP": f"₹{r.ltp:,.2f}" if r.ltp > 0 else "—",
                        "RSI": f"{r.rsi:.1f}" if r.rsi > 0 else "—",
                        "BB %B": f"{r.bollinger_pct_b:.2f}" if r.bollinger_pct_b > 0 else "—",
                        "Trend": "📈" if r.supertrend_direction == 1 else "📉",
                    })
                st.dataframe(pd.DataFrame(scan_data), use_container_width=True, hide_index=True)
