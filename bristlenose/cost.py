"""Cost accounting + display helpers — Slice 3 of Phase 1f.

Wraps ``bristlenose.llm.pricing.estimate_cost`` to expose
honestly-named values to the events log, the CLI, and the UI:

- ``RunCost`` — small dataclass for token totals + USD estimate.
- ``compute_run_cost`` — given model + tokens, return a ``RunCost`` with
  the price-table version stamped on. Returns ``None`` when no LLM
  calls were made (transcribe-only with local Whisper).
- ``format_cost_estimate`` — render as ``"~$0.46 (est.)"``. Never bare
  dollars; the UI/CLI must use this helper so we don't ship "We charged
  you $0.46" text by accident.

All cost values flowing through this module are estimates by
construction. We don't see the provider's actual billing (rate-limit
penalties, batch tiers, custom pricing, cache discounts).
"""

from __future__ import annotations

from dataclasses import dataclass

from bristlenose.llm.pricing import (
    CURRENCY,
    PRICE_TABLE_VERSION,
    estimate_cost,
)


@dataclass(frozen=True)
class RunCost:
    """Token totals + cost estimate for a run.

    ``input_tokens`` / ``output_tokens`` are real (the LLM provider
    returned them in ``usage``). ``cost_usd_estimate`` is best-effort.
    """

    input_tokens: int
    output_tokens: int
    cost_usd_estimate: float | None
    price_table_version: str
    currency: str = CURRENCY


def compute_run_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> RunCost | None:
    """Compute a ``RunCost`` from totals. Returns None when no LLM calls happened.

    Returns ``None`` when there were zero tokens and the price table has
    nothing to say. Returns a ``RunCost`` with ``cost_usd_estimate=None``
    when the model isn't in the price table — token counts are still
    real and worth recording.
    """
    if input_tokens == 0 and output_tokens == 0:
        return None
    estimate = estimate_cost(model, input_tokens, output_tokens)
    return RunCost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_estimate=estimate,
        price_table_version=PRICE_TABLE_VERSION,
    )


def format_cost_estimate(usd: float | None) -> str:
    """Render a cost estimate as ``"~$0.46 (est.)"``.

    Returns ``"unknown"`` for ``None`` (model not in price table).
    Renders very small estimates with extra precision so they don't
    collapse to ``~$0.00 (est.)``.
    """
    if usd is None:
        return "unknown"
    if usd < 0.01:
        return f"~${usd:.4f} (est.)"
    return f"~${usd:.2f} (est.)"
