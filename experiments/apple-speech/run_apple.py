"""Run Apple's on-device transcribers over the trial corpus.

Reads the multilingual manifest (trial-runs/whisper-prompt-samples/manifest.json)
plus the English and CJK WAVs in trial-runs/apple-speech/audio/, and runs the
`transcribe` probe (transcribe.swift) once per file and engine. One locale's
model is installed if missing (timed, logged to installs.jsonl) and released
after its files are done, because an app may hold at most 5 reserved locales.

    .venv/bin/python experiments/apple-speech/run_apple.py BIN speech|dictation [ids...]

Outputs: trial-runs/apple-speech/apple/<id>.<engine>.json. Local compute only,
apart from Apple's own model download for a locale not yet on the Mac.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("trial-runs")
OUT = ROOT / "apple-speech"
MANIFEST = ROOT / "whisper-prompt-samples" / "manifest.json"

#: One locale per language, the region where the recording's speakers are from
#: when known. The model asset is per language; the region sets formatting.
LOCALE = {
    "es": "es-ES", "fr": "fr-FR", "de": "de-DE", "it": "it-IT", "ko": "ko-KR",
    "ca": "ca-ES", "nl": "nl-NL", "sv": "sv-SE", "da": "da-DK", "no": "nb-NO",
    "pl": "pl-PL", "cs": "cs-CZ", "ru": "ru-RU", "uk": "uk-UA", "fi": "fi-FI",
    "tr": "tr-TR", "ja": "ja-JP", "zh": "zh-CN",
}
BY_ID = {"pt-br-1": "pt-BR", "pt-pt-1": "pt-PT", "pt-pt-2": "pt-PT", "pt-ao-1": "pt-PT",
         "de-3": "de-AT"}
SPEECH_LANGS = {"en", "es", "fr", "de", "it", "pt", "ko", "ja", "zh"}


def corpus() -> list[dict[str, str]]:
    items = []
    for sid, it in json.loads(MANIFEST.read_text()).items():
        items.append({"id": sid, "lang": it["lang"], "wav": it["wav"]})
    for wav in sorted((OUT / "audio").glob("*.wav")):
        sid = wav.stem
        items.append({"id": sid, "lang": sid.split("-")[0], "wav": str(wav)})
    return items


def locale_for(item: dict[str, str]) -> str:
    if item["id"] in BY_ID:
        return BY_ID[item["id"]]
    if item["lang"] == "en":
        return "en-US" if "fossda" in item["id"] else "en-GB"
    return LOCALE[item["lang"]]


def main(binary: str, engine: str, only: list[str]) -> int:
    (OUT / "apple").mkdir(parents=True, exist_ok=True)
    items = [i for i in corpus() if not only or i["id"] in only or i["lang"] in only]
    if engine == "speech":
        items = [i for i in items if i["lang"] in SPEECH_LANGS]
    items.sort(key=lambda i: (locale_for(i)[:2], i["id"]))
    current: str | None = None
    used: set[str] = set()
    for item in items:
        loc = locale_for(item)
        lang = loc.split("-")[0]
        if current and current != lang and current != "en":
            # Free the language's reservations before the next (limit of 5).
            for old in used:
                subprocess.run([binary, "--release", old], check=False)
            used = set()
        current = lang
        used.add(loc)
        out = OUT / "apple" / f"{item['id']}.{engine}.json"
        if out.exists():
            continue
        t0 = time.time()
        p = subprocess.run([binary, item["wav"], loc, str(out), "--engine", engine, "--install"],
                           capture_output=True, text=True)
        print(item["id"], loc, p.stdout.strip() or p.stderr.strip()[-300:], flush=True)
        if out.exists():
            d = json.loads(out.read_text())
            if d.get("install_s") is not None:
                with (OUT / "installs.jsonl").open("a") as f:
                    f.write(json.dumps({"engine": engine, "locale": loc, "install_s": d["install_s"],
                                        "status_before": d["status_before"],
                                        "when": time.strftime("%Y-%m-%d %H:%M"),
                                        "process_s": round(time.time() - t0, 1)}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3:]))
