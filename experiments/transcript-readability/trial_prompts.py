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
    # Waves 1 and 2 (13 Oct 2026): v1 already without a lone assent word, the
    # lesson of es/pt v1; fillers from each language's corpus conventions.
    "ca": "Eh, doncs, jo crec que sí, mm, saps? No ho sé, depèn.",
    "nl": "Uhm, nou, ik denk het wel, uh, en dan? Dat weet ik niet precies.",
    "sv": "Ehm, alltså, jag tänker väl så, eh, och sen då? Det beror lite på, liksom.",
    "da": "Øh, altså, jeg tror nok det, øh, og hvad så? Det kommer lidt an på.",
    "no": "Ehm, altså, jeg tror vel det, eh, og hva da? Det kommer litt an på, liksom.",
    # Waves 3 and 4: each shows the comma its language requires before a
    # subordinate clause; Ukrainian uses і and ї so it cannot read as Russian.
    "pl": "Yyy, no, wydaje mi się, że tak, eee, ale nie wiem. Mmm, trochę zależy, jak na to patrzeć.",
    "cs": "Eee, no, myslím si, že jo, mmm, ale nevím. Eee, záleží na tom, jak se to vezme.",
    "ru": "Э-э, ну, мне кажется, что да, м-м, но не знаю. Э, тут зависит от того, как посмотреть.",
    "uk": "Е-е, ну, мені здається, що так, м-м, але не знаю. Е, тут залежить від того, як подивитися.",
    "fi": "Öö, no, mä luulen, että se on ihan hyvä. Mutta, mm, en ole ihan varma, koska se riippuu vähän.",
    "tr": "Eee, şey, bence öyle, yani. Ama ııı, tam emin değilim, çünkü biraz duruma bağlı.",
    "ko": "음, 그러니까, 저는 그렇게 생각해요. 근데 어, 잘 모르겠어요, 좀 상황에 따라 다른 것 같아요.",
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
        "ca": "Eh, doncs, mm, la veritat és que sí, no? Eh, més o menys, perquè, em, depèn.",
        "nl": "Uhm, nou, uh, eigenlijk wel, toch? Uh, min of meer, want, uhm, dat ligt eraan.",
        "sv": "Öh, alltså, mm, det är väl så, eller hur? Eh, mer eller mindre, för att, mm, det beror på.",
        "da": "Øh, altså, mm, det er vel sådan set rigtigt, ikke? Øh, mere eller mindre, fordi, mm, det kommer an på.",
        "no": "Eh, altså, mm, det er vel egentlig sånn, ikke sant? Eh, mer eller mindre, fordi, mm, det kommer an på.",
        "pl": "Yyy, no, mmm, szczerze mówiąc, to chyba tak, nie? Eee, mniej więcej, bo, yyy, to zależy.",
        "cs": "Eee, no, mmm, popravdě asi jo, ne? Eee, víceméně, protože, mmm, to záleží.",
        "ru": "Э-э, ну, м-м, честно говоря, вроде да, вот. Э, более-менее, потому что, м-м, смотря как.",
        "uk": "Е-е, ну, м-м, чесно кажучи, начебто так, от. Е, більш-менш, тому що, м-м, буває по-різному.",
        "fi": "Öö, tota, niinku, kyl mä sitä mieltä oon, eiks nii? Mm, no, en tiiä, koska se vähän riippuu.",
        "tr": "Eee, yani, ııı, aslında öyle, değil mi? Şey, bilmiyorum, ııı, biraz duruma bağlı.",
        "ko": "음, 그, 사실 좀 그런 것 같아요, 그렇죠? 어, 뭐, 잘 모르겠는데, 음, 좀 다를 수도 있고요.",
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
    "ca": {"eh", "em", "mm", "ah"},
    "nl": {"uh", "uhm", "eh", "ehm"},
    "sv": {"eh", "öh", "ehm", "mm", "äh"},
    "da": {"øh", "øhm", "mm", "eh"},
    "no": {"eh", "ehm", "mm", "eee", "emm"},
    "pl": {"yyy", "eee", "mmm", "yy", "ee"},
    "cs": {"eee", "mmm", "ehm", "ee"},
    "ru": {"э", "ээ", "эээ", "м", "мм", "э-э", "м-м"},
    "uk": {"е", "ее", "м", "мм", "е-е", "м-м"},
    "fi": {"öö", "mm", "aa", "tota"},
    "tr": {"eee", "ııı", "şey", "ee"},
    "ko": {"음", "어", "그", "아"},
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
        "segments": [
            {"start": s.start_time, "end": s.end_time, "text": s.text,
             **({"inaudible": True} if s.inaudible else {})}
            for s in segs
        ],
        "metrics": metrics(texts, lang),
    }


def main(root: str, only: list[str], variant: str = "prompt", net: bool = False,
         include_none: bool = True, inaudible: bool = False, seed: int = 0) -> int:
    # The skipped-window and inaudible nets are off unless asked for, so runs
    # made before they existed stay comparable; a run with them is stored as
    # "<condition>+net" and "<condition>+net+inaudible".
    s05.SKIP_NET_ENABLED = net
    if not inaudible:
        s05.is_prompt_guess = lambda *_a, **_k: False  # type: ignore[assignment]
    suffix = ("+net" if net else "") + ("+inaudible" if inaudible else "")
    if seed:
        # Stage 5 seeds every file with 0; a different seed shows how much of a
        # difference between two runs is chance (the sampling fallback windows).
        import mlx.core as mx
        real_seed = mx.random.seed
        mx.random.seed = lambda _s: real_seed(seed)  # type: ignore[assignment]
        suffix += f"+seed{seed}"
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
    variant, net, include_none, inaudible, seed = "prompt", False, True, False, 0
    while args and args[0].startswith("--"):
        flag = args.pop(0)
        if flag.startswith("--variant="):
            variant = flag.split("=", 1)[1]
        elif flag == "--net":
            net = True
        elif flag == "--prompt-only":
            include_none = False
        elif flag == "--inaudible":
            inaudible = True
        elif flag.startswith("--seed="):
            seed = int(flag.split("=", 1)[1])
    sys.exit(main(args[0], args[1:], variant, net, include_none, inaudible, seed))
