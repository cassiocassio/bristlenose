"""The repair step for providers that describe a shape but do not enforce it.

Grounded in a measured incident, not an imagined one. `claude-sonnet-5` returned
malformed tool input on two of the six real stage prompts — quote-clustering
(2 of 2 passes) and thematic-grouping (1 of 2) — while the four earlier stages
passed, so a run died at stage 10 or 11, *after* transcription and every
per-session quote call had been paid for. Sonnet 4.6 was clean on identical
input. `docs/design-llm-live-checking.md` carries the full record.

The shapes below are the ones observed: a field arriving as a JSON **string**
carrying the result re-serialised, and a field arriving as a **dict** carrying
the expected container. Everything else here exists to stop the repair from
becoming a "make it parse" pass, which would hide the next genuine break.
"""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import ValidationError

from bristlenose.llm.client import _validate_repairing
from bristlenose.llm.structured import (
    QuoteExtractionResult,
    ScreenClusteringResult,
    ThematicGroupingResult,
    repair_candidates,
)

GOOD_CLUSTERS = {
    "clusters": [
        {
            "screen_label": "Renewal form",
            "description": "Where the user completes the renewal.",
            "display_order": 1,
            "quote_indices": [0, 2],
        }
    ]
}
GOOD_THEMES = {
    "themes": [
        {
            "theme_label": "Navigation mismatch",
            "description": "The email's wording does not match the interface.",
            "quote_indices": [1, 3],
        }
    ]
}


def _repair(data, model):
    return _validate_repairing(data, model, provider="anthropic", model="claude-sonnet-5")


# ---------------------------------------------------------------------------
# The shapes actually seen
# ---------------------------------------------------------------------------


def test_field_arrives_as_a_json_string_carrying_the_container():
    """The headline Sonnet 5 shape: `clusters` is a str holding the list."""
    payload = {"clusters": json.dumps(GOOD_CLUSTERS["clusters"])}
    with pytest.raises(ValidationError):
        ScreenClusteringResult.model_validate(payload)          # unrepaired: dead run
    assert _repair(payload, ScreenClusteringResult).clusters[0].screen_label == "Renewal form"


def test_the_whole_result_re_serialised_inside_the_first_field():
    """`quotes` came back as a string holding the ENTIRE result object.

    This is the exact wording of the 4 Sep observation — "the entire result
    re-serialised inside the first field" — and it is why unwrapping the field
    alone is not enough: what comes out is the parent, not the container.
    """
    payload = {"themes": json.dumps(GOOD_THEMES)}
    with pytest.raises(ValidationError):
        ThematicGroupingResult.model_validate(payload)
    assert _repair(payload, ThematicGroupingResult).themes[0].theme_label == "Navigation mismatch"


def test_field_arrives_as_a_dict_wrapping_the_container():
    """`{"clusters": {"clusters": [...]}}` — a dict where a list was expected."""
    payload = {"clusters": {"clusters": GOOD_CLUSTERS["clusters"]}}
    with pytest.raises(ValidationError):
        ScreenClusteringResult.model_validate(payload)
    assert len(_repair(payload, ScreenClusteringResult).clusters) == 1


def test_field_arrives_as_a_single_key_dict_under_some_other_name():
    payload = {"themes": {"items": GOOD_THEMES["themes"]}}
    assert len(_repair(payload, ThematicGroupingResult).themes) == 1


def test_whole_payload_is_one_json_string():
    assert len(_repair(json.dumps(GOOD_THEMES), ThematicGroupingResult).themes) == 1


# ---------------------------------------------------------------------------
# The repair must not become a "make it parse" pass
# ---------------------------------------------------------------------------


def test_a_well_formed_payload_never_enters_the_repair_path(caplog):
    with caplog.at_level(logging.WARNING):
        assert len(_repair(GOOD_CLUSTERS, ScreenClusteringResult).clusters) == 1
    assert "llm_shape_repair" not in caplog.text, "a clean response must not log a repair"


def test_a_repair_is_a_warning_never_silent(caplog):
    """A provider quietly degrading its output shape is a thing to notice.

    The repair buys the researcher their run; the log line is what says the run
    needed buying. Without it, a model could regress for months and the only
    symptom would be everything continuing to work.
    """
    with caplog.at_level(logging.WARNING):
        _repair({"clusters": json.dumps(GOOD_CLUSTERS["clusters"])}, ScreenClusteringResult)
    assert "llm_shape_repair" in caplog.text
    assert "claude-sonnet-5" in caplog.text
    assert "ScreenClusteringResult" in caplog.text


def test_an_unrepairable_payload_raises_the_original_error():
    """Not the last repair attempt's error — the first one describes what we got."""
    payload = {"clusters": [{"screen_label": "x"}]}   # genuinely missing fields
    with pytest.raises(ValidationError) as got:
        _repair(payload, ScreenClusteringResult)
    with pytest.raises(ValidationError) as want:
        ScreenClusteringResult.model_validate(payload)
    assert str(got.value) == str(want.value)


def test_garbage_is_not_repaired_into_emptiness():
    """The failure mode a lenient repair invites: a valid but vacuous result.

    An empty list satisfies every one of these models, and an empty list is
    exactly how a stage produces a report with nothing in it. A repair that
    reaches that is worse than the crash it replaced.
    """
    for junk in ({"clusters": "not json at all"}, {"clusters": 17}, {"clusters": None}):
        with pytest.raises(ValidationError):
            _repair(junk, ScreenClusteringResult)


def test_candidates_are_derived_from_the_model_not_guessed():
    """A key the model does not declare is never unwrapped."""
    payload = {"themes": [], "some_other_key": json.dumps({"themes": GOOD_THEMES["themes"]})}
    assert all("some_other_key" not in what for what, _ in
               repair_candidates(payload, ThematicGroupingResult))


def test_no_candidates_for_a_non_dict_non_str_payload():
    assert repair_candidates([1, 2, 3], ThematicGroupingResult) == []
    assert repair_candidates(None, ThematicGroupingResult) == []


def test_repair_is_one_level_deep_only():
    """Double-wrapped is not a shape anyone has seen, and guessing at it invites
    the lenient-repair failure above. One level is what was measured."""
    payload = {"themes": json.dumps({"themes": {"themes": GOOD_THEMES["themes"]}})}
    with pytest.raises(ValidationError):
        _repair(payload, ThematicGroupingResult)


# ---------------------------------------------------------------------------
# The exclusion is the load-bearing half
# ---------------------------------------------------------------------------


def test_strict_structured_output_paths_do_not_repair():
    """OpenAI and Azure go through strict Structured Outputs, where the API
    guarantees the shape. A ValidationError there is a real break in that
    guarantee, and repairing it would hide exactly the regression we need to
    see. Asserted structurally because there is no other way to pin a decision
    not to call something."""
    import inspect

    from bristlenose.llm.client import LLMClient

    def code(name: str) -> str:
        """Source with comments stripped.

        Not a bare substring search over the source: the strict paths carry a
        comment *naming* `_validate_repairing` to record why they do not call it,
        and the first version of this test failed on that comment. Matching prose
        as if it were code is the trap CLAUDE.md keeps a section on.
        """
        src = inspect.getsource(getattr(LLMClient, name))
        return "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))

    for name in ("_analyze_openai", "_analyze_azure"):
        assert "_validate_repairing(" not in code(name), f"{name} must not repair"
        assert "model_validate(" in code(name), f"{name} must still validate"

    for name in ("_analyze_anthropic", "_analyze_google"):
        assert "_validate_repairing(" in code(name), f"{name} lost its repair step"


def test_every_shipped_response_model_survives_a_repair_attempt():
    """`repair_candidates` runs against whatever model a stage passes, so it must
    not raise on any of them — including ones with no list field at all."""
    for model in (QuoteExtractionResult, ScreenClusteringResult, ThematicGroupingResult):
        assert repair_candidates({}, model) == []
        repair_candidates(dict.fromkeys(model.model_fields, "x"), model)


def test_a_failed_call_logs_field_paths_not_the_reply(caplog):
    """`llm_call_failed` is one line and quotes none of the model's reply.

    pydantic's message runs to several lines and repeats each bad
    ``input_value``, which is the participant's words. Seen in the any-llm
    walks (23 Oct 2026), where a Mistral Small reply dropped required fields.
    """
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from bristlenose.config import BristlenoseSettings
    from bristlenose.llm.client import LLMClient

    words = "I nearly cancelled the whole renewal"
    bad = {"quotes": [{"verbatim_excerpt": words}]}
    client = LLMClient(BristlenoseSettings(  # type: ignore[arg-type]
        llm_provider="anthropic", anthropic_api_key="sk-ant-test-key",
        llm_model="claude-sonnet-4-6", llm_max_tokens=8192,
    ))
    response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="tool_use", name="structured_output", input=bad)],
        usage=SimpleNamespace(input_tokens=100, output_tokens=5),
        model="claude-sonnet-4-6",
    )
    client._anthropic_client = AsyncMock()
    client._anthropic_client.messages.create = AsyncMock(return_value=response)

    with caplog.at_level(logging.WARNING), pytest.raises(ValidationError):
        asyncio.run(client.analyze("sys", "usr", QuoteExtractionResult))

    [line] = [r.getMessage() for r in caplog.records if "llm_call_failed" in r.getMessage()]
    assert "\n" not in line
    assert words not in line
    assert "quotes.0." in line and "(missing)" in line


# What a provider's error body carries back must not reach the log either.
# OpenRouter's moderation 403 puts up to 100 characters of the prompt in
# `metadata.flagged_input` (documented; not yet captured live). Review round 2,
# finding 41.
_FLAGGED = "she said she had thought about ending it"


class _StatusError(Exception):
    """The openai/anthropic SDKs' shape: `str` is the whole body."""

    def __init__(self, status: int, body: dict) -> None:
        self.status_code = status
        self.body = body
        super().__init__(f"Error code: {status} - {body}")


def _moderation_403() -> _StatusError:
    return _StatusError(403, {
        "message": "Input was flagged by moderation", "code": 403,
        "metadata": {"reasons": ["self-harm"], "flagged_input": _FLAGGED,
                     "provider_name": "OpenAI"},
    })


def test_a_provider_error_logs_its_status_and_message_not_its_body(caplog):
    import asyncio
    from unittest.mock import AsyncMock

    from bristlenose.config import BristlenoseSettings
    from bristlenose.llm.client import LLMClient

    client = LLMClient(BristlenoseSettings(  # type: ignore[arg-type]
        llm_provider="anthropic", anthropic_api_key="sk-ant-test-key",
        llm_model="claude-sonnet-4-6", llm_max_tokens=8192,
    ))
    client._anthropic_client = AsyncMock()
    client._anthropic_client.messages.create = AsyncMock(side_effect=_moderation_403())
    with caplog.at_level(logging.WARNING), pytest.raises(_StatusError):
        asyncio.run(client.analyze("sys", "usr", QuoteExtractionResult))
    [line] = [r.getMessage() for r in caplog.records if "llm_call_failed" in r.getMessage()]
    assert _FLAGGED not in line
    assert "status=403" in line and "flagged by moderation" in line


def test_any_llms_wrapper_is_read_through_to_the_providers_body():
    """any-llm's error has no `body`; the provider's error it wraps does, and
    any-llm's own `str` repeats that error's text, body included."""
    from bristlenose.llm.client import failure_summary

    inner = _moderation_403()
    outer = RuntimeError(f"[openrouter] {inner}")
    outer.original_exception = inner  # type: ignore[attr-defined]
    summary = failure_summary(outer)
    assert _FLAGGED not in summary
    assert summary.startswith("status=403")


def test_a_stage_that_falls_back_logs_no_reply_text(caplog):
    """Stages 5b, 8, 9, 10 and 11 log the error they caught; pydantic's text
    quotes the reply. Stage 10 stands for the seven sites."""
    import asyncio
    from unittest.mock import AsyncMock

    from bristlenose.models import ExtractedQuote, QuoteType
    from bristlenose.stages.s10_quote_clustering import cluster_by_screen

    words = "I cried"  # short: pydantic shortens a long value in its message
    try:
        ScreenClusteringResult.model_validate({"clusters": [{"screen_label": words}]})
    except ValidationError as exc:
        error = exc
    client = AsyncMock()
    client.provider = "anthropic"
    client.analyze = AsyncMock(side_effect=error)
    quote = ExtractedQuote(
        session_id="s1", participant_id="p1", start_timecode=1.0, end_timecode=2.0,
        text="the basket", topic_label="Basket", quote_type=QuoteType.SCREEN_SPECIFIC,
    )
    with caplog.at_level(logging.DEBUG):
        asyncio.run(cluster_by_screen([quote], client))
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "Screen clustering failed" in logged
    assert words in str(error)  # the shape this test exists for
    assert words not in logged
