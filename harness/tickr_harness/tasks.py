"""The tickr development session: 9 turns of realistic human+agent work.

One trial = one continuous agent session (claude -p --session-id / --resume)
walking these 9 turns in order, in a fresh git repo. Both arms get byte-identical
prompts; the ONLY difference between arms is which context tool is available
(see arms.py). Nothing here mentions Prism, grep, or any tool by name.

The turns are shaped like a real sprint: scaffold, two features, two refactors
with genuine blast radius, a test-authoring turn, a behavioural bug report, a
feature built on top of the refactored code, and a cleanup pass. Every turn that
changes the public contract states the new contract precisely, because the
hidden conformance suite grades against it and a vague spec would measure
prompt-guessing instead of engineering.
"""
from __future__ import annotations

from pathlib import Path

SPEC = (Path(__file__).parent / "SPEC.md").read_text()

# Appended to every turn. Keeps the loop honest and terminating without hinting
# at any particular way of finding code.
TAIL = """

Work in this repository. When you are done with this work item:
  1. make sure every module still imports cleanly,
  2. run the test suite and make it pass,
  3. stop.

Do not create git commits. Do not add third-party runtime dependencies."""

TURNS = [
    # ---------------------------------------------------------------- T1
    dict(
        id="t1_scaffold",
        kind="scaffold",
        prompt=f"""We are starting `tickr`, a real-time stock tracking and prediction service.
Build the first version in this empty repository, following this specification exactly.
Other teams are already coding against these names and signatures.

{SPEC}

Also write `tests/` covering the feed's determinism, the store's eviction, each
indicator, the predictor, the alert engine, and the pipeline. Then run them.""",
    ),
    # ---------------------------------------------------------------- T2
    dict(
        id="t2_macd",
        kind="feature",
        prompt="""Work item: traders want MACD, and they want the predictor to use it.

1. Add to `tickr/indicators.py`:

```python
def macd(values: list[float], fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[float, float] | None: ...
```

   It returns `(macd_line, signal_line)`, or `None` when there is not enough
   data. Pinned semantics — a backtester depends on the exact numbers:

   - Return `None` if any of `fast`, `slow`, `signal` is <= 0, or if
     `len(values) < slow + signal - 1`.
   - Build the MACD-line series over every prefix long enough to have both EMAs:
     `macd_series = [ema(values[:i+1], fast) - ema(values[:i+1], slow)
                     for i in range(slow - 1, len(values))]`
   - `macd_line = macd_series[-1]`
   - `signal_line = ema(macd_series, signal)`; if that is `None`, return `None`.
   - Return `(macd_line, signal_line)`.

2. `Predictor.__init__` gains a keyword parameter `use_macd: bool = True`,
   appended after `horizon`. When `use_macd` is true and `macd(prices)` (default
   fast/slow/signal) returns a result, the predicted price becomes

       price = last * (1 + momentum) + (macd_line - signal_line) * 0.5

   Everything else about `Predictor.predict` is unchanged. When `use_macd` is
   false, or MACD returns `None`, the predicted price is exactly what it was.

3. Cover the new behaviour with tests.""",
    ),
    # ---------------------------------------------------------------- T3
    dict(
        id="t3_journal",
        kind="feature",
        prompt="""Work item: we need to replay a trading session offline, so the pipeline must
journal every tick it consumes.

1. New module `tickr/journal.py`:

```python
class Journal:
    def __init__(self, path: str) -> None: ...
    def record(self, tick: Tick) -> None: ...
    def replay(self) -> list[Tick]: ...
    def close(self) -> None: ...
```

   - `record` appends exactly one line to the file at `path`, containing
     `json.dumps({"symbol": ..., "ts": ..., "price": ..., "volume": ...})`
     with those four keys in that order. The file is created if absent.
   - `replay` reads the file back and returns the ticks in the order recorded.
     A missing file yields `[]`. Blank lines are skipped.
   - `close` releases any handle the journal holds. It must be safe to call
     `close` more than once, and `replay` must work after `close`.

2. `Pipeline.__init__` gains a final keyword parameter `journal: Journal | None
   = None`. When it is set, each tick the pipeline consumes is recorded to the
   journal, before the prediction is computed. When it is `None` the pipeline
   behaves exactly as before.

3. Cover the new behaviour with tests, including a round-trip through a
   temporary file.""",
    ),
    # ---------------------------------------------------------------- T4
    dict(
        id="t4_series_id",
        kind="refactor",
        prompt="""Work item: indicator computations are impossible to trace in production. When a
prediction looks wrong we cannot tell which symbol's series produced which
indicator value.

Every indicator function in `tickr/indicators.py` gains a **new required first
parameter** `series_id: str`, ahead of all existing parameters:

```python
def sma(series_id: str, values: list[float], window: int) -> float | None: ...
def ema(series_id: str, values: list[float], window: int) -> float | None: ...
def rsi(series_id: str, values: list[float], window: int = 14) -> float | None: ...
def volatility(series_id: str, values: list[float], window: int) -> float | None: ...
def macd(series_id: str, values: list[float], fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[float, float] | None: ...
```

The computation itself does not change. What changes is that each call is now
traced. Add to the same module:

```python
def traces() -> list[str]: ...        # every series_id seen, in call order
def clear_traces() -> None: ...
```

- Every indicator call appends its `series_id` to the trace log, including calls
  that return `None`, and including calls made internally by other indicators
  (`macd` calls `ema`, so it contributes several entries).
- `traces()` returns a copy — mutating the returned list must not affect the log.

Every caller of an indicator must now pass a `series_id`. Where the caller knows
the symbol it is working on, pass that symbol. `Predictor.predict` passes the
`symbol` it was asked about; `macd`'s internal `ema` calls pass through the
`series_id` they were given.

Update every call site in the repository — production code and tests alike. No
caller may be left on the old signature.""",
    ),
    # ---------------------------------------------------------------- T5
    dict(
        id="t5_rename_move",
        kind="refactor",
        prompt="""Work item: naming cleanup ahead of the public 1.0, agreed at the API review.

1. `Pipeline.run_once` is renamed to `Pipeline.step`. Same behaviour, same
   return value. `run_once` must no longer exist — do not leave an alias.

2. `AlertEngine.evaluate` is renamed to `AlertEngine.check`. Same behaviour,
   same return value. `evaluate` must no longer exist — do not leave an alias.

3. The `AlertEngine` class moves from `tickr/alerts.py` to a new module
   `tickr/alerting.py`. After this change `tickr/alerts.py` must be **deleted**
   from the repository — not left as a re-export shim. `from tickr.alerts import
   AlertEngine` must fail with an ImportError, and `from tickr.alerting import
   AlertEngine` must work.

Update every reference in the repository — production code, the CLI, and tests.
Nothing may still refer to `run_once`, to `evaluate`, or to `tickr.alerts`.""",
    ),
    # ---------------------------------------------------------------- T6
    dict(
        id="t6_tests",
        kind="tests",
        prompt="""Work item: the test suite has grown unevenly and we do not know what it misses.

Find the parts of the `tickr` package that the current tests do not exercise —
whole functions with no test, and untested branches of functions that do have
one (short-input `None` paths, eviction boundaries, the empty-symbol paths, the
journal's missing-file and double-close paths, the alert engine's
no-threshold-registered path, the predictor's not-enough-data path, and the
`use_macd=False` path).

Then write the tests that close those gaps, in `tests/`. Keep the existing tests.
Finish by reporting, in your final message, which functions had no coverage
before this work item and which of them you have now covered.""",
    ),
    # ---------------------------------------------------------------- T7
    dict(
        id="t7_bug",
        kind="bugfix",
        prompt="""Bug report from the trading desk — P1, alert spam.

> When a symbol's price sits outside its threshold band, we get a `threshold`
> alert on *every single tick* until it comes back. During this morning's dip
> one symbol produced 40 identical alerts in two minutes. Same story for
> `signal` alerts: a sustained predicted move re-fires on every tick.

Fix the alert engine so alerts are edge-triggered, not level-triggered. The
agreed semantics:

- **threshold**: the engine tracks, per symbol, whether the price is currently
  outside the band. A threshold alert fires only on the transition from inside
  to outside. While the price stays outside, no further threshold alert fires
  for that symbol — even if it crosses from below-low to above-high. Once the
  price is back inside `[low, high]` (inclusive), the symbol is armed again and
  the next excursion fires.
- **signal**: a signal alert for a symbol is suppressed if a signal alert was
  already raised for that symbol within the last 300 seconds, compared on the
  tick `ts` values (`latest.ts - last_signal_ts < 300` suppresses). At exactly
  300 seconds it fires.
- Registering a threshold for a symbol (again) resets that symbol to armed.
- Suppressed alerts are not returned and are not appended to the history.

Everything else about the alert engine is unchanged. Add tests that pin the
edge-triggering, the re-arm, and the 300-second signal window.""",
    ),
    # ---------------------------------------------------------------- T8
    dict(
        id="t8_portfolio",
        kind="feature",
        prompt="""Work item: customers hold baskets, not single symbols. Add portfolio-level
tracking on top of what we have.

New module `tickr/portfolio.py`:

```python
def portfolio_forecast(store: TickStore, predictor: Predictor,
                       symbols: list[str]) -> dict[str, Prediction | None]: ...
def portfolio_value(store: TickStore, holdings: dict[str, int]) -> float: ...
def portfolio_expected_value(store: TickStore, predictor: Predictor,
                             holdings: dict[str, int]) -> float: ...
```

- `portfolio_forecast` — maps each symbol in `symbols`, in the order given, to
  `predictor.predict(store, symbol)`. A symbol the predictor cannot forecast
  maps to `None`. A symbol repeated in the input appears once in the result.
- `portfolio_value` — the sum over `holdings` of the symbol's latest price times
  its quantity. A symbol with no ticks contributes `0.0`. An empty holdings dict
  gives `0.0`.
- `portfolio_expected_value` — the same sum, but using each symbol's forecast
  price instead of its latest price. Where the forecast is `None`, fall back to
  the symbol's latest price. A symbol with no ticks contributes `0.0`.

Cover it with tests.""",
    ),
    # ---------------------------------------------------------------- T9
    dict(
        id="t9_cleanup",
        kind="cleanup",
        prompt="""Work item: pre-1.0 cleanup pass.

Go through the `tickr` package and remove code that nothing reaches any more —
functions, classes, modules, and imports left behind by the renames, the module
move, and the refactors of the last few work items. Do not remove anything that
is part of the specified public API, and do not remove anything the tests or the
CLI still use.

Then make sure the whole thing is healthy: every module imports cleanly, the CLI
runs, and the full test suite passes. Report what you removed and why it was
unreachable.""",
    ),
]

TURN_IDS = [t["id"] for t in TURNS]
