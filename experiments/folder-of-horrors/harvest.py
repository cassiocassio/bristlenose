#!/usr/bin/env python3
"""Harvest real, short media samples from this Mac into the folder of horrors.

Step 1 of the corpus described in the format-torture-corpus handoff: take what
the machine already has before synthesising the rest. Selection is by *format
signature*, not by file — one representative per (extension-as-written,
container, video codec, audio codec) so the corpus covers the matrix rather
than piling up 200 H.264 MP4s.

Safety rules, in order of how much they'd cost to get wrong:

1. **Never materialise a cloud placeholder.** iCloud Drive files report their
   logical size while occupying zero blocks; probing one triggers a download of
   arbitrary size over the user's connection. We skip anything with zero
   allocated blocks, and skip ``Mobile Documents`` wholesale.
2. **Never hang.** Every ffprobe gets a timeout; a file that won't answer is
   recorded as unprobeable, which is itself corpus-relevant.
3. **Read-only at source.** We copy, never move, and never touch the original.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Extensions worth hunting. Case matters for the corpus (iPhone writes .MOV),
# so we search case-insensitively but record what was actually written.
VIDEO_EXTS = [
    "mov", "mp4", "m4v", "mkv", "webm", "avi", "wmv", "asf", "flv", "f4v",
    "3gp", "3g2", "ogv", "mpg", "mpeg", "m2v", "vob", "m2ts", "dv", "mxf",
    "rm", "rmvb", "divx", "qt",
]
AUDIO_EXTS = [
    "m4a", "mp3", "wav", "aac", "flac", "ogg", "opus", "wma", "aiff", "aif",
    "caf", "amr", "au", "w64", "dss", "ds2", "wv", "ape",
]

MAX_DURATION = 60.0          # "less than a minute", per the ask
MAX_COPY_BYTES = 300 * 1024 * 1024
PROBE_TIMEOUT = 8


def spotlight(ext: str) -> list[Path]:
    """Filenames matching *ext*, case-insensitively, via Spotlight."""
    try:
        out = subprocess.run(
            ["mdfind", f'kMDItemFSName == "*.{ext}"c'],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except (subprocess.TimeoutExpired, OSError):
        return []
    return [Path(line) for line in out.splitlines() if line.strip()]


def is_cloud_placeholder(path: Path) -> bool:
    """True if reading this file would pull bytes down from iCloud.

    A dataless file advertises st_size but allocates no blocks. Checking
    st_blocks is portable enough here and does not depend on st_flags, which
    is macOS-only and silently absent elsewhere.
    """
    if "Mobile Documents" in path.parts or path.name.startswith("."):
        return True
    try:
        st = path.stat()
    except OSError:
        return True
    return st.st_size > 0 and st.st_blocks == 0


def probe(path: Path) -> dict | None:
    """Return ffprobe's view of *path*, or None if it will not answer."""
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def summarise(path: Path, info: dict) -> dict:
    fmt = info.get("format", {})
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        duration = float(fmt.get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "path": str(path),
        "name": path.name,
        "ext": path.suffix.lstrip("."),          # case as written
        "container": fmt.get("format_name", "?"),
        "vcodec": (video or {}).get("codec_name", "-"),
        "vprofile": (video or {}).get("profile", "-"),
        "pix_fmt": (video or {}).get("pix_fmt", "-"),
        "width": (video or {}).get("width", ""),
        "height": (video or {}).get("height", ""),
        "acodec": (audio or {}).get("codec_name", "-"),
        "achannels": (audio or {}).get("channels", ""),
        "arate": (audio or {}).get("sample_rate", ""),
        "duration": round(duration, 2),
        "size": int(fmt.get("size", 0) or 0),
        "creation_time": fmt.get("tags", {}).get("creation_time", ""),
    }


def signature(row: dict) -> tuple:
    """What makes a sample worth keeping — the format, not the content."""
    return (row["ext"], row["container"], row["vcodec"], row["acodec"])


def main() -> int:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("trial-runs/folder-of-horrors")
    dest.mkdir(parents=True, exist_ok=True)

    print("scanning Spotlight…", file=sys.stderr)
    candidates: set[Path] = set()
    for ext in VIDEO_EXTS + AUDIO_EXTS:
        candidates.update(spotlight(ext))
    print(f"  {len(candidates)} candidate files", file=sys.stderr)

    skipped_cloud = 0
    live: list[Path] = []
    for p in candidates:
        if is_cloud_placeholder(p):
            skipped_cloud += 1
            continue
        live.append(p)
    print(f"  {skipped_cloud} skipped (cloud placeholder / hidden)", file=sys.stderr)
    print(f"  probing {len(live)}…", file=sys.stderr)

    rows: list[dict] = []
    unprobeable: list[str] = []
    for i, p in enumerate(live, 1):
        if i % 100 == 0:
            print(f"    {i}/{len(live)}", file=sys.stderr)
        info = probe(p)
        if info is None:
            unprobeable.append(str(p))
            continue
        rows.append(summarise(p, info))

    short = [r for r in rows if 0 < r["duration"] <= MAX_DURATION]
    print(f"  {len(rows)} probed, {len(short)} under {MAX_DURATION:.0f}s, "
          f"{len(unprobeable)} unprobeable", file=sys.stderr)

    # One representative per signature: prefer the smallest, so the corpus stays
    # light and a 4K clip never stands in for a format a 2MB clip demonstrates.
    by_sig: dict[tuple, list[dict]] = defaultdict(list)
    for r in short:
        by_sig[signature(r)].append(r)
    chosen = [min(v, key=lambda r: r["size"]) for v in by_sig.values()]
    chosen.sort(key=lambda r: (r["ext"].lower(), r["container"], r["vcodec"]))

    copied, collisions = [], []
    for r in chosen:
        src = Path(r["path"])
        if r["size"] > MAX_COPY_BYTES:
            continue
        target = dest / src.name
        if target.exists():
            collisions.append(src.name)
            stem, suffix = src.stem, src.suffix
            n = 2
            while target.exists():
                target = dest / f"{stem}-{n}{suffix}"
                n += 1
        try:
            # copyfile, not copy2: copy2 replicates metadata, and SIP-protected
            # sources under /System carry BSD flags the copy cannot be given.
            # copy2 raises *after* writing the bytes, which orphaned seven files
            # in the destination with no manifest row on the first run.
            shutil.copyfile(src, target)
            try:
                shutil.copystat(src, target)
            except OSError:
                pass  # metadata is a nicety; the bytes are the sample
        except OSError as exc:
            print(f"  copy failed {src}: {exc}", file=sys.stderr)
            continue
        r["copied_as"] = target.name
        copied.append(r)

    fields = ["copied_as", "ext", "container", "vcodec", "vprofile", "acodec",
              "achannels", "arate", "duration", "size", "width", "height",
              "creation_time", "name", "path"]
    with (dest / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in copied:
            w.writerow(r)

    # The full probe result is worth keeping: the formats this machine does NOT
    # have are what the synthesis step has to cover.
    with (dest / "probe-all.json").open("w", encoding="utf-8") as fh:
        json.dump({"probed": rows, "unprobeable": unprobeable,
                   "skipped_cloud": skipped_cloud}, fh, indent=2)

    print(f"\ncopied {len(copied)} samples ({len(by_sig)} distinct signatures) → {dest}",
          file=sys.stderr)
    if collisions:
        print(f"name collisions renamed: {', '.join(collisions)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
