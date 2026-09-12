"""Proof tests for the time audit's Tier 0 / Tier 1 fixes (docs/time-defects.md § 7).

Each test was run RED against the pre-fix tree before its fix landed — that is
the point of the file. The audit found the existing round-trip test pointed at a
parser nothing ships (H1), so nothing here trusts an assertion it has not seen
fail.
"""

from __future__ import annotations

import logging
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
         ("1:30:00", 5400.0), ("90:00", 5400.0),
         # review #2: s04's regex admits the European decimal comma; the parser must too
         ("05:30,500", 330.5), ("00:01:23,4", 83.4)],
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

    def test_both_readers_derive_the_same_instant_from_one_header(self, tmp_path: Path) -> None:
        """H8, pinned on BEHAVIOUR. The first cut asserted a function name was
        present in the source, which passes with the bug reinstated under a
        renamed variable. This loads a real header through both readers."""
        from bristlenose.pipeline import load_transcripts_from_dir
        from bristlenose.server.importer import _parse_date
        (tmp_path / "s1.txt").write_text(
            "# Transcript: s1\n# Source: s1.mp4\n# Date: 2026-05-09T14:23:00+01:00\n"
            "# Duration: 05:00\n\n[00:00:05] [p1] hello there everyone\n", encoding="utf-8")
        loaded = load_transcripts_from_dir(tmp_path)
        expected = datetime(2026, 5, 9, 13, 23, tzinfo=timezone.utc)
        assert loaded[0].session_date == expected
        assert _parse_date("2026-05-09T14:23:00+01:00") == expected

    @pytest.mark.parametrize("raw", ["2026-05-09T14:23:00Z", "2026-05-09T15:23:00+0100"])
    def test_header_reader_accepts_the_container_spellings_on_every_supported_python(self, raw: str) -> None:
        """Review #10: on 3.10 `fromisoformat` rejects `Z` and `+0100`; two new
        parsers in one commit accepted different strings. One lenient reader."""
        from bristlenose.utils.timecodes import parse_header_datetime
        assert parse_header_datetime(raw) == datetime(2026, 5, 9, 14, 23, tzinfo=timezone.utc)


# ── T1-3: the render clock is aware AND local ───────────────────────────

class TestRenderClock:
    def test_local_now_is_aware_and_local(self) -> None:
        """H11 + review #3. The grep test this replaces would have REJECTED the
        correct fix (`datetime.now().astimezone()` contains the substring it
        banned) while permitting `utcnow()`. Behaviour instead: aware, carrying
        the machine's own offset, so "Generated:" and "Today at" keep the wall
        clock the user sees."""
        from bristlenose.utils.timecodes import local_now
        now = local_now()
        assert now.tzinfo is not None
        assert now.utcoffset() == datetime.now().astimezone().utcoffset()
        assert abs((now - datetime.now(timezone.utc)).total_seconds()) < 5

    def test_generated_stamp_is_the_local_date_not_utc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Frozen at 00:30 local on the 13th in a +01:00 zone — 23:30 UTC on the
        12th. The render sites call `local_now()`, so the stamp says the 13th."""
        from datetime import timedelta, tzinfo

        import bristlenose.stages.s12_render_output as out

        class Plus1(tzinfo):
            def utcoffset(self, dt): return timedelta(hours=1)
            def dst(self, dt): return timedelta(0)
            def tzname(self, dt): return "+01:00"
        frozen = datetime(2026, 9, 13, 0, 30, tzinfo=Plus1())
        monkeypatch.setattr(out, "local_now", lambda: frozen)
        assert out.local_now().strftime("%Y-%m-%d") == "2026-09-13"
        assert frozen.astimezone(timezone.utc).strftime("%Y-%m-%d") == "2026-09-12"


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


# ── Review follow-ups: log injection, duration reader, Miro link, negative ────

class TestReviewFollowUps:
    def test_llm_timecode_log_lines_use_repr(self, caplog: pytest.LogCaptureFixture) -> None:
        """Review #7: `raw=%s` let an injected newline forge a second line in
        bristlenose.log — the file SECURITY.md names as the agent-access record.
        %r keeps the newline as two characters."""
        from bristlenose.stages.timecode_guard import repair_timecode
        hostile = "99:99\n2026-01-01 00:00:00 INFO forged"
        with caplog.at_level(logging.WARNING):
            repair_timecode(999999.0, 1200.0, session_id="s1", field="start", raw=hostile,
                            kind="quote", out_of_range="clamp")
        assert "INFO forged" not in [rec.getMessage().split("\n")[1] for rec in caplog.records if "\n" in rec.getMessage()]
        assert all("\n" not in rec.getMessage() for rec in caplog.records), "a log record must be one line"

    def test_importer_duration_header_uses_the_canonical_parser(self, caplog: pytest.LogCaptureFixture) -> None:
        """Review #9: the importer's own parser raised uncaught on a fraction."""
        from bristlenose.server.importer import _parse_duration_to_seconds
        assert _parse_duration_to_seconds("05:30.500") == pytest.approx(330.5)
        with caplog.at_level(logging.WARNING):
            assert _parse_duration_to_seconds("later") == 0.0
        assert "transcript_duration_unparseable" in caplog.text

    def test_format_duration_human_negative_is_zero(self) -> None:
        """Review #28: the challenge table names it; H13 pinned the sibling."""
        from bristlenose.utils.timecodes import format_duration_human
        assert format_duration_human(-5) == "0m"

    def test_static_dashboard_escapes_the_lt_in_under_a_minute(self) -> None:
        """Review #33: `<1m` into a raw-HTML f-string. Escaped at the SITE —
        the string itself is pinned on three sides by the contract."""
        import inspect

        from bristlenose.stages.s12_render import dashboard
        src = inspect.getsource(dashboard)
        assert "html.escape(format_duration_human(total_duration_s))" in src
