"""
Order Manager — handles order placement, tracking, and paper trading.
"""
from datetime import datetime
from typing import Optional, List
from data.models import TradeRecord, TradeStatus, OrderSide
from data.storage import get_db
from config.settings import get_settings


class OrderManager:
    """
    Manages order lifecycle: create → open → close/cancel.
    In paper trading mode, orders are simulated instantly.
    """

    def __init__(self):
        self.db = get_db()
        self.settings = get_settings()

    def place_order(self, symbol: str, side: str, entry_price: float,
                    quantity: int, segment: str = "intraday",
                    mode: str = "prediction", stop_loss: float = 0.0,
                    take_profit: float = 0.0, lot_size: int = 1,
                    confidence: float = 0.0, notes: str = "") -> TradeRecord:
        """Place a new order (paper or live)."""
        trade = TradeRecord(
            symbol=symbol.upper(),
            segment=segment,
            mode=mode,
            side=OrderSide(side.upper()),
            entry_price=entry_price,
            quantity=quantity,
            lot_size=lot_size,
            status=TradeStatus.OPEN,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence_score=confidence,
            strategy_notes=notes,
            created_at=datetime.now(),
        )

        if self.settings.paper_trading:
            # Paper mode: immediately mark as OPEN
            trade.status = TradeStatus.OPEN
        else:
            # Live mode: would call broker API here
            # For now, mark as PENDING
            trade.status = TradeStatus.PENDING

        self.db.save_trade(trade)
        return trade

    def close_order(self, trade_id: str, exit_price: float,
                    commission: float = 0.0) -> Optional[TradeRecord]:
        """Close an open order."""
        trades = self.db.get_trades()
        trade = next((t for t in trades if t.id == trade_id), None)

        if trade is None:
            return None

        trade.exit_price = exit_price
        trade.status = TradeStatus.CLOSED
        trade.closed_at = datetime.now()
        trade.pnl = trade.calculate_pnl()
        trade.commission = commission

        self.db.save_trade(trade)
        return trade

    def cancel_order(self, trade_id: str) -> Optional[TradeRecord]:
        """Cancel a pending/open order."""
        trades = self.db.get_trades()
        trade = next((t for t in trades if t.id == trade_id), None)

        if trade is None:
            return None

        trade.status = TradeStatus.CANCELLED
        trade.closed_at = datetime.now()
        self.db.save_trade(trade)
        return trade

    def check_stop_loss_take_profit(self, trade: TradeRecord,
                                     current_price: float) -> Optional[str]:
        """Check if SL or TP is hit. Returns 'SL', 'TP', or None."""
        if trade.status != TradeStatus.OPEN:
            return None

        if trade.side == OrderSide.BUY:
            if trade.stop_loss > 0 and current_price <= trade.stop_loss:
                return "SL"
            if trade.take_profit > 0 and current_price >= trade.take_profit:
                return "TP"
        else:
            if trade.stop_loss > 0 and current_price >= trade.stop_loss:
                return "SL"
            if trade.take_profit > 0 and current_price <= trade.take_profit:
                return "TP"

        return None

    def get_open_orders(self) -> List[TradeRecord]:
        """Get all open orders."""
        return self.db.get_trades(status="OPEN")

    def get_trade_history(self, limit: int = 100) -> List[TradeRecord]:
        """Get trade history."""
        return self.db.get_trades(limit=limit)
