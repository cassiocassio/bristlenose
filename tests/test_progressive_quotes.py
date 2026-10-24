"""Progressive lenses, Phase 2: quotes arrive session by session.

docs/design-progressive-lenses.md, Phase 2. The gate the phase rests on: a
star, a hide or a tag on a quote imported during the run survives the whole
import at the end, when the quote joins a section.
"""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.manifest import (
    STAGE_MERGE_TRANSCRIPT,
    STAGE_PII_REMOVAL,
    STAGE_QUOTE_EXTRACTION,
    create_manifest,
    load_manifest,
    mark_session_complete,
    mark_stage_running,
    write_manifest,
)
from bristlenose.server.lens_readiness import quoted_in_manifest, readable_in_manifest
from tests.test_progressive_lenses import _follow, _record_readable, first_analysis  # noqa: F401

QUOTE = {
    "session_id": "s1",
    "participant_id": "p1",
    "start_timecode": 10.0,
    "end_timecode": 18.0,
    "text": "Thanks for having me, it is good to be here.",
    "topic_label": "Welcome",
    "quote_type": "general_context",
    "researcher_context": None,
    "sentiment": "delight",
    "intensity": 2,
}
DOM_ID = "q-p1-10"


def _intermediate(out: Path) -> Path:
    return out / ".bristlenose" / "intermediate"


def _write_quotes(out: Path, quotes: list[dict]) -> None:
    (_intermediate(out) / "extracted_quotes.json").write_text(json.dumps(quotes), encoding="utf-8")


def _record_quoted(out: Path, *sids: str) -> None:
    m = load_manifest(out) or create_manifest("p", "0")
    for sid in sids:
        mark_session_complete(m, STAGE_QUOTE_EXTRACTION, sid)
    write_manifest(m, out)


class TestManifestReads:
    def test_under_redaction_readable_means_redacted(self) -> None:
        m = create_manifest("p", "0")
        mark_session_complete(m, STAGE_MERGE_TRANSCRIPT, "s1")
        mark_stage_running(m, STAGE_PII_REMOVAL)
        assert readable_in_manifest(m) == frozenset(), "unredacted files are not readable"
        mark_session_complete(m, STAGE_PII_REMOVAL, "s1")
        assert readable_in_manifest(m) == {"s1"}

    def test_quoted_is_quote_extraction_done(self) -> None:
        m = create_manifest("p", "0")
        assert quoted_in_manifest(m) == frozenset()
        mark_session_complete(m, STAGE_QUOTE_EXTRACTION, "s2")
        assert quoted_in_manifest(m) == {"s2"}


class TestQuotesDuringTheRun:
    def test_a_quoted_session_lights_the_quotes_lens_and_serves_its_quotes(
        self, first_analysis,  # noqa: F811
    ) -> None:
        project, out, client = first_analysis
        _record_readable(out, "s1")
        _follow(client, project)
        assert client.get("/api/projects/1/condition").json()["lenses"]["quotes"] is False

        _write_quotes(out, [QUOTE])
        _record_quoted(out, "s1")
        _follow(client, project)
        body = client.get("/api/projects/1/condition").json()
        assert body["lenses"]["quotes"] is True
        assert body["data_version"] == 2, "one move per import: sessions, then quotes"
        quotes = client.get("/api/projects/1/quotes").json()
        assert [q["dom_id"] for q in quotes["unjoined"]] == [DOM_ID]
        assert quotes["sections"] == [] and quotes["themes"] == []

    def test_a_session_with_no_quotes_does_not_light_the_lens(
        self, first_analysis,  # noqa: F811
    ) -> None:
        project, out, client = first_analysis
        _record_readable(out, "s1")
        _write_quotes(out, [])
        _record_quoted(out, "s1")
        _follow(client, project)
        assert client.get("/api/projects/1/condition").json()["lenses"]["quotes"] is False

    def test_quotes_wait_for_their_session(self, first_analysis) -> None:  # noqa: F811
        """A quote for a session not yet in the database is not imported."""
        project, out, client = first_analysis
        _write_quotes(out, [QUOTE])
        _record_quoted(out, "s1")
        _follow(client, project)
        assert client.get("/api/projects/1/quotes").json()["unjoined"] == []

    def test_curation_made_during_the_run_survives_the_whole_import(
        self, first_analysis,  # noqa: F811
    ) -> None:
        from bristlenose.server.importer import import_project

        project, out, client = first_analysis
        _record_readable(out, "s1")
        _write_quotes(out, [QUOTE])
        _record_quoted(out, "s1")
        _follow(client, project)
        assert client.put("/api/projects/1/starred", json={DOM_ID: True}).status_code == 200
        assert client.put("/api/projects/1/tags", json={DOM_ID: ["first impression"]}).status_code == 200

        # The run ends: the quote joins a section, and the whole import runs.
        inter = _intermediate(out)
        (inter / "screen_clusters.json").write_text(json.dumps([{
            "screen_label": "Welcome", "description": "", "display_order": 1, "quotes": [QUOTE],
        }]), encoding="utf-8")
        (inter / "theme_groups.json").write_text("[]", encoding="utf-8")
        client.app.state.progress = None
        db = client.app.state.db_factory()
        try:
            import_project(db, project)
        finally:
            db.close()

        quotes = client.get("/api/projects/1/quotes").json()
        assert quotes["unjoined"] == [], "served only during the run"
        (got,) = [q for s in quotes["sections"] for q in s["quotes"]]
        assert got["dom_id"] == DOM_ID
        assert got["is_starred"] is True
        assert "first impression" in {t["name"] for t in got["tags"]}


def test_extract_quotes_hands_each_session_over_as_it_succeeds() -> None:
    """``on_session_done`` fires per succeeded session, zero quotes included,
    and never for a failed one."""
    import asyncio
    from unittest.mock import patch

    from bristlenose.models import PiiCleanTranscript
    from bristlenose.stages.s09_quote_extraction import extract_quotes

    def _t(sid: str) -> PiiCleanTranscript:
        return PiiCleanTranscript.model_construct(session_id=sid, participant_id="p1", segments=[])

    async def _one(transcript, *_a, **_kw):
        if transcript.session_id == "s3":
            raise RuntimeError("model refused")
        return [] if transcript.session_id == "s2" else ["q"]

    seen: list[tuple[str, int]] = []
    client = type("C", (), {"provider": "anthropic"})()
    with patch("bristlenose.stages.s09_quote_extraction._extract_with_split", new=_one):
        asyncio.run(extract_quotes(
            [_t("s1"), _t("s2"), _t("s3")], [], client,  # type: ignore[arg-type]
            on_session_done=lambda sid, qs: seen.append((sid, len(qs))),
        ))
    assert sorted(seen) == [("s1", 1), ("s2", 0)]


def test_sessions_of_one_first_analysis_are_not_new_to_each_other(first_analysis) -> None:  # noqa: F811
    """Sessions delivered one by one share the run's stamp, so the run's own
    second session is not flagged New against its first (R2)."""
    import time

    from bristlenose.server.importer import import_project
    from tests.test_progressive_lenses import _add_session

    project, out, client = first_analysis
    _record_readable(out, "s1")
    _follow(client, project)
    time.sleep(0.01)
    _add_session(project, "s2", "p2", "21")
    _record_readable(out, "s2")
    _follow(client, project)
    assert client.get("/api/projects/1/quotes").json()["new_since"] is None

    inter = _intermediate(out)
    (inter / "screen_clusters.json").write_text("[]", encoding="utf-8")
    (inter / "theme_groups.json").write_text("[]", encoding="utf-8")
    client.app.state.progress = None
    db = client.app.state.db_factory()
    try:
        import_project(db, project)
    finally:
        db.close()
    assert client.get("/api/projects/1/quotes").json()["new_since"] is None


def test_a_serve_restarted_mid_run_does_not_make_the_run_new_to_itself(
    first_analysis,  # noqa: F811
) -> None:
    """A second serve imports the rest of the run under the run's own stamp; the
    whole import at the end makes the first analysis one generation, a session it
    creates itself included."""
    import asyncio
    import time
    from datetime import datetime, timezone

    from bristlenose.events import (
        KindEnum,
        OutcomeEnum,
        RunCompletedEvent,
        append_event,
        events_path,
    )
    from bristlenose.server.app import _make_run_completed_handler
    from tests.test_progressive_lenses import _add_session

    project, out, client = first_analysis
    _record_readable(out, "s1")
    _follow(client, project)
    client.app.state.__dict__.pop("_test_follower")  # a new serve's follower
    time.sleep(0.01)
    _add_session(project, "s2", "p2", "21")
    _record_readable(out, "s2")
    _follow(client, project)
    assert client.get("/api/projects/1/quotes").json()["new_since"] is None

    time.sleep(0.01)
    _add_session(project, "s3", "p3", "22")  # never delivered during the run
    inter = _intermediate(out)
    (inter / "screen_clusters.json").write_text("[]", encoding="utf-8")
    (inter / "theme_groups.json").write_text("[]", encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()
    done = RunCompletedEvent(ts=now, run_id="RUN1", kind=KindEnum.RUN, started_at=now,
                             ended_at=now, outcome=OutcomeEnum.COMPLETED)
    append_event(events_path(out), done)
    _follow(client, project)
    handler = _make_run_completed_handler(client.app, client.app.state.db_factory, project)
    asyncio.run(handler(done))
    assert client.app.state.progress is None
    assert client.get("/api/projects/1/quotes").json()["new_since"] is None


def test_the_tapestry_draws_what_exists_during_the_run(first_analysis) -> None:  # noqa: F811
    """Phase 4 item 2: turns with the transcript, quotes with no section or theme
    once quoted, and no sections until the barrier — no schema change."""
    project, out, client = first_analysis
    _record_readable(out, "s1")
    _follow(client, project)
    (s1,) = client.get("/api/projects/1/tapestry").json()["sessions"]
    assert s1["turns"], "turns arrive with the transcript"
    assert s1["sections"] == [] and s1["quotes"] == []

    _write_quotes(out, [QUOTE])
    _record_quoted(out, "s1")
    _follow(client, project)
    (s1,) = client.get("/api/projects/1/tapestry").json()["sessions"]
    assert s1["sections"] == []
    (q,) = s1["quotes"]
    assert q["section"] is None and q["theme"] is None


def test_quotes_stay_served_when_the_run_ends_without_the_whole_import(
    first_analysis,  # noqa: F811
) -> None:
    """A first analysis that fails or is stopped after extraction leaves its quotes
    join-less: the researcher was reading them By session, and they stay."""
    project, out, client = first_analysis
    _record_readable(out, "s1")
    _write_quotes(out, [QUOTE])
    _record_quoted(out, "s1")
    _follow(client, project)
    client.app.state.progress = None  # what follow() does once the run is not in progress
    assert [q["dom_id"] for q in client.get("/api/projects/1/quotes").json()["unjoined"]] == [DOM_ID]


def test_the_previous_runs_manifest_is_not_this_runs(first_analysis) -> None:  # noqa: F811
    """Until the pipeline first writes its manifest (after ingest), the file on disk
    is the previous run's. Its sessions — maybe unredacted, maybe re-transcribed to
    new timecodes — are not imported as this run's."""
    project, out, client = first_analysis
    _record_readable(out, "s1")
    m = load_manifest(out)
    assert m is not None
    m.created_at = "2020-01-01T00:00:00+00:00"
    write_manifest(m, out)
    _follow(client, project)
    assert client.get("/api/projects/1/condition").json()["data_version"] == 0, "nothing imported"

    m.created_at = create_manifest("p", "0").created_at  # the run writes its own
    write_manifest(m, out)
    _follow(client, project)
    assert client.get("/api/projects/1/condition").json()["data_version"] == 1


def test_an_intermediate_write_survives_a_replace_windows_refuses(tmp_path: Path) -> None:
    """Windows will not replace a file the server has open: the write retries,
    then falls back to writing in place, and leaves no temp file."""
    from unittest.mock import patch

    from bristlenose.stages.s12_render_output import write_intermediate_json

    target = tmp_path / ".bristlenose" / "intermediate"
    target.mkdir(parents=True)
    with patch("pathlib.Path.replace", side_effect=PermissionError("in use")), \
            patch("bristlenose.stages.s12_render_output.time.sleep"):
        path = write_intermediate_json([{"a": 1}], "extracted_quotes.json", tmp_path)
    assert json.loads(path.read_text(encoding="utf-8")) == [{"a": 1}]
    assert list(path.parent.glob("*.tmp")) == []
