import pandas as pd

from src.selector import average_noise, select_low_noise


def _df(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])


def test_average_noise_trending_is_low():
    # 몸통이 봉 전체를 거의 채움(추세적) -> noise 낮음
    df = _df([[100, 110, 100, 110, 1]] * 5)  # |o-c|=10, range=10 -> noise=0
    assert average_noise(df, 5) == 0.0


def test_average_noise_doji_is_high():
    # 시가=종가(도지), 위아래 꼬리만 -> noise 높음(=1)
    df = _df([[100, 110, 90, 100, 1]] * 5)  # |o-c|=0 -> noise=1
    assert average_noise(df, 5) == 1.0


def test_select_low_noise_picks_and_limits():
    trending = _df([[100, 110, 100, 110, 1]] * 5)  # range10, |o-c|10 -> noise 0
    doji = _df([[100, 110, 90, 100, 1]] * 5)        # |o-c|0 -> noise 1 (한계 초과 제외)
    mid = _df([[100, 110, 90, 110, 1]] * 5)         # range20, |o-c|10 -> noise 0.5
    picked = select_low_noise(
        {"A": trending, "B": doji, "C": mid}, days=5, limit=5, noise_limit=0.6
    )
    assert picked == ["A", "C"]  # noise 오름차순, doji 는 0.6 초과로 탈락
