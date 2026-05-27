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

from src.backtest import run_backtest, run_portfolio_backtest  # noqa: E402
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
    strategy = VolatilityBreakout(k=0.5)

    for ma in (0, 15):
        s = VolatilityBreakout(k=0.5, ma_window=ma)
        result = run_backtest(df, s, fee=0.0005)
        label = "돌파" if ma == 0 else f"돌파+MA{ma}"
        print(f"== {label} (합성 데이터) ==")
        print(result.summary())
        print()

    print("== 트레일링 스탑 비교 (돌파, 합성 데이터) ==")
    plain = run_backtest(df, strategy, fee=0.0005)
    trailed = run_backtest(
        df, strategy, fee=0.0005, trail_stop_pct=0.05, trail_min_profit_pct=0.005
    )
    print(f"트레일링 미사용: {plain.summary().splitlines()[1]}")
    print(f"트레일링 5%   : {trailed.summary().splitlines()[1]}")
    print()

    print("== 멀티코인 포트폴리오 (3코인, 합성 데이터) ==")
    df_map = {
        "COIN-A": make_ohlcv(seed=1),
        "COIN-B": make_ohlcv(seed=2),
        "COIN-C": make_ohlcv(seed=3),
    }
    pf = run_portfolio_backtest(df_map, strategy, fee=0.0005)
    print(pf.summary())


if __name__ == "__main__":
    main()
