"""
Chart Components — Plotly candlestick charts with indicator overlays.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from data.models import AnalysisResult


def create_candlestick_chart(df: pd.DataFrame, symbol: str,
                              analysis: AnalysisResult = None,
                              show_bollinger: bool = True,
                              show_ema: bool = True,
                              show_volume: bool = True) -> go.Figure:
    """
    Create an interactive candlestick chart with indicator overlays.
    """
    from analysis.indicators import compute_all_indicators

    data = compute_all_indicators(df)

    # Create subplots: price + volume + RSI + MACD
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.2],
        subplot_titles=(f"{symbol} — Price", "Volume", "RSI", "MACD"),
    )

    # ── Row 1: Candlestick ──
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        name="Price",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ), row=1, col=1)

    # Bollinger Bands
    if show_bollinger and "bollinger_upper" in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index, y=data["bollinger_upper"],
            line=dict(color="rgba(173,216,230,0.6)", width=1),
            name="BB Upper", showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["bollinger_lower"],
            line=dict(color="rgba(173,216,230,0.6)", width=1),
            fill="tonexty", fillcolor="rgba(173,216,230,0.1)",
            name="BB Lower", showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["bollinger_mid"],
            line=dict(color="rgba(255,165,0,0.5)", width=1, dash="dash"),
            name="BB Mid (SMA20)",
        ), row=1, col=1)

    # EMAs
    if show_ema and "ema_9" in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index, y=data["ema_9"],
            line=dict(color="#ff6b6b", width=1.5),
            name="EMA 9",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["ema_21"],
            line=dict(color="#4ecdc4", width=1.5),
            name="EMA 21",
        ), row=1, col=1)

    # VWAP
    if "vwap" in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index, y=data["vwap"],
            line=dict(color="#ffd93d", width=1.5, dash="dot"),
            name="VWAP",
        ), row=1, col=1)

    # Supertrend
    if "supertrend" in data.columns:
        colors = ["#26a69a" if d == 1 else "#ef5350" for d in data["supertrend_direction"]]
        fig.add_trace(go.Scatter(
            x=data.index, y=data["supertrend"],
            line=dict(color="#9c27b0", width=2),
            name="Supertrend",
        ), row=1, col=1)

    # Demand/Supply zones
    if analysis:
        for zone in analysis.demand_zones[:2]:
            fig.add_hrect(
                y0=zone.price_low, y1=zone.price_high,
                fillcolor="rgba(0,255,0,0.08)", line_width=0,
                annotation_text=f"Demand ({zone.strength:.0f}%)",
                annotation_position="left",
                row=1, col=1,
            )
        for zone in analysis.supply_zones[:2]:
            fig.add_hrect(
                y0=zone.price_low, y1=zone.price_high,
                fillcolor="rgba(255,0,0,0.08)", line_width=0,
                annotation_text=f"Supply ({zone.strength:.0f}%)",
                annotation_position="left",
                row=1, col=1,
            )

    # ── Row 2: Volume ──
    if show_volume:
        colors = ["#26a69a" if c >= o else "#ef5350"
                  for c, o in zip(data["close"], data["open"])]
        fig.add_trace(go.Bar(
            x=data.index, y=data["volume"],
            marker_color=colors, name="Volume",
            showlegend=False,
        ), row=2, col=1)

    # ── Row 3: RSI ──
    if "rsi" in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index, y=data["rsi"],
            line=dict(color="#ab47bc", width=1.5),
            name="RSI(14)",
        ), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
        fig.add_hrect(y0=30, y1=70, fillcolor="rgba(128,128,128,0.05)", line_width=0, row=3, col=1)

    # ── Row 4: MACD ──
    if "macd_line" in data.columns:
        fig.add_trace(go.Scatter(
            x=data.index, y=data["macd_line"],
            line=dict(color="#2196F3", width=1.5),
            name="MACD",
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["macd_signal"],
            line=dict(color="#FF9800", width=1.5),
            name="Signal",
        ), row=4, col=1)

        hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in data["macd_histogram"]]
        fig.add_trace(go.Bar(
            x=data.index, y=data["macd_histogram"],
            marker_color=hist_colors, name="Histogram",
            showlegend=False,
        ), row=4, col=1)

    # ── Layout ──
    fig.update_layout(
        height=900,
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#fafafa", size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=20, t=50, b=20),
    )

    fig.update_xaxes(gridcolor="#1e2530")
    fig.update_yaxes(gridcolor="#1e2530")

    return fig


def create_mini_chart(df: pd.DataFrame, symbol: str, height: int = 200) -> go.Figure:
    """Create a small sparkline chart for watchlist cards."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df.index[-50:] if len(df) > 50 else df.index,
        y=df["close"].tail(50),
        mode="lines",
        line=dict(
            color="#26a69a" if df["close"].iloc[-1] >= df["close"].iloc[-2] else "#ef5350",
            width=2,
        ),
        fill="tozeroy",
        fillcolor="rgba(38,166,154,0.1)" if df["close"].iloc[-1] >= df["close"].iloc[-2] else "rgba(239,83,80,0.1)",
        showlegend=False,
    ))

    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )

    return fig
