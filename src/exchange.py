"""업비트 거래소 래퍼.

pyupbit 는 이 클래스 안에서만 import 한다(지연 import). 일부 환경에서 모듈
로드 자체가 실패할 수 있어, 전략/백테스트 코드가 거래소 의존성에 오염되지 않도록 격리한다.

모든 API 호출은 RateLimiter 를 거쳐 초당 요청 수 제한을 지킨다. 일봉 OHLCV 는
같은 날 동안 완료 봉이 바뀌지 않으므로 짧은 TTL 로 캐시해 멀티코인 시 요청을 줄인다.
"""
from __future__ import annotations

import pandas as pd

from .ratelimit import RateLimiter, TTLCache


class UpbitExchange:
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        req_per_sec: float = 8.0,
        ohlcv_ttl: float = 60.0,
    ):
        import pyupbit  # 지연 import

        self._pyupbit = pyupbit
        self._upbit = pyupbit.Upbit(access_key, secret_key)
        self._limiter = RateLimiter(1.0 / req_per_sec)
        self._ohlcv_cache = TTLCache(ohlcv_ttl)

    def get_daily_ohlcv(self, ticker: str, count: int) -> pd.DataFrame:
        key = (ticker, count)
        cached = self._ohlcv_cache.get(key)
        if cached is not None:
            return cached
        self._limiter.wait()
        df = self._pyupbit.get_ohlcv(ticker, interval="day", count=count)
        if df is not None:
            self._ohlcv_cache.set(key, df)
        return df

    def get_current_price(self, ticker: str) -> float:
        self._limiter.wait()
        return float(self._pyupbit.get_current_price(ticker))

    def get_balance(self, currency: str) -> float:
        """보유 수량 조회. currency 예: 'KRW', 'BTC'."""
        self._limiter.wait()
        balances = self._upbit.get_balances()
        for b in balances:
            if b["currency"] == currency:
                return float(b["balance"]) if b["balance"] else 0.0
        return 0.0

    def buy_market(self, ticker: str, krw_amount: float):
        self._limiter.wait()
        return self._upbit.buy_market_order(ticker, krw_amount)

    def sell_market(self, ticker: str, volume: float):
        self._limiter.wait()
        return self._upbit.sell_market_order(ticker, volume)
