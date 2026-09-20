"""Signal elaboration's LLM spend reaches ``llm-calls.jsonl``.

It did not, for as long as the feature has existed. ``generate_elaborations``
bound ``telemetry.stage("serve_signal_elaboration")`` — the half that LABELS a
row — and never a run context, which is the half that decides whether there is
a file to write it to. ``record_call`` then finds no ``_run_dir``, logs at
DEBUG and returns, so an entire surface's spend was absent with nothing
anywhere reporting it. Found by reading 260 logged calls and noticing which
stage was missing, not by anything going red.

The check that matters is the FILE, not the contextvar: a bound contextvar
pointing somewhere nothing writes would satisfy a weaker test and still record
nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bristlenose.llm import telemetry
from bristlenose.server.elaboration import generate_elaborations


def _record_one() -> None:
    """Mirrors the production call shape exactly, stage and all.

    `record_call` needs THREE contextvars — `_run_dir`, `_run_id` and
    `_stage_id` — and a missing one of any of them is the same silent DEBUG
    skip. A helper that recorded without the stage would test a path production
    never takes, and would have "passed" against the very defect below.
    """
    with telemetry.stage("serve_signal_elaboration"):
        telemetry.record_call(
            provider="anthropic",
            request_model="claude-sonnet-5",
            response_model="SignalElaborationResult",
            input_chars=1234,
            elapsed_ms=2500,
            outcome="ok",
            price_table_version="test",
        )


class TestServeRunContext:
    def test_a_call_inside_it_lands_in_the_project_log(self, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        with telemetry.serve_run_context(tmp_path, "elaboration-1-norman-x"):
            _record_one()

        log = out / ".bristlenose" / "llm-calls.jsonl"
        assert log.exists(), "the call was recorded nowhere — the original defect"
        rows = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert len(rows) == 1
        assert rows[0]["run_id"] == "elaboration-1-norman-x"

    def test_it_writes_beside_the_output_not_into_it(self, tmp_path: Path) -> None:
        """The log is a re-identification key: session ids, prompt shas, timing
        fingerprints. It belongs in the hidden `.bristlenose/` dir, never in the
        shareable output root — same rule as `pii_summary.txt`."""
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        with telemetry.serve_run_context(tmp_path, "r"):
            _record_one()

        assert (out / ".bristlenose" / "llm-calls.jsonl").exists()
        assert not (out / "llm-calls.jsonl").exists()

    def test_it_accepts_the_output_dir_as_well_as_the_project_root(
        self, tmp_path: Path
    ) -> None:
        """Callers hold one or the other, and guessing wrong writes the file
        somewhere nobody looks — which is indistinguishable from not writing."""
        with telemetry.serve_run_context(tmp_path, "r"):
            _record_one()
        assert (tmp_path / ".bristlenose" / "llm-calls.jsonl").exists()

    def test_no_project_dir_is_not_an_error(self, tmp_path: Path) -> None:
        """The app can run without a project. That must not raise, and must not
        invent a location — it restores the old silent skip for that case only."""
        with telemetry.serve_run_context(None, "r"):
            _record_one()
        assert list(tmp_path.rglob("llm-calls.jsonl")) == []

    def test_it_restores_the_previous_context(self, tmp_path: Path) -> None:
        """A leaked contextvar sends the NEXT surface's rows into this project."""
        assert telemetry._run_dir.get() is None
        with telemetry.serve_run_context(tmp_path, "r"):
            assert telemetry._run_dir.get() is not None
        assert telemetry._run_dir.get() is None, "context leaked past the block"


class TestTheThreeGuards:
    """Each is a separate silent skip, and elaboration was missing one.

    Recorded because the failure mode is identical from outside — no file, no
    error, a DEBUG line nobody reads — so a future surface that binds two of
    three will look exactly like one that binds none.
    """

    def test_stage_alone_records_nothing(self, tmp_path: Path) -> None:
        """Precisely the shape elaboration shipped in."""
        with telemetry.stage("serve_signal_elaboration"):
            telemetry.record_call(
                provider="anthropic", request_model="m", response_model=None,
                input_chars=1, elapsed_ms=1, outcome="ok", price_table_version="t",
            )
        assert list(tmp_path.rglob("llm-calls.jsonl")) == []

    def test_run_context_alone_records_nothing(self, tmp_path: Path) -> None:
        """The mirror image, and the trap in writing a test for the fix."""
        with telemetry.serve_run_context(tmp_path, "r"):
            telemetry.record_call(
                provider="anthropic", request_model="m", response_model=None,
                input_chars=1, elapsed_ms=1, outcome="ok", price_table_version="t",
            )
        assert list(tmp_path.rglob("llm-calls.jsonl")) == []


class TestElaborationIsWiredToIt:
    def test_generate_elaborations_takes_a_project_dir(self) -> None:
        """Pinned by signature: the parameter is how the route hands the
        location down, and it is optional so the ten existing positional
        callers keep working."""
        import inspect

        from bristlenose.server.elaboration import generate_elaborations

        sig = inspect.signature(generate_elaborations)
        assert "project_dir" in sig.parameters
        assert sig.parameters["project_dir"].default is None

    @pytest.mark.asyncio
    async def test_a_real_generate_call_writes_a_row(self, tmp_path: Path) -> None:
        """End to end, through `generate_elaborations` itself.

        The first version of this asserted on the SOURCE — that the two context
        managers sit near each other — and broke the moment the formatter split
        the `with` across lines. It was also testing the wrong thing: what
        matters is that a row lands, not that two names appear close together.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        from tests.test_elaboration import (
            _make_settings,
            _make_signal,
            _make_signal_quote,
            _make_template,
        )

        out = tmp_path / "bristlenose-output"
        out.mkdir()

        sig = _make_signal(
            location="Homepage", group_name="Discoverability",
            quotes=[_make_signal_quote(text="I see it", tags=["visible action"])],
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []   # cold cache

        item = MagicMock(signal_index=0, signal_name="Nav clarity",
                         pattern="success", elaboration="Clear || they find it.")

        async def _analyze(**_kw):
            # Stands in for the real client, which records from inside the
            # bound context. If the binding is missing this writes nowhere and
            # no exception is raised — which is the whole defect.
            telemetry.record_call(
                provider="anthropic", request_model="claude-sonnet-5",
                response_model="SignalElaborationResult", input_chars=10,
                elapsed_ms=42, outcome="ok", price_table_version="test",
            )
            return MagicMock(elaborations=[item])

        client = AsyncMock()
        client.analyze = _analyze

        with (
            patch("bristlenose.server.codebook.get_template",
                  return_value=_make_template([("Discoverability", "lens", [])])),
            patch("bristlenose.llm.client.LLMClient", return_value=client),
            patch("bristlenose.llm.prompts.get_prompt") as prompt,
        ):
            prompt.return_value.system = "sys"
            prompt.return_value.user = "User: {signals_text}"
            await generate_elaborations(
                [sig], "norman", _make_settings(), db, 1, project_dir=tmp_path,
            )

        log = out / ".bristlenose" / "llm-calls.jsonl"
        assert log.exists(), "elaboration's spend went unrecorded — the defect"
        row = json.loads(log.read_text().splitlines()[0])
        assert row["stage"] == "serve_signal_elaboration"
        assert row["run_id"].startswith("elaboration-1-norman-")
