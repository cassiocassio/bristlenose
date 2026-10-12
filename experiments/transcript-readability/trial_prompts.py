"""Trial a style prompt per language: no prompt against the candidate, through the
shipped mlx code path (`_init_mlx_backend`), seeded, so each run is repeatable.

Reads ``manifest.json`` written by ``fetch_samples.py`` and writes one JSON per
(sample, condition) plus ``results.json`` next to it. Local compute only.

    .venv/bin/python experiments/transcript-readability/trial_prompts.py \
        trial-runs/whisper-prompt-samples [ids...]
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from bristlenose.stages import s05_transcribe as s05

CANDIDATES: dict[str, str] = {
    "es": "Eeh, bueno. Sí, claro, mm, ¿y entonces? Vale.",
    "fr": "Euh, bon. Oui, je pense, hein, et alors ? D'accord.",
    "de": "Ähm, ja. Also, ich denke schon, äh, und dann? Genau.",
    "it": "Ehm, sì. Allora, penso di sì, eh, e poi? Esatto.",
    "pt": "Ahn, é. Então, acho que sim, né, e depois? Certo.",
}

#: v2 (12 Oct 2026): v1's Spanish and Portuguese prompts skipped whole stretches of
#: speech (5-8 of the 30-second blocks per recording), and the skipped stretch came
#: back as a lone assent word from the prompt ("Certo."). v2 keeps the fillers, drops
#: the standalone assent words, and ends on a hedging clause.
VARIANTS: dict[str, dict[str, str]] = {
    "prompt": CANDIDATES,
    "prompt-v2": {
        "es": "Eeh, pues, mm, la verdad es que sí, ¿no? Eh, más o menos, porque, mm, depende.",
        "pt": "Ahn, então, hum, na verdade é isso, né? Eh, mais ou menos, porque, ahn, depende.",
        "it": "Ehm, allora, mh, in realtà sì, no? Eh, più o meno, perché, ehm, dipende.",
        # v1 French nearly doubled commas and barely moved full stops (comma-heavy
        # prompt); v2 has more full stops and still no lone assent word.
        "fr": "Euh, bon, je pense que oui. Mais ça dépend, hein. Et alors ? Je ne sais pas trop.",
    },
}

#: Pure hesitation forms per language (from each language's corpus conventions),
#: to see whether a prompt makes Whisper keep or drop them.
FILLERS: dict[str, set[str]] = {
    "es": {"eh", "eeh", "mm", "mmm", "em", "este"},
    "fr": {"euh", "heu", "hum", "mh", "hein"},
    "de": {"äh", "ähm", "öh", "hm", "ehm", "äm"},
    "it": {"ehm", "eh", "mh", "uhm", "mm"},
    "pt": {"ahn", "hum", "né", "eh", "uhn"},
}

_END = re.compile(r"[.?!…]+[\"'”»)]*$")


def metrics(texts: list[str], lang: str) -> dict[str, object]:
    joined = " ".join(texts)
    toks = joined.split()
    runs, cur = [], 0
    for t in toks:
        cur += 1
        if re.search(r"[.,?!;:…]+[\"'”»)]*$", t):
            runs.append(cur)
            cur = 0
    runs.append(cur)
    ends = [i for i, t in enumerate(toks[:-1]) if _END.search(t)]
    lower_starts = sum(1 for i in ends if toks[i + 1][:1].islower())
    fill = sum(1 for t in toks if re.sub(r"[^\w]", "", t.lower()) in FILLERS.get(lang, set()))
    return {
        "words": len(toks),
        "sentences": len(ends) + (1 if toks and _END.search(toks[-1]) else 0),
        "words_per_sentence": round(len(toks) / max(1, len(ends) + 1), 1),
        "longest_unpunctuated": max(runs) if toks else 0,
        "lowercase_after_sentence_end": lower_starts,
        "commas": joined.count(","),
        "fillers": fill,
        "inverted_marks": joined.count("¿") + joined.count("¡"),
    }


def run(wav: Path, lang: str, prompt: str | None) -> dict[str, object]:
    saved = dict(s05.STYLE_PROMPTS)
    s05.STYLE_PROMPTS.clear()
    s05.STYLE_PROMPTS.update({k: v for k, v in saved.items() if k != lang})
    if prompt:
        s05.STYLE_PROMPTS[lang] = prompt
    settings = type("S", (), {"whisper_model": "large-v3-turbo", "whisper_language": "auto"})()
    try:
        fn = s05._init_mlx_backend(settings)
        t0 = time.time()
        segs, detected = fn(wav, settings)
        secs = time.time() - t0
    finally:
        s05.STYLE_PROMPTS.clear()
        s05.STYLE_PROMPTS.update(saved)
    texts = [s.text for s in segs]
    return {
        "detected": detected,
        "secs": round(secs),
        "segments": [{"start": s.start_time, "end": s.end_time, "text": s.text} for s in segs],
        "metrics": metrics(texts, lang),
    }


def main(root: str, only: list[str], variant: str = "prompt", net: bool = False,
         include_none: bool = True) -> int:
    # The skipped-window net is off unless asked for, so runs made before it
    # existed stay comparable; a run with it is stored as "<condition>+net".
    s05.SKIP_NET_ENABLED = net
    suffix = "+net" if net else ""
    base = Path(root)
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    out_dir = base / "trials"
    out_dir.mkdir(exist_ok=True)
    results_path = out_dir / "results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    for sid, item in manifest.items():
        if only and sid not in only:
            continue
        lang = item["lang"]
        prompts = VARIANTS[variant]
        if lang not in prompts:
            continue
        pairs = [("none", None), (variant, prompts[lang])]
        if not include_none:
            pairs = pairs[1:]
        for base_cond, prompt in pairs:
            cond = base_cond + suffix
            out = out_dir / f"{sid}.{cond}.json"
            if out.exists():
                r = json.loads(out.read_text(encoding="utf-8"))
            else:
                r = run(Path(item["wav"]), lang, prompt)
                r.update(id=sid, lang=lang, condition=cond, prompt=prompt)
                out.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
            results[f"{sid}.{cond}"] = {k: r[k] for k in ("id", "lang", "condition", "detected",
                                                            "secs", "metrics", "prompt")}
            print(sid, cond, r["detected"], r["secs"], "s", json.dumps(r["metrics"]), flush=True)
    results_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    variant, net, include_none = "prompt", False, True
    while args and args[0].startswith("--"):
        flag = args.pop(0)
        if flag.startswith("--variant="):
            variant = flag.split("=", 1)[1]
        elif flag == "--net":
            net = True
        elif flag == "--prompt-only":
            include_none = False
    sys.exit(main(args[0], args[1:], variant, net, include_none))
