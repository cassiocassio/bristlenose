"""Proof tests for the time audit's Tier 0 / Tier 1 fixes (docs/time-defects.md § 7).

Each test was run RED against the pre-fix tree before its fix landed — that is
the point of the file. The audit found the existing round-trip test pointed at a
parser nothing ships (H1), so nothing here trusts an assertion it has not seen
fail.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.utils.timecodes import format_timecode, format_timecode_prompt, parse_timecode

ROOT = Path(__file__).resolve().parents[1]


# ── T0-1: one parser, and the domain declared ─────────────────────────────

class TestOneParser:
    def test_models_no_longer_exports_a_second_parser(self) -> None:
        """H1: `models.parse_timecode` had zero production callers and disagreed
        with the canonical parser on 5 of 14 inputs; the round-trip test was
        pointed at it. Gone means the test cannot be pointed at it again."""
        with pytest.raises(ImportError):
            from bristlenose.models import parse_timecode  # noqa: F401

    def test_domain_ceiling_is_declared_not_implicit(self) -> None:
        """H2: the formatter emits `100:00:00`; the parser refuses it. Pin the
        edge so it is a stated limit rather than a surprise."""
        assert format_timecode(360000) == "100:00:00"
        with pytest.raises(ValueError):
            parse_timecode("100:00:00")


# ── T0-2: fullmatch ───────────────────────────────────────────────────────

class TestParserRefusesTrailingText:
    @pytest.mark.parametrize("bad", ["00:01:23 extra", "05:30 (approx)", "1:00:00,"])
    def test_trailing_garbage_is_refused(self, bad: str) -> None:
        """H4: `re.match` accepted a prefix and returned a plausible number."""
        with pytest.raises(ValueError):
            parse_timecode(bad)

    @pytest.mark.parametrize(
        ("good", "secs"),
        [("00:01:23,456", 83.456), ("00:01:23.456", 83.456), ("  05:30  ", 330.0),
         ("1:30:00", 5400.0), ("90:00", 5400.0)],
    )
    def test_every_legitimate_shape_still_parses(self, good: str, secs: float) -> None:
        assert parse_timecode(good) == pytest.approx(secs)


# ── T0-3: Miro renders the house format and parses it back ────────────────

class TestMiroTimecodes:
    def test_fmt_timecode_rolls_into_hours(self) -> None:
        """H5: overflowed minutes (`100:00`) and was unparseable from 100 min —
        the corpus's longest session is 99.7 min."""
        from bristlenose.miro_board import fmt_timecode
        assert fmt_timecode(6000) == "1:40:00"
        assert fmt_timecode(330) == "05:30"
        assert parse_timecode(fmt_timecode(6000)) == 6000.0

    def test_export_parser_reads_fractional_seconds(self) -> None:
        """`miro_export._parse_timecode` returned 0.0 for ANY failure,
        including a VTT-style fractional second."""
        from bristlenose.server.miro_export import _parse_timecode
        assert _parse_timecode("00:01:23.456") == pytest.approx(83.456)
        assert _parse_timecode("1:40:00") == 6000.0


# ── T0-4 / T0-5: one duration formatter ───────────────────────────────────

class TestOneDurationFormatter:
    @pytest.mark.parametrize(("secs", "out"), [(0, "0m"), (30, "<1m"), (60, "1m"),
                                               (3600, "1h"), (3661, "1h 1m"), (66180, "18h 23m")])
    def test_utils_helper_is_the_canonical_shape(self, secs: float, out: str) -> None:
        """H7: the helper in the obvious module rendered `1 min` for 30 s and
        `1 h 0 min` for an hour, and the static dashboard used it."""
        from bristlenose.utils.timecodes import format_duration_human
        assert format_duration_human(secs) == out

    def test_route_delegates(self) -> None:
        from bristlenose.server.routes.dashboard import _format_duration_human
        from bristlenose.utils.timecodes import format_duration_human
        for v in (0, 30, 3600, 66180):
            assert _format_duration_human(v) == format_duration_human(v)

    def test_dev_route_stops_rendering_a_duration_as_a_timecode(self) -> None:
        from bristlenose.server.routes.dev import _format_duration
        assert _format_duration(66180) == "18h 23m"
        assert _format_duration(0) == "—"

    def test_cli_stage_timer_rolls_into_hours(self) -> None:
        """T0-6: `66180` rendered `1103m 00s`."""
        from bristlenose.pipeline import _format_duration
        assert _format_duration(0.1) == "0.1s"
        assert _format_duration(221) == "3m 41s"
        assert _format_duration(3661) == "1h 01m 01s"


# ── T0-8: round-trip over the whole declared domain ───────────────────────

class TestRoundTrip:
    def test_format_then_parse_is_identity_across_the_domain(self) -> None:
        """Would have caught H1 and H2. Stride of 7 covers every field
        boundary in ~51k cases well under a second."""
        for s in range(0, 360000, 7):
            assert int(parse_timecode(format_timecode(s))) == s
            assert int(parse_timecode(format_timecode_prompt(s))) == s

    def test_edges(self) -> None:
        assert format_timecode(3599.9) == "59:59"       # truncate, never round up
        assert format_timecode(-1) == "00:00"           # clamp


# ── T1-1: one header-date reader, converting not relabelling ──────────────

class TestHeaderDate:
    def test_offset_is_converted_not_overwritten(self) -> None:
        """H8: `pipeline.py` did `.replace(tzinfo=utc)` on an aware value —
        a BST header was stored an hour late — while `importer.py` got it
        right. One helper, both sites."""
        from bristlenose.utils.timecodes import parse_header_datetime
        dt = parse_header_datetime("2026-05-09T14:23:00+01:00")
        assert dt == datetime(2026, 5, 9, 13, 23, tzinfo=timezone.utc)

    def test_naive_means_utc_by_documented_decision(self) -> None:
        from bristlenose.utils.timecodes import parse_header_datetime
        assert parse_header_datetime("2026-05-09T14:23:00") == datetime(2026, 5, 9, 14, 23, tzinfo=timezone.utc)
        assert parse_header_datetime("2026-05-09") == datetime(2026, 5, 9, tzinfo=timezone.utc)
        assert parse_header_datetime("not a date") is None

    def test_both_readers_use_it(self) -> None:
        """Source-level: the relabelling idiom must not survive at either site."""
        for rel in ("bristlenose/pipeline.py", "bristlenose/server/importer.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            assert "parse_header_datetime" in src, rel
        pipeline = (ROOT / "bristlenose/pipeline.py").read_text(encoding="utf-8")
        assert "fromisoformat(date_str).replace(tzinfo=timezone.utc)" not in pipeline


# ── T1-3: no naive now() at the render sites ──────────────────────────────

class TestNoNaiveNow:
    @pytest.mark.parametrize("rel", [
        "bristlenose/stages/s12_render_output.py",
        "bristlenose/stages/s12_render/report.py",
        "bristlenose/utils/markdown.py",
    ])
    def test_render_sites_use_aware_now(self, rel: str) -> None:
        """H11: naive `now()` beside an aware session_date is a latent
        TypeError and the mechanism behind the UTC-vs-local fork."""
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"datetime\.now\(\)", src), f"bare datetime.now() in {rel}"


# ── T1-2: unpadded fields are refused, by measurement ─────────────────────

class TestUnpaddedIsRefused:
    @pytest.mark.parametrize("bad", ["1:2:3", "5:3", "00:01:2"])
    def test_unpadded_seconds_are_refused(self, bad: str) -> None:
        """H3, closed as by-design. Measured 12 Sep 2026 over 344 real
        transcript-like files (.txt/.md/.srt/.vtt/.docx): zero unpadded
        timecodes; the seven regex hits were Stephanus citations in Plato
        texts. No export produces this shape, so refusing it is the contract."""
        with pytest.raises(ValueError):
            parse_timecode(bad)
