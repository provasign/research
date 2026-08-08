"""Feed -> store -> journal -> predictor -> alerts orchestration."""
from __future__ import annotations

from .alerting import AlertEngine
from .feed import SyntheticFeed
from .journal import Journal
from .models import Alert, Prediction, Tick
from .predict import Predictor
from .store import TickStore


class Pipeline:
    def __init__(self, feed: SyntheticFeed, store: TickStore,
                 predictor: Predictor, alerts: AlertEngine,
                 journal: Journal | None = None) -> None:
        self.feed = feed
        self.store = store
        self.predictor = predictor
        self.alerts = alerts
        self.journal = journal

    def step(self) -> tuple[Tick, Prediction | None, list[Alert]]:
        tick = self.feed.next_tick()
        self.store.add(tick)
        if self.journal is not None:
            self.journal.record(tick)
        prediction = self.predictor.predict(self.store, tick.symbol)
        alerts = self.alerts.check(self.store, tick.symbol, prediction)
        return tick, prediction, alerts

    def run(self, n: int) -> list[Alert]:
        out: list[Alert] = []
        for _ in range(n):
            _tick, _prediction, alerts = self.step()
            out.extend(alerts)
        return out
