"""``bristlenose status`` shows "Last run" on this machine's clock (N155).

The manifest stores ``updated_at`` in UTC; the header printed it with the UTC
hour and no zone, so a London researcher saw 08:00 for a run that ended at 09:00
in British summer time. The day was also formatted with ``%-d``, a glibc/BSD
extension that raises ValueError on Windows, which the surrounding except turned
into the raw ISO string.
"""

from __future__ import annotations

import pytest

from bristlenose import cli
from bristlenose.status import ProjectStatus


def _last_run_line(capsys: pytest.CaptureFixture[str], stamp: str) -> str:
    cli._print_project_status(
        ProjectStatus(project_name="P", pipeline_version="0", last_run=stamp, stages=[])
    )
    out = capsys.readouterr().out
    return next(ln.strip() for ln in out.splitlines() if "Last run" in ln)


@pytest.mark.usefixtures("london")
class TestLastRunIsLocal:
    def test_summer_time_adds_the_hour(self, capsys: pytest.CaptureFixture[str]) -> None:
        line = _last_run_line(capsys, "2026-07-07T08:00:00+00:00")
        assert line == "Last run: 7 Jul 2026 09:00"

    def test_winter_time_is_unchanged(self, capsys: pytest.CaptureFixture[str]) -> None:
        line = _last_run_line(capsys, "2026-12-12T08:00:00+00:00")
        assert line == "Last run: 12 Dec 2026 08:00"

    def test_the_local_day_can_differ_from_the_utc_day(
        self, capsys: pytest.CaptureFixture[str],
    ) -> None:
        line = _last_run_line(capsys, "2026-07-07T23:30:00+00:00")
        assert line == "Last run: 8 Jul 2026 00:30"

    def test_a_stamp_that_will_not_parse_is_shown_as_written(
        self, capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert _last_run_line(capsys, "not a date") == "Last run: not a date"
