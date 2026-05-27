"""멀티코인 종목 선정: 노이즈(추세 약함) 낮은 코인을 우선 선택.

noise = 1 - |open-close| / (high-low). 캔들의 몸통 비중이 클수록(추세적일수록)
noise 가 낮다. 변동성 돌파는 추세장에서 유리하므로 noise 가 낮은 코인을 고른다.
"""
from __future__ import annotations

import pandas as pd


def average_noise(df: pd.DataFrame, days: int) -> float:
    recent = df.iloc[-days:]
    rng = (recent["high"] - recent["low"]).replace(0, pd.NA)
    noise = 1 - (recent["open"] - recent["close"]).abs() / rng
    return float(noise.mean())


def select_low_noise(
    candidates: dict[str, pd.DataFrame],
    days: int = 5,
    limit: int = 5,
    noise_limit: float = 0.6,
) -> list[str]:
    scored: list[tuple[float, str]] = []
    for ticker, df in candidates.items():
        if df is None or len(df) < days:
            continue
        n = average_noise(df, days)
        if n <= noise_limit:
            scored.append((n, ticker))
    scored.sort()
    return [t for _, t in scored[:limit]]
