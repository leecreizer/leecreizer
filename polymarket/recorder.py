"""레코더: 두 피드를 폴링해 공정확률·갭·순엣지를 CSV 로 기록 (읽기 전용).

feeds 객체는 주입식이라 테스트에서 가짜 피드로 대체할 수 있다.
"""
from __future__ import annotations

import csv
import time
from collections import deque
from typing import Callable

from . import CSV_COLUMNS
from .fair_value import annualized_vol, compute_edge, implied_prob_up


class Recorder:
    def __init__(
        self,
        binance,
        polymarket,
        symbol: str,
        token_id: str,
        strike: float,
        expiry_ts: float,
        interval: float = 1.0,
        vol_window: int = 60,
        cost: float = 0.0,
        clock: Callable[[], float] = time.time,
    ):
        self.binance = binance
        self.pm = polymarket
        self.symbol = symbol
        self.token_id = token_id
        self.strike = strike
        self.expiry_ts = expiry_ts
        self.interval = interval
        self.cost = cost
        self._clock = clock
        self._prices: deque[float] = deque(maxlen=vol_window)

    def sample(self) -> dict:
        now = self._clock()
        price = self.binance.get_price(self.symbol)
        self._prices.append(price)
        vol = annualized_vol(list(self._prices), self.interval)
        tau = max(self.expiry_ts - now, 0.0)
        fair = implied_prob_up(price, self.strike, tau, vol)

        book = self.pm.get_book(self.token_id)
        best_bid, best_ask = book["best_bid"], book["best_ask"]
        mid = book["mid"] if book["mid"] is not None else (best_bid + best_ask) / 2
        gap = fair - mid
        direction, edge = compute_edge(fair, best_ask, best_bid, self.cost)

        return {
            "ts": now,
            "binance_price": price,
            "strike": self.strike,
            "tau_sec": tau,
            "vol": vol,
            "fair_prob": fair,
            "pm_mid": mid,
            "pm_best_bid": best_bid,
            "pm_best_ask": best_ask,
            "gap": gap,
            "direction": direction,
            "net_edge": edge,
        }

    def run(self, duration_sec: float, out_csv: str) -> int:
        end = self._clock() + duration_sec
        n = 0
        with open(out_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            while self._clock() < end:
                try:
                    writer.writerow(self.sample())
                    f.flush()
                    n += 1
                except Exception as e:  # noqa: BLE001 - 한 틱 실패해도 계속
                    print(f"[recorder] sample 실패: {e}", flush=True)
                time.sleep(self.interval)
        return n
