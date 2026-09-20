"""Findings are written in chunks and yielded as each chunk lands.

It used to be one LLM call per codebook, awaited whole. That is the cheapest
way to get every finding and the worst way to get the FIRST one: the reader sat
behind a placeholder for the length of a batched serve-time call, and
``serve_autocode`` — the closest measured analogue in the telemetry — runs a
median 25.8s and a max of 54.3s.

Chunking is only safe because cards are independent: the prompt's one
cross-cutting instruction ("across all evidence") is about the quotes WITHIN a
card, and the output schema is "one elaboration per input signal, in order".
If that stops being true, these tests keep passing and the NAMES quietly get
worse — so that premise is asserted in ``test_the_prompt_still_treats_cards_as
_independent`` rather than left in a comment.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

import pytest

from bristlenose.server.routes.analysis import (
    ELABORATION_CHUNK,
    CodebookAnalysisOut,
    MatrixOut,
    TagSignal,
    _elaborate_signals,
)


@dataclass
class _Elab:
    signal_name: str
    pattern: str
    elaboration: str


def _sig(n: int) -> TagSignal:
    """A real TagSignal, not a stand-in — a degenerate fixture would let the
    generator's own guards make the path under test unreachable."""
    return TagSignal(
        location=f"Place {n}", source_type="section", group_name=f"Group {n}",
        colour_set="ux", count=2, participants=["p1", "p2"],
        n_eff=1.8, mean_intensity=2.0, concentration=1.4,
        composite_signal=1.0 - n / 100, confidence="moderate",
        label=f"Group {n}", label_kind="group",
        quotes=[{
            "text": f"quote {n}", "participant_id": "p1", "session_id": "s1",
            "start_seconds": 1.0, "intensity": 2, "tag_names": ["t"],
            "segment_index": 0,
        }],
    )


_EMPTY_MATRIX = MatrixOut(
    cells={}, row_totals={}, col_totals={}, grand_total=0,
    row_labels=[], col_labels=[],
)


def _codebook(n_signals: int) -> CodebookAnalysisOut:
    return CodebookAnalysisOut(
        codebook_id="uxr", codebook_name="UX", colour_set="ux",
        signals=[_sig(i) for i in range(n_signals)],
        section_matrix=_EMPTY_MATRIX, theme_matrix=_EMPTY_MATRIX, columns=[],
        participant_ids=["p1", "p2"], tag_colour_indices={},
        source_breakdown={"accepted": 2, "pending": 0, "total": 2},
    )


@pytest.fixture
def fake_llm(monkeypatch):
    """Record the size of every batch handed to the model."""
    import bristlenose.server.elaboration as el
    from bristlenose.server.elaboration import compute_signal_key

    calls: list[int] = []

    async def _gen(signals, codebook_id, settings, db, project_id):
        calls.append(len(signals))
        return {
            compute_signal_key(s.source_type, s.location, s.group_name):
                _Elab(f"Finding {s.location}", "gap", "Because. || And so.")
            for s in signals
        }

    monkeypatch.setattr(el, "generate_elaborations", _gen)
    monkeypatch.setattr("bristlenose.config.load_settings", lambda: object())
    return calls


async def _drain(codebooks):
    return [(k, e) async for k, e in _elaborate_signals(codebooks, db=None, project_id=1)]


class TestItArrivesInPieces:
    @pytest.mark.asyncio
    async def test_a_finding_is_yielded_as_soon_as_its_chunk_lands(self, fake_llm) -> None:
        out = await _drain([_codebook(ELABORATION_CHUNK * 2 + 1)])
        assert len(out) == ELABORATION_CHUNK * 2 + 1
        assert fake_llm == [ELABORATION_CHUNK, ELABORATION_CHUNK, 1], (
            f"not chunked: the model was handed {fake_llm}"
        )

    @pytest.mark.asyncio
    async def test_one_call_for_a_set_that_fits(self, fake_llm) -> None:
        """The cheap path is not made expensive: under a chunk, one call."""
        await _drain([_codebook(ELABORATION_CHUNK - 1)])
        assert fake_llm == [ELABORATION_CHUNK - 1]

    @pytest.mark.asyncio
    async def test_strongest_first(self, fake_llm) -> None:
        """A researcher reads top down, so the first chunk must be the top cards."""
        out = await _drain([_codebook(ELABORATION_CHUNK + 2)])
        assert [k for k, _ in out][:2] == ["section|Place 0|Group 0", "section|Place 1|Group 1"]

    @pytest.mark.asyncio
    async def test_a_refusal_costs_one_chunk_not_the_codebook(self, monkeypatch) -> None:
        """The blast radius is why chunking is worth its extra prompt overhead.

        One batched call meant a single refusal left every card in the codebook
        nameless. Here the first chunk fails and the rest still arrive.
        """
        import bristlenose.server.elaboration as el
        from bristlenose.server.elaboration import compute_signal_key

        seen: list[int] = []

        async def _gen(signals, codebook_id, settings, db, project_id):
            seen.append(len(signals))
            if len(seen) == 1:
                return {}          # what generate_elaborations returns on failure
            return {
                compute_signal_key(s.source_type, s.location, s.group_name):
                    _Elab("n", "gap", "a || b") for s in signals
            }

        monkeypatch.setattr(el, "generate_elaborations", _gen)
        monkeypatch.setattr("bristlenose.config.load_settings", lambda: object())

        out = await _drain([_codebook(ELABORATION_CHUNK * 2)])
        assert len(out) == ELABORATION_CHUNK, "a failed chunk took the others with it"


class TestThePremiseChunkingRestsOn:
    def test_the_prompt_still_treats_cards_as_independent(self) -> None:
        """Chunking is quality-neutral only while this holds.

        If the prompt ever asks the model to differentiate a card against the
        others in its batch, chunking silently makes names worse and every test
        above still passes. Pinned here so the change is loud.
        """
        prompt = pathlib.Path("bristlenose/llm/prompts/signal-elaboration.md").read_text()
        schema = "One elaboration per input signal, in order"

        from bristlenose.llm.structured import SignalElaborationResult
        assert schema in str(SignalElaborationResult.model_fields["elaborations"].description)

        for phrase in ("other cards", "across the cards", "compared with the other",
                       "distinct from the other", "each of the other"):
            assert phrase not in prompt.lower(), (
                f"the prompt now reasons across cards ({phrase!r}) — chunking is no "
                "longer free, and ELABORATION_CHUNK must be reconsidered"
            )
