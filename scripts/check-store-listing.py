#!/usr/bin/env python3
"""Mechanical pre-paste check of the Mac App Store listing text.

Usage: scripts/check-store-listing.py [listing.md] [--shots DIR] [--preview FILE]   (default: the private draft)
Exit 1 on any FAIL. A PASS prints a hash of the checked fields so what is pasted
into App Store Connect can be shown to be what was checked.

Limits, stated plainly: this proves the required sentences and fields EXIST and that
known rejection triggers are absent. It cannot prove the copy is adequate, and nothing
here can stop a manual paste. Rules: docs/private/app-store-launch/rejection-checklist.md.
"""

import hashlib
import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / "docs/private/app-store-launch/listing-draft.md"
LIMITS = {
    "name": 30,
    "subtitle": 30,
    "promo": 170,
    "desc": 4000,
}  # keywords: 100 BYTES, checked below
PUBLIC = ["name", "subtitle", "promo", "keywords", "desc", "captions"]
MARKS = [
    "claude",
    "chatgpt",
    "openai",
    "anthropic",
    "gemini",
    "azure",
    "miro",
    "zoom",
    "teams",
    "google",
    "microsoft",
    "notion",
    "figma",
    "dovetail",
    "marvin",
    "obsidian",
    "ollama",
]


def parse(path):
    f = {}
    for m in re.finditer(
        r"^## (\w+)[^\n]*\n(.*?)(?=^## |\Z)", path.read_text(encoding="utf-8"), re.S | re.M
    ):
        f[m.group(1)] = m.group(2).strip()
    return f


MAC_SIZES = {(1280, 800), (1440, 900), (2560, 1600), (2880, 1800)}


def check_shots(d):
    """Screenshot files: macOS only (uses sips). Returns list of failure strings."""
    import subprocess

    bad, files = (
        [],
        sorted(p for p in Path(d).iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")),
    )
    if not 1 <= len(files) <= 10:
        bad.append(f"{len(files)} screenshots; need 1 to 10 PNG/JPEG files")
    for p in files:
        o = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", "-g", "hasAlpha", str(p)],
            capture_output=True,
            text=True,
        ).stdout
        w = int(re.search(r"pixelWidth: (\d+)", o).group(1))
        h = int(re.search(r"pixelHeight: (\d+)", o).group(1))
        if (w, h) not in MAC_SIZES:
            bad.append(f"{p.name}: {w}x{h} is not one of 1280x800, 1440x900, 2560x1600, 2880x1800")
        if "hasAlpha: yes" in o:
            bad.append(f"{p.name}: has an alpha channel (not allowed)")
    return bad


def check_preview(fp):
    """Mac app preview: 15-30 s, <=500 MB, H.264, <=30 fps, 1920x1080 landscape, stereo AAC."""
    import json
    import subprocess

    p = Path(fp)
    bad = []
    if p.suffix.lower() not in (".mov", ".m4v", ".mp4"):
        bad.append("extension must be .mov, .m4v or .mp4")
    if p.stat().st_size > 500 * 1024 * 1024:
        bad.append("file is over 500 MB")
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)],
        capture_output=True,
        text=True,
    )
    if r.returncode:
        return bad + ["ffprobe could not read the file"]
    j = json.loads(r.stdout)
    dur = float(j["format"]["duration"])
    if not 15 <= dur <= 30:
        bad.append(f"duration {dur:.1f}s; must be 15 to 30 s")
    v = next((x for x in j["streams"] if x["codec_type"] == "video"), None)
    a = next((x for x in j["streams"] if x["codec_type"] == "audio"), None)
    if not v:
        return bad + ["no video stream"]
    if v["codec_name"] != "h264":
        bad.append(f"video codec {v['codec_name']}; must be H.264")
    if (v["width"], v["height"]) != (1920, 1080):
        bad.append(f"{v['width']}x{v['height']}; Mac previews are 1920x1080 landscape")
    n, d = map(int, v["avg_frame_rate"].split("/"))
    fps = n / d if d else 0
    if fps > 30.01:
        bad.append(f"{fps:.1f} fps; max 30")
    if not a:
        bad.append("no audio track (spec lists stereo audio)")
    elif a["channels"] != 2:
        bad.append(f"audio has {a['channels']} channel(s); must be stereo")
    return bad


def main():
    args = sys.argv[1:]
    shots = preview = None
    if "--preview" in args:
        i = args.index("--preview")
        preview = args[i + 1]
        del args[i : i + 2]
    if "--shots" in args:
        i = args.index("--shots")
        shots = args[i + 1]
        del args[i : i + 2]
    path = Path(args[0]) if args else DEFAULT
    f = parse(path)
    out = []  # (level, guideline, message)

    def fail(g, m):
        out.append(("FAIL", g, m))

    def warn(g, m):
        out.append(("WARN", g, m))

    for k in [
        "name",
        "subtitle",
        "promo",
        "keywords",
        "desc",
        "privacy_url",
        "support_url",
        "review_notes",
        "captions",
        "copyright",
    ]:
        v = f.get(k, "")
        if not v:
            fail("2.1/1.5/5.1.1", f"field '{k}' is missing or empty")
        elif re.search(r"\bTODO\b", v):
            fail("2.1/1.5/5.1.1", f"field '{k}' still says TODO")
    for k, n in LIMITS.items():
        if len(f.get(k, "")) > n:
            fail("2.3.7" if k == "name" else "limit", f"{k} is {len(f[k])}/{n} chars")
    kw = f.get("keywords", "")
    if len(kw.encode("utf-8")) > 100:
        fail("limit", f"keywords are {len(kw.encode('utf-8'))}/100 bytes")
    words = [w.strip() for w in kw.split(",") if w.strip()]
    for w in words:
        if len(w) <= 2:
            fail("platform spec", f"keyword '{w}' must be longer than two characters")
    if len({x.lower() for x in words}) != len(words):
        fail("product page guide", "duplicate keywords")
    for w in words + [x for ww in words for x in ww.split()]:
        if w.lower() in {"app", "bristlenose"} | set(
            re.findall(r"[a-z]+", f.get("name", "").lower())
        ):
            fail("platform spec", f"keyword '{w}' duplicates the app name or is the word 'app'")
    if re.search(r"<\s*/?[a-z][^>]*>", f.get("desc", ""), re.I):
        fail("platform spec", "description must be plain text: HTML found")
    if re.search(r"(\*\*|^#{1,6} |\]\()", f.get("desc", ""), re.M):
        warn("platform spec", "description contains markdown; the store shows it literally")
    if re.search(r"[$£€]\s?\d", f.get("desc", "")):
        fail(
            "product page guide",
            "description contains a specific price (pricing may differ by region)",
        )
    for k in ("privacy_url", "support_url", "marketing_url"):
        v = f.get(k, "")
        if k == "marketing_url" and not v:
            continue
        if v and not re.search(r"\bTODO\b", v) and not re.fullmatch(r"https://\S+", v):
            fail("5.1.1(i)/1.5", f"{k} must be one https URL")

    for k in PUBLIC:
        v = f.get(k, "")
        if re.search(r"\b(beta|alpha|demo|early access|pre-?release)\b", v, re.I):
            fail(
                "2.2",
                f"'{k}' calls the app a beta/demo/alpha: not allowed on the store, use TestFlight",
            )
        if re.search(r"\btrial\b", v, re.I):
            warn(
                "2.2/3.1.1",
                f"'{k}' says trial: ok only for a real IAP trial ('XX-day Trial', 3.1.1) or subscription free trial (3.1.2)",
            )
        if re.search(r"\b(android|google play|play store)\b", v, re.I):
            fail("2.3.10", f"'{k}' names another mobile platform/marketplace")
        if re.search(r"\b(windows|linux|snap)\b", v, re.I):
            warn(
                "2.3.10",
                f"'{k}' names another platform: confirm it is not a store/marketplace reference",
            )
    for k in ("name", "subtitle", "keywords", "captions", "promo"):
        v = f.get(k, "")
        hit = [t for t in MARKS if re.search(rf"\b{t}\b", v, re.I)]
        if hit and k != "promo":
            fail("2.3.7/5.2.1", f"'{k}' contains third-party names: {', '.join(hit)}")
        if hit and k == "promo":
            warn("2.3.7/5.2.1", f"'promo' contains third-party names: {', '.join(hit)}")
        if k != "promo" and re.search(
            r"[$£€]\s?\d|\b(free|price|discount|sale|cheap|% off)\b", v, re.I
        ):
            fail("2.3.7", f"'{k}' contains pricing language")
    for k in PUBLIC:
        v = f.get(k, "")
        if re.search(
            r"editors?['’]? choice|apple[- ](recommended|endorsed|approved)|app of the year",
            v,
            re.I,
        ):
            fail(
                "5.2.4",
                f"'{k}' implies an Apple endorsement or badge (Apple applies Editors' Choice itself)",
            )
    sub = f.get("subtitle", "")
    if re.search(
        r"\b(best|#1|number one|fastest|only|leading|world'?s|award[- ]winning|perfect)\b",
        sub,
        re.I,
    ):
        fail("2.3.7", "subtitle makes an unverifiable product claim")
    caps = [ln for ln in f.get("captions", "").splitlines() if ln.strip()]
    if not 3 <= len(caps) <= 10:
        fail("2.3.3", f"{len(caps)} captions; the store takes 1 to 10 screenshots, we require 3+")
    for c in caps:
        if len(c.split()) > 12:
            warn("style", f"caption over 12 words: {c[:40]}...")

    d = f.get("desc", "")
    if not re.search(r"\b(sent|sends|goes|go)\b[^.]{0,60}\bto\b[^.]{0,60}\bAI\b", d, re.I | re.S):
        fail("5.1.2(i)", "description must say the interview text is sent to an AI provider")
    if not re.search(r"\byour own (AI )?(account|key)\b", d, re.I):
        fail("2.3.1/5.1.2(i)", "description must say the analysis needs the user's own AI account")
    if not re.search(r"\b(Claude|ChatGPT|Gemini|Azure OpenAI)\b", d):
        fail("2.3.1", "description must name the AI providers the app can use")
    if not re.search(r"\bon your Mac\b", d, re.I):
        warn("2.3.1", "description does not say what runs on the Mac")
    if re.search(r"\bimport[^.\n]{0,60}\bzoom\b|\bzoom\b[^.\n]{0,30}\bimport", d, re.I):
        fail(
            "2.3.1", "description claims Zoom import; it is a beta-only feature, say 'transcripts'"
        )
    notes = f.get("review_notes", "")
    sizes = {
        k: set(re.findall(r"(\d+(?:\.\d+)?)\s?GB(?!\s+(?:of\s+)?free)", f.get(k, "")))
        for k in ("desc", "review_notes")
    }
    if sizes["desc"] and sizes["review_notes"] and sizes["desc"] != sizes["review_notes"]:
        fail(
            "2.3.1/4.2.3",
            "download size differs between description "
            f"({', '.join(sorted(sizes['desc']))} GB) and review notes "
            f"({', '.join(sorted(sizes['review_notes']))} GB)",
        )
    if (
        notes
        and not re.search(r"\bkey\b", notes, re.I)
        or notes
        and not re.search(r"\btest\b", notes, re.I)
    ):
        fail(
            "2.1(a)",
            "review notes must say a test key/account is supplied and how the reviewer runs an analysis",
        )

    if preview:
        for m in check_preview(preview):
            fail("2.3.4/spec", m)
    if shots:
        for m in check_shots(shots):
            fail("2.3.3/spec", m)
    for lv, g, m in out:
        print(f"{lv:4}  [{g}]  {m}")
    n = sum(1 for o in out if o[0] == "FAIL")
    if n:
        print(f"\nNOT READY: {n} FAIL ({len(out) - n} warn). Do not paste into App Store Connect.")
        sys.exit(1)
    h = hashlib.sha256("\n".join(f"{k}={f.get(k, '')}" for k in sorted(f)).encode()).hexdigest()[
        :12
    ]
    print(
        f"\nPASS ({len(out)} warn). fields hash {h}. This does not check the in-app items in the checklist."
    )


main()
