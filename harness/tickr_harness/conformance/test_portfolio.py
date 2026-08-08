"""t8_portfolio: basket-level forecast, value and expected value."""
import pytest

from tickr.models import Prediction, Tick
from tickr.portfolio import (portfolio_expected_value, portfolio_forecast,
                             portfolio_value)
from tickr.predict import Predictor
from tickr.store import TickStore

LINEAR20 = [float(100 + i) for i in range(20)]
AAPL_FORECAST = 127.15068493150686  # Predictor() over LINEAR20


def _store():
    """AAPL is forecastable (20 ticks), MSFT is not (5 ticks), GOOG is absent."""
    store = TickStore()
    for i, price in enumerate(LINEAR20):
        store.add(Tick(symbol="AAPL", ts=1000 + 60 * i, price=price, volume=1))
    for i in range(5):
        store.add(Tick(symbol="MSFT", ts=1000 + 60 * i, price=50.0, volume=1))
    return store


@pytest.mark.turn("t8_portfolio")
def test_forecast_preserves_input_order():
    result = portfolio_forecast(_store(), Predictor(), ["MSFT", "AAPL", "GOOG"])
    assert list(result.keys()) == ["MSFT", "AAPL", "GOOG"]


@pytest.mark.turn("t8_portfolio")
def test_forecast_collapses_duplicate_symbols():
    result = portfolio_forecast(_store(), Predictor(),
                                ["AAPL", "MSFT", "AAPL", "MSFT", "AAPL"])
    assert list(result.keys()) == ["AAPL", "MSFT"]


@pytest.mark.turn("t8_portfolio")
def test_forecast_maps_unforecastable_symbols_to_none():
    result = portfolio_forecast(_store(), Predictor(), ["AAPL", "MSFT", "GOOG"])
    assert isinstance(result["AAPL"], Prediction)
    assert result["MSFT"] is None
    assert result["GOOG"] is None


@pytest.mark.turn("t8_portfolio")
def test_forecast_values_match_the_predictor():
    store = _store()
    predictor = Predictor()
    result = portfolio_forecast(store, predictor, ["AAPL"])
    assert result["AAPL"].price == pytest.approx(AAPL_FORECAST, rel=1e-9)
    assert result["AAPL"] == predictor.predict(store, "AAPL")


@pytest.mark.turn("t8_portfolio")
def test_forecast_of_no_symbols_is_empty():
    assert portfolio_forecast(_store(), Predictor(), []) == {}


@pytest.mark.turn("t8_portfolio")
def test_value_sums_latest_price_times_quantity():
    assert portfolio_value(_store(), {"AAPL": 2, "MSFT": 3}) == pytest.approx(
        119.0 * 2 + 50.0 * 3, abs=1e-6)


@pytest.mark.turn("t8_portfolio")
def test_value_ignores_symbols_with_no_ticks():
    assert portfolio_value(_store(), {"AAPL": 1, "GOOG": 10}) == pytest.approx(
        119.0, abs=1e-6)
    assert portfolio_value(_store(), {"GOOG": 10}) == pytest.approx(0.0, abs=1e-6)


@pytest.mark.turn("t8_portfolio")
def test_value_of_empty_holdings_is_zero():
    assert portfolio_value(_store(), {}) == pytest.approx(0.0, abs=1e-6)
    assert portfolio_value(TickStore(), {}) == pytest.approx(0.0, abs=1e-6)


@pytest.mark.turn("t8_portfolio")
def test_value_handles_zero_and_negative_quantities():
    assert portfolio_value(_store(), {"AAPL": 0}) == pytest.approx(0.0, abs=1e-6)
    assert portfolio_value(_store(), {"AAPL": -2}) == pytest.approx(
        -238.0, abs=1e-6)


@pytest.mark.turn("t8_portfolio")
def test_expected_value_uses_the_forecast_price():
    assert portfolio_expected_value(_store(), Predictor(), {"AAPL": 2}) == \
        pytest.approx(AAPL_FORECAST * 2, rel=1e-9)


@pytest.mark.turn("t8_portfolio")
def test_expected_value_falls_back_to_the_latest_price():
    # MSFT has ticks but too few to forecast.
    assert portfolio_expected_value(_store(), Predictor(), {"MSFT": 3}) == \
        pytest.approx(150.0, abs=1e-6)


@pytest.mark.turn("t8_portfolio")
def test_expected_value_mixes_forecast_fallback_and_missing_symbols():
    holdings = {"AAPL": 2, "MSFT": 3, "GOOG": 10}
    assert portfolio_expected_value(_store(), Predictor(), holdings) == \
        pytest.approx(AAPL_FORECAST * 2 + 150.0, rel=1e-9)


@pytest.mark.turn("t8_portfolio")
def test_expected_value_of_empty_holdings_is_zero():
    assert portfolio_expected_value(_store(), Predictor(), {}) == pytest.approx(
        0.0, abs=1e-6)


@pytest.mark.turn("t8_portfolio")
def test_expected_value_equals_value_when_nothing_is_forecastable():
    holdings = {"MSFT": 3, "GOOG": 10}
    store = _store()
    assert portfolio_expected_value(store, Predictor(), holdings) == \
        pytest.approx(portfolio_value(store, holdings), abs=1e-6)


@pytest.mark.turn("t8_portfolio")
def test_portfolio_helpers_do_not_mutate_the_store():
    store = _store()
    holdings = {"AAPL": 1, "MSFT": 1}
    portfolio_forecast(store, Predictor(), ["AAPL", "MSFT"])
    portfolio_value(store, holdings)
    portfolio_expected_value(store, Predictor(), holdings)
    assert store.symbols() == ["AAPL", "MSFT"]
    assert len(store.ticks("AAPL")) == 20
    assert len(store.ticks("MSFT")) == 5
