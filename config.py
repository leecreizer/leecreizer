"""환경변수(.env) 기반 설정 로딩."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _float(key: str, default: float) -> float:
    raw = os.getenv(key)
    return float(raw) if raw not in (None, "") else default


def _int(key: str, default: int) -> int:
    raw = os.getenv(key)
    return int(raw) if raw not in (None, "") else default


@dataclass
class Config:
    access_key: str = os.getenv("UPBIT_ACCESS_KEY", "")
    secret_key: str = os.getenv("UPBIT_SECRET_KEY", "")

    ticker: str = os.getenv("TICKER", "KRW-BTC")
    breakout_k: float = _float("BREAKOUT_K", 0.5)
    ma_window: int = _int("MA_WINDOW", 0)  # 0 = 미사용

    invest_ratio: float = _float("INVEST_RATIO", 0.9995)
    stop_loss_pct: float = _float("STOP_LOSS_PCT", 0.05)
    fee: float = _float("FEE", 0.0005)

    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")


config = Config()
