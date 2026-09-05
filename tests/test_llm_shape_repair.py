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


def test_an_unrepairable_payload_raises_the_ORIGINAL_error():
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


def test_strict_structured_output_paths_do_NOT_repair():
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
        repair_candidates({f: "x" for f in model.model_fields}, model)
