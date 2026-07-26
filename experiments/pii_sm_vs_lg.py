"""PII horror-harness: en_core_web_sm vs en_core_web_lg comparison.

Preserved from the 26 Jul 2026 Redact-PII exploration (see
docs/design-redact-pii.md §Evidence). Runs the planted-PII fixture
(tests/fixtures/pii_horror_*) through Presidio with each spaCy model and diffs
the catches. Mirrors tests/test_pii_audit.py's detection logic exactly.

Run from repo root:  .venv/bin/python experiments/pii_sm_vs_lg.py
Requires: presidio-analyzer + spacy + both en_core_web_sm and en_core_web_lg.

Headline result (26 Jul 2026): sm == lg on the 15 must-catch items (100% each);
lg's only edge is 6 hard-tail items — Fatimah bint Khalid, Kapoor, Bazza, a
spelled-out email, an employee ID — i.e. exactly the non-Western names an LLM
would catch trivially. This motivated the "roll our own PII" (regex + LLM-NER)
forward direction.
"""
import re
from pathlib import Path

import yaml
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from bristlenose.stages.s07_pii_removal import _DEFAULT_ENTITIES

FIX = Path("tests/fixtures")
TRANSCRIPT = FIX / "pii_horror_transcript.txt"
EXPECTED = FIX / "pii_horror_expected.yaml"


def parse_segments():
    segs = {}
    for line in TRANSCRIPT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"\[(\d+:\d+)\]\s+\[\w+\]\s+(.*)", line)
        if m:
            segs[m.group(1)] = m.group(2)
    return segs


def make_analyzer(model_name):
    cfg = {"nlp_engine_name": "spacy",
           "models": [{"lang_code": "en", "model_name": model_name}]}
    nlp = NlpEngineProvider(nlp_configuration=cfg).create_engine()
    return AnalyzerEngine(nlp_engine=nlp)


def finds(analyzer, text, target):
    for r in analyzer.analyze(text=text, language="en",
                              entities=_DEFAULT_ENTITIES, score_threshold=0.7):
        det = text[r.start:r.end]
        if target in det or det in target:
            return True
    return False


def main():
    segs = parse_segments()
    items = yaml.safe_load(EXPECTED.read_text(encoding="utf-8"))["items"]
    analyzers = {"sm": make_analyzer("en_core_web_sm"),
                 "lg": make_analyzer("en_core_web_lg")}

    rows = []
    for it in items:
        seg_text = segs.get(it.get("segment_time"))
        row = {"text": it["text"], "cat": it["category"], "should": it["should_catch"],
               "entity": it.get("entity_type") or "", "seg_found": seg_text is not None}
        for name, an in analyzers.items():
            row[name] = finds(an, seg_text, it["text"]) if seg_text is not None else None
        rows.append(row)

    mapped = [r for r in rows if r["should"] and r["seg_found"]]
    sm_c = sum(1 for r in mapped if r["sm"])
    lg_c = sum(1 for r in mapped if r["lg"])
    print(f"must-catch (mapped={len(mapped)}): sm {sm_c}/{len(mapped)}  lg {lg_c}/{len(mapped)}")

    shouldnt = [r for r in rows if not r["should"] and r["seg_found"]]
    print(f"hard tail (mapped={len(shouldnt)}): "
          f"sm {sum(1 for r in shouldnt if r['sm'])}  lg {sum(1 for r in shouldnt if r['lg'])}")
    print("\nhard-tail items LG catches but SM misses:")
    for r in shouldnt:
        if r["lg"] and not r["sm"]:
            print(f"  cat{r['cat']} {r['entity']:14} {r['text']!r}")


if __name__ == "__main__":
    main()
