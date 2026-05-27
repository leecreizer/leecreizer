"""선택적 AI 매수 게이트.

다음 거래일 종가를 예측해, 예측가가 현재가 이상일 때만 매수를 허용한다.
전략(변동성 돌파) 판단을 대체하지 않고, 그 위에 얹는 추가 필터다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Predictor(ABC):
    @abstractmethod
    def predict_next_close(self, daily_df: pd.DataFrame) -> float:
        ...

    def approves_buy(self, daily_df: pd.DataFrame, current_price: float) -> bool:
        try:
            return self.predict_next_close(daily_df) >= current_price
        except Exception:
            return True  # 예측 실패 시 게이트는 통과시키고 전략 판단에 맡긴다


class ProphetPredictor(Predictor):
    """Facebook Prophet 으로 다음날 종가 예측. prophet 패키지는 지연 import."""

    def __init__(self, periods: int = 1):
        self.periods = periods

    def predict_next_close(self, daily_df: pd.DataFrame) -> float:
        from prophet import Prophet  # 지연 import (무거운 의존성)

        df = daily_df.reset_index()
        df = df.rename(columns={df.columns[0]: "ds", "close": "y"})[["ds", "y"]]
        df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)
        model = Prophet(daily_seasonality=True)
        model.fit(df)
        future = model.make_future_dataframe(periods=self.periods)
        forecast = model.predict(future)
        return float(forecast["yhat"].iloc[-1])
