"""리스크 관리: 포지션 사이징, 손절, 일일 손실 한도."""
from __future__ import annotations

from dataclasses import dataclass

MIN_ORDER_KRW = 5000  # 업비트 최소 주문 금액


@dataclass
class RiskManager:
    invest_ratio: float = 0.9995  # 매수 시 사용할 KRW 비율
    stop_loss_pct: float = 0.05   # 진입가 대비 손절 비율
    daily_loss_limit_pct: float | None = None  # 당일 누적손실 한도 (선택)

    def position_size(self, krw_balance: float) -> float:
        """이번 매수에 투입할 KRW 금액. 최소 주문금액 미만이면 0."""
        amount = krw_balance * self.invest_ratio
        return amount if amount >= MIN_ORDER_KRW else 0.0

    def should_stop_loss(self, entry_price: float, current_price: float) -> bool:
        if entry_price <= 0:
            return False
        return (current_price - entry_price) / entry_price <= -self.stop_loss_pct

    def daily_limit_hit(self, day_return_pct: float) -> bool:
        if self.daily_loss_limit_pct is None:
            return False
        return day_return_pct <= -self.daily_loss_limit_pct
