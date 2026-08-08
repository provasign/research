"""Deterministic synthetic market feed.

Bit-for-bit reproducible: one 32-bit LCG per feed instance, and within a tick
`_rand()` is called for the delta first, then for the volume.
"""
from __future__ import annotations

from .models import Tick

_LCG_A = 1103515245
_LCG_C = 12345
_LCG_M = 2 ** 31


class SyntheticFeed:
    def __init__(self, symbols: list[str], seed: int,
                 start_ts: int = 1700000000, start_price: float = 100.0) -> None:
        self.symbols = list(symbols)
        self.seed = seed
        self.start_ts = start_ts
        self.start_price = start_price
        self._state = seed
        self._i = 0
        self._prev_price: dict[str, float] = {s: start_price for s in self.symbols}

    def _rand(self) -> int:
        self._state = (_LCG_A * self._state + _LCG_C) % _LCG_M
        return self._state

    def next_tick(self) -> Tick:
        n = len(self.symbols)
        i = self._i
        symbol = self.symbols[i % n]
        ts = self.start_ts + (i // n) * 60
        delta = ((self._rand() % 2001) - 1000) / 10000.0
        prev = self._prev_price.get(symbol, self.start_price)
        price = prev * (1 + delta)
        volume = self._rand() % 10000
        self._prev_price[symbol] = price
        self._i += 1
        return Tick(symbol=symbol, ts=ts, price=price, volume=volume)

    def take(self, n: int) -> list[Tick]:
        return [self.next_tick() for _ in range(n)]
