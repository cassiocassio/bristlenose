"""LLM pricing estimates for token usage reporting.

Prices are approximate and may be outdated — users see a verification link
in the CLI output so they can check current rates. The estimate is honest
by construction: see ``cost_usd_estimate`` in ``bristlenose/events.py``
and the design-pipeline-resilience.md cost discussion.

Pre-run forecast (``estimate_pipeline_cost``) is data-driven (Slice C):
it reads the project's own ``llm-calls.jsonl`` for cohort medians, falls
back to shipped baselines in ``cohort-baselines.json``, and returns
``None`` when neither matches. Set ``BRISTLENOSE_LLM_FORECAST=legacy`` to
short-circuit to the pre-Slice-C constant.
"""

from __future__ import annotations

import json
import os
import statistics
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from .cohort_normalise import normalise_model
from .telemetry import iter_rows

# Bump when any rate changes — stamped onto every cost-bearing event so a
# future reader can recompute against a newer table.
PRICE_TABLE_VERSION = "2026-04-25"
CURRENCY = "USD"

# Pricing per million tokens: (input_rate_usd, output_rate_usd).
PRICING: dict[str, tuple[float, float]] = {
    # Anthropic (Claude)
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-3-5-20241022": (0.80, 4.0),
    # OpenAI (ChatGPT)
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    # Google (Gemini)
    "gemini-2.5-flash": (0.15, 3.50),
    "gemini-2.5-pro": (1.25, 10.0),
}

# Mirrors PRICING — provider lookup for cohort key resolution.
_MODEL_PROVIDER: dict[str, str] = {
    "claude-sonnet-4-20250514": "anthropic",
    "claude-haiku-3-5-20241022": "anthropic",
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "gemini-2.5-flash": "google",
    "gemini-2.5-pro": "google",
}

PRICING_URLS: dict[str, str] = {
    "anthropic": "https://docs.anthropic.com/en/docs/about-claude/models",
    "openai": "https://platform.openai.com/docs/pricing",
    "azure": "https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/",
    "google": "https://ai.google.dev/gemini-api/docs/pricing",
    # Local provider has no pricing — models are free
}

# Pre-Slice-C hardcoded constant. Retained as kill switch behind
# ``BRISTLENOSE_LLM_FORECAST=legacy``. Remove in Phase 2.
_LEGACY_TOKENS_PER_SESSION: tuple[int, int] = (17_000, 10_000)

_BASELINES_PATH = Path(__file__).parent / "cohort-baselines.json"

# Minimum sample size before a local-cohort cell is trusted over the
# shipped baseline. Three is enough to compute a non-degenerate median
# while still being conservative.
_LOCAL_N_THRESHOLD = 3


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int,
) -> float | None:
    """Return estimated cost in USD, or None if model not in pricing table."""
    if model not in PRICING:
        return None
    inp_rate, out_rate = PRICING[model]
    return (input_tokens * inp_rate + output_tokens * out_rate) / 1_000_000


@lru_cache(maxsize=1)
def _load_baselines() -> list[dict[str, Any]]:
    """Load shipped cohort baselines. Cached for the process lifetime."""
    try:
        raw = _BASELINES_PATH.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    cohorts = data.get("cohorts", [])
    return cohorts if isinstance(cohorts, list) else []


def _baseline_lookup(family: str, major: str) -> list[dict[str, Any]]:
    """Return baseline rows for the (family, major) cohort key."""
    return [
        row for row in _load_baselines()
        if row.get("model_family") == family and row.get("model_major") == major
    ]


def _scan_local_jsonl(
    run_dir: Path, family: str, major: str,
) -> dict[str, dict[str, Any]]:
    """Aggregate local JSONL rows into per-stage cohort buckets.

    Returns a dict keyed by ``stage_id`` containing:
      - ``input_tokens``: list[int] of observed values
      - ``output_tokens``: list[int]
      - ``per_session``: bool — True if any row had a non-null session_id

    Only includes pipeline-stage rows (``stage.startswith("s")``) — excludes
    serve-mode autocode rows that would inflate the next pre-run estimate.
    Only includes rows with usage_source == "reported" (skip rows where the
    provider didn't return token counts).
    """
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"input_tokens": [], "output_tokens": [], "per_session": False},
    )
    for row in iter_rows(run_dir):
        if row.get("model_family") != family or row.get("model_major") != major:
            continue
        stage = row.get("stage")
        # Accept pipeline-stage rows only (e.g. "s05b_identify_speakers",
        # "s09_quote_extraction"); reject serve-mode rows like
        # "serve_autocode" which would inflate the next pre-run estimate.
        if not isinstance(stage, str) or len(stage) < 2 or stage[0] != "s" \
                or not stage[1].isdigit():
            continue
        if row.get("usage_source") != "reported":
            continue
        in_tok = row.get("gen_ai.usage.input_tokens")
        out_tok = row.get("gen_ai.usage.output_tokens")
        if not isinstance(in_tok, int) or not isinstance(out_tok, int):
            continue
        bucket = buckets[stage]
        bucket["input_tokens"].append(in_tok)
        bucket["output_tokens"].append(out_tok)
        if row.get("session_id") is not None:
            bucket["per_session"] = True
    return dict(buckets)


def _forecast_from_local(
    buckets: dict[str, dict[str, Any]], n_sessions: int,
) -> tuple[int, int] | None:
    """Sum per-stage medians; multiply per-session stages by n_sessions.

    Returns ``(total_input_tokens, total_output_tokens)`` or ``None`` if
    any stage has fewer than ``_LOCAL_N_THRESHOLD`` samples.
    """
    if not buckets:
        return None
    total_in = 0
    total_out = 0
    for bucket in buckets.values():
        n = len(bucket["input_tokens"])
        if n < _LOCAL_N_THRESHOLD:
            return None
        med_in = int(statistics.median(bucket["input_tokens"]))
        med_out = int(statistics.median(bucket["output_tokens"]))
        multiplier = n_sessions if bucket["per_session"] else 1
        total_in += med_in * multiplier
        total_out += med_out * multiplier
    return total_in, total_out


def _forecast_from_baselines(
    baseline_rows: list[dict[str, Any]], n_sessions: int,
) -> tuple[int, int] | None:
    """Sum baseline medians per stage; multiply per-session stages by n_sessions.

    Per-session vs per-run is inferred from ``stage_id``: stages 5b/8/9 are
    per-session (one row per participant), stages 10/11 are per-run.
    A baseline row is treated as per-session if its ``stage_id`` matches
    the per-session stage prefixes.
    """
    if not baseline_rows:
        return None
    per_session_prefixes = ("s05b", "s08", "s09")
    total_in = 0
    total_out = 0
    for row in baseline_rows:
        med_in = row.get("median_input_tokens")
        med_out = row.get("median_output_tokens")
        if not isinstance(med_in, int) or not isinstance(med_out, int):
            continue
        stage_id = row.get("stage_id", "")
        multiplier = n_sessions if str(stage_id).startswith(per_session_prefixes) else 1
        total_in += med_in * multiplier
        total_out += med_out * multiplier
    if total_in == 0 and total_out == 0:
        return None
    return total_in, total_out


def estimate_pipeline_cost(
    model: str,
    n_sessions: int,
    run_dir: Path | None = None,
) -> float | None:
    """Estimate total LLM cost for a pipeline run before it starts.

    Returns estimated USD, or ``None`` when the model isn't priced or no
    cohort data is available (neither local nor shipped baseline).

    Resolution order:
      1. ``BRISTLENOSE_LLM_FORECAST=legacy`` → pre-Slice-C constant.
      2. Local ``llm-calls.jsonl`` cohort medians (when every per-stage
         cell has ≥ 3 samples).
      3. Shipped ``cohort-baselines.json`` for the (family, major) cohort.
      4. ``None``.
    """
    if n_sessions <= 0:
        return None

    if os.environ.get("BRISTLENOSE_LLM_FORECAST") == "legacy":
        inp, out = _LEGACY_TOKENS_PER_SESSION
        return estimate_cost(model, inp * n_sessions, out * n_sessions)

    if model not in PRICING:
        return None

    provider = _MODEL_PROVIDER.get(model)
    if provider is None:
        return None
    family, major = normalise_model(provider, model)

    if run_dir is not None:
        buckets = _scan_local_jsonl(run_dir, family, major)
        local = _forecast_from_local(buckets, n_sessions)
        if local is not None:
            return estimate_cost(model, local[0], local[1])

    baseline_rows = _baseline_lookup(family, major)
    baseline = _forecast_from_baselines(baseline_rows, n_sessions)
    if baseline is not None:
        return estimate_cost(model, baseline[0], baseline[1])

    return None
