"""Catalogue invariants — behavioural, not snapshot."""

from __future__ import annotations

from bristlenose.pipeline_view.catalogue import STAGES, find_stage


def test_every_stage_has_unique_id() -> None:
    ids = [s.id for s in STAGES]
    assert len(ids) == len(set(ids)), "duplicate stage ids in catalogue"


def test_every_stage_has_non_empty_name_and_notes() -> None:
    for s in STAGES:
        assert s.name.strip(), f"empty name on {s.id}"
        assert s.notes.strip(), f"empty notes on {s.id}"


def test_apple_fm_row_present_and_typed_apple_fm() -> None:
    apple = find_stage("apple_foundation_models")
    assert apple is not None
    assert apple.kind == "apple_fm"


def test_find_stage_returns_none_on_unknown() -> None:
    assert find_stage("not_a_real_stage") is None


def test_kinds_are_within_known_set() -> None:
    allowed = {"transcription", "llm", "anonymisation", "apple_fm"}
    for s in STAGES:
        assert s.kind in allowed, f"unknown kind {s.kind!r} on {s.id}"


# ── catalogue invariants ──────────────────────────────────────────────────


def test_every_backend_option_has_non_empty_id_and_display() -> None:
    for stage in STAGES:
        for option in stage.viable_backends:
            assert option.id.strip(), f"empty id on option in {stage.id}"
            assert option.display.strip(), f"empty display on {option.id} in {stage.id}"


def test_every_requirement_has_a_translation_key() -> None:
    """`reason_key` is a translation key like `pipeline.reasons.foo`.

    v2: `requirements_for` is object-taking and aggregates backend-level +
    model-level requirements. Sweep both grains."""
    from bristlenose.pipeline_view.catalogue import requirements_for

    for stage in STAGES:
        for option in stage.viable_backends:
            grains = [None, *option.models]
            for model in grains:
                for req in requirements_for(option, model):
                    assert req.reason_key.startswith("pipeline.reasons."), (
                        f"{stage.id}/{option.id} requirement {req.kind} has "
                        f"non-key reason_key={req.reason_key!r}"
                    )


def test_five_llm_stages_share_identical_viable_backends() -> None:
    """If someone hand-edits one LLM stage's options, this catches the drift.

    Load-bearing: dedup at code level relies on the shared `_LLM_BACKENDS`
    constant; the render layer's collapse-when-uniform relies on this equality.
    """
    llm_stages = [s for s in STAGES if s.kind == "llm"]
    assert len(llm_stages) == 5, f"expected 5 LLM stages, found {len(llm_stages)}"
    first_ids = [o.id for o in llm_stages[0].viable_backends]
    for stage in llm_stages[1:]:
        ids = [o.id for o in stage.viable_backends]
        assert ids == first_ids, (
            f"LLM stage {stage.id} has different viable_backends than "
            f"{llm_stages[0].id}: {ids} vs {first_ids}"
        )


def test_all_python_packages_derives_from_catalogue() -> None:
    """Single source of truth — host.installed_packages probe set."""
    from bristlenose.pipeline_view.catalogue import all_python_packages

    pkgs = all_python_packages()
    # The four packages declared in catalogue cells.
    assert pkgs == {"mlx_whisper", "ctranslate2", "presidio_analyzer", "en_core_web_lg"}
