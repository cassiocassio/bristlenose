"""Round-trip contract for curation persistence — Phase 1 (Freeze).

The executable contract: any quote the researcher touches (star / edit / human
tag) survives a re-import that would otherwise lose it, in its frozen form,
with its marks.  Untouched marginal quotes fall off as before, and machine
signals (sentiment tags) never pin.  These are hard assertions — no "passes
most of the time".

Everything here is deterministic: hand-placed drift, no live re-extraction, no
LLM, no API keys.  Re-import is simulated by rewriting the intermediate JSON
and calling ``import_project`` again against the shared in-memory DB.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.importer import _pinned_quote_ids, import_project
from bristlenose.server.models import Quote, QuoteState
from tests.conftest import AuthTestClient

# ---------------------------------------------------------------------------
# Synthetic project helpers
# ---------------------------------------------------------------------------


def _quote(pid: str, tc: float, text: str, sentiment: str | None = None) -> dict:
    q = {
        "session_id": "s1",
        "participant_id": pid,
        "start_timecode": float(tc),
        "end_timecode": float(tc) + 5.0,
        "text": text,
        "topic_label": "Topic",
        "quote_type": "screen_specific",
    }
    if sentiment:
        q["sentiment"] = sentiment
    return q


def _cluster(label: str, quotes: list[dict], order: int = 1) -> dict:
    return {
        "screen_label": label,
        "description": "",
        "display_order": order,
        "quotes": quotes,
    }


def _write_intermediate(
    project_dir: Path,
    clusters: list[dict],
    themes: list[dict] | None = None,
    project_name: str = "Freeze Test",
) -> None:
    inter = project_dir / "bristlenose-output" / ".bristlenose" / "intermediate"
    inter.mkdir(parents=True, exist_ok=True)
    (inter / "metadata.json").write_text(json.dumps({"project_name": project_name}))
    (inter / "screen_clusters.json").write_text(json.dumps(clusters))
    (inter / "theme_groups.json").write_text(json.dumps(themes or []))


def _dom(pid: str, tc: float) -> str:
    return f"q-{pid}-{int(tc)}"


def _quote_at(db, tc: float) -> Quote:
    return db.query(Quote).filter_by(start_timecode=float(tc)).one()


# ---------------------------------------------------------------------------
# The round-trip
# ---------------------------------------------------------------------------


class TestFreezeRoundTrip:
    def test_marked_work_survives_a_reimport_that_drops_everything(
        self, tmp_path: Path
    ) -> None:
        """Star A, edit B, tag C, leave D untouched.  Re-import emits none of
        them (extreme boundary drift).  A/B/C survive frozen with their marks;
        D is gone."""
        clusters = [
            _cluster(
                "Dashboard",
                [
                    _quote("p1", 10, "Original A text", sentiment="confusion"),
                    _quote("p1", 20, "Original B text, rambling and unclear"),
                    _quote("p1", 30, "Original C text"),
                    _quote("p1", 40, "Original D text — marginal"),
                ],
            )
        ]
        _write_intermediate(tmp_path, clusters)
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        # Researcher invests effort.
        assert client.put(
            "/api/projects/1/starred", json={_dom("p1", 10): True}
        ).status_code == 200
        assert client.put(
            "/api/projects/1/edits",
            json={_dom("p1", 20): "Edited B — trimmed and clarified"},
        ).status_code == 200
        assert client.put(
            "/api/projects/1/tags",
            json={_dom("p1", 30): ["User prefers design B"]},
        ).status_code == 200

        db = app.state.db_factory()
        try:
            a, b, c, d = (_quote_at(db, tc) for tc in (10, 20, 30, 40))
            a_id, b_id, c_id, d_id = a.id, b.id, c.id, d.id

            # Minting on first human touch.
            for q in (a, b, c):
                assert q.durable_id is not None, "pinned quote must mint a durable_id"
                assert q.frozen_form is not None
            assert d.durable_id is None, "untouched quote must not be pinned"

            # Frozen form = the researcher's words at pin time.
            assert b.frozen_form == "Edited B — trimmed and clarified"
            assert a.frozen_form == "Original A text"
            assert c.frozen_form == "Original C text"

            # Pin set is exactly the three touched quotes (sentiment tag on A
            # does NOT add extra pins — A is pinned by its star).
            assert _pinned_quote_ids(db, 1) == {a_id, b_id, c_id}

            # Re-import: the pipeline surfaces a completely different quote —
            # none of the originals match, so all four look stale.
            _write_intermediate(
                tmp_path, [_cluster("Dashboard", [_quote("p1", 90, "Brand new")])]
            )
            import_project(db, tmp_path)
            db.commit()

            surviving = {q.id for q in db.query(Quote).all()}
            assert a_id in surviving, "starred quote must survive"
            assert b_id in surviving, "edited quote must survive"
            assert c_id in surviving, "tagged quote must survive"
            assert d_id not in surviving, "untouched marginal quote falls off"

            # Marks and frozen form intact after the re-run.
            assert (
                db.query(QuoteState).filter_by(quote_id=a_id).one().is_starred is True
            )
            b_after = db.get(Quote, b_id)
            assert b_after is not None
            assert b_after.frozen_form == "Edited B — trimmed and clarified"
            assert b_after.durable_id is not None
        finally:
            db.close()


    def test_freeze_does_not_survive_session_removal(self, tmp_path: Path) -> None:
        """Governance boundary: Freeze protects against re-extraction drift, not
        against removing an interview.  A starred quote whose *session* is
        deleted (withdrawn consent, removed recording) is deleted with it —
        pinned or not."""
        clusters = [
            _cluster(
                "Dashboard",
                [
                    _quote("p1", 10, "Keep — session stays"),
                    _quote("p1", 12, "Star me — session goes"),
                ],
            )
        ]
        # Put the second quote in its own session so we can remove that session.
        clusters[0]["quotes"][1]["session_id"] = "s2"
        _write_intermediate(tmp_path, clusters)
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        db = app.state.db_factory()
        try:
            gone = db.query(Quote).filter_by(session_id="s2").one()
            gone_id = gone.id
            client.put("/api/projects/1/starred", json={_dom("p1", 12): True})
            db.expire_all()
            assert _pinned_quote_ids(db, 1) == {gone_id}

            # Re-import WITHOUT session s2 — the interview is gone.
            _write_intermediate(
                tmp_path, [_cluster("Dashboard", [_quote("p1", 10, "Keep")])]
            )
            import_project(db, tmp_path)
            db.commit()

            assert db.get(Quote, gone_id) is None, (
                "a pinned quote must NOT survive removal of its session"
            )
            assert db.query(QuoteState).filter_by(quote_id=gone_id).count() == 0
        finally:
            db.close()


class TestPinPredicate:
    def test_sentiment_tag_alone_does_not_pin(self, tmp_path: Path) -> None:
        """A quote with only a machine sentiment tag is not the researcher's
        work — it must not be exempt from cleanup."""
        clusters = [
            _cluster("Dashboard", [_quote("p1", 10, "Has sentiment", "confusion")])
        ]
        _write_intermediate(tmp_path, clusters)
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")

        db = app.state.db_factory()
        try:
            q = _quote_at(db, 10)
            q_id = q.id
            # It has a sentiment QuoteTag (auto-created) but no human work.
            assert _pinned_quote_ids(db, 1) == set()

            # Re-import without it → gone.
            _write_intermediate(
                tmp_path, [_cluster("Dashboard", [_quote("p1", 90, "New")])]
            )
            import_project(db, tmp_path)
            db.commit()
            assert db.get(Quote, q_id) is None
        finally:
            db.close()

    def test_unpin_lets_the_quote_fall_off_again(self, tmp_path: Path) -> None:
        """Star then unstar (no other work): protection lifts, and a re-import
        that drops the quote deletes it.  Object permanence lasts exactly as
        long as the human's investment."""
        clusters = [_cluster("Dashboard", [_quote("p1", 10, "Star me then not")])]
        _write_intermediate(tmp_path, clusters)
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        db = app.state.db_factory()
        try:
            q_id = _quote_at(db, 10).id

            client.put("/api/projects/1/starred", json={_dom("p1", 10): True})
            assert _pinned_quote_ids(db, 1) == {q_id}

            # Unstar — PUT the empty map clears all stars.
            client.put("/api/projects/1/starred", json={})
            db.expire_all()
            assert _pinned_quote_ids(db, 1) == set()

            _write_intermediate(
                tmp_path, [_cluster("Dashboard", [_quote("p1", 90, "New")])]
            )
            import_project(db, tmp_path)
            db.commit()
            assert db.get(Quote, q_id) is None
        finally:
            db.close()


class TestHidePersistence:
    def test_hidden_survives_when_the_quote_is_reemitted(self, tmp_path: Path) -> None:
        """Hide is best-effort, not a freeze: a hidden quote that the pipeline
        re-emits keeps its hidden state.  (A dropped hidden quote is not
        protected — that miss-rate is documented, not asserted here.)"""
        clusters = [_cluster("Dashboard", [_quote("p1", 10, "Hide me")])]
        _write_intermediate(tmp_path, clusters)
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        db = app.state.db_factory()
        try:
            q_id = _quote_at(db, 10).id
            client.put("/api/projects/1/hidden", json={_dom("p1", 10): True})

            # Re-import emitting the same quote (stable key unchanged).
            import_project(db, tmp_path)
            db.commit()
            db.expire_all()

            state = db.query(QuoteState).filter_by(quote_id=q_id).one()
            assert state.is_hidden is True
        finally:
            db.close()
