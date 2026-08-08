"""Append-only JSONL tick journal for offline replay."""
from __future__ import annotations

import json
import os

from .models import Tick


class Journal:
    def __init__(self, path: str) -> None:
        self.path = path
        self._fh = None

    def _handle(self):
        if self._fh is None:
            self._fh = open(self.path, "a", encoding="utf-8")
        return self._fh

    def record(self, tick: Tick) -> None:
        line = json.dumps({
            "symbol": tick.symbol,
            "ts": tick.ts,
            "price": tick.price,
            "volume": tick.volume,
        })
        fh = self._handle()
        fh.write(line + "\n")
        fh.flush()

    def replay(self) -> list[Tick]:
        if self._fh is not None:
            self._fh.flush()
        if not os.path.exists(self.path):
            return []
        out: list[Tick] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                d = json.loads(line)
                out.append(Tick(symbol=d["symbol"], ts=d["ts"],
                                price=d["price"], volume=d["volume"]))
        return out

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
