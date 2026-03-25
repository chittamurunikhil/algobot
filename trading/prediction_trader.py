"""
Prediction Trader — directional trading based on ML predictions.
Takes positions in the predicted direction and profits from price movement.
"""
from datetime import datetime
from typing import Optional
from data.models import AnalysisResult, Signal
from trading.risk_manager import RiskManager
from trading.order_manager import OrderManager


class PredictionTrader:
    """
    Prediction Trading Strategy:
    1. Use ML ensemble + technical signals to predict direction
    2. Enter trade in predicted direction when confidence >= threshold
    3. Use ATR-based stop-loss and take-profit
    4. Profit from directional price movement
    """

    def __init__(self, capital: float = 100000.0):
        self.risk_manager = RiskManager(capital)
        self.order_manager = OrderManager()

    def evaluate_opportunity(self, analysis: AnalysisResult,
                              ml_confidence: float = 0.0) -> dict:
        """
        Evaluate if a prediction-based trade opportunity exists.
        Combines technical signal with ML confidence.
        """
        # Combine technical and ML confidence
        tech_confidence = analysis.confidence
        combined_confidence = (tech_confidence * 0.4 + ml_confidence * 0.6) if ml_confidence > 0 else tech_confidence

        # Determine direction
        if analysis.signal in (Signal.BUY, Signal.STRONG_BUY):
            direction = "BUY"
        elif analysis.signal in (Signal.SELL, Signal.STRONG_SELL):
            direction = "SELL"
        else:
            direction = "HOLD"

        # Validate
        valid, reason = self.risk_manager.validate_prediction_trade(combined_confidence)
        can_trade, trade_reason = self.risk_manager.can_open_trade()

        # Calculate levels
        sl = self.risk_manager.calculate_stop_loss(analysis.ltp, analysis.atr, direction)
        tp = self.risk_manager.calculate_take_profit(analysis.ltp, analysis.atr, direction)

        return {
            "symbol": analysis.symbol,
            "opportunity": valid and can_trade and direction != "HOLD",
            "reason": reason if not valid else trade_reason if not can_trade else "No clear direction" if direction == "HOLD" else "Opportunity available",
            "direction": direction,
            "entry_price": analysis.ltp,
            "stop_loss": sl,
            "take_profit": tp,
            "technical_confidence": tech_confidence,
            "ml_confidence": ml_confidence,
            "combined_confidence": round(combined_confidence, 1),
            "signal": analysis.signal.value,
        }

    def execute_prediction_trade(self, analysis: AnalysisResult,
                                   ml_confidence: float = 0.0,
                                   quantity: Optional[int] = None) -> dict:
        """
        Execute a prediction-based trade.
        """
        opp = self.evaluate_opportunity(analysis, ml_confidence)

        if not opp["opportunity"]:
            return {"success": False, "reason": opp["reason"]}

        direction = opp["direction"]

        # Calculate position size
        if quantity is None:
            quantity = self.risk_manager.calculate_position_size(
                opp["entry_price"], opp["stop_loss"]
            )

        # Place order
        order = self.order_manager.place_order(
            symbol=analysis.symbol,
            side=direction,
            entry_price=opp["entry_price"],
            quantity=quantity,
            segment=analysis.segment,
            mode="prediction",
            stop_loss=opp["stop_loss"],
            take_profit=opp["take_profit"],
            confidence=opp["combined_confidence"],
            notes=f"Prediction trade - Signal: {opp['signal']}, Conf: {opp['combined_confidence']:.0f}%",
        )

        potential_profit = abs(opp["take_profit"] - opp["entry_price"]) * quantity
        potential_loss = abs(opp["entry_price"] - opp["stop_loss"]) * quantity

        return {
            "success": True,
            "order": order,
            "direction": direction,
            "entry_price": opp["entry_price"],
            "stop_loss": opp["stop_loss"],
            "take_profit": opp["take_profit"],
            "quantity": quantity,
            "potential_profit": round(potential_profit, 2),
            "potential_loss": round(potential_loss, 2),
            "risk_reward": round(potential_profit / potential_loss, 2) if potential_loss > 0 else 0,
            "confidence": opp["combined_confidence"],
        }
