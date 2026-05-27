"""공정확률(fair value) 계산 — 순수 함수, 네트워크 불필요.

바이낸스 현물 가격으로 "단기 up/down 이진 계약"의 공정 확률을 추정한다.
모델: 분 단위 짧은 만기에서는 드리프트를 0 으로 두고, 로그수익률이
정규분포를 따른다고 가정한다(디지털 옵션 근사).

    P(만기가격 >= 행사가) = Φ( ln(P/K) / (σ·√τ) )

여기서 P=현재가, K=행사가(예: 계약 시작가), τ=잔여시간(년), σ=연환산 변동성.
"""
from __future__ import annotations

import math
from typing import Sequence

SECONDS_PER_YEAR = 365 * 24 * 3600


def _phi(z: float) -> float:
    """표준정규 누적분포."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def annualized_vol(prices: Sequence[float], dt_sec: float) -> float:
    """등간격 가격 시계열의 연환산 변동성(로그수익률 표준편차 기반)."""
    if len(prices) < 2 or dt_sec <= 0:
        return 0.0
    rets = [
        math.log(prices[i] / prices[i - 1])
        for i in range(1, len(prices))
        if prices[i] > 0 and prices[i - 1] > 0
    ]
    n = len(rets)
    if n < 2:
        return 0.0
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)  # 표본분산
    sigma_step = math.sqrt(var)
    steps_per_year = SECONDS_PER_YEAR / dt_sec
    return sigma_step * math.sqrt(steps_per_year)


def implied_prob_up(
    price: float, strike: float, tau_sec: float, annual_vol: float
) -> float:
    """현재가/행사가/잔여시간/변동성으로 'UP(가격 상승)' 확률 추정. 0~1."""
    if price <= 0 or strike <= 0:
        raise ValueError("price/strike must be > 0")
    # 만기 도달 또는 변동성 0 이면 계단함수(결과 확정)
    if tau_sec <= 0 or annual_vol <= 0:
        if price > strike:
            return 1.0
        if price < strike:
            return 0.0
        return 0.5
    tau_years = tau_sec / SECONDS_PER_YEAR
    denom = annual_vol * math.sqrt(tau_years)
    if denom == 0:
        return 1.0 if price > strike else (0.0 if price < strike else 0.5)
    z = math.log(price / strike) / denom
    return _phi(z)


def compute_edge(
    fair_prob: float,
    up_ask: float,
    up_bid: float,
    cost: float = 0.0,
) -> tuple[str, float]:
    """공정확률 대비 체결가 기준 순엣지. 매수 방향과 엣지값을 반환.

    - UP 매수: 공정확률 - UP 매도호가(ask) - 비용
    - DOWN 매수: (1-공정확률) - DOWN 매도호가 - 비용  (DOWN ask ≈ 1 - UP bid)
    """
    buy_up = fair_prob - up_ask - cost
    down_ask = 1.0 - up_bid
    buy_down = (1.0 - fair_prob) - down_ask - cost
    if buy_up >= buy_down:
        return "UP", buy_up
    return "DOWN", buy_down
