"""봇 상태(포지션) 영속화.

봇이 재시작돼도 진입가/당일고가를 복구할 수 있도록 JSON 으로 저장한다.
실제 보유 수량은 거래소 잔고가 진실원본이고, 여기서는 손절/트레일링에 필요한
'진입가'와 '진입 후 당일 고가' 같은 봇 고유 메타데이터만 보관한다.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class Position:
    ticker: str
    entry_price: float = 0.0
    day_high: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.entry_price > 0

    def reset(self) -> None:
        self.entry_price = 0.0
        self.day_high = 0.0


class StateStore:
    def __init__(self, path: str = "state.json"):
        self.path = path

    def load(self, tickers: list[str]) -> dict[str, Position]:
        positions = {t: Position(t) for t in tickers}
        if not os.path.exists(self.path):
            return positions
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return positions  # 손상된 파일이면 새 상태로 시작
        for t in tickers:
            d = data.get(t)
            if d:
                positions[t] = Position(
                    ticker=t,
                    entry_price=float(d.get("entry_price", 0.0)),
                    day_high=float(d.get("day_high", 0.0)),
                )
        return positions

    def save(self, positions: dict[str, Position]) -> None:
        data = {
            t: {"entry_price": p.entry_price, "day_high": p.day_high}
            for t, p in positions.items()
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)  # 원자적 교체(쓰기 도중 중단돼도 손상 방지)
