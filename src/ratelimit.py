"""API 호출 속도 제한 + 단순 TTL 캐시.

업비트 REST API 는 초당 요청 수 제한이 있다(시세 ~10/s, 주문 ~8/s). 멀티코인이면
매 틱마다 코인 수만큼 호출하므로, 호출 간 최소 간격을 강제하고 일봉처럼 자주
변하지 않는 응답은 캐시해 요청 수를 줄인다.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Hashable


class RateLimiter:
    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            elapsed = now - self._last
            if elapsed < self.min_interval:
                self._sleep(self.min_interval - elapsed)
        self._last = self._clock()


class TTLCache:
    def __init__(self, ttl: float, clock: Callable[[], float] = time.monotonic):
        self.ttl = ttl
        self._clock = clock
        self._store: dict[Hashable, tuple[float, Any]] = {}

    def get(self, key: Hashable) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if self._clock() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: Hashable, value: Any) -> None:
        self._store[key] = (self._clock() + self.ttl, value)
