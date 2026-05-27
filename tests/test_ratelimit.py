from src.ratelimit import RateLimiter, TTLCache


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def test_rate_limiter_first_call_no_sleep():
    clock = FakeClock()
    slept = []
    rl = RateLimiter(0.125, clock=clock, sleep=lambda d: slept.append(d))
    rl.wait()
    assert slept == []


def test_rate_limiter_enforces_min_interval():
    clock = FakeClock()
    slept = []

    def sleep(d):
        slept.append(d)
        clock.advance(d)  # 잠든 만큼 시간 흐름 시뮬레이션

    rl = RateLimiter(0.125, clock=clock, sleep=sleep)
    rl.wait()              # last=0
    clock.advance(0.05)    # 0.05s 만 지남 (작업 시간)
    rl.wait()              # 0.075s 추가로 자야 함
    assert slept == [0.075]


def test_ttl_cache_hit_and_expiry():
    clock = FakeClock()
    cache = TTLCache(ttl=10, clock=clock)
    cache.set("a", 123)
    assert cache.get("a") == 123
    clock.advance(9)
    assert cache.get("a") == 123  # 아직 유효
    clock.advance(2)
    assert cache.get("a") is None  # 만료


def test_ttl_cache_miss():
    assert TTLCache(ttl=10).get("missing") is None
