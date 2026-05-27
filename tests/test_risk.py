from src.risk import MIN_ORDER_KRW, RiskManager


def test_position_size_uses_ratio():
    r = RiskManager(invest_ratio=0.5)
    assert r.position_size(1_000_000) == 500_000


def test_position_size_below_minimum_is_zero():
    r = RiskManager(invest_ratio=0.9995)
    assert r.position_size(1000) == 0.0  # 최소 주문금액 미만
    assert r.position_size(MIN_ORDER_KRW + 100) > 0


def test_position_size_splits_across_slots():
    r = RiskManager(invest_ratio=1.0)
    assert r.position_size(1_000_000, slots=4) == 250_000


def test_trailing_stop_triggers_after_min_profit():
    r = RiskManager(trail_stop_pct=0.05, trail_min_profit_pct=0.005)
    # 진입100, 고점120, 현재113: 고점 대비 -5.8% & 수익 +13% -> 청산
    assert r.should_trailing_stop(100, 120, 113) is True


def test_trailing_stop_blocked_below_min_profit():
    r = RiskManager(trail_stop_pct=0.05, trail_min_profit_pct=0.02)
    # 현재100.5 는 진입가 대비 +0.5% 로 최소수익(2%) 미달 -> 미발동
    assert r.should_trailing_stop(100, 101, 100.5) is False


def test_trailing_stop_disabled_by_default():
    r = RiskManager()  # trail_stop_pct None
    assert r.should_trailing_stop(100, 200, 150) is False


def test_stop_loss_triggers():
    r = RiskManager(stop_loss_pct=0.05)
    assert r.should_stop_loss(entry_price=100, current_price=94) is True   # -6%
    assert r.should_stop_loss(entry_price=100, current_price=96) is False  # -4%


def test_daily_limit():
    r = RiskManager(daily_loss_limit_pct=10)
    assert r.daily_limit_hit(-12) is True
    assert r.daily_limit_hit(-5) is False
