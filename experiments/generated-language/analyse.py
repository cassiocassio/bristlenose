#!/usr/bin/env python3
"""Read the passes on disk and write `out/compare.md`.

Three measurements, per the README:

  1. language per field, with labels and descriptions counted SEPARATELY — a
     model that translates the two-word label and leaves the fifteen-word
     description in English is a plausible failure, and a single percentage
     would hide it;
  2. stability across passes within a cell (theme count, label overlap, ARI);
  3. drift between steered and unsteered on the same corpus and provider,
     reported NEXT TO the within-condition ARI, because a steered-vs-unsteered
     gap smaller than the pass-to-pass wobble is not a gap.

No third-party dependencies. `scikit-learn` is not in this venv — the
thematic-spike README says it installs it, but the venv has been rebuilt since
and it is gone. ARI is a closed form over a contingency table, so it is
computed here and self-checked at import against four published values rather
than pulling numpy and scipy into a throwaway.

The language classifier is deliberately crude and says so: it scores marker
words and orthography, and anything short or close goes to `?` for a human to
read. A two-word screen label is the normal case here, not the edge, so the
`?` column is expected to be non-empty and is not a defect. The table is the
finding; the classifier only sorts it.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

# --------------------------------------------------------------------------
# Adjusted Rand index
# --------------------------------------------------------------------------


def adjusted_rand(a: list[int], b: list[int]) -> float:
    """Agreement between two partitions of the same items, chance-corrected.

    1.0 identical (relabelling included), ~0 for independent partitions, and
    negative for worse-than-chance. The closed form over the contingency table
    n_ij = |A_i ∩ B_j|.
    """
    if len(a) != len(b):
        raise ValueError("partitions cover different item counts")
    n = len(a)
    if n < 2:
        return 1.0
    table: Counter = Counter(zip(a, b))
    sum_ij = sum(comb(v, 2) for v in table.values())
    sum_a = sum(comb(v, 2) for v in Counter(a).values())
    sum_b = sum(comb(v, 2) for v in Counter(b).values())
    expected = sum_a * sum_b / comb(n, 2)
    maximum = (sum_a + sum_b) / 2
    if maximum == expected:
        return 1.0                      # both partitions trivial; nothing to disagree about
    return (sum_ij - expected) / (maximum - expected)


def _self_check() -> None:
    """Four published values. A metric nothing checks is a number, not a measure."""
    cases = [
        (([0, 0, 1, 1], [0, 0, 1, 1]), 1.0),
        (([0, 0, 1, 1], [1, 1, 0, 0]), 1.0),     # relabelling must not matter
        (([0, 0, 1, 1], [0, 1, 0, 1]), -0.5),    # worse than chance
        (([0, 0, 0, 0], [0, 1, 2, 3]), 0.0),
    ]
    for (x, y), want in cases:
        got = adjusted_rand(x, y)
        if abs(got - want) > 1e-9:
            raise AssertionError(f"ARI({x},{y}) = {got}, expected {want}")


_self_check()

# --------------------------------------------------------------------------
# Language classification
# --------------------------------------------------------------------------

_EN = {"the", "and", "of", "to", "in", "for", "with", "on", "is", "are", "a", "an",
       "that", "this", "their", "from", "about", "how", "what", "when", "over",
       "into", "during", "its", "it", "as", "at", "by", "or", "challenges",
       "experience", "issues", "concerns", "expectations"}
_ES = {"el", "los", "las", "un", "con", "para", "por", "como", "más", "muy", "también",
       "están", "está", "sobre", "desde", "entre", "sin", "sus", "al", "lo", "se",
       "búsqueda", "página", "experiencia", "navegación", "productos"}
_CA = {"amb", "això", "és", "què", "aquest", "aquesta", "els", "hi", "seva", "seu",
       "molt", "però", "fer", "tenir", "ja", "nosaltres", "dins", "cap", "una",
       "cerca", "pàgina", "experiència", "navegació", "productes"}
# Shared between es and ca — counted for neither, or every Catalan string reads
# as Spanish on `de que la del`.
# `compra` is spelled identically in both and counted for neither: a word
# two languages share is evidence for neither of them.
_SHARED_ROMANCE = {"de", "que", "la", "del", "una", "en", "i", "y", "les", "no",
                   "compra"}

_CA_MARKS = ("l'", "d'", "n'", "s'", "·", "tx", "ny", "à", "è", "ò", "ï")
_ES_MARKS = ("ñ", "¿", "¡", "ción", "ciones", "sión")
#: Evidence the string is Romance rather than English, carrying no information
#: about WHICH Romance language. The shared function words are the bulk of it —
#: excluding them from the es/ca scores is right (a word two languages share
#: cannot discriminate them) but throwing them away entirely was wrong: `de` and
#: `que` are excellent evidence that the text is not English, which is the first
#: question. Without this, every label whose distinctive vocabulary sat outside
#: a 30-word lexicon fell to `?`, and openai's terser labels are mostly that
#: shape — "Decisión de estudiar gastronomía" read as unknown.
_ROMANCE_ACCENTS = "áéíóúàèòïüñç"


def _words(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+['·]?[^\W\d_]*", text.lower(), flags=re.UNICODE)


def classify(text: str) -> str:
    """`en` / `es` / `ca` / `mixed` / `?`. Crude by design — see the module docstring."""
    words = [w for w in _words(text) if w not in _SHARED_ROMANCE]
    if not words:
        return "?"
    low = text.lower()
    score = {
        "en": sum(w in _EN for w in words),
        "es": sum(w in _ES for w in words) + sum(m in low for m in _ES_MARKS),
        "ca": sum(w in _CA for w in words) + sum(m in low for m in _CA_MARKS),
    }
    # An accented character no English word carries is weak evidence against en.
    if any("WITH" in unicodedata.name(c, "") for c in text if c.isalpha() and ord(c) > 127):
        score["en"] -= 1

    ranked = sorted(score.items(), key=lambda kv: -kv[1])
    (top, hi), (_, second) = ranked[0], ranked[1]
    if hi > 0 and hi != second:
        return top
    if hi > 0 and hi == second:
        return "mixed"

    # No distinctive vocabulary matched. Before giving up, ask the cheaper
    # question: is this Romance at all? Shared function words and Romance
    # accents both answer it, and Catalan's orthography (à, è, ò, l·l, ny, tx,
    # elided articles) is distinctive enough that its absence in a Romance
    # string of any length is good evidence for Spanish.
    romance = sum(w in _SHARED_ROMANCE for w in _words(text))
    romance += sum(c in _ROMANCE_ACCENTS for c in low)
    if romance and score["en"] <= 0:
        return "ca" if any(m in low for m in _CA_MARKS) else "es"
    if score["en"] > 0:
        return "en"
    # The mirror of the Romance fallback, and needed for the same reason: an
    # English label built only of content words ("Gastronomy education
    # background") carries no function word either, and fell to `?` while its
    # Spanish counterpart was resolved. In a corpus known to be en/es/ca, a
    # multi-word phrase with no accent and no shared Romance word is English —
    # a Spanish or Catalan phrase of that length almost always carries an
    # article or a preposition. Single words stay `?`: `Checkout` and `Stage`
    # are the shape this must not guess at, being exactly the on-screen terms
    # the mixed corpus exists to watch.
    if len(words) >= 3 and text.isascii():
        return "en"
    return "?"


# --------------------------------------------------------------------------
# Reading the passes
# --------------------------------------------------------------------------

#: stage → (label field, description field, container of quotes)
FIELDS = {
    "s10": ("screen_label", "description"),
    "s11": ("theme_label", "description"),
    "s08": ("topic_label", None),
}


def load_passes() -> list[dict]:
    out = []
    for path in sorted(OUT.rglob("*_pass*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        record["pass"] = int(path.stem.rsplit("pass", 1)[1])
        record["path"] = path
        out.append(record)
    return out


def labels_and_descriptions(record: dict) -> tuple[list[str], list[str]]:
    label_f, desc_f = FIELDS[record["stage"]]
    labels, descs = [], []
    for group in record["result"]:
        if record["stage"] == "s08":
            for b in group.get("boundaries", []):
                labels.append(b.get(label_f, ""))
            continue
        labels.append(group.get(label_f, ""))
        if desc_f and group.get(desc_f):
            descs.append(group[desc_f])
    return labels, descs


def partition(record: dict) -> dict[tuple, int]:
    """quote key → group index. s08 has no partition and returns empty."""
    if record["stage"] == "s08":
        return {}
    out = {}
    for i, group in enumerate(record["result"]):
        for q in group.get("quotes", []):
            out[(q["participant_id"], q["start_timecode"], q["text"][:40])] = i
    return out


def compare_partitions(a: dict[tuple, int], b: dict[tuple, int]) -> tuple[float, int]:
    """ARI over the quotes both passes placed, and how many that was."""
    shared = sorted(set(a) & set(b))
    if len(shared) < 2:
        return float("nan"), len(shared)
    return adjusted_rand([a[k] for k in shared], [b[k] for k in shared]), len(shared)


def _norm(s: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFD", s.lower())
                       if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()


def main() -> int:
    records = load_passes()
    if not records:
        print("no passes on disk — run `run.py --yes` first", file=sys.stderr)
        return 1

    lines = ["# Generated-language spike — results", "",
             f"{len(records)} pass file(s). Language of each generated field, "
             "labels and descriptions counted separately.", ""]

    # ---- 1. language per field ------------------------------------------
    lines += ["## Language per field", "",
              "| corpus | stage | provider | condition | field | " +
              " | ".join(("en", "es", "ca", "mixed", "?")) + " |",
              "|---|---|---|---|---|" + "---|" * 5]
    by_cell = defaultdict(list)
    for r in records:
        by_cell[(r["corpus"], r["stage"], r["provider"], r["condition"])].append(r)

    for key, group in sorted(by_cell.items()):
        for field_name, extract in (("label", 0), ("description", 1)):
            tally: Counter = Counter()
            for r in group:
                for value in labels_and_descriptions(r)[extract]:
                    tally[classify(value)] += 1
            if not tally:
                continue
            row = " | ".join(str(tally.get(k, 0)) for k in ("en", "es", "ca", "mixed", "?"))
            lines.append(f"| {' | '.join(key)} | {field_name} | {row} |")

    # ---- 2 & 3. stability, and steered vs unsteered ----------------------
    lines += ["", "## Stability and drift", "",
              "ARI over the quote→group partition. `un` and `st` are the wobble "
              "*within* each condition — how much the same cell disagrees with "
              "itself across passes. `across` is steered vs unsteered.", "",
              "Read `across` against the two wobble bands, not against 1.0. The "
              "two conditions are reported separately because pooling them hides "
              "the case that matters: a steer that makes the analysis *less* "
              "stable would raise the pooled band and so disguise itself as "
              "ordinary noise.", "",
              "| corpus | stage | provider | groups | un | st | across |",
              "|---|---|---|---|---|---|---|"]

    for (corpus, stage, provider), _ in sorted(
        {(c, s, p): 1 for c, s, p, _ in by_cell}.items()
    ):
        if stage == "s08":
            continue
        cells = {cond: by_cell.get((corpus, stage, provider, cond), [])
                 for cond in ("unsteered", "steered")}
        within = {}
        for cond, group in cells.items():
            band = []
            for x, y in combinations(group, 2):
                ari, n = compare_partitions(partition(x), partition(y))
                if n >= 2:
                    band.append(ari)
            within[cond] = band
        across = []
        for x in cells["unsteered"]:
            for y in cells["steered"]:
                ari, n = compare_partitions(partition(x), partition(y))
                if n >= 2:
                    across.append(ari)
        counts = sorted({len(r["result"]) for g in cells.values() for r in g})
        fmt = lambda v: f"{min(v):.2f}–{max(v):.2f}" if v else "—"   # noqa: E731
        lines.append(f"| {corpus} | {stage} | {provider} | "
                     f"{','.join(map(str, counts)) or '—'} | "
                     f"{fmt(within['unsteered'])} | {fmt(within['steered'])} | "
                     f"{fmt(across)} |")

    # ---- the labels themselves, for the human read ----------------------
    lines += ["", "## Every label produced", "",
              "Read these. The classifier sorts; it does not judge. Retention of "
              "on-screen terms on `ikea-mixed` is a hand-read and this is the "
              "list to do it from.", ""]
    for key, group in sorted(by_cell.items()):
        lines.append(f"**{' · '.join(key)}**")
        seen: dict[str, set] = defaultdict(set)
        for r in group:
            for label in labels_and_descriptions(r)[0]:
                seen[_norm(label)].add(label)
        for _, variants in sorted(seen.items()):
            label = sorted(variants)[0]
            lines.append(f"- `{classify(label)}` {label}"
                         + (f"  _(also: {', '.join(sorted(variants)[1:])})_"
                            if len(variants) > 1 else ""))
        lines.append("")

    # ---- failures --------------------------------------------------------
    failed = [r for r in records if r["failed"] or not r["succeeded"]]
    if failed:
        lines += ["## Stage failures", ""]
        for r in failed:
            lines.append(f"- {r['corpus']} {r['stage']} {r['provider']} "
                         f"{r['condition']} pass {r['pass']}: "
                         f"attempted={r['attempted']} succeeded={r['succeeded']} "
                         f"failed={len(r['failed'])}")
        lines.append("")

    target = OUT / "compare.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
