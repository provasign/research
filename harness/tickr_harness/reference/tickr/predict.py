"""Momentum + MACD price predictor."""
from __future__ import annotations

from .indicators import macd, sma, volatility
from .models import Prediction
from .store import TickStore


class Predictor:
    def __init__(self, short_window: int = 5, long_window: int = 20,
                 horizon: int = 60, use_macd: bool = True) -> None:
        self.short_window = short_window
        self.long_window = long_window
        self.horizon = horizon
        self.use_macd = use_macd

    def predict(self, store: TickStore, symbol: str) -> Prediction | None:
        prices = store.prices(symbol)
        if len(prices) < self.long_window:
            return None
        s = sma(symbol, prices, self.short_window)
        l = sma(symbol, prices, self.long_window)
        if s is None or l is None or l == 0:
            return None
        momentum = (s - l) / l
        last = prices[-1]
        price = last * (1 + momentum)
        if self.use_macd:
            m = macd(symbol, prices)
            if m is not None:
                macd_line, signal_line = m
                price = price + (macd_line - signal_line) * 0.5
        vol = volatility(symbol, prices, self.long_window)
        if last == 0:
            confidence = 0.0
        else:
            confidence = 1.0 - (vol / last) * 10
            confidence = max(0.0, min(1.0, confidence))
        latest = store.latest(symbol)
        return Prediction(
            symbol=symbol,
            ts=latest.ts,
            horizon=self.horizon,
            price=price,
            confidence=confidence,
        )
