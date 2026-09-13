"""Per-model API list-price tables, kept out of runner scripts.

Claude arms report `cost_usd` directly from the `claude` CLI's own usage
estimate (see `runner_core.summarize_sonnet`), so no table is needed for
them here. Codex/GPT arms report raw token usage only, so this module
supplies the price table used to compute an API-list-price equivalent.

Adding a new model's pricing means adding an entry to `PRICING` -- no
runner code changes required.
"""
from __future__ import annotations

PRICING: dict[str, dict] = {
    "gpt-5.5": {
        "currency": "USD",
        "unit": "one_million_tokens",
        "input": 5.00,
        "cached_input": 0.50,
        "output": 30.00,
        "long_context_input_threshold": 272_000,
        "long_context_input_multiplier": 2.0,
        "long_context_output_multiplier": 1.5,
        "observed_utc": "2026-09-07",
        "source": "https://developers.openai.com/api/docs/models/gpt-5.5",
    },
}

# Backward-compatible alias for existing callers/tests.
GPT55_PRICING = PRICING["gpt-5.5"]


def pricing_for(model: str) -> dict | None:
    """Return the price table for `model`, or None if untabulated."""
    return PRICING.get(model)


def add_api_cost(rec: dict, model: str) -> None:
    """Record an API-list-price equivalent for a measured token-usage record.

    `rec` must carry `measurement_complete`, `input_tokens`,
    `cache_read_tokens`, `output_tokens`, and `usage_raw` (a list of
    per-turn usage dicts with an `input_tokens` key), as produced by
    `runner_core.summarize_codex`. No-op (leaves `cost_usd` untouched) when
    the measurement is incomplete or the model is untabulated.
    """
    table = pricing_for(model)
    if table is None or not rec.get("measurement_complete"):
        return
    input_tokens = rec["input_tokens"]
    cached_tokens = rec["cache_read_tokens"]
    output_tokens = rec["output_tokens"]
    long_context = any(
        (usage or {}).get("input_tokens", 0) > table["long_context_input_threshold"]
        for usage in rec.get("usage_raw", [])
    )
    input_multiplier = table["long_context_input_multiplier"] if long_context else 1.0
    output_multiplier = table["long_context_output_multiplier"] if long_context else 1.0
    uncached_tokens = max(0, input_tokens - cached_tokens)
    cost = (
        uncached_tokens * table["input"] * input_multiplier
        + cached_tokens * table["cached_input"] * input_multiplier
        + output_tokens * table["output"] * output_multiplier
    ) / 1_000_000
    rec.update(
        cost_usd=round(cost, 8),
        cost_basis=f"{model} API list-price equivalent; not subscription billing",
        long_context_pricing=long_context,
    )


# Backward-compatible name matching coding_suite.py's original helper.
def add_gpt55_cost(rec: dict) -> None:
    add_api_cost(rec, "gpt-5.5")
