"""합성 데이터 생성 — 네트워크 없이 하니스 전체를 검증/시연한다.

바이낸스 가격을 랜덤워크로 만들고, Polymarket 중간값은 공정확률을 'lag 초'
지연시킨 값에 스프레드/노이즈를 더해 만든다. 즉 글에서 말하는 '지연 갭'을
인위적으로 재현한다. lag 가 클수록, 비용/스프레드가 작을수록 엣지 기회가 늘어난다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import CSV_COLUMNS
from .fair_value import compute_edge, implied_prob_up


def simulate(
    duration_sec: int = 900,
    interval_sec: float = 1.0,
    lag_sec: float = 3.0,
    spread: float = 0.02,
    cost: float = 0.0,
    annual_vol: float = 0.8,
    noise: float = 0.01,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = int(duration_sec / interval_sec)
    # 가격 랜덤워크 (연환산 vol 을 스텝 vol 로 환산)
    step_vol = annual_vol * np.sqrt(interval_sec / (365 * 24 * 3600))
    rets = rng.normal(0, step_vol, n)
    price = 100_000 * np.cumprod(1 + rets)
    strike = float(price[0])

    fair = np.array(
        [
            implied_prob_up(
                float(price[i]), strike, (n - i) * interval_sec, annual_vol
            )
            for i in range(n)
        ]
    )

    lag_steps = max(int(lag_sec / interval_sec), 0)
    # Polymarket 중간값 = 공정확률을 lag 만큼 지연 + 노이즈
    delayed = np.empty(n)
    delayed[:lag_steps] = fair[0]
    delayed[lag_steps:] = fair[: n - lag_steps]
    mid = np.clip(delayed + rng.normal(0, noise, n), 0.01, 0.99)
    best_ask = np.clip(mid + spread / 2, 0.0, 1.0)
    best_bid = np.clip(mid - spread / 2, 0.0, 1.0)

    rows = []
    t0 = 0.0
    for i in range(n):
        direction, edge = compute_edge(
            float(fair[i]), float(best_ask[i]), float(best_bid[i]), cost
        )
        rows.append(
            {
                "ts": t0 + i * interval_sec,
                "binance_price": float(price[i]),
                "strike": strike,
                "tau_sec": (n - i) * interval_sec,
                "vol": annual_vol,
                "fair_prob": float(fair[i]),
                "pm_mid": float(mid[i]),
                "pm_best_bid": float(best_bid[i]),
                "pm_best_ask": float(best_ask[i]),
                "gap": float(fair[i] - mid[i]),
                "direction": direction,
                "net_edge": edge,
            }
        )
    return pd.DataFrame(rows, columns=CSV_COLUMNS)
