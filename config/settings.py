"""
AlgoBot Configuration — centralized settings via pydantic-settings.
Reads from .env file and environment variables.
"""
from enum import Enum
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class TradingSegment(str, Enum):
    DELIVERY = "delivery"
    INTRADAY = "intraday"
    OPTIONS = "options"
    FUTURES = "futures"
    COMMODITIES = "commodities"
    DERIVATIVES = "derivatives"


class TradeMode(str, Enum):
    MARGIN = "margin"
    PREDICTION = "prediction"


class BrokerName(str, Enum):
    ZERODHA = "zerodha"
    ANGELONE = "angelone"
    UPSTOX = "upstox"
    PAPER = "paper"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    TEMPLATE = "template"


class Settings(BaseSettings):
    # ── Broker ──
    broker_name: BrokerName = BrokerName.PAPER

    zerodha_api_key: str = ""
    zerodha_api_secret: str = ""
    zerodha_access_token: str = ""

    angelone_api_key: str = ""
    angelone_client_id: str = ""
    angelone_password: str = ""
    angelone_totp_secret: str = ""

    upstox_api_key: str = ""
    upstox_api_secret: str = ""
    upstox_access_token: str = ""

    # ── LLM ──
    llm_provider: LLMProvider = LLMProvider.TEMPLATE
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # ── Risk Management ──
    max_loss_per_trade_pct: float = 1.0
    daily_loss_limit_pct: float = 3.0
    max_open_positions: int = 5
    position_size_pct: float = 2.0
    trailing_stop_atr_multiplier: float = 1.5
    margin_min_spread_pct: float = 0.3
    prediction_min_confidence: float = 75.0

    # ── Database ──
    db_path: str = "data/algobot.db"

    # ── Trading ──
    paper_trading: bool = True
    default_segment: TradingSegment = TradingSegment.INTRADAY
    default_trade_mode: TradeMode = TradeMode.PREDICTION

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            _settings = Settings(_env_file=env_path)
        else:
            _settings = Settings()
    return _settings
