"""The study usage ledger: tokens counted per job, kept for the life of a study.

Layer 1 of three in docs/design-llm-usage.md. What these pin:

- the wire format, through the contract fixture both languages read;
- the counting, through ``telemetry.record_call`` (every provider's calls pass
  it), including with per-call telemetry switched off and with no
  ``stage(...)`` bound;
- that each job's END writes its row, whichever way it ends: pinned at the
  callers, because a helper test stays green when a caller stops calling it.
  The run lifecycle and the serve-time context are pinned here; the chat lens
  and codebook builder routes beside their own fixtures
  (``test_chat_lens.py``, ``test_codebook_builder.py``); the Re-analyse carry
  and restore at the CLI wiring level (``test_cli_output_backup_wiring.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bristlenose.events import KindEnum
from bristlenose.llm import telemetry, usage
from bristlenose.run_lifecycle import run_lifecycle

_CONTRACT = json.loads(
    (Path(__file__).parent / "fixtures" / "usage-ledger-contract.json").read_text(
        encoding="utf-8"
    )
)


def _call(input_tokens: int | None = 1000, output_tokens: int | None = 200, **kw) -> None:
    """One LLM call as the client reports it."""
    telemetry.record_call(
        provider=kw.pop("provider", "anthropic"),
        request_model=kw.pop("request_model", "claude-sonnet-4"),
        response_model=None,
        input_chars=10,
        elapsed_ms=5,
        outcome=kw.pop("outcome", "ok"),
        price_table_version="test",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        **kw,
    )


# ---------------------------------------------------------------------------
# The contract both languages read
# ---------------------------------------------------------------------------


class TestContract:
    def test_the_reader_turns_the_fixture_lines_into_the_expected_totals(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / usage.USAGE_FILENAME).write_text(
            "\n".join(_CONTRACT["lines"]) + "\n", encoding="utf-8"
        )
        rows = usage.read_rows(tmp_path)
        assert len(rows) == _CONTRACT["expected_rows"]
        totals = [t.model_dump() for t in usage.study_totals(rows)]
        assert totals == _CONTRACT["expected_totals"]

    def test_the_writer_writes_the_fields_the_contract_names_in_its_order(
        self, tmp_path: Path
    ) -> None:
        usage.note_call(
            run_id="r", provider="anthropic", model="m", input_tokens=1, output_tokens=1
        )
        usage.flush(tmp_path, "r", "run")
        line = (tmp_path / usage.USAGE_FILENAME).read_text(encoding="utf-8").splitlines()[0]
        assert list(json.loads(line)) == _CONTRACT["row_fields"]
        assert json.loads(line)["schema_version"] == _CONTRACT["schema_version"]

    def test_every_kind_a_caller_writes_is_in_the_contract(self) -> None:
        """A new kind is a change to what a reader must expect."""
        written = {k.value for k in KindEnum} | {
            "autocode", "elaboration", "chat_lens", "codebook_builder",
        }
        assert written == set(_CONTRACT["kinds"])


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


class TestCounting:
    def test_a_job_writes_one_row_per_model_and_then_forgets(self, tmp_path: Path) -> None:
        for model, n_in, n_out in [("a", 100, 10), ("a", 50, 5), ("b", 7, 1)]:
            usage.note_call(
                run_id="r1", provider="anthropic", model=model,
                input_tokens=n_in, output_tokens=n_out,
            )
        assert usage.flush(tmp_path, "r1", "run") == 2
        rows = usage.read_rows(tmp_path)
        assert [(r.model, r.calls, r.input_tokens, r.output_tokens) for r in rows] == [
            ("a", 2, 150, 15), ("b", 1, 7, 1),
        ]
        assert usage.flush(tmp_path, "r1", "run") == 0, "a tally is written once"

    def test_a_job_with_no_call_leaves_no_ledger(self, tmp_path: Path) -> None:
        """A run served from cache spent nothing; an empty file says otherwise."""
        assert usage.flush(tmp_path, "cached", "run") == 0
        assert not (tmp_path / usage.USAGE_FILENAME).exists()

    def test_a_call_without_reported_usage_is_counted_as_such(self, tmp_path: Path) -> None:
        usage.note_call(
            run_id="r", provider="local", model="llama3.2:3b",
            input_tokens=None, output_tokens=None,
        )
        usage.flush(tmp_path, "r", "run")
        (row,) = usage.read_rows(tmp_path)
        assert (row.calls, row.calls_without_usage, row.input_tokens) == (1, 1, 0)

    def test_one_job_does_not_take_another_jobs_tokens(self, tmp_path: Path) -> None:
        usage.note_call(run_id="mine", provider="p", model="m", input_tokens=1, output_tokens=1)
        usage.note_call(run_id="theirs", provider="p", model="m", input_tokens=9, output_tokens=9)
        usage.flush(tmp_path, "mine", "chat_lens")
        assert [r.run_id for r in usage.read_rows(tmp_path)] == ["mine"]
        assert ("theirs", "p", "m") in usage._tallies

    def test_the_file_is_private(self, tmp_path: Path) -> None:
        usage.note_call(run_id="r", provider="p", model="m", input_tokens=1, output_tokens=1)
        usage.flush(tmp_path, "r", "run")
        import os
        import stat

        if os.name == "posix":
            mode = stat.S_IMODE((tmp_path / usage.USAGE_FILENAME).stat().st_mode)
            assert mode == 0o600


class TestRecordCallCounts:
    """``record_call`` is where every provider's calls arrive."""

    def test_counted_with_per_call_telemetry_switched_off(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv("BRISTLENOSE_LLM_TELEMETRY", "0")
        _call(run_id="r", run_dir=tmp_path, stage_override="s09")
        usage.flush(tmp_path, "r", "run")
        assert not (tmp_path / telemetry.JSONL_FILENAME).exists(), "the switch still holds"
        assert usage.read_rows(tmp_path)[0].input_tokens == 1000

    def test_counted_when_no_stage_is_bound(self, tmp_path: Path) -> None:
        """A missing `stage(...)` drops the per-call row; it must not drop the
        researcher's tokens from their total."""
        _call(run_id="r", run_dir=tmp_path)
        usage.flush(tmp_path, "r", "run")
        assert usage.read_rows(tmp_path)[0].calls == 1

    def test_keyed_on_the_model_the_request_named(self, tmp_path: Path) -> None:
        telemetry.record_call(
            provider="anthropic", request_model="claude-sonnet-4",
            response_model="claude-sonnet-4-20250514", input_chars=1, elapsed_ms=1,
            outcome="ok", price_table_version="t", input_tokens=1, output_tokens=1,
            run_id="r", run_dir=tmp_path, stage_override="s",
        )
        _call(run_id="r", run_dir=tmp_path, stage_override="s", outcome="error",
              input_tokens=None, output_tokens=None)
        usage.flush(tmp_path, "r", "run")
        (row,) = usage.read_rows(tmp_path)
        assert (row.model, row.calls, row.calls_without_usage) == ("claude-sonnet-4", 2, 1)


# ---------------------------------------------------------------------------
# Every job's end writes its row — pinned at the callers
# ---------------------------------------------------------------------------


class TestPipelineRunsAreCounted:
    def _ledger(self, out: Path) -> list[usage.UsageRow]:
        return usage.read_rows(out / ".bristlenose")

    def test_a_completed_run(self, tmp_path: Path) -> None:
        with run_lifecycle(tmp_path, KindEnum.ANALYZE, install_signal_handlers=False):
            _call()
        (row,) = self._ledger(tmp_path)
        assert (row.kind, row.input_tokens, row.output_tokens) == ("analyze", 1000, 200)

    def test_a_failed_run_spent_what_it_spent(self, tmp_path: Path) -> None:
        """The end event's cost is only set for a run that returned; the
        ledger must not inherit that blind spot."""
        with pytest.raises(RuntimeError):
            with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
                _call()
                raise RuntimeError("provider out of credit")
        assert self._ledger(tmp_path)[0].calls == 1

    def test_a_stopped_run(self, tmp_path: Path) -> None:
        with pytest.raises(KeyboardInterrupt):
            with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
                _call()
                raise KeyboardInterrupt()
        assert self._ledger(tmp_path)[0].calls == 1

    def test_runs_add_up(self, tmp_path: Path) -> None:
        for _ in range(2):
            with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
                _call()
        (total,) = usage.study_totals(self._ledger(tmp_path))
        assert (total.jobs, total.input_tokens) == (2, 2000)


class TestServeJobsAreCounted:
    def test_the_serve_context_writes_the_row_when_the_job_fails(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        with pytest.raises(ValueError):
            with telemetry.serve_run_context(tmp_path, "job-1", "elaboration"):
                with telemetry.stage("serve_signal_elaboration"):
                    _call()
                raise ValueError("parse failed after the call was paid for")
        (row,) = usage.read_rows(out / ".bristlenose")
        assert (row.run_id, row.kind) == ("job-1", "elaboration")


# ---------------------------------------------------------------------------
# One meaning across providers (contract `field_meanings`)
# ---------------------------------------------------------------------------


class TestOneMeaningAcrossProviders:
    def test_a_cached_share_counted_inside_the_prompt_moves_to_cache_read(
        self, tmp_path: Path
    ) -> None:
        usage.note_call(run_id="r", provider="openai", model="gpt-4o",
                        input_tokens=1000, output_tokens=10, cached_input_tokens_included=800)
        usage.flush(tmp_path, "r", "run")
        (row,) = usage.read_rows(tmp_path)
        assert (row.input_tokens, row.cache_read_input_tokens) == (200, 800)

    def test_a_cached_share_larger_than_the_prompt_cannot_go_negative(
        self, tmp_path: Path
    ) -> None:
        usage.note_call(run_id="r", provider="google", model="m",
                        input_tokens=100, output_tokens=1, cached_input_tokens_included=500)
        usage.flush(tmp_path, "r", "run")
        (row,) = usage.read_rows(tmp_path)
        assert (row.input_tokens, row.cache_read_input_tokens) == (0, 100)

    @pytest.mark.asyncio
    async def test_gemini_thinking_is_billed_output_and_its_cache_is_read(
        self, tmp_path: Path
    ) -> None:
        """Until 17 Nov 2026 `candidates_token_count` alone was the output:
        Gemini bills thinking as output and reports it apart, so every Gemini
        count and cost — the CLI's too — was short."""
        from types import SimpleNamespace

        from pydantic import BaseModel

        from bristlenose.llm.client import LLMClient
        from tests.test_gemini import _google_settings

        class R(BaseModel):
            answer: str

        meta = SimpleNamespace(prompt_token_count=1000, candidates_token_count=100,
                               thoughts_token_count=400, cached_content_token_count=600)
        response = SimpleNamespace(text='{"answer": "x"}', usage_metadata=meta,
                                   candidates=[], model_version="gemini-2.5-flash",
                                   prompt_feedback=None)

        async def _generate(*a, **k):
            return response

        client = LLMClient(_google_settings())
        client._google_client = SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=_generate))
        )
        tokens = telemetry.set_run_context("g1", tmp_path)
        try:
            with telemetry.stage("s"):
                await client.analyze(system_prompt="s", user_prompt="u", response_model=R)
        finally:
            telemetry.reset_run_context(tokens)
        assert client.tracker.output_tokens == 500, "the CLI line counts thinking too"
        usage.flush(tmp_path, "g1", "run")
        (row,) = usage.read_rows(tmp_path)
        assert (row.input_tokens, row.cache_read_input_tokens, row.output_tokens) == (
            400, 600, 500,
        )

    @pytest.mark.asyncio
    async def test_openai_cached_share_reaches_the_ledger(self, tmp_path: Path) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from pydantic import BaseModel

        from bristlenose.config import BristlenoseSettings
        from bristlenose.llm.client import LLMClient

        class R(BaseModel):
            answer: str

        response = SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content='{"answer": "x"}', refusal=None),
            )],
            usage=SimpleNamespace(
                prompt_tokens=1000, completion_tokens=20,
                prompt_tokens_details=SimpleNamespace(cached_tokens=900),
            ),
            model="gpt-4o",
        )
        client = LLMClient(BristlenoseSettings(
            llm_provider="openai", openai_api_key="sk-test", llm_model="gpt-4o",
            output_dir=tmp_path,
        ))
        sdk = AsyncMock()
        sdk.chat.completions.create = AsyncMock(return_value=response)
        client._openai_client = sdk
        tokens = telemetry.set_run_context("o1", tmp_path)
        try:
            with telemetry.stage("s"):
                await client.analyze(system_prompt="s", user_prompt="u", response_model=R)
        finally:
            telemetry.reset_run_context(tokens)
        usage.flush(tmp_path, "o1", "run")
        (row,) = usage.read_rows(tmp_path)
        assert (row.input_tokens, row.cache_read_input_tokens) == (100, 900)
        assert client.tracker.input_tokens == 1000, "the tracker keeps the provider's count"


# ---------------------------------------------------------------------------
# Live: in flight, late calls, progress lines
# ---------------------------------------------------------------------------


class TestInFlight:
    def test_peek_shows_a_begun_job_for_its_own_study_only(self, tmp_path: Path) -> None:
        mine, theirs = tmp_path / "a", tmp_path / "b"
        usage.begin("j1", mine, "autocode")
        usage.begin("j2", theirs, "autocode")
        for rid in ("j1", "j2"):
            usage.note_call(run_id=rid, provider="p", model="m", input_tokens=5, output_tokens=1)
        assert [f.run_id for f in usage.peek(mine)] == ["j1"]

    def test_a_flushed_job_leaves_flight(self, tmp_path: Path) -> None:
        usage.begin("j", tmp_path, "chat_lens")
        usage.note_call(run_id="j", provider="p", model="m", input_tokens=5, output_tokens=1)
        usage.flush(tmp_path, "j", "chat_lens")
        assert usage.peek(tmp_path) == []

    def test_a_call_that_lands_after_its_job_ended_is_still_written(
        self, tmp_path: Path
    ) -> None:
        """A cancelled task can finish its call after the job flushed. Kept in a
        tally nothing flushes, its tokens would never be counted."""
        usage.begin("j", tmp_path, "autocode")
        usage.note_call(run_id="j", provider="p", model="m", input_tokens=5, output_tokens=1)
        usage.flush(tmp_path, "j", "autocode")
        usage.note_call(run_id="j", provider="p", model="m", input_tokens=7, output_tokens=1)
        (total,) = usage.study_totals(usage.read_rows(tmp_path))
        assert total.input_tokens == 12
        assert usage._tallies == {}

    def test_a_new_job_reusing_an_ended_ones_id_is_not_late(self, tmp_path: Path) -> None:
        """AutoCode and elaboration mint run ids to the second."""
        usage.begin("same", tmp_path, "autocode")
        usage.note_call(run_id="same", provider="p", model="m", input_tokens=1, output_tokens=1)
        usage.flush(tmp_path, "same", "autocode")
        usage.begin("same", tmp_path, "autocode")
        usage.note_call(run_id="same", provider="p", model="m", input_tokens=2, output_tokens=1)
        assert len(usage.read_rows(tmp_path)) == 1, "not written per call"
        assert usage.peek(tmp_path)[0].input_tokens == 2

    def test_a_run_reports_its_use_so_far_on_each_progress_line(self, tmp_path: Path) -> None:
        from bristlenose.events import RunProgressEvent, events_path, read_events

        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False) as handle:
            handle.progress(stage="s08")
            _call(input_tokens=300, output_tokens=30)
            handle.progress(stage="s09")
        progress = [e for e in read_events(events_path(tmp_path))
                    if isinstance(e, RunProgressEvent)]
        assert progress[0].usage_calls is None, "nothing before the first call"
        assert (progress[1].usage_calls, progress[1].usage_input_tokens) == (1, 300)

    def test_the_progress_fields_are_the_contracts(self) -> None:
        from bristlenose.events import RunProgressEvent

        for name in _CONTRACT["progress_fields"]["fields"]:
            assert RunProgressEvent.model_fields[name].default is None


class TestJobsAreVisibleWhileTheyRun:
    """`begin` is what makes a running job readable; pinned at its callers."""

    def test_a_serve_job_is_in_flight_inside_its_context(self, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        with telemetry.serve_run_context(tmp_path, "live-job", "chat_lens"):
            with telemetry.stage("serve_chat_lens"):
                _call()
            (live,) = usage.peek(out / ".bristlenose")
            assert (live.run_id, live.kind) == ("live-job", "chat_lens")
        assert usage.peek(out / ".bristlenose") == []


class TestFailuresAreSaidNotHidden:
    """Review, 17 Nov 2026."""

    def test_a_flush_that_cannot_write_says_what_was_lost_and_does_not_raise(
        self, tmp_path: Path, caplog
    ) -> None:
        import logging

        blocker = tmp_path / "file-not-dir"
        blocker.write_text("x", encoding="utf-8")
        usage.note_call(run_id="r", provider="anthropic", model="m",
                        input_tokens=1234, output_tokens=56)
        with caplog.at_level(logging.WARNING, logger="bristlenose.llm.usage"):
            assert usage.flush(blocker / "sub", "r", "run") == 0
        assert "1234" in caplog.text and "anthropic/m" in caplog.text

    def test_a_count_that_is_not_a_count_is_not_reported_and_cannot_corrupt(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import MagicMock

        usage.note_call(run_id="r", provider="p", model="m", input_tokens=10,
                        output_tokens=2, cache_read_input_tokens=MagicMock())  # type: ignore[arg-type]
        usage.note_call(run_id="r", provider="p", model="m",
                        input_tokens="12", output_tokens=None)  # type: ignore[arg-type]
        assert usage.flush(tmp_path, "r", "run") == 1
        (row,) = usage.read_rows(tmp_path)
        assert (row.calls, row.input_tokens, row.cache_read_input_tokens,
                row.calls_without_usage) == (2, 10, 0, 1)

    def test_a_row_written_before_row_ids_is_read_and_its_repeat_dropped(
        self, tmp_path: Path
    ) -> None:
        old = ('{"schema_version":1,"ts":"2026-11-17T10:00:00.000Z","run_id":"r","kind":"run",'
               '"provider":"anthropic","model":"m","calls":1,"input_tokens":5,"output_tokens":1,'
               '"cache_read_input_tokens":0,"cache_creation_input_tokens":0,'
               '"calls_without_usage":0}')
        (tmp_path / usage.USAGE_FILENAME).write_text(old + "\n" + old + "\n", encoding="utf-8")
        rows, unreadable = usage.read_rows_counted(tmp_path)
        assert (len(rows), unreadable) == (1, 0)


class TestMerge:
    def _tree(self, root: Path, *row_ids: str) -> Path:
        run_dir = root / ".bristlenose"
        run_dir.mkdir(parents=True)
        lines = [
            usage.UsageRow(row_id=rid, ts="2026-11-17T10:00:00.000Z", run_id=rid, kind="run",
                           provider="p", model="m", calls=1, input_tokens=1, output_tokens=1,
                           cache_read_input_tokens=0, cache_creation_input_tokens=0,
                           calls_without_usage=0).model_dump_json()
            for rid in row_ids
        ]
        (run_dir / usage.USAGE_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return root

    def test_adds_only_what_is_missing_and_again_adds_nothing(self, tmp_path: Path) -> None:
        a = self._tree(tmp_path / "a", "1", "2", "3")
        b = self._tree(tmp_path / "b", "1")
        assert usage.merge_ledger(a, b) == 2
        assert usage.merge_ledger(a, b) == 0
        lines = (b / ".bristlenose" / usage.USAGE_FILENAME).read_text(
            encoding="utf-8").splitlines()
        assert len(lines) == 3, "the file holds each row once, not a repeat to be dropped"

    def test_into_a_tree_with_no_ledger(self, tmp_path: Path) -> None:
        a = self._tree(tmp_path / "a", "1")
        (tmp_path / "b").mkdir()
        assert usage.merge_ledger(a, tmp_path / "b") == 1
