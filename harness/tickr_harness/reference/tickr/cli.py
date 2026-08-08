"""Human-readable command line entry point."""
from __future__ import annotations

import argparse

from .alerting import AlertEngine
from .feed import SyntheticFeed
from .pipeline import Pipeline
from .portfolio import portfolio_value
from .predict import Predictor
from .store import TickStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tickr")
    parser.add_argument("--symbols", default="AAPL,MSFT,GOOG")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=120)
    args = parser.parse_args(argv)

    symbols = [s for s in args.symbols.split(",") if s]
    feed = SyntheticFeed(symbols, seed=args.seed)
    store = TickStore()
    predictor = Predictor()
    engine = AlertEngine()
    for symbol in symbols:
        engine.add_threshold(symbol, 90.0, 110.0)
    pipeline = Pipeline(feed, store, predictor, engine)

    alerts = pipeline.run(args.ticks)

    print(f"tickr — {args.ticks} ticks over {len(symbols)} symbol(s), seed {args.seed}")
    for symbol in store.symbols():
        latest = store.latest(symbol)
        prediction = predictor.predict(store, symbol)
        if prediction is None:
            print(f"  {symbol}: last={latest.price:.4f} prediction=n/a")
        else:
            print(f"  {symbol}: last={latest.price:.4f} "
                  f"predicted={prediction.price:.4f} "
                  f"confidence={prediction.confidence:.3f}")
    print(f"  holdings value (1 share each): "
          f"{portfolio_value(store, {s: 1 for s in symbols}):.4f}")
    print(f"  alerts raised: {len(alerts)}")
    for alert in alerts[-10:]:
        print(f"    [{alert.kind}] {alert.ts} {alert.message}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
