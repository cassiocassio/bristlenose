"""Model-declaration axis invariants.

Distinct from test_quality.py: this file pins the *catalogue declaration* of
models on `BackendOption.models` (`ModelOption.id` / `.default`), whereas
test_quality.py pins the *editorial ratings* keyed in `_LLM_QUALITY`. The two
axes are orthogonal (`ModelOption.default` is BN's wired default; a
`QualityRating.default` is the editorial endorsement) — don't conflate them.

Per Bach: pin what would silently break, not editorial values that will shift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bristlenose.pipeline_view.catalogue import _LLM_BACKENDS
from bristlenose.providers import PROVIDERS

_SWIFT_PROVIDER = (
    Path(__file__).resolve().parents[2]
    / "desktop/Bristlenose/Bristlenose/LLMProvider.swift"
)

# catalogue backend id → (registry provider name, Swift enum case). Azure has no
# catalogued models (its row is synthesised from the deployment name) and Local
# is governed by the Ollama catalogue, so neither is in the shipping-list check.
_CLOUD = {
    "claude": ("anthropic", "claude"),
    "openai": ("openai", "chatGPT"),
    "google": ("google", "gemini"),
}


def _picker_models(swift_case: str) -> list[str]:
    """The models the macOS picker offers for one provider, read from Swift."""
    src = _SWIFT_PROVIDER.read_text(encoding="utf-8")
    block = re.search(r"var availableModels: \[String\] \{(.*?)\n    \}", src, re.S)
    assert block, f"could not find availableModels in {_SWIFT_PROVIDER}"
    match = re.search(rf"case \.{swift_case}: \[([^\]]*)\]", block.group(1))
    assert match, f"no availableModels case for .{swift_case}"
    models = re.findall(r'"([^"]+)"', match.group(1))
    # A parse that silently finds nothing would make the assertions below
    # vacuously true — the failure mode this whole test exists to prevent.
    assert models, f"parsed zero models for .{swift_case}"
    return models


@pytest.mark.parametrize("backend_id", sorted(_CLOUD))
def test_catalogue_ids_match_the_shipping_model_lists(backend_id: str) -> None:
    """Every catalogued cloud model is one we actually ship.

    The Pipeline view is a *fourth* place model ids are written down, after
    `providers.py`, `LLMProvider.swift` and the pricing table. On 4 Sep 2026 the
    other three moved and this one did not, so the view spent the day offering
    `gemini-2.5-pro` — 404 for new accounts — as Gemini's default, with the
    model that actually runs shown beneath it as an untested synthesised row.
    Nothing was red, because nothing connected the lists.
    """
    provider, swift_case = _CLOUD[backend_id]
    backend = next(b for b in _LLM_BACKENDS if b.id == backend_id)
    shipped = {PROVIDERS[provider].default_model, *_picker_models(swift_case)}
    for model in backend.models:
        assert model.id in shipped, (
            f"catalogue offers {backend_id}/{model.id}, which is in neither "
            f"providers.py's default nor the macOS picker: {sorted(shipped)}. "
            f"Either ship it or drop it — a model in the view that the app "
            f"cannot dispatch is the 4 Sep 2026 defect."
        )


@pytest.mark.parametrize("backend_id", sorted(_CLOUD))
def test_catalogue_default_model_is_the_registry_default(backend_id: str) -> None:
    """The view's per-provider default is the one dispatch would pick.

    Separate from the membership test above: a catalogue can list only shipping
    models and still flag the wrong one as the provider's out-of-the-box pick.
    """
    provider, _ = _CLOUD[backend_id]
    backend = next(b for b in _LLM_BACKENDS if b.id == backend_id)
    flagged = [m.id for m in backend.models if m.default]
    assert flagged == [PROVIDERS[provider].default_model], (
        f"{backend_id} flags {flagged} as default; providers.py dispatches "
        f"{PROVIDERS[provider].default_model!r}"
    )


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
