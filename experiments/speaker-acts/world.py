"""The synthetic study the speaker-act harness drives.

Three sessions, small enough to read by eye, shaped to reach every menu act:

- s1: Marcus (m1) moderates Rosalind (p1). Two voices: the swap is offered.
- s2: Marcus (m1 again, the same person) moderates Sarah (p2).
- s3: Kerri (m1 here, m2 as an identity) moderates Dana (p3); Olu (o1) observes.

Every participant paragraph that matters carries a quote with a sentiment, a
section and a theme, so a lost quote shows up on every surface at once.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

# (seconds, speaker, text). Paragraph positions are the list indexes.
S1 = [
    (2, "m1", "Welcome Rosalind, thanks for coming in today."),
    (10, "p1", "Thanks for having me, the import screen confused me straight away."),
    (20, "m1", "Tell me more about the import screen."),
    (30, "p1", "I dragged the folder in and nothing visibly happened for a while."),
    (40, "m1", "Yes that is true, it does sit there silently."),
    (50, "p1", "So I dragged it again and then I had two copies which annoyed me."),
    (60, "m1", "What did you expect instead?"),
    (70, "p1", "A progress bar, honestly anything that tells me it heard me."),
    (80, "m1", "And the quotes page?"),
    (90, "p1", "The quotes page is lovely, I could read that all day."),
    (100, "m1", "Great, thank you."),
]
S2 = [
    (2, "m1", "Hello Sarah, shall we begin?"),
    (10, "p2", "Sure, I mostly use the signals page to plan my week."),
    (20, "m1", "How so?"),
    (30, "p2", "It tells me which problems come up in every single session."),
    (40, "m1", "Anything missing?"),
    (50, "p2", "Export to slides is missing and I miss it every Friday."),
]
S3 = [
    (2, "m1", "Hi Dana, Olu is sitting in today."),
    (10, "o1", "Hello, pretend I am not here."),
    (20, "p3", "No problem, the codebook is the part I trust least."),
    (30, "m1", "Why is that?"),
    (40, "p3", "The tags feel invented, I cannot see where they came from."),
    (50, "o1", "That matches what support hears."),
]
TRANSCRIPTS = {"s1": S1, "s2": S2, "s3": S3}
PARTICIPANT = {"s1": "p1", "s2": "p2", "s3": "p3"}

# (session, start, end, section, theme, sentiment)
QUOTES = [
    ("s1", 10, 18, "Import", "Silent failure", "confusion"),
    ("s1", 30, 38, "Import", "Silent failure", "frustration"),
    ("s1", 50, 58, "Import", "Silent failure", "frustration"),
    ("s1", 70, 78, "Import", "Feedback wanted", "doubt"),
    ("s1", 90, 98, "Quotes", "Delight in reading", "delight"),
    ("s2", 10, 18, "Signals", "Planning", "satisfaction"),
    ("s2", 30, 38, "Signals", "Planning", "confidence"),
    ("s2", 50, 58, "Export", "Feedback wanted", "frustration"),
    ("s3", 20, 28, "Codebook", "Trust", "doubt"),
    ("s3", 40, 48, "Codebook", "Trust", "suspicion"),
]


def _stamp(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _entry(full: str, evidence: str = "platform-name") -> dict:
    return {"full_name": full, "short_name": full.split()[0], "role": "", "evidence": evidence}


def quote_id(session: str, start: int) -> str:
    return f"q-{PARTICIPANT[session]}-{start}"


def build(root: Path) -> Path:
    """Write the study's output folder under ``root``; returns ``root``."""
    out = root / "bristlenose-output"
    inter = out / ".bristlenose" / "intermediate"
    inter.mkdir(parents=True, exist_ok=True)
    (inter / "metadata.json").write_text('{"project_name": "Speaker acts"}', encoding="utf-8")
    raw = out / "transcripts-raw"
    raw.mkdir(exist_ok=True)
    for day, (sid, lines) in enumerate(TRANSCRIPTS.items(), start=20):
        body = f"# Transcript: {sid}\n# Date: 2026-09-{day}\n# Duration: 00:02:00\n\n"
        body += "".join(f"[{_stamp(t)}] [{code}] {text}\n" for t, code, text in lines)
        (raw / f"{sid}.txt").write_text(body, encoding="utf-8")

    def text_at(sid: str, start: int) -> str:
        return next(text for t, _, text in TRANSCRIPTS[sid] if t == start)

    def as_quote(sid: str, start: int, end: int, label: str, sentiment: str) -> dict:
        return {"session_id": sid, "participant_id": PARTICIPANT[sid], "start_timecode": float(start),
                "end_timecode": float(end), "text": text_at(sid, start), "topic_label": label,
                "quote_type": "screen_specific", "sentiment": sentiment, "intensity": 2}

    sections: dict[str, list[dict]] = {}
    themes: dict[str, list[dict]] = {}
    for sid, start, end, section, theme, sentiment in QUOTES:
        sections.setdefault(section, []).append(as_quote(sid, start, end, section, sentiment))
        q = as_quote(sid, start, end, theme, sentiment)
        q["quote_type"] = "general_context"
        themes.setdefault(theme, []).append(q)
    (inter / "screen_clusters.json").write_text(json.dumps([
        {"screen_label": label, "description": "", "display_order": n, "quotes": quotes}
        for n, (label, quotes) in enumerate(sections.items(), start=1)
    ]), encoding="utf-8")
    (inter / "theme_groups.json").write_text(json.dumps([
        {"theme_label": label, "description": "", "quotes": quotes}
        for label, quotes in themes.items()
    ]), encoding="utf-8")

    names = {"p1": "Rosalind", "p2": "Sarah", "p3": "Dana"}
    (out / "people.yaml").write_text(yaml.safe_dump({"participants": {
        pid: {"computed": {"participant_id": pid, "session_id": sid},
              "editable": {"full_name": names[pid], "short_name": names[pid], "role": ""}}
        for sid, pid in PARTICIPANT.items()
    }}), encoding="utf-8")
    (inter / "session-speakers.json").write_text(json.dumps({"version": 2, "sessions": {
        "s1": {"m1": _entry("Marcus Stone")},
        "s2": {"m1": _entry("Marcus Stone")},
        "s3": {"m1": _entry("Kerri Lee"), "o1": _entry("Olu Ade")},
    }}), encoding="utf-8")
    # The registry the pipeline leaves: which diarised label got which code.
    (out / ".bristlenose" / "sessions.json").write_text(json.dumps({
        "version": 3, "sessions": {}, "participants_issued": 3,
        "speakers": {"s1": {"Speaker A": "m1", "Speaker B": "p1"},
                     "s2": {"Speaker A": "m1", "Speaker B": "p2"},
                     "s3": {"Speaker A": "m1", "Speaker B": "p3", "Speaker C": "o1"}},
        "pins": {}, "starts": {}, "hints": {},
    }), encoding="utf-8")
    return root
