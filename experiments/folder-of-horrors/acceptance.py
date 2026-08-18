#!/usr/bin/env python3
"""Drive the real ingest stages over the folder of horrors and tabulate outcomes.

The point is NOT "did it work". It is the three-outcome taxonomy from the
corpus brief, plus a fourth this corpus exposed:

  1 INGESTED   — the file reached a session with usable audio
  2 REFUSED    — declined by name, with a reason a researcher can act on
  3 DROPPED    — absent from the run, and nothing said so   <- the real failure
  4 ABORTS     — took the whole batch down with it          <- worse at n=100

Ground truth comes from ffprobe, not from our own classifier, so the table can
say "this was real media and we lost it" rather than only "we lost it".

Stages 1 and 2 only: no Whisper, no LLM, no spend. That answers every question
in the taxonomy except the analysis stage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logging.disable(logging.CRITICAL)

from bristlenose.models import InputSession, classify_file  # noqa: E402
from bristlenose.stages.s01_ingest import discover_files  # noqa: E402
from bristlenose.stages.s02_extract_audio import extract_audio_for_sessions  # noqa: E402
from bristlenose.utils.audio import AudioToolError  # noqa: E402

def _watcher_exts() -> set[str]:
    """Read the macOS folder watcher's set from Swift, so the column cannot lie."""
    import re
    src = (Path(__file__).resolve().parents[2] / "desktop" / "Bristlenose"
           / "Bristlenose" / "ProjectFolderWatcher.swift")
    m = re.search(r"static let eligibleExtensions\s*:\s*Set<String>\s*=\s*\[(.*?)\]",
                  src.read_text(encoding="utf-8"), re.DOTALL)
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()


WATCHER_EXTS = _watcher_exts()

NON_MEDIA = {".csv", ".json", ".md"}


def ground_truth(path: Path) -> tuple[str, bool]:
    """(verdict, has_audio) straight from ffprobe — independent of our code."""
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ("unreadable", False)
    if res.returncode != 0:
        return ("unreadable", False)
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError:
        return ("unreadable", False)
    streams = data.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    has_video = any(s.get("codec_type") == "video" for s in streams)
    if has_audio:
        return ("media+audio", True)
    if has_video:
        return ("media, silent", False)
    return ("unreadable", False)


async def stage2_one(session: InputSession, tmp: Path) -> tuple[str, str]:
    """Run stage 2 for a single session in isolation. Returns (outcome, detail)."""
    try:
        await extract_audio_for_sessions([session], tmp)
    except AudioToolError as exc:
        return ("ABORTS", str(exc).split("\n")[0][:60])
    except Exception as exc:  # noqa: BLE001 — we are cataloguing, not handling
        return ("ABORTS", f"{type(exc).__name__}: {str(exc)[:50]}")
    if session.audio_path and Path(session.audio_path).exists():
        return ("INGESTED", "")
    if session.has_existing_transcript:
        return ("INGESTED", "transcript, no audio needed")
    return ("DROPPED", "no audio produced, nothing reported")


def main() -> int:
    corpus = Path(sys.argv[1]).resolve()
    tmp = Path(sys.argv[2]) if len(sys.argv) > 2 else corpus.parent / "_acceptance-tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    on_disk = sorted(p for p in corpus.iterdir()
                     if p.is_file() and p.suffix.lower() not in NON_MEDIA
                     and not p.name.startswith("."))

    skipped_list: list = []
    discovered = {f.path.resolve(): f for f in discover_files(corpus, skipped_list)}
    reported_skips = {s.path.resolve(): s.reason for s in skipped_list}

    rows = []
    for path in on_disk:
        truth, _has_audio = ground_truth(path)
        seen_by_watcher = path.suffix.lstrip(".").lower() in WATCHER_EXTS
        inp = discovered.get(path.resolve())

        if inp is None:
            reason = reported_skips.get(path.resolve())
            if reason:
                # Declined, and said so — outcome 2, not outcome 3.
                rows.append((path.name, truth, "REFUSED", reason, seen_by_watcher))
            else:
                cls = classify_file(path)
                detail = "not accepted" if cls is None else "discovered but absent"
                rows.append((path.name, truth, "DROPPED", detail, seen_by_watcher))
            continue

        session = InputSession(
            session_id="s1", session_number=1, participant_id="p1",
            participant_number=1, session_date=datetime.now(timezone.utc), files=[inp],
        )
        outcome, detail = asyncio.run(stage2_one(session, tmp))
        # A file stage 2 recorded a reason for is refused, not lost.
        if outcome == "DROPPED" and session.files[0].error:
            outcome, detail = "REFUSED", session.files[0].error
        rows.append((path.name, truth, outcome, detail, seen_by_watcher))

    # ---- report -----------------------------------------------------------
    w = max(len(r[0]) for r in rows) + 1
    print(f"{'FILE':<{w}} {'GROUND TRUTH':<14} {'OUTCOME':<9} {'WATCHER':<8} DETAIL")
    print("-" * (w + 60))
    order = {"ABORTS": 0, "DROPPED": 1, "REFUSED": 2, "INGESTED": 3}
    for name, truth, outcome, detail, watched in sorted(rows, key=lambda r: (order[r[2]], r[0])):
        print(f"{name:<{w}} {truth:<14} {outcome:<9} {'yes' if watched else 'NO':<8} {detail}")

    tally: dict[str, int] = {}
    for r in rows:
        tally[r[2]] = tally.get(r[2], 0) + 1
    print("\n" + "=" * 60)
    for k in ("INGESTED", "REFUSED", "DROPPED", "ABORTS"):
        print(f"  {k:<9} {tally.get(k, 0):3d}")
    blind = sum(1 for r in rows if not r[4])
    lost = sum(1 for r in rows if r[2] == "DROPPED" and r[1] == "media+audio")
    print(f"\n  invisible to the folder watcher : {blind:3d} of {len(rows)}")
    print(f"  REAL MEDIA WITH AUDIO, SILENTLY LOST: {lost:3d}   <- outcome 3")

    # The batch question: what does one damaged file do to a whole drop?
    print("\n" + "=" * 60)
    print("BATCH BEHAVIOUR — all files in one run, as a researcher would drop them:")
    files = list(discovered.values())
    sessions = [
        InputSession(session_id=f"s{i}", session_number=i, participant_id=f"p{i}",
                     participant_number=i, session_date=datetime.now(timezone.utc), files=[f])
        for i, f in enumerate(files, 1)
    ]
    try:
        asyncio.run(extract_audio_for_sessions(sessions, tmp))
        ok = sum(1 for s in sessions if s.audio_path)
        print(f"  completed: {ok}/{len(sessions)} sessions got audio")
    except Exception as exc:  # noqa: BLE001
        print(f"  *** RUN ABORTED: {type(exc).__name__}")
        print(f"  *** {str(exc).splitlines()[0][:100]}")
        print(f"  *** all {len(sessions)} sessions lost, including the healthy ones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
