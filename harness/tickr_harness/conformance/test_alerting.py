"""AlertEngine, post-t5 (module `tickr.alerting`, method `check`) and post-t7
(edge-triggered thresholds, 300s signal window)."""
import importlib

import pytest

from tickr.alerting import AlertEngine
from tickr.models import Prediction, Tick
from tickr.store import TickStore


def _push(store, price, ts=1000, symbol="AAPL"):
    store.add(Tick(symbol=symbol, ts=ts, price=price, volume=1))
    return store


def _pred(price, symbol="AAPL", ts=1000):
    return Prediction(symbol=symbol, ts=ts, horizon=60, price=price,
                      confidence=0.5)


# ----------------------------------------------------------- module & names
@pytest.mark.turn("t5_rename_move")
def test_alert_engine_lives_in_tickr_alerting():
    from tickr.alerting import AlertEngine as Engine
    assert Engine is AlertEngine


@pytest.mark.turn("t5_rename_move")
def test_tickr_alerts_module_is_gone():
    with pytest.raises(ImportError):
        importlib.import_module("tickr.alerts")


@pytest.mark.turn("t5_rename_move")
def test_alert_engine_has_check_and_no_evaluate():
    assert callable(getattr(AlertEngine, "check", None))
    assert not hasattr(AlertEngine, "evaluate")


# ------------------------------------------------------------------ basics
@pytest.mark.turn("t1_scaffold")
def test_check_returns_empty_when_the_store_has_no_tick():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    assert engine.check(TickStore(), "AAPL", None) == []
    assert engine.history() == []


@pytest.mark.turn("t1_scaffold")
def test_no_threshold_registered_means_no_threshold_alert():
    engine = AlertEngine()
    store = _push(TickStore(), 1000.0)
    assert engine.check(store, "AAPL", None) == []


@pytest.mark.turn("t1_scaffold")
def test_threshold_below_message_and_fields():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    alerts = engine.check(_push(TickStore(), 85.0, ts=1234), "AAPL", None)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.symbol == "AAPL"
    assert alert.ts == 1234
    assert alert.kind == "threshold"
    assert alert.message == "AAPL below 90.0"


@pytest.mark.turn("t1_scaffold")
def test_threshold_above_message_and_fields():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    alerts = engine.check(_push(TickStore(), 120.0, ts=77), "AAPL", None)
    assert len(alerts) == 1
    assert alerts[0].kind == "threshold"
    assert alerts[0].message == "AAPL above 110.0"
    assert alerts[0].ts == 77


@pytest.mark.turn("t1_scaffold")
def test_price_inside_the_band_raises_nothing():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    assert engine.check(_push(TickStore(), 100.0), "AAPL", None) == []


@pytest.mark.turn("t1_scaffold")
def test_registering_a_threshold_replaces_the_previous_band():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    engine.add_threshold("AAPL", 95.0, 105.0)
    alerts = engine.check(_push(TickStore(), 92.0), "AAPL", None)
    assert len(alerts) == 1
    assert alerts[0].message == "AAPL below 95.0"


@pytest.mark.turn("t1_scaffold")
def test_no_signal_when_prediction_is_none():
    engine = AlertEngine()
    assert engine.check(_push(TickStore(), 100.0), "AAPL", None) == []


@pytest.mark.turn("t1_scaffold")
def test_signal_fires_at_exactly_two_percent():
    engine = AlertEngine()
    alerts = engine.check(_push(TickStore(), 100.0, ts=42), "AAPL", _pred(102.0))
    assert len(alerts) == 1
    assert alerts[0].kind == "signal"
    assert alerts[0].ts == 42
    assert alerts[0].message == "AAPL predicted move 2.00%"


@pytest.mark.turn("t1_scaffold")
def test_signal_fires_on_a_negative_move():
    engine = AlertEngine()
    alerts = engine.check(_push(TickStore(), 100.0), "AAPL", _pred(97.0))
    assert len(alerts) == 1
    assert alerts[0].message == "AAPL predicted move -3.00%"


@pytest.mark.turn("t1_scaffold")
def test_signal_does_not_fire_below_two_percent():
    engine = AlertEngine()
    assert engine.check(_push(TickStore(), 100.0), "AAPL", _pred(101.9)) == []


@pytest.mark.turn("t1_scaffold")
def test_signal_message_uses_two_decimal_places():
    engine = AlertEngine()
    alerts = engine.check(_push(TickStore(), 100.0), "AAPL", _pred(103.456))
    assert alerts[0].message == "AAPL predicted move 3.46%"


@pytest.mark.turn("t1_scaffold")
def test_threshold_precedes_signal_within_one_call():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    alerts = engine.check(_push(TickStore(), 80.0), "AAPL", _pred(100.0))
    assert [a.kind for a in alerts] == ["threshold", "signal"]


@pytest.mark.turn("t1_scaffold")
def test_history_is_empty_initially_and_accumulates_oldest_first():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    assert engine.history() == []
    store = TickStore()
    first = engine.check(_push(store, 80.0, ts=1000), "AAPL", None)
    second = engine.check(_push(store, 100.0, ts=1060), "AAPL", _pred(110.0))
    assert engine.history() == first + second
    assert [a.kind for a in engine.history()] == ["threshold", "signal"]


# --------------------------------------------------- t7: edge-triggering
@pytest.mark.turn("t7_bug")
def test_threshold_fires_once_per_excursion():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    store = TickStore()
    raised = []
    for i, price in enumerate([85.0, 84.0, 83.0, 80.0, 89.9]):
        raised.extend(engine.check(_push(store, price, ts=1000 + 60 * i),
                                   "AAPL", None))
    assert len(raised) == 1
    assert raised[0].ts == 1000
    assert raised[0].message == "AAPL below 90.0"
    assert len(engine.history()) == 1


@pytest.mark.turn("t7_bug")
def test_crossing_from_below_low_to_above_high_stays_silent():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    store = TickStore()
    first = engine.check(_push(store, 85.0, ts=1000), "AAPL", None)
    second = engine.check(_push(store, 120.0, ts=1060), "AAPL", None)
    assert len(first) == 1
    assert second == []
    assert len(engine.history()) == 1


@pytest.mark.turn("t7_bug")
def test_returning_inside_the_band_re_arms_the_symbol():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    store = TickStore()
    assert len(engine.check(_push(store, 85.0, ts=1000), "AAPL", None)) == 1
    assert engine.check(_push(store, 100.0, ts=1060), "AAPL", None) == []
    again = engine.check(_push(store, 85.0, ts=1120), "AAPL", None)
    assert len(again) == 1
    assert again[0].ts == 1120
    assert len(engine.history()) == 2


@pytest.mark.turn("t7_bug")
def test_the_re_arm_band_is_inclusive_at_both_ends():
    for boundary in (90.0, 110.0):
        engine = AlertEngine()
        engine.add_threshold("AAPL", 90.0, 110.0)
        store = TickStore()
        assert len(engine.check(_push(store, 200.0, ts=1000), "AAPL", None)) == 1
        assert engine.check(_push(store, boundary, ts=1060), "AAPL", None) == []
        assert len(engine.check(_push(store, 200.0, ts=1120), "AAPL", None)) == 1


@pytest.mark.turn("t7_bug")
def test_re_registering_a_threshold_re_arms_the_symbol():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    store = TickStore()
    assert len(engine.check(_push(store, 85.0, ts=1000), "AAPL", None)) == 1
    assert engine.check(_push(store, 84.0, ts=1060), "AAPL", None) == []
    engine.add_threshold("AAPL", 90.0, 110.0)
    assert len(engine.check(_push(store, 83.0, ts=1120), "AAPL", None)) == 1


@pytest.mark.turn("t7_bug")
def test_threshold_arming_state_is_per_symbol():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    engine.add_threshold("MSFT", 90.0, 110.0)
    store = TickStore()
    _push(store, 85.0, ts=1000, symbol="AAPL")
    _push(store, 85.0, ts=1000, symbol="MSFT")
    assert len(engine.check(store, "AAPL", None)) == 1
    assert len(engine.check(store, "MSFT", None)) == 1
    _push(store, 84.0, ts=1060, symbol="AAPL")
    _push(store, 84.0, ts=1060, symbol="MSFT")
    assert engine.check(store, "AAPL", None) == []
    assert engine.check(store, "MSFT", None) == []


@pytest.mark.turn("t7_bug")
def test_suppressed_threshold_alerts_are_absent_from_history():
    engine = AlertEngine()
    engine.add_threshold("AAPL", 90.0, 110.0)
    store = TickStore()
    for i in range(10):
        engine.check(_push(store, 80.0, ts=1000 + 60 * i), "AAPL", None)
    assert len(engine.history()) == 1


# ------------------------------------------------ t7: signal rate limiting
@pytest.mark.turn("t7_bug")
def test_signal_is_suppressed_inside_the_300_second_window():
    engine = AlertEngine()
    store = TickStore()
    assert len(engine.check(_push(store, 100.0, ts=1000), "AAPL",
                            _pred(105.0))) == 1
    assert engine.check(_push(store, 100.0, ts=1001), "AAPL", _pred(105.0)) == []
    assert engine.check(_push(store, 100.0, ts=1299), "AAPL", _pred(105.0)) == []
    assert len(engine.history()) == 1


@pytest.mark.turn("t7_bug")
def test_signal_fires_again_at_exactly_300_seconds():
    engine = AlertEngine()
    store = TickStore()
    assert len(engine.check(_push(store, 100.0, ts=1000), "AAPL",
                            _pred(105.0))) == 1
    alerts = engine.check(_push(store, 100.0, ts=1300), "AAPL", _pred(105.0))
    assert len(alerts) == 1
    assert alerts[0].kind == "signal"
    assert alerts[0].ts == 1300


@pytest.mark.turn("t7_bug")
def test_signal_window_is_measured_from_the_last_raised_signal():
    engine = AlertEngine()
    store = TickStore()
    assert len(engine.check(_push(store, 100.0, ts=1000), "AAPL",
                            _pred(105.0))) == 1
    # Suppressed, and must NOT restart the window.
    assert engine.check(_push(store, 100.0, ts=1200), "AAPL", _pred(105.0)) == []
    assert len(engine.check(_push(store, 100.0, ts=1300), "AAPL",
                            _pred(105.0))) == 1
    assert [a.ts for a in engine.history()] == [1000, 1300]


@pytest.mark.turn("t7_bug")
def test_signal_suppression_is_per_symbol():
    engine = AlertEngine()
    store = TickStore()
    _push(store, 100.0, ts=1000, symbol="AAPL")
    _push(store, 100.0, ts=1000, symbol="MSFT")
    assert len(engine.check(store, "AAPL", _pred(105.0, "AAPL"))) == 1
    assert len(engine.check(store, "MSFT", _pred(105.0, "MSFT"))) == 1
    _push(store, 100.0, ts=1060, symbol="AAPL")
    _push(store, 100.0, ts=1060, symbol="MSFT")
    assert engine.check(store, "AAPL", _pred(105.0, "AAPL")) == []
    assert engine.check(store, "MSFT", _pred(105.0, "MSFT")) == []


@pytest.mark.turn("t7_bug")
def test_a_sub_threshold_move_does_not_start_the_suppression_window():
    engine = AlertEngine()
    store = TickStore()
    assert engine.check(_push(store, 100.0, ts=1000), "AAPL", _pred(100.5)) == []
    assert len(engine.check(_push(store, 100.0, ts=1060), "AAPL",
                            _pred(105.0))) == 1
