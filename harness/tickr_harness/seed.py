"""The `desk/` consumer codebase for the LARGE condition.

The pilot at ~350 LOC ended in a dead tie: the baseline never missed a call
site, so the scorer saturated and neither arm could win. That is a real finding
about small projects, but it cannot answer "does a code graph help", because
the question only bites once enumerating the callers is harder than eyeballing
them.

So the large condition keeps the greenfield build exactly as it was for turns
1-3, and then — right before the blast-radius refactor — merges in a package of
downstream consumers, the way a platform team's work lands in your repo while
you were busy elsewhere. The consumers are GENERATED FROM THE FROZEN SPEC, not
from either arm's code, so they are byte-identical in both arms and depend on
nothing an agent chose. Every one of them is valid against the pre-t4 contract:
they call the indicators on the old signature, call `Pipeline.run_once`, call
`AlertEngine.evaluate`, and import `tickr.alerts` — so turns 4 and 5 must find
and update all of them.

Nothing here is random. Same inputs, same bytes, every run.
"""
from __future__ import annotations

from pathlib import Path

SYMBOLS = ["AAPL", "MSFT", "GOOG", "AMZN", "TSLA", "NVDA", "META", "NFLX",
           "AMD", "INTC", "ORCL", "CRM"]

# (family, count) — 60 modules total.
FAMILIES = [("strategies", 18), ("backtests", 14), ("dashboards", 14),
            ("notifiers", 8), ("reports", 6)]

_HEADER = '"""Generated consumer module — {family}/{name}."""\n'


def _strategy(i: int, sym: str) -> str:
    return f'''
from tickr.indicators import sma, ema, rsi, volatility, macd
from tickr.store import TickStore


SYMBOL = "{sym}"
SHORT_WINDOW = {3 + i % 7}
LONG_WINDOW = {12 + i % 11}


def signal_strength(store: TickStore) -> float:
    prices = store.prices(SYMBOL)
    fast = sma(prices, SHORT_WINDOW)
    slow = sma(prices, LONG_WINDOW)
    if fast is None or slow is None:
        return 0.0
    return fast - slow


def trend_score(store: TickStore) -> float:
    prices = store.prices(SYMBOL)
    smoothed = ema(prices, LONG_WINDOW)
    strength = rsi(prices, {9 + i % 6})
    if smoothed is None or strength is None:
        return 0.0
    return smoothed * (strength / 100.0)


def risk_adjusted(store: TickStore) -> float:
    prices = store.prices(SYMBOL)
    spread = volatility(prices, LONG_WINDOW)
    base = signal_strength(store)
    if spread is None or spread == 0:
        return base
    return base / spread


def convergence(store: TickStore) -> float:
    prices = store.prices(SYMBOL)
    pair = macd(prices)
    if pair is None:
        return 0.0
    line, signal = pair
    return line - signal
'''


def _backtest(i: int, sym: str) -> str:
    return f'''
from tickr.indicators import sma, volatility, rsi
from tickr.predict import Predictor
from tickr.store import TickStore


SYMBOL = "{sym}"
WINDOW = {10 + i % 9}


def replay_score(store: TickStore, predictor: Predictor) -> float:
    prediction = predictor.predict(store, SYMBOL)
    if prediction is None:
        return 0.0
    prices = store.prices(SYMBOL)
    baseline = sma(prices, WINDOW)
    if baseline is None:
        return 0.0
    return prediction.price - baseline


def drawdown(store: TickStore) -> float:
    prices = store.prices(SYMBOL)
    spread = volatility(prices, WINDOW)
    return 0.0 if spread is None else spread * {1 + i % 4}


def momentum_check(store: TickStore) -> bool:
    prices = store.prices(SYMBOL)
    strength = rsi(prices, WINDOW)
    return strength is not None and strength > {40 + i % 20}
'''


def _dashboard(i: int, sym: str) -> str:
    return f'''
from tickr.alerts import AlertEngine
from tickr.indicators import sma, ema
from tickr.pipeline import Pipeline
from tickr.store import TickStore


SYMBOL = "{sym}"
WINDOW = {5 + i % 8}


def panel_rows(pipeline: Pipeline, rows: int = {3 + i % 5}) -> list[tuple]:
    out = []
    for _ in range(rows):
        tick, prediction, alerts = pipeline.run_once()
        out.append((tick.symbol, tick.price, prediction, len(alerts)))
    return out


def headline(store: TickStore) -> float:
    prices = store.prices(SYMBOL)
    value = sma(prices, WINDOW)
    return 0.0 if value is None else value


def sparkline(store: TickStore) -> float:
    prices = store.prices(SYMBOL)
    value = ema(prices, WINDOW)
    return 0.0 if value is None else value


def live_alerts(engine: AlertEngine, store: TickStore) -> list:
    return engine.evaluate(store, SYMBOL, None)
'''


def _notifier(i: int, sym: str) -> str:
    return f'''
from tickr.alerts import AlertEngine
from tickr.predict import Predictor
from tickr.store import TickStore
from tickr.indicators import volatility


SYMBOL = "{sym}"
WINDOW = {8 + i % 6}


def push(engine: AlertEngine, store: TickStore, predictor: Predictor) -> int:
    prediction = predictor.predict(store, SYMBOL)
    raised = engine.evaluate(store, SYMBOL, prediction)
    return len(raised)


def quiet_hours(store: TickStore) -> bool:
    prices = store.prices(SYMBOL)
    spread = volatility(prices, WINDOW)
    return spread is not None and spread < {1 + i % 3}


def digest(engine: AlertEngine) -> int:
    return len(engine.history())
'''


def _report(i: int, sym: str) -> str:
    return f'''
from tickr.alerts import AlertEngine
from tickr.indicators import sma, rsi, macd
from tickr.pipeline import Pipeline
from tickr.store import TickStore


SYMBOL = "{sym}"
WINDOW = {14 + i % 7}


def daily(store: TickStore) -> dict:
    prices = store.prices(SYMBOL)
    return {{
        "mean": sma(prices, WINDOW),
        "strength": rsi(prices, WINDOW),
        "convergence": macd(prices),
    }}


def session(pipeline: Pipeline, steps: int = {4 + i % 4}) -> int:
    seen = 0
    for _ in range(steps):
        pipeline.run_once()
        seen += 1
    return seen


def audit(engine: AlertEngine, store: TickStore) -> int:
    engine.evaluate(store, SYMBOL, None)
    return len(engine.history())
'''


BUILDERS = {"strategies": _strategy, "backtests": _backtest,
            "dashboards": _dashboard, "notifiers": _notifier,
            "reports": _report}


PKG = "desk"


def _assert_no_stdlib_shadow() -> None:
    """The seeded package must not shadow a stdlib module.

    This bit once: the package was called `platform/`, and because the repo root
    goes on sys.path, `import platform` resolved to the seeded package instead of
    the standard library. That breaks pytest itself — every test run in the large
    condition, the agent's included — and it fails as a truncated JUnit file
    rather than anything that names the real cause. Guard it permanently.
    """
    import importlib.util
    names = [PKG] + [f for f, _ in FAMILIES]
    clash = [n for n in names if importlib.util.find_spec(n) is not None]
    if clash:
        raise RuntimeError(
            f"seeded package name(s) shadow importable modules: {clash}. "
            "Rename them — the repo root is on sys.path for every test run.")


def seed(repo: Path) -> dict:
    """Materialise the consumer package into `repo`. Returns what was written."""
    _assert_no_stdlib_shadow()
    root = repo / PKG
    root.mkdir(exist_ok=True)
    (root / "__init__.py").write_text('"""Downstream consumers of the tickr API (trading desk)."""\n')
    files, n = [], 0
    for family, count in FAMILIES:
        d = root / family
        d.mkdir(exist_ok=True)
        (d / "__init__.py").write_text("")
        for i in range(count):
            sym = SYMBOLS[(i + n) % len(SYMBOLS)]
            name = f"{family[:-1] if family.endswith('s') else family}_{i:02d}.py"
            body = _HEADER.format(family=family, name=name) + BUILDERS[family](i, sym)
            (d / name).write_text(body)
            files.append(f"desk/{family}/{name}")
        n += count
    return {"files": files, "count": len(files),
            "loc": sum(len((repo / f).read_text().splitlines()) for f in files)}


# What turn 4 is told. A colleague would know the merge happened; they would NOT
# be handed the list of affected lines — finding those is the work being measured.
MERGE_NOTE = """

Heads-up before you start: while you were on the last work item, the platform
team merged their `desk/` package into this repository. It is a set of
downstream consumers — strategies, backtests, dashboards, notifiers and reports
— written against our public API. It is part of this repository now, so it is
part of "every call site"."""


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(seed(Path(sys.argv[1])), indent=2)[:2000])
