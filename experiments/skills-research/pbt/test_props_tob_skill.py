"""Property-based tests for bristlenose.utils.timecodes and text.slugify/safe_filename."""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from bristlenose.utils.text import safe_filename, slugify
from bristlenose.utils.timecodes import (  # noqa: I001
    format_duration_human, format_timecode, format_timecode_ms, format_timecode_prompt,
    local_now, parse_header_datetime, parse_iso_lenient, parse_timecode, seconds_between,
)

settings.register_profile("props", max_examples=200, deadline=None)  # CI-sized budget
settings.load_profile("props")

# parse_timecode's declared domain: hours are 1-2 digits, so < 100 h.
MAX_TC = 99 * 3600 + 59 * 60 + 59
in_domain_secs = st.floats(min_value=0, max_value=MAX_TC + 0.999, allow_nan=False)
finite = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e9, max_value=1e9)

@given(in_domain_secs)
@example(0.0)
@example(3599.0)
@example(float(MAX_TC))
def test_format_timecode_roundtrips_to_whole_seconds(s):
    assert parse_timecode(format_timecode(s)) == int(s)


@given(finite)
@example(-0.5)
def test_format_timecode_clamps_negative_and_has_valid_fields(s):
    out = format_timecode(s)
    parts = [int(p) for p in out.split(":")]
    assert all(p >= 0 for p in parts)
    assert all(p < 60 for p in parts[1:])  # minutes and seconds
    if s < 3600:
        assert re.fullmatch(r"\d{2}:\d{2}", out)  # hours only when >= 1 h
    if s <= 0:
        assert out == "00:00"


@given(in_domain_secs)
def test_format_timecode_prompt_shape_and_agrees_with_display(s):
    out = format_timecode_prompt(s)
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", out)
    # Oracle against the sibling: same instant, only the padding differs.
    assert parse_timecode(out) == parse_timecode(format_timecode(s))


@given(in_domain_secs)
def test_format_timecode_ms_roundtrips_within_a_millisecond(s):
    out = format_timecode_ms(s)
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}\.\d{3}", out)
    assert abs(parse_timecode(out) - s) <= 0.0005 + 1e-9


@pytest.mark.xfail(
    strict=True,
    reason="format_timecode_ms rounds s%60 with :06.3f after flooring minutes, "
    "so 59.9996 renders '00:00:60.000' — not a valid HH:MM:SS.mmm",
)
@given(in_domain_secs)
@example(59.9996)
def test_format_timecode_ms_seconds_field_below_60(s):
    hh, mm, ss = format_timecode_ms(s).split(":")
    assert int(mm) < 60 and float(ss) < 60


@st.composite
def srt_like(draw):
    h = draw(st.integers(0, 99))
    m = draw(st.integers(0, 59))
    s = draw(st.integers(0, 59))
    ms = draw(st.text("0123456789", min_size=1, max_size=3))
    sep = draw(st.sampled_from([",", "."]))
    h_txt = f"{h:02d}" if draw(st.booleans()) else str(h)
    expected = h * 3600 + m * 60 + s + int(ms.ljust(3, "0")) / 1000
    return f"{h_txt}:{m:02d}:{s:02d}{sep}{ms}", expected


@given(srt_like(), st.sampled_from(["", " ", "\t", "\n", "  \r\n"]))
@example(("00:00:01,5", 1.5), "")
def test_parse_timecode_srt_value_and_whitespace_insensitive(pair, ws):
    tc, expected = pair
    assert math.isclose(parse_timecode(ws + tc + ws), expected, abs_tol=1e-9)


@given(srt_like(), st.text(min_size=1).filter(lambda t: t.strip() and not t[0].isspace()))
def test_parse_timecode_refuses_trailing_garbage(pair, junk):
    tc, _ = pair
    with pytest.raises(ValueError):
        parse_timecode(tc + " " + junk)


@given(st.text())
@example("1:2:3")
@example("100:00:00")
@example("")
def test_parse_timecode_only_raises_valueerror(tc):
    try:
        out = parse_timecode(tc)
    except ValueError:
        return
    assert out >= 0


@given(finite, finite, finite)
def test_seconds_between_algebra(a, b, c):
    assert seconds_between(a, a) == 0
    assert seconds_between(a, b) >= 0
    assert seconds_between(a, b) == 0 or seconds_between(b, a) == 0
    lo, mid, hi = sorted((a, b, c))
    total = seconds_between(lo, mid) + seconds_between(mid, hi)
    assert math.isclose(total, seconds_between(lo, hi), rel_tol=1e-9, abs_tol=1e-6)


def _minutes(out):
    """Read a duration_human string back as minutes ("0m" -> -1, "<1m" -> 0)."""
    if out in ("0m", "<1m"):
        return -1 if out == "0m" else 0
    m = re.fullmatch(r"(?:(\d+)h)?(?: ?(\d+)m)?", out)
    assert m and (m.group(1) or m.group(2)), out
    assert int(m.group(2) or 0) < 60
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


@given(st.floats(min_value=-1e6, max_value=1e8, allow_nan=False))
@example(30.0)
@example(3600.0)
@example(3780.0)
def test_format_duration_human_is_a_floor(s):
    out = format_duration_human(s)
    if s <= 0:
        assert out == "0m"
        return
    if out == "<1m":
        assert 0 < s < 60
        return
    shown = _minutes(out) * 60
    assert shown > 0 and shown <= s < shown + 60  # truncates, never rounds up


@given(st.floats(min_value=0, max_value=1e8), st.floats(min_value=0, max_value=1e8))
def test_format_duration_human_is_monotonic(a, b):
    a, b = sorted((a, b))
    assert _minutes(format_duration_human(a)) <= _minutes(format_duration_human(b))


def test_local_now_is_aware():  # no input domain: an example test, not a property
    now = local_now()
    assert now.utcoffset() is not None
    assert abs(now - datetime.now(timezone.utc)) < timedelta(seconds=5)


# Offsets in whole minutes: the docstring's colon-less shape is ``+0100``.
offsets = st.integers(-23 * 60 - 59, 23 * 60 + 59).map(
    lambda mins: timezone(timedelta(minutes=mins))
)
naive_dts = st.datetimes(min_value=datetime(1900, 1, 1), max_value=datetime(9998, 12, 31))
aware_dts = st.builds(lambda d, tz: d.replace(tzinfo=tz), naive_dts, offsets)


def _same(a, b):
    return a == b and a.utcoffset() == b.utcoffset()


@given(st.one_of(naive_dts, aware_dts), st.sampled_from(["T", " "]))
def test_parse_iso_lenient_roundtrips_isoformat(dt, sep):
    assert _same(parse_iso_lenient(dt.isoformat(sep=sep)), dt)


@given(aware_dts)
def test_parse_iso_lenient_reads_colonless_offset_and_z(dt):
    colonless = dt.strftime("%Y-%m-%dT%H:%M:%S") + dt.strftime("%z")
    assert re.search(r"[+-]\d{4}$", colonless)
    assert _same(parse_iso_lenient(colonless), dt.replace(microsecond=0))
    utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    z_form = utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    assert _same(parse_iso_lenient(z_form), utc)


@given(st.text())
@example("+0100")
def test_parse_iso_lenient_never_raises(s):
    out = parse_iso_lenient(s)
    assert out is None or isinstance(out, datetime)


@given(st.one_of(naive_dts, aware_dts))
def test_parse_header_datetime_is_utc_and_same_instant(dt):
    out = parse_header_datetime(dt.isoformat())
    assert out.utcoffset() == timedelta(0)
    # Naive means UTC by decision; aware is converted, not overwritten.
    expected = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    assert out == expected
    assert _same(parse_header_datetime(out.isoformat()), out)  # idempotent


SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@given(st.text(), st.integers(1, 80))
@example("Rock Climbing", 50)
@example("café", 50)
@example("a" * 49 + " b", 50)
def test_slugify_output_shape_length_and_idempotence(text, n):
    out = slugify(text, n)
    assert out == "" or SLUG_RE.fullmatch(out), out
    assert len(out) <= n
    assert slugify(out, n) == out


@given(st.text(), st.integers(1, 80))
def test_slugify_truncation_is_a_prefix(text, n):
    assert slugify(text, 10**6).startswith(slugify(text, n))


UNSAFE = set('/\\:*?"<>|\x00\r\n')


@given(st.text(), st.integers(1, 200))
@example("../../etc/cron.d/evil", 120)
@example("", 120)
@example(" . ", 120)
def test_safe_filename_guarantees_except_dotdot(text, n):
    out = safe_filename(text, n)
    assert out and len(out) <= max(n, 1)
    assert not (UNSAFE & set(out))
    assert out[0] not in ". " and out[-1] not in ". "


@pytest.mark.xfail(
    strict=True,
    reason="'..' is stripped BEFORE unsafe chars are removed, so removing ':' "
    "reassembles it: safe_filename('a.:.b') == 'a..b', breaking the "
    "documented 'No .. path traversal sequences' and idempotence",
)
@given(st.text())
@example("a.:.b")
def test_safe_filename_no_dotdot_and_idempotent(text):
    out = safe_filename(text)
    assert ".." not in out
    assert safe_filename(out) == out


_word = st.text(
    alphabet=st.characters(exclude_characters=UNSAFE | {".", " "}), min_size=1, max_size=12
)


@given(st.lists(_word, min_size=1, max_size=8).map(" ".join))
@example("Sarah")
@example("p1 03m45 Sarah onboarding was confusing")
def test_safe_filename_leaves_clean_names_untouched(name):
    assert len(name) <= 120  # strategy stays under the default cap (max 103 chars)
    assert safe_filename(name) == name
