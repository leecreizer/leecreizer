"""백테스팅 엔진.

일봉 데이터에 대해 매일 다음을 시뮬레이션한다:
  - 직전일까지의 완료 봉으로 매수 목표가/필터 계산
  - 당일 고가가 목표가 이상이면 목표가에 진입했다고 본다
  - 청산가는 손절/트레일링/종가 순으로 결정 (intraday 경로는 일봉으로 근사)
  - 매수/매도 각각에 수수료(fee) 차감
수익률은 일 단위 곱(누적)으로 집계한다.

intraday 근사 한계: 하루 안에서 손절·트레일링·종가 중 무엇이 먼저 닿았는지는
일봉만으로 알 수 없다. 보수적으로 '손절 우선'으로 판정한다.
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


@dataclass
class PortfolioResult:
    aggregate: BacktestResult
    per_coin: dict[str, BacktestResult]

    def summary(self) -> str:
        lines = [f"[포트폴리오 {len(self.per_coin)}코인] {self.aggregate.summary()}"]
        for ticker, r in self.per_coin.items():
            lines.append(
                f"  - {ticker}: 수익률 {r.total_return:.2f}% / "
                f"MDD {r.mdd:.2f}% / 진입 {r.trades} / 승률 {r.win_rate:.1f}%"
            )
        return "\n".join(lines)


def _exit_price(
    today: pd.Series,
    target: float,
    stop_loss_pct: float | None,
    trail_stop_pct: float | None,
    trail_min_profit_pct: float,
) -> float:
    # 손절 우선(보수적): 당일 저가가 손절선에 닿으면 손절가에 청산
    if stop_loss_pct is not None and today["low"] <= target * (1 - stop_loss_pct):
        return target * (1 - stop_loss_pct)
    # 트레일링: 고점이 최소수익선 위로 갔고, 저가가 고점 대비 trail% 아래로 떨어졌으면
    if (
        trail_stop_pct is not None
        and today["high"] >= target * (1 + trail_min_profit_pct)
        and today["low"] <= today["high"] * (1 - trail_stop_pct)
    ):
        return today["high"] * (1 - trail_stop_pct)
    return float(today["close"])  # 그 외에는 종가 청산


def _finalize(out: pd.DataFrame, trades: int, wins: int) -> BacktestResult:
    out["hpr"] = out["ror"].cumprod()
    out["dd"] = (out["hpr"].cummax() - out["hpr"]) / out["hpr"].cummax() * 100
    total_return = (out["hpr"].iloc[-1] - 1) * 100
    mdd = out["dd"].max()
    days = len(out)
    cagr = (out["hpr"].iloc[-1] ** (365 / days) - 1) * 100 if days > 0 else 0.0
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


def run_backtest(
    df: pd.DataFrame,
    strategy: Strategy,
    fee: float = 0.0005,
    stop_loss_pct: float | None = None,
    trail_stop_pct: float | None = None,
    trail_min_profit_pct: float = 0.0,
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
        if today["high"] >= target and strategy.should_buy(completed, target):
            exit_price = _exit_price(
                today, target, stop_loss_pct, trail_stop_pct, trail_min_profit_pct
            )
            ror = (exit_price / target) * (1 - fee) ** 2  # 매수/매도 수수료
            trades += 1
            if ror > 1.0:
                wins += 1
        else:
            ror = 1.0
        rors.append(ror)

    out = df.iloc[1:].copy()
    out["ror"] = rors
    return _finalize(out, trades, wins)


def run_portfolio_backtest(
    df_map: dict[str, pd.DataFrame],
    strategy: Strategy,
    fee: float = 0.0005,
    stop_loss_pct: float | None = None,
    trail_stop_pct: float | None = None,
    trail_min_profit_pct: float = 0.0,
) -> PortfolioResult:
    """여러 코인을 매일 균등 배분(동일 비중)했다고 가정한 포트폴리오 백테스트."""
    per_coin = {
        ticker: run_backtest(
            df,
            strategy,
            fee=fee,
            stop_loss_pct=stop_loss_pct,
            trail_stop_pct=trail_stop_pct,
            trail_min_profit_pct=trail_min_profit_pct,
        )
        for ticker, df in df_map.items()
    }

    # 날짜축 정렬 후 미보유일은 ror=1.0 으로 채우고 매일 동일 비중 평균
    ror_df = pd.DataFrame({t: r.df["ror"] for t, r in per_coin.items()})
    ror_df = ror_df.sort_index().fillna(1.0)
    port_ror = ror_df.mean(axis=1)

    trades = sum(r.trades for r in per_coin.values())
    wins = sum(r.wins for r in per_coin.values())
    out = pd.DataFrame({"ror": port_ror})
    aggregate = _finalize(out, trades, wins)
    return PortfolioResult(aggregate=aggregate, per_coin=per_coin)
