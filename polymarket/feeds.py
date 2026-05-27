"""읽기 전용 시세 피드 (라이브 전용).

여기서 하는 일은 '읽기'뿐이다. 주문 제출도, 개인키/API 키 입력도 없다.
- 바이낸스: 공개 현물 가격 (REST)
- Polymarket: 공개 CLOB 오더북 (REST, 인증 불필요)

네트워크가 막힌 환경에서는 호출 시 예외가 나며, 분석/시뮬레이션 경로는
이 모듈 없이도 동작한다.
"""
from __future__ import annotations

import requests


class BinanceFeed:
    """바이낸스 공개 현물 가격 (REST 폴링)."""

    def __init__(self, base: str = "https://api.binance.com", timeout: float = 5.0):
        self.base = base
        self.timeout = timeout

    def get_price(self, symbol: str = "BTCUSDT") -> float:
        r = requests.get(
            f"{self.base}/api/v3/ticker/price",
            params={"symbol": symbol},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return float(r.json()["price"])


class PolymarketFeed:
    """Polymarket 공개 CLOB 오더북 (읽기 전용, 인증 불필요)."""

    def __init__(self, base: str = "https://clob.polymarket.com", timeout: float = 5.0):
        self.base = base
        self.timeout = timeout

    def get_book(self, token_id: str) -> dict:
        """outcome 토큰의 최우선 매수/매도 호가와 중간값."""
        r = requests.get(
            f"{self.base}/book", params={"token_id": token_id}, timeout=self.timeout
        )
        r.raise_for_status()
        data = r.json()
        bids = data.get("bids") or []
        asks = data.get("asks") or []
        best_bid = max((float(b["price"]) for b in bids), default=0.0)
        best_ask = min((float(a["price"]) for a in asks), default=1.0)
        mid = (best_bid + best_ask) / 2 if bids and asks else None
        return {"best_bid": best_bid, "best_ask": best_ask, "mid": mid}
