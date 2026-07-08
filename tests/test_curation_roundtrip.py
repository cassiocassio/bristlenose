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

from pathlib import Path

from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.importer import (
    _match_by_anchor,
    _match_by_membership,
    _pinned_quote_ids,
    import_project,
)
from bristlenose.server.models import ClusterQuote, HeadingEdit, Quote, QuoteState
from tests.conftest import AuthTestClient
from tests.server_fixtures import cluster as _cluster
from tests.server_fixtures import dom_id as _dom
from tests.server_fixtures import quote as _quote
from tests.server_fixtures import quote_at as _quote_at
from tests.server_fixtures import theme as _theme
from tests.server_fixtures import write_intermediate as _write_intermediate

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

    def test_human_tag_colliding_with_a_sentiment_label_does_not_mint(
        self, tmp_path: Path
    ) -> None:
        """Regression (mint/pin drift): a hand-typed tag whose name collides
        with a sentiment label ("confusion") resolves by name to the sentiment
        TagDefinition and arrives source="human".  It must NOT mint a
        durable_id / frozen_form — the mint site mirrors the pin predicate's
        sentiment exclusion, so minted-and-pinned stay in lockstep."""
        clusters = [
            _cluster(
                "Dashboard",
                [
                    # Quote A's sentiment auto-creates the "confusion" sentiment
                    # TagDefinition.
                    _quote("p1", 10, "Has sentiment", sentiment="confusion"),
                    _quote("p1", 20, "Tag me with a colliding name"),
                ],
            )
        ]
        _write_intermediate(tmp_path, clusters)
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        # Hand-apply that same "confusion" name to quote B (a genuine human PUT).
        client.put("/api/projects/1/tags", json={_dom("p1", 20): ["confusion"]})

        db = app.state.db_factory()
        try:
            b = _quote_at(db, 20)
            assert b.durable_id is None, "a sentiment-framework tag must not mint"
            assert b.frozen_form is None
            assert _pinned_quote_ids(db, 1) == set()
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


class TestMintIdempotency:
    def test_durable_id_stable_across_repin_within_pin_lifetime(
        self, tmp_path: Path
    ) -> None:
        """First-touch-wins WITHIN a pin lifetime: re-starring an already-pinned
        quote is a no-op — the durable_id and frozen words don't change.  Phase 2
        keys section/theme identity on durable_id stability, so a regen-per-toggle
        must fail here rather than ship silently."""
        _write_intermediate(
            tmp_path, [_cluster("Dashboard", [_quote("p1", 10, "Original words")])]
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        db = app.state.db_factory()
        try:
            q_id = _quote_at(db, 10).id
            client.put("/api/projects/1/starred", json={_dom("p1", 10): True})
            db.expire_all()
            durable = db.get(Quote, q_id).durable_id
            assert durable is not None

            client.put("/api/projects/1/starred", json={_dom("p1", 10): True})
            db.expire_all()
            again = db.get(Quote, q_id)
            assert again.durable_id == durable, "durable_id must not change on re-star"
            assert again.frozen_form == "Original words"
        finally:
            db.close()

    def test_unpin_scrubs_frozen_form_then_repin_remints(
        self, tmp_path: Path
    ) -> None:
        """Design decision (frozen_form scrub): un-pinning clears the durable_id +
        frozen_form (a re-identification key shouldn't linger on a quote the
        researcher un-pinned), so re-pinning is a *fresh* commitment — a new
        durable_id and the current (drifted) words, not the originals."""
        _write_intermediate(
            tmp_path, [_cluster("Dashboard", [_quote("p1", 10, "Original words")])]
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        db = app.state.db_factory()
        try:
            q_id = _quote_at(db, 10).id
            client.put("/api/projects/1/starred", json={_dom("p1", 10): True})
            db.expire_all()
            original_durable = db.get(Quote, q_id).durable_id
            assert original_durable is not None

            # Unstar, then re-import with drifted text (the row survives).
            client.put("/api/projects/1/starred", json={})
            _write_intermediate(
                tmp_path,
                [_cluster("Dashboard", [_quote("p1", 10, "Drifted pipeline text")])],
            )
            import_project(db, tmp_path)
            db.commit()
            db.expire_all()

            scrubbed = db.get(Quote, q_id)
            assert scrubbed.durable_id is None, "un-pin scrubs the durable id"
            assert scrubbed.frozen_form is None, "un-pin scrubs the frozen re-id key"

            # Re-star → a fresh commitment: new id, current words.
            client.put("/api/projects/1/starred", json={_dom("p1", 10): True})
            db.expire_all()
            repinned = db.get(Quote, q_id)
            assert repinned.durable_id is not None
            assert repinned.durable_id != original_durable, "re-pin mints a fresh id"
            assert repinned.frozen_form == "Drifted pipeline text", (
                "re-pin freezes the current words, not the scrubbed originals"
            )
        finally:
            db.close()

    def test_empty_incoming_group_is_not_persisted(self, tmp_path: Path) -> None:
        """A quote-less section/theme from the pipeline must not persist as an
        empty shell (design decision: retire drained/empty groups)."""
        _write_intermediate(
            tmp_path,
            [
                _cluster("Real", [_quote("p1", 10, "a")]),
                _cluster("Empty", []),
            ],
            themes=[_theme("EmptyTheme", [])],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        data = client.get("/api/projects/1/quotes").json()
        assert [s["screen_label"] for s in data["sections"]] == ["Real"]
        assert data["themes"] == []


class TestFrozenFormStaysOffTheExportBoundary:
    def test_quotes_payload_never_serialises_frozen_form_or_durable_id(
        self, tmp_path: Path
    ) -> None:
        """frozen_form is a re-identification key; durable_id is internal.
        Neither may cross the serialization boundary the HTML export embeds —
        export_data["quotes"] IS the /quotes payload (export.py:418).  The
        exclusion is structural today (the response models are field-explicit
        allowlists), and the deferred 'display frozen_form' work is exactly the
        temptation to add it to QuoteResponse; this makes the boundary enforced
        so that regression fails loudly."""
        clusters = [_cluster("Dashboard", [_quote("p1", 10, "Pin me")])]
        _write_intermediate(tmp_path, clusters)
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        # Pin the quote so frozen_form / durable_id are populated in the DB.
        client.put("/api/projects/1/starred", json={_dom("p1", 10): True})
        db = app.state.db_factory()
        try:
            q = _quote_at(db, 10)
            assert q.frozen_form is not None and q.durable_id is not None
        finally:
            db.close()

        resp = client.get("/api/projects/1/quotes")
        assert resp.status_code == 200
        body = resp.text
        for key in ("frozen_form", "frozenForm", "durable_id", "durableId"):
            assert key not in body, (
                f"{key} must not cross the export/serialisation boundary"
            )


# ---------------------------------------------------------------------------
# Phase 2 — Section identity
# ---------------------------------------------------------------------------


class TestMembershipMatcher:
    """Pure-logic matcher used by the importer to upsert by quote overlap."""

    def test_majority_child_keeps_id_on_split(self) -> None:
        existing = [(100, {1, 2, 3, 4})]
        incoming = [(0, {1, 2, 3}), (1, {4, 9, 10})]
        # 0 overlaps 100 by 3/4=0.75 (kept); 1 by 1/6≈0.17 (new).
        assert _match_by_membership(existing, incoming) == {0: 100}

    def test_no_match_below_threshold(self) -> None:
        existing = [(100, {1, 2, 3, 4})]
        incoming = [(0, {4, 5, 6, 7})]  # jaccard 1/7 < 0.5 → new group
        assert _match_by_membership(existing, incoming) == {}

    def test_each_existing_claimed_once_best_overlap_wins(self) -> None:
        existing = [(100, {1, 2, 3})]
        incoming = [(0, {1, 2, 3}), (1, {1, 2})]  # both overlap; 0 (1.0) wins
        assert _match_by_membership(existing, incoming) == {0: 100}


class TestSectionIdentity:
    def test_section_rename_survives_label_drift(self, tmp_path: Path) -> None:
        """The core Phase 2 contract: rename a section, then re-import with the
        pipeline label drifted (membership unchanged).  The rename still shows
        on the same durable cluster_id; the raw label tracks the pipeline."""
        members = [
            _quote("p1", 10, "A"),
            _quote("p1", 20, "B"),
            _quote("p1", 30, "C"),
        ]
        _write_intermediate(tmp_path, [_cluster("Dashboard", members)])
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        sections = client.get("/api/projects/1/quotes").json()["sections"]
        assert len(sections) == 1
        cid = sections[0]["cluster_id"]
        assert sections[0]["screen_label"] == "Dashboard"
        assert sections[0]["edited_label"] is None

        # Rename, keyed on the durable cluster id.
        assert client.put(
            "/api/projects/1/edits",
            json={f"section-cluster-{cid}:title": "Home screen"},
        ).status_code == 200

        after = client.get("/api/projects/1/quotes").json()["sections"][0]
        assert after["edited_label"] == "Home screen"
        assert after["screen_label"] == "Dashboard", "raw label preserved for reset"

        # Re-import: SAME quotes, pipeline label DRIFTED → membership upsert must
        # keep the cluster id, so the rename still applies.
        db = app.state.db_factory()
        try:
            _write_intermediate(
                tmp_path,
                [
                    _cluster(
                        "Main dashboard screen",
                        [_quote("p1", 10, "A"), _quote("p1", 20, "B"),
                         _quote("p1", 30, "C")],
                    )
                ],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        drifted = client.get("/api/projects/1/quotes").json()["sections"]
        assert len(drifted) == 1
        assert drifted[0]["cluster_id"] == cid, "membership upsert must keep the id"
        assert drifted[0]["screen_label"] == "Main dashboard screen", (
            "raw label tracks the pipeline"
        )
        assert drifted[0]["edited_label"] == "Home screen", (
            "rename survives pipeline label drift"
        )

    def test_new_section_gets_a_fresh_id_not_a_reused_one(
        self, tmp_path: Path
    ) -> None:
        """A section made of entirely new quotes (no predecessor) is a new
        group — it must not inherit a retiring section's id or its rename."""
        _write_intermediate(
            tmp_path,
            [_cluster("Login", [_quote("p1", 10, "old-a"), _quote("p1", 20, "old-b")])],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        old_cid = client.get("/api/projects/1/quotes").json()["sections"][0]["cluster_id"]

        db = app.state.db_factory()
        try:
            # Re-import: the old section is gone, a brand-new one takes its place
            # (all-new quotes) — and happens to reuse the label "Login".
            _write_intermediate(
                tmp_path,
                [_cluster("Login", [_quote("p1", 90, "new-a"), _quote("p1", 95, "new-b")])],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        sections = client.get("/api/projects/1/quotes").json()["sections"]
        assert len(sections) == 1
        assert sections[0]["cluster_id"] != old_cid, (
            "no membership overlap → a fresh id, not the retired section's"
        )

    def test_quote_moved_between_sections_appears_only_once(
        self, tmp_path: Path
    ) -> None:
        """A quote reassigned to a different section across a re-import must not
        linger in its old (membership-reused) section — quote exclusivity."""
        _write_intermediate(
            tmp_path,
            [
                _cluster(
                    "Login",
                    [_quote("p1", 10, "a"), _quote("p1", 20, "b"),
                     _quote("p1", 30, "c")],
                    order=1,
                ),
                _cluster(
                    "Settings",
                    [_quote("p1", 40, "d"), _quote("p1", 50, "e")],
                    order=2,
                ),
            ],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        # Re-import: quote at tc=30 moves Login→Settings. Both sections keep
        # their id (majority overlap), so both are reused, not recreated.
        db = app.state.db_factory()
        try:
            _write_intermediate(
                tmp_path,
                [
                    _cluster(
                        "Login",
                        [_quote("p1", 10, "a"), _quote("p1", 20, "b")],
                        order=1,
                    ),
                    _cluster(
                        "Settings",
                        [_quote("p1", 40, "d"), _quote("p1", 50, "e"),
                         _quote("p1", 30, "c")],
                        order=2,
                    ),
                ],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        sections = client.get("/api/projects/1/quotes").json()["sections"]
        appearances = sum(
            1
            for s in sections
            for q in s["quotes"]
            if q["dom_id"] == _dom("p1", 30)
        )
        assert appearances == 1, "a moved quote must appear in exactly one section"

    def test_named_section_survives_when_the_pipeline_drops_it(
        self, tmp_path: Path
    ) -> None:
        """A *renamed* (human-owned) section is exempt from retirement: even when
        the pipeline stops emitting it entirely, the section survives — down to
        zero members — carrying its rename.  (Theme-naming commitment model: the
        researcher claimed the container; only they delete it.)  A surviving
        section never frees its integer id, so the old id-reuse rename leak is
        structurally impossible — no other section can inherit the rename."""
        _write_intermediate(tmp_path, [_cluster("Login", [_quote("p1", 10, "a")])])
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        cid = client.get("/api/projects/1/quotes").json()["sections"][0]["cluster_id"]
        client.put(
            "/api/projects/1/edits",
            json={f"section-cluster-{cid}:title": "Renamed"},
        )

        db = app.state.db_factory()
        try:
            # No overlap with the renamed section → the pipeline drops it entirely.
            _write_intermediate(
                tmp_path, [_cluster("Onboarding", [_quote("p1", 90, "z")])]
            )
            import_project(db, tmp_path)
            db.commit()
            # The rename survives — the section was NOT retired.
            leftover = (
                db.query(HeadingEdit)
                .filter_by(heading_key=f"section-cluster-{cid}:title")
                .count()
            )
            assert leftover == 1, "a named section's rename must survive the drop"
        finally:
            db.close()

        sections = {
            s["cluster_id"]: s
            for s in client.get("/api/projects/1/quotes").json()["sections"]
        }
        # The named section still exists — now empty — still showing its name.
        assert cid in sections, "a named section must not be retired"
        assert sections[cid]["edited_label"] == "Renamed"
        assert sections[cid]["quotes"] == []
        # Every other section shows its own pipeline label, never the rename.
        for scid, s in sections.items():
            if scid != cid:
                assert s["edited_label"] is None

    def test_pinned_quote_dropped_from_reused_section_stays_visible(
        self, tmp_path: Path
    ) -> None:
        """A starred quote the pipeline stops emitting, from a section that is
        otherwise REUSED (membership majority), must not be orphaned by the
        membership rebuild — Freeze keeps the row, and it must stay visible in
        exactly one section (regression: the rebuild deleted its only join)."""
        _write_intermediate(
            tmp_path,
            [_cluster("Dashboard", [_quote("p1", 10, "a"), _quote("p1", 20, "b"),
                                    _quote("p1", 30, "c"), _quote("p1", 40, "d")])],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        client.put("/api/projects/1/starred", json={_dom("p1", 10): True})

        db = app.state.db_factory()
        try:
            # Re-import Dashboard emitting {20,30,40} — drops the starred q@10.
            # Overlap 3/4 → REUSED (same cluster id), so the rebuild fires.
            _write_intermediate(
                tmp_path,
                [_cluster("Dashboard", [_quote("p1", 20, "b"), _quote("p1", 30, "c"),
                                        _quote("p1", 40, "d")])],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        sections = client.get("/api/projects/1/quotes").json()["sections"]
        appearances = [
            s["screen_label"] for s in sections
            for q in s["quotes"] if q["dom_id"] == _dom("p1", 10)
        ]
        assert appearances == ["Dashboard"], (
            "a pinned but no-longer-emitted quote must stay visible in its "
            f"reused section exactly once, got {appearances}"
        )

    def test_pinned_quote_moved_between_reused_sections_appears_once(
        self, tmp_path: Path
    ) -> None:
        """The exclusivity edge the strand fix must NOT reintroduce: a PINNED
        quote that MOVES between two reused sections appears in exactly one (its
        stale source join is still deleted because it IS in an incoming set)."""
        _write_intermediate(
            tmp_path,
            [
                _cluster("Login", [_quote("p1", 10, "a"), _quote("p1", 20, "b"),
                                   _quote("p1", 30, "c")], order=1),
                _cluster("Settings", [_quote("p1", 40, "d"), _quote("p1", 50, "e")],
                         order=2),
            ],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        client.put("/api/projects/1/starred", json={_dom("p1", 30): True})  # pin the mover

        db = app.state.db_factory()
        try:
            _write_intermediate(
                tmp_path,
                [
                    _cluster("Login", [_quote("p1", 10, "a"), _quote("p1", 20, "b")],
                             order=1),
                    _cluster("Settings", [_quote("p1", 40, "d"), _quote("p1", 50, "e"),
                                          _quote("p1", 30, "c")], order=2),
                ],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        sections = client.get("/api/projects/1/quotes").json()["sections"]
        appearances = [
            s["screen_label"] for s in sections
            for q in s["quotes"] if q["dom_id"] == _dom("p1", 30)
        ]
        assert appearances == ["Settings"], (
            f"a pinned moved quote must appear once, in its new section; got {appearances}"
        )


class TestThemeIdentity:
    """The theme arm of Phase 2 is hand-duplicated from clusters; mirror the
    identity + exclusivity coverage so the two can't silently diverge."""

    def test_theme_rename_survives_label_drift(self, tmp_path: Path) -> None:
        members = [_quote("p1", 10, "a"), _quote("p1", 20, "b"), _quote("p1", 30, "c")]
        _write_intermediate(
            tmp_path, [_cluster("Sec", [_quote("p1", 5, "x")])],
            themes=[_theme("Trust", members)],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        themes = client.get("/api/projects/1/quotes").json()["themes"]
        tid = themes[0]["theme_id"]
        assert client.put(
            "/api/projects/1/edits",
            json={f"theme-group-{tid}:title": "Confidence"},
        ).status_code == 200

        db = app.state.db_factory()
        try:
            _write_intermediate(
                tmp_path, [_cluster("Sec", [_quote("p1", 5, "x")])],
                themes=[_theme("Trust & safety", [_quote("p1", 10, "a"),
                                                  _quote("p1", 20, "b"),
                                                  _quote("p1", 30, "c")])],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        t = client.get("/api/projects/1/quotes").json()["themes"][0]
        assert t["theme_id"] == tid, "theme id stable across label drift"
        assert t["theme_label"] == "Trust & safety", "raw label tracks pipeline"
        assert t["edited_label"] == "Confidence", "rename survives drift"

    def test_quote_moved_between_reused_themes_appears_once(
        self, tmp_path: Path
    ) -> None:
        _write_intermediate(
            tmp_path, [_cluster("Sec", [_quote("p1", 5, "x")])],
            themes=[
                _theme("A", [_quote("p1", 10, "a"), _quote("p1", 20, "b"),
                             _quote("p1", 30, "c")]),
                _theme("B", [_quote("p1", 40, "d"), _quote("p1", 50, "e")]),
            ],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        db = app.state.db_factory()
        try:
            _write_intermediate(
                tmp_path, [_cluster("Sec", [_quote("p1", 5, "x")])],
                themes=[
                    _theme("A", [_quote("p1", 10, "a"), _quote("p1", 20, "b")]),
                    _theme("B", [_quote("p1", 40, "d"), _quote("p1", 50, "e"),
                                 _quote("p1", 30, "c")]),
                ],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        themes = client.get("/api/projects/1/quotes").json()["themes"]
        appearances = sum(
            1 for t in themes for q in t["quotes"] if q["dom_id"] == _dom("p1", 30)
        )
        assert appearances == 1, "a quote moved between reused themes appears once"


class TestNewFlag:
    """Phase 3 (3c) — the M3 'New' gate: a section/theme is New when a majority
    of its quotes come from an interview added in the latest import."""

    def test_nothing_new_on_first_import(self, tmp_path: Path) -> None:
        _write_intermediate(
            tmp_path, [_cluster("Alpha", [_quote("p1", 10, "a", session="s1")])]
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        data = client.get("/api/projects/1/quotes").json()
        assert data["new_since"] is None
        assert all(not s["is_new"] for s in data["sections"])

    def test_added_interview_flags_its_new_section_only(self, tmp_path: Path) -> None:
        _write_intermediate(
            tmp_path,
            [
                _cluster("Alpha", [_quote("p1", 10, "a", session="s1")]),
                _cluster("Beta", [_quote("p1", 20, "b", session="s1")]),
            ],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)

        db = app.state.db_factory()
        try:
            # Add interview s2 → a new section made of its quotes; Alpha grows by
            # a minority (1 new of 3), Beta unchanged.
            _write_intermediate(
                tmp_path,
                [
                    _cluster("Alpha", [_quote("p1", 10, "a", session="s1"),
                                       _quote("p1", 11, "a2", session="s1"),
                                       _quote("p1", 30, "c", session="s2")]),
                    _cluster("Beta", [_quote("p1", 20, "b", session="s1")]),
                    _cluster("Gamma", [_quote("p1", 40, "d", session="s2"),
                                       _quote("p1", 50, "e", session="s2")]),
                ],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        data = client.get("/api/projects/1/quotes").json()
        assert data["new_since"] is not None
        flags = {s["screen_label"]: s["is_new"] for s in data["sections"]}
        assert flags["Gamma"] is True, "a section made of the new interview is New"
        assert flags["Alpha"] is False, "minority-new material (1/3) is below the gate"
        assert flags["Beta"] is False, "unchanged section is not New"


class TestThemeStarAnchor:
    """Phase 3 — a renamed theme's custom name follows its frozen star-anchors
    across the theme churn (ARI ~0.43) that membership matching can't survive."""

    def test_anchor_matcher_follows_plurality(self) -> None:
        # theme 100 anchored on pinned {1,2,3}; incoming idx 1 holds 2 of them.
        assert _match_by_anchor([(100, {1, 2, 3})], [(0, {1, 9}), (1, {2, 3, 8})]) == {
            1: 100
        }

    def test_anchor_matcher_claims_each_once(self) -> None:
        # both themes' anchors land in one incoming theme; the bigger overlap wins.
        assert _match_by_anchor([(100, {1, 2}), (200, {3})], [(0, {1, 2, 3})]) == {
            0: 100
        }

    def test_renamed_theme_name_follows_star_anchor_through_divergence(
        self, tmp_path: Path
    ) -> None:
        """The core Phase 3 contract: rename a theme with a starred quote, then
        re-import with the theme SCATTERED (membership far below the match
        threshold).  The custom name lands on whichever incoming theme holds the
        star-anchor — not lost, not on an unrelated theme."""
        _write_intermediate(
            tmp_path, [_cluster("Sec", [_quote("p1", 1, "s")])],
            themes=[_theme("Onboarding", [_quote("p1", 10, "a"), _quote("p1", 20, "b"),
                                          _quote("p1", 30, "c"), _quote("p1", 40, "d"),
                                          _quote("p1", 50, "e")])],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        tid = client.get("/api/projects/1/quotes").json()["themes"][0]["theme_id"]
        client.put("/api/projects/1/starred", json={_dom("p1", 10): True})
        client.put(
            "/api/projects/1/edits", json={f"theme-group-{tid}:title": "Early experience"}
        )

        db = app.state.db_factory()
        try:
            # Scatter Onboarding's quotes across 3 unrelated themes (ARI-0.43).
            # The star-anchor q@10 lands in "Trust".
            _write_intermediate(
                tmp_path, [_cluster("Sec", [_quote("p1", 1, "s")])],
                themes=[
                    _theme("Trust", [_quote("p1", 10, "a"), _quote("p1", 60, "x")]),
                    _theme("Navigation", [_quote("p1", 20, "b"), _quote("p1", 30, "c")]),
                    _theme("Pricing", [_quote("p1", 40, "d"), _quote("p1", 50, "e"),
                                       _quote("p1", 70, "y")]),
                ],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        themes = client.get("/api/projects/1/quotes").json()["themes"]
        named = [t for t in themes if t["edited_label"] == "Early experience"]
        assert len(named) == 1, "the custom name must survive on exactly one theme"
        assert named[0]["theme_id"] == tid, "the theme keeps its durable id"
        assert _dom("p1", 10) in [q["dom_id"] for q in named[0]["quotes"]], (
            "the name lands on the theme holding the star-anchor"
        )

    def test_renamed_theme_name_sticks_across_two_reimports(
        self, tmp_path: Path
    ) -> None:
        """Bind-then-stick: the name keeps following the star-anchor over
        successive churny re-imports, not just the first."""
        _write_intermediate(
            tmp_path, [_cluster("Sec", [_quote("p1", 1, "s")])],
            themes=[_theme("T", [_quote("p1", 10, "a"), _quote("p1", 20, "b")])],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        tid = client.get("/api/projects/1/quotes").json()["themes"][0]["theme_id"]
        client.put("/api/projects/1/starred", json={_dom("p1", 10): True})
        client.put("/api/projects/1/edits", json={f"theme-group-{tid}:title": "Named"})

        db = app.state.db_factory()
        try:
            # Run 2: anchor q@10 moves into "Alpha".
            _write_intermediate(
                tmp_path, [_cluster("Sec", [_quote("p1", 1, "s")])],
                themes=[_theme("Alpha", [_quote("p1", 10, "a"), _quote("p1", 80, "z")]),
                        _theme("Beta", [_quote("p1", 20, "b")])],
            )
            import_project(db, tmp_path)
            db.commit()
            # Run 3: anchor q@10 moves again, into "Gamma".
            _write_intermediate(
                tmp_path, [_cluster("Sec", [_quote("p1", 1, "s")])],
                themes=[_theme("Gamma", [_quote("p1", 10, "a"), _quote("p1", 90, "w")]),
                        _theme("Delta", [_quote("p1", 80, "z")])],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        themes = client.get("/api/projects/1/quotes").json()["themes"]
        named = [t for t in themes if t["edited_label"] == "Named"]
        assert len(named) == 1 and named[0]["theme_id"] == tid, (
            "the custom name sticks to the star-anchor's theme across re-imports"
        )
        assert _dom("p1", 10) in [q["dom_id"] for q in named[0]["quotes"]]


class TestUncategorisedFloor:
    """When healthier theming drops a pinned quote and its group drains, the
    quote must never be silently hidden.  Two outcomes, split by the theme-naming
    commitment model:
      * un-named (machine) theme retires -> the pinned quote surfaces in the
        read-only Uncategorised floor (keep the quote, bin the theme);
      * named (human-owned) theme survives -> the quote stays in it, even down to
        a single member, and the rename is preserved.
    All cases keep the quote's session present, so the ONLY variable is the theme
    retiring (session-removal is a separate, by-design deletion path).
    """

    def _homed(self, pl: dict) -> set[str]:
        return {q["dom_id"] for g in pl["sections"] + pl["themes"] for q in g["quotes"]}

    def test_unnamed_theme_drain_surfaces_starred_quote_in_uncategorised(
        self, tmp_path: Path
    ) -> None:
        _write_intermediate(
            tmp_path,
            [_cluster("Nav", [_quote("p1", 10, "nav")])],
            [_theme("Machine theme", [_quote("p2", 5, "valuable", session="s2")])],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        client.put("/api/projects/1/starred", json={_dom("p2", 5): True})
        pl = client.get("/api/projects/1/quotes").json()
        assert _dom("p2", 5) in self._homed(pl), "starts homed in its theme"
        assert pl["uncategorised"] == []

        db = app.state.db_factory()
        try:
            # s2 kept alive by p2@40; the star (p2@5) is dropped from all themes;
            # the un-named theme overlaps nothing incoming -> retires.
            _write_intermediate(
                tmp_path,
                [_cluster("Nav", [_quote("p1", 10, "nav")])],
                [_theme("Other", [_quote("p2", 40, "other", session="s2")])],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        pl = client.get("/api/projects/1/quotes").json()
        uncat = {q["dom_id"] for q in pl["uncategorised"]}
        assert "Machine theme" not in {t["theme_label"] for t in pl["themes"]}, (
            "an un-named drained theme retires"
        )
        assert _dom("p2", 5) not in self._homed(pl), "the star lost its group"
        assert _dom("p2", 5) in uncat, (
            "a dropped pinned quote must surface in the Uncategorised floor"
        )
        assert pl["total_uncategorised"] == len(pl["uncategorised"]) == 1, (
            "the top-level count tracks the populated floor"
        )

    def test_named_theme_survives_drain_keeping_its_starred_quote(
        self, tmp_path: Path
    ) -> None:
        _write_intermediate(
            tmp_path,
            [_cluster("Nav", [_quote("p1", 10, "nav")])],
            [_theme("Machine theme", [_quote("p2", 5, "valuable", session="s2")])],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        client.put("/api/projects/1/starred", json={_dom("p2", 5): True})
        tid = client.get("/api/projects/1/quotes").json()["themes"][0]["theme_id"]
        client.put("/api/projects/1/edits", json={f"theme-group-{tid}:title": "Mine"})

        db = app.state.db_factory()
        try:
            _write_intermediate(
                tmp_path,
                [_cluster("Nav", [_quote("p1", 10, "nav")])],
                [_theme("Other", [_quote("p2", 40, "other", session="s2")])],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        pl = client.get("/api/projects/1/quotes").json()
        themes = {t["theme_id"]: t for t in pl["themes"]}
        assert tid in themes, "a named theme must survive the drain"
        assert themes[tid]["edited_label"] == "Mine", "its rename is preserved"
        assert _dom("p2", 5) in [q["dom_id"] for q in themes[tid]["quotes"]], (
            "the starred quote stays in the theme the researcher named"
        )
        assert pl["uncategorised"] == [], "nothing is orphaned"

    def test_named_theme_survives_to_zero_members(self, tmp_path: Path) -> None:
        _write_intermediate(
            tmp_path,
            [_cluster("Nav", [_quote("p1", 10, "nav")])],
            [_theme("Machine theme", [_quote("p2", 5, "x", session="s2")])],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        tid = client.get("/api/projects/1/quotes").json()["themes"][0]["theme_id"]
        client.put("/api/projects/1/edits", json={f"theme-group-{tid}:title": "Kept"})

        db = app.state.db_factory()
        try:
            # The theme's only quote is un-pinned and dropped -> swept.  s2 stays
            # alive via a section quote, so the named theme drains to zero, not the
            # quote's session vanishing.
            _write_intermediate(
                tmp_path,
                [_cluster("Nav", [_quote("p1", 10, "nav"),
                                  _quote("p2", 40, "keeps s2", session="s2")])],
                [_theme("Other", [_quote("p3", 7, "z", session="s3")])],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        themes = {
            t["theme_id"]: t
            for t in client.get("/api/projects/1/quotes").json()["themes"]
        }
        assert tid in themes, "a named theme survives even at zero members"
        assert themes[tid]["edited_label"] == "Kept"
        assert themes[tid]["quotes"] == [], "a 0-member named theme is a valid state"


class TestManualReassignment:
    """Phase 0 — a researcher's manual placement is honoured and survives
    re-analysis.  The machine's grouping is a draft; the researcher overrules it,
    and the overrule sticks even when the next pipeline run still emits the quote
    in its old group (suppression) or stops emitting it entirely (freeze).
    """

    def _section_placements(self, client: TestClient, dom: str) -> list[str]:
        secs = client.get("/api/projects/1/quotes").json()["sections"]
        return [
            s["screen_label"]
            for s in secs
            for q in s["quotes"]
            if q["dom_id"] == dom
        ]

    def _theme_placements(self, client: TestClient, dom: str) -> list[str]:
        themes = client.get("/api/projects/1/quotes").json()["themes"]
        return [
            t["theme_label"]
            for t in themes
            for q in t["quotes"]
            if q["dom_id"] == dom
        ]

    def test_move_is_exclusive_and_marked_researcher(self, tmp_path: Path) -> None:
        """A move removes the old section join and adds one researcher join —
        the quote is in exactly one section immediately."""
        _write_intermediate(
            tmp_path,
            [
                _cluster("Login", [_quote("p1", 10, "a"), _quote("p1", 20, "b")],
                         order=1),
                _cluster("Settings", [_quote("p1", 40, "d")], order=2),
            ],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        sections = client.get("/api/projects/1/quotes").json()["sections"]
        settings_id = next(
            s["cluster_id"] for s in sections if s["screen_label"] == "Settings"
        )

        resp = client.post(
            "/api/projects/1/reassign",
            json={
                "quotes": [_dom("p1", 20)],
                "target_kind": "section",
                "target_id": settings_id,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["moved"] == [_dom("p1", 20)]
        assert self._section_placements(client, _dom("p1", 20)) == ["Settings"], (
            "the moved quote is in exactly one section"
        )

        db = app.state.db_factory()
        try:
            q20 = _quote_at(db, 20)
            join = (
                db.query(ClusterQuote).filter_by(quote_id=q20.id).one()
            )
            assert join.assigned_by == "researcher"
            assert q20.durable_id is not None, "a move freezes the quote"
        finally:
            db.close()

    def test_placement_survives_a_reimport_that_re_emits_the_old_group(
        self, tmp_path: Path
    ) -> None:
        """The load-bearing rule: the next pipeline run still emits q@20 in Login
        (it can't know the researcher moved it).  Suppression must keep the quote
        in Settings only — never re-add a pipeline join to Login."""
        _write_intermediate(
            tmp_path,
            [
                _cluster("Login", [_quote("p1", 10, "a"), _quote("p1", 20, "b")],
                         order=1),
                _cluster("Settings", [_quote("p1", 40, "d")], order=2),
            ],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        sections = client.get("/api/projects/1/quotes").json()["sections"]
        settings_id = next(
            s["cluster_id"] for s in sections if s["screen_label"] == "Settings"
        )
        client.post(
            "/api/projects/1/reassign",
            json={
                "quotes": [_dom("p1", 20)],
                "target_kind": "section",
                "target_id": settings_id,
            },
        )

        db = app.state.db_factory()
        try:
            # Unchanged intermediate: the pipeline STILL puts q@20 in Login.
            _write_intermediate(
                tmp_path,
                [
                    _cluster("Login", [_quote("p1", 10, "a"), _quote("p1", 20, "b")],
                             order=1),
                    _cluster("Settings", [_quote("p1", 40, "d")], order=2),
                ],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        assert self._section_placements(client, _dom("p1", 20)) == ["Settings"], (
            "a researcher placement must survive re-analysis, and the pipeline "
            "must not resurrect the quote in its old section"
        )

    def test_move_freezes_the_quote_against_a_pipeline_drop(
        self, tmp_path: Path
    ) -> None:
        """A moved-but-unstarred quote the next run stops emitting entirely (its
        session still present) must not be swept — the move alone freezes it, so
        a committed placement is never silently lost."""
        _write_intermediate(
            tmp_path,
            [
                _cluster("Login", [_quote("p1", 10, "a"), _quote("p1", 20, "b")],
                         order=1),
                _cluster("Settings", [_quote("p1", 40, "d")], order=2),
            ],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        sections = client.get("/api/projects/1/quotes").json()["sections"]
        settings_id = next(
            s["cluster_id"] for s in sections if s["screen_label"] == "Settings"
        )
        client.post(
            "/api/projects/1/reassign",
            json={
                "quotes": [_dom("p1", 20)],
                "target_kind": "section",
                "target_id": settings_id,
            },
        )

        db = app.state.db_factory()
        try:
            # The pipeline drops q@20 completely; its session (s1) stays alive.
            _write_intermediate(
                tmp_path,
                [
                    _cluster("Login", [_quote("p1", 10, "a")], order=1),
                    _cluster("Settings", [_quote("p1", 40, "d")], order=2),
                ],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        assert self._section_placements(client, _dom("p1", 20)) == ["Settings"], (
            "freeze-on-move keeps the quote alive and in its researcher section"
        )

    def test_theme_placement_is_exclusive_and_survives(self, tmp_path: Path) -> None:
        """The theme axis mirrors sections: move q@5 into another theme, and it
        appears in exactly one theme, surviving a re-import that re-emits it in
        the old one."""
        _write_intermediate(
            tmp_path,
            [_cluster("Nav", [_quote("p1", 10, "nav")])],
            [
                _theme("Trust", [_quote("p2", 5, "x", session="s2")]),
                _theme("Speed", [_quote("p2", 8, "y", session="s2")]),
            ],
        )
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        client: TestClient = AuthTestClient(app)
        themes = client.get("/api/projects/1/quotes").json()["themes"]
        speed_id = next(t["theme_id"] for t in themes if t["theme_label"] == "Speed")
        client.post(
            "/api/projects/1/reassign",
            json={
                "quotes": [_dom("p2", 5)],
                "target_kind": "theme",
                "target_id": speed_id,
            },
        )
        assert self._theme_placements(client, _dom("p2", 5)) == ["Speed"]

        db = app.state.db_factory()
        try:
            _write_intermediate(
                tmp_path,
                [_cluster("Nav", [_quote("p1", 10, "nav")])],
                [
                    _theme("Trust", [_quote("p2", 5, "x", session="s2")]),
                    _theme("Speed", [_quote("p2", 8, "y", session="s2")]),
                ],
            )
            import_project(db, tmp_path)
            db.commit()
        finally:
            db.close()

        assert self._theme_placements(client, _dom("p2", 5)) == ["Speed"], (
            "a researcher theme placement survives re-analysis"
        )
