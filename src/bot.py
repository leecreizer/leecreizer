"""라이브 멀티코인 매매 봇 (시간 기반 상태머신).

각 코인에 대해 매 틱:
  - 장중(거래일 시작 ~ 종가 10초 전):
      · 미보유 → 돌파(+선택적 AI 게이트) 만족 시 매수
      · 보유   → 손절 또는 트레일링 스탑 체크
  - 종가 직전/장외: 보유분 전량 청산
예산은 보유 가능 슬롯 수로 균등 배분. 포지션은 StateStore 로 영속화해
봇이 재시작돼도 진입가/당일고가를 복구한다.
"""
from __future__ import annotations

import datetime
import time

from .exchange import UpbitExchange
from .notifier import Notifier
from .predictor import Predictor
from .risk import RiskManager
from .state import StateStore
from .strategies.base import Strategy

MIN_EVAL_KRW = 5000  # 보유 판정 기준 평가액


class PortfolioBot:
    def __init__(
        self,
        exchange: UpbitExchange,
        strategy: Strategy,
        risk: RiskManager,
        notifier: Notifier,
        tickers: list[str],
        state_store: StateStore | None = None,
        predictor: Predictor | None = None,
    ):
        self.exchange = exchange
        self.strategy = strategy
        self.risk = risk
        self.notifier = notifier
        self.tickers = tickers
        self.state_store = state_store or StateStore()
        self.predictor = predictor
        self.positions = self.state_store.load(tickers)

    def _save(self) -> None:
        self.state_store.save(self.positions)

    def _open_slots(self) -> int:
        """아직 미보유인 코인 수(예산 균등 배분의 분모)."""
        return sum(1 for p in self.positions.values() if not p.is_open) or 1

    def _buy_approved(self, completed, current_price: float) -> bool:
        if not self.strategy.should_buy(completed, current_price):
            return False
        if self.predictor is not None:
            return self.predictor.approves_buy(completed, current_price)
        return True

    def _tick_ticker(self, ticker: str, now: datetime.datetime) -> None:
        pos = self.positions[ticker]
        count = self.strategy.required_history + 1  # +1: 오늘 형성 중인 봉
        df = self.exchange.get_daily_ohlcv(ticker, count=count)
        completed = df.iloc[:-1]  # 완료 봉만

        day_start = df.index[-1].to_pydatetime()
        day_end = day_start + datetime.timedelta(days=1)
        price = self.exchange.get_current_price(ticker)
        base = ticker.split("-")[1]
        holding = self.exchange.get_balance(base)
        in_position = holding * price > MIN_EVAL_KRW

        if in_position:
            pos.day_high = max(pos.day_high, price)

        if day_start < now < day_end - datetime.timedelta(seconds=10):
            if not in_position:
                if self._buy_approved(completed, price):
                    krw = self.exchange.get_balance("KRW")
                    amount = self.risk.position_size(krw, self._open_slots())
                    if amount > 0:
                        self.exchange.buy_market(ticker, amount)
                        pos.entry_price = price
                        pos.day_high = price
                        self._save()
                        self.notifier.send(
                            f"매수 {ticker} @ {price:,.0f} (투입 {amount:,.0f}원)"
                        )
            elif self.risk.should_stop_loss(pos.entry_price, price):
                self.exchange.sell_market(ticker, holding)
                pos.reset()
                self._save()
                self.notifier.send(f"손절 {ticker} @ {price:,.0f}")
            elif self.risk.should_trailing_stop(pos.entry_price, pos.day_high, price):
                self.exchange.sell_market(ticker, holding)
                pos.reset()
                self._save()
                self.notifier.send(f"트레일링 청산 {ticker} @ {price:,.0f}")
        elif in_position:
            self.exchange.sell_market(ticker, holding)
            pos.reset()
            self._save()
            self.notifier.send(f"종가 청산 {ticker} @ {price:,.0f}")

    def run(self) -> None:
        self.notifier.send(f"autotrade 시작: {', '.join(self.tickers)}")
        while True:
            now = datetime.datetime.now()
            for ticker in self.tickers:
                try:
                    self._tick_ticker(ticker, now)
                except Exception as e:  # noqa: BLE001 - 루프 생존이 최우선
                    self.notifier.send(f"에러[{ticker}]: {e}")
            time.sleep(1)
