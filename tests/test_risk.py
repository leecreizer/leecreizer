from src.risk import MIN_ORDER_KRW, RiskManager


def test_position_size_uses_ratio():
    r = RiskManager(invest_ratio=0.5)
    assert r.position_size(1_000_000) == 500_000


def test_position_size_below_minimum_is_zero():
    r = RiskManager(invest_ratio=0.9995)
    assert r.position_size(1000) == 0.0  # 최소 주문금액 미만
    assert r.position_size(MIN_ORDER_KRW + 100) > 0


def test_stop_loss_triggers():
    r = RiskManager(stop_loss_pct=0.05)
    assert r.should_stop_loss(entry_price=100, current_price=94) is True   # -6%
    assert r.should_stop_loss(entry_price=100, current_price=96) is False  # -4%


def test_daily_limit():
    r = RiskManager(daily_loss_limit_pct=10)
    assert r.daily_limit_hit(-12) is True
    assert r.daily_limit_hit(-5) is False
