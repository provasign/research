"""TickStore: per-symbol bounded history, ordering, missing-symbol behaviour."""
import pytest

from tickr.models import Tick
from tickr.store import TickStore


def _tick(symbol, ts, price, volume=1):
    return Tick(symbol=symbol, ts=ts, price=price, volume=volume)


@pytest.mark.turn("t1_scaffold")
def test_store_prices_and_ticks_are_oldest_first():
    store = TickStore()
    ticks = [_tick("AAPL", 100 + i, 10.0 + i) for i in range(4)]
    for tick in ticks:
        store.add(tick)
    assert store.ticks("AAPL") == ticks
    assert store.prices("AAPL") == pytest.approx([10.0, 11.0, 12.0, 13.0], abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_store_latest_returns_the_most_recent_tick():
    store = TickStore()
    store.add(_tick("AAPL", 1, 10.0))
    last = _tick("AAPL", 2, 11.0)
    store.add(last)
    assert store.latest("AAPL") == last


@pytest.mark.turn("t1_scaffold")
def test_store_evicts_oldest_first_at_max_ticks():
    store = TickStore(max_ticks=3)
    for i in range(5):
        store.add(_tick("AAPL", i, float(i)))
    assert len(store.ticks("AAPL")) == 3
    assert store.prices("AAPL") == pytest.approx([2.0, 3.0, 4.0], abs=1e-6)
    assert [t.ts for t in store.ticks("AAPL")] == [2, 3, 4]


@pytest.mark.turn("t1_scaffold")
def test_store_eviction_boundary_keeps_exactly_max_ticks():
    store = TickStore(max_ticks=2)
    store.add(_tick("AAPL", 1, 1.0))
    store.add(_tick("AAPL", 2, 2.0))
    assert store.prices("AAPL") == pytest.approx([1.0, 2.0], abs=1e-6)
    store.add(_tick("AAPL", 3, 3.0))
    assert store.prices("AAPL") == pytest.approx([2.0, 3.0], abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_store_eviction_limit_is_per_symbol():
    store = TickStore(max_ticks=2)
    for i in range(4):
        store.add(_tick("AAPL", i, float(i)))
        store.add(_tick("MSFT", i, float(100 + i)))
    assert store.prices("AAPL") == pytest.approx([2.0, 3.0], abs=1e-6)
    assert store.prices("MSFT") == pytest.approx([102.0, 103.0], abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_store_default_max_ticks_is_1000():
    store = TickStore()
    for i in range(1001):
        store.add(_tick("AAPL", i, float(i)))
    prices = store.prices("AAPL")
    assert len(prices) == 1000
    assert prices[0] == pytest.approx(1.0, abs=1e-6)
    assert prices[-1] == pytest.approx(1000.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_store_unknown_symbol_yields_empty_and_none_without_raising():
    store = TickStore()
    store.add(_tick("AAPL", 1, 10.0))
    assert store.prices("NOPE") == []
    assert store.ticks("NOPE") == []
    assert store.latest("NOPE") is None


@pytest.mark.turn("t1_scaffold")
def test_store_empty_store_is_inert():
    store = TickStore()
    assert store.symbols() == []
    assert store.prices("AAPL") == []
    assert store.ticks("AAPL") == []
    assert store.latest("AAPL") is None


@pytest.mark.turn("t1_scaffold")
def test_store_symbols_sorted_ascending_and_unique():
    store = TickStore()
    for symbol in ["MSFT", "aapl", "GOOG", "MSFT", "AAPL"]:
        store.add(_tick(symbol, 1, 10.0))
    assert store.symbols() == ["AAPL", "GOOG", "MSFT", "aapl"]


@pytest.mark.turn("t1_scaffold")
def test_store_prices_track_ticks():
    store = TickStore()
    for i in range(6):
        store.add(_tick("AAPL", i, 1.5 * i))
    assert store.prices("AAPL") == pytest.approx(
        [t.price for t in store.ticks("AAPL")], abs=1e-6)
