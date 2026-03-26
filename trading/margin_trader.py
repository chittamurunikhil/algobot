"""
Margin Trader — commission-based spread trading.
Executes paired buy/sell orders within a calculated margin band
to capture the spread as commission income.
"""
from datetime import datetime
from typing import Optional, Tuple
from data.models import AnalysisResult, Signal
from trading.risk_manager import RiskManager
from trading.order_manager import OrderManager


class MarginTrader:
    """
    Margin Trading Strategy:
    1. Calculate spread band from Bollinger Band width or MAD
    2. Place BUY at lower band + offset, SELL at upper band - offset
    3. Profit = spread captured as commission
    4. Works best in range-bound markets with moderate volatility
    """

    def __init__(self, capital: float = 100000.0):
        self.risk_manager = RiskManager(capital)
        self.order_manager = OrderManager()

    def evaluate_opportunity(self, analysis: AnalysisResult) -> dict:
        """
        Evaluate if a margin trade opportunity exists.
        Returns dict with opportunity details.
        """
        # Calculate spread from Bollinger Band width
        bb_spread = analysis.bollinger_upper - analysis.bollinger_lower
        spread_pct = (bb_spread / analysis.ltp * 100) if analysis.ltp > 0 else 0

        # Alternative: use MAD for spread estimation
        mad_spread_pct = (analysis.mad_20 * 2 / analysis.ltp * 100) if analysis.ltp > 0 else 0

        # Use the wider of the two
        effective_spread = max(spread_pct, mad_spread_pct)

        # Validate
        valid, reason = self.risk_manager.validate_margin_trade(effective_spread)
        can_trade, trade_reason = self.risk_manager.can_open_trade()

        # Calculate entry/exit levels
        buy_price = analysis.bollinger_lower + (bb_spread * 0.1)
        sell_price = analysis.bollinger_upper - (bb_spread * 0.1)
        estimated_commission = sell_price - buy_price

        return {
            "symbol": analysis.symbol,
            "opportunity": valid and can_trade,
            "reason": reason if not valid else trade_reason if not can_trade else "Opportunity available",
            "spread_pct": round(effective_spread, 2),
            "buy_price": round(buy_price, 2),
            "sell_price": round(sell_price, 2),
            "estimated_commission_per_share": round(estimated_commission, 2),
            "bb_spread": round(bb_spread, 2),
            "mad_spread": round(analysis.mad_20 * 2, 2),
            "confidence": analysis.confidence,
        }

    def execute_margin_trade(self, analysis: AnalysisResult,
                              quantity: Optional[int] = None,
                              stop_loss: Optional[float] = None,
                              buy_price: Optional[float] = None,
                              sell_price: Optional[float] = None) -> dict:
        """
        Execute a margin trade pair (buy + sell).
        In paper mode, both orders are simulated.
        """
        opp = self.evaluate_opportunity(analysis)

        if not opp["opportunity"]:
            return {"success": False, "reason": opp["reason"]}

        # Determine Price Overrides
        final_buy = buy_price if buy_price is not None else opp["buy_price"]
        final_sell = sell_price if sell_price is not None else opp["sell_price"]
        
        # Determine Stop Loss to use
        sl_to_use = stop_loss if stop_loss is not None else self.risk_manager.calculate_stop_loss(final_buy, analysis.atr, "BUY")

        # Calculate position size if not provided
        if quantity is None:
            quantity = self.risk_manager.calculate_position_size(
                final_buy,
                sl_to_use
            )

        # Place buy order
        buy_order = self.order_manager.place_order(
            symbol=analysis.symbol,
            side="BUY",
            entry_price=final_buy,
            quantity=quantity,
            segment=analysis.segment,
            mode="margin",
            stop_loss=sl_to_use,
            take_profit=final_sell,
            confidence=analysis.confidence,
            notes=f"Margin trade - spread override",
        )

        return {
            "success": True,
            "buy_order": buy_order,
            "buy_price": final_buy,
            "target_sell_price": final_sell,
            "quantity": quantity,
            "estimated_profit": (final_sell - final_buy) * quantity,
            "spread_pct": ((final_sell - final_buy) / final_buy * 100) if final_buy > 0 else 0.0,
        }
