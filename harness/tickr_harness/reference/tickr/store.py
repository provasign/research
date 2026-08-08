"""In-memory rolling tick store, bounded per symbol."""
from __future__ import annotations

from collections import deque

from .models import Tick


class TickStore:
    def __init__(self, max_ticks: int = 1000) -> None:
        self.max_ticks = max_ticks
        self._by_symbol: dict[str, deque[Tick]] = {}

    def add(self, tick: Tick) -> None:
        bucket = self._by_symbol.get(tick.symbol)
        if bucket is None:
            bucket = deque(maxlen=self.max_ticks)
            self._by_symbol[tick.symbol] = bucket
        bucket.append(tick)

    def prices(self, symbol: str) -> list[float]:
        return [t.price for t in self._by_symbol.get(symbol, ())]

    def ticks(self, symbol: str) -> list[Tick]:
        return list(self._by_symbol.get(symbol, ()))

    def latest(self, symbol: str) -> Tick | None:
        bucket = self._by_symbol.get(symbol)
        if not bucket:
            return None
        return bucket[-1]

    def symbols(self) -> list[str]:
        return sorted(self._by_symbol)
