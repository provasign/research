"""Pipeline: one tick per step, alert concatenation, journalling, and the
post-t5 naming (`step`, no `run_once`, no `tickr.alerts`)."""
import importlib

import pytest

from tickr.alerting import AlertEngine
from tickr.feed import SyntheticFeed
from tickr.journal import Journal
from tickr.models import Alert, Tick
from tickr.pipeline import Pipeline
from tickr.predict import Predictor
from tickr.store import TickStore


def _parts(symbols=("AAPL",), seed=42, journal=None):
    """Build a pipeline AND hand back its collaborators.

    Tests must never reach into `pipeline.feed` / `.store` / `.alerts`: SPEC
    pins the constructor and the methods, not how the object stores what it was
    handed. An implementation that keeps them in `self._feed` is fully
    conformant, and a test assuming otherwise grades conformity to one
    particular implementation instead of to the contract.
    """
    feed = SyntheticFeed(list(symbols), seed)
    store = TickStore()
    predictor = Predictor()
    engine = AlertEngine()
    pipeline = Pipeline(feed, store, predictor, engine, journal=journal)
    return pipeline, feed, store, predictor, engine


def _build(symbols=("AAPL",), seed=42, journal=None):
    return _parts(symbols, seed, journal)[0]


@pytest.mark.turn("t1_scaffold")
def test_step_returns_tick_prediction_and_alerts():
    tick, prediction, alerts = _build().step()
    assert isinstance(tick, Tick)
    assert prediction is None  # only one tick so far
    assert alerts == []


@pytest.mark.turn("t1_scaffold")
def test_step_consumes_exactly_one_tick():
    pipeline, feed, _store, _pred, _engine = _parts()
    reference = SyntheticFeed(["AAPL"], 42).take(2)
    tick, _prediction, _alerts = pipeline.step()
    assert tick == reference[0]
    assert feed.next_tick() == reference[1]


@pytest.mark.turn("t1_scaffold")
def test_step_adds_the_tick_to_the_store():
    pipeline, _feed, store, _pred, _engine = _parts()
    tick, _prediction, _alerts = pipeline.step()
    assert store.ticks(tick.symbol) == [tick]
    assert store.latest(tick.symbol) == tick


@pytest.mark.turn("t1_scaffold")
def test_step_produces_a_prediction_once_there_is_enough_history():
    pipeline = _build()
    for _ in range(19):
        _tick, prediction, _alerts = pipeline.step()
        assert prediction is None
    _tick, prediction, _alerts = pipeline.step()
    assert prediction is not None
    assert prediction.symbol == "AAPL"


@pytest.mark.turn("t1_scaffold")
def test_run_advances_n_ticks_and_returns_alerts_in_order():
    pipeline, _feed, store, _pred, engine = _parts(symbols=("AAPL", "MSFT"))
    alerts = pipeline.run(30)
    assert all(isinstance(a, Alert) for a in alerts)
    assert alerts == engine.history()
    assert len(store.ticks("AAPL")) + len(store.ticks("MSFT")) == 30


@pytest.mark.turn("t1_scaffold")
def test_run_zero_is_a_no_op():
    pipeline, _feed, store, _pred, _engine = _parts()
    assert pipeline.run(0) == []
    assert store.symbols() == []


@pytest.mark.turn("t1_scaffold")
def test_run_concatenates_what_step_returns():
    a = _build(seed=5)
    b = _build(seed=5)
    expected = []
    for _ in range(25):
        expected.extend(a.step()[2])
    assert b.run(25) == expected


@pytest.mark.turn("t3_journal")
def test_pipeline_journals_every_consumed_tick(tmp_path):
    journal = Journal(str(tmp_path / "j.jsonl"))
    pipeline = _build(symbols=("AAPL", "MSFT"), journal=journal)
    ticks = []
    for _ in range(6):
        ticks.append(pipeline.step()[0])
    journal.close()
    assert journal.replay() == ticks


@pytest.mark.turn("t3_journal")
def test_pipeline_journal_defaults_to_none_and_changes_nothing(tmp_path):
    journal = Journal(str(tmp_path / "j.jsonl"))
    with_journal = Pipeline(SyntheticFeed(["AAPL"], 42), TickStore(),
                            Predictor(), AlertEngine(), journal=journal)
    without = Pipeline(SyntheticFeed(["AAPL"], 42), TickStore(),
                       Predictor(), AlertEngine())
    assert with_journal.run(30) == without.run(30)
    journal.close()


@pytest.mark.turn("t3_journal")
def test_pipeline_records_the_tick_before_predicting(tmp_path):
    order = []

    class WatchedJournal(Journal):
        def record(self, tick):
            order.append("record")
            return super().record(tick)

    class WatchedPredictor(Predictor):
        def predict(self, store, symbol):
            order.append("predict")
            return super().predict(store, symbol)

    journal = WatchedJournal(str(tmp_path / "j.jsonl"))
    pipeline = Pipeline(SyntheticFeed(["AAPL"], 42), TickStore(),
                        WatchedPredictor(), AlertEngine(), journal=journal)
    pipeline.step()
    journal.close()
    assert order == ["record", "predict"]


@pytest.mark.turn("t5_rename_move")
def test_pipeline_run_once_no_longer_exists():
    assert not hasattr(Pipeline, "run_once")
    assert callable(getattr(Pipeline, "step", None))


@pytest.mark.turn("t5_rename_move")
def test_pipeline_module_does_not_depend_on_tickr_alerts():
    with pytest.raises(ImportError):
        importlib.import_module("tickr.alerts")
    _build().run(3)  # still works with the moved AlertEngine
