"""SyntheticFeed: bit-for-bit determinism, round-robin, ts stepping, take()."""
import pytest

from tickr.feed import SyntheticFeed
from tickr.models import Tick

M = 2 ** 31


def _lcg(seed, n):
    """The pinned generator, transcribed from the spec, for cross-checking."""
    state = seed
    out = []
    for _ in range(n):
        state = (1103515245 * state + 12345) % M
        out.append(state)
    return out


@pytest.mark.turn("t1_scaffold")
def test_feed_first_tick_exact_values():
    tick = SyntheticFeed(["AAPL"], 42).next_tick()
    assert isinstance(tick, Tick)
    assert tick.symbol == "AAPL"
    assert tick.ts == 1700000000
    assert tick.price == pytest.approx(100.92, abs=1e-6)
    assert tick.volume == 2264


@pytest.mark.turn("t1_scaffold")
def test_feed_first_five_ticks_exact_single_symbol():
    ticks = SyntheticFeed(["AAPL"], 42).take(5)
    expected_prices = [
        100.92000000000002,
        97.53918000000002,
        106.46401497000001,
        99.959063655333,
        92.89195785490095,
    ]
    expected_volumes = [2264, 4806, 6532, 1266, 4752]
    assert [t.price for t in ticks] == pytest.approx(expected_prices, abs=1e-6)
    assert [t.volume for t in ticks] == expected_volumes


@pytest.mark.turn("t1_scaffold")
def test_feed_ts_steps_by_60_for_single_symbol():
    ticks = SyntheticFeed(["AAPL"], 42).take(4)
    assert [t.ts for t in ticks] == [1700000000, 1700000060, 1700000120, 1700000180]


@pytest.mark.turn("t1_scaffold")
def test_feed_round_robin_symbol_order_and_shared_ts():
    ticks = SyntheticFeed(["AAPL", "MSFT", "GOOG"], 3).take(7)
    assert [t.symbol for t in ticks] == [
        "AAPL", "MSFT", "GOOG", "AAPL", "MSFT", "GOOG", "AAPL"]
    assert [t.ts for t in ticks] == [
        1700000000, 1700000000, 1700000000,
        1700000060, 1700000060, 1700000060,
        1700000120,
    ]


@pytest.mark.turn("t1_scaffold")
def test_feed_multi_symbol_exact_values():
    ticks = SyntheticFeed(["AAPL", "MSFT"], 7).take(6)
    assert [t.symbol for t in ticks] == [
        "AAPL", "MSFT", "AAPL", "MSFT", "AAPL", "MSFT"]
    assert [t.price for t in ticks] == pytest.approx([
        103.52999999999999,
        109.84,
        105.38318699999999,
        99.6798,
        108.24960968639998,
        91.71538398,
    ], abs=1e-6)
    assert [t.volume for t in ticks] == [6333, 1571, 2521, 9087, 7717, 5227]


@pytest.mark.turn("t1_scaffold")
def test_feed_start_ts_and_start_price_are_honoured():
    ticks = SyntheticFeed(["A", "B", "C"], 1, 0, 50.0).take(7)
    assert [t.symbol for t in ticks] == ["A", "B", "C", "A", "B", "C", "A"]
    assert [t.ts for t in ticks] == [0, 0, 0, 60, 60, 60, 120]
    assert [t.price for t in ticks] == pytest.approx([
        45.51, 49.19, 47.375, 42.388014, 48.663667, 48.64465, 39.6158378844,
    ], abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_feed_rand_call_order_is_delta_then_volume():
    r1, r2 = _lcg(42, 2)
    correct_price = 100.0 * (1 + ((r1 % 2001) - 1000) / 10000.0)
    swapped_price = 100.0 * (1 + ((r2 % 2001) - 1000) / 10000.0)
    # Guard: the two orderings must actually be distinguishable here.
    assert correct_price != pytest.approx(swapped_price, abs=1e-6)
    assert r1 % 10000 != r2 % 10000

    tick = SyntheticFeed(["AAPL"], 42).next_tick()
    assert tick.price == pytest.approx(correct_price, abs=1e-6)
    assert tick.volume == r2 % 10000


@pytest.mark.turn("t1_scaffold")
def test_feed_previous_price_is_tracked_per_symbol():
    ticks = SyntheticFeed(["AAPL", "MSFT"], 7).take(4)
    r = _lcg(7, 8)
    aapl_second_delta = ((r[4] % 2001) - 1000) / 10000.0
    assert ticks[2].price == pytest.approx(
        ticks[0].price * (1 + aapl_second_delta), abs=1e-6)
    msft_second_delta = ((r[6] % 2001) - 1000) / 10000.0
    assert ticks[3].price == pytest.approx(
        ticks[1].price * (1 + msft_second_delta), abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_feed_take_advances_and_concatenates():
    a = SyntheticFeed(["AAPL", "MSFT"], 11)
    b = SyntheticFeed(["AAPL", "MSFT"], 11)
    first = a.take(3)
    second = a.take(3)
    assert first + second == b.take(6)
    assert a.take(0) == []


@pytest.mark.turn("t1_scaffold")
def test_feed_take_equals_repeated_next_tick():
    a = SyntheticFeed(["AAPL"], 99)
    b = SyntheticFeed(["AAPL"], 99)
    assert a.take(5) == [b.next_tick() for _ in range(5)]


@pytest.mark.turn("t1_scaffold")
def test_feed_same_seed_reproducible_different_seed_differs():
    same_a = SyntheticFeed(["AAPL"], 5).take(10)
    same_b = SyntheticFeed(["AAPL"], 5).take(10)
    other = SyntheticFeed(["AAPL"], 6).take(10)
    assert [t.price for t in same_a] == [t.price for t in same_b]
    assert [t.price for t in same_a] != [t.price for t in other]


@pytest.mark.turn("t1_scaffold")
def test_feed_delta_and_volume_stay_in_range():
    ticks = SyntheticFeed(["AAPL", "MSFT"], 1234).take(200)
    prev = {"AAPL": 100.0, "MSFT": 100.0}
    for tick in ticks:
        ratio = tick.price / prev[tick.symbol]
        assert 0.9 - 1e-9 <= ratio <= 1.1 + 1e-9
        assert 0 <= tick.volume < 10000
        assert isinstance(tick.volume, int)
        prev[tick.symbol] = tick.price


@pytest.mark.turn("t1_scaffold")
def test_feed_price_is_not_rounded():
    ticks = SyntheticFeed(["A", "B", "C"], 1, 0, 50.0).take(7)
    assert ticks[6].price == pytest.approx(39.6158378844, abs=1e-9)
    assert ticks[6].price != pytest.approx(round(39.6158378844, 2), abs=1e-9)
