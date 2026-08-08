"""Portfolio-level aggregation on top of the store and the predictor."""
from __future__ import annotations

from .models import Prediction
from .predict import Predictor
from .store import TickStore


def portfolio_forecast(store: TickStore, predictor: Predictor,
                       symbols: list[str]) -> dict[str, Prediction | None]:
    out: dict[str, Prediction | None] = {}
    for symbol in symbols:
        if symbol in out:
            continue
        out[symbol] = predictor.predict(store, symbol)
    return out


def portfolio_value(store: TickStore, holdings: dict[str, int]) -> float:
    total = 0.0
    for symbol, qty in holdings.items():
        latest = store.latest(symbol)
        if latest is None:
            continue
        total += latest.price * qty
    return total


def portfolio_expected_value(store: TickStore, predictor: Predictor,
                             holdings: dict[str, int]) -> float:
    forecasts = portfolio_forecast(store, predictor, list(holdings))
    total = 0.0
    for symbol, qty in holdings.items():
        latest = store.latest(symbol)
        if latest is None:
            continue
        forecast = forecasts.get(symbol)
        price = latest.price if forecast is None else forecast.price
        total += price * qty
    return total
