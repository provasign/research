"""Technical indicators.

Every public indicator takes a `series_id` as its required first parameter and
appends it to a module-level trace log — including calls that return `None`,
and including the `ema` calls that `macd` makes internally.

Nothing here ever raises on short input: it returns `None`.
"""
from __future__ import annotations

import math

_TRACE: list[str] = []


def traces() -> list[str]:
    """Every series_id seen, in call order. Returns a copy."""
    return list(_TRACE)


def clear_traces() -> None:
    _TRACE.clear()


def _trace(series_id: str) -> None:
    _TRACE.append(series_id)


# --------------------------------------------------------------- internals
def _sma(values: list[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def _ema(values: list[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    alpha = 2 / (window + 1)
    e = _sma(values[:window], window)
    for value in values[window:]:
        e = value * alpha + e * (1 - alpha)
    return e


# ------------------------------------------------------------------ public
def sma(series_id: str, values: list[float], window: int) -> float | None:
    _trace(series_id)
    return _sma(values, window)


def ema(series_id: str, values: list[float], window: int) -> float | None:
    _trace(series_id)
    return _ema(values, window)


def rsi(series_id: str, values: list[float], window: int = 14) -> float | None:
    _trace(series_id)
    if window <= 0 or len(values) < window + 1:
        return None
    deltas = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    head, tail = deltas[:window], deltas[window:]
    avg_gain = sum(max(d, 0.0) for d in head) / window
    avg_loss = sum(max(-d, 0.0) for d in head) / window
    for d in tail:
        avg_gain = (avg_gain * (window - 1) + max(d, 0.0)) / window
        avg_loss = (avg_loss * (window - 1) + max(-d, 0.0)) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def volatility(series_id: str, values: list[float], window: int) -> float | None:
    _trace(series_id)
    if window <= 0 or len(values) < window:
        return None
    w = values[-window:]
    mean = sum(w) / window
    var = sum((v - mean) ** 2 for v in w) / window  # population, not sample
    return math.sqrt(var)


def macd(series_id: str, values: list[float], fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[float, float] | None:
    _trace(series_id)
    if fast <= 0 or slow <= 0 or signal <= 0:
        return None
    if len(values) < slow + signal - 1:
        return None
    macd_series: list[float] = []
    for i in range(slow - 1, len(values)):
        prefix = values[:i + 1]
        f = ema(series_id, prefix, fast)
        s = ema(series_id, prefix, slow)
        if f is None or s is None:
            return None
        macd_series.append(f - s)
    macd_line = macd_series[-1]
    signal_line = ema(series_id, macd_series, signal)
    if signal_line is None:
        return None
    return (macd_line, signal_line)
