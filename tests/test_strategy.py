import pandas as pd

from src.strategies import VolatilityBreakout


def _df(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])


def test_target_price():
    # 전일: close=100, high=120, low=80 -> range=40, k=0.5 -> target=100+20=120
    df = _df([[90, 120, 80, 100, 1]])
    s = VolatilityBreakout(k=0.5)
    assert s.target_price(df) == 120.0


def test_should_buy_breakout():
    df = _df([[90, 120, 80, 100, 1]])  # target=120
    s = VolatilityBreakout(k=0.5)
    assert s.should_buy(df, 121) is True
    assert s.should_buy(df, 119) is False


def test_ma_filter_blocks_below_ma():
    # 종가 평균이 높아 MA 필터가 매수를 막는 경우
    rows = [[c, c + 5, c - 5, c, 1] for c in [200, 200, 200]]
    df = _df(rows)  # target from last row: 200 + (205-195)*0.5 = 205
    s = VolatilityBreakout(k=0.5, ma_window=3)
    # 현재가 206 은 target(205) 돌파했지만 MA(200) 이상이라 통과
    assert s.should_buy(df, 206) is True
    s2 = VolatilityBreakout(k=0.5, ma_window=3)
    # MA 보다 낮은 가격은 애초에 target 돌파도 못 함 -> False
    assert s2.should_buy(df, 199) is False


def test_ma_insufficient_history_blocks():
    df = _df([[100, 110, 90, 100, 1]])
    s = VolatilityBreakout(k=0.5, ma_window=15)
    assert s.should_buy(df, 999) is False  # 데이터 부족 -> 보류
