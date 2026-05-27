"""래리 윌리엄스 변동성 돌파 전략 (+ 선택적 이동평균 필터)."""
from __future__ import annotations

import pandas as pd

from .base import Strategy


class VolatilityBreakout(Strategy):
    def __init__(self, k: float = 0.5, ma_window: int = 0):
        if k <= 0:
            raise ValueError("k must be > 0")
        self.k = k
        self.ma_window = ma_window  # 0 이면 MA 필터 미사용

    @property
    def required_history(self) -> int:
        return max(1, self.ma_window)

    def target_price(self, completed: pd.DataFrame) -> float:
        prev = completed.iloc[-1]
        return float(prev["close"] + (prev["high"] - prev["low"]) * self.k)

    def _ma_ok(self, completed: pd.DataFrame, price: float) -> bool:
        if self.ma_window <= 0:
            return True
        if len(completed) < self.ma_window:
            return False  # 데이터 부족 시 진입 보류
        ma = completed["close"].iloc[-self.ma_window:].mean()
        return bool(price >= ma)

    def should_buy(self, completed: pd.DataFrame, current_price: float) -> bool:
        target = self.target_price(completed)
        return bool(current_price >= target and self._ma_ok(completed, current_price))
