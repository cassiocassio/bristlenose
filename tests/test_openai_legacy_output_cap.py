"""Every OpenAI model sent the legacy ``max_tokens`` has a known output ceiling.

``_OPENAI_LEGACY_PARAMS`` names the models that take ``max_tokens`` (GPT-4o and its
dated snapshots); the default of 64000 is above what each of them accepts, and the
ChatGPT path, unlike Azure, does not learn a ceiling from the refusal. Until 19 Nov
2026 the two dated snapshots were in the first table and missing from the second, so
choosing either one failed every call with "max_tokens is too large".
"""

from __future__ import annotations

from bristlenose.llm.client import (
    _MODEL_MAX_OUTPUT_TOKENS,
    _OPENAI_LEGACY_PARAMS,
    request_params,
)


def test_every_legacy_model_has_a_ceiling() -> None:
    missing = sorted(_OPENAI_LEGACY_PARAMS - set(_MODEL_MAX_OUTPUT_TOKENS))
    assert missing == []


def test_a_dated_snapshot_is_clamped_at_the_request() -> None:
    for model in ("gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18"):
        assert request_params("openai", model, 64000, 0.1)["max_tokens"] == 16384
