"""Edge-triggered alert engine.

Threshold alerts fire only on the inside -> outside transition; signal alerts
are rate-limited to one per symbol per 300 seconds of tick time.
"""
from __future__ import annotations

from .models import Alert, Prediction
from .store import TickStore

SIGNAL_MOVE = 0.02
SIGNAL_WINDOW = 300


class AlertEngine:
    def __init__(self) -> None:
        self._thresholds: dict[str, tuple[float, float]] = {}
        self._outside: dict[str, bool] = {}
        self._last_signal_ts: dict[str, int] = {}
        self._history: list[Alert] = []

    def add_threshold(self, symbol: str, low: float, high: float) -> None:
        # A registration replaces any previous one, and re-arms the symbol.
        self._thresholds[symbol] = (low, high)
        self._outside[symbol] = False

    def check(self, store: TickStore, symbol: str,
              prediction: Prediction | None) -> list[Alert]:
        latest = store.latest(symbol)
        if latest is None:
            return []

        raised: list[Alert] = []

        band = self._thresholds.get(symbol)
        if band is not None:
            low, high = band
            below = latest.price < low
            above = latest.price > high
            if below or above:
                if not self._outside.get(symbol, False):
                    if below:
                        message = f"{symbol} below {low}"
                    else:
                        message = f"{symbol} above {high}"
                    raised.append(Alert(symbol=symbol, ts=latest.ts,
                                        kind="threshold", message=message))
                self._outside[symbol] = True
            else:
                self._outside[symbol] = False

        if prediction is not None and latest.price != 0:
            move = (prediction.price - latest.price) / latest.price
            if abs(move) >= SIGNAL_MOVE:
                last = self._last_signal_ts.get(symbol)
                if last is None or latest.ts - last >= SIGNAL_WINDOW:
                    raised.append(Alert(
                        symbol=symbol, ts=latest.ts, kind="signal",
                        message=f"{symbol} predicted move {move * 100:.2f}%"))
                    self._last_signal_ts[symbol] = latest.ts

        self._history.extend(raised)
        return raised

    def history(self) -> list[Alert]:
        return list(self._history)
