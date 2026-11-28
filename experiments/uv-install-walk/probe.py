"""Exercise an installed Bristlenose past `--version`: real media, FFmpeg, PII, serve.

Run with the installed tool's own Python, after `bristlenose transcribe <project>`:

    probe.py <project-dir> [pii]

Prints one `PROBE <name>: ok|FAIL ...` line per check and exits non-zero if any
check failed. No LLM call is made (nothing here needs a key).
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

failed = []


def report(name: str, ok: bool, detail: str = "") -> None:
    print(f"PROBE {name}: {'ok' if ok else 'FAIL'} {detail}".rstrip(), flush=True)
    if not ok:
        failed.append(name)


project = Path(sys.argv[1])
want_pii = len(sys.argv) > 2 and sys.argv[2] == "pii"
out = project / "bristlenose-output"
raw = out / "transcripts-raw"

# 1. Transcripts: every session that had speech has a non-empty .txt.
txts = sorted(raw.glob("*.txt"))
sizes = {t.name: len(t.read_text(encoding="utf-8").splitlines()) for t in txts}
# 7 for the full walk project (8 speech sessions, one of them the long Word
# transcript); set PROBE_MIN_TRANSCRIPTS for a smaller folder.
min_txts = int(__import__("os").environ.get("PROBE_MIN_TRANSCRIPTS", "7"))
report("transcripts", len(txts) >= min_txts and all(n > 2 for n in sizes.values()), str(sizes))

# 2. FFmpeg decoding: a thumbnail from every video (H.264 from Teams/Meet, HEVC from a phone).
from bristlenose.utils.video import extract_thumbnail  # noqa: E402

for video in sorted(p for p in project.iterdir() if p.suffix.lower() in {".mp4", ".mov"}):
    dest = Path("/tmp") / f"thumb-{abs(hash(video.name))}.jpg"
    got = extract_thumbnail(video, dest, 5.0)
    size = dest.stat().st_size if got and dest.exists() else 0
    report(f"thumbnail[{video.name}]", size > 1000, f"{size} bytes")

# 3. PII redaction on the real transcripts (fetches the spaCy model if missing).
if want_pii:
    from bristlenose.config import load_settings
    from bristlenose.pipeline import load_transcripts_from_dir
    from bristlenose.stages.s07_pii_removal import remove_pii

    transcripts = load_transcripts_from_dir(raw)
    t0 = time.monotonic()
    try:
        cleaned, redactions = remove_pii(transcripts, load_settings())
        report(
            "pii",
            len(cleaned) == len(transcripts),
            f"{len(cleaned)} transcripts, {len(redactions)} redactions, {time.monotonic() - t0:.0f}s",
        )
    except Exception as exc:  # report, don't hide
        report("pii", False, f"{type(exc).__name__}: {exc}")

# 4. serve: starts, answers /api/health, serves the React report.
proc = subprocess.Popen(
    ["bristlenose", "serve", str(project), "--no-open", "--port", "8484"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)
health = report_status = None
deadline = time.monotonic() + 120
while time.monotonic() < deadline and health is None:
    if proc.poll() is not None:
        break
    try:
        with urllib.request.urlopen("http://127.0.0.1:8484/api/health", timeout=2) as r:
            health = r.status
    except OSError:
        time.sleep(1)
if health is not None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8484/report/", timeout=10) as r:
            body = r.read()
            report_status = r.status
            report("serve report", r.status == 200 and b"<script" in body, f"{r.status}, {len(body)} bytes")
    except OSError as exc:
        report("serve report", False, str(exc))
report("serve health", health == 200, f"{health}")
proc.terminate()
try:
    tail, _ = proc.communicate(timeout=20)
except subprocess.TimeoutExpired:
    proc.kill()
    tail, _ = proc.communicate()
if health != 200 or report_status != 200:
    print("serve output (tail):\n" + "\n".join((tail or "").splitlines()[-25:]))

print(f"PROBE SUMMARY: {'all ok' if not failed else 'failed: ' + ', '.join(failed)}")
sys.exit(1 if failed else 0)
