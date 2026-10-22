"""A quote the researcher hid counts nowhere (owner, 22 Oct 2026; R73, R99).

Hiding a quote discounts it as evidence. Signals (all three lenses), the
per-session sentiment bars (Sessions lens and Dashboard), the Dashboard's
featured quotes and the clip export leave it out, as the
chat lens and MCP already did (``grounding.load_signals``). The Quotes lens
still returns it, so it can be unhidden, and quote coverage still counts it,
because coverage measures what was extracted, not what is evidence.

Smoke fixture: one participant, four quotes. ``q-p1-10`` (confusion) and
``q-p1-26`` (frustration) are in Dashboard, ``q-p1-46`` (delight) in Search,
``q-p1-66`` (frustration) in the Onboarding theme.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import (
    AutoCodeJob,
    ClusterQuote,
    ProposedTag,
    Quote,
    TagDefinition,
)
from bristlenose.server.routes import clips_export
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_ALL = ("q-p1-10", "q-p1-26", "q-p1-46", "q-p1-66")


@pytest.fixture()
def client() -> TestClient:
    clips_export._jobs.clear()
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


def _hide(client: TestClient, *ids: str, hidden: bool = True) -> None:
    resp = client.patch("/api/projects/1/hidden", json=dict.fromkeys(ids, hidden))
    assert resp.status_code == 200 and resp.json()["unresolved"] == []


def _grand_total(client: TestClient, lens: str) -> int:
    data = client.get(f"/api/projects/1/signals/{lens}").json()
    if lens == "codebooks":
        (sentiment,) = [c for c in data["codebooks"] if c["codebook_id"] == "sentiment"]
        return sentiment["section_matrix"]["grand_total"]
    matrix = data.get("section_matrix") or data["sectionMatrix"]
    return matrix.get("grand_total", matrix.get("grandTotal"))


class TestSignals:
    @pytest.mark.parametrize("lens", ["sentiment", "tags", "codebooks"])
    def test_a_hidden_quote_leaves_the_grid_and_comes_back_when_unhidden(
        self, client: TestClient, lens: str,
    ) -> None:
        assert _grand_total(client, lens) == 3
        _hide(client, "q-p1-10")
        assert _grand_total(client, lens) == 2
        _hide(client, "q-p1-10", hidden=False)
        assert _grand_total(client, lens) == 3

    def test_a_hidden_quote_is_not_listed_on_its_card(self, client: TestClient) -> None:
        def card_starts() -> list[float]:
            data = client.get("/api/projects/1/signals/tags").json()
            return [q["start_seconds"] for s in data["signals"] for q in s["quotes"]]

        assert 10.0 in card_starts()
        _hide(client, "q-p1-10")
        assert 10.0 not in card_starts()

    @pytest.mark.parametrize("lens", ["tags", "codebooks"])
    def test_the_tags_a_card_is_based_on_leave_out_a_hidden_quote(
        self, client: TestClient, lens: str,
    ) -> None:
        """The "based on N tags" footer counts the same quotes as the grid."""

        def breakdown() -> dict[str, int]:
            data = client.get(f"/api/projects/1/signals/{lens}").json()
            if lens == "codebooks":
                (data,) = [c for c in data["codebooks"] if c["codebook_id"] == "sentiment"]
            return data["source_breakdown"]

        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:  # a pending proposal on the quote about to be hidden
            quote = db.query(Quote).filter_by(project_id=1, participant_id="p1").filter(
                Quote.start_timecode >= 10, Quote.start_timecode < 11).one()
            delight = db.query(TagDefinition).filter_by(name="delight").one()
            job = AutoCodeJob(project_id=1, framework_id="sentiment", status="completed")
            db.add(job)
            db.flush()
            db.add(ProposedTag(job_id=job.id, quote_id=quote.id, tag_definition_id=delight.id,
                               confidence=0.8, rationale="test", status="pending"))
            db.commit()
        finally:
            db.close()

        assert breakdown() == {"accepted": 4, "pending": 1, "total": 5}
        _hide(client, "q-p1-10")
        assert breakdown() == {"accepted": 3, "pending": 0, "total": 3}

    def test_a_participant_whose_quotes_are_all_hidden_is_not_counted(
        self, client: TestClient,
    ) -> None:
        """p2 says one thing, in the Dashboard section; hiding it leaves p1 alone."""
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            first = db.query(Quote).filter_by(project_id=1).order_by(Quote.start_timecode).first()
            cluster = db.query(ClusterQuote).filter_by(quote_id=first.id).one().cluster_id
            q = Quote(project_id=1, session_id=first.session_id, participant_id="p2",
                      start_timecode=120.0, end_timecode=125.0, text="Another view",
                      quote_type=first.quote_type, sentiment="frustration", intensity=2)
            db.add(q)
            db.flush()
            db.add(ClusterQuote(cluster_id=cluster, quote_id=q.id))
            db.commit()
        finally:
            db.close()

        def totals() -> dict[str, int]:
            out = {}
            for lens in ("sentiment", "tags", "codebooks"):
                data = client.get(f"/api/projects/1/signals/{lens}").json()
                out[lens] = data.get("total_participants", data.get("totalParticipants"))
            return out

        assert totals() == {"sentiment": 2, "tags": 2, "codebooks": 2}
        _hide(client, "q-p2-120")
        assert totals() == {"sentiment": 1, "tags": 1, "codebooks": 1}


class TestDashboard:
    def test_sentiment_bars_leave_out_a_hidden_quote(self, client: TestClient) -> None:
        def counts() -> dict[str, int]:
            return client.get("/api/projects/1/dashboard").json()["sessions"][0][
                "sentiment_counts"
            ]

        assert counts() == {"confusion": 1, "frustration": 2, "delight": 1}
        _hide(client, "q-p1-10", "q-p1-26")
        assert counts() == {"frustration": 1, "delight": 1}

    def test_the_sessions_lens_bars_leave_out_a_hidden_quote(self, client: TestClient) -> None:
        """The bars a researcher sees are the Sessions lens row's sparkline (/sessions)."""

        def counts() -> dict[str, int]:
            return client.get("/api/projects/1/sessions").json()["sessions"][0][
                "sentiment_counts"
            ]

        assert counts() == {"confusion": 1, "frustration": 2, "delight": 1}
        _hide(client, "q-p1-10", "q-p1-26")
        assert counts() == {"frustration": 1, "delight": 1}

    def test_a_hidden_quote_is_never_featured(self, client: TestClient) -> None:
        def featured() -> list[str]:
            return [q["dom_id"] for q in
                    client.get("/api/projects/1/dashboard").json()["featured_quotes"]]

        assert "q-p1-10" in featured()
        _hide(client, "q-p1-10")
        assert "q-p1-10" not in featured() and featured()

    def test_coverage_still_counts_a_hidden_quote(self, client: TestClient) -> None:
        """Coverage is how much of the transcript was extracted, not evidence."""
        before = client.get("/api/projects/1/dashboard").json()["coverage"]
        assert before is not None and before["pct_in_report"] > 0
        _hide(client, *_ALL)
        assert client.get("/api/projects/1/dashboard").json()["coverage"] == before

    def test_the_quotes_lens_still_returns_a_hidden_quote(self, client: TestClient) -> None:
        """So it can be unhidden: ``evidence_quotes`` itself is unchanged."""
        _hide(client, "q-p1-10")
        data = client.get("/api/projects/1/quotes").json()
        ids = [
            q["dom_id"]
            for group in (*data["sections"], *data["themes"])
            for q in group["quotes"]
        ]
        assert "q-p1-10" in ids


async def _no_job(*_args: object, **_kwargs: object) -> None:
    """The manifest is the evidence; cutting the clips is another test's job."""


class TestClips:
    @staticmethod
    def _clipped(client: TestClient, tmp_path: Path, body: dict | None) -> list[str]:
        clips_export._jobs.clear()  # each call is a fresh export, not a second one
        built: list[list[str]] = []
        real_build = clips_export.build_clip_manifest

        def spy(*args, **kwargs):  # type: ignore[no-untyped-def]
            specs = real_build(*args, **kwargs)
            built.append([s.quote_id for s in specs])
            return specs

        media = ({"s1": (tmp_path / "s1.mp4", False)}, {"s1": 300.0})
        with patch.object(clips_export.FFmpegBackend, "check_available", return_value=(True, "")), \
                patch.object(clips_export, "_load_session_media", return_value=media), \
                patch.object(clips_export, "build_clip_manifest", spy), \
                patch.object(clips_export, "_run_clip_extraction", _no_job):
            resp = client.post("/api/projects/1/export/clips", json=body)
        assert resp.status_code == 200
        assert len(built) == 1
        return built[0]

    def test_a_starred_quote_that_is_hidden_is_not_clipped(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        """Hiding doesn't clear a star; the legacy no-scope export unions stars (R73)."""
        assert client.patch("/api/projects/1/starred", json={"q-p1-10": True}).status_code == 200
        assert "q-p1-10" in self._clipped(client, tmp_path, None)
        _hide(client, "q-p1-10")
        assert "q-p1-10" not in self._clipped(client, tmp_path, None)

    def test_a_hidden_quote_named_by_the_picker_is_not_clipped(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        _hide(client, "q-p1-10")
        assert self._clipped(client, tmp_path, {"ids": ["q-p1-10", "q-p1-26"]}) == ["q-p1-26"]

    def test_a_hidden_quote_is_never_picked_as_a_featured_clip(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        _hide(client, "q-p1-10", "q-p1-26", "q-p1-46")
        assert self._clipped(client, tmp_path, None) == ["q-p1-66"]
