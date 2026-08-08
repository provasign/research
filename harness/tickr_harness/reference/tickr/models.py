"""Frozen data carriers for the tickr contract."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tick:
    symbol: str
    ts: int          # epoch seconds
    price: float
    volume: int


@dataclass(frozen=True)
class Prediction:
    symbol: str
    ts: int          # ts of the tick this prediction was made from
    horizon: int     # seconds ahead
    price: float     # predicted price
    confidence: float  # clamped to [0.0, 1.0]


@dataclass(frozen=True)
class Alert:
    symbol: str
    ts: int
    kind: str        # "threshold" or "signal"
    message: str
