"""Hidden conformance suite for tickr.

Graded against the FINAL contract: SPEC.md v1 as amended by turns
t2_macd, t3_journal, t4_series_id, t5_rename_move, t7_bug and t8_portfolio.

The suite imports ONLY the public contract (`tickr.<module>` names and
signatures that the spec and the turn prompts pin). It never reaches into
private helpers and never assumes internal structure, so a correct but
differently-organised implementation passes.

Run it against any candidate repo by putting that repo's root on sys.path:

    cd <candidate-repo-root> && python3 -m pytest <path-to>/conformance -q

Every test carries a `turn` marker naming the EARLIEST turn whose contract it
checks, so the harness can compute a per-turn correctness curve.
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "turn(turn_id): the earliest tasks.py turn whose contract this test checks",
    )


@pytest.fixture(autouse=True)
def _isolate_indicator_traces():
    """Keep the module-level indicator trace log from leaking between tests."""
    try:
        from tickr.indicators import clear_traces
    except Exception:  # pragma: no cover - reported by the tests themselves
        yield
        return
    clear_traces()
    yield
    clear_traces()
