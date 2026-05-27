"""CLI 진입점.

  python run.py backtest --days 365 --k 0.5 --ma 0
  python run.py backtest --csv data/btc.csv --stop-loss 0.05 --trail 0.05
  python run.py backtest --csv data/btc.csv,data/eth.csv   # 멀티코인 포트폴리오
  python run.py backtest --tickers KRW-BTC,KRW-ETH --days 365
  python run.py live
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

from config import config
from src.backtest import run_backtest, run_portfolio_backtest
from src.strategies import VolatilityBreakout


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def _load_df_map(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    csvs = _split(args.csv)
    if csvs:
        out: dict[str, pd.DataFrame] = {}
        for path in csvs:
            name = os.path.splitext(os.path.basename(path))[0]
            out[name] = pd.read_csv(path, index_col=0, parse_dates=True)
        return out

    tickers = _split(args.tickers) or [args.ticker]
    try:
        import pyupbit  # 지연 import (라이브 데이터)
    except BaseException as e:  # noqa: BLE001 - pyo3 PanicException 은 Exception 이 아님
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        sys.exit(
            "pyupbit 로드 실패(이 환경은 외부 네트워크/네이티브 의존성이 제한될 수 있음).\n"
            f"  → CSV 로 백테스트하세요: --csv data/btc.csv\n  원인: {type(e).__name__}: {e}"
        )
    out = {}
    for t in tickers:
        df = pyupbit.get_ohlcv(t, interval="day", count=args.days)
        if df is None or df.empty:
            sys.exit(f"{t} OHLCV 데이터를 가져오지 못했습니다.")
        out[t] = df
    return out


def cmd_backtest(args: argparse.Namespace) -> None:
    df_map = _load_df_map(args)
    strategy = VolatilityBreakout(k=args.k, ma_window=args.ma)
    risk = dict(
        stop_loss_pct=args.stop_loss or None,
        trail_stop_pct=args.trail or None,
        trail_min_profit_pct=args.trail_min_profit,
    )
    if len(df_map) == 1:
        ((name, df),) = df_map.items()
        result = run_backtest(df, strategy, fee=config.fee, **risk)
        print(f"== 백테스트 {name}  k={args.k}  ma={args.ma} ==")
        print(result.summary())
    else:
        result = run_portfolio_backtest(df_map, strategy, fee=config.fee, **risk)
        print(f"== 포트폴리오 백테스트  k={args.k}  ma={args.ma} ==")
        print(result.summary())


def cmd_live(args: argparse.Namespace) -> None:
    if not config.access_key or not config.secret_key:
        sys.exit("UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY 를 .env 에 설정하세요.")
    from src.bot import PortfolioBot
    from src.exchange import UpbitExchange
    from src.notifier import Notifier
    from src.risk import RiskManager
    from src.state import StateStore

    exchange = UpbitExchange(config.access_key, config.secret_key)
    strategy = VolatilityBreakout(k=config.breakout_k, ma_window=config.ma_window)
    risk = RiskManager(
        invest_ratio=config.invest_ratio,
        stop_loss_pct=config.stop_loss_pct,
        trail_stop_pct=config.trail_stop_pct or None,
        trail_min_profit_pct=config.trail_min_profit_pct,
    )
    notifier = Notifier(config.telegram_token, config.telegram_chat_id)

    predictor = None
    if config.use_ai_gate:
        from src.predictor import ProphetPredictor

        predictor = ProphetPredictor()

    store = StateStore(config.state_path)
    PortfolioBot(
        exchange,
        strategy,
        risk,
        notifier,
        config.tickers,
        state_store=store,
        predictor=predictor,
    ).run()


def main() -> None:
    parser = argparse.ArgumentParser(description="업비트 코인 자동매매")
    sub = parser.add_subparsers(dest="cmd", required=True)

    bt = sub.add_parser("backtest", help="과거 데이터로 전략 검증")
    bt.add_argument("--ticker", default=config.ticker)
    bt.add_argument("--tickers", default=None, help="멀티코인 (콤마 구분)")
    bt.add_argument("--days", type=int, default=365)
    bt.add_argument("--k", type=float, default=config.breakout_k)
    bt.add_argument("--ma", type=int, default=config.ma_window)
    bt.add_argument(
        "--csv", default=None, help="OHLCV CSV 경로 (콤마 구분 시 포트폴리오)"
    )
    bt.add_argument("--stop-loss", type=float, default=0.0, help="진입가 대비 손절 (0=미사용)")
    bt.add_argument("--trail", type=float, default=0.0, help="당일 고점 대비 트레일링 (0=미사용)")
    bt.add_argument("--trail-min-profit", type=float, default=0.0, help="트레일링 발동 최소수익")
    bt.set_defaults(func=cmd_backtest)

    lv = sub.add_parser("live", help="실시간 자동매매 (실거래 주의!)")
    lv.set_defaults(func=cmd_live)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
