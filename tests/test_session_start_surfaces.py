"""The start time on its way out: database refresh, the wire, and the renderer.

The database column has no timezone, so SQLite returns a naive value — UTC by
construction. Emitted bare, both clients read it as LOCAL (`new Date()` and
Swift's `SessionsFinderDate.parse`), and every start rendered an hour early
through BST (design-timezones § 1, T1). No test asserted the emitted form,
which is how that survived.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bristlenose.server.app import create_app
from bristlenose.server.db import create_session_factory, get_engine, init_db
from bristlenose.server.importer import import_project
from bristlenose.server.models import Session as SessionModel
from bristlenose.utils.markdown import format_finder_date
from bristlenose.utils.timecodes import iso_utc, parse_header_datetime
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
UTC = timezone.utc


class TestIsoUtc:
    def test_naive_is_read_as_utc_and_marked(self) -> None:
        assert iso_utc(datetime(2026, 7, 21, 9, 0)) == "2026-07-21T09:00:00+00:00"

    def test_aware_is_converted_to_utc(self) -> None:
        bst = timezone(timedelta(hours=1))
        assert iso_utc(datetime(2026, 7, 21, 10, 0, tzinfo=bst)) == "2026-07-21T09:00:00+00:00"

    def test_none(self) -> None:
        assert iso_utc(None) is None


class TestTheWire:
    @pytest.fixture()
    def client(self):
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        return AuthTestClient(app)

    @pytest.mark.parametrize("route", ["sessions", "dashboard"])
    def test_session_date_says_it_is_utc(self, london, client, route: str) -> None:
        session = client.get(f"/api/projects/1/{route}").json()["sessions"][0]
        # The smoke fixture's header is "# Date: 2026-01-20": local midnight,
        # which in London in January is UTC midnight.
        assert session["session_date"] == "2026-01-20T00:00:00+00:00"


class TestDateOnlyHeaders:
    """A date with no time names a day. As UTC midnight it read as the evening
    before to anyone west of London once the wire marked it UTC."""

    def test_a_summer_day_is_local_midnight(self, london) -> None:
        assert parse_header_datetime("2026-07-20") == datetime(2026, 7, 19, 23, 0, tzinfo=UTC)

    def test_new_york_keeps_its_day(self, pin_local_zone) -> None:
        est = timezone(timedelta(hours=-5))  # New York in January
        pin_local_zone(est)
        at = parse_header_datetime("2026-01-20")
        assert at == datetime(2026, 1, 20, 5, 0, tzinfo=UTC)
        assert at.astimezone(est).day == 20

    def test_a_full_naive_value_still_means_utc(self, london) -> None:
        assert parse_header_datetime("2026-07-20T10:00:00") == datetime(2026, 7, 20, 10, 0, tzinfo=UTC)


class TestImporterRefresh:
    def test_a_rerun_with_a_better_start_reaches_the_database(
        self, london, tmp_path: Path
    ) -> None:
        project = tmp_path / "input"
        shutil.copytree(_FIXTURE_DIR, project)
        transcript = project / "bristlenose-output" / "transcripts-raw" / "s1.txt"

        engine = get_engine("sqlite://")
        init_db(engine)
        db = create_session_factory(engine)()
        try:
            import_project(db, project)
            db.commit()
            first = db.query(SessionModel).one().session_date
            assert first is not None and (first.hour, first.minute) == (0, 0)

            text = transcript.read_text(encoding="utf-8")
            assert "# Date: 2026-01-20\n" in text
            transcript.write_text(
                text.replace("# Date: 2026-01-20\n", "# Date: 2026-01-20T09:30:00+00:00\n"),
                encoding="utf-8",
            )
            import_project(db, project)
            db.commit()
            again = db.query(SessionModel).one().session_date
            assert again is not None and (again.hour, again.minute) == (9, 30)
        finally:
            db.close()


class TestRenderer:
    def test_an_aware_summer_start_shows_on_the_local_clock(self, london) -> None:
        dt = datetime(2026, 7, 21, 9, 0, tzinfo=UTC)
        now = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
        assert format_finder_date(dt, now=now) == "21 Jul 2026 at 10:00"

    def test_a_winter_start_is_not_moved_by_a_summer_now(self, london) -> None:
        # local_now() carries today's fixed offset; converting with it would
        # put a December session an hour out.
        dt = datetime(2026, 12, 8, 10, 0, tzinfo=UTC)
        now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone(timedelta(hours=1)))
        assert format_finder_date(dt, now=now) == "8 Dec 2026 at 10:00"

    def test_naive_values_keep_the_legacy_contract(self, london) -> None:
        dt = datetime(2026, 7, 21, 9, 0)
        now = datetime(2026, 8, 1, 12, 0)
        assert format_finder_date(dt, now=now) == "21 Jul 2026 at 09:00"
