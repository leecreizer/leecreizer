"""리스크 관리: 포지션 사이징, 손절, 일일 손실 한도."""
from __future__ import annotations

from dataclasses import dataclass

MIN_ORDER_KRW = 5000  # 업비트 최소 주문 금액


@dataclass
class RiskManager:
    invest_ratio: float = 0.9995  # 매수 시 사용할 KRW 비율
    stop_loss_pct: float = 0.05   # 진입가 대비 손절 비율
    trail_stop_pct: float | None = None  # 당일 고점 대비 하락 청산 비율 (선택)
    trail_min_profit_pct: float = 0.0    # 트레일링 발동 최소 수익 (예: 0.005=+0.5%)
    daily_loss_limit_pct: float | None = None  # 당일 누적손실 한도 (선택)

    def position_size(self, krw_balance: float, slots: int = 1) -> float:
        """이번 매수에 투입할 KRW 금액. 보유 가능 슬롯 수로 균등 배분.

        최소 주문금액 미만이면 0.
        """
        amount = (krw_balance / max(slots, 1)) * self.invest_ratio
        return amount if amount >= MIN_ORDER_KRW else 0.0

    def should_stop_loss(self, entry_price: float, current_price: float) -> bool:
        if entry_price <= 0:
            return False
        return (current_price - entry_price) / entry_price <= -self.stop_loss_pct

    def should_trailing_stop(
        self, entry_price: float, day_high: float, current_price: float
    ) -> bool:
        """진입 후 일정 수익을 낸 뒤, 당일 고점 대비 일정 % 하락하면 청산."""
        if self.trail_stop_pct is None or entry_price <= 0 or day_high <= 0:
            return False
        if current_price < entry_price * (1 + self.trail_min_profit_pct):
            return False  # 아직 최소 수익 미달이면 트레일링 미적용
        return current_price <= day_high * (1 - self.trail_stop_pct)

    def daily_limit_hit(self, day_return_pct: float) -> bool:
        if self.daily_loss_limit_pct is None:
            return False
        return day_return_pct <= -self.daily_loss_limit_pct
