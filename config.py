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


def _bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class Config:
    access_key: str = os.getenv("UPBIT_ACCESS_KEY", "")
    secret_key: str = os.getenv("UPBIT_SECRET_KEY", "")

    # 단일 코인(TICKER) 또는 멀티코인(TICKERS, 콤마 구분)
    ticker: str = os.getenv("TICKER", "KRW-BTC")
    tickers_raw: str = os.getenv("TICKERS", "")

    breakout_k: float = _float("BREAKOUT_K", 0.5)
    ma_window: int = _int("MA_WINDOW", 0)  # 0 = 미사용

    invest_ratio: float = _float("INVEST_RATIO", 0.9995)
    stop_loss_pct: float = _float("STOP_LOSS_PCT", 0.05)
    trail_stop_pct: float = _float("TRAIL_STOP_PCT", 0.0)  # 0 = 미사용
    trail_min_profit_pct: float = _float("TRAIL_MIN_PROFIT_PCT", 0.0)
    fee: float = _float("FEE", 0.0005)

    use_ai_gate: bool = _bool("USE_AI_GATE", False)
    state_path: str = os.getenv("STATE_PATH", "state.json")

    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def tickers(self) -> list[str]:
        if self.tickers_raw.strip():
            return [t.strip() for t in self.tickers_raw.split(",") if t.strip()]
        return [self.ticker]


config = Config()
