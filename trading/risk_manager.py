"""
Risk Manager — enforces position sizing, stop-loss, and daily loss limits.
"""
from datetime import datetime
from typing import Optional
from data.models import TradeRecord, TradeStatus
from data.storage import get_db
from config.settings import get_settings


class RiskManager:
    """
    Enforces risk management rules:
    - Max loss per trade (% of capital)
    - Daily loss limit (% of capital)
    - Max open positions
    - Position sizing (% of capital per trade)
    - Trailing stop-loss (ATR-based)
    """

    def __init__(self, capital: float = 100000.0):
        self.capital = capital
        settings = get_settings()
        self.max_loss_per_trade_pct = settings.max_loss_per_trade_pct
        self.daily_loss_limit_pct = settings.daily_loss_limit_pct
        self.max_open_positions = settings.max_open_positions
        self.position_size_pct = settings.position_size_pct
        self.trailing_stop_atr_multiplier = settings.trailing_stop_atr_multiplier
        self.margin_min_spread_pct = settings.margin_min_spread_pct
        self.prediction_min_confidence = settings.prediction_min_confidence

    def can_open_trade(self) -> tuple:
        """Check if a new trade can be opened. Returns (allowed, reason)."""
        db = get_db()

        # Check open positions
        open_trades = db.get_trades(status="OPEN")
        if len(open_trades) >= self.max_open_positions:
            return False, f"Max open positions reached ({self.max_open_positions})"

        # Check daily loss limit
        today_trades = db.get_today_trades()
        today_loss = sum(t.pnl for t in today_trades if t.status == TradeStatus.CLOSED and t.pnl < 0)
        max_daily_loss = self.capital * (self.daily_loss_limit_pct / 100)
        if abs(today_loss) >= max_daily_loss:
            return False, f"Daily loss limit hit (₹{abs(today_loss):,.2f} / ₹{max_daily_loss:,.2f})"

        return True, "OK"

    def calculate_position_size(self, entry_price: float, stop_loss: float) -> int:
        """Calculate quantity based on risk per trade."""
        max_risk = self.capital * (self.max_loss_per_trade_pct / 100)
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0:
            risk_per_share = entry_price * 0.01  # Default 1% risk

        quantity = int(max_risk / risk_per_share)

        # Cap by position size limit
        max_position_value = self.capital * (self.position_size_pct / 100)
        max_qty_by_capital = int(max_position_value / entry_price)

        return max(1, min(quantity, max_qty_by_capital))

    def calculate_stop_loss(self, entry_price: float, atr: float,
                            side: str = "BUY") -> float:
        """Calculate stop-loss based on ATR multiplier."""
        sl_distance = atr * self.trailing_stop_atr_multiplier
        if side == "BUY":
            return round(entry_price - sl_distance, 2)
        else:
            return round(entry_price + sl_distance, 2)

    def calculate_take_profit(self, entry_price: float, atr: float,
                              side: str = "BUY", risk_reward: float = 2.5) -> float:
        """Calculate take-profit based on risk-reward ratio × ATR."""
        tp_distance = atr * self.trailing_stop_atr_multiplier * risk_reward
        if side == "BUY":
            return round(entry_price + tp_distance, 2)
        else:
            return round(entry_price - tp_distance, 2)

    def validate_margin_trade(self, spread_pct: float) -> tuple:
        """Check if a margin trade meets minimum spread requirement."""
        if spread_pct < self.margin_min_spread_pct:
            return False, f"Spread {spread_pct:.2f}% < minimum {self.margin_min_spread_pct}%"
        return True, "OK"

    def validate_prediction_trade(self, confidence: float) -> tuple:
        """Check if a prediction trade meets minimum confidence."""
        if confidence < self.prediction_min_confidence:
            return False, f"Confidence {confidence:.0f}% < minimum {self.prediction_min_confidence:.0f}%"
        return True, "OK"

    def get_daily_stats(self) -> dict:
        """Get today's risk stats."""
        db = get_db()
        today_trades = db.get_today_trades()

        total_pnl = sum(t.pnl for t in today_trades if t.status == TradeStatus.CLOSED)
        total_loss = sum(t.pnl for t in today_trades if t.status == TradeStatus.CLOSED and t.pnl < 0)
        open_count = len([t for t in db.get_trades(status="OPEN")])

        return {
            "today_pnl": total_pnl,
            "today_loss": abs(total_loss),
            "daily_loss_limit": self.capital * (self.daily_loss_limit_pct / 100),
            "loss_remaining": max(0, self.capital * (self.daily_loss_limit_pct / 100) - abs(total_loss)),
            "open_positions": open_count,
            "max_positions": self.max_open_positions,
            "can_trade": open_count < self.max_open_positions and abs(total_loss) < self.capital * (self.daily_loss_limit_pct / 100),
        }
