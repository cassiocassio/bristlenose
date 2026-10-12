"""Fetch approved test recordings, carefully.

Reads an approved list (JSON) and downloads each file into a gitignored trial-run
folder, then converts it to a plain 16 kHz mono WAV, which is the only thing the
Whisper trials read. Built for untrusted media from the public internet:

- HTTPS only, from hosts on the list's own ``allowed_hosts``; every redirect hop
  is checked against it (no silent bounce to another host).
- A size cap and timeouts; the body streams to a ``.part`` file and is renamed
  only when complete.
- The first bytes must be a known audio/video container (MP3/ID3, Ogg, FLAC,
  WAV/RIFF, MP4/M4A, WebM/Matroska). A web page, archive or executable is
  refused and deleted. Nothing is unpacked.
- ffprobe and ffmpeg, the only tools that parse the media, run under macOS
  ``sandbox-exec`` with network denied and ``-protocol_whitelist file``, so a
  crafted playlist cannot make them fetch URLs or read other local files.
- Files are written 0644 (never executable) and recorded in ``manifest.json``
  with URL, licence, size and SHA-256. Nothing here is ever committed:
  the destination must be gitignored, or the script stops.

Usage::

    .venv/bin/python experiments/transcript-readability/fetch_samples.py approved.json

``approved.json``::

    {"dest": "trial-runs/whisper-prompt-samples",
     "allowed_hosts": ["upload.wikimedia.org", "archive.org"],
     "items": [{"lang": "es", "id": "es-1", "url": "https://...",
                "licence": "CC BY-SA 4.0", "licence_url": "https://..."}]}
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

MAX_BYTES = 400 * 1024 * 1024
TIMEOUT_S = 60
SANDBOX = "(version 1)(allow default)(deny network*)"
#: Wikimedia's User-Agent policy asks for a name and a way to reach the operator;
#: a bare agent gets throttled (429 after two files, 12 Oct 2026).
USER_AGENT = "BristlenoseResearch/1.0 (https://bristlenose.app; transcription test samples)"
#: Seconds between files, and the most a 429's Retry-After may make us wait.
PAUSE_S = 15
MAX_RETRY_WAIT_S = 300

MAGIC = (
    (0, b"ID3", "mp3"), (0, b"\xff\xfb", "mp3"), (0, b"\xff\xf3", "mp3"),
    (0, b"\xff\xf2", "mp3"), (0, b"OggS", "ogg"), (0, b"fLaC", "flac"),
    (0, b"RIFF", "wav"), (4, b"ftyp", "mp4"), (0, b"\x1a\x45\xdf\xa3", "mkv"),
)


def _sniff(head: bytes) -> str | None:
    for offset, sig, kind in MAGIC:
        if head[offset:offset + len(sig)] == sig:
            return kind
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None  # handled by hand, so each hop's host is checked


def _check_url(url: str, allowed: set[str]) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        raise ValueError(f"not https: {url}")
    if parts.hostname not in allowed:
        raise ValueError(f"host not allowed: {parts.hostname}")


def _download(url: str, allowed: set[str], dest: Path) -> str:
    opener = urllib.request.build_opener(_NoRedirect)
    for _hop in range(5):
        _check_url(url, allowed)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            resp = opener.open(req, timeout=TIMEOUT_S)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308) and exc.headers.get("Location"):
                url = urllib.parse.urljoin(url, exc.headers["Location"])
                continue
            if exc.code == 429:
                retry = exc.headers.get("Retry-After", "")
                wait = min(int(retry) if retry.isdigit() else 60, MAX_RETRY_WAIT_S)
                print(f"  rate-limited; waiting {wait} s")
                time.sleep(wait)
                continue
            raise
        length = resp.headers.get("Content-Length")
        if length and int(length) > MAX_BYTES:
            raise ValueError(f"too large: {length} bytes")
        part = dest.with_suffix(dest.suffix + ".part")
        digest = hashlib.sha256()
        total = 0
        with resp, open(part, "wb") as fh:
            while chunk := resp.read(1 << 20):
                total += len(chunk)
                if total > MAX_BYTES:
                    fh.close()
                    part.unlink()
                    raise ValueError("exceeded size cap while streaming")
                digest.update(chunk)
                fh.write(chunk)
        with open(part, "rb") as fh:
            kind = _sniff(fh.read(16))
        if kind is None:
            part.unlink()
            raise ValueError("not a recognised audio/video file; deleted")
        os.chmod(part, 0o644)
        part.rename(dest)
        return digest.hexdigest()
    raise ValueError("too many redirects")


def _sandboxed(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sandbox-exec", "-p", SANDBOX, *cmd],
        capture_output=True, text=True, timeout=1800, check=False,
    )


def _probe_and_convert(src: Path, wav: Path) -> float:
    ffprobe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise RuntimeError("ffprobe/ffmpeg not found")
    probe = _sandboxed([
        ffprobe, "-v", "error", "-protocol_whitelist", "file",
        "-select_streams", "a:0", "-show_entries", "format=duration:stream=codec_type",
        "-of", "json", str(src),
    ])
    info = json.loads(probe.stdout or "{}")
    if probe.returncode or not info.get("streams"):
        raise ValueError(f"no audio stream: {probe.stderr.strip()[:200]}")
    conv = _sandboxed([
        ffmpeg, "-v", "error", "-nostdin", "-protocol_whitelist", "file", "-y",
        "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav),
    ])
    if conv.returncode or not wav.exists():
        raise ValueError(f"conversion failed: {conv.stderr.strip()[:200]}")
    os.chmod(wav, 0o644)
    return float(info.get("format", {}).get("duration") or 0.0)


def main(list_path: str) -> int:
    spec = json.loads(Path(list_path).read_text(encoding="utf-8"))
    dest_root = Path(spec["dest"])
    check = subprocess.run(
        ["git", "check-ignore", "-q", str(dest_root / "probe")], check=False,
    )
    if check.returncode != 0:
        print(f"refusing: {dest_root} is not gitignored", file=sys.stderr)
        return 2
    allowed = set(spec["allowed_hosts"])
    manifest_path = dest_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for item in spec["items"]:
        lang_dir = dest_root / item["lang"]
        lang_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(urllib.parse.urlsplit(item["url"]).path).suffix.lower() or ".bin"
        src = lang_dir / f"{item['id']}{suffix}"
        wav = lang_dir / f"{item['id']}.wav"
        try:
            if not src.exists():
                time.sleep(PAUSE_S)  # be polite to the host
            sha = _download(item["url"], allowed, src) if not src.exists() else None
            duration = _probe_and_convert(src, wav)
        except Exception as exc:  # report and carry on with the next item
            print(f"✗ {item['id']}: {exc}")
            continue
        manifest[item["id"]] = {
            **item, "file": str(src), "wav": str(wav), "bytes": src.stat().st_size,
            "sha256": sha or manifest.get(item["id"], {}).get("sha256"),
            "duration_s": round(duration, 1),
        }
        print(f"✓ {item['id']}: {src.stat().st_size // 1024} KB, {duration / 60:.1f} min")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
