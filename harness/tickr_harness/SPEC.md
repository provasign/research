# tickr — real-time stock tracking & prediction: API SPEC v1

This is the contract. Other code (dashboards, notifiers, backtesters) is written
against these exact module paths, names, and signatures, so they are **frozen**:
do not rename, do not reorder parameters, do not change return types unless a
later work item explicitly says to.

Hard constraints:

- **No network access.** The market feed is synthetic and deterministic.
- **Standard library only.** No numpy, pandas, requests, or any third-party
  runtime dependency. `pytest` may be used for tests.
- Python 3.11+ syntax is fine.
- The package lives in `tickr/` at the repository root, with `tickr/__init__.py`.
- Tests live in `tests/` at the repository root.
- Indicator and prediction functions **never raise on short input** — they
  return `None`.
- Floating-point results are compared with a tolerance of `1e-6`. Do not round.

---

## `tickr/models.py`

```python
@dataclass(frozen=True)
class Tick:
    symbol: str
    ts: int          # epoch seconds
    price: float
    volume: int

@dataclass(frozen=True)
class Prediction:
    symbol: str
    ts: int          # ts of the tick this prediction was made from
    horizon: int     # seconds ahead
    price: float     # predicted price
    confidence: float  # clamped to [0.0, 1.0]

@dataclass(frozen=True)
class Alert:
    symbol: str
    ts: int
    kind: str        # "threshold" or "signal"
    message: str
```

---

## `tickr/feed.py`

```python
class SyntheticFeed:
    def __init__(self, symbols: list[str], seed: int,
                 start_ts: int = 1700000000, start_price: float = 100.0) -> None: ...
    def next_tick(self) -> Tick: ...
    def take(self, n: int) -> list[Tick]: ...
```

The feed stands in for a live market socket. It must be **bit-for-bit
reproducible** — downstream backtests pin exact prices — so the generator is
pinned:

- One 32-bit LCG per feed instance. `state` starts at `seed`.
  `state = (1103515245 * state + 12345) % 2**31`; `_rand()` advances the state
  and returns the new value.
- Ticks are emitted round-robin over `symbols` in the order given, starting at
  `symbols[0]`.
- For the i-th emitted tick (i starting at 0):
  - `symbol = symbols[i % len(symbols)]`
  - `ts = start_ts + (i // len(symbols)) * 60`
  - `delta = ((_rand() % 2001) - 1000) / 10000.0`   (so delta is in [-0.1, 0.1])
  - `price = prev_price[symbol] * (1 + delta)`, where `prev_price[symbol]`
    starts at `start_price` and is then the last price emitted for that symbol.
    Do not round the price.
  - `volume = _rand() % 10000`
- **Call order matters**: within one tick, `_rand()` is called for `delta`
  first, then for `volume`.
- `take(n)` returns the next `n` ticks, in order, by advancing the feed.

---

## `tickr/store.py`

```python
class TickStore:
    def __init__(self, max_ticks: int = 1000) -> None: ...
    def add(self, tick: Tick) -> None: ...
    def prices(self, symbol: str) -> list[float]: ...   # oldest first
    def ticks(self, symbol: str) -> list[Tick]: ...     # oldest first
    def latest(self, symbol: str) -> Tick | None: ...
    def symbols(self) -> list[str]: ...                 # sorted ascending
```

- Keeps at most `max_ticks` ticks **per symbol**; when full, the oldest tick for
  that symbol is dropped.
- An unknown symbol yields `[]` from `prices`/`ticks` and `None` from `latest`.
  Never raises.

---

## `tickr/indicators.py`

Every function returns `float | None` and returns `None` — never raises — when
there is not enough data or the window is not positive.

```python
def sma(values: list[float], window: int) -> float | None: ...
def ema(values: list[float], window: int) -> float | None: ...
def rsi(values: list[float], window: int = 14) -> float | None: ...
def volatility(values: list[float], window: int) -> float | None: ...
```

- `sma` — arithmetic mean of the **last** `window` values.
  `None` if `window <= 0` or `len(values) < window`.
- `ema` — `alpha = 2 / (window + 1)`. Seed with `sma(values[:window], window)`,
  then for each value in `values[window:]`: `e = value * alpha + e * (1 - alpha)`.
  `None` if `window <= 0` or `len(values) < window`.
- `rsi` — Wilder's smoothing. `None` if `window <= 0` or
  `len(values) < window + 1`. Let `deltas[i] = values[i+1] - values[i]`.
  `avg_gain` = mean of `max(d, 0)` over the first `window` deltas;
  `avg_loss` = mean of `max(-d, 0)` over the first `window` deltas.
  Then for each remaining delta `d`:
  `avg_gain = (avg_gain * (window - 1) + max(d, 0)) / window` and
  `avg_loss = (avg_loss * (window - 1) + max(-d, 0)) / window`.
  If `avg_loss == 0` the result is `100.0`; otherwise
  `rs = avg_gain / avg_loss` and the result is `100 - 100 / (1 + rs)`.
- `volatility` — **population** standard deviation (divide by `window`, not
  `window - 1`) of the last `window` values.
  `None` if `window <= 0` or `len(values) < window`.

---

## `tickr/predict.py`

```python
class Predictor:
    def __init__(self, short_window: int = 5, long_window: int = 20,
                 horizon: int = 60) -> None: ...
    def predict(self, store: TickStore, symbol: str) -> Prediction | None: ...
```

Returns `None` when the store holds fewer than `long_window` ticks for `symbol`.
Otherwise, with `prices = store.prices(symbol)`:

```
s        = sma(prices, short_window)
l        = sma(prices, long_window)
momentum = (s - l) / l
last     = prices[-1]
price    = last * (1 + momentum)
vol      = volatility(prices, long_window)
confidence = clamp(1.0 - (vol / last) * 10, 0.0, 1.0)   # 0.0 if last == 0
```

`symbol` and `horizon` come from the arguments/config; `ts` is
`store.latest(symbol).ts`.

---

## `tickr/alerts.py`

```python
class AlertEngine:
    def __init__(self) -> None: ...
    def add_threshold(self, symbol: str, low: float, high: float) -> None: ...
    def evaluate(self, store: TickStore, symbol: str,
                 prediction: Prediction | None) -> list[Alert]: ...
    def history(self) -> list[Alert]: ...
```

`evaluate` returns the alerts raised by this one call, in this order, and also
appends each of them to the engine's history (oldest first). If the store has no
tick for `symbol`, it returns `[]`. Every alert's `ts` is the latest tick's `ts`.

1. **threshold** — only if a threshold was registered for the symbol.
   `latest.price < low` → `kind="threshold"`,
   `message = f"{symbol} below {low}"`.
   `latest.price > high` → `kind="threshold"`,
   `message = f"{symbol} above {high}"`.
   (A registration replaces any previous one for that symbol.)
2. **signal** — only if `prediction is not None`. With
   `move = (prediction.price - latest.price) / latest.price`, raise when
   `abs(move) >= 0.02`: `kind="signal"`,
   `message = f"{symbol} predicted move {move * 100:.2f}%"`.

---

## `tickr/pipeline.py`

```python
class Pipeline:
    def __init__(self, feed: SyntheticFeed, store: TickStore,
                 predictor: Predictor, alerts: AlertEngine) -> None: ...
    def run_once(self) -> tuple[Tick, Prediction | None, list[Alert]]: ...
    def run(self, n: int) -> list[Alert]: ...
```

- `run_once` — pull exactly one tick from the feed, add it to the store, run the
  predictor for that tick's symbol, evaluate the alert engine for that symbol
  with that prediction, and return the three results.
- `run(n)` — call `run_once` `n` times and return every alert raised, in order.

---

## `tickr/cli.py`

```python
def main(argv: list[str] | None = None) -> int: ...
```

Builds a feed/store/predictor/alert engine, runs the pipeline for a while,
prints a human-readable summary, and returns `0`.
