import pandas as pd

from src.backtest import run_backtest, run_portfolio_backtest
from src.strategies import VolatilityBreakout


def _df(rows):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(
        rows, columns=["open", "high", "low", "close", "volume"], index=idx
    )


def test_single_winning_trade_no_fee():
    df = _df(
        [
            [100, 110, 90, 100, 1],   # day0: range=20 -> day1 target=110
            [110, 130, 105, 121, 1],  # day1: high130>=110 진입, 종가121 -> +10%
            [121, 120, 118, 119, 1],  # day2: target=133.5, 진입 안 함
        ]
    )
    r = run_backtest(df, VolatilityBreakout(k=0.5), fee=0.0)
    assert r.trades == 1
    assert r.wins == 1
    assert r.win_rate == 100.0
    assert round(r.total_return, 6) == 10.0
    assert r.mdd == 0.0


def test_fee_reduces_return():
    df = _df(
        [
            [100, 110, 90, 100, 1],
            [110, 130, 105, 121, 1],
            [121, 120, 118, 119, 1],
        ]
    )
    r0 = run_backtest(df, VolatilityBreakout(k=0.5), fee=0.0)
    rf = run_backtest(df, VolatilityBreakout(k=0.5), fee=0.0005)
    assert rf.total_return < r0.total_return


def test_no_trades_in_downtrend():
    df = _df(
        [
            [100, 105, 95, 100, 1],  # day0: range=10 -> target=105
            [100, 101, 80, 85, 1],   # day1: high101<105 진입 안 함
            [85, 86, 70, 72, 1],     # day2: target=95.5, high86 진입 안 함
        ]
    )
    r = run_backtest(df, VolatilityBreakout(k=0.5), fee=0.0005)
    assert r.trades == 0
    assert r.total_return == 0.0


def test_trailing_stop_exits_above_close():
    # day1: target=110 진입, 고점200까지 갔다가 저가150 -> 고점 대비 -25%
    df = _df(
        [
            [100, 110, 90, 100, 1],
            [110, 200, 150, 160, 1],
            [160, 161, 159, 160, 1],
        ]
    )
    base = run_backtest(df, VolatilityBreakout(k=0.5), fee=0.0)
    trailed = run_backtest(df, VolatilityBreakout(k=0.5), fee=0.0, trail_stop_pct=0.1)
    # 트레일링은 고점200의 -10%=180 에 청산 -> 종가160 보다 높은 수익
    assert trailed.total_return > base.total_return


def test_stop_loss_caps_downside():
    # day1: target=110 진입, 저가100 으로 하락 -> 손절선 110*0.95=104.5 청산
    df = _df(
        [
            [100, 110, 90, 100, 1],
            [110, 120, 100, 105, 1],
            [105, 106, 104, 105, 1],
        ]
    )
    base = run_backtest(df, VolatilityBreakout(k=0.5), fee=0.0)
    stopped = run_backtest(df, VolatilityBreakout(k=0.5), fee=0.0, stop_loss_pct=0.05)
    # 손절(104.5)이 종가(105)보다 낮으므로 손실이 더 큼
    assert stopped.total_return < base.total_return


def test_portfolio_backtest_aggregates():
    coin = _df(
        [
            [100, 110, 90, 100, 1],
            [110, 130, 105, 121, 1],
            [121, 120, 118, 119, 1],
        ]
    )
    res = run_portfolio_backtest(
        {"KRW-BTC": coin, "KRW-ETH": coin}, VolatilityBreakout(k=0.5), fee=0.0
    )
    assert set(res.per_coin) == {"KRW-BTC", "KRW-ETH"}
    assert res.aggregate.trades == 2  # 코인당 1회
    assert round(res.aggregate.total_return, 6) == 10.0  # 동일 코인이라 누적 +10%
