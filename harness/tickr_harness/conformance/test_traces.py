"""t4_series_id: the required `series_id` first parameter and the trace log.

The spec pins THAT every indicator call is traced under the series_id it was
given, including calls that return None and calls made internally by other
indicators. It does NOT pin how many internal calls an implementation makes, so
exact counts/orderings are only asserted for a direct call to an indicator whose
specified formula involves no other indicator (sma, rsi). Everywhere else we
assert the pinned properties: non-empty, and every entry equals the series_id.
"""
import pytest

from tickr.indicators import (clear_traces, ema, macd, rsi, sma, traces,
                              volatility)

LINEAR20 = [float(100 + i) for i in range(20)]
LINEAR40 = [float(100 + i) for i in range(40)]


@pytest.mark.turn("t4_series_id")
def test_series_id_is_the_required_first_positional_parameter():
    clear_traces()
    assert sma("AAPL", [1.0, 2.0, 3.0], 3) == pytest.approx(2.0, abs=1e-6)
    assert ema("AAPL", [1.0, 2.0, 3.0], 3) == pytest.approx(2.0, abs=1e-6)
    assert rsi("AAPL", LINEAR20, 14) is not None
    assert volatility("AAPL", [1.0, 2.0, 3.0], 3) is not None
    assert macd("AAPL", LINEAR40) is not None


@pytest.mark.turn("t4_series_id")
def test_indicators_reject_the_old_pre_series_id_signature():
    with pytest.raises(TypeError):
        sma([1.0, 2.0, 3.0], 3)
    with pytest.raises(TypeError):
        volatility([1.0, 2.0, 3.0], 3)


@pytest.mark.turn("t4_series_id")
def test_direct_sma_call_appends_exactly_one_entry():
    clear_traces()
    sma("AAPL", [1.0, 2.0, 3.0], 2)
    assert traces() == ["AAPL"]


@pytest.mark.turn("t4_series_id")
def test_direct_rsi_call_appends_exactly_one_entry():
    clear_traces()
    rsi("MSFT", LINEAR20, 14)
    assert traces() == ["MSFT"]


@pytest.mark.turn("t4_series_id")
def test_none_returning_calls_are_still_traced():
    clear_traces()
    assert sma("AAPL", [1.0], 5) is None
    assert traces() == ["AAPL"]

    clear_traces()
    assert rsi("AAPL", [1.0], 14) is None
    assert traces() == ["AAPL"]

    clear_traces()
    assert ema("AAPL", [1.0], 5) is None
    assert traces() and set(traces()) == {"AAPL"}

    clear_traces()
    assert volatility("AAPL", [1.0], 5) is None
    assert traces() and set(traces()) == {"AAPL"}

    clear_traces()
    assert macd("AAPL", [1.0, 2.0]) is None
    assert traces() and set(traces()) == {"AAPL"}


@pytest.mark.turn("t4_series_id")
def test_trace_order_follows_call_order():
    clear_traces()
    sma("A", [1.0, 2.0], 2)
    sma("B", [1.0, 2.0], 2)
    sma("C", [1.0, 2.0], 2)
    sma("A", [1.0, 2.0], 2)
    assert traces() == ["A", "B", "C", "A"]


@pytest.mark.turn("t4_series_id")
def test_macd_contributes_internal_ema_entries_under_the_same_series_id():
    clear_traces()
    assert macd("GOOG", LINEAR40) is not None
    log = traces()
    # macd's internal ema calls must be traced, so the log is longer than the
    # single entry a leaf call would produce. The exact count is not pinned.
    assert len(log) > 1
    assert set(log) == {"GOOG"}


@pytest.mark.turn("t4_series_id")
def test_macd_trace_volume_grows_with_the_prefix_series():
    # The spec builds macd_series with an ema() call per prefix, so a longer
    # input means more traced internal calls. The exact counts are not pinned;
    # the fact that they grow is.
    long_series = [float(100 + i) for i in range(60)]
    clear_traces()
    assert macd("AAPL", LINEAR40) is not None
    short_log = len(traces())
    clear_traces()
    assert macd("AAPL", long_series) is not None
    long_log = len(traces())
    assert long_log > short_log


@pytest.mark.turn("t4_series_id")
def test_traces_never_leaks_other_or_empty_series_ids():
    clear_traces()
    macd("AAPL", LINEAR40)
    ema("AAPL", LINEAR20, 5)
    log = traces()
    assert log
    assert all(entry == "AAPL" for entry in log)


@pytest.mark.turn("t4_series_id")
def test_traces_returns_a_copy():
    clear_traces()
    sma("AAPL", [1.0, 2.0], 2)
    first = traces()
    first.append("TAMPERED")
    first.clear()
    assert traces() == ["AAPL"]


@pytest.mark.turn("t4_series_id")
def test_traces_returns_a_distinct_list_each_call():
    clear_traces()
    sma("AAPL", [1.0, 2.0], 2)
    assert traces() is not traces()


@pytest.mark.turn("t4_series_id")
def test_clear_traces_empties_the_log():
    clear_traces()
    sma("AAPL", [1.0, 2.0], 2)
    macd("AAPL", LINEAR40)
    assert traces()
    clear_traces()
    assert traces() == []
    clear_traces()
    assert traces() == []


@pytest.mark.turn("t4_series_id")
def test_predictor_traces_under_the_symbol_it_was_asked_about():
    from tickr.models import Tick
    from tickr.predict import Predictor
    from tickr.store import TickStore

    store = TickStore()
    for i, price in enumerate(LINEAR40):
        store.add(Tick(symbol="TSLA", ts=1000 + 60 * i, price=price, volume=1))
    clear_traces()
    assert Predictor().predict(store, "TSLA") is not None
    log = traces()
    assert log
    assert set(log) == {"TSLA"}
