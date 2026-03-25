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
                              quantity: Optional[int] = None) -> dict:
        """
        Execute a margin trade pair (buy + sell).
        In paper mode, both orders are simulated.
        """
        opp = self.evaluate_opportunity(analysis)

        if not opp["opportunity"]:
            return {"success": False, "reason": opp["reason"]}

        # Calculate position size if not provided
        if quantity is None:
            quantity = self.risk_manager.calculate_position_size(
                opp["buy_price"],
                self.risk_manager.calculate_stop_loss(opp["buy_price"], analysis.atr, "BUY")
            )

        # Place buy order
        buy_order = self.order_manager.place_order(
            symbol=analysis.symbol,
            side="BUY",
            entry_price=opp["buy_price"],
            quantity=quantity,
            segment=analysis.segment,
            mode="margin",
            stop_loss=self.risk_manager.calculate_stop_loss(opp["buy_price"], analysis.atr, "BUY"),
            take_profit=opp["sell_price"],
            confidence=analysis.confidence,
            notes=f"Margin trade - spread: {opp['spread_pct']:.2f}%",
        )

        return {
            "success": True,
            "buy_order": buy_order,
            "buy_price": opp["buy_price"],
            "target_sell_price": opp["sell_price"],
            "quantity": quantity,
            "estimated_profit": opp["estimated_commission_per_share"] * quantity,
            "spread_pct": opp["spread_pct"],
        }
