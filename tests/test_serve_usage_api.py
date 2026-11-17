"""``GET /api/projects/{id}/usage`` — a study's LLM use, priced (docs/design-llm-usage.md).

Through the real app and route: ledger rows from any process, this server's
jobs in flight, a pipeline run's progress line, the currency, the ETag a poller
leans on, and the shape the contract fixture names.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from bristlenose.events import (
    KindEnum,
    RunProgressEvent,
    RunStartedEvent,
    _now_iso,
    append_event,
    events_path,
)
from bristlenose.llm import usage
from bristlenose.server.app import create_app
from bristlenose.server.models import Project
from tests.conftest import AuthTestClient

_SMOKE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_CONTRACT = json.loads(
    (Path(__file__).parent / "fixtures" / "usage-ledger-contract.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture()
def study(tmp_path: Path) -> tuple[AuthTestClient, Path]:
    """A served copy of the smoke study, and its output folder."""
    project_dir = tmp_path / "study"
    shutil.copytree(_SMOKE, project_dir)
    app = create_app(project_dir=project_dir, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        out = Path(db.get(Project, 1).output_dir)
    finally:
        db.close()
    return AuthTestClient(app), out


def _ledger(out: Path, *lines: str) -> None:
    run_dir = out / ".bristlenose"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / usage.USAGE_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _row(**kw: object) -> str:
    base: dict[str, object] = {
        "ts": "2026-11-10T09:00:00.000Z", "run_id": "r1", "kind": "run",
        "provider": "anthropic", "model": "claude-sonnet-5", "calls": 3,
        "input_tokens": 1_000_000, "output_tokens": 100_000,
        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
        "calls_without_usage": 0,
    }
    base.update(kw)
    base.setdefault("row_id", f"{base['run_id']}-{base['ts']}")
    return usage.UsageRow.model_validate(base).model_dump_json()


class TestShape:
    def test_the_response_has_the_contract_keys(self, study) -> None:
        client, out = study
        _ledger(out, _row())
        body = client.get("/api/projects/1/usage").json()
        api = _CONTRACT["api_fields"]
        assert list(body) == api["response"]
        assert list(body["rows"][0]["price"]) == api["price"]
        assert list(body["totals"][0]["price"]) == api["price"]

    def test_a_study_with_no_use_says_so(self, study) -> None:
        client, _ = study
        body = client.get("/api/projects/1/usage").json()
        assert (body["rows"], body["totals"], body["in_flight"]) == ([], [], [])

    def test_404_for_an_unknown_project(self, study) -> None:
        client, _ = study
        assert client.get("/api/projects/99/usage").status_code == 404

    def test_requires_the_bearer(self, study) -> None:
        from fastapi.testclient import TestClient

        client, _ = study
        bare = TestClient(client.app, base_url="http://127.0.0.1")
        assert bare.get("/api/projects/1/usage").status_code == 401


class TestMoney:
    def test_priced_in_usd_by_default(self, study) -> None:
        client, out = study
        _ledger(out, _row())  # sonnet-5: $2 in, $10 out per million
        body = client.get("/api/projects/1/usage").json()
        assert body["currency"] == "USD"
        assert body["totals"][0]["price"]["cost_usd"] == pytest.approx(3.0)
        assert body["totals"][0]["price"]["cost"] == pytest.approx(3.0)

    def test_converted_when_a_currency_is_asked_for(self, study) -> None:
        client, out = study
        _ledger(out, _row())
        body = client.get("/api/projects/1/usage?currency=gbp").json()
        rate = body["conversion"]["rate"]
        assert body["currency"] == "GBP" and body["conversion"]["as_of"]
        assert body["totals"][0]["price"]["cost"] == pytest.approx(3.0 * rate)
        assert body["rows"][0]["price"]["cost"] == pytest.approx(3.0 * rate)
        assert body["rows"][0]["price"]["cost_usd"] == pytest.approx(3.0)

    def test_an_unknown_currency_is_named_and_falls_back_to_usd(self, study) -> None:
        client, out = study
        _ledger(out, _row())
        body = client.get("/api/projects/1/usage?currency=XYZ").json()
        assert (body["currency"], body["currency_unavailable"]) == ("USD", "XYZ")
        assert body["totals"][0]["price"]["cost"] == pytest.approx(3.0)

    def test_unpriced_and_free_models_say_which(self, study) -> None:
        client, out = study
        _ledger(
            out,
            _row(run_id="a", provider="azure", model="my-deployment"),
            _row(run_id="b", provider="local", model="llama3.2:3b"),
        )
        status = {
            t["provider"]: (t["price"]["status"], t["price"]["cost_usd"])
            for t in client.get("/api/projects/1/usage").json()["totals"]
        }
        assert status == {"azure": ("unpriced", None), "local": ("free", 0.0)}

    def test_totals_add_the_rows(self, study) -> None:
        client, out = study
        _ledger(out, _row(run_id="a"), _row(run_id="b", ts="2026-11-11T09:00:00.000Z"))
        body = client.get("/api/projects/1/usage").json()
        (total,) = body["totals"]
        assert (total["jobs"], total["input_tokens"]) == (2, 2_000_000)
        assert total["price"]["cost_usd"] == pytest.approx(
            sum(r["price"]["cost_usd"] for r in body["rows"])
        )


class TestLive:
    def test_a_job_running_in_this_server_shows_before_it_ends(self, study) -> None:
        client, out = study
        usage.begin("job-1", out / ".bristlenose", "autocode")
        usage.note_call(run_id="job-1", provider="anthropic", model="claude-sonnet-5",
                        input_tokens=500, output_tokens=50)
        (live,) = client.get("/api/projects/1/usage").json()["in_flight"]
        assert (live["source"], live["kind"], live["input_tokens"]) == (
            "this_server", "autocode", 500,
        )
        assert live["price"]["status"] == "priced"

    def test_another_studys_job_is_not_shown(self, study, tmp_path: Path) -> None:
        client, _ = study
        usage.begin("elsewhere", tmp_path / "other" / ".bristlenose", "autocode")
        usage.note_call(run_id="elsewhere", provider="anthropic", model="m",
                        input_tokens=1, output_tokens=1)
        assert client.get("/api/projects/1/usage").json()["in_flight"] == []

    def test_a_pipeline_run_in_its_own_process_shows_from_its_progress_line(
        self, study, monkeypatch
    ) -> None:
        client, out = study
        now = _now_iso()
        ev_file = events_path(out)
        ev_file.parent.mkdir(parents=True, exist_ok=True)
        from bristlenose.events import Process

        append_event(ev_file, RunStartedEvent(
            ts=now, run_id="live", kind=KindEnum.RUN, started_at=now,
            process=Process(pid=1, start_time="x", hostname="h", user="u",
                            bristlenose_version="0", python_version="3", os="t"),
        ))
        append_event(ev_file, RunProgressEvent(
            ts=now, run_id="live", kind=KindEnum.RUN, started_at=now, stage="s09",
            usage_calls=4, usage_input_tokens=9_000, usage_output_tokens=900,
            usage_cache_read_input_tokens=0, usage_cache_creation_input_tokens=0,
        ))
        monkeypatch.setattr("bristlenose.run_lifecycle.live_run_id", lambda _o: "live")
        (live,) = client.get("/api/projects/1/usage").json()["in_flight"]
        assert live["as_of"] == now, "a pipeline's use is as of its last line, not now"
        assert (live["source"], live["run_id"], live["input_tokens"]) == (
            "pipeline_run", "live", 9_000,
        )
        assert live["price"] is None, "a progress line sums its models: no price"

    def test_a_dead_run_is_not_in_flight(self, study) -> None:
        """Its last progress line stays in the log; without a live owner it is
        history, not a run."""
        client, out = study
        now = _now_iso()
        ev_file = events_path(out)
        ev_file.parent.mkdir(parents=True, exist_ok=True)
        append_event(ev_file, RunProgressEvent(
            ts=now, run_id="dead", kind=KindEnum.RUN, started_at=now, usage_calls=1,
            usage_input_tokens=1, usage_output_tokens=1,
        ))
        assert client.get("/api/projects/1/usage").json()["in_flight"] == []


class TestPolling:
    def test_an_unchanged_answer_is_a_304(self, study) -> None:
        client, out = study
        _ledger(out, _row())
        first = client.get("/api/projects/1/usage")
        etag = first.headers["etag"]
        again = client.get("/api/projects/1/usage", headers={"If-None-Match": etag})
        assert again.status_code == 304

    def test_a_new_row_changes_the_etag(self, study) -> None:
        client, out = study
        _ledger(out, _row())
        etag = client.get("/api/projects/1/usage").headers["etag"]
        _ledger(out, _row(), _row(run_id="r2"))
        fresh = client.get("/api/projects/1/usage", headers={"If-None-Match": etag})
        assert fresh.status_code == 200 and fresh.headers["etag"] != etag

    def test_a_running_job_changes_the_etag_as_it_spends(self, study) -> None:
        client, out = study
        usage.begin("job", out / ".bristlenose", "chat_lens")
        usage.note_call(run_id="job", provider="anthropic", model="claude-sonnet-5",
                        input_tokens=1, output_tokens=1)
        etag = client.get("/api/projects/1/usage").headers["etag"]
        usage.note_call(run_id="job", provider="anthropic", model="claude-sonnet-5",
                        input_tokens=1, output_tokens=1)
        assert client.get(
            "/api/projects/1/usage", headers={"If-None-Match": etag}
        ).status_code == 200


class TestTheLiveRunIsTheOneThatHoldsTheStudy:
    """Review, 17 Nov 2026: the PID file is written before `run_started`, a
    dead run's lines stay in the log, and a line from a newer or older
    Bristlenose may not parse."""

    def _log(self, out: Path, *events) -> None:
        ev_file = events_path(out)
        ev_file.parent.mkdir(parents=True, exist_ok=True)
        for ev in events:
            append_event(ev_file, ev)

    def _progress(self, run_id: str, calls: int) -> RunProgressEvent:
        now = _now_iso()
        return RunProgressEvent(ts=now, run_id=run_id, kind=KindEnum.RUN, started_at=now,
                                usage_calls=calls, usage_input_tokens=calls * 100,
                                usage_output_tokens=calls)

    def test_a_dead_runs_last_line_is_not_the_live_runs(self, study, monkeypatch) -> None:
        client, out = study
        self._log(out, self._progress("dead", 9))
        monkeypatch.setattr("bristlenose.run_lifecycle.live_run_id", lambda _o: "new")
        assert client.get("/api/projects/1/usage").json()["in_flight"] == []

    def test_a_line_that_will_not_parse_is_skipped_not_a_500(
        self, study, monkeypatch
    ) -> None:
        client, out = study
        self._log(out, self._progress("live", 2))
        with events_path(out).open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "run_progress", "run_id": "live",
                                "kind": "a-kind-from-the-future"}) + "\n")
        monkeypatch.setattr("bristlenose.run_lifecycle.live_run_id", lambda _o: "live")
        r = client.get("/api/projects/1/usage")
        assert r.status_code == 200
        (live,) = r.json()["in_flight"]
        assert live["calls"] == 2, "the newest readable line"

    def test_unreadable_ledger_lines_are_counted_not_hidden(self, study) -> None:
        client, out = study
        _ledger(out, _row(), '{"schema_version": 1, "torn', '{"not": "a row"}')
        body = client.get("/api/projects/1/usage").json()
        assert (len(body["rows"]), body["rows_unreadable"]) == (1, 2)

    def test_rows_carry_their_id(self, study) -> None:
        client, out = study
        _ledger(out, _row())
        assert client.get("/api/projects/1/usage").json()["rows"][0]["row_id"]
