"""Predictor: momentum forecast, confidence clamp, and the t2 MACD term."""
import math

import pytest

from tickr.models import Prediction, Tick
from tickr.predict import Predictor
from tickr.store import TickStore

LINEAR20 = [float(100 + i) for i in range(20)]
LINEAR40 = [float(100 + i) for i in range(40)]
# 40 points with real curvature, so the MACD term is non-zero.
WOBBLY40 = [100.0 + math.sin(i / 3.0) * 5 + i * 0.1 for i in range(40)]


def _store(prices, symbol="AAPL", start_ts=1000, step=60):
    store = TickStore()
    for i, price in enumerate(prices):
        store.add(Tick(symbol=symbol, ts=start_ts + step * i,
                       price=price, volume=1))
    return store


@pytest.mark.turn("t1_scaffold")
def test_predict_returns_none_below_long_window():
    assert Predictor().predict(_store(LINEAR20[:19]), "AAPL") is None


@pytest.mark.turn("t1_scaffold")
def test_predict_returns_none_for_unknown_symbol():
    assert Predictor().predict(_store(LINEAR20), "NOPE") is None
    assert Predictor().predict(TickStore(), "AAPL") is None


@pytest.mark.turn("t1_scaffold")
def test_predict_works_at_exactly_long_window():
    prediction = Predictor().predict(_store(LINEAR20), "AAPL")
    assert isinstance(prediction, Prediction)


@pytest.mark.turn("t1_scaffold")
def test_predict_exact_price_and_confidence():
    prediction = Predictor().predict(_store(LINEAR20), "AAPL")
    assert prediction.price == pytest.approx(127.15068493150686, rel=1e-9)
    assert prediction.confidence == pytest.approx(0.5154385464424035, rel=1e-9)


@pytest.mark.turn("t1_scaffold")
def test_predict_symbol_ts_and_horizon_come_from_arguments_and_config():
    store = _store(LINEAR20, symbol="MSFT", start_ts=5000, step=60)
    prediction = Predictor(horizon=300).predict(store, "MSFT")
    assert prediction.symbol == "MSFT"
    assert prediction.ts == store.latest("MSFT").ts == 5000 + 19 * 60
    assert prediction.horizon == 300


@pytest.mark.turn("t1_scaffold")
def test_predict_default_horizon_is_60():
    assert Predictor().predict(_store(LINEAR20), "AAPL").horizon == 60


@pytest.mark.turn("t1_scaffold")
def test_predict_confidence_clamped_to_one_for_a_flat_series():
    prediction = Predictor().predict(_store([100.0] * 20), "AAPL")
    assert prediction.confidence == pytest.approx(1.0, abs=1e-6)
    assert prediction.price == pytest.approx(100.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_predict_confidence_clamped_to_zero_for_a_wild_series():
    prices = [50.0 if i % 2 == 0 else 150.0 for i in range(20)]
    prediction = Predictor().predict(_store(prices), "AAPL")
    assert prediction.confidence == pytest.approx(0.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_predict_confidence_always_within_unit_interval():
    for prices in (LINEAR20, LINEAR40, WOBBLY40, [100.0] * 25):
        prediction = Predictor().predict(_store(prices), "AAPL")
        assert 0.0 <= prediction.confidence <= 1.0


@pytest.mark.turn("t1_scaffold")
def test_predict_honours_custom_windows():
    store = _store(LINEAR20)
    assert Predictor(short_window=2, long_window=25).predict(store, "AAPL") is None
    prediction = Predictor(short_window=2, long_window=10,
                           use_macd=False).predict(store, "AAPL")
    # sma2 = 118.5, sma10 = 114.5, last = 119
    expected = 119.0 * (1 + (118.5 - 114.5) / 114.5)
    assert prediction.price == pytest.approx(expected, rel=1e-9)


@pytest.mark.turn("t2_macd")
def test_predict_use_macd_false_reproduces_the_pre_macd_price():
    prediction = Predictor(use_macd=False).predict(_store(WOBBLY40), "AAPL")
    assert prediction.price == pytest.approx(105.5951493087959, rel=1e-9)


@pytest.mark.turn("t2_macd")
def test_predict_use_macd_true_adds_the_macd_term():
    prediction = Predictor().predict(_store(WOBBLY40), "AAPL")
    assert prediction.price == pytest.approx(105.66786861687048, rel=1e-9)


@pytest.mark.turn("t2_macd")
def test_predict_macd_term_is_half_the_macd_histogram():
    from tickr.indicators import macd

    store = _store(WOBBLY40)
    with_macd = Predictor(use_macd=True).predict(store, "AAPL")
    without = Predictor(use_macd=False).predict(store, "AAPL")
    macd_line, signal_line = macd("AAPL", WOBBLY40)
    assert with_macd.price - without.price == pytest.approx(
        (macd_line - signal_line) * 0.5, rel=1e-9)
    assert with_macd.price != pytest.approx(without.price, abs=1e-6)


@pytest.mark.turn("t2_macd")
def test_predict_use_macd_defaults_to_true():
    store = _store(WOBBLY40)
    assert Predictor().predict(store, "AAPL").price == pytest.approx(
        Predictor(use_macd=True).predict(store, "AAPL").price, rel=1e-9)


@pytest.mark.turn("t2_macd")
def test_predict_ignores_macd_when_it_returns_none():
    # 20 prices < slow + signal - 1 = 34, so macd() is None either way.
    store = _store(LINEAR20)
    assert Predictor(use_macd=True).predict(store, "AAPL").price == pytest.approx(
        Predictor(use_macd=False).predict(store, "AAPL").price, rel=1e-9)


@pytest.mark.turn("t2_macd")
def test_predict_confidence_is_unaffected_by_use_macd():
    store = _store(WOBBLY40)
    assert Predictor(use_macd=True).predict(store, "AAPL").confidence == \
        pytest.approx(Predictor(use_macd=False).predict(store, "AAPL").confidence,
                      rel=1e-9)


@pytest.mark.turn("t1_scaffold")
def test_predict_does_not_mutate_the_store():
    store = _store(WOBBLY40)
    before = store.prices("AAPL")
    Predictor().predict(store, "AAPL")
    assert store.prices("AAPL") == pytest.approx(before, abs=1e-9)
    assert store.symbols() == ["AAPL"]
