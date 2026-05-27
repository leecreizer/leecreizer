"""CLI 진입점.

  python run.py backtest --days 365 --k 0.5 --ma 0
  python run.py backtest --csv data/btc.csv
  python run.py live
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from config import config
from src.backtest import run_backtest
from src.strategies import VolatilityBreakout


def _load_ohlcv(ticker: str, days: int, csv: str | None) -> pd.DataFrame:
    if csv:
        df = pd.read_csv(csv, index_col=0, parse_dates=True)
        return df
    import pyupbit  # 지연 import (라이브 데이터)

    df = pyupbit.get_ohlcv(ticker, interval="day", count=days)
    if df is None or df.empty:
        sys.exit("OHLCV 데이터를 가져오지 못했습니다. 네트워크/티커를 확인하세요.")
    return df


def cmd_backtest(args: argparse.Namespace) -> None:
    df = _load_ohlcv(args.ticker, args.days, args.csv)
    strategy = VolatilityBreakout(k=args.k, ma_window=args.ma)
    result = run_backtest(df, strategy, fee=config.fee)
    print(f"== 백테스트 {args.ticker}  k={args.k}  ma={args.ma} ==")
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
    bt.add_argument("--days", type=int, default=365)
    bt.add_argument("--k", type=float, default=config.breakout_k)
    bt.add_argument("--ma", type=int, default=config.ma_window)
    bt.add_argument("--csv", default=None, help="OHLCV CSV 경로 (없으면 업비트에서 조회)")
    bt.set_defaults(func=cmd_backtest)

    lv = sub.add_parser("live", help="실시간 자동매매 (실거래 주의!)")
    lv.set_defaults(func=cmd_live)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
