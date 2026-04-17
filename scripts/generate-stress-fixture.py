#!/usr/bin/env python3
"""Generate a synthetic Bristlenose project for performance stress testing.

Produces a serve-mode-ready project directory containing:
  - metadata.json, screen_clusters.json, theme_groups.json in .bristlenose/intermediate/
  - Parseable transcripts (s1.txt ... sN.txt) under transcripts-raw/
  - people.yaml with one participant per session

The output bypasses the pipeline entirely — no LLM calls, no audio, no
transcription.  The quote JSON is structured to match the importer's
expectations (`_get_or_create_quote` stable key, `_SEGMENT_RE` format).

Determinism: `random.seed(0)` at import time.  Same flags → identical
fixtures, so before/after virtualisation comparisons stay apples-to-apples.

Dependencies: PyYAML (in the project venv's .[dev] extras).  Run via
``.venv/bin/python scripts/generate-stress-fixture.py``.

See docs/design-perf-stress-test.md for the full measurement plan.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "ERROR: PyYAML is required. Run the script from the project venv:\n"
        "  .venv/bin/python scripts/generate-stress-fixture.py",
        file=sys.stderr,
    )
    sys.exit(1)

# Deterministic output — changing the seed changes every fixture byte.
random.seed(0)


# ---------------------------------------------------------------------------
# Content templates (slot-filled to produce varied but realistic quote text)
# ---------------------------------------------------------------------------

SECTION_LABELS = [
    "Dashboard",
    "Search",
    "Onboarding",
    "Checkout",
    "Navigation",
    "Settings",
    "Notifications",
    "Help and support",
    "Profile and account",
    "Reporting and analytics",
    "Integrations",
    "Billing",
]

THEME_LABELS = [
    "Onboarding gaps",
    "Trust and reliability",
    "Speed and efficiency",
    "Discoverability",
    "Mental model mismatch",
    "Accessibility",
    "Power-user workflows",
    "Cross-device continuity",
    "Error recovery",
    "Collaboration friction",
]

SECTION_DESCRIPTIONS = [
    "Participants described the {label} area as the main point of interaction.",
    "Quotes in this cluster surface friction points and wins around {label}.",
    "{label} came up repeatedly as a place where expectations diverged from reality.",
]

THEME_DESCRIPTIONS = [
    "A cross-cutting pattern about {label} that surfaced across multiple sessions.",
    "Quotes grouped under {label} cut across specific screens and tasks.",
    "{label} emerged as a general theme, not tied to one part of the product.",
]

# ~50 varied template sentences — slot-filled with feature/sentiment words.
# Lengths range from short reactions to longer narratives.  Good mix of
# moaning, praise, confusion, and concrete feature references so tag
# badges and sentiment labels render realistically.
QUOTE_TEMPLATES = [
    "I found the {feature} pretty {mood} at first. I couldn't figure out where anything was.",
    "The {feature} was hidden behind a menu I didn't notice. I kept hunting around for it.",
    "Honestly the {feature} was the best part. It was fast and the results were really relevant.",
    "I think the {feature} could be {mood_adj}. When I first used it I had no idea what was happening.",
    "What I really wanted from the {feature} was a clearer indication of what state I was in.",
    "Once I figured out the {feature} it was fine, but getting there took longer than I expected.",
    "I gave up on the {feature} after a few tries. There was no indication I was doing it right.",
    "The {feature} works but it's not where I'd expect to find it. I had to ask someone.",
    "I like that the {feature} remembers my preferences. That saved me a lot of time.",
    "My biggest complaint is the {feature}. It never does what I expect on the first try.",
    "When I hit the {feature} I wasn't sure if it had worked or if I needed to do something else.",
    "The {feature} is great when it works, but the error messages are completely useless.",
    "I've been using similar tools for years, and the {feature} here is genuinely {mood_adj}.",
    "There's no way to undo what you did in the {feature}. That's a deal-breaker for me.",
    "I had to read the help page twice to understand the {feature}. It shouldn't be that complicated.",
    "The {feature} is buried three clicks deep. I'd put it on the main screen.",
    "Once you get past the {feature} setup, the rest is actually pretty smooth.",
    "I don't think the {feature} is labelled clearly. The wording didn't match what it actually did.",
    "When the {feature} shows a loading spinner for more than a few seconds, I assume something broke.",
    "I appreciated that the {feature} had a keyboard shortcut. That's the mark of a thoughtful design.",
    "My team uses the {feature} every day and it's a core part of our workflow now.",
    "The {feature} behaves differently on mobile than on desktop and that threw me off.",
    "I wish the {feature} would confirm before deleting. I've lost work that way twice now.",
    "The {feature} is a bit {mood} to be honest. It needs more polish.",
    "After the first session I barely noticed the {feature} anymore. It just faded into the background.",
    "I was {mood} by how well the {feature} handled my edge case. That doesn't usually happen.",
    "The {feature} feels like it was designed by someone who's never actually used the product.",
    "I'd pay for a version of the {feature} that did just one thing well instead of many things poorly.",
    "The {feature} almost works, but the last 10% of the experience is frustrating.",
    "I genuinely can't tell whether the {feature} is saving my changes or not.",
    "Whoever designed the {feature} must have had a clear mental model that I don't share.",
    "The {feature} is great in theory. In practice I hit a bug every third time.",
    "I didn't realise the {feature} existed until someone on my team showed me. It should be more visible.",
    "The {feature} assumes a level of expertise I don't have. A tutorial would help.",
    "When the {feature} crashed I lost everything. There's no auto-save anywhere.",
    "I love the {feature}, but I wish it had better keyboard navigation.",
    "The first time I used the {feature} I got stuck. The second time was fine. Something about it isn't sticky.",
    "I'd describe the {feature} as {mood_adj}. It mostly works but every interaction has a small papercut.",
    "The {feature} needs better defaults. I spent ten minutes configuring something that should just work out of the box.",
    "I was {mood} when I saw the {feature} could handle bulk operations. That saves me hours.",
    "The {feature} is inconsistent with the rest of the product. It uses different terms for the same thing.",
    "There are two ways to do the {feature} and I never know which one is right.",
    "Honestly the {feature} is fine. It's not amazing but it does what it says.",
    "The {feature} shows an error I've never been able to decipher. I just close the dialog and try again.",
    "My preferred workflow would be to do the {feature} entirely from the keyboard but that's not possible.",
    "The {feature} is the reason I recommend this product to other people. Nothing else does it this well.",
    "I was expecting the {feature} to have a search field. When I couldn't find one I was {mood}.",
    "The {feature} feels slow on my work machine but fast on my home machine. Something is off.",
    "When the {feature} first loads it seems like nothing is happening. A progress indicator would help.",
    "I trust the {feature} for my own work, but I wouldn't use it for client-facing work without more review.",
]

FEATURES = [
    "dashboard",
    "search bar",
    "navigation",
    "onboarding flow",
    "settings page",
    "notification system",
    "help centre",
    "account profile",
    "reporting view",
    "billing page",
    "export button",
    "filter panel",
    "main sidebar",
    "command palette",
    "autosave behaviour",
    "undo function",
    "keyboard shortcut",
    "mobile layout",
    "integration setup",
    "sharing dialog",
]

MOOD_WORDS = {
    "frustration": ("frustrating", "exhausting"),
    "confusion": ("confusing", "ambiguous"),
    "doubt": ("questionable", "suspicious"),
    "surprise": ("unexpected", "startling"),
    "satisfaction": ("solid", "reliable"),
    "delight": ("delightful", "wonderful"),
    "confidence": ("trustworthy", "dependable"),
}

MOOD_REACTION = {
    "frustration": ("annoyed", "frustrated"),
    "confusion": ("confused", "uncertain"),
    "doubt": ("doubtful", "sceptical"),
    "surprise": ("surprised", "taken aback"),
    "satisfaction": ("satisfied", "pleased"),
    "delight": ("delighted", "impressed"),
    "confidence": ("confident", "reassured"),
}

CONTEXT_PREFIXES = [
    "When asked about their first impression",
    "Describing a recent task",
    "Unprompted feedback",
    "When asked to rate the experience",
    "Walking through a task",
    "After completing the scenario",
    "While demonstrating their workflow",
    "Reflecting on the overall experience",
]

MODERATOR_QUESTIONS = [
    "Can you tell me more about that?",
    "What happened next?",
    "How did that make you feel?",
    "Walk me through what you were trying to do.",
    "What did you expect to happen?",
    "Was there anything else that stood out?",
    "Why do you think that is?",
    "Can you give me an example?",
    "What were you hoping for?",
    "How often does that happen?",
    "What would make this easier?",
    "Did you notice anything else on the screen?",
    "Where would you normally go for help?",
    "And then what did you do?",
    "Is that different from what you usually do?",
]

# Weighted sentiment distribution — matches the pipeline's observed real-world mix.
SENTIMENT_WEIGHTS: list[tuple[str, int]] = [
    ("frustration", 35),
    ("confusion", 20),
    ("satisfaction", 15),
    ("delight", 10),
    ("doubt", 8),
    ("surprise", 7),
    ("confidence", 5),
]


# ---------------------------------------------------------------------------
# Fixture generation
# ---------------------------------------------------------------------------


def _weighted_choice(choices: list[tuple[str, int]]) -> str:
    """Pick from (value, weight) pairs using the seeded random module."""
    total = sum(w for _, w in choices)
    pick = random.randint(1, total)
    running = 0
    for value, weight in choices:
        running += weight
        if pick <= running:
            return value
    return choices[-1][0]


def _format_timecode(seconds: int) -> str:
    """Format an integer second count as ``MM:SS`` or ``HH:MM:SS``.

    Matches ``_SEGMENT_RE`` in importer.py — the regex accepts either form.
    """
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"


def _fill_quote_text(sentiment: str) -> str:
    """Render one quote string by slot-filling a random template."""
    template = random.choice(QUOTE_TEMPLATES)
    mood_adj = random.choice(MOOD_WORDS[sentiment])
    mood_reaction = random.choice(MOOD_REACTION[sentiment])
    return template.format(
        feature=random.choice(FEATURES),
        mood=mood_reaction,
        mood_adj=mood_adj,
    )


def _quote_record(
    session_id: str,
    participant_id: str,
    start_tc: int,
    end_tc: int,
    text: str,
    topic_label: str,
    quote_type: str,
    sentiment: str,
    segment_index: int,
) -> dict:
    """Build one ExtractedQuote-shaped dict.

    Includes the deprecated intent/emotion/journey_stage fields (importer
    ignores them, but real JSON on disk carries them — present here for realism).
    """
    return {
        "session_id": session_id,
        "participant_id": participant_id,
        "start_timecode": float(start_tc),
        "end_timecode": float(end_tc),
        "text": text,
        "topic_label": topic_label,
        "quote_type": quote_type,
        "researcher_context": random.choice(CONTEXT_PREFIXES),
        "sentiment": sentiment,
        "intensity": random.randint(1, 3),
        "segment_index": segment_index,
        "intent": "narration",
        "emotion": "neutral",
        "journey_stage": "other",
    }


def _build_session(
    session_num: int,
    quote_count: int,
) -> tuple[list[tuple[int, str, str]], list[dict]]:
    """Generate one session's transcript segments and their matched quotes.

    Returns (segments, quotes).  Each quote's ``start_timecode`` matches
    a participant segment's timecode exactly, and ``segment_index`` is
    that segment's position in the transcript.
    """
    session_id = f"s{session_num}"
    participant_id = f"p{session_num}"

    segments: list[tuple[int, str, str]] = []
    quotes: list[dict] = []

    t = 2  # first moderator question starts at 00:02
    for _ in range(quote_count):
        # Moderator question
        mod_text = random.choice(MODERATOR_QUESTIONS)
        segments.append((t, "m1", mod_text))
        t += random.randint(4, 9)  # question duration + small gap

        # Participant quote — this becomes a Quote record
        sentiment = _weighted_choice(SENTIMENT_WEIGHTS)
        text = _fill_quote_text(sentiment)
        start_tc = t
        duration = random.randint(5, 25)
        end_tc = start_tc + duration

        quote_segment_index = len(segments)  # position of the participant line
        segments.append((start_tc, participant_id, text))

        quotes.append(
            {
                "session_id": session_id,
                "participant_id": participant_id,
                "start_tc": start_tc,
                "end_tc": end_tc,
                "text": text,
                "sentiment": sentiment,
                "segment_index": quote_segment_index,
            }
        )

        # Gap between end of quote and next moderator question
        t = end_tc + random.randint(2, 8)

    return segments, quotes


def _render_transcript(
    session_id: str,
    segments: list[tuple[int, str, str]],
    source_name: str,
) -> str:
    """Serialise segments to the format `_SEGMENT_RE` expects."""
    last_tc = segments[-1][0] if segments else 0
    # Round the session duration up to the next minute for a tidy header
    duration_s = last_tc + 30
    hours = duration_s // 3600
    minutes = (duration_s % 3600) // 60
    secs = duration_s % 60
    duration_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"

    lines = [
        f"# Transcript: {session_id}",
        f"# Source: {source_name}",
        "# Date: 2026-01-20",
        f"# Duration: {duration_str}",
        "",
    ]
    for tc, speaker, text in segments:
        lines.append(f"[{_format_timecode(tc)}] [{speaker}] {text}")
    lines.append("")
    return "\n".join(lines)


def _build_people_yaml(sessions: int) -> dict:
    """Build a people.yaml dict with one participant per session plus a moderator.

    Includes a valid ``computed`` block per entry so the strict
    ``bristlenose.people.load_people_file`` validator (used by the render
    path on ``bristlenose serve`` startup) accepts the file.  The
    importer is lenient and only reads ``editable``.
    """
    participants: dict = {}
    session_date_iso = "2026-01-20T00:00:00"
    for i in range(1, sessions + 1):
        sid = f"s{i}"
        participants[f"p{i}"] = {
            "computed": {
                "participant_id": f"p{i}",
                "session_id": sid,
                "session_date": session_date_iso,
                "duration_seconds": 5400.0,
                "words_spoken": 5000,
                "pct_words": 60.0,
                "pct_time_speaking": 55.0,
                "source_file": f"Stress Test Session {i}.mp4",
            },
            "editable": {
                "full_name": f"Test Participant {i}",
                "short_name": f"P{i}",
                "role": "Tester",
            },
        }
    # Moderator is a speaker but not a participant — still listed so names surface.
    participants["m1"] = {
        "computed": {
            "participant_id": "m1",
            "session_id": "s1",
            "session_date": session_date_iso,
            "duration_seconds": 5400.0,
            "words_spoken": 2000,
            "pct_words": 40.0,
            "pct_time_speaking": 45.0,
            "source_file": "Stress Test Session 1.mp4",
        },
        "editable": {
            "full_name": "Research Moderator",
            "short_name": "Mod",
            "role": "Researcher",
        },
    }
    return {"participants": participants}


def generate(
    output: Path,
    total_quotes: int,
    num_sessions: int,
    num_sections: int,
    num_themes: int,
) -> None:
    """Generate the full fixture tree at ``output``."""
    # Safety guard: refuse to `rmtree` anything we didn't create ourselves.
    # Previous fixtures carry a sentinel file; if it's missing we bail so
    # a slip of the finger on ``--output`` can't delete a real project.
    sentinel_name = ".bristlenose-stress-fixture"
    if output.exists():
        if not (output / sentinel_name).exists():
            raise SystemExit(
                f"ERROR: --output {output} exists but is not a stress "
                f"fixture (no {sentinel_name} sentinel).  Refusing to rmtree."
            )
        shutil.rmtree(output)

    intermediate = output / "bristlenose-output" / ".bristlenose" / "intermediate"
    transcripts_dir = output / "bristlenose-output" / "transcripts-raw"
    intermediate.mkdir(parents=True)
    transcripts_dir.mkdir(parents=True)
    # Drop the sentinel so re-runs can safely clear this directory.
    (output / sentinel_name).write_text(
        "Generated by scripts/generate-stress-fixture.py.  Safe to delete.\n",
        encoding="utf-8",
    )

    # --- Split total_quotes across sessions -----------------------------
    base = total_quotes // num_sessions if num_sessions else 0
    remainder = total_quotes % num_sessions if num_sessions else 0
    per_session: list[int] = [
        base + (1 if i < remainder else 0) for i in range(num_sessions)
    ]

    # --- Build sessions + transcripts + quotes --------------------------
    all_quotes: list[dict] = []
    for idx, count in enumerate(per_session, start=1):
        if count == 0:
            # Still create an empty transcript so the session row exists.
            transcript = _render_transcript(
                f"s{idx}", [], f"Stress Test Session {idx}.mp4"
            )
            (transcripts_dir / f"s{idx}.txt").write_text(transcript, encoding="utf-8")
            continue

        segments, quotes = _build_session(idx, count)
        transcript = _render_transcript(
            f"s{idx}", segments, f"Stress Test Session {idx}.mp4"
        )
        (transcripts_dir / f"s{idx}.txt").write_text(transcript, encoding="utf-8")
        all_quotes.extend(quotes)

    # --- Split quotes 70 / 30 between screen_specific and general_context
    # Deterministic split: mark every quote with a weighted coin flip, then
    # enforce the exact ratio by reclassifying tail quotes if we drifted.
    for q in all_quotes:
        q["quote_type"] = (
            "screen_specific" if random.random() < 0.7 else "general_context"
        )

    target_screen = round(len(all_quotes) * 0.7)
    actual_screen = sum(1 for q in all_quotes if q["quote_type"] == "screen_specific")
    drift = actual_screen - target_screen
    if drift > 0:
        # Too many screen_specific — flip some to general_context.
        flipped = 0
        for q in all_quotes:
            if flipped >= drift:
                break
            if q["quote_type"] == "screen_specific":
                q["quote_type"] = "general_context"
                flipped += 1
    elif drift < 0:
        flipped = 0
        for q in all_quotes:
            if flipped >= -drift:
                break
            if q["quote_type"] == "general_context":
                q["quote_type"] = "screen_specific"
                flipped += 1

    # --- Assign each quote to one section or theme (round-robin) ---------
    screen_quotes = [q for q in all_quotes if q["quote_type"] == "screen_specific"]
    theme_quotes = [q for q in all_quotes if q["quote_type"] == "general_context"]

    sections: list[dict] = []
    for i in range(num_sections):
        label = SECTION_LABELS[i % len(SECTION_LABELS)]
        if num_sections > len(SECTION_LABELS):
            label = f"{label} {i + 1}"
        sections.append(
            {
                "screen_label": label,
                "description": random.choice(SECTION_DESCRIPTIONS).format(label=label),
                "display_order": i + 1,
                "quotes": [],
            }
        )

    themes: list[dict] = []
    for i in range(num_themes):
        label = THEME_LABELS[i % len(THEME_LABELS)]
        if num_themes > len(THEME_LABELS):
            label = f"{label} {i + 1}"
        themes.append(
            {
                "theme_label": label,
                "description": random.choice(THEME_DESCRIPTIONS).format(label=label),
                "quotes": [],
            }
        )

    for i, q in enumerate(screen_quotes):
        section = sections[i % num_sections] if num_sections else None
        if section is None:
            continue
        record = _quote_record(
            session_id=q["session_id"],
            participant_id=q["participant_id"],
            start_tc=q["start_tc"],
            end_tc=q["end_tc"],
            text=q["text"],
            topic_label=section["screen_label"],
            quote_type="screen_specific",
            sentiment=q["sentiment"],
            segment_index=q["segment_index"],
        )
        section["quotes"].append(record)

    for i, q in enumerate(theme_quotes):
        theme = themes[i % num_themes] if num_themes else None
        if theme is None:
            continue
        record = _quote_record(
            session_id=q["session_id"],
            participant_id=q["participant_id"],
            start_tc=q["start_tc"],
            end_tc=q["end_tc"],
            text=q["text"],
            topic_label=theme["theme_label"],
            quote_type="general_context",
            sentiment=q["sentiment"],
            segment_index=q["segment_index"],
        )
        theme["quotes"].append(record)

    # --- Write intermediate JSON ----------------------------------------
    metadata = {"project_name": f"Stress Test ({total_quotes} quotes)"}
    (intermediate / "metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    (intermediate / "screen_clusters.json").write_text(
        json.dumps(sections, indent=2), encoding="utf-8"
    )
    (intermediate / "theme_groups.json").write_text(
        json.dumps(themes, indent=2), encoding="utf-8"
    )

    # --- Write people.yaml ---------------------------------------------
    people = _build_people_yaml(num_sessions)
    (output / "bristlenose-output" / "people.yaml").write_text(
        yaml.safe_dump(people, sort_keys=False), encoding="utf-8"
    )

    # --- Summary --------------------------------------------------------
    print(f"Generated fixture at {output}")
    print(f"  Sessions:       {num_sessions}")
    print(f"  Sections:       {num_sections} ({len(screen_quotes)} quotes)")
    print(f"  Themes:         {num_themes} ({len(theme_quotes)} quotes)")
    print(f"  Total quotes:   {len(screen_quotes) + len(theme_quotes)}")
    print(f"  Transcript dir: {transcripts_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quotes", type=int, default=1500, help="Total quote count (default 1500)")
    parser.add_argument("--sessions", type=int, default=5, help="Number of sessions (default 5)")
    parser.add_argument("--sections", type=int, default=8, help="Number of screen clusters (default 8)")
    parser.add_argument("--themes", type=int, default=6, help="Number of theme groups (default 6)")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("trial-runs/stress-test-1500"),
        help="Output directory (default trial-runs/stress-test-1500)",
    )
    args = parser.parse_args()

    if args.quotes < 0:
        parser.error("--quotes must be >= 0")
    if args.sessions < 1:
        parser.error("--sessions must be >= 1")
    if args.sections < 1:
        parser.error("--sections must be >= 1")
    if args.themes < 1:
        parser.error("--themes must be >= 1")

    generate(
        output=args.output,
        total_quotes=args.quotes,
        num_sessions=args.sessions,
        num_sections=args.sections,
        num_themes=args.themes,
    )


if __name__ == "__main__":
    main()
