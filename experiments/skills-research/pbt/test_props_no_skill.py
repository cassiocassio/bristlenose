"""Property-based tests for bristlenose.utils.timecodes and slugify/safe_filename."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st

from bristlenose.utils.text import safe_filename, slugify
from bristlenose.utils.timecodes import (
    format_duration_human,
    format_timecode,
    format_timecode_ms,
    format_timecode_prompt,
    local_now,
    parse_header_datetime,
    parse_iso_lenient,
    parse_timecode,
    seconds_between,
)

# parse_timecode's declared domain: hours are at most two digits.
UNDER_100H = 100 * 3600
finite = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e7, max_value=1e7)
in_domain = st.floats(min_value=0, max_value=UNDER_100H - 1, allow_nan=False)

# ---------------------------------------------------------------- timecodes


@given(finite)
def test_format_timecode_shape(s):
    out = format_timecode(s)
    if max(0, int(s)) < 3600:
        assert re.fullmatch(r"\d{2}:[0-5]\d", out), out
    else:
        assert re.fullmatch(r"[1-9]\d*:[0-5]\d:[0-5]\d", out), out


@given(in_domain)
def test_format_timecode_roundtrips_through_parse(s):
    assert parse_timecode(format_timecode(s)) == int(s)


@given(in_domain)
def test_format_timecode_prompt_roundtrips_and_always_has_hours(s):
    out = format_timecode_prompt(s)
    assert re.fullmatch(r"\d{2}:[0-5]\d:[0-5]\d", out), out
    assert parse_timecode(out) == int(s)


@given(st.floats(max_value=0, allow_nan=False, allow_infinity=False))
def test_negative_clamps_to_zero(s):
    assert format_timecode(s) == "00:00"
    assert format_timecode_prompt(s) == "00:00:00"
    assert format_timecode_ms(s) == "00:00:00.000"


@given(in_domain)
def test_format_timecode_ms_roundtrips_within_half_a_millisecond(s):
    assert abs(parse_timecode(format_timecode_ms(s)) - s) <= 0.0005 + 1e-9


@pytest.mark.xfail(
    strict=True,
    reason="format_timecode_ms rounds the seconds field independently of the "
    "minutes, so 59.9996 renders '00:00:60.000' (seconds field = 60).",
)
@given(in_domain)
@example(59.9996)
def test_format_timecode_ms_fields_are_in_range(s):
    out = format_timecode_ms(s)
    m = re.fullmatch(r"(\d{2,}):(\d{2}):(\d{2})\.(\d{3})", out)
    assert m, out
    assert int(m.group(2)) < 60 and int(m.group(3)) < 60, out


@given(finite)
def test_format_duration_human_grammar_and_value(s):
    out = format_duration_human(s)
    if s <= 0:
        assert out == "0m"
        return
    if out == "<1m":
        assert s < 60
        return
    m = re.fullmatch(r"(?:([1-9]\d*)h)?(?: ?([1-5]?\d)m)?", out)
    assert m and out and not out.startswith(" "), out
    h, mins = int(m.group(1) or 0), int(m.group(2) or 0)
    assert mins < 60 and (h or mins)
    assert m.group(2) is None or mins > 0  # never "1h 0m" / "0m" here
    assert h * 3600 + mins * 60 <= s < h * 3600 + mins * 60 + 60


@given(finite, finite)
def test_seconds_between(a, b):
    d = seconds_between(a, b)
    assert d >= 0
    assert d == (b - a if b >= a else 0.0)


@given(
    st.integers(0, 99), st.integers(0, 59), st.integers(0, 59), st.integers(0, 999),
    st.sampled_from([",", "."]), st.sampled_from(["", " ", "\t", "\n"]),
)
def test_parse_timecode_srt_vtt(h, m, s, ms, sep, pad):
    tc = f"{pad}{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}{pad}"
    assert parse_timecode(tc) == pytest.approx(h * 3600 + m * 60 + s + ms / 1000)


@given(st.integers(0, 59), st.integers(0, 59), st.integers(0, 999), st.integers(1, 3))
def test_parse_timecode_short_fraction_is_padded_not_scaled(m, s, ms, width):
    frac = f"{ms:03d}"[:width]
    expected = m * 60 + s + int(frac.ljust(3, "0")) / 1000
    assert parse_timecode(f"{m:02d}:{s:02d}.{frac}") == pytest.approx(expected)


@given(in_domain, st.text(min_size=1).filter(lambda t: t.strip() and not t[0].isspace()))
def test_parse_timecode_refuses_trailing_garbage(s, junk):
    tc = format_timecode_prompt(s) + " " + junk
    with pytest.raises(ValueError):
        parse_timecode(tc)


@given(st.text())
def test_parse_timecode_only_raises_value_error(t):
    try:
        r = parse_timecode(t)
    except ValueError:
        return
    assert r >= 0


@given(st.integers(100, 10_000))
def test_parse_timecode_refuses_three_digit_hours(h):
    with pytest.raises(ValueError):
        parse_timecode(f"{h}:00:00")


# --------------------------------------------------------------- datetimes

offsets = st.integers(-14 * 60 + 1, 14 * 60 - 1).map(lambda m: timezone(timedelta(minutes=m)))
aware = st.datetimes(
    min_value=datetime(1900, 1, 1), max_value=datetime(2200, 1, 1), timezones=offsets
)


@given(st.text())
def test_parse_iso_lenient_never_raises(t):
    r = parse_iso_lenient(t)
    assert r is None or isinstance(r, datetime)


@given(aware)
def test_parse_iso_lenient_roundtrips_isoformat(dt):
    assert parse_iso_lenient(dt.isoformat()) == dt
    assert parse_iso_lenient(dt.isoformat()).utcoffset() == dt.utcoffset()


@given(aware)
def test_parse_iso_lenient_accepts_colonless_offset_and_z(dt):
    iso = dt.isoformat()
    colonless = iso[:-3] + iso[-2:]  # "+01:00" -> "+0100"
    got = parse_iso_lenient(colonless)
    assert got == dt and got.utcoffset() == dt.utcoffset()
    utc = dt.astimezone(timezone.utc).isoformat()
    assert parse_iso_lenient(utc[:-6] + "Z") == dt


@given(st.datetimes(min_value=datetime(1900, 1, 1), max_value=datetime(2200, 1, 1)))
def test_parse_iso_lenient_naive_stays_naive(dt):
    got = parse_iso_lenient(dt.isoformat())
    assert got == dt and got.tzinfo is None


@given(aware)
def test_parse_header_datetime_converts_not_overwrites(dt):
    got = parse_header_datetime(dt.isoformat())
    assert got is not None
    assert got.utcoffset() == timedelta(0)
    assert got == dt  # same instant


@given(st.datetimes(min_value=datetime(1900, 1, 1), max_value=datetime(2200, 1, 1)))
def test_parse_header_datetime_naive_means_utc(dt):
    assert parse_header_datetime(dt.isoformat()) == dt.replace(tzinfo=timezone.utc)


@given(st.text())
def test_parse_header_datetime_is_none_or_utc(t):
    got = parse_header_datetime(t)
    assert got is None or got.utcoffset() == timedelta(0)


def test_local_now_is_aware():
    now = local_now()
    assert now.tzinfo is not None
    assert abs(now - datetime.now(timezone.utc)) < timedelta(seconds=5)


# ------------------------------------------------------------------ slugify

SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@given(st.text(), st.integers(0, 80))
def test_slugify_shape_and_length(t, n):
    out = slugify(t, max_length=n)
    assert out == "" or SLUG_RE.fullmatch(out), out
    assert len(out) <= n


@given(st.text(), st.integers(0, 80))
def test_slugify_idempotent(t, n):
    once = slugify(t, max_length=n)
    assert slugify(once, max_length=n) == once


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=50))
def test_slugify_fixed_point_on_slug_alphabet(t):
    assert slugify(t) == t


@given(st.text(), st.text())
def test_slugify_space_and_underscore_are_equivalent(a, b):
    assert slugify(f"{a} {b}") == slugify(f"{a}_{b}")


# ------------------------------------------------------------ safe_filename

UNSAFE = set('/\\:*?"<>|\x00\r\n')


@given(st.text(), st.integers(1, 200))
@example("a./.b", 120)
def test_safe_filename_guarantees(t, n):
    out = safe_filename(t, max_length=n)
    assert out
    assert not (set(out) & UNSAFE), out
    assert out == "_" or (out[0] not in ". " and out[-1] not in ". "), out
    assert len(out) <= n
    assert "  " not in out


@pytest.mark.xfail(
    strict=True,
    reason="'..' is stripped BEFORE unsafe chars are removed, so removing a "
    "separator reassembles it: safe_filename('a./.b') == 'a..b'.",
)
@given(st.text(alphabet="./\\:ab ", max_size=20))
@example("a./.b")
def test_safe_filename_has_no_dotdot(t):
    assert ".." not in safe_filename(t)


@given(st.text(), st.integers(1, 200))
def test_safe_filename_idempotent_when_no_dotdot(t, n):
    once = safe_filename(t, max_length=n)
    assume(".." not in once)
    assert safe_filename(once, max_length=n) == once


@given(
    st.text(
        alphabet=st.characters(blacklist_characters="./\\:*?\"<>|\x00\r\n ",
                               blacklist_categories=("Cs",)),
        min_size=1, max_size=40,
    ),
    st.text(alphabet=st.characters(blacklist_characters="./\\:*?\"<>|\x00\r\n ",
                                   blacklist_categories=("Cs",)),
            max_size=40),
)
def test_safe_filename_preserves_already_safe_text(a, b):
    t = f"{a} {b}" if b else a
    assert safe_filename(t) == t
