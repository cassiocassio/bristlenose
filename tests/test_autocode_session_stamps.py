"""AutoCode per-session stamps (RE#66, decisions #60–#67, 22 Oct 2026).

A session counts as coded by a codebook only when every one of its quotes was
sent in a batch that answered. Until then it is owed, and the next re-apply (a
finished run's, or the catch-up on switching the codebook back on) codes its
quotes that have no proposal yet. Before this, one watermark per codebook
(``AutoCodeJob.completed_at``) said which sessions were done, and a pass where
some batches failed moved it past them for good.

No LLM is called: ``LLMClient`` is patched.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

import bristlenose.server.autocode as ac
from bristlenose.llm.structured import AutoCodeBatchResult, AutoCodeTagAssignment
from bristlenose.server.autocode import (
    reapply_active_frameworks,
    reapply_to_new_quotes,
    run_autocode_job,
)
from bristlenose.server.codebook import get_template
from bristlenose.server.db import Base, get_engine
from bristlenose.server.models import (
    AutoCodeJob,
    AutoCodeSessionStamp,
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    ProjectFrameworkState,
    ProposedTag,
    Quote,
    QuoteTag,
    Session,
    TagDefinition,
)

_EARLY = datetime(2019, 1, 1)
_LATER = datetime(2021, 1, 1)


def _result(n: int, confidence: float = 0.85) -> AutoCodeBatchResult:
    return AutoCodeBatchResult(assignments=[
        AutoCodeTagAssignment(
            quote_index=i, tag_name="user need", confidence=confidence, rationale="r",
        )
        for i in range(n)
    ])


def _settings() -> MagicMock:
    s = MagicMock()
    s.llm_provider = "anthropic"
    s.llm_model = "claude-sonnet-4-20250514"
    s.llm_concurrency = 1
    return s


class _LLM:
    """Patch LLMClient with ``analyze``; the prompt each call carried is kept."""

    def __init__(self, analyze: AsyncMock, tokens: tuple[int, int] = (0, 0)) -> None:
        self.analyze = analyze
        self.tokens = tokens

    def __enter__(self) -> _LLM:
        client = MagicMock()
        client.analyze = self.analyze
        client.tracker = MagicMock(input_tokens=self.tokens[0], output_tokens=self.tokens[1])
        self._p = patch("bristlenose.llm.client.LLMClient", return_value=client)
        self.client_cls = self._p.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._p.__exit__(*args)

    def prompts(self) -> list[str]:
        return [c.kwargs["user_prompt"] for c in self.analyze.await_args_list]


def _answer_unless(marker: str) -> AsyncMock:
    """Answers every batch, except one carrying ``marker``, which raises."""

    async def analyze(**kw: object) -> AutoCodeBatchResult:
        if marker in str(kw["user_prompt"]):
            raise RuntimeError("rate limited")
        return _result(ac.BATCH_SIZE)

    return AsyncMock(side_effect=analyze)


def _answer_all() -> AsyncMock:
    return AsyncMock(side_effect=lambda **_kw: _result(ac.BATCH_SIZE))


@pytest.fixture()
def factory():
    # The serve's own engine: foreign keys on, so a write against a deleted job
    # or session fails here as it would for a researcher.
    engine = get_engine("sqlite://")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine)
    db = maker()
    db.add(Project(id=1, name="P", slug="p", input_dir="/tmp/in", output_dir="/tmp/out"))
    db.flush()
    for name in ("garrett", "norman"):
        template = get_template(name)
        assert template is not None
        for g in template.groups:
            group = CodebookGroup(
                name=g.name, subtitle=g.subtitle, colour_set=g.colour_set,
                framework_id=name,
            )
            db.add(group)
            db.flush()
            db.add(ProjectCodebookGroup(project_id=1, codebook_group_id=group.id))
            for t in g.tags:
                db.add(TagDefinition(name=t.name, codebook_group_id=group.id))
    db.commit()
    db.close()
    return maker


@pytest.fixture(autouse=True)
def _two_per_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Two quotes per batch and two per session, so a batch is a session.
    monkeypatch.setattr(ac, "BATCH_SIZE", 2)


def _session(factory, sid: str, *, words: str = "ok", n: int = 2,
             imported: datetime = _LATER) -> None:
    db = factory()
    number = int(sid[1:])
    db.add(Session(project_id=1, session_id=sid, session_number=number,
                   first_imported_at=imported))
    for i in range(n):
        db.add(Quote(
            project_id=1, session_id=sid, participant_id="p1",
            start_timecode=float(number * 1000 + i * 10),
            end_timecode=float(number * 1000 + i * 10 + 5),
            text=f"{words} quote {sid}-{i}", quote_type="screen_specific",
            topic_label="Dashboard",
        ))
    db.commit()
    db.close()


def _job(factory, framework: str = "garrett") -> AutoCodeJob:
    db = factory()
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id=framework).one()
        db.expunge(job)
        return job
    finally:
        db.close()


def _first_apply(factory, analyze: AsyncMock, framework: str = "garrett") -> None:
    db = factory()
    db.add(AutoCodeJob(project_id=1, framework_id=framework, status="pending"))
    db.commit()
    db.close()
    with _LLM(analyze):
        asyncio.run(run_autocode_job(factory, 1, framework, _settings()))
    db = factory()
    job = db.query(AutoCodeJob).filter_by(framework_id=framework).one()
    job.applied_upper_threshold = 0.7
    db.commit()
    db.close()


def _stamped(factory, framework: str = "garrett") -> set[str]:
    db = factory()
    try:
        return {
            row[0]
            for row in db.query(Session.session_id)
            .join(AutoCodeSessionStamp, AutoCodeSessionStamp.session_id == Session.id)
            .join(AutoCodeJob, AutoCodeJob.id == AutoCodeSessionStamp.job_id)
            .filter(AutoCodeJob.framework_id == framework)
        }
    finally:
        db.close()


def _set_status(factory, status: str, framework: str = "garrett") -> None:
    db = factory()
    db.query(AutoCodeJob).filter_by(framework_id=framework).update({"status": status})
    db.commit()
    db.close()


def _switch_off(factory, framework: str) -> None:
    db = factory()
    db.add(ProjectFrameworkState(project_id=1, framework_id=framework, enabled=False))
    db.commit()
    db.close()


def _count(factory, model) -> int:  # type: ignore[no-untyped-def]
    db = factory()
    try:
        return db.query(model).count()
    finally:
        db.close()


class TestSessionStamps:
    def test_a_first_apply_stamps_the_sessions_it_coded(self, factory) -> None:
        _session(factory, "s1", imported=_EARLY)
        _session(factory, "s2", imported=_EARLY)
        _first_apply(factory, _answer_all())
        assert _stamped(factory) == {"s1", "s2"}

    def test_a_partial_re_apply_leaves_the_failed_sessions_owed(self, factory) -> None:
        """#66: a batch that failed moved the watermark past its session, so no
        later re-apply coded it."""
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        _session(factory, "s2")
        _session(factory, "s3", words="FAIL")

        with _LLM(_answer_unless("FAIL")):
            assert asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings())) == 2
        assert _stamped(factory) == {"s1", "s2"}

        with _LLM(_answer_all()) as llm:
            accepted = asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings()))
        assert accepted == 2
        assert len(llm.prompts()) == 1
        assert "FAIL quote s3-0" in llm.prompts()[0]
        assert _stamped(factory) == {"s1", "s2", "s3"}

    def test_a_partial_first_apply_leaves_its_failed_sessions_owed(self, factory) -> None:
        """#66: the first apply's failed batches were never revisited."""
        _session(factory, "s1", imported=_EARLY)
        _session(factory, "s2", words="FAIL", imported=_EARLY)
        _first_apply(factory, _answer_unless("FAIL"))
        assert _job(factory).status == "completed"
        assert _stamped(factory) == {"s1"}

        with _LLM(_answer_all()) as llm:
            accepted = asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings()))
        assert accepted == 2
        assert ["FAIL quote s2-0" in p for p in llm.prompts()] == [True]

    def test_a_coded_corpus_sends_nothing(self, factory) -> None:
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        with _LLM(_answer_all()) as llm:
            assert asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings())) == 0
        assert llm.prompts() == []

    def test_a_session_with_no_quotes_starts_no_catch_up(self, factory) -> None:
        """An unstamped session with nothing to code is not owed: a catch-up chip
        over it would say "Re-coded" over nothing."""
        from bristlenose.server.routes.data import _start_catch_ups

        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        _session(factory, "s2", n=0)
        db = factory()
        try:
            assert _start_catch_ups(db, 1, ["garrett"]) == []
        finally:
            db.close()


class TestStoppedCatchUp:
    def test_a_stopped_catch_up_keeps_what_answered(self, factory) -> None:
        """#60: a Stop kept nothing, so the batches already paid for were sent
        again. They are kept, and only what was never sent stays owed."""
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        _session(factory, "s2", n=4)  # two batches in one session
        _set_status(factory, "running")

        async def stop_then_answer(**_kw: object) -> AutoCodeBatchResult:
            _set_status(factory, "cancelled")
            return _result(2)

        with _LLM(AsyncMock(side_effect=stop_then_answer)) as llm:
            asyncio.run(reapply_to_new_quotes(
                factory, 1, "garrett", _settings(), track_status=True,
            ))
        assert len(llm.prompts()) == 1
        assert _job(factory).status == "cancelled"
        assert _count(factory, QuoteTag) == 2
        assert _stamped(factory) == {"s1"}  # s2 half done: still owed

        with _LLM(_answer_all()) as llm:
            assert asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings())) == 2
        assert len(llm.prompts()) == 1
        assert "s2-2" in llm.prompts()[0] and "s2-0" not in llm.prompts()[0]
        assert _stamped(factory) == {"s1", "s2"}


class TestRunClearsAFailedCatchUp:
    def _failed_catch_up(self, factory) -> None:
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        _session(factory, "s2")
        _session(factory, "s3", words="FAIL")
        _set_status(factory, "running")
        with _LLM(AsyncMock(side_effect=RuntimeError("credit balance is too low"))):
            asyncio.run(reapply_to_new_quotes(
                factory, 1, "garrett", _settings(), track_status=True,
            ))
        assert _job(factory).status == "failed"

    def test_a_run_that_codes_what_a_failed_catch_up_left_clears_it(self, factory) -> None:
        """#61: the run coded those sessions and the job still read failed."""
        self._failed_catch_up(factory)
        with _LLM(_answer_all()):
            asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings()))
        job = _job(factory)
        assert (job.status, job.error_message, job.failure_kind) == ("completed", "", "")

    def test_a_run_that_leaves_sessions_still_owed_keeps_the_failure(self, factory) -> None:
        self._failed_catch_up(factory)
        with _LLM(_answer_unless("FAIL")):
            asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings()))
        assert _job(factory).status == "failed"


    def test_a_run_that_codes_what_a_partial_first_apply_left_clears_it(
        self, factory,
    ) -> None:
        """A partial first apply is "completed" and carries its failure; a run
        that codes the sessions it left clears that too, not only a failed or
        stopped catch-up's (#61)."""
        _session(factory, "s1", imported=_EARLY)
        _session(factory, "s2", words="FAIL", imported=_EARLY)
        _first_apply(factory, _answer_unless("FAIL"))
        job = _job(factory)
        assert job.status == "completed" and job.error_message
        with _LLM(_answer_all()):
            asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings()))
        job = _job(factory)
        assert (job.status, job.error_message, job.failure_kind) == ("completed", "", "")


    def test_a_run_after_a_stop_that_coded_everything_clears_it(self, factory) -> None:
        """A Stop that lands while the last batch is out: everything answers and is
        stamped, the job reads "cancelled", and the next run, finding nothing
        owed, returned before clearing it, so it read "cancelled" for good."""
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        _session(factory, "s2")
        _set_status(factory, "running")

        async def stop_on_the_last(**_kw: object) -> AutoCodeBatchResult:
            _set_status(factory, "cancelled")
            return _result(2)

        with _LLM(AsyncMock(side_effect=stop_on_the_last)):
            asyncio.run(reapply_to_new_quotes(
                factory, 1, "garrett", _settings(), track_status=True,
            ))
        assert _job(factory).status == "cancelled"
        assert _stamped(factory) == {"s1", "s2"}
        with _LLM(_answer_all()) as llm:
            asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings()))
        assert llm.prompts() == []
        assert _job(factory).status == "completed"


class TestOffMeansOffDuringARun:
    def test_a_codebook_switched_off_before_its_turn_is_not_coded(self, factory) -> None:
        """#62: the run picked its codebooks when it started."""
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all(), "garrett")
        _first_apply(factory, _answer_all(), "norman")
        _session(factory, "s2")
        coded: list[str] = []

        async def fake(_f, _p, framework: str, _s, **_k) -> int:
            coded.append(framework)
            _switch_off(factory, "norman" if framework == "garrett" else "garrett")
            return 0

        with patch("bristlenose.server.autocode.reapply_to_new_quotes", fake):
            asyncio.run(reapply_active_frameworks(factory, 1, _settings()))
        assert len(coded) == 1

    def test_a_codebook_switched_off_mid_re_apply_stops_at_the_next_batch(
        self, factory,
    ) -> None:
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        _session(factory, "s2", n=4)

        async def off_then_answer(**_kw: object) -> AutoCodeBatchResult:
            _switch_off(factory, "garrett")
            return _result(2)

        with _LLM(AsyncMock(side_effect=off_then_answer)) as llm:
            assert asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings())) == 2
        assert len(llm.prompts()) == 1
        assert _stamped(factory) == {"s1"}


class TestReapplyWaitsOnlyOnItsOwnCatchUp:
    def test_a_codebook_without_a_live_catch_up_is_not_held_by_one_with(
        self, factory,
    ) -> None:
        """#67: the run's codebooks were re-applied in turn, and one with a live
        catch-up held every codebook after it until that catch-up ended."""
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all(), "garrett")
        _first_apply(factory, _answer_all(), "norman")
        _session(factory, "s2")
        order: list[str] = []

        async def scenario() -> None:
            release = asyncio.Event()

            async def catch_up() -> None:
                await release.wait()
                order.append("garrett catch-up ends")

            async def fake(_f, _p, framework: str, _s, **_k) -> int:
                order.append(f"{framework} re-applied")
                return 0

            live = asyncio.create_task(catch_up())
            with (
                patch.dict(ac._REAPPLY_IN_FLIGHT, {(1, "garrett"): live}),
                patch("bristlenose.server.autocode.reapply_to_new_quotes", fake),
            ):
                run = asyncio.create_task(reapply_active_frameworks(factory, 1, _settings()))
                for _ in range(10):
                    await asyncio.sleep(0)
                assert order == ["norman re-applied"]
                release.set()
                await run

        asyncio.run(scenario())
        assert order == ["norman re-applied", "garrett catch-up ends", "garrett re-applied"]


class TestRemovingWhatAStampPointsAt:
    def test_a_catch_up_whose_codebook_is_uninstalled_stops_sending(self, factory) -> None:
        """Its per-batch check read a missing job as "not stopped" and paid for
        every batch left, all of it rolled back at the end."""
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        _session(factory, "s2", n=4)
        _set_status(factory, "running")
        job_id = _job(factory).id

        async def uninstall_then_answer(**_kw: object) -> AutoCodeBatchResult:
            db = factory()
            ac.delete_jobs(db, [job_id])
            db.commit()
            db.close()
            return _result(2)

        with _LLM(AsyncMock(side_effect=uninstall_then_answer)) as llm:
            asyncio.run(reapply_to_new_quotes(
                factory, 1, "garrett", _settings(), track_status=True,
            ))
        assert len(llm.prompts()) == 1

    def test_a_run_whose_codebook_is_removed_stops_sending(self, factory) -> None:
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        _session(factory, "s2", n=4)

        async def unlink_then_answer(**_kw: object) -> AutoCodeBatchResult:
            db = factory()
            group_ids = [g.id for g in db.query(CodebookGroup).filter_by(framework_id="garrett")]
            db.query(ProjectCodebookGroup).filter(
                ProjectCodebookGroup.codebook_group_id.in_(group_ids)
            ).delete(synchronize_session=False)
            db.commit()
            db.close()
            return _result(2)

        with _LLM(AsyncMock(side_effect=unlink_then_answer)) as llm:
            asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings()))
        assert len(llm.prompts()) == 1

    def test_an_uninstall_mid_re_apply_writes_nothing_and_fails_nothing(
        self, factory, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An uninstall deletes the job while a re-apply codes: its finishing
        UPDATE touches no row, which read as a Stop, and the Stop's commit of
        proposals and stamps against the deleted job failed on the foreign key
        and was logged as a failed re-apply."""
        _session(factory, "s1", imported=_EARLY)
        _first_apply(factory, _answer_all())
        _session(factory, "s2")
        job_id = _job(factory).id

        async def uninstall_then_answer(**_kw: object) -> AutoCodeBatchResult:
            db = factory()
            ac.delete_jobs(db, [job_id])
            db.commit()
            db.close()
            return _result(2)

        with _LLM(AsyncMock(side_effect=uninstall_then_answer)):
            assert asyncio.run(reapply_to_new_quotes(factory, 1, "garrett", _settings())) == 0
        assert "Re-apply failed" not in caplog.text
        assert _count(factory, ProposedTag) == 0
        assert _count(factory, AutoCodeSessionStamp) == 0
        assert _count(factory, QuoteTag) == 0



def _app(factory):  # type: ignore[no-untyped-def]
    """The AutoCode routes over ``factory``, refusals answered as the serve does."""
    from fastapi import FastAPI

    from bristlenose.server.refusal import RefusalError, refusal_handler
    from bristlenose.server.routes.autocode import router

    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(RefusalError, refusal_handler)
    app.state.db_factory = factory
    app.state.project_dir = None
    return app


def _apply(factory, analyze: AsyncMock, tokens: tuple[int, int] = (0, 0)) -> _LLM:
    """Press Apply: the real route, then the job it spawns, with the LLM mocked."""
    from fastapi.testclient import TestClient

    app = _app(factory)
    settings = _settings()
    settings.anthropic_api_key = "test-key"
    spawned: list[object] = []

    def keep(coro: object) -> MagicMock:
        spawned.append(coro)
        return MagicMock()

    with (
        patch("bristlenose.server.routes.autocode.load_settings", return_value=settings),
        patch("bristlenose.server.routes.autocode.asyncio.create_task", side_effect=keep),
    ):
        resp = TestClient(app).post("/api/projects/1/autocode/garrett")
    assert resp.status_code == 200, resp.text
    assert len(spawned) == 1
    with _LLM(analyze, tokens) as llm:
        asyncio.run(spawned[0])  # type: ignore[arg-type]
    return llm


def _stopped_first_apply(factory, stop_on: str, tokens: tuple[int, int] = (0, 0),
                         tagged: int = 1) -> None:
    """A first apply whose Stop lands while the batch carrying ``stop_on`` codes:
    that batch answers (tagging its first ``tagged`` quotes), the next is never
    sent."""
    db = factory()
    db.add(AutoCodeJob(project_id=1, framework_id="garrett", status="pending"))
    db.commit()
    db.close()

    async def analyze(**kw: object) -> AutoCodeBatchResult:
        if stop_on in str(kw["user_prompt"]):
            _set_status(factory, "cancelled")
            return _result(tagged)
        return _result(2)

    with _LLM(AsyncMock(side_effect=analyze), tokens):
        asyncio.run(run_autocode_job(factory, 1, "garrett", _settings()))
    job = _job(factory)
    assert (job.status, job.completed_at) == ("cancelled", None)


def _proposals(factory) -> dict[str, str]:
    """``{quote text tail: proposal status}`` on the garrett job."""
    db = factory()
    try:
        return {
            text.split(" quote ")[1]: status
            for status, text in db.query(ProposedTag.status, Quote.text)
            .join(Quote, Quote.id == ProposedTag.quote_id)
        }
    finally:
        db.close()


def _review(factory, decisions: dict[str, str]) -> None:
    """The researcher's review of a stopped apply's proposals (an old release
    showed them; migration 022 un-applied such a job)."""
    db = factory()
    for p, text in db.query(ProposedTag, Quote.text).join(Quote, Quote.id == ProposedTag.quote_id):
        status = decisions.get(text.split(" quote ")[1])
        if status is None:
            continue
        p.status = status
        if status == "accepted":
            db.add(QuoteTag(quote_id=p.quote_id, tag_definition_id=p.tag_definition_id,
                            source="autocode"))
    db.commit()
    db.close()


class TestApplyKeepsANeverAppliedJobsWork:
    """#127: Apply on a stopped or failed first apply deleted its proposals and
    stamps and sent the whole corpus again, so the coded half was paid for twice
    and the tags the researcher had denied came back pending."""

    @pytest.mark.parametrize("status", ["cancelled", "failed"])
    def test_a_stopped_first_apply_keeps_its_work(self, factory, status: str) -> None:
        for sid in ("s1", "s2", "s3"):
            _session(factory, sid)
        _stopped_first_apply(factory, stop_on="s2-0", tokens=(100, 10))
        _review(factory, {"s1-0": "denied", "s1-1": "accepted"})
        db = factory()
        db.query(AutoCodeJob).update({
            "status": status, "error_message": "boom", "failure_kind": "rate_limited",
            "started_at": datetime(2020, 1, 1),
        })
        db.commit()
        db.close()
        job_id = _job(factory).id
        assert _stamped(factory) == {"s1", "s2"}

        llm = _apply(factory, _answer_all(), tokens=(30, 3))

        # Only s3 was sent: s1 and s2 were coded, s2-1 left untagged in a coded
        # session (the stamp is the cost gate).
        assert len(llm.prompts()) == 1
        assert "s3-0" in llm.prompts()[0] and "s3-1" in llm.prompts()[0]
        assert "s1-" not in llm.prompts()[0] and "s2-" not in llm.prompts()[0]
        assert _proposals(factory) == {
            "s1-0": "denied", "s1-1": "accepted", "s2-0": "pending",
            "s3-0": "pending", "s3-1": "pending",
        }
        assert _count(factory, QuoteTag) == 1
        assert _stamped(factory) == {"s1", "s2", "s3"}
        job = _job(factory)
        assert job.id == job_id
        assert (job.status, job.error_message, job.failure_kind) == ("completed", "", "")
        assert job.completed_at is not None
        assert job.started_at > datetime(2020, 1, 1)
        assert (job.total_quotes, job.processed_quotes, job.proposed_count) == (6, 6, 5)
        assert (job.input_tokens, job.output_tokens) == (130, 13)

    def test_a_half_coded_session_sends_only_its_rest(self, factory) -> None:
        _session(factory, "s1", n=4)  # two batches in one session
        _stopped_first_apply(factory, stop_on="s1-0", tagged=2)
        assert _stamped(factory) == set()

        llm = _apply(factory, _answer_all())

        assert len(llm.prompts()) == 1
        assert "s1-2" in llm.prompts()[0] and "s1-0" not in llm.prompts()[0]
        assert _stamped(factory) == {"s1"}
        assert _job(factory).processed_quotes == _job(factory).total_quotes == 4

    def test_a_fully_proposed_corpus_completes_without_a_call(self, factory) -> None:
        """The Stop landed on the last batch; and, as migration 022 leaves an
        old stopped first apply, no stamps: proposed quotes are coded all the
        same, and their sessions are stamped now."""
        _session(factory, "s1")
        _session(factory, "s2")
        _stopped_first_apply(factory, stop_on="s2-0", tagged=2)
        db = factory()
        db.query(AutoCodeSessionStamp).delete()
        db.commit()
        db.close()

        llm = _apply(factory, _answer_all())

        assert llm.client_cls.call_count == 0
        assert llm.prompts() == []
        assert _stamped(factory) == {"s1", "s2"}
        job = _job(factory)
        assert job.status == "completed" and job.completed_at is not None
        assert (job.total_quotes, job.processed_quotes, job.proposed_count) == (4, 4, 4)

    def test_proposed_quotes_are_skipped_without_a_stamp(self, factory) -> None:
        """Migration 022 un-applies an old stopped first apply before its backfill,
        so its sessions carry no stamp: what has a proposal is still not sent,
        and a session all of whose quotes have one is stamped by this pass."""
        _session(factory, "s1")
        _session(factory, "s2")
        _stopped_first_apply(factory, stop_on="s1-0", tagged=2)
        _review(factory, {"s1-0": "denied"})
        db = factory()
        db.query(AutoCodeSessionStamp).delete()
        db.commit()
        db.close()

        llm = _apply(factory, _answer_all())

        assert len(llm.prompts()) == 1
        assert "s2-0" in llm.prompts()[0] and "s1-" not in llm.prompts()[0]
        assert _proposals(factory)["s1-0"] == "denied"
        assert _stamped(factory) == {"s1", "s2"}

    def test_a_failed_job_with_nothing_kept_codes_everything(self, factory) -> None:
        _session(factory, "s1")
        _session(factory, "s2")
        db = factory()
        db.add(AutoCodeJob(project_id=1, framework_id="garrett", status="failed"))
        db.commit()
        db.close()

        llm = _apply(factory, _answer_all())

        assert len(llm.prompts()) == 2
        assert _stamped(factory) == {"s1", "s2"}
        assert _job(factory).status == "completed"

    def test_a_retry_that_fails_keeps_the_earlier_work(self, factory) -> None:
        for sid in ("s1", "s2", "s3"):
            _session(factory, sid)
        _stopped_first_apply(factory, stop_on="s2-0")
        _review(factory, {"s1-0": "denied"})

        _apply(factory, AsyncMock(side_effect=RuntimeError("credit balance is too low")))

        job = _job(factory)
        assert (job.status, job.completed_at) == ("failed", None)
        assert job.failure_kind != ""
        assert _proposals(factory) == {"s1-0": "denied", "s1-1": "pending", "s2-0": "pending"}
        assert _stamped(factory) == {"s1", "s2"}

        # And the next Apply still sends only s3.
        llm = _apply(factory, _answer_all())
        assert len(llm.prompts()) == 1 and "s3-0" in llm.prompts()[0]
        assert _job(factory).status == "completed"


class TestApplyWaitsForAStoppedRunner:
    """#127 review: a Stop sets the row "cancelled" at once, but the batch already
    sent still answers. Apply in that moment started a second runner on the same
    row: both sent the same quotes, and the loser's collision marked it failed."""

    def test_apply_is_refused_while_the_stopped_runner_still_runs(self, factory) -> None:
        from fastapi.testclient import TestClient

        from bristlenose.server.routes import autocode as route

        _session(factory, "s1")
        _stopped_first_apply(factory, stop_on="s1-0")
        app = _app(factory)
        still_running = MagicMock()
        still_running.done.return_value = False
        settings = _settings()
        settings.anthropic_api_key = "test-key"
        with (
            patch.dict(route._AUTOCODE_LIVE, {(1, "garrett"): still_running}),
            patch("bristlenose.server.routes.autocode.load_settings", return_value=settings),
            patch("bristlenose.server.routes.autocode.asyncio.create_task") as spawn,
        ):
            resp = TestClient(app).post("/api/projects/1/autocode/garrett")
        assert resp.status_code == 409
        assert resp.json()["reason"] == "already_running"
        spawn.assert_not_called()
        assert _job(factory).status == "cancelled"

    def test_the_runner_is_live_until_it_ends(self, factory) -> None:
        from bristlenose.server.routes import autocode as route

        _session(factory, "s1")
        with patch.dict(route._AUTOCODE_LIVE, clear=True):
            _apply(factory, _answer_all())
            task = route._AUTOCODE_LIVE[(1, "garrett")]
            forget = [c.args[0] for c in task.add_done_callback.call_args_list]
            for callback in forget:
                callback(task)
            assert (1, "garrett") not in route._AUTOCODE_LIVE

    def test_a_stop_while_nothing_is_left_to_send_stands(self, factory) -> None:
        _session(factory, "s1")
        _stopped_first_apply(factory, stop_on="s1-0", tagged=2)
        real = ac._session_pks

        def stop_meanwhile(*args: object) -> list[int]:
            _set_status(factory, "cancelled")
            return real(*args)  # type: ignore[arg-type]

        with patch.object(ac, "_session_pks", side_effect=stop_meanwhile):
            _apply(factory, _answer_all())
        job = _job(factory)
        assert (job.status, job.completed_at) == ("cancelled", None)
