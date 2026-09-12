#!/usr/bin/env python3
"""End-to-end check of the SHIPPED redaction path on the planted-PII corpus.

Deliberately different from `pii_measure_hour.py`, which drives Presidio's
analyzer directly to compare models. This calls **`remove_pii()` itself** — the
function `Pipeline.run` calls — so it exercises `resolve_spacy_model()`, the
engine binding, the entity map, the score threshold, the `words` clearing and
the `PiiCleanTranscript` construction as one piece. A green analyzer says
nothing about whether the stage that wraps it leaks.

Scoring frame, and it matters: the product deliberately does NOT redact
LOCATION (Presidio fires on any named place and destroys research data — see
`_ENTITY_MAP`'s comment) and does not map ORG at all. Counting those planted
items as misses would manufacture a failure out of a design decision, so they
are reported separately as out-of-scope-by-design.

**Read the false-positive number for what it is.** Every one of the corpus's
32 negatives is a *word* — product names, month names, sentence starts — and
none contains a digit. So this harness cannot show a false positive on any
number-shaped entity (phone, NHS, card, IBAN, IP, the US identifiers), at any
threshold. On 12 Sep 2026 an unchanged 9/32 was cited as proof that lowering
those entities' bar was safe; the fixture was structurally incapable of
disagreeing. A numeric-negative class (prices, dates, times, order numbers,
version strings, postcodes, SKUs, extensions) belongs in `pii_corpus_hour.py`
before that column means anything for structured entities.

Needs `trial-runs/pii-hour-corpus/` (gitignored; build it with
`pii_corpus_hour.py`). Planted PII is entirely synthetic; the FOSSDA base text
names real public figures, so background hits are counted, never printed.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bristlenose.config import BristlenoseSettings  # noqa: E402
from bristlenose.models import FullTranscript, TranscriptSegment, Word  # noqa: E402
from bristlenose.stages.s07_pii_removal import remove_pii, resolve_spacy_model  # noqa: E402

CORPUS = ROOT / "trial-runs" / "pii-hour-corpus"

# Categories the shipped entity map actually targets.
IN_SCOPE = ("PERSON", "EMAIL", "PHONE", "ID/nhs", "ID/dob")
# Planted, but deliberately not redacted by the product.
BY_DESIGN_OUT = ("LOCATION", "ORG", "ID/postcode", "ID/employee")


def _targeted(category: str) -> bool:
    return any(category.startswith(c) for c in IN_SCOPE)


def _by_design_out(category: str) -> bool:
    return any(category.startswith(c) for c in BY_DESIGN_OUT)


def main() -> int:
    segs = json.loads((CORPUS / "segments.json").read_text())
    truth = json.loads((CORPUS / "ground_truth.json").read_text())

    # One transcript, words populated on every segment. The words are the point:
    # `model_copy()` is shallow, so a redacted segment used to keep the original
    # unredacted word list — which then reached the anonymised HTML export.
    segments = []
    for i, s in enumerate(segs):
        words = [
            Word(text=w, start_time=float(i), end_time=float(i) + 0.5)
            for w in s["text"].split()
        ]
        segments.append(
            TranscriptSegment(
                start_time=float(i * 30),
                end_time=float(i * 30 + 29),
                text=s["text"],
                speaker_label=s.get("speaker") or "Speaker A",
                source="whisper",
                segment_index=i,
                words=words,
            )
        )

    transcript = FullTranscript(
        session_id="s1",
        participant_id="p1",
        source_file="corpus.txt",
        session_date=datetime.now(timezone.utc),
        duration_seconds=float(len(segs) * 30),
        segments=segments,
    )

    settings = BristlenoseSettings(project_name="pii-e2e", pii_enabled=True)

    print(f"model resolved to : {resolve_spacy_model()}")
    print(f"score threshold   : {settings.pii_score_threshold}")
    print(f"segments          : {len(segments)}")
    t0 = time.perf_counter()
    clean, redactions = remove_pii([transcript], settings)
    elapsed = time.perf_counter() - t0
    print(f"remove_pii        : {elapsed:.1f}s, {len(redactions)} redaction(s)\n")

    out = clean[0]

    # --- the leak that shipped: words must be gone -------------------------
    leaked = [s.segment_index for s in out.segments if s.words]
    print("WORDS CLEARED     :", "yes" if not leaked else f"NO — {len(leaked)} segments kept words")

    # --- recall on planted positives, scored per segment -------------------
    clean_by_idx = {s.segment_index: s.text for s in out.segments}
    seg_index_by_id = {s["seg_id"]: i for i, s in enumerate(segs)}

    hit: Counter = Counter()
    miss: defaultdict = defaultdict(list)
    fp: list = []
    out_of_scope: Counter = Counter()

    for g in truth:
        idx = seg_index_by_id.get(g["seg_id"])
        if idx is None:
            continue
        after = clean_by_idx.get(idx, "")
        gone = g["surface"] not in after
        cat = g["category"]

        if g["kind"] == "positive":
            if _by_design_out(cat):
                out_of_scope[("redacted" if gone else "kept")] += 1
                continue
            if not _targeted(cat):
                continue
            family = cat.split("/")[0]
            if gone:
                hit[family] += 1
            else:
                miss[family].append(cat.split("/")[1])
        else:
            if gone:  # a ground-truth negative that got redacted
                fp.append(cat)

    print("\nRECALL on targeted planted PII")
    total_h = total_m = 0
    for family in ("PERSON", "EMAIL", "PHONE", "ID"):
        h = hit[family]
        m = len(miss[family])
        total_h += h
        total_m += m
        if h + m:
            print(f"  {family:8} {h:3}/{h + m:<3}" + (f"   missed: {', '.join(miss[family])}" if m else ""))
    print(f"  {'TOTAL':8} {total_h:3}/{total_h + total_m}")

    print("\nFALSE POSITIVES on planted near-miss probes")
    if fp:
        for cat, n in sorted(Counter(fp).items()):
            print(f"  {cat:42} {n}")
        print(f"  {'TOTAL':42} {len(fp)} of 32 negatives redacted")
    else:
        print("  none of the 32 negatives were redacted")

    print("\nOUT OF SCOPE BY DESIGN (planted, product does not target)")
    print(f"  kept as written : {out_of_scope['kept']}")
    print(f"  redacted anyway : {out_of_scope['redacted']}")

    # Background = spans in the untouched FOSSDA text. Real public figures, so
    # a PERSON hit there is correct NER. Counted, never printed.
    print(f"\nredactions recorded by the stage: {len(redactions)}")
    return 0 if not leaked else 1


if __name__ == "__main__":
    raise SystemExit(main())
