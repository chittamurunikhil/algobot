"""
Watchlist Scanner — batch-analyze all symbols in a watchlist.
"""
import pandas as pd
from typing import List
from data.models import AnalysisResult
from data.market_feed import get_data_provider
from analysis.signal_generator import generate_signals


def scan_watchlist(symbols: List[str], segment: str = "intraday",
                   interval: str = "5min", days: int = 30) -> List[AnalysisResult]:
    """
    Run analysis on all symbols in a list.
    Returns results sorted by confidence (highest first).
    """
    provider = get_data_provider()
    results = []

    for symbol in symbols:
        try:
            df = provider.get_historical_data(symbol, interval=interval, days=days)
            if df.empty or len(df) < 50:
                continue
            result = generate_signals(df, symbol, segment)
            results.append(result)
        except Exception as e:
            # Log error but continue scanning
            results.append(AnalysisResult(
                symbol=symbol,
                segment=segment,
                explanation=f"Error analyzing: {str(e)}",
            ))

    # Sort by confidence descending, then by signal strength
    signal_priority = {"STRONG_BUY": 5, "BUY": 4, "HOLD": 3, "SELL": 2, "STRONG_SELL": 1}
    results.sort(
        key=lambda r: (signal_priority.get(r.signal.value, 3), r.confidence),
        reverse=True
    )

    return results
