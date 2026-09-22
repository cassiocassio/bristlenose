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
PRICE_TABLE_VERSION = "2026-09-04"
CURRENCY = "USD"

# Pricing per million tokens: (input_rate_usd, output_rate_usd).
PRICING: dict[str, tuple[float, float]] = {
    # Anthropic (Claude)
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    # Legacy — kept because a user pinned to one in Settings still needs a
    # cost estimate. `estimate_cost` returns None for anything unlisted, so a
    # missing row is a silently absent feature, not an error.
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-3-5-20241022": (0.80, 4.0),
    # OpenAI (ChatGPT) — verified against developers.openai.com/api/docs/models
    # on 2026-09-04.
    "gpt-6-astra": (10.0, 50.0),
    "gpt-5.6-sol": (4.0, 20.0),
    "gpt-5.6-terra": (2.0, 12.0),
    "gpt-5.6-luna": (0.20, 1.20),
    # Legacy — still selectable, and still the Azure picker's list.
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    # Google (Gemini). Verified against ai.google.dev/gemini-api/docs/pricing
    # on 2026-09-04 — the 2.5-flash row was wrong in BOTH directions ($0.15/
    # $3.50 recorded against an actual $0.30/$2.50), so every Gemini cost
    # estimate has been understating input and overstating output.
    #
    # NOTE the 3.x rows are PROMOTIONAL through 2026-12-31 and roughly double
    # on 2027-01-01 (3.8-flash goes to $1.50/$7.50). Re-check at the turn of
    # the year rather than trusting these.
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.5-flash-lite": (0.30, 2.50),
}

# Mirrors PRICING — provider lookup for cohort key resolution.
_MODEL_PROVIDER: dict[str, str] = {
    "claude-sonnet-5": "anthropic",
    "claude-opus-5": "anthropic",
    "claude-haiku-4-5-20251001": "anthropic",
    "claude-sonnet-4-6": "anthropic",
    "claude-opus-4-8": "anthropic",
    "claude-sonnet-4-20250514": "anthropic",
    "claude-haiku-3-5-20241022": "anthropic",
    "gpt-6-astra": "openai",
    "gpt-5.6-sol": "openai",
    "gpt-5.6-terra": "openai",
    "gpt-5.6-luna": "openai",
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "gemini-2.5-flash": "google",
    "gemini-2.5-pro": "google",
    "gemini-3.8-flash": "google",
    "gemini-3.7-flash": "google",
    "gemini-3.6-flash": "google",
    "gemini-3.5-flash": "google",
    "gemini-3.5-flash-lite": "google",
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
#
# It applies to PER-SESSION stages only. A per-run stage (s10, s11) issues
# exactly one call per run by construction, so demanding three samples
# demands three runs of the same project — and because an under-sampled
# bucket used to veto the whole forecast, a single-run project could never
# use its own data no matter how many sessions it had. Measured 21 Sep 2026
# on the FOSSDA log: 39 well-sampled per-session rows thrown away because
# s10 and s11 had one row each, which is all they will ever have.
_LOCAL_N_THRESHOLD = 3

# Per-run stages need one sample, because one is the whole population.
_PER_RUN_N_THRESHOLD = 1

# Cohort key used when no family-specific baseline matches. Token usage is
# driven by the transcript and the prompt schema far more than by the model,
# so a pooled median is a better answer than no answer at all — which is
# what every unseen model got before 21 Sep 2026, including three of the
# four cloud providers' current defaults.
_GENERIC_COHORT = "*"


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
    """Return one baseline row per stage for the nearest matching cohort.

    Resolution is widest-last, and returns at most one row per ``stage_id``
    so a family carrying two majors cannot double-count a stage:

      1. exact ``(family, major)``;
      2. same ``family``, nearest major (prefer the highest below the one
         asked for, else the lowest above it);
      3. the pooled ``("*", "*")`` cohort.

    Step 2 exists because a model generation bump does not change how many
    tokens a transcript is. ``claude-sonnet-5`` is priced but unseen, and
    before this it forecast ``None`` while ``claude-sonnet-4`` rows sat in
    the same file. Step 3 covers a family we have never measured at all —
    ``gpt-5.6-terra`` and ``gemini-3.8-flash``, two current provider
    defaults, both of which normalise to a family with no rows.
    """
    rows = _load_baselines()

    exact = [
        row for row in rows
        if row.get("model_family") == family and row.get("model_major") == major
    ]
    if exact:
        return _one_row_per_stage(exact)

    same_family = [row for row in rows if row.get("model_family") == family]
    if same_family:
        nearest = _nearest_major(same_family, major)
        if nearest is not None:
            return _one_row_per_stage(
                [row for row in same_family if row.get("model_major") == nearest],
            )

    generic = [
        row for row in rows
        if row.get("model_family") == _GENERIC_COHORT
    ]
    return _one_row_per_stage(generic)


def _one_row_per_stage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse to the first row seen per ``stage_id``.

    A forecast sums across stages, so two rows for one stage would silently
    bill it twice.
    """
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        stage_id = str(row.get("stage_id", ""))
        if stage_id and stage_id not in seen:
            seen[stage_id] = row
    return list(seen.values())


def _nearest_major(rows: list[dict[str, Any]], major: str) -> str | None:
    """Pick the closest available major: highest below, else lowest above."""
    try:
        want = int(major)
    except (TypeError, ValueError):
        return None
    available: set[int] = set()
    for row in rows:
        try:
            available.add(int(str(row.get("model_major"))))
        except (TypeError, ValueError):
            continue
    if not available:
        return None
    below = [m for m in available if m <= want]
    return str(max(below)) if below else str(min(available))


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

    Returns ``(total_input_tokens, total_output_tokens)``, or ``None`` when
    no bucket clears its threshold.

    The threshold is per-bucket and depends on the stage's cardinality:
    ``_LOCAL_N_THRESHOLD`` for a per-session stage, ``_PER_RUN_N_THRESHOLD``
    for a per-run one. A bucket that misses its threshold is **skipped**
    rather than vetoing the forecast — the caller tops the result up from
    the shipped baseline for whichever stages the local data could not
    speak for, so one thin cell no longer discards every good one.
    """
    if not buckets:
        return None
    covered = _local_covered_stages(buckets)
    if not covered:
        return None
    total_in = 0
    total_out = 0
    for stage_id in covered:
        bucket = buckets[stage_id]
        med_in = int(statistics.median(bucket["input_tokens"]))
        med_out = int(statistics.median(bucket["output_tokens"]))
        multiplier = n_sessions if bucket["per_session"] else 1
        total_in += med_in * multiplier
        total_out += med_out * multiplier
    return total_in, total_out


def _local_covered_stages(buckets: dict[str, dict[str, Any]]) -> set[str]:
    """Stage ids whose local bucket cleared its threshold.

    The single place the threshold rule lives — ``_forecast_from_local``
    sums exactly these stages and ``estimate_pipeline_cost`` skips exactly
    these when topping up from the shipped baseline, so the two cannot
    disagree about which stage the local data spoke for.
    """
    covered: set[str] = set()
    for stage_id, bucket in buckets.items():
        threshold = (
            _LOCAL_N_THRESHOLD if bucket["per_session"] else _PER_RUN_N_THRESHOLD
        )
        if len(bucket["input_tokens"]) >= threshold:
            covered.add(stage_id)
    return covered


# Stages that issue one call per participant. Everything else is per-run.
_PER_SESSION_STAGE_PREFIXES = ("s05b", "s08", "s09")


def _is_per_session_stage(stage_id: str) -> bool:
    return str(stage_id).startswith(_PER_SESSION_STAGE_PREFIXES)


def _forecast_from_baselines(
    baseline_rows: list[dict[str, Any]],
    n_sessions: int,
    skip_stages: set[str] | None = None,
) -> tuple[int, int] | None:
    """Sum baseline medians per stage; multiply per-session stages by n_sessions.

    Per-session vs per-run is inferred from ``stage_id``: stages 5b/8/9 are
    per-session (one row per participant), stages 10/11 are per-run.

    ``skip_stages`` names stages the local log already answered for, so the
    two sources compose instead of competing — local where it is trusted,
    shipped baseline for the rest.
    """
    if not baseline_rows:
        return None
    skip = skip_stages or set()
    total_in = 0
    total_out = 0
    for row in baseline_rows:
        stage_id = str(row.get("stage_id", ""))
        if stage_id in skip:
            continue
        med_in = row.get("median_input_tokens")
        med_out = row.get("median_output_tokens")
        if not isinstance(med_in, int) or not isinstance(med_out, int):
            continue
        multiplier = n_sessions if _is_per_session_stage(stage_id) else 1
        total_in += med_in * multiplier
        total_out += med_out * multiplier
    if total_in == 0 and total_out == 0:
        return None
    return total_in, total_out


def cohort_medians(family: str, major: str, stage_id: str) -> tuple[int, int] | None:
    """Shipped per-call median ``(input, output)`` tokens for one stage.

    Used by ``telemetry.record_call`` to stamp ``cost_usd_predicted`` on each
    row, so the residual against ``cost_usd_actual_estimate`` measures how far
    the *shipped* calibration is from reality. Reads the lru-cached baselines
    only — never the JSONL, since this runs on every LLM call.
    """
    for row in _baseline_lookup(family, major):
        if str(row.get("stage_id", "")) != stage_id:
            continue
        med_in = row.get("median_input_tokens")
        med_out = row.get("median_output_tokens")
        if isinstance(med_in, int) and isinstance(med_out, int):
            return med_in, med_out
    return None


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
      2. Local ``llm-calls.jsonl`` cohort medians, per stage, for every
         stage whose bucket clears its threshold.
      3. Shipped ``cohort-baselines.json`` for whichever stages step 2 could
         not speak for — nearest cohort, pooled ``*`` last.
      4. ``None`` when neither source has anything.

    Steps 2 and 3 **compose**: a project with plenty of per-session rows and
    a single per-run row uses its own numbers for the former and the shipped
    ones for the latter, rather than discarding either.
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

    total_in = 0
    total_out = 0
    covered: set[str] = set()

    if run_dir is not None:
        buckets = _scan_local_jsonl(run_dir, family, major)
        local = _forecast_from_local(buckets, n_sessions)
        if local is not None:
            total_in, total_out = local
            covered = _local_covered_stages(buckets)

    baseline_rows = _baseline_lookup(family, major)
    baseline = _forecast_from_baselines(baseline_rows, n_sessions, skip_stages=covered)
    if baseline is not None:
        total_in += baseline[0]
        total_out += baseline[1]

    if total_in == 0 and total_out == 0:
        return None
    return estimate_cost(model, total_in, total_out)
