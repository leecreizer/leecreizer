import math

import pytest

from polymarket.fair_value import annualized_vol, compute_edge, implied_prob_up


def test_implied_prob_at_strike_is_half():
    p = implied_prob_up(price=100, strike=100, tau_sec=600, annual_vol=0.8)
    assert abs(p - 0.5) < 1e-9


def test_implied_prob_monotonic_in_price():
    lo = implied_prob_up(99, 100, 600, 0.8)
    hi = implied_prob_up(101, 100, 600, 0.8)
    assert lo < 0.5 < hi


def test_implied_prob_expiry_is_step():
    assert implied_prob_up(101, 100, tau_sec=0, annual_vol=0.8) == 1.0
    assert implied_prob_up(99, 100, tau_sec=0, annual_vol=0.8) == 0.0


def test_implied_prob_rejects_nonpositive():
    with pytest.raises(ValueError):
        implied_prob_up(0, 100, 600, 0.8)


def test_annualized_vol_zero_for_flat_series():
    assert annualized_vol([100, 100, 100, 100], dt_sec=1.0) == 0.0


def test_annualized_vol_positive():
    v = annualized_vol([100, 101, 100, 102, 99], dt_sec=1.0)
    assert v > 0 and math.isfinite(v)


def test_compute_edge_picks_underpriced_side():
    # 공정확률 0.8 인데 UP 매도호가 0.55 -> UP 매수 엣지 큼
    direction, edge = compute_edge(fair_prob=0.8, up_ask=0.55, up_bid=0.53, cost=0.0)
    assert direction == "UP"
    assert abs(edge - (0.8 - 0.55)) < 1e-9


def test_compute_edge_down_side():
    # 공정확률 0.2 (UP 비쌈) -> DOWN 매수가 유리
    direction, edge = compute_edge(fair_prob=0.2, up_ask=0.55, up_bid=0.45, cost=0.0)
    assert direction == "DOWN"
    # DOWN ask = 1 - up_bid = 0.55; (1-0.2)-0.55 = 0.25
    assert abs(edge - 0.25) < 1e-9
