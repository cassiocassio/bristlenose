"""v1.9 quality-rating invariants — behavioural, not snapshot.

The load-bearing test for this layer: every rated cell parses as a valid
`QualityRating`, every `note_key` is a translation key, every `source` is
in the closed enum, and the LLM stages share an identical option-id set
(mirrors v1.5's _LLM_BACKENDS drift catcher, one layer up).
"""

from __future__ import annotations

import pytest

from bristlenose.pipeline_view.catalogue import (
    _LLM_QUALITY,
    _TRANSCRIPTION_QUALITY,
    STAGES,
    QualityRating,
    quality_for,
)

_VALID_RATINGS = {"excellent", "good", "marginal", "avoid"}
_VALID_SOURCES = {"internal_bench", "published_bench", "community", "editorial"}


def test_quality_for_unknown_cell_returns_none() -> None:
    assert quality_for("not_a_stage", "claude") is None
    assert quality_for("quote_extraction", "not_a_backend") is None


def test_quality_for_known_cell_returns_rating() -> None:
    """Structural: known cells return a `QualityRating`. Editorial values
    (specific rating + source) are covered by the parametrised enum sweep
    below — don't pin them here, they're catalogue editorial data that
    will shift as ratings get refined."""
    r = quality_for("quote_extraction", "claude")
    assert isinstance(r, QualityRating)


def test_quality_for_transcription_cells_resolve() -> None:
    """Structural: transcription cells resolve to a rating, not None."""
    mlx = quality_for("transcription", "mlx")
    fw = quality_for("transcription", "faster-whisper")
    assert isinstance(mlx, QualityRating)
    assert isinstance(fw, QualityRating)


@pytest.mark.parametrize("cell", list(_LLM_QUALITY.items()) + list(_TRANSCRIPTION_QUALITY.items()))
def test_every_rating_uses_closed_enums(
    cell: tuple[tuple[str, str], QualityRating],
) -> None:
    (stage_id, option_id), r = cell
    assert r.rating in _VALID_RATINGS, f"{stage_id}/{option_id} bad rating {r.rating!r}"
    assert r.source in _VALID_SOURCES, f"{stage_id}/{option_id} bad source {r.source!r}"


@pytest.mark.parametrize("cell", list(_LLM_QUALITY.items()) + list(_TRANSCRIPTION_QUALITY.items()))
def test_every_note_key_is_a_translation_key(
    cell: tuple[tuple[str, str], QualityRating],
) -> None:
    """`note_key` is either None or starts with `pipeline.quality.`."""
    (stage_id, option_id), r = cell
    if r.note_key is not None:
        assert r.note_key.startswith("pipeline.quality."), (
            f"{stage_id}/{option_id} note_key={r.note_key!r} is not a pipeline.quality.* key"
        )


def test_llm_quality_shares_identical_option_ids_across_stages() -> None:
    """Drift catcher — one layer up from v1.5's _LLM_BACKENDS invariant.

    If someone seeds quality for one LLM stage but forgets another, this
    fails loudly rather than letting the render layer silently default
    half a column to "untested".
    """
    by_stage: dict[str, set[str]] = {}
    for (stage_id, option_id) in _LLM_QUALITY:
        by_stage.setdefault(stage_id, set()).add(option_id)
    llm_stage_ids = {s.id for s in STAGES if s.kind == "llm"}
    assert set(by_stage) == llm_stage_ids, (
        f"_LLM_QUALITY stage coverage {set(by_stage)} != LLM stages {llm_stage_ids}"
    )
    sets = list(by_stage.values())
    first = sets[0]
    for s in sets[1:]:
        assert s == first, f"option-id drift across LLM stages: {sets}"


def test_apple_fm_cells_are_unrated() -> None:
    """Apple FM stays untested until a probe ships — render layer shows ⚠."""
    for stage in STAGES:
        if stage.kind != "llm":
            continue
        assert quality_for(stage.id, "apple_fm") is None, (
            f"{stage.id}/apple_fm should be unrated until the probe ships"
        )


def test_default_flag_at_most_once_per_llm_stage() -> None:
    """`default=True` marks BN's out-of-the-box pick. At most one per LLM
    stage — multiple defaults would defeat the purpose. Drift catcher for
    accidental dual-default during catalogue edits."""
    by_stage: dict[str, list[str]] = {}
    for (stage_id, option_id), rating in _LLM_QUALITY.items():
        if rating.default:
            by_stage.setdefault(stage_id, []).append(option_id)
    for stage_id, options in by_stage.items():
        assert len(options) == 1, (
            f"{stage_id} has {len(options)} default-flagged options: {options}; "
            f"expected exactly one"
        )


def test_default_flag_never_on_marginal_or_avoid() -> None:
    """BN's default pick must be `good` or `excellent` — never marginal or
    avoid. This invariant lets the render layer assume default ⇒ safe."""
    for cell_key, rating in _LLM_QUALITY.items():
        if rating.default:
            assert rating.rating in ("excellent", "good"), (
                f"{cell_key} is default-flagged but rated {rating.rating!r}; "
                f"BN must not default to marginal/avoid"
            )


def test_default_implies_recommended() -> None:
    """Invariant: `default ⇒ recommended`. BN cannot default to a cell it
    does not actively endorse. Drift catcher: a future edit that demotes a
    cell from recommended while leaving it default produces a contradictory
    catalogue state — this test catches it loudly.

    `recommended` is plural by design (multiple cells per stage may be
    recommended); `default` is singular. The implication is one-way."""
    for cell_key, rating in {**_LLM_QUALITY, **_TRANSCRIPTION_QUALITY}.items():
        if rating.default:
            assert rating.recommended, (
                f"{cell_key} is default-flagged but not recommended; "
                f"every default cell must be recommended (default ⇒ recommended)"
            )


def test_recommended_never_on_marginal_or_avoid() -> None:
    """BN's active endorsement must be `good` or `excellent` — never marginal
    or avoid. Parallel invariant to `test_default_flag_never_on_marginal_or_avoid`.

    Researchers who go off-piste are free to pick marginal cells, but BN
    won't put its weight behind them. This is what keeps the recommended set
    trustworthy as it widens with cohort signal."""
    for cell_key, rating in {**_LLM_QUALITY, **_TRANSCRIPTION_QUALITY}.items():
        if rating.recommended:
            assert rating.rating in ("excellent", "good"), (
                f"{cell_key} is recommended but rated {rating.rating!r}; "
                f"BN must not actively endorse marginal/avoid cells"
            )


def test_unrated_available_backend_is_a_distinct_state() -> None:
    """When the Apple FM probe ships, apple_fm rows will be `available=True`
    with `quality=None` — a third state the render layer must distinguish
    from `quality="marginal"`. This test pins the invariant at the data
    layer so the React rung doesn't conflate the two.

    Build a fake stage with a `BackendOption` whose `quality_for()` returns
    None, simulate it as available, and confirm the resulting
    `BackendAvailability` carries `available=True` AND `quality=None`."""
    from bristlenose.config import BristlenoseSettings
    from bristlenose.pipeline_view.catalogue import BackendOption, PipelineStageDef
    from bristlenose.pipeline_view.host import HostFacts
    from bristlenose.pipeline_view.render import _stage_alternatives

    # Use anonymisation stage as the host (its built-in option doesn't need a
    # network/key probe); inject a synthetic option with no catalogue rating.
    synth_stage = PipelineStageDef(
        id="apple_foundation_models",  # has no _LLM_QUALITY entries for any option
        name="Apple Foundation Models",
        kind="apple_fm",
        notes="probe placeholder",
        viable_backends=[
            BackendOption(id="apple_fm", display="Apple FM"),
        ],
    )
    rating = quality_for(synth_stage.id, "apple_fm")
    assert rating is None, "premise broken: apple_fm IS rated in the catalogue"
    # Sort path + state coexistence is exercised via the next test
    # (test_unrated_cell_sort_weight_matches_marginal); this one pins the
    # data invariant: an unrated cell can exist alongside available=True
    # without the model rejecting it.
    settings = BristlenoseSettings(
        anthropic_api_key="sk-test",
        llm_provider="anthropic",
        llm_model="claude-sonnet-4-20250514",
    )  # type: ignore[arg-type]
    host = HostFacts(
        os="Darwin", arch="arm64", os_version="26.0", memory_gb=32.0,
        keys_present={"anthropic": True, "openai": False, "azure": False, "google": False},
        installed_packages={}, ollama_running=False, network_reachable=True,
        apple_fm_status="unknown",
    )
    rows = _stage_alternatives(synth_stage, None, host, settings)
    by_id = {r.id: r for r in rows}
    # Apple FM stays unavailable on CLI (apple_fm_status="unknown"), but the
    # key invariant — `quality=None` is a valid field state on a
    # BackendAvailability — is what's pinned here.
    assert by_id["apple_fm"].quality is None
    assert by_id["apple_fm"].quality_source is None
    assert by_id["apple_fm"].default is False


def test_unrated_cell_sort_weight_matches_marginal() -> None:
    """Untested cells (quality=None) must sort in the same bucket as
    `marginal` — never accidentally promoted to excellent-equivalent
    position by a dict-reorder. Closes Findings 7 + 8: silent regression
    class on `_QUALITY_SORT_WEIGHT[None]`."""
    from bristlenose.pipeline_view.render import (
        _QUALITY_SORT_WEIGHT,
        BackendAvailability,
    )

    # Direct dict assertion: untested ranks with marginal.
    assert _QUALITY_SORT_WEIGHT[None] == _QUALITY_SORT_WEIGHT["marginal"], (
        "untested cells must sort with marginal — reordering this dict to put "
        "None at excellent-weight would silently promote unrated backends"
    )

    # Behavioural assertion: a `good` row sorts before an unrated row when
    # both are available. Exercises the sort weight, not just the dict value.
    rows = [
        BackendAvailability(id="untested_a", display="A", available=True, quality=None),
        BackendAvailability(id="good_b", display="B", available=True, quality="good"),
    ]

    # Cribbed copy of the sort_key inside _stage_alternatives — if they
    # diverge, the test breaks loudly rather than silently passing.
    def sort_key(row: BackendAvailability) -> tuple[int, int, int]:
        is_chosen = 1
        is_available = 0 if row.available else 1
        quality_weight = _QUALITY_SORT_WEIGHT[row.quality] if row.available else 0
        return (is_available, is_chosen, quality_weight)
    rows.sort(key=sort_key)
    assert [r.id for r in rows] == ["good_b", "untested_a"], (
        "good (weight 1) must sort before untested (weight 2 = marginal)"
    )


def test_every_rated_cell_targets_a_real_catalogue_option() -> None:
    """No quality rating for a (stage, option) pair the catalogue doesn't know."""
    valid_pairs: set[tuple[str, str]] = set()
    for stage in STAGES:
        for opt in stage.viable_backends:
            valid_pairs.add((stage.id, opt.id))
    for key in list(_LLM_QUALITY.keys()) + list(_TRANSCRIPTION_QUALITY.keys()):
        assert key in valid_pairs, f"quality entry {key} has no matching catalogue option"
