from polymarket import CSV_COLUMNS
from polymarket.analyze import plot, summarize
from polymarket.recorder import Recorder
from polymarket.simulate import simulate


def test_simulate_schema_and_lag_creates_edge():
    df = simulate(duration_sec=300, interval_sec=1.0, lag_sec=3.0, spread=0.01, cost=0.0)
    assert list(df.columns) == CSV_COLUMNS
    s = summarize(df)
    # 지연이 있고 비용이 0 이면 양의 순엣지 표본이 존재해야 함
    assert s.edge_pos_fraction > 0


def test_high_cost_kills_edge():
    df = simulate(duration_sec=300, interval_sec=1.0, lag_sec=3.0, spread=0.02, cost=0.5)
    s = summarize(df)
    # 비용이 과도하면 엣지 기회 소멸
    assert s.edge_pos_fraction == 0
    assert "엣지 없음" in s.verdict


def test_plot_writes_png(tmp_path):
    df = simulate(duration_sec=120, interval_sec=1.0, lag_sec=2.0)
    out = tmp_path / "chart.png"
    plot(df, str(out))
    assert out.exists() and out.stat().st_size > 0


class FakeBinance:
    def __init__(self, price):
        self.price = price

    def get_price(self, symbol):
        return self.price


class FakePM:
    def __init__(self, bid, ask):
        self.bid, self.ask = bid, ask

    def get_book(self, token_id):
        return {"best_bid": self.bid, "best_ask": self.ask, "mid": (self.bid + self.ask) / 2}


def test_recorder_sample_computes_gap_and_direction():
    rec = Recorder(
        binance=FakeBinance(110),
        polymarket=FakePM(bid=0.50, ask=0.52),
        symbol="BTCUSDT",
        token_id="x",
        strike=100,
        expiry_ts=600,
        interval=1.0,
        cost=0.0,
        clock=lambda: 0.0,  # tau = 600
    )
    row = rec.sample()
    assert set(row) == set(CSV_COLUMNS)
    # 가격>행사가이므로 공정확률>0.5, 중간값=0.51 -> 갭>0, UP 저평가
    assert row["fair_prob"] > 0.5
    assert row["gap"] == row["fair_prob"] - 0.51
    assert row["direction"] == "UP"
