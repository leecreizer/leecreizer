import datetime

import pandas as pd

from src.bot import PortfolioBot
from src.notifier import Notifier
from src.risk import RiskManager
from src.state import StateStore
from src.strategies import VolatilityBreakout


class FakeExchange:
    """테스트용 거래소: 잔고/가격을 메모리에서 시뮬레이션."""

    def __init__(self, df_map, prices, balances):
        self.df_map = df_map
        self.prices = prices
        self.balances = balances
        self.orders = []

    def get_daily_ohlcv(self, ticker, count):
        return self.df_map[ticker].iloc[-count:]

    def get_current_price(self, ticker):
        return self.prices[ticker]

    def get_balance(self, currency):
        return self.balances.get(currency, 0.0)

    def buy_market(self, ticker, krw):
        self.orders.append(("buy", ticker, krw))
        base = ticker.split("-")[1]
        self.balances[base] = self.balances.get(base, 0.0) + krw / self.prices[ticker]
        self.balances["KRW"] = self.balances.get("KRW", 0.0) - krw

    def sell_market(self, ticker, volume):
        self.orders.append(("sell", ticker, volume))
        base = ticker.split("-")[1]
        self.balances["KRW"] = self.balances.get("KRW", 0.0) + volume * self.prices[ticker]
        self.balances[base] = 0.0


def _two_day_df(today):
    # day0(완료봉): close=100, high=110, low=90 -> 목표가 = 100 + (110-90)*0.5 = 110
    idx = pd.DatetimeIndex([today - datetime.timedelta(days=1), today])
    return pd.DataFrame(
        [[90, 110, 90, 100, 1], [100, 130, 100, 120, 1]],
        columns=["open", "high", "low", "close", "volume"],
        index=idx,
    )


def _bot(exchange, tmp_path, tickers):
    return PortfolioBot(
        exchange,
        VolatilityBreakout(k=0.5, ma_window=0),
        RiskManager(invest_ratio=1.0, stop_loss_pct=0.05),
        Notifier(),
        tickers,
        state_store=StateStore(str(tmp_path / "state.json")),
    )


def test_buys_on_breakout_and_persists(tmp_path):
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ex = FakeExchange(
        {"KRW-BTC": _two_day_df(today)},
        {"KRW-BTC": 1000},          # 현재가 1000 > 목표가 110 -> 돌파
        {"KRW": 1_000_000, "BTC": 0.0},
    )
    bot = _bot(ex, tmp_path, ["KRW-BTC"])
    now = today + datetime.timedelta(hours=12)  # 장중
    bot._tick_ticker("KRW-BTC", now)

    assert any(o[0] == "buy" for o in ex.orders)
    assert bot.positions["KRW-BTC"].is_open
    # 상태가 파일로 저장됐는지 확인
    reloaded = StateStore(str(tmp_path / "state.json")).load(["KRW-BTC"])
    assert reloaded["KRW-BTC"].entry_price == 1000


def test_liquidates_at_end_of_day(tmp_path):
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ex = FakeExchange(
        {"KRW-BTC": _two_day_df(today)},
        {"KRW-BTC": 1000},
        {"KRW": 0.0, "BTC": 10.0},  # 보유 중 (평가액 10,000 > 5,000)
    )
    bot = _bot(ex, tmp_path, ["KRW-BTC"])
    bot.positions["KRW-BTC"].entry_price = 900  # 진입 상태로 복구돼 있다고 가정
    now = today + datetime.timedelta(days=1) - datetime.timedelta(seconds=5)  # 종가 직전
    bot._tick_ticker("KRW-BTC", now)

    assert any(o[0] == "sell" for o in ex.orders)
    assert not bot.positions["KRW-BTC"].is_open


def test_budget_split_across_two_coins(tmp_path):
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ex = FakeExchange(
        {"KRW-BTC": _two_day_df(today), "KRW-ETH": _two_day_df(today)},
        {"KRW-BTC": 1000, "KRW-ETH": 1000},
        {"KRW": 1_000_000, "BTC": 0.0, "ETH": 0.0},
    )
    bot = _bot(ex, tmp_path, ["KRW-BTC", "KRW-ETH"])
    now = today + datetime.timedelta(hours=12)
    bot._tick_ticker("KRW-BTC", now)
    # 첫 매수는 슬롯 2개로 균등배분 -> 1,000,000 / 2 = 500,000
    buy = next(o for o in ex.orders if o[0] == "buy")
    assert buy[2] == 500_000
