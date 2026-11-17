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
from collections.abc import Iterator
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


@pytest.fixture(autouse=True)
def _no_tallies_left_over() -> Iterator[None]:
    """The tally is process-wide; a test must neither inherit nor leave one."""
    usage._tallies.clear()
    yield
    usage._tallies.clear()


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
