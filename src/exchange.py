"""업비트 거래소 래퍼.

pyupbit 는 이 클래스 안에서만 import 한다(지연 import). 일부 환경에서 모듈
로드 자체가 실패할 수 있어, 전략/백테스트 코드가 거래소 의존성에 오염되지 않도록 격리한다.
"""
from __future__ import annotations

import pandas as pd


class UpbitExchange:
    def __init__(self, access_key: str, secret_key: str):
        import pyupbit  # 지연 import

        self._pyupbit = pyupbit
        self._upbit = pyupbit.Upbit(access_key, secret_key)

    def get_daily_ohlcv(self, ticker: str, count: int) -> pd.DataFrame:
        return self._pyupbit.get_ohlcv(ticker, interval="day", count=count)

    def get_current_price(self, ticker: str) -> float:
        return float(self._pyupbit.get_current_price(ticker))

    def get_balance(self, currency: str) -> float:
        """보유 수량 조회. currency 예: 'KRW', 'BTC'."""
        balances = self._upbit.get_balances()
        for b in balances:
            if b["currency"] == currency:
                return float(b["balance"]) if b["balance"] else 0.0
        return 0.0

    def buy_market(self, ticker: str, krw_amount: float):
        return self._upbit.buy_market_order(ticker, krw_amount)

    def sell_market(self, ticker: str, volume: float):
        return self._upbit.sell_market_order(ticker, volume)
