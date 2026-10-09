"""`bristlenose doctor` exits non-zero when a check fails.

Until 9 Oct 2026 it printed ✗ rows and exited 0 regardless, so every script
and CI step that ran it (`bristlenose doctor || true` in install-test.yml)
was checking nothing. Warnings and notes stay exit 0: they are advice, not
something that stops a run.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from bristlenose.cli import app
from bristlenose.doctor import CheckResult, CheckStatus, DoctorReport

runner = CliRunner()


def _report(*statuses: CheckStatus) -> DoctorReport:
    return DoctorReport(results=[
        CheckResult(status=s, label=f"check {i}", detail="d") for i, s in enumerate(statuses)
    ])


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((CheckStatus.OK, CheckStatus.OK), 0),
        ((CheckStatus.OK, CheckStatus.SKIP), 0),
        ((CheckStatus.OK, CheckStatus.WARN), 0),
        ((CheckStatus.OK, CheckStatus.FAIL), 1),
        ((CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.FAIL), 1),
    ],
)
def test_doctor_exit_code_follows_failures(statuses: tuple[CheckStatus, ...], expected: int) -> None:
    with (
        patch("bristlenose.doctor.run_all", return_value=_report(*statuses)),
        patch("bristlenose.cli._maybe_offer_mlx_install", return_value=False),
        patch("bristlenose.cli._print_doctor_fixes"),
        patch("bristlenose.cli._write_doctor_sentinel") as sentinel,
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == expected, result.output
    # The sentinel records that doctor ran, whatever it found.
    sentinel.assert_called_once()
