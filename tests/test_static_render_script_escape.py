"""The static renderer's embedded JSON cannot break out of its ``<script>``.

``json.dumps`` escapes nothing ASCII, so a literal ``</script>`` in embedded
data closes the script block and whatever follows runs as markup — in a file
a researcher opens from ``file://`` and hands to a client. Participant names
come from speaker labels in client-supplied .docx/.vtt; section and theme
labels and quote text come from the transcripts. Same guard as the HTML
export (``routes/export.py`` and ``test_embedded_data_cannot_break_out_of_script``
in ``test_serve_export_api.py``); the static renderer is sealed, but this is a
security fix.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from bristlenose.models import (
    ExtractedQuote,
    PeopleFile,
    PersonComputed,
    PersonEditable,
    PersonEntry,
    QuoteType,
    ScreenCluster,
    Sentiment,
)
from bristlenose.stages.s12_render import render_html, render_transcript_pages
from bristlenose.stages.s12_render.html_helpers import script_json

_EVIL = "</script><script>alert(1)</script>"

_RAW_TRANSCRIPT = """\
# Transcript: s1
# Source: interview_01.mp4
# Date: 2026-01-20
# Duration: 00:05:00

[00:42] [p1] The login page was really confusing at first.
"""


def _people(full_name: str) -> PeopleFile:
    return PeopleFile(participants={
        "p1": PersonEntry(
            computed=PersonComputed(
                participant_id="p1",
                session_id="s1",
                session_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
                duration_seconds=60.0,
                words_spoken=100,
                pct_words=50.0,
                pct_time_speaking=50.0,
                source_file="interview.vtt",
            ),
            editable=PersonEditable(full_name=full_name),
        )
    })


def _cluster(label: str) -> tuple[ExtractedQuote, ScreenCluster]:
    q = ExtractedQuote(
        session_id="s1",
        participant_id="p1",
        start_timecode=42.0,
        end_timecode=48.0,
        text="The login page was really confusing at first",
        verbatim_excerpt="The login page was really confusing at first.",
        topic_label="Login flow",
        quote_type=QuoteType.SCREEN_SPECIFIC,
        sentiment=Sentiment.CONFUSION,
    )
    return q, ScreenCluster(
        screen_label=label, description="d", display_order=1, quotes=[q],
    )


def _script_bodies(html: str) -> str:
    return "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))


def test_participant_name_cannot_break_out_of_report_script(tmp_path: Path) -> None:
    path = render_html(
        screen_clusters=[], theme_groups=[], sessions=[],
        project_name="Test", output_dir=tmp_path, people=_people(_EVIL),
    )
    html = path.read_text(encoding="utf-8")
    assert _EVIL not in html
    assert "var BN_PARTICIPANTS = " in html
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert(1)" in html


def test_label_cannot_break_out_of_transcript_script(tmp_path: Path) -> None:
    raw = tmp_path / "transcripts-raw"
    raw.mkdir()
    (raw / "s1.txt").write_text(_RAW_TRANSCRIPT, encoding="utf-8")
    q, cluster = _cluster(_EVIL)
    render_transcript_pages(
        sessions=[], project_name="Test", output_dir=tmp_path,
        all_quotes=[q], screen_clusters=[cluster],
    )
    html = (tmp_path / "sessions" / "transcript_s1.html").read_text(encoding="utf-8")
    assert _EVIL not in _script_bodies(html)
    assert "alert(1)</script>" not in html
    assert "var BRISTLENOSE_QUOTE_MAP = " in html


def test_script_json_round_trips() -> None:
    import json

    data = {"a": _EVIL, "b": "Tom & Jerry <3", "c": "Zoë — “quoted”"}
    out = script_json(data)
    assert "<" not in out and ">" not in out and "&" not in out
    assert json.loads(out) == data


def test_every_script_embed_goes_through_script_json() -> None:
    """A new ``json.dumps`` in the static renderer would reopen the hole."""
    root = Path(__file__).parent.parent / "bristlenose" / "stages" / "s12_render"
    offenders = [
        f"{p.name}:{n}"
        for p in sorted(root.glob("*.py"))
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if "json.dumps(" in line and not line.lstrip().startswith("#")
        and not (p.name == "html_helpers.py" and "def script_json" not in line
                 and _inside_script_json(p, n))
    ]
    assert offenders == [], offenders


def _inside_script_json(path: Path, lineno: int) -> bool:
    """True when ``lineno`` falls inside ``def script_json`` in ``path``."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines, 1) if ln.startswith("def script_json"))
    end = next(
        (i for i, ln in enumerate(lines, 1) if i > start and ln and not ln[0].isspace()),
        len(lines) + 1,
    )
    return start < lineno < end
