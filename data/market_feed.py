"""
Market Data Feed — Real-time data via yfinance with intelligent fallback.
Supports Indian stocks (NSE/BSE), global equities, commodities, indices, and crypto.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Symbol Mapping — Auto-resolves to correct exchange suffix
# ══════════════════════════════════════════════════════════════════════════════

EXCHANGE_SUFFIXES = {
    "nse": ".NS",
    "bse": ".BO",
    "mcx": ".NS",   # MCX commodities via NSE proxy
    "nasdaq": "",
    "nyse": "",
    "crypto": "-USD",
}

# Common Indian stock symbols that need .NS suffix
KNOWN_NSE_SYMBOLS = {
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL",
    "ITC", "HINDUNILVR", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE",
    "TATAMOTORS", "MARUTI", "WIPRO", "HCLTECH", "ADANIENT", "ADANIPORTS",
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "ULTRACEMCO", "TITAN", "NESTLEIND",
    "BAJAJFINSV", "POWERGRID", "NTPC", "SUNPHARMA", "DRREDDY", "CIPLA",
    "DIVISLAB", "APOLLOHOSP", "ASIANPAINT", "HEROMOTOCO", "EICHERMOT",
    "TECHM", "ONGC", "COALINDIA", "BPCL", "GRASIM", "TATACONSUM",
    "BRITANNIA", "BAJAJ-AUTO", "INDUSINDBK", "SBILIFE", "HDFCLIFE",
    "UPL", "M&M", "SHREECEM",
}

# Index symbols
INDEX_SYMBOLS = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "NIFTYIT": "^CNXIT",
    "NIFTYPHARMA": "^CNXPHARMA",
}

# Commodity symbols
COMMODITY_SYMBOLS = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "CRUDEOIL": "CL=F",
    "CRUDE": "CL=F",
    "NATURALGAS": "NG=F",
    "COPPER": "HG=F",
}

# Interval mapping: our notation → yfinance notation
INTERVAL_MAP = {
    "1min": "1m",
    "2min": "2m",
    "5min": "5m",
    "15min": "15m",
    "30min": "30m",
    "60min": "60m",
    "1h": "1h",
    "1day": "1d",
    "1week": "1wk",
    "1month": "1mo",
}

# Max period allowed per interval in yfinance
MAX_DAYS_FOR_INTERVAL = {
    "1m": 7,
    "2m": 60,
    "5m": 60,
    "15m": 60,
    "30m": 60,
    "60m": 730,
    "1h": 730,
    "1d": 10000,
    "1wk": 10000,
    "1mo": 10000,
}


def resolve_symbol(symbol: str) -> str:
    """
    Resolve a user-friendly symbol to a yfinance-compatible ticker.
    - Indian stocks: RELIANCE → RELIANCE.NS
    - Indices: NIFTY → ^NSEI
    - Commodities: GOLD → GC=F
    - Already suffixed: pass through
    """
    symbol = symbol.upper().strip()

    # Check index mapping first
    if symbol in INDEX_SYMBOLS:
        return INDEX_SYMBOLS[symbol]

    # Check commodity mapping
    if symbol in COMMODITY_SYMBOLS:
        return COMMODITY_SYMBOLS[symbol]

    # If already has a suffix (.NS, .BO, etc.) or special chars, pass through
    if "." in symbol or "^" in symbol or "=" in symbol or "-USD" in symbol:
        return symbol

    # Check known NSE symbols
    if symbol in KNOWN_NSE_SYMBOLS:
        return f"{symbol}.NS"

    # Default: try as NSE stock
    return f"{symbol}.NS"


def get_display_symbol(yf_symbol: str) -> str:
    """Convert yfinance symbol back to display name."""
    for display, yf in INDEX_SYMBOLS.items():
        if yf == yf_symbol:
            return display
    for display, yf in COMMODITY_SYMBOLS.items():
        if yf == yf_symbol:
            return display
    return yf_symbol.replace(".NS", "").replace(".BO", "")


# ══════════════════════════════════════════════════════════════════════════════
# Market Data Provider
# ══════════════════════════════════════════════════════════════════════════════

class MarketDataProvider:
    """Abstract market data provider interface."""

    def get_historical_data(self, symbol: str, interval: str = "5min",
                            days: int = 30) -> pd.DataFrame:
        raise NotImplementedError

    def get_ltp(self, symbol: str) -> float:
        raise NotImplementedError

    def get_quote(self, symbol: str) -> dict:
        raise NotImplementedError

    def search_symbols(self, query: str) -> List[dict]:
        raise NotImplementedError


class YFinanceProvider(MarketDataProvider):
    """
    Real-time market data via yfinance.
    Supports NSE/BSE stocks, global indices, commodities, and crypto.
    """

    def __init__(self):
        try:
            import yfinance as yf
            self.yf = yf
            self._available = True
        except ImportError:
            logger.warning("yfinance not installed. Run: pip install yfinance")
            self._available = False

        self._cache: Dict[str, tuple] = {}  # symbol -> (timestamp, data)
        self._cache_ttl = 60  # Cache TTL in seconds

    def get_historical_data(self, symbol: str, interval: str = "5min",
                            days: int = 30) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Yahoo Finance.
        Auto-resolves Indian stock symbols and handles interval limits.
        """
        if not self._available:
            return pd.DataFrame()

        yf_symbol = resolve_symbol(symbol)
        yf_interval = INTERVAL_MAP.get(interval, "5m")

        # Clamp days to max allowed for the interval
        max_days = MAX_DAYS_FOR_INTERVAL.get(yf_interval, 60)
        days = min(days, max_days)

        # Check cache
        cache_key = f"{yf_symbol}_{yf_interval}_{days}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now() - cached_time).seconds < self._cache_ttl:
                return cached_data

        try:
            ticker = self.yf.Ticker(yf_symbol)

            # Calculate period
            if yf_interval in ("1m", "2m"):
                # For minute intervals, use period parameter
                period_map = {1: "1d", 2: "2d", 3: "3d", 5: "5d", 7: "5d"}
                period = period_map.get(days, f"{min(days, 7)}d")
                df = ticker.history(period=period, interval=yf_interval)
            else:
                start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                end_date = datetime.now().strftime("%Y-%m-%d")
                df = ticker.history(start=start_date, end=end_date, interval=yf_interval)

            if df.empty:
                logger.warning(f"No data returned for {yf_symbol} ({interval}, {days}d)")
                return pd.DataFrame()

            # Standardize column names to lowercase
            df.columns = [c.lower() for c in df.columns]

            # Ensure required columns exist
            required = ["open", "high", "low", "close", "volume"]
            for col in required:
                if col not in df.columns:
                    logger.warning(f"Missing column '{col}' for {yf_symbol}")
                    return pd.DataFrame()

            # Clean data
            df = df[required].copy()
            df.dropna(inplace=True)

            # Remove zero-volume rows (holidays/gaps)
            df = df[df["volume"] > 0]

            # Cache result
            self._cache[cache_key] = (datetime.now(), df)

            logger.info(f"Fetched {len(df)} candles for {yf_symbol} ({yf_interval}, {days}d)")
            return df

        except Exception as e:
            logger.error(f"Error fetching data for {yf_symbol}: {e}")
            return pd.DataFrame()

    def get_ltp(self, symbol: str) -> float:
        """Get last traded price."""
        if not self._available:
            return 0.0

        try:
            yf_symbol = resolve_symbol(symbol)
            ticker = self.yf.Ticker(yf_symbol)
            info = ticker.fast_info
            return float(info.get("lastPrice", 0) or info.get("last_price", 0) or 0)
        except Exception as e:
            logger.error(f"Error getting LTP for {symbol}: {e}")
            return 0.0

    def get_quote(self, symbol: str) -> dict:
        """Get full quote for a symbol."""
        if not self._available:
            return {}

        try:
            yf_symbol = resolve_symbol(symbol)
            ticker = self.yf.Ticker(yf_symbol)

            # Get today's data
            df = ticker.history(period="1d", interval="1m")
            if df.empty:
                df = ticker.history(period="5d", interval="1d")

            if df.empty:
                return {"symbol": symbol, "error": "No data available"}

            df.columns = [c.lower() for c in df.columns]

            info = {}
            try:
                fi = ticker.fast_info
                info = {
                    "market_cap": getattr(fi, "market_cap", None),
                    "shares": getattr(fi, "shares", None),
                }
            except Exception:
                pass

            day_open = df.iloc[0]["open"]
            latest_close = df.iloc[-1]["close"]
            change = latest_close - day_open
            change_pct = (change / day_open * 100) if day_open > 0 else 0

            return {
                "symbol": get_display_symbol(yf_symbol),
                "yf_symbol": yf_symbol,
                "ltp": round(latest_close, 2),
                "open": round(day_open, 2),
                "high": round(df["high"].max(), 2),
                "low": round(df["low"].min(), 2),
                "close": round(latest_close, 2),
                "volume": int(df["volume"].sum()),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                **info,
            }

        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def search_symbols(self, query: str) -> List[dict]:
        """Search for stock symbols matching a query."""
        if not self._available:
            return []

        try:
            # Search via yfinance
            results = self.yf.Search(query)
            quotes = results.quotes if hasattr(results, 'quotes') else []

            return [
                {
                    "symbol": q.get("symbol", ""),
                    "name": q.get("shortname", q.get("longname", "")),
                    "exchange": q.get("exchange", ""),
                    "type": q.get("quoteType", ""),
                }
                for q in quotes[:20]
            ]
        except Exception as e:
            logger.error(f"Search error for '{query}': {e}")
            return []

    def clear_cache(self):
        """Clear the data cache."""
        self._cache.clear()


class MockDataProvider(MarketDataProvider):
    """
    Fallback mock data provider — used when yfinance is unavailable.
    Generates synthetic data using geometric Brownian motion.
    """

    def get_historical_data(self, symbol: str, interval: str = "5min",
                            days: int = 30) -> pd.DataFrame:
        """Generate synthetic OHLCV data."""
        base_price = hash(symbol.upper()) % 5000 + 500
        volatility = 0.02

        interval_minutes = {"1min": 1, "5min": 5, "15min": 15, "30min": 30,
                           "60min": 60, "1h": 60, "1day": 375}.get(interval, 5)

        trading_minutes = 375
        candles_per_day = trading_minutes // interval_minutes
        timestamps = self._generate_market_timestamps(days, interval_minutes)
        total_candles = len(timestamps)

        if total_candles == 0:
            return pd.DataFrame()

        np.random.seed(hash(symbol.upper()) % (2**31))
        returns = np.random.normal(0.0001, volatility / np.sqrt(max(candles_per_day, 1)), total_candles)
        prices = base_price * np.cumprod(1 + returns)

        data = []
        for i, ts in enumerate(timestamps):
            close = prices[i]
            noise = volatility * close
            open_p = close + np.random.uniform(-noise * 0.3, noise * 0.3)
            high = max(open_p, close) + abs(np.random.normal(0, noise * 0.5))
            low = min(open_p, close) - abs(np.random.normal(0, noise * 0.5))
            volume = int(np.random.lognormal(mean=12, sigma=1.5))
            data.append({"timestamp": ts, "open": round(open_p, 2), "high": round(high, 2),
                         "low": round(low, 2), "close": round(close, 2), "volume": volume})

        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df

    def get_ltp(self, symbol: str) -> float:
        df = self.get_historical_data(symbol, "1min", 1)
        return df["close"].iloc[-1] if not df.empty else 0.0

    def get_quote(self, symbol: str) -> dict:
        df = self.get_historical_data(symbol, "1min", 1)
        if df.empty:
            return {}
        return {
            "symbol": symbol.upper(), "ltp": df.iloc[-1]["close"],
            "open": df.iloc[0]["open"], "high": df["high"].max(),
            "low": df["low"].min(), "close": df.iloc[-1]["close"],
            "volume": int(df["volume"].sum()),
            "change": df.iloc[-1]["close"] - df.iloc[0]["open"],
            "change_pct": ((df.iloc[-1]["close"] - df.iloc[0]["open"]) / df.iloc[0]["open"]) * 100,
        }

    def search_symbols(self, query: str) -> List[dict]:
        return []

    def _generate_market_timestamps(self, days: int, interval_minutes: int) -> List[datetime]:
        timestamps = []
        current_date = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        current_date -= timedelta(days=days)
        for d in range(days):
            date = current_date + timedelta(days=d)
            if date.weekday() >= 5:
                continue
            market_open = date.replace(hour=9, minute=15)
            market_close = date.replace(hour=15, minute=30)
            t = market_open
            while t <= market_close:
                timestamps.append(t)
                t += timedelta(minutes=interval_minutes)
        return timestamps


# ══════════════════════════════════════════════════════════════════════════════
# Factory
# ══════════════════════════════════════════════════════════════════════════════

_provider: Optional[MarketDataProvider] = None


def get_data_provider(force_mock: bool = False) -> MarketDataProvider:
    """
    Factory: returns YFinanceProvider if available, else MockDataProvider.
    Set force_mock=True to always use mock data.
    """
    global _provider

    if _provider is not None and not force_mock:
        return _provider

    if force_mock:
        _provider = MockDataProvider()
    else:
        try:
            import yfinance
            _provider = YFinanceProvider()
            logger.info("Using YFinance for real-time market data")
        except ImportError:
            logger.warning("yfinance not available, falling back to mock data")
            _provider = MockDataProvider()

    return _provider
