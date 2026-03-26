"""
AlgoBot — Multi-Segment Trading Application
Main Streamlit entry point with navigation and segment selector.
"""
import streamlit as st
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ══════════════════════════════════════════════════════════════════════════════
# Page Config
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AlgoBot — Multi-Segment Trading",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# Custom CSS
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    /* Dark theme enhancements */
    .stApp {
        background-color: #f8f9fa;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0e1117 0%, #1a1f2e 100%);
        border-right: 1px solid #2d3748;
    }

    /* Header gradient */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
        text-align: center;
        color: white;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1f2e 0%, #2d3748 100%);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #374151;
    }

    [data-testid="stMetricLabel"] {
        color: #9ca3af;
        font-size: 0.85rem;
    }

    [data-testid="stMetricValue"] {
        font-weight: 700;
        color: #f9fafb;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #1a1f2e;
        border-radius: 8px;
        border: 1px solid #374151;
        padding: 8px 16px;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none;
    }

    /* Dataframes */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }

    /* Info/Warning/Success boxes */
    .stAlert {
        border-radius: 10px;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }

    /* Segment badge */
    .segment-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .segment-delivery { background: #065f46; color: #6ee7b7; }
    .segment-intraday { background: #1e40af; color: #93c5fd; }
    .segment-options { background: #7c2d12; color: #fdba74; }
    .segment-futures { background: #581c87; color: #d8b4fe; }
    .segment-commodities { background: #713f12; color: #fcd34d; }
    .segment-derivatives { background: #831843; color: #f9a8d4; }

    /* Divider */
    hr {
        border-color: #2d3748;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <h1 style="font-size: 2rem; margin: 0; background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🤖 AlgoBot
        </h1>
        <p style="color: #9ca3af; font-size: 0.85rem; margin: 5px 0 0 0;">
            Multi-Segment Trading Engine
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Segment Selector
    st.markdown("### 🏷️ Trading Segment")
    segments = {
        "📦 Delivery": "delivery",
        "⚡ Intraday": "intraday",
        "📊 Options": "options",
        "📈 Futures": "futures",
        "🛢️ Commodities": "commodities",
        "🔄 Derivatives": "derivatives",
    }
    selected_label = st.radio(
        "Select segment",
        list(segments.keys()),
        index=1,
        label_visibility="collapsed",
    )
    segment = segments[selected_label]

    st.divider()

    # Navigation
    st.markdown("### 🧭 Navigation")
    pages = {
        "📊 Dashboard": "dashboard",
        "🔬 Analysis": "analysis",
        "📋 Watchlists": "watchlists",
        "📜 Trades": "trades",
        "⚙️ Settings": "settings",
    }
    selected_page = st.radio(
        "Go to",
        list(pages.keys()),
        label_visibility="collapsed",
    )
    page = pages[selected_page]

    st.divider()

    # Quick Info
    from config.settings import get_settings
    settings = get_settings()
    mode_emoji = "📝" if settings.paper_trading else "💰"
    st.markdown(f"""
    <div style="background: #1a1f2e; padding: 12px; border-radius: 10px; border: 1px solid #374151;">
        <p style="margin: 0; font-size: 0.85rem; color: #9ca3af;">Mode</p>
        <p style="margin: 0; font-size: 0.95rem; color: #f9fafb;">{mode_emoji} {'Paper Trading' if settings.paper_trading else 'Live Trading'}</p>
        <br>
        <p style="margin: 0; font-size: 0.85rem; color: #9ca3af;">Broker</p>
        <p style="margin: 0; font-size: 0.95rem; color: #f9fafb;">🏦 {settings.broker_name.value.title()}</p>
        <br>
        <p style="margin: 0; font-size: 0.85rem; color: #9ca3af;">LLM</p>
        <p style="margin: 0; font-size: 0.95rem; color: #f9fafb;">🤖 {settings.llm_provider.value.title()}</p>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Main Content
# ══════════════════════════════════════════════════════════════════════════════

# Header
segment_class = f"segment-{segment}"
st.markdown(f"""
<div class="main-header">
    <h1 style="margin: 0; font-size: 1.8rem;">🤖 AlgoBot Trading Engine</h1>
    <p style="margin: 5px 0; opacity: 0.9;">
        <span class="segment-badge {segment_class}">{segment.upper()}</span>
        &nbsp;|&nbsp; Multi-Segment Intelligent Trading
    </p>
</div>
""", unsafe_allow_html=True)

# Route to pages
if page == "dashboard":
    from ui.pages.dashboard import render_dashboard
    render_dashboard(segment)
elif page == "analysis":
    from ui.pages.analysis import render_analysis
    render_analysis(segment)
elif page == "watchlists":
    from ui.pages.watchlists import render_watchlists
    render_watchlists(segment)
elif page == "trades":
    from ui.pages.trades import render_trades
    render_trades(segment)
elif page == "settings":
    from ui.pages.settings_page import render_settings
    render_settings()
