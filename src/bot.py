"""라이브 매매 봇.

시간 기반 상태머신:
  - 장중(거래일 시작 ~ 종가 10초 전): 포지션 없으면 돌파 매수 시도,
    보유 중이면 손절 체크
  - 종가 직전/장외: 보유분 전량 청산
매 1초 폴링하며, 예외가 나도 루프가 죽지 않도록 감싼다.
"""
from __future__ import annotations

import datetime
import time

from .exchange import UpbitExchange
from .notifier import Notifier
from .risk import RiskManager
from .strategies.base import Strategy


class TradingBot:
    def __init__(
        self,
        exchange: UpbitExchange,
        strategy: Strategy,
        risk: RiskManager,
        notifier: Notifier,
        ticker: str = "KRW-BTC",
    ):
        self.exchange = exchange
        self.strategy = strategy
        self.risk = risk
        self.notifier = notifier
        self.ticker = ticker
        self.base = ticker.split("-")[1]  # KRW-BTC -> BTC
        self.entry_price: float | None = None

    def _tick(self) -> None:
        count = self.strategy.required_history + 1  # +1: 오늘 형성 중인 봉
        df = self.exchange.get_daily_ohlcv(self.ticker, count=count)
        completed = df.iloc[:-1]  # 오늘 봉 제외 = 완료 봉만

        now = datetime.datetime.now()
        day_start = df.index[-1].to_pydatetime()
        day_end = day_start + datetime.timedelta(days=1)
        price = self.exchange.get_current_price(self.ticker)
        holding = self.exchange.get_balance(self.base)
        in_position = holding * price > 5000  # 평가액 기준

        if day_start < now < day_end - datetime.timedelta(seconds=10):
            if not in_position:
                if self.strategy.should_buy(completed, price):
                    krw = self.exchange.get_balance("KRW")
                    amount = self.risk.position_size(krw)
                    if amount > 0:
                        self.exchange.buy_market(self.ticker, amount)
                        self.entry_price = price
                        self.notifier.send(
                            f"매수 {self.ticker} @ {price:,.0f} (투입 {amount:,.0f}원)"
                        )
            elif self.entry_price and self.risk.should_stop_loss(self.entry_price, price):
                self.exchange.sell_market(self.ticker, holding)
                self.notifier.send(f"손절 {self.ticker} @ {price:,.0f}")
                self.entry_price = None
        else:
            if in_position:
                self.exchange.sell_market(self.ticker, holding)
                self.notifier.send(f"종가 청산 {self.ticker} @ {price:,.0f}")
                self.entry_price = None

    def run(self) -> None:
        self.notifier.send(f"autotrade 시작: {self.ticker}")
        while True:
            try:
                self._tick()
            except Exception as e:  # noqa: BLE001 - 루프 생존이 최우선
                self.notifier.send(f"에러: {e}")
            time.sleep(1)
