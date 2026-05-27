"""백테스팅 엔진.

일봉 데이터에 대해 매일 다음을 시뮬레이션한다:
  - 직전일까지의 완료 봉으로 매수 목표가/필터 계산
  - 당일 고가가 목표가 이상이면 목표가에 진입했다고 보고, 당일 종가에 청산
  - 매수/매도 각각에 수수료(fee) 차감
수익률은 일 단위 곱(누적)으로 집계한다.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .strategies.base import Strategy


@dataclass
class BacktestResult:
    trades: int
    wins: int
    win_rate: float        # %
    total_return: float    # % (누적)
    cagr: float            # % (연환산)
    mdd: float             # % (최대 낙폭)
    df: pd.DataFrame       # 일별 상세 (ror, hpr, dd)

    def summary(self) -> str:
        return (
            f"거래일수={len(self.df)}  진입={self.trades}  승률={self.win_rate:.1f}%\n"
            f"누적수익률={self.total_return:.2f}%  CAGR={self.cagr:.2f}%  MDD={self.mdd:.2f}%"
        )


def run_backtest(
    df: pd.DataFrame,
    strategy: Strategy,
    fee: float = 0.0005,
) -> BacktestResult:
    if len(df) < strategy.required_history + 1:
        raise ValueError("데이터가 전략 요구 기간보다 짧습니다.")

    df = df.copy()
    rors: list[float] = []
    trades = wins = 0

    for i in range(1, len(df)):
        completed = df.iloc[:i]  # i일째 직전까지의 완료 봉
        today = df.iloc[i]

        if len(completed) < strategy.required_history:
            rors.append(1.0)
            continue

        target = strategy.target_price(completed)
        # 당일 고가가 목표가를 찍었고 필터(MA 등)도 통과하면 진입
        if today["high"] >= target and strategy.should_buy(completed, target):
            ror = (today["close"] / target) * (1 - fee) ** 2  # 매수/매도 수수료
            trades += 1
            if ror > 1.0:
                wins += 1
        else:
            ror = 1.0
        rors.append(ror)

    out = df.iloc[1:].copy()
    out["ror"] = rors
    out["hpr"] = out["ror"].cumprod()
    out["dd"] = (out["hpr"].cummax() - out["hpr"]) / out["hpr"].cummax() * 100

    total_return = (out["hpr"].iloc[-1] - 1) * 100
    mdd = out["dd"].max()
    days = len(out)
    cagr = ((out["hpr"].iloc[-1]) ** (365 / days) - 1) * 100 if days > 0 else 0.0
    win_rate = (wins / trades * 100) if trades else 0.0

    return BacktestResult(
        trades=trades,
        wins=wins,
        win_rate=win_rate,
        total_return=total_return,
        cagr=cagr,
        mdd=mdd,
        df=out,
    )
