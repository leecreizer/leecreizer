"""전략 추상 인터페이스.

전략 메서드는 모두 '완료된 일봉만' 담긴 DataFrame 을 입력으로 받는다.
즉 마지막 행(iloc[-1]) = 직전 거래일(어제). 오늘 형성 중인 봉은 호출 측에서 제외해
넘긴다. 이렇게 하면 라이브 매매와 백테스트가 동일한 규칙을 공유한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    @property
    @abstractmethod
    def required_history(self) -> int:
        """전략 판단에 필요한 최소 완료 일봉 수."""

    @abstractmethod
    def target_price(self, completed: pd.DataFrame) -> float:
        """매수 목표가."""

    @abstractmethod
    def should_buy(self, completed: pd.DataFrame, current_price: float) -> bool:
        """현재가가 매수 조건을 만족하는지."""
