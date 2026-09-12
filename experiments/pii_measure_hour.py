#!/usr/bin/env python3
"""Measure en_core_web_sm vs en_core_web_lg on the planted-PII hour corpus.

Runs Presidio exactly the way ``bristlenose/stages/s07_pii_removal.py`` does —
``NlpEngineProvider`` bound to a named model, ``analyzer.analyze(...)`` **per
segment** (production analyses ``seg.text``, never the whole document), the
production entity list, and ``score_threshold`` from config's default of 0.7.

Three numbers per model:

  RECALL     over planted synthetic PII, by category.
  PRECISION  over planted near-miss probes — product names, technical terms
             that are also surnames, capitalised sentence starts, month names.
             These are ground-truth negatives, so a hit is an unambiguous
             false positive.
  BACKGROUND every span flagged in the untouched FOSSDA base text. These are
             *not* scored as errors: FOSSDA interviews name real public
             figures, so a PERSON hit there is correct NER. They are bucketed
             and listed so over-firing is visible either way.

A second "wide" pass adds LOCATION / ORGANIZATION / DATE_TIME, which production
deliberately does **not** request (see ``_DEFAULT_ENTITIES`` and the LOCATION
comment in s07). Reported separately and clearly marked as out-of-scope today.

Usage:
    .venv/bin/python experiments/pii_measure_hour.py
    .venv/bin/python experiments/pii_measure_hour.py --corpus trial-runs/pii-hour-corpus
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO / "trial-runs" / "pii-hour-corpus"

MODELS = ["en_core_web_sm", "en_core_web_lg"]

# Mirror of bristlenose/stages/s07_pii_removal.py:_DEFAULT_ENTITIES
PROD_ENTITIES = [
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "US_SSN",
    "UK_NHS",
    "IBAN_CODE",
    "IP_ADDRESS",
]
WIDE_EXTRA = ["LOCATION", "ORGANIZATION", "DATE_TIME"]
THRESHOLD = 0.7

# ---------------------------------------------------------------------------
# Background classification for hits in the untouched FOSSDA base text.
# ---------------------------------------------------------------------------

# Real people named in these public interviews. A PERSON hit here is correct
# NER — and simultaneously a redaction of research-relevant content, which is
# the trade-off decision D1 in docs/design-redact-pii.md is about.
REAL_PEOPLE = {
    "richard stallman", "stallman", "linus torvalds", "linus", "torvalds",
    "tim berners-lee", "berners-lee", "eric allman", "cat allman", "allman",
    "bruce perens", "perens", "deb goodkin", "goodkin", "dominic mazzoni",
    "mazzoni", "abhishek tiwari", "tiwari", "daniel ruggeri", "ruggeri",
    "myrle krantz", "krantz", "heather meeker", "meeker", "elisabetta mori",
    "mori", "bill gates", "steve jobs", "larry wall", "guido", "brian",
    "ada lovelace", "eben moglen", "moglen", "lawrence lessig", "lessig",
    "kirk mckusick", "mckusick", "keith packard", "packard", "alan cox",
    "andrew tanenbaum", "tanenbaum", "brian behlendorf", "behlendorf",
    "jim jagielski", "jagielski", "roy fielding", "fielding", "eric raymond",
    "raymond", "michael tiemann", "tiemann", "tim o'reilly", "o'reilly",
    "bob young", "mark shuttleworth", "shuttleworth", "ian murdock",
    "murdock", "theo de raadt", "de raadt", "poul-henning kamp",
    "marshall kirk mckusick", "danese cooper", "karen sandler", "bradley kuhn",
    "simon phipps", "phipps", "mitchell baker", "jono bacon", "greg",
    "chris", "sarah", "john", "dave", "steve", "mike", "paul", "peter",
}

# Software, projects, companies, standards, conferences — anything a
# researcher would want left in the transcript.
TECH_TERMS = {
    "linux", "unix", "bsd", "gnu", "sendmail", "apache", "debian", "ubuntu",
    "fedora", "gentoo", "red hat", "suse", "perl", "python", "ruby", "java",
    "javascript", "rust", "kotlin", "swift", "julia", "ada", "vala", "bash",
    "emacs", "vim", "git", "mercurial", "subversion", "cvs", "jenkins",
    "bugzilla", "nagios", "grafana", "docker", "kubernetes", "mozilla",
    "firefox", "netscape", "openbsd", "freebsd", "netbsd", "solaris", "vax",
    "decus", "dec", "macintosh", "windows", "microsoft", "google", "ibm",
    "oracle", "sun", "at&t", "berkeley", "audacity", "sourceforge", "github",
    "gitlab", "fosdem", "oscon", "linuxcon", "usenix", "ietf", "w3c", "osi",
    "fsf", "gpl", "lgpl", "agpl", "mit", "bsd licence", "apache licence",
    "creative commons", "wikipedia", "wordpress", "drupal", "mysql",
    "postgresql", "sqlite", "nginx", "openssl", "openssh", "samba", "kde",
    "gnome", "x11", "wayland", "systemd", "cpan", "npm", "pypi", "maven",
    "the linux foundation", "the apache software foundation", "sendmail inc",
    "o'reilly", "slashdot", "freshmeat", "cd-rom", "isp", "dot-com",
    "world wide web", "internet", "sendmail.org", "sendmail.com",
}


def classify_background(surface: str) -> str:
    s = surface.strip().strip(".,;:'\"").lower()
    if s in REAL_PEOPLE:
        return "real-person-in-base-text"
    if s in TECH_TERMS:
        return "tech/product term"
    # Multi-token: classify on any constituent being a known real person.
    parts = s.split()
    if len(parts) >= 2 and any(p in REAL_PEOPLE for p in parts):
        return "real-person-in-base-text"
    if any(p in TECH_TERMS for p in parts):
        return "tech/product term"
    return "unclassified"


# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Hit:
    seg_id: str
    start: int  # global
    end: int
    entity: str
    score: float
    surface: str


def load(corpus: Path) -> tuple[list[dict], list[dict]]:
    segs = json.loads((corpus / "segments.json").read_text())
    truth = json.loads((corpus / "ground_truth.json").read_text())
    return segs, truth


def build_analyzer(model: str):
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": model}],
        }
    )
    return AnalyzerEngine(nlp_engine=provider.create_engine())


def run_pass(analyzer, segs: list[dict], entities: list[str]) -> list[Hit]:
    hits: list[Hit] = []
    for seg in segs:
        text = seg["text"]
        for r in analyzer.analyze(
            text=text, language="en", entities=entities, score_threshold=THRESHOLD
        ):
            hits.append(
                Hit(
                    seg_id=seg["seg_id"],
                    start=seg["offset"] + r.start,
                    end=seg["offset"] + r.end,
                    entity=r.entity_type,
                    score=round(r.score, 3),
                    surface=text[r.start : r.end],
                )
            )
    return hits


def run_pass_at(analyzer, segs: list[dict], entities: list[str], thr: float) -> list[Hit]:
    hits: list[Hit] = []
    for seg in segs:
        text = seg["text"]
        for r in analyzer.analyze(
            text=text, language="en", entities=entities, score_threshold=thr
        ):
            hits.append(Hit(seg["seg_id"], seg["offset"] + r.start, seg["offset"] + r.end,
                            r.entity_type, round(r.score, 3), text[r.start : r.end]))
    return hits


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def score(truth: list[dict], hits: list[Hit]) -> dict:
    """Overlap-based scoring.

    Boundary agreement is not the question — Presidio will flag ``University
    of Ashcombe`` where the plant says ``the University of Ashcombe``, and that
    is a catch, not a miss. Any character overlap counts.
    """
    caught: dict[int, list[Hit]] = defaultdict(list)
    matched_hits: set[int] = set()
    for gi, g in enumerate(truth):
        for hi, h in enumerate(hits):
            if overlaps(g["start"], g["end"], h.start, h.end):
                caught[gi].append(h)
                matched_hits.add(hi)
    background = [h for hi, h in enumerate(hits) if hi not in matched_hits]
    return {"caught": caught, "background": background}


def fmt_table(rows: list[tuple], headers: tuple) -> str:
    cols = len(headers)
    widths = [len(str(headers[i])) for i in range(cols)]
    for r in rows:
        for i in range(cols):
            widths[i] = max(widths[i], len(str(r[i])))
    out = ["  ".join(str(headers[i]).ljust(widths[i]) for i in range(cols)).rstrip()]
    out.append("  ".join("-" * widths[i] for i in range(cols)))
    for r in rows:
        out.append("  ".join(str(r[i]).ljust(widths[i]) for i in range(cols)).rstrip())
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--wide", action="store_true",
                    help="also run the out-of-scope LOCATION/ORG/DATE_TIME pass")
    args = ap.parse_args()

    segs, truth = load(args.corpus)
    positives = [t for t in truth if t["kind"] == "positive"]
    negatives = [t for t in truth if t["kind"] == "negative"]
    words = sum(len(s["text"].split()) for s in segs)

    print("=" * 78)
    print("PLANTED-PII HOUR CORPUS — en_core_web_sm vs en_core_web_lg")
    print("=" * 78)
    print(f"corpus            {len(segs)} segments, {words:,} words "
          f"(FOSSDA base, synthetic plants)")
    print(f"planted positives {len(positives)}")
    print(f"negative probes   {len(negatives)}")
    print(f"entities          {', '.join(PROD_ENTITIES)}")
    print(f"threshold         {THRESHOLD}  (analysed per segment, as production does)")
    print()

    results: dict[str, dict] = {}
    for model in MODELS:
        t0 = time.perf_counter()
        analyzer = build_analyzer(model)
        load_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        hits = run_pass(analyzer, segs, PROD_ENTITIES)
        run_s = time.perf_counter() - t1
        res = score(truth, hits)
        res["hits"] = hits
        # Same entity set, no threshold — for the sub-threshold diagnostic.
        low_hits = [h for h in run_pass_at(analyzer, segs, PROD_ENTITIES, 0.0)]
        res["low"] = score(truth, low_hits)
        res["low"]["hits"] = low_hits
        res["load_s"] = load_s
        res["run_s"] = run_s
        if args.wide:
            supported = set(analyzer.get_supported_entities())
            wide_ents = PROD_ENTITIES + [e for e in WIDE_EXTRA if e in supported]
            wide_hits = run_pass(analyzer, segs, wide_ents)
            res["wide"] = score(truth, wide_hits)
            res["wide"]["hits"] = wide_hits
        results[model] = res
        print(f"[{model}] loaded in {load_s:.1f}s, analysed {len(segs)} segments "
              f"in {run_s:.1f}s, {len(hits)} spans flagged")
    print()

    # ---- RECALL --------------------------------------------------------
    cats = sorted({t["category"] for t in positives})
    rows = []
    for cat in cats:
        items = [(i, t) for i, t in enumerate(truth)
                 if t["kind"] == "positive" and t["category"] == cat]
        n = len(items)
        cells = []
        for model in MODELS:
            hitlist = [results[model]["caught"].get(i) for i, _ in items]
            got = sum(1 for h in hitlist if h)
            ents = sorted({h[0].entity for h in hitlist if h})
            label = f"{got}/{n}"
            # Flag when the redaction happened under a surprising entity type —
            # a LOCATION plant "caught" because PERSON fired on it is a catch
            # for redaction purposes but says nothing good about the model.
            expected = {
                "PERSON": "PERSON", "EMAIL": "EMAIL_ADDRESS", "PHONE": "PHONE_NUMBER",
            }.get(cat.split("/")[0])
            if ents and (expected is None or ents != [expected]):
                label += f" [{'/'.join(ents)}]"
            cells.append(label)
        rows.append((cat, n, *cells))
    total = len(positives)
    tot_cells = []
    for model in MODELS:
        got = sum(1 for i, t in enumerate(truth)
                  if t["kind"] == "positive" and results[model]["caught"].get(i))
        tot_cells.append(f"{got}/{total}  ({got / total:.0%})")
    print("RECALL — planted synthetic PII, production entity set")
    print("-" * 78)
    print(fmt_table(rows, ("category", "n", "sm", "lg")))
    print()
    print(f"  TOTAL   sm {tot_cells[0]}    lg {tot_cells[1]}")
    print()

    # Which categories are structurally out of scope (no matching entity)?
    oos = [c for c in cats if c.split("/")[0] in {"LOCATION", "ORG"}
           or c in {"ID/employee", "ID/postcode", "ID/dob"}]
    print("  Note: these categories have NO recognizer in the production entity set,")
    print("  so a 0 is a scope decision, not a model failure:")
    print("    " + ", ".join(oos))
    print()

    # ---- THE PERSON AXIS -------------------------------------------------
    # Everything in the production entity set except PERSON is a regex or a
    # checksum recognizer, so the spaCy model cannot affect it. If that holds
    # empirically, the whole 425 MB question reduces to PERSON.
    print("THE PERSON AXIS — the only place the model can matter")
    print("-" * 78)
    nonperson = {
        m: sorted((h.start, h.end, h.entity) for h in results[m]["hits"]
                  if h.entity != "PERSON")
        for m in MODELS
    }
    same = nonperson[MODELS[0]] == nonperson[MODELS[1]]
    print(f"  non-PERSON spans identical across models: {same}  "
          f"({len(nonperson[MODELS[0]])} spans each)")
    if not same:
        for m in MODELS:
            extra = set(nonperson[m]) - set(nonperson[[x for x in MODELS if x != m][0]])
            print(f"    only {m}: {sorted(extra)}")
    person_pos = [i for i, t in enumerate(truth)
                  if t["kind"] == "positive" and t["category"].startswith("PERSON/")]
    print()
    rows = []
    for m in MODELS:
        got = sum(1 for i in person_pos if results[m]["caught"].get(i))
        flagged = [h for h in results[m]["hits"] if h.entity == "PERSON"]
        tp = sum(1 for i in person_pos if results[m]["caught"].get(i))
        fp_probe = sum(1 for i, t in enumerate(truth)
                       if t["kind"] == "negative" and results[m]["caught"].get(i))
        bg = len([h for h in results[m]["background"] if h.entity == "PERSON"])
        rows.append((
            m,
            f"{got}/{len(person_pos)} ({got / len(person_pos):.0%})",
            f"{fp_probe}/{len(negatives)} ({fp_probe / len(negatives):.0%})",
            len(flagged), tp, fp_probe, bg,
        ))
    print(fmt_table(rows, ("model", "PERSON recall", "probe FP rate",
                           "PERSON spans", "planted", "probe FP", "base text")))
    print()
    print("  'base text' = PERSON spans in the untouched FOSSDA prose: mostly real")
    print("  public figures (correct NER), which redaction removes from the research")
    print("  record either way. Not counted as error; counted here for volume.")
    print()

    # ---- SUB-THRESHOLD --------------------------------------------------
    # Separates "the model never saw it" from "the model saw it and the 0.7
    # threshold threw it away". Only the first is a model-capability question.
    print("SUB-THRESHOLD — planted positives DETECTED but scored below 0.7")
    print("-" * 78)
    for model in MODELS:
        low = results[model]["low"]
        rows = []
        for i, t in enumerate(truth):
            if t["kind"] != "positive" or results[model]["caught"].get(i):
                continue
            near = low["caught"].get(i)
            if near:
                best = max(near, key=lambda h: h.score)
                rows.append((t["category"], t["surface"][:44], best.entity, best.score))
        print(f"  {model}: {len(rows)} of the misses were seen but under-scored")
        if rows:
            print("    " + fmt_table(sorted(rows),
                                     ("category", "surface", "entity", "score")
                                     ).replace("\n", "\n    "))
        print()

    # ---- PRECISION -----------------------------------------------------
    print("PRECISION — planted near-miss probes that must NOT be redacted")
    print("-" * 78)
    ncats = sorted({t["category"] for t in negatives})
    rows = []
    for cat in ncats:
        items = [(i, t) for i, t in enumerate(truth)
                 if t["kind"] == "negative" and t["category"] == cat]
        n = len(items)
        cells = []
        for model in MODELS:
            bad = sum(1 for i, _ in items if results[model]["caught"].get(i))
            cells.append(f"{bad}/{n}")
        rows.append((cat, n, *cells))
    print(fmt_table(rows, ("probe category", "n", "sm FP", "lg FP")))
    print()
    for model in MODELS:
        fired = [(t["surface"], results[model]["caught"][i][0].entity,
                  results[model]["caught"][i][0].score)
                 for i, t in enumerate(truth)
                 if t["kind"] == "negative" and results[model]["caught"].get(i)]
        n = len(negatives)
        print(f"  {model}: {len(fired)}/{n} probes falsely redacted "
              f"({len(fired) / n:.0%})")
        for surf, ent, sc in fired:
            print(f"      {surf!r} -> {ent} ({sc})")
    print()

    # ---- BACKGROUND ----------------------------------------------------
    print("BACKGROUND — spans flagged in the untouched FOSSDA base text")
    print("-" * 78)
    print("  Not scored as errors: these interviews name real public figures, so a")
    print("  PERSON hit is correct NER. It is still a redaction of research content.")
    print()
    for model in MODELS:
        bg = results[model]["background"]
        buckets: Counter[str] = Counter(classify_background(h.surface) for h in bg)
        uniq = len({h.surface for h in bg})
        print(f"  {model}: {len(bg)} spans ({uniq} distinct surfaces)")
        for b, c in buckets.most_common():
            print(f"      {b:28s} {c}")
        unc = Counter(h.surface for h in bg if classify_background(h.surface) == "unclassified")
        if unc:
            print(f"      unclassified surfaces ({len(unc)} distinct), most common:")
            for surf, c in unc.most_common(20):
                print(f"        {c:3d}x  {surf!r}")
        print()

    # ---- DISAGREEMENT --------------------------------------------------
    print("DISAGREEMENT SET")
    print("-" * 78)
    only = {}
    for a, b in (("en_core_web_sm", "en_core_web_lg"), ("en_core_web_lg", "en_core_web_sm")):
        b_spans = [(h.start, h.end) for h in results[b]["hits"]]
        uniq = [h for h in results[a]["hits"]
                if not any(overlaps(h.start, h.end, s, e) for s, e in b_spans)]
        only[a] = uniq
    for model, uniq in only.items():
        other = [m for m in MODELS if m != model][0]
        print(f"  Flagged by {model} but NOT {other}: {len(uniq)}")
        by_class: dict[str, list[Hit]] = defaultdict(list)
        for h in uniq:
            gt = next((t for t in truth
                       if overlaps(t["start"], t["end"], h.start, h.end)), None)
            key = (f"{gt['kind']}:{gt['category']}" if gt else
                   f"background:{classify_background(h.surface)}")
            by_class[key].append(h)
        for key in sorted(by_class):
            surfaces = Counter(h.surface for h in by_class[key])
            shown = ", ".join(f"{s!r}" + (f" x{c}" if c > 1 else "")
                              for s, c in surfaces.most_common(12))
            print(f"      {key:44s} {len(by_class[key]):3d}  {shown}")
        print()

    # ---- UNIQUE WINS ---------------------------------------------------
    print("UNIQUE CATEGORY WINS (planted positives only)")
    print("-" * 78)
    rows = []
    for cat in cats:
        items = [i for i, t in enumerate(truth)
                 if t["kind"] == "positive" and t["category"] == cat]
        sm_only = [i for i in items
                   if results["en_core_web_sm"]["caught"].get(i)
                   and not results["en_core_web_lg"]["caught"].get(i)]
        lg_only = [i for i in items
                   if results["en_core_web_lg"]["caught"].get(i)
                   and not results["en_core_web_sm"]["caught"].get(i)]
        if sm_only or lg_only:
            rows.append((
                cat,
                ", ".join(truth[i]["surface"] for i in sm_only) or "—",
                ", ".join(truth[i]["surface"] for i in lg_only) or "—",
            ))
    if rows:
        print(fmt_table(rows, ("category", "sm only", "lg only")))
    else:
        print("  none — the two models agree on every planted positive")
    print()

    # ---- WIDE PASS -----------------------------------------------------
    if args.wide:
        print("APPENDIX — wide pass (+LOCATION, +ORGANIZATION, +DATE_TIME)")
        print("-" * 78)
        print("  Production does NOT request these. LOCATION is excluded by an explicit")
        print("  decision in s07 (it destroys research data); ORGANIZATION and DATE_TIME")
        print("  are not in _DEFAULT_ENTITIES at all. Shown only to price the ceiling.")
        print()
        wcats = [c for c in cats if c.split("/")[0] in {"LOCATION", "ORG"}
                 or c == "ID/dob"]
        rows = []
        for cat in wcats:
            items = [i for i, t in enumerate(truth)
                     if t["kind"] == "positive" and t["category"] == cat]
            cells = [f"{sum(1 for i in items if results[m]['wide']['caught'].get(i))}"
                     f"/{len(items)}" for m in MODELS]
            rows.append((cat, len(items), *cells))
        print(fmt_table(rows, ("category", "n", "sm", "lg")))
        print()
        for model in MODELS:
            bad = [(t["surface"], results[model]["wide"]["caught"][i][0].entity)
                   for i, t in enumerate(truth)
                   if t["kind"] == "negative" and results[model]["wide"]["caught"].get(i)]
            print(f"  {model}: {len(bad)}/{len(negatives)} negative probes flagged "
                  f"in the wide pass, {len(results[model]['wide']['hits'])} spans total")
        print()

    # persist raw output for auditing
    dump = {
        model: {
            "hits": [h.__dict__ for h in results[model]["hits"]],
            "load_s": results[model]["load_s"],
            "run_s": results[model]["run_s"],
        }
        for model in MODELS
    }
    (args.corpus / "measurement.json").write_text(json.dumps(dump, indent=1))
    print(f"raw spans written to {args.corpus / 'measurement.json'}")


if __name__ == "__main__":
    main()
