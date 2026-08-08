"""Indicator maths.

Signatures are the post-t4 ones (`series_id` first); the VALUES pinned here are
the t1/t2 contract, so these carry the earliest turn that fixed the maths.
"""
import statistics

import pytest

from tickr.indicators import ema, macd, rsi, sma, volatility

LINEAR20 = [float(100 + i) for i in range(20)]
LINEAR34 = [float(100 + i) for i in range(34)]
LINEAR40 = [float(100 + i) for i in range(40)]
ZIGZAG = [10.0, 11.0, 10.5, 11.5, 11.0, 12.0, 11.5, 12.5]


# --------------------------------------------------------------------- sma
@pytest.mark.turn("t1_scaffold")
def test_sma_is_mean_of_last_window():
    assert sma("s", LINEAR20, 5) == pytest.approx(117.0, abs=1e-6)
    assert sma("s", LINEAR20, 20) == pytest.approx(109.5, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_sma_uses_the_tail_not_the_head():
    assert sma("s", [1.0, 2.0, 3.0, 100.0], 2) == pytest.approx(51.5, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_sma_window_of_one_is_the_last_value():
    assert sma("s", [1.0, 2.0, 3.0], 1) == pytest.approx(3.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_sma_window_equal_to_length():
    assert sma("s", [2.0, 4.0, 6.0], 3) == pytest.approx(4.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_sma_returns_none_on_short_input():
    assert sma("s", [1.0, 2.0], 3) is None
    assert sma("s", [], 1) is None


@pytest.mark.turn("t1_scaffold")
def test_sma_returns_none_on_non_positive_window():
    assert sma("s", LINEAR20, 0) is None
    assert sma("s", LINEAR20, -3) is None


# --------------------------------------------------------------------- ema
@pytest.mark.turn("t1_scaffold")
def test_ema_window_equal_to_length_is_the_seed_sma():
    assert ema("s", [2.0, 4.0, 6.0], 3) == pytest.approx(4.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_ema_exact_value_small_series():
    # alpha = 2/3; seed = mean([1,2]) = 1.5; then 3,4,5.
    assert ema("s", [1.0, 2.0, 3.0, 4.0, 5.0], 2) == pytest.approx(4.5, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_ema_window_of_one_is_the_last_value():
    assert ema("s", [1.0, 2.0, 3.0], 1) == pytest.approx(3.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_ema_matches_the_pinned_recurrence():
    values, window = ZIGZAG, 3
    alpha = 2 / (window + 1)
    expected = sum(values[:window]) / window
    for value in values[window:]:
        expected = value * alpha + expected * (1 - alpha)
    assert ema("s", values, window) == pytest.approx(expected, rel=1e-9)


@pytest.mark.turn("t1_scaffold")
def test_ema_returns_none_on_short_input_and_bad_window():
    assert ema("s", [1.0, 2.0], 3) is None
    assert ema("s", LINEAR20, 0) is None
    assert ema("s", LINEAR20, -1) is None


# --------------------------------------------------------------------- rsi
@pytest.mark.turn("t1_scaffold")
def test_rsi_all_gains_is_100():
    assert rsi("s", [1.0, 2.0, 3.0, 4.0, 5.0], 3) == pytest.approx(100.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_rsi_flat_series_has_zero_avg_loss_and_is_100():
    assert rsi("s", [5.0, 5.0, 5.0, 5.0, 5.0], 3) == pytest.approx(100.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_rsi_all_losses_is_zero():
    assert rsi("s", [5.0, 4.0, 3.0, 2.0, 1.0], 3) == pytest.approx(0.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_rsi_wilder_smoothing_exact_value():
    assert rsi("s", ZIGZAG, 3) == pytest.approx(76.02040816326532, rel=1e-9)


@pytest.mark.turn("t1_scaffold")
def test_rsi_needs_window_plus_one_values():
    assert rsi("s", [1.0, 2.0, 3.0], 3) is None
    assert rsi("s", [1.0, 2.0, 3.0, 4.0], 3) is not None


@pytest.mark.turn("t1_scaffold")
def test_rsi_returns_none_on_non_positive_window():
    assert rsi("s", LINEAR20, 0) is None
    assert rsi("s", LINEAR20, -2) is None


@pytest.mark.turn("t1_scaffold")
def test_rsi_default_window_is_14():
    assert rsi("s", LINEAR20) == pytest.approx(rsi("s", LINEAR20, 14), abs=1e-6)
    assert rsi("s", LINEAR20[:14]) is None
    assert rsi("s", LINEAR20[:15]) is not None


# -------------------------------------------------------------- volatility
@pytest.mark.turn("t1_scaffold")
def test_volatility_is_population_stdev():
    values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    assert volatility("s", values, 8) == pytest.approx(2.0, abs=1e-6)
    assert volatility("s", values, 8) == pytest.approx(
        statistics.pstdev(values), rel=1e-9)


@pytest.mark.turn("t1_scaffold")
def test_volatility_is_not_sample_stdev():
    values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    assert volatility("s", values, 8) != pytest.approx(
        statistics.stdev(values), abs=1e-3)


@pytest.mark.turn("t1_scaffold")
def test_volatility_exact_small_window():
    assert volatility("s", [1.0, 2.0, 3.0, 4.0], 2) == pytest.approx(0.5, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_volatility_of_linear_series():
    assert volatility("s", LINEAR20, 20) == pytest.approx(
        5.766281297335398, rel=1e-9)


@pytest.mark.turn("t1_scaffold")
def test_volatility_of_constant_series_is_zero():
    assert volatility("s", [7.0] * 5, 5) == pytest.approx(0.0, abs=1e-6)
    assert volatility("s", [1.0, 2.0, 3.0], 1) == pytest.approx(0.0, abs=1e-6)


@pytest.mark.turn("t1_scaffold")
def test_volatility_returns_none_on_short_input_and_bad_window():
    assert volatility("s", [1.0, 2.0], 3) is None
    assert volatility("s", LINEAR20, 0) is None
    assert volatility("s", LINEAR20, -5) is None


# -------------------------------------------------------------------- macd
@pytest.mark.turn("t2_macd")
def test_macd_returns_none_below_slow_plus_signal_minus_one():
    assert macd("s", [float(100 + i) for i in range(33)]) is None
    assert macd("s", []) is None


@pytest.mark.turn("t2_macd")
def test_macd_works_at_exactly_slow_plus_signal_minus_one():
    result = macd("s", LINEAR34)
    assert result is not None
    assert len(result) == 2


@pytest.mark.turn("t2_macd")
def test_macd_exact_values_on_linear_series():
    macd_line, signal_line = macd("s", LINEAR40)
    assert macd_line == pytest.approx(7.0, abs=1e-6)
    assert signal_line == pytest.approx(7.0, abs=1e-6)


@pytest.mark.turn("t2_macd")
def test_macd_line_is_the_last_prefix_difference():
    values = LINEAR40
    expected = ema("s", values, 12) - ema("s", values, 26)
    macd_line, _ = macd("s", values)
    assert macd_line == pytest.approx(expected, rel=1e-9)


@pytest.mark.turn("t2_macd")
def test_macd_signal_line_is_ema_of_the_prefix_series():
    values = ZIGZAG * 6  # 48 values, genuinely non-linear
    fast, slow, signal = 3, 6, 4
    series = [ema("s", values[:i + 1], fast) - ema("s", values[:i + 1], slow)
              for i in range(slow - 1, len(values))]
    expected_line = series[-1]
    expected_signal = ema("s", series, signal)
    macd_line, signal_line = macd("s", values, fast, slow, signal)
    assert macd_line == pytest.approx(expected_line, rel=1e-9)
    assert signal_line == pytest.approx(expected_signal, rel=1e-9)


@pytest.mark.turn("t2_macd")
def test_macd_custom_windows_exact_values():
    values = [float(i) for i in range(1, 11)]
    macd_line, signal_line = macd("s", values, 2, 3, 2)
    assert macd_line == pytest.approx(0.5, abs=1e-6)
    assert signal_line == pytest.approx(0.5, abs=1e-6)


@pytest.mark.turn("t2_macd")
def test_macd_custom_windows_length_boundary():
    values = [float(i) for i in range(1, 11)]
    # slow + signal - 1 == 4
    assert macd("s", values[:3], 2, 3, 2) is None
    assert macd("s", values[:4], 2, 3, 2) is not None


@pytest.mark.turn("t2_macd")
def test_macd_returns_none_for_non_positive_windows():
    assert macd("s", LINEAR40, 0, 26, 9) is None
    assert macd("s", LINEAR40, -1, 26, 9) is None
    assert macd("s", LINEAR40, 12, 0, 9) is None
    assert macd("s", LINEAR40, 12, -26, 9) is None
    assert macd("s", LINEAR40, 12, 26, 0) is None
    assert macd("s", LINEAR40, 12, 26, -9) is None


@pytest.mark.turn("t2_macd")
def test_macd_default_windows_are_12_26_9():
    assert macd("s", LINEAR40) == pytest.approx(
        macd("s", LINEAR40, 12, 26, 9), rel=1e-9)


@pytest.mark.turn("t2_macd")
def test_macd_returns_a_two_tuple_of_floats():
    result = macd("s", LINEAR40)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert all(isinstance(x, float) for x in result)


@pytest.mark.turn("t1_scaffold")
def test_indicators_do_not_mutate_their_input():
    values = list(LINEAR40)
    snapshot = list(values)
    sma("s", values, 5)
    ema("s", values, 5)
    rsi("s", values, 14)
    volatility("s", values, 5)
    macd("s", values)
    assert values == snapshot
