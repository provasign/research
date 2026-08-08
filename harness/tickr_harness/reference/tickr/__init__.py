"""tickr — real-time stock tracking & prediction (reference implementation).

This package is the oracle definition of the final tickr contract:
SPEC.md v1 as amended by turns t2_macd, t3_journal, t4_series_id,
t5_rename_move, t7_bug and t8_portfolio.
"""

__all__ = [
    "models",
    "feed",
    "store",
    "indicators",
    "predict",
    "alerting",
    "pipeline",
    "journal",
    "portfolio",
    "cli",
]
