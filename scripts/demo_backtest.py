"""네트워크 없이 합성 데이터로 백테스트 엔진을 시연한다.

실제 업비트 데이터 대신 랜덤워크 일봉을 생성해 전략을 돌려본다.
엔진/지표 동작 확인용이며, 수치 자체에 투자 의미는 없다.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backtest import run_backtest  # noqa: E402
from src.strategies import VolatilityBreakout  # noqa: E402


def make_ohlcv(days: int = 365, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.001, 0.03, days)  # 약한 상승 추세 + 변동성
    close = 30_000_000 * np.cumprod(1 + rets)
    high = close * (1 + np.abs(rng.normal(0, 0.02, days)))
    low = close * (1 - np.abs(rng.normal(0, 0.02, days)))
    open_ = close * (1 + rng.normal(0, 0.01, days))
    idx = pd.date_range("2024-01-01", periods=days, freq="D")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1.0},
        index=idx,
    )


def main() -> None:
    df = make_ohlcv()
    for ma in (0, 15):
        strategy = VolatilityBreakout(k=0.5, ma_window=ma)
        result = run_backtest(df, strategy, fee=0.0005)
        label = "돌파" if ma == 0 else f"돌파+MA{ma}"
        print(f"== {label} (합성 데이터) ==")
        print(result.summary())
        print()


if __name__ == "__main__":
    main()
