"""Model-declaration axis invariants.

Distinct from test_quality.py: this file pins the *catalogue declaration* of
models on `BackendOption.models` (`ModelOption.id` / `.default`), whereas
test_quality.py pins the *editorial ratings* keyed in `_LLM_QUALITY`. The two
axes are orthogonal (`ModelOption.default` is BN's wired default; a
`QualityRating.default` is the editorial endorsement) — don't conflate them.

Per Bach: pin what would silently break, not editorial values that will shift.
"""

from __future__ import annotations

from bristlenose.pipeline_view.catalogue import _LLM_BACKENDS


def test_model_ids_unique_within_provider() -> None:
    for backend in _LLM_BACKENDS:
        ids = [m.id for m in backend.models]
        assert len(ids) == len(set(ids)), (
            f"{backend.id} has duplicate model ids: {ids}"
        )


def test_at_most_one_default_model_per_provider() -> None:
    """`ModelOption.default` is the wired out-of-the-box pick — singular.
    Two defaults on one provider would make dispatch ambiguous."""
    for backend in _LLM_BACKENDS:
        defaults = [m for m in backend.models if m.default]
        assert len(defaults) <= 1, (
            f"{backend.id} has multiple default models: "
            f"{[m.id for m in defaults]}"
        )


def test_every_declared_model_has_non_empty_id_and_display() -> None:
    for backend in _LLM_BACKENDS:
        for model in backend.models:
            assert model.id.strip(), f"empty model id in {backend.id}"
            assert model.display.strip(), (
                f"empty display on {model.id} in {backend.id}"
            )


def test_build_llm_summary_function_does_not_exist() -> None:
    """Deletion invariant: prevents revival-by-grep of v1.9's summary card
    after v2's per-stage rendering replaces it."""
    from bristlenose.pipeline_view import render

    assert not hasattr(render, "_build_llm_summary"), (
        "_build_llm_summary was removed in v2 — per-stage rendering replaces "
        "the summary card. Don't bring it back."
    )
