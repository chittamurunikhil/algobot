"""
Data models for all trading segments.
Uses Python dataclasses for lightweight, serializable structures.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
import uuid


# ══════════════════════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════════════════════

class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OptionType(str, Enum):
    CALL = "CE"
    PUT = "PE"


# ══════════════════════════════════════════════════════════════════════════════
# Market Data Models
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StockTick:
    """OHLCV tick data — used for equity delivery & intraday."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    ltp: float = 0.0  # Last Traded Price

    def __post_init__(self):
        if self.ltp == 0.0:
            self.ltp = self.close


@dataclass
class OptionData:
    """Option chain entry."""
    symbol: str
    underlying: str
    expiry: datetime
    strike: float
    option_type: OptionType
    ltp: float
    open_interest: int
    volume: int
    iv: float  # Implied Volatility
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FuturesData:
    """Futures contract data."""
    symbol: str
    underlying: str
    expiry: datetime
    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int
    lot_size: int = 1
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CommodityTick:
    """Commodity data (MCX/NCDEX)."""
    symbol: str
    exchange: str  # MCX, NCDEX
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    ltp: float
    lot_size: int = 1
    expiry: Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# Analysis & Signal Models
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DemandSupplyZone:
    """A single demand or supply zone."""
    zone_type: str  # "demand" or "supply"
    price_low: float
    price_high: float
    strength: float  # 0-100
    volume_concentration: float


@dataclass
class AnalysisResult:
    """Complete analysis output for a symbol."""
    symbol: str
    segment: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Price
    ltp: float = 0.0

    # MAD
    mad_5: float = 0.0
    mad_10: float = 0.0
    mad_20: float = 0.0
    mad_50: float = 0.0

    # Bollinger Bands
    bollinger_upper: float = 0.0
    bollinger_mid: float = 0.0
    bollinger_lower: float = 0.0
    bollinger_width: float = 0.0
    bollinger_pct_b: float = 0.0

    # Demand / Supply
    demand_zones: List[DemandSupplyZone] = field(default_factory=list)
    supply_zones: List[DemandSupplyZone] = field(default_factory=list)

    # Additional Indicators
    rsi: float = 0.0
    vwap: float = 0.0
    ema_9: float = 0.0
    ema_21: float = 0.0
    macd_line: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    atr: float = 0.0
    supertrend: float = 0.0
    supertrend_direction: int = 1  # 1=bullish, -1=bearish

    # Option-specific (if segment is options)
    iv: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0

    # Futures-specific
    open_interest: int = 0
    oi_change: float = 0.0

    # Signal
    signal: Signal = Signal.HOLD
    confidence: float = 0.0
    explanation: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# Watchlist
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Watchlist:
    """A named watchlist containing up to 200 symbols."""
    id: int  # 1–10
    name: str
    symbols: List[str] = field(default_factory=list)
    segment: str = "intraday"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def count(self) -> int:
        return len(self.symbols)

    def is_full(self) -> bool:
        return len(self.symbols) >= 200


# ══════════════════════════════════════════════════════════════════════════════
# Trade Records
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TradeRecord:
    """Logged trade — supports all segments and both trading modes."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    segment: str = "intraday"
    mode: str = "prediction"  # "margin" or "prediction"
    side: OrderSide = OrderSide.BUY
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    quantity: int = 0
    lot_size: int = 1
    status: TradeStatus = TradeStatus.PENDING
    pnl: float = 0.0
    commission: float = 0.0
    confidence_score: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    strategy_notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None

    @property
    def is_open(self) -> bool:
        return self.status in (TradeStatus.OPEN, TradeStatus.PENDING, TradeStatus.PARTIALLY_FILLED)

    def calculate_pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        multiplier = self.quantity * self.lot_size
        if self.side == OrderSide.BUY:
            return (self.exit_price - self.entry_price) * multiplier
        else:
            return (self.entry_price - self.exit_price) * multiplier
