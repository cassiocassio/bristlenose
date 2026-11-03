"""A quote that counts again is coded by itself (ruling 4, 30 Oct 2026).

Hide a quote, Apply a codebook, unhide the quote: a proposal appears without the
researcher doing anything, accepted at the cutoff the Apply stored, and the quote
goes on the codebook's register of sent quotes. Driven through the real routes of a
real app (the Quotes lens's own PATCH), with the model mocked and the debounce
shrunk to a fraction of a second.

``with client:`` runs the app's event loop for the length of the block; without it
a timer the route armed would die with the request (server/CLAUDE.md).
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import bristlenose.server.autocode_catch_up as cu
from bristlenose.llm.structured import AutoCodeBatchResult, AutoCodeTagAssignment
from bristlenose.server.app import create_app
from bristlenose.server.autocode import run_autocode_job
from bristlenose.server.codebook import get_template
from bristlenose.server.grounding import quote_dom_id
from bristlenose.server.models import (
    AutoCodeJob,
    AutoCodeSentQuote,
    ProposedTag,
    Quote,
    QuoteState,
    QuoteTag,
)
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_P = "/api/projects/1"
_TITLES = {fw: get_template(fw).title for fw in ("garrett", "norman")}  # type: ignore[union-attr]


class _Model:
    """The model: tags every quote it is sent as "user need" at ``confidence``,
    and keeps what each call carried. ``fail`` makes it raise instead."""

    def __init__(self, confidence: float = 0.85) -> None:
        self.confidence = confidence
        self.fail: str | None = None
        #: With ``fail``, only the calls whose prompt carries this (a codebook's title).
        self.fail_only: str | None = None
        self.prompts: list[str] = []

    async def analyze(self, **kw: Any) -> AutoCodeBatchResult:
        prompt = str(kw["user_prompt"])
        self.prompts.append(prompt)
        if self.fail is not None and (self.fail_only is None or self.fail_only in prompt):
            raise RuntimeError(self.fail)
        n = len(re.findall(r"^\d+\. \[", prompt, re.M))
        tag = "user need"  # garrett's; another codebook is answered in its own first tag
        for fw, title in _TITLES.items():
            if fw != "garrett" and title in prompt:
                tag = get_template(fw).groups[0].tags[0].name  # type: ignore[union-attr]
        return AutoCodeBatchResult(assignments=[
            AutoCodeTagAssignment(
                quote_index=i, tag_name=tag, confidence=self.confidence, rationale="r",
            )
            for i in range(n)
        ])

    def batch_sizes(self, codebook: str | None = None) -> list[int]:
        return [
            len(re.findall(r"^\d+\. \[", p, re.M))
            for p in self.prompts
            if codebook is None or _TITLES[codebook] in p
        ]

    def __enter__(self) -> _Model:
        client = MagicMock()
        client.analyze = self.analyze
        client.tracker = MagicMock(input_tokens=0, output_tokens=0)
        self._patch = patch("bristlenose.llm.client.LLMClient", return_value=client)
        self._patch.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._patch.__exit__(*args)


def _settings(key: str = "test-key") -> MagicMock:
    s = MagicMock()
    s.llm_provider = "anthropic"
    s.llm_model = "claude-sonnet-4-20250514"
    s.llm_concurrency = 1
    s.anthropic_api_key = key
    return s


@pytest.fixture(autouse=True)
def _fast_debounce(monkeypatch: pytest.MonkeyPatch) -> Any:
    import bristlenose.server.autocode as ac

    def clear() -> None:
        # Module state of the one loop a serve has; each test here has its own, and
        # a task a closed loop left unfinished would read as "coding" for ever.
        cu.forget_everything()
        ac._REAPPLY_IN_FLIGHT.clear()

    clear()
    monkeypatch.setattr(cu, "DEBOUNCE_S", 0.2)
    monkeypatch.setattr(cu, "CAP_S", 5.0)
    yield
    clear()


def _app(tmp_path: Path, frameworks: tuple[str, ...] = ("garrett",)) -> tuple[Any, AuthTestClient]:
    proj = tmp_path / "proj"
    shutil.copytree(_FIXTURE_DIR, proj)
    # A file, not memory: an in-memory database is one connection shared by every
    # thread, and a test that reads while the serve's loop writes would roll its
    # transaction back.
    app = create_app(project_dir=proj, dev=True, db_url=f"sqlite:///{tmp_path / 'bn.db'}")
    app.state.settings = _settings()
    client = AuthTestClient(app)
    for fw in frameworks:
        r = client.post(f"{_P}/codebook/import-template", json={"template_id": fw})
        assert r.status_code == 200, r.text
    return app, client


def _file_client(project: Path, tmp_path: Path) -> AuthTestClient:
    """A client over a database file (see ``_app``) for a project built elsewhere."""
    return AuthTestClient(
        create_app(project_dir=project, dev=True, db_url=f"sqlite:///{tmp_path / 'bn.db'}")
    )


def _more_quotes(app: Any, n: int) -> None:
    """``n`` more quotes in session s1 (for a burst)."""
    db = app.state.db_factory()
    try:
        for i in range(n):
            db.add(Quote(
                project_id=1, session_id="s1", participant_id="p1",
                start_timecode=1000.0 + i, end_timecode=1000.5 + i,
                text=f"burst quote {i}", quote_type="screen_specific", topic_label="T",
            ))
        db.commit()
    finally:
        db.close()


def _dom(app: Any, text: str | None = None, *, like: str | None = None) -> list[str]:
    db = app.state.db_factory()
    try:
        rows = db.query(Quote).order_by(Quote.id).all()
        return [
            quote_dom_id(q.participant_id, q.start_timecode, q.ordinal)
            for q in rows
            if (text is None and like is None)
            or (text is not None and q.text == text)
            or (like is not None and q.text.startswith(like))
        ]
    finally:
        db.close()


def _apply(
    app: Any, model: _Model, framework: str, *, cutoff: float = 0.7,
    lower: float | None = None,
) -> None:
    """Apply a codebook as the route does (a pending job, then the runner), and
    store the cutoffs the review would have: ``accept-all`` writes the upper,
    ``deny-all`` the lower (not stored at all when ``lower`` is None)."""
    factory = app.state.db_factory
    db = factory()
    db.add(AutoCodeJob(project_id=1, framework_id=framework, status="pending"))
    db.commit()
    db.close()
    import asyncio

    with model:
        asyncio.run(run_autocode_job(factory, 1, framework, app.state.settings))
    db = factory()
    db.query(AutoCodeJob).filter_by(framework_id=framework).update(
        {"applied_upper_threshold": cutoff, "applied_lower_threshold": lower}
    )
    db.commit()
    db.close()


def _hide(client: AuthTestClient, doms: list[str], on: bool) -> dict[str, Any]:
    r = client.patch(f"{_P}/hidden", json=dict.fromkeys(doms, on))
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    body.setdefault("catchUp", [])  # named only when there is one
    return body


def _hide_in_db(app: Any, doms: list[str]) -> None:
    db = app.state.db_factory()
    try:
        for q in db.query(Quote):
            if quote_dom_id(q.participant_id, q.start_timecode, q.ordinal) in doms:
                db.add(QuoteState(quote_id=q.id, is_hidden=True))
        db.commit()
    finally:
        db.close()


def _wait(check: Any, what: str, seconds: float = 8.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    raise AssertionError(f"waited {seconds:.0f}s for {what}")


def _tag_sources(app: Any, text: str) -> list[str]:
    db = app.state.db_factory()
    try:
        return sorted(
            source for (source,) in db.query(QuoteTag.source)
            .join(Quote, Quote.id == QuoteTag.quote_id)
            .filter(Quote.text == text, QuoteTag.source != "pipeline")  # not the sentiment tags
        )
    finally:
        db.close()


def _quiet(seconds: float = 0.8) -> None:
    time.sleep(seconds)


def _first_quote_text(app: Any) -> str:
    db = app.state.db_factory()
    try:
        return str(db.query(Quote).order_by(Quote.id).first().text)  # type: ignore[union-attr]
    finally:
        db.close()


class TestHideApplyUnhide:
    def test_the_quote_is_coded_by_itself_at_the_stored_cutoff(self, tmp_path: Path) -> None:
        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model(confidence=0.85)
        _apply(app, model, "garrett", cutoff=0.7)
        sent_at_apply = len(model.prompts)
        assert text not in "".join(model.prompts), "a hidden quote is never sent while hidden"

        with model, client:
            answer = _hide(client, dom, False)
            assert [(c["framework_id"], c["title"]) for c in answer["catchUp"]] == [
                ("garrett", _TITLES["garrett"])
            ]
            assert answer["catchUp"][0]["started_at"], "the job's start now, for the page to compare"
            _wait(lambda: "autocode" in _tag_sources(app, text), "the tag to appear")

        later = model.prompts[sent_at_apply:]
        assert len(later) == 1 and text in later[0], "one call, carrying the unhidden quote"
        db = app.state.db_factory()
        try:
            proposal = (
                db.query(ProposedTag).join(Quote, Quote.id == ProposedTag.quote_id)
                .filter(Quote.text == text).one()
            )
            assert (proposal.status, proposal.confidence) == ("accepted", 0.85)
            job = db.query(AutoCodeJob).filter_by(framework_id="garrett").one()
            assert job.status == "completed" and job.failure_kind == ""
            assert db.query(AutoCodeSentQuote).filter_by(
                job_id=job.id, quote_id=proposal.quote_id
            ).count() == 1
        finally:
            db.close()

    def test_the_whole_map_write_triggers_it_too(self, tmp_path: Path) -> None:
        """``PUT /hidden`` replaces the map; a quote it leaves out is unhidden."""
        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        with model, client:
            assert client.put(f"{_P}/hidden", json={}).status_code == 200
            _wait(lambda: "autocode" in _tag_sources(app, text), "the tag to appear")

    @pytest.mark.parametrize(
        ("confidence", "lower", "expected"),
        [
            (0.90, 0.3, "accepted"),
            (0.50, 0.3, "pending"),   # between the lines: the review's to decide
            (0.50, None, "pending"),  # no lower stored: the dialog's 0.30
            (0.20, 0.3, "denied"),
            (0.20, None, "denied"),
            (0.30, 0.3, "pending"),   # on the lower line: the dialog denies strictly below
        ],
    )
    def test_the_late_quote_lands_in_the_band_the_review_would_give_it(
        self, tmp_path: Path, confidence: float, lower: float | None, expected: str
    ) -> None:
        """The same three bands as the review dialog, from the unhide's own pass: only
        the accepted proposal tags the quote; a pending one waits, undated, for the
        review, and a denied one is closed."""
        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model(confidence=confidence)
        _apply(app, model, "garrett", cutoff=0.7, lower=lower)
        applied = len(model.prompts)
        with model, client:
            _hide(client, dom, False)
            _wait(lambda: len(model.prompts) == applied + 1, "the catch-up call")
            _quiet()
        assert _tag_sources(app, text) == (["autocode"] if expected == "accepted" else [])
        db = app.state.db_factory()
        try:
            rows = db.query(ProposedTag.status, ProposedTag.reviewed_at).join(
                Quote, Quote.id == ProposedTag.quote_id).filter(Quote.text == text).all()
        finally:
            db.close()
        assert [r[0] for r in rows] == [expected]
        assert (rows[0][1] is None) == (expected == "pending")

    def test_a_human_tag_on_the_quote_survives(self, tmp_path: Path) -> None:
        from bristlenose.server.models import TagDefinition

        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        db = app.state.db_factory()
        tag = db.query(TagDefinition).filter_by(name="user need").first()
        quote = db.query(Quote).filter_by(text=text).one()
        db.add(QuoteTag(quote_id=quote.id, tag_definition_id=tag.id, source="human"))
        db.commit()
        db.close()
        applied = len(model.prompts)
        with model, client:
            _hide(client, dom, False)
            _wait(lambda: len(model.prompts) == applied + 1, "the catch-up call")
            _quiet()
        assert _tag_sources(app, text) == ["human"]


class TestTheDebounce:
    def test_a_burst_of_thirty_unhides_is_one_pass_per_codebook_in_batches_of_25(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Thirty gestures, each its own request, under a wait no stall can outrun; then
        the last gesture is given the short wait. Under the 0.2 s window one request held
        for a quarter of a second (a loaded CI runner's commit) fired the timer inside
        the burst, and the gestures after it armed a second pass per codebook (CI, 2 Nov
        2026). That the wait restarts per gesture is ``test_each_gesture_restarts_the_wait``'s."""
        import bristlenose.server.autocode as ac

        monkeypatch.setattr(cu, "DEBOUNCE_S", 60.0)
        monkeypatch.setattr(cu, "CAP_S", 60.0)
        app, client = _app(tmp_path, ("garrett", "norman"))
        _more_quotes(app, 30)
        burst = _dom(app, like="burst quote")
        assert len(burst) == 30
        _hide_in_db(app, burst)
        model = _Model()
        _apply(app, model, "garrett")
        _apply(app, model, "norman")
        applied = len(model.prompts)

        passes: list[str] = []
        real = ac.reapply_to_new_quotes

        async def spy(db_factory: Any, project_id: int, framework_id: str, *a: Any, **k: Any):
            passes.append(framework_id)
            return await real(db_factory, project_id, framework_id, *a, **k)

        with model, client, patch("bristlenose.server.autocode.reapply_to_new_quotes", spy):
            for dom in burst:  # thirty gestures, each its own request
                named = _hide(client, [dom], False)["catchUp"]
            assert sorted(c["framework_id"] for c in named) == ["garrett", "norman"]
            monkeypatch.setattr(cu, "DEBOUNCE_S", 0.2)
            assert client.portal is not None  # ``with client:`` opened the loop's portal
            client.portal.call(cu._arm, app, 1)  # the last gesture again, with the short wait
            _wait(lambda: len(model.prompts) - applied >= 4, "both codebooks to code them")
            _quiet()

        assert sorted(passes) == ["garrett", "norman"], "one pass per codebook"
        later = _later(model, applied)
        assert later.batch_sizes("garrett") == [25, 5]
        assert later.batch_sizes("norman") == [25, 5]
        assert ac.BATCH_SIZE == 25

    def test_a_quote_hidden_again_during_the_wait_is_skipped_and_stays_owed(
        self, tmp_path: Path
    ) -> None:
        import bristlenose.server.autocode as ac

        app, client = _app(tmp_path)
        _more_quotes(app, 2)
        a, b = _dom(app, like="burst quote")
        _hide_in_db(app, [a, b])
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        with model, client:
            _hide(client, [a, b], False)
            _hide(client, [b], True)  # changed their mind inside the wait
            _wait(lambda: len(model.prompts) - applied == 1, "the pass")
            _quiet()
            assert "burst quote 0" in model.prompts[applied]
            assert "burst quote 1" not in model.prompts[applied]
            db = app.state.db_factory()
            try:
                job = db.query(AutoCodeJob).filter_by(framework_id="garrett").one()
                db.query(QuoteState).update({"is_hidden": False})
                db.commit()
                owed = [q.text for q in ac.owed_quotes(db, job)]
            finally:
                db.close()
            assert owed == ["burst quote 1"], "still owed, sent the moment it counts again"

    def test_each_gesture_restarts_the_wait(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each gesture cancels the wait the last one started and starts its own, so a burst
        is one call carrying all three. Pinned on the timers themselves, under a wait no stall
        can outrun, not on wall-clock gaps: three requests 0.35 s apart inside a 0.6 s window
        split into two calls whenever a loaded machine delayed one by a quarter second (CI,
        2 Nov 2026, the same class as the thirty-unhide test)."""
        monkeypatch.setattr(cu, "DEBOUNCE_S", 60.0)
        monkeypatch.setattr(cu, "CAP_S", 600.0)
        app, client = _app(tmp_path)
        _more_quotes(app, 3)
        doms = _dom(app, like="burst quote")
        _hide_in_db(app, doms)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        handles: list[Any] = []
        with model, client:
            for dom in doms:
                _hide(client, [dom], False)
                handle = cu._WAITS[1].handle
                assert handle is not None, "the gesture started a wait"
                if handles:
                    assert handles[-1].cancelled(), "the earlier wait was cancelled"
                    assert handle is not handles[-1], "and a new one started"
                handles.append(handle)
            assert len(model.prompts) == applied, "nothing fired inside the burst"
            monkeypatch.setattr(cu, "DEBOUNCE_S", 0.2)
            assert client.portal is not None  # ``with client:`` opened the loop's portal
            client.portal.call(cu._arm, app, 1)  # the last gesture again, with the short wait
            _wait(lambda: len(model.prompts) > applied, "the pass")
            _quiet(1.2)
        assert model.batch_sizes()[applied:] == [3]

    def test_the_cap_stops_a_long_burst_pushing_the_pass_back_for_ever(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cu, "DEBOUNCE_S", 0.4)
        monkeypatch.setattr(cu, "CAP_S", 0.9)
        app, client = _app(tmp_path)
        _more_quotes(app, 20)
        doms = _dom(app, like="burst quote")
        _hide_in_db(app, doms)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        with model, client:
            for dom in doms:  # one every 0.15 s: 3 s of gestures, never a 0.4 s gap
                _hide(client, [dom], False)
                time.sleep(0.15)
                if len(model.prompts) > applied:
                    break
            assert len(model.prompts) > applied, "the cap fired while the gestures went on"
            _wait(lambda: len(model.prompts) - applied >= 1, "the first pass")
            first = model.prompts[applied]
            assert len(re.findall(r"^\d+\. \[", first, re.M)) < 20


def _later(model: _Model, applied: int) -> _Model:
    later = _Model()
    later.prompts = model.prompts[applied:]
    return later


class TestNothingSpendsAtOpen:
    def test_owed_quotes_alone_start_no_catch_up(self, tmp_path: Path) -> None:
        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        db = app.state.db_factory()
        db.query(QuoteState).update({"is_hidden": False})  # owed now
        db.commit()
        db.close()
        applied = len(model.prompts)
        with model, client:
            client.get(f"{_P}/quotes")
            _quiet(1.0)
        assert len(model.prompts) == applied


class TestACodebookSwitchedOff:
    def test_it_leaves_the_quote_owed_until_it_is_switched_back_on(self, tmp_path: Path) -> None:
        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        with model, client:
            assert client.put(f"{_P}/framework-states", json={"garrett": False}).json()[
                "catchUp"] == []
            assert _hide(client, dom, False)["catchUp"] == []
            _quiet()
            assert len(model.prompts) == applied, "off means off"
            assert _tag_sources(app, text) == []

            on = client.put(f"{_P}/framework-states", json={"garrett": True}).json()
            assert on["catchUp"] == ["garrett"]
            _wait(lambda: "autocode" in _tag_sources(app, text), "the switch-on catch-up")


class TestWithoutAKey:
    def test_the_quote_stays_owed_and_nothing_is_tried_until_a_key_is_set(
        self, tmp_path: Path
    ) -> None:
        app, client = _app(tmp_path)
        _more_quotes(app, 6)
        doms = _dom(app, like="burst quote")
        _hide_in_db(app, doms)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        app.state.settings = _settings(key="")
        with model, client:
            for dom in doms[:5]:  # five unhides with no key
                assert _hide(client, [dom], False)["catchUp"] == []
            _quiet(1.0)
            assert len(model.prompts) == applied, "no call without a key"
            db = app.state.db_factory()
            try:
                job = db.query(AutoCodeJob).filter_by(framework_id="garrett").one()
                assert (job.status, job.failure_kind, job.error_message) == ("completed", "", "")
            finally:
                db.close()

            app.state.settings = _settings(key="test-key")  # the key arrives
            _hide(client, doms[5:], False)
            _wait(lambda: len(model.prompts) > applied, "one catch-up for the backlog")
            _quiet()
        assert model.batch_sizes()[applied:] == [6], "the whole backlog in one pass"


class TestSavingAKeyStartsIt:
    """The Mac restarts the serve when a key is saved; a write that found quotes owed and
    no key left word (``AWAITING_KEY``), and the next start with a key codes them (owner,
    1 Nov 2026). An ordinary start spends nothing."""

    @staticmethod
    def _marker(app: Any) -> Path:
        from bristlenose.output_paths import project_output_dir

        return project_output_dir(app.state.project_dir) / ".bristlenose" / cu.AWAITING_KEY

    @staticmethod
    def _restart(app: Any, tmp_path: Path, key: str) -> tuple[Any, AuthTestClient]:
        """A new serve over the same study and database, as the Mac's restart makes."""
        cu.forget_everything()
        again = create_app(
            project_dir=app.state.project_dir, dev=True, db_url=f"sqlite:///{tmp_path / 'bn.db'}",
        )
        again.state.settings = _settings(key=key)
        return again, AuthTestClient(again)

    def _owed_with_no_key(self, tmp_path: Path) -> tuple[Any, _Model, str, int]:
        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        app.state.settings = _settings(key="")
        with model, client:
            assert _hide(client, dom, False)["catchUp"] == []
        return app, model, text, applied

    def test_a_write_with_no_key_leaves_word(self, tmp_path: Path) -> None:
        app, _, _, _ = self._owed_with_no_key(tmp_path)
        assert self._marker(app).exists()

    def test_the_start_after_a_key_is_saved_codes_what_was_owed(self, tmp_path: Path) -> None:
        app, model, text, applied = self._owed_with_no_key(tmp_path)
        again, client = self._restart(app, tmp_path, key="test-key")
        with model, client:
            _wait(lambda: "autocode" in _tag_sources(again, text), "the owed quote to be coded")
        assert len(model.prompts) == applied + 1, "one call, for the one owed quote"
        assert not self._marker(app).exists(), "the word is used up"

    def test_a_start_with_no_key_keeps_the_word(self, tmp_path: Path) -> None:
        app, model, _, applied = self._owed_with_no_key(tmp_path)
        again, client = self._restart(app, tmp_path, key="")
        with model, client:
            _quiet(1.0)
        assert len(model.prompts) == applied, "no call without a key"
        assert self._marker(app).exists(), "waits for the start that has one"

    def test_an_ordinary_start_with_owed_quotes_and_no_word_spends_nothing(
        self, tmp_path: Path
    ) -> None:
        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        db = app.state.db_factory()  # unhidden outside the routes: owed, and no word left
        try:
            db.query(QuoteState).delete()
            db.commit()
        finally:
            db.close()
        assert not self._marker(app).exists()
        again, client = self._restart(app, tmp_path, key="test-key")
        with model, client:
            _quiet(1.0)
        assert len(model.prompts) == applied, "owed quotes alone spend nothing at start"

    def test_a_bad_key_that_is_replaced_starts_it_too(self, tmp_path: Path) -> None:
        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        model.fail = "api key not valid"
        with model, client:
            _hide(client, dom, False)
            _wait(lambda: self_job(app).status == "failed", "the failure to be recorded")
        assert self_job(app).failure_kind == "invalid_key"
        assert self._marker(app).exists(), "word is left for the start that has a better key"

        model.fail = None
        again, client2 = self._restart(app, tmp_path, key="a-better-key")
        with model, client2:
            _wait(lambda: "autocode" in _tag_sources(again, text), "the owed quote to be coded")
        assert len(model.prompts) == applied + 2, "the failed attempt, then the retry"
        assert not self._marker(app).exists()


class TestAKeyOrCreditFailure:
    def test_it_is_tried_once_then_not_again_until_the_provider_state_changes(
        self, tmp_path: Path
    ) -> None:
        app, client = _app(tmp_path)
        _more_quotes(app, 7)
        doms = _dom(app, like="burst quote")
        _hide_in_db(app, doms)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        model.fail = "api key not valid"
        with model, client:
            _hide(client, doms[:1], False)
            _wait(lambda: len(model.prompts) - applied == 1, "the one attempt")
            _wait(lambda: self_job(app).status == "failed", "the failure to be recorded")
            assert self_job(app).failure_kind == "invalid_key"

            for dom in doms[1:5]:  # four more unhides: no more attempts
                assert _hide(client, [dom], False)["catchUp"] == []
            _quiet(1.0)
            assert len(model.prompts) - applied == 1

            model.fail = None
            app.state.settings.llm_model = "claude-a-different-model"  # the state changed
            _hide(client, doms[5:], False)
            _wait(lambda: self_job(app).status == "completed", "the one catch-up")
            _quiet()
        assert len(model.prompts) - applied == 2, "one more attempt, not one per unhide"
        assert model.batch_sizes()[applied + 1:] == [7], "the whole backlog in it"

    def test_the_hold_lapses_after_a_while_for_one_attempt_and_is_set_again_if_it_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A key mended by ``bristlenose configure`` while a CLI serve runs changes
        nothing the serve can see: the hold is lifted by the clock, once, on the next
        trigger (no timer, nothing spent without one)."""
        assert 10 * 60 <= cu.HOLD_S <= 30 * 60, "about a quarter of an hour"
        now = [1000.0]
        monkeypatch.setattr(cu, "_clock", lambda: now[0])
        app, client = _app(tmp_path)
        _more_quotes(app, 6)
        doms = _dom(app, like="burst quote")
        _hide_in_db(app, doms)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)

        def attempts() -> int:
            return len(model.prompts) - applied

        def settled(n: int) -> None:
            _wait(lambda: attempts() == n and not cu._FIRING, f"attempt {n} to end")
            _wait(lambda: self_job(app).status in ("failed", "completed"), "the job to settle")

        model.fail = "api key not valid"
        with model, client:
            _hide(client, doms[:1], False)
            settled(1)
            assert self_job(app).failure_kind == "invalid_key"

            now[0] += cu.HOLD_S - 1  # inside the hold: nothing tried
            assert _hide(client, doms[1:2], False)["catchUp"] == []
            _quiet(0.5)
            assert attempts() == 1

            now[0] += 2  # past it: ONE attempt, for the whole backlog
            assert [c["framework_id"] for c in _hide(client, doms[2:3], False)["catchUp"]] == [
                "garrett"
            ]
            settled(2)
            assert self_job(app).failure_kind == "invalid_key"  # failed again

            # ... and held again for another full period from now.
            assert _hide(client, doms[3:4], False)["catchUp"] == []
            now[0] += cu.HOLD_S - 1
            assert _hide(client, doms[4:5], False)["catchUp"] == []
            _quiet(0.5)
            assert attempts() == 2

            model.fail = None  # the key is mended
            now[0] += 2
            _hide(client, doms[5:], False)
            settled(3)
            assert self_job(app).status == "completed"
            assert cu._BLOCKED == {}
        assert model.batch_sizes()[applied + 2:] == [6], "the whole backlog in the last"

    def test_the_hold_is_measured_on_a_clock_that_runs_while_the_mac_sleeps(self) -> None:
        """``time.monotonic`` stops with the lid closed on a Mac: a 15-minute hold set
        in the evening would still be running the next morning."""
        import time as _time

        assert cu._clock is _time.time

    def test_attempts_for_one_codebook_never_overlap(self, tmp_path: Path) -> None:
        """A second trigger that reaches ``_catch_up`` while another attempt for the same
        codebook is anywhere between its check and its re-arming waits for all of it
        (the ``live_reapply`` wait alone left a gap between a finished pass and the
        attempt's own continuation)."""
        import asyncio

        app, _client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        db = app.state.db_factory()
        db.query(QuoteState).delete()  # unhidden: the quote counts and is owed
        db.commit()
        db.close()

        async def go() -> None:
            lock = cu._LOCKS.setdefault((1, "garrett"), asyncio.Lock())
            await lock.acquire()  # another attempt for this codebook is in progress
            attempt = asyncio.ensure_future(cu._catch_up(app, 1, "garrett"))
            for _ in range(30):
                await asyncio.sleep(0.01)
            assert not attempt.done()
            assert len(model.prompts) == applied, "it must wait, not call the provider"
            lock.release()
            await attempt

        with model:
            asyncio.run(go())
        assert len(model.prompts) == applied + 1

    def test_a_credit_failure_is_held_the_same_way(self, tmp_path: Path) -> None:
        app, client = _app(tmp_path)
        _more_quotes(app, 2)
        doms = _dom(app, like="burst quote")
        _hide_in_db(app, doms)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        model.fail = "Your credit balance is too low to access the Anthropic API"
        with model, client:
            _hide(client, doms[:1], False)
            _wait(lambda: self_job(app).status == "failed", "the failure")
            assert self_job(app).failure_kind == "out_of_credit"
            assert _hide(client, doms[1:], False)["catchUp"] == []
            _quiet(0.8)
        assert len(model.prompts) - applied == 1

    def test_a_rate_limit_is_not_held(self, tmp_path: Path) -> None:
        """It passes: the next unhide may try again."""
        app, client = _app(tmp_path)
        _more_quotes(app, 2)
        doms = _dom(app, like="burst quote")
        _hide_in_db(app, doms)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        model.fail = "rate limit exceeded"
        with model, client:
            _hide(client, doms[:1], False)
            _wait(lambda: self_job(app).status == "failed", "the failure")
            assert self_job(app).failure_kind == "rate_limited"
            assert [c["framework_id"] for c in _hide(client, doms[1:], False)["catchUp"]] == [
                "garrett"
            ]
            _wait(lambda: len(model.prompts) - applied == 2, "the second attempt")
            _wait(lambda: self_job(app).status == "failed" and cu._BLOCKED == {}, "it to end")
            _quiet(0.3)


def self_job(app: Any) -> AutoCodeJob:
    db = app.state.db_factory()
    try:
        job = db.query(AutoCodeJob).filter_by(framework_id="garrett").one()
        db.expunge(job)
        return job
    finally:
        db.close()


class TestARecodeBackIn:
    """The speaker recoded as the moderator is not evidence, so AutoCode did not send
    their quotes; recoding them back in makes the quotes count again."""

    def test_the_quotes_are_coded_by_themselves(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _martin, _with_quotes

        client = _file_client(_with_quotes(tmp_path), tmp_path)
        app = client.app  # type: ignore[attr-defined]
        app.state.settings = _settings()
        assert client.post(
            f"{_P}/codebook/import-template", json={"template_id": "garrett"}
        ).status_code == 200
        r = client.put(f"{_P}/sessions/s1/speakers/p1",
                       json={"kind": "moderator", "person": _martin(client)})
        assert r.status_code == 200, r.text
        model = _Model()
        _apply(app, model, "garrett")
        assert "Quote from p1" not in "".join(model.prompts)
        applied = len(model.prompts)

        with model, client:
            back = client.put(f"{_P}/sessions/s1/speakers/p1",
                              json={"kind": "participant", "confirmed": True})
            assert back.status_code == 200, back.text
            assert [c["framework_id"] for c in back.json()["catchUp"]] == ["garrett"]
            _wait(lambda: "autocode" in _tag_sources(app, "Quote from p1"), "the tag to appear")
        assert len(model.prompts) - applied == 1
        assert "Quote from p1" in model.prompts[applied]


class TestAParagraphMovedBack:
    """A paragraph moved off its participant takes its quote out of the evidence
    (§K); undoing the move brings it back, and the quote is owed."""

    def test_undoing_the_move_codes_the_quote_by_itself(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _with_quotes

        client = _file_client(_with_quotes(tmp_path), tmp_path)
        app = client.app  # type: ignore[attr-defined]
        app.state.settings = _settings()
        assert client.post(
            f"{_P}/codebook/import-template", json={"template_id": "garrett"}
        ).status_code == 200
        moved = client.post(
            f"{_P}/transcripts/s1/reassign",
            json={"position": 1, "verify": "Thanks for having me, it is", "new": "moderator"},
        )
        assert moved.status_code == 200, moved.text
        model = _Model()
        _apply(app, model, "garrett")
        assert "Quote from p1" not in "".join(model.prompts), "moved off them: not evidence"
        applied = len(model.prompts)

        with model, client:
            undone = client.delete(f"{_P}/transcripts/s1/layout-edits/{moved.json()['id']}")
            assert undone.status_code == 200, undone.text
            assert [c["framework_id"] for c in undone.json()["catchUp"]] == ["garrett"]
            _wait(lambda: "autocode" in _tag_sources(app, "Quote from p1"), "the tag to appear")
        assert len(model.prompts) - applied == 1

    def test_moving_it_back_by_hand_does_too(self, tmp_path: Path) -> None:
        from tests.test_serve_participant_recode import _with_quotes

        client = _file_client(_with_quotes(tmp_path), tmp_path)
        app = client.app  # type: ignore[attr-defined]
        app.state.settings = _settings()
        assert client.post(
            f"{_P}/codebook/import-template", json={"template_id": "garrett"}
        ).status_code == 200
        words = "Thanks for having me, it is"
        away = client.post(f"{_P}/transcripts/s1/reassign",
                           json={"position": 1, "verify": words, "new": "moderator"})
        assert away.status_code == 200, away.text
        assert away.json()["catchUp"] == [], "moved away: nothing newly owed"
        model = _Model()
        _apply(app, model, "garrett")
        with model, client:
            back = client.post(f"{_P}/transcripts/s1/reassign",
                               json={"position": 1, "verify": words, "slot": "p1"})
            assert back.status_code == 200, back.text
            assert [c["framework_id"] for c in back.json()["catchUp"]] == ["garrett"]
            _wait(lambda: "autocode" in _tag_sources(app, "Quote from p1"), "the tag to appear")


class TestTheCodebooksTakeTurns:
    def test_one_failing_does_not_stop_the_next(self, tmp_path: Path) -> None:
        app, client = _app(tmp_path, ("garrett", "norman"))
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        _apply(app, model, "norman")
        model.fail, model.fail_only = "rate limit exceeded", _TITLES["garrett"]
        with model, client:
            _hide(client, dom, False)
            _wait(lambda: "autocode" in _tag_sources(app, text), "norman to code it")
        assert self_job(app).status == "failed"

    def test_one_that_cannot_start_does_not_stop_the_next_and_is_not_left_running(
        self, tmp_path: Path
    ) -> None:
        import bristlenose.server.routes.data as data_routes

        app, client = _app(tmp_path, ("garrett", "norman"))
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        _apply(app, model, "norman")
        real = data_routes.launch_catch_up

        def launch(app_: Any, project_id: int, framework_id: str) -> None:
            if framework_id == "garrett":
                raise RuntimeError("could not start")
            real(app_, project_id, framework_id)

        with model, client, patch.object(data_routes, "launch_catch_up", launch):
            _hide(client, dom, False)
            _wait(lambda: "autocode" in _tag_sources(app, text), "norman to code it")
        assert self_job(app).status == "completed", "not left 'running' with no task behind it"

    def test_a_codebook_switched_off_while_it_waits_its_turn_is_not_coded(
        self, tmp_path: Path
    ) -> None:
        """The codebooks go one at a time, so norman's turn can come minutes after the
        list was made; off means off still."""
        import threading

        app, client = _app(tmp_path, ("garrett", "norman"))
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        model = _Model()
        _apply(app, model, "garrett")
        _apply(app, model, "norman")
        applied = len(model.prompts)

        gate, out = threading.Event(), threading.Event()
        real = model.analyze

        async def slow(**kw: Any) -> AutoCodeBatchResult:
            import asyncio

            if _TITLES["garrett"] in str(kw["user_prompt"]):  # garrett codes first
                out.set()
                await asyncio.get_running_loop().run_in_executor(None, gate.wait)
            return await real(**kw)

        model.analyze = slow  # type: ignore[method-assign]
        try:
            with model, client:
                _hide(client, dom, False)
                _wait(out.is_set, "garrett to be out with its call")
                off = client.put(f"{_P}/framework-states", json={"norman": False})
                assert off.status_code == 200, off.text
                gate.set()
                _wait(lambda: "autocode" in _tag_sources(app, text), "garrett to finish")
                _quiet(1.0)
        finally:
            gate.set()  # never leave a thread waiting for ever
        assert not any(_TITLES["norman"] in p for p in model.prompts[applied:]), "off means off"


class TestACatchUpWhoseCodebookIsSwitchedOffMidWay:
    """N93: the catch-up read only a Stop before each batch, so a codebook switched off while it
    coded went on sending (and paying for) every batch after the switch ("off means off", #62)."""

    def test_the_batches_after_the_switch_are_not_sent_and_stay_owed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import threading

        import bristlenose.server.autocode as ac

        monkeypatch.setattr(ac, "BATCH_SIZE", 1)
        app, client = _app(tmp_path)
        _more_quotes(app, 3)
        burst = _dom(app, like="burst quote")
        _hide_in_db(app, burst)
        model = _Model()
        _apply(app, model, "garrett")
        applied = len(model.prompts)
        texts = ("burst quote 0", "burst quote 1", "burst quote 2")

        gate, out = threading.Event(), threading.Event()
        real = model.analyze

        async def slow(**kw: Any) -> AutoCodeBatchResult:
            import asyncio

            if len(model.prompts) == applied:  # the first batch of the catch-up
                out.set()
                await asyncio.get_running_loop().run_in_executor(None, gate.wait)
            return await real(**kw)

        model.analyze = slow  # type: ignore[method-assign]
        try:
            with model, client:
                _hide(client, burst, False)
                _wait(out.is_set, "the first batch to be out")
                off = client.put(f"{_P}/framework-states", json={"garrett": False})
                assert off.status_code == 200, off.text
                gate.set()
                _quiet(1.5)
                assert len(model.prompts) - applied == 1, "only the batch already out was paid for"
                assert self_job(app).status == "completed", "not left 'running' with no task behind it"
                assert sum(1 for t in texts if _tag_sources(app, t)) == 1, "the others were never sent"

                # Switched back on, it codes what was left owed, and only that.
                on = client.put(f"{_P}/framework-states", json={"garrett": True}).json()
                assert on["catchUp"] == ["garrett"]
                _wait(lambda: all(_tag_sources(app, t) for t in texts), "the rest to be coded")
                _quiet()
        finally:
            gate.set()
        assert len(model.prompts) - applied == 3, "each quote was sent once, none twice"


class TestAQuoteUnhiddenWhileTheFirstApplyRuns:
    def test_it_is_coded_when_the_apply_ends(self, tmp_path: Path) -> None:
        """The job is not applied until it ends, so the unhide armed nothing; the
        quote was not in its batches. The end of the apply asks again."""
        import threading

        app, client = _app(tmp_path)
        text = _first_quote_text(app)
        dom = _dom(app, text)
        _hide_in_db(app, dom)
        gate, out = threading.Event(), threading.Event()
        model = _Model()
        real = model.analyze

        async def slow(**kw: Any) -> AutoCodeBatchResult:
            import asyncio

            if not gate.is_set():
                out.set()
                await asyncio.get_running_loop().run_in_executor(None, gate.wait)
            return await real(**kw)

        model.analyze = slow  # type: ignore[method-assign]
        try:
            with model, client, patch("bristlenose.server.routes.autocode.load_settings",
                                      return_value=app.state.settings):
                started = client.post(f"{_P}/autocode/garrett")
                assert started.status_code == 200, started.text
                _wait(out.is_set, "the apply to be out with its call")
                assert _hide(client, dom, False)["catchUp"] == [], "not applied: nothing to arm"
                gate.set()
                _wait(lambda: "autocode" in _tag_sources(app, text), "the quote to be coded")
        finally:
            gate.set()
        assert text in "".join(model.prompts[1:])


class TestAHoldIsLiftedByAnyPassThatWorks:
    def test_a_switch_on_catch_up_that_succeeds_frees_the_codebook(self, tmp_path: Path) -> None:
        app, client = _app(tmp_path)
        _more_quotes(app, 3)
        doms = _dom(app, like="burst quote")
        _hide_in_db(app, doms)
        model = _Model()
        _apply(app, model, "garrett")
        model.fail = "api key not valid"
        with model, client:
            _hide(client, doms[:1], False)
            _wait(lambda: self_job(app).status == "failed", "the failure")
            assert _hide(client, doms[1:2], False)["catchUp"] == [], "held"

            model.fail = None  # the key was mended some other way: off and on again
            assert client.put(f"{_P}/framework-states", json={"garrett": False}).status_code == 200
            on = client.put(f"{_P}/framework-states", json={"garrett": True}).json()
            assert on["catchUp"] == ["garrett"]
            _wait(lambda: self_job(app).status == "completed", "the switch-on catch-up")

            hide_again = _hide(client, doms[2:], False)
        assert [c["framework_id"] for c in hide_again["catchUp"]] == ["garrett"]


class TestWhatAnUnhideCosts:
    """The route asks on every unhide; the credential store is a subprocess per key on the Mac."""

    def test_a_project_with_no_codebook_applied_reads_no_settings(self, tmp_path: Path) -> None:
        app, _client = _app(tmp_path)
        del app.state.settings
        with patch("bristlenose.config.load_settings") as load:
            assert cu.note_quotes_counting(app, 1) == []
        load.assert_not_called()

    def test_the_settings_are_kept_for_a_while(self, tmp_path: Path) -> None:
        app, _client = _app(tmp_path)
        del app.state.settings
        with patch("bristlenose.config.load_settings", return_value=_settings()) as load:
            for _ in range(5):
                cu._settings(app)
            assert load.call_count == 1
            cu._settings_memo = (id(app), time.monotonic() - cu._SETTINGS_TTL_S - 1, _settings())
            cu._settings(app)
            assert load.call_count == 2
