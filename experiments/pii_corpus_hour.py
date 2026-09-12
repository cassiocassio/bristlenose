#!/usr/bin/env python3
"""Build an hour-length, realistically-planted PII test corpus.

Base text is FOSSDA (public open-source-history interviews, public figures in
public interviews). Every planted item is **entirely synthetic** — invented
names, Ofcom/NANP reserved drama phone ranges, non-existent domains. No real
person's real details are inserted anywhere.

Output (deterministic from ``--seed``) goes to ``trial-runs/pii-hour-corpus/``:

  segments.json   the corpus as a list of segments (production analyses
                  *per segment*, so the corpus keeps that shape) plus, for
                  each segment, its global character offset in ``corpus.txt``
  ground_truth.json  every planted span: category, kind, surface, global
                  offsets, and the segment it lives in
  corpus.txt      the flat text, for eyeballing

Ground truth has three classes:

  positive   planted synthetic PII. Recall is measured against these.
  negative   planted near-miss probes that must NOT be redacted (product
             names, technical terms that look like proper nouns, capitalised
             sentence starts, month names). Precision is measured against
             these.
  (unmarked) the FOSSDA base text itself. It contains *real* names of public
             figures, so a hit there is not automatically a false positive —
             the measurement script classifies those separately rather than
             scoring them.

Usage:
    .venv/bin/python experiments/pii_corpus_hour.py
    .venv/bin/python experiments/pii_corpus_hour.py --words 9000 --seed 7
"""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO / "trial-runs" / "fossda-opensource" / "bristlenose-output" / "transcripts-raw"
DEFAULT_OUT = REPO / "trial-runs" / "pii-hour-corpus"

# Sessions in the order they are drawn from. Deliberately more than needed so
# the word target can be met without touching the tail.
SESSION_ORDER = ["s2", "s4", "s9", "s6", "s1", "s8", "s10", "s7", "s5", "s3"]

_SEGMENT_RE = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s+\[(\w+)\]\s+(?:\([^)]*\)\s*)?(.*)$")


# ---------------------------------------------------------------------------
# NHS numbers — modulus-11 checksum, so the digits must be generated, not
# guessed. Presidio's UK_NHS recognizer validates the check digit.
# ---------------------------------------------------------------------------

def nhs_check_digit(first_nine: str) -> int:
    total = sum(int(d) * w for d, w in zip(first_nine, range(10, 1, -1)))
    remainder = total % 11
    check = 11 - remainder
    if check == 11:
        return 0
    if check == 10:
        raise ValueError(f"{first_nine} yields an invalid NHS check digit")
    return check


def nhs_number(first_nine: str) -> str:
    """Return a checksum-valid NHS number in the conventional 3-3-4 grouping."""
    c = nhs_check_digit(first_nine)
    return f"{first_nine[0:3]} {first_nine[3:6]} {first_nine[6:9]}{c}"


# ---------------------------------------------------------------------------
# The planted material
# ---------------------------------------------------------------------------

@dataclass
class Span:
    """One planted surface with its category and polarity."""

    category: str
    kind: str  # "positive" | "negative"
    surface: str
    note: str = ""


@dataclass
class Plant:
    """A conversational sentence inserted mid-utterance, carrying spans."""

    sentence: str
    spans: list[Span] = field(default_factory=list)


def _p(sentence: str, *spans: Span) -> Plant:
    for s in spans:
        if s.surface not in sentence:
            raise ValueError(f"surface {s.surface!r} not found in {sentence!r}")
        if sentence.count(s.surface) != 1:
            raise ValueError(f"surface {s.surface!r} is ambiguous in {sentence!r}")
    return Plant(sentence, list(spans))


def person(surface: str, subtype: str) -> Span:
    return Span(f"PERSON/{subtype}", "positive", surface)


def neg(surface: str, subtype: str, note: str = "") -> Span:
    return Span(f"NEGATIVE/{subtype}", "negative", surface, note)


NHS_A = nhs_number("943476585")
NHS_B = nhs_number("610315872")
NHS_C = nhs_number("401023213")


def build_plants() -> list[Plant]:
    """Every planted sentence.

    Placement style is deliberately oblique — no "my name is X" introductions.
    That clean-introduction shape is the flaw in the existing hand-planted
    fixture, and it is what makes the existing sm==lg result untrustworthy.
    """
    plants: list[Plant] = []

    # ---- PERSON: Anglo two-token -----------------------------------------
    plants += [
        _p(
            "and then Marguerite Hollingsworth took over the release engineering "
            "side, so that was that.",
            person("Marguerite Hollingsworth", "anglo_two_token"),
        ),
        _p(
            "we shipped it anyway, mostly because Trevor Bracewell wouldn't stop "
            "asking about it in standup.",
            person("Trevor Bracewell", "anglo_two_token"),
        ),
        _p(
            "I mean, honestly, half of that patch was Rosalind Pettifer's work and "
            "she never got the credit.",
            person("Rosalind Pettifer", "anglo_two_token"),
        ),
    ]

    # ---- PERSON: single bare first name -----------------------------------
    plants += [
        _p(
            "I still owe Delphine a proper answer about the licence question.",
            person("Delphine", "bare_first_name"),
        ),
        _p(
            "so Kwame reckoned we should just fork it and be done, which, fair enough.",
            person("Kwame", "bare_first_name"),
        ),
        _p(
            "and Ingrid was in the room for that one, she'll remember it better than me.",
            person("Ingrid", "bare_first_name"),
        ),
    ]

    # ---- PERSON: Arabic ---------------------------------------------------
    plants += [
        _p(
            "the packaging work was almost entirely Yusra Al-Mansouri, working "
            "evenings, unpaid.",
            person("Yusra Al-Mansouri", "arabic"),
        ),
        _p(
            "we only got the Arabic rendering right because Tariq Benhaddou "
            "rewrote the shaping layer.",
            person("Tariq Benhaddou", "arabic"),
        ),
        _p(
            "I remember Nadia Boukhari saying the whole governance model was upside down.",
            person("Nadia Boukhari", "arabic"),
        ),
    ]

    # ---- PERSON: South Asian ---------------------------------------------
    plants += [
        _p(
            "Prathiba Venkataraman ran the Pune office and she was the one who "
            "actually understood the build.",
            person("Prathiba Venkataraman", "south_asian"),
        ),
        _p(
            "so we handed the whole thing to Arjun Chaturvedi and he had it working by Friday.",
            person("Arjun Chaturvedi", "south_asian"),
        ),
        _p(
            "and Meenakshi Rajagopalan kept the mailing list civil for about six years.",
            person("Meenakshi Rajagopalan", "south_asian"),
        ),
    ]

    # ---- PERSON: East Asian ----------------------------------------------
    plants += [
        _p(
            "most of the CJK font work came through Haruki Nakashima, who nobody outside "
            "the project has heard of.",
            person("Haruki Nakashima", "east_asian"),
        ),
        _p(
            "we'd never have got the Taiwanese mirror without Wei-Chen Lau pushing for it.",
            person("Wei-Chen Lau", "east_asian"),
        ),
        _p(
            "and Ji-woo Seong ended up maintaining it for a decade more or less alone.",
            person("Ji-woo Seong", "east_asian"),
        ),
    ]

    # ---- PERSON: Slavic ---------------------------------------------------
    plants += [
        _p(
            "Zofia Wisniewska was doing the security review in her own time, which "
            "is mad when you think about it.",
            person("Zofia Wisniewska", "slavic"),
        ),
        _p(
            "there's a long thread where Bogdan Petrescu explains exactly why that "
            "was a terrible idea.",
            person("Bogdan Petrescu", "slavic"),
        ),
        _p(
            "and then Katarzyna Nowakowa took the maintainer hat and nothing broke for years.",
            person("Katarzyna Nowakowa", "slavic"),
        ),
    ]

    # ---- PERSON: nickname / diminutive ------------------------------------
    plants += [
        _p(
            "we all just called him Bazza, I genuinely could not tell you his legal name.",
            person("Bazza", "nickname"),
        ),
        _p(
            "Debs handled the conference logistics and did it better than any of us would have.",
            person("Debs", "nickname"),
        ),
        _p(
            "so Wozza turns up with a suitcase full of CD-ROMs, as you do.",
            person("Wozza", "nickname"),
        ),
    ]

    # ---- PERSON: titled ---------------------------------------------------
    plants += [
        _p(
            "the ethics side was signed off by Dr Okonjo before we touched any of the data.",
            person("Dr Okonjo", "titled"),
        ),
        _p(
            "Professor Halvorsen wrote the foreword and then quietly funded two of the interns.",
            person("Professor Halvorsen", "titled"),
        ),
        _p(
            "we ran it past Sister Mulcahy on the ward first, which turned out to matter.",
            person("Sister Mulcahy", "titled"),
        ),
    ]

    # ---- PERSON: surname only ---------------------------------------------
    plants += [
        _p(
            "you'd have to ask Fairweather about that, he ran the build farm.",
            person("Fairweather", "surname_only"),
        ),
        _p(
            "Kowalczyk disagreed with every one of us and, looking back, was right.",
            person("Kowalczyk", "surname_only"),
        ),
        _p(
            "that was the year Threlfall left and the whole QA process went with him.",
            person("Threlfall", "surname_only"),
        ),
    ]

    # ---- PERSON: hyphenated -----------------------------------------------
    plants += [
        _p(
            "Anne-Sophie Beauchamp-Laurent chaired the working group for three terms.",
            person("Anne-Sophie Beauchamp-Laurent", "hyphenated"),
        ),
        _p(
            "and Mary-Kate Fitzsimmons-Hardy did the accessibility audit for nothing.",
            person("Mary-Kate Fitzsimmons-Hardy", "hyphenated"),
        ),
        _p(
            "the original proposal is still filed under Jean-Baptiste Rousseau-Marchand somewhere.",
            person("Jean-Baptiste Rousseau-Marchand", "hyphenated"),
        ),
    ]

    # ---- PERSON: apostrophe surname ---------------------------------------
    plants += [
        _p(
            "Niamh O'Halloran ended up doing all the translation coordination.",
            person("Niamh O'Halloran", "apostrophe"),
        ),
        _p(
            "we lost the archive when Declan O'Shaughnessy's server went offline.",
            person("Declan O'Shaughnessy", "apostrophe"),
        ),
        _p(
            "and Bridget D'Angelo kept minutes for every single meeting, bless her.",
            person("Bridget D'Angelo", "apostrophe"),
        ),
    ]

    # ---- EMAIL: normal ----------------------------------------------------
    plants += [
        _p(
            "anything on that goes to r.tindall@northgate-clinic.example.co.uk and "
            "she'll route it.",
            Span("EMAIL/normal", "positive", "r.tindall@northgate-clinic.example.co.uk"),
        ),
        _p(
            "the old list address was foss-archive@calderfield-logistics.example.com "
            "and it bounced for years.",
            Span("EMAIL/normal", "positive", "foss-archive@calderfield-logistics.example.com"),
        ),
        _p(
            "just cc p.venkataraman@ashcombe.example.ac.uk, she keeps the master copy.",
            Span("EMAIL/normal", "positive", "p.venkataraman@ashcombe.example.ac.uk"),
        ),
    ]

    # ---- EMAIL: spelled out -----------------------------------------------
    plants += [
        _p(
            "he told me it was r dot tindall at northgate clinic dot example dot co "
            "dot uk, which I wrote on my hand.",
            Span(
                "EMAIL/spelled_out",
                "positive",
                "r dot tindall at northgate clinic dot example dot co dot uk",
            ),
        ),
        _p(
            "so I said fine, send it to bogdan underscore petrescu at calderfield "
            "dot example dot com and forget about it.",
            Span(
                "EMAIL/spelled_out",
                "positive",
                "bogdan underscore petrescu at calderfield dot example dot com",
            ),
        ),
        _p(
            "the address on the poster was literally debs at ridgeway house dot example "
            "dot org, spelled out like that.",
            Span(
                "EMAIL/spelled_out",
                "positive",
                "debs at ridgeway house dot example dot org",
            ),
        ),
    ]

    # ---- PHONE ------------------------------------------------------------
    # Ofcom drama-reserved (07700 900xxx, 020 7946 0xxx) and NANP 555-01xx.
    plants += [
        _p(
            "she left me a voicemail on 07700 900412 and I never called back.",
            Span("PHONE/uk_mobile", "positive", "07700 900412"),
        ),
        _p(
            "my number then was 07700 900187, which I have not had for twenty years.",
            Span("PHONE/uk_mobile", "positive", "07700 900187"),
        ),
        _p(
            "the office line was 020 7946 0812 and it rang in an empty room most days.",
            Span("PHONE/uk_landline", "positive", "020 7946 0812"),
        ),
        _p(
            "you could reach the whole department on 020 7946 0345 back then.",
            Span("PHONE/uk_landline", "positive", "020 7946 0345"),
        ),
        _p(
            "their US desk was (212) 555-0147 and nobody ever picked up.",
            Span("PHONE/us", "positive", "(212) 555-0147"),
        ),
        _p(
            "I still remember the number, 415-555-0182, which tells you how often I rang it.",
            Span("PHONE/us", "positive", "415-555-0182"),
        ),
        _p(
            "for anyone outside the UK it was +44 7700 900318, and that worked fine.",
            Span("PHONE/intl", "positive", "+44 7700 900318"),
        ),
        _p(
            "the fax, and yes it was a fax, was +44 20 7946 0629.",
            Span("PHONE/intl", "positive", "+44 20 7946 0629"),
        ),
    ]

    # ---- LOCATION (outside production's entity set — reported separately) --
    plants += [
        _p(
            "we ran the whole sprint out of a rented flat in Harrogate, which was a mistake.",
            Span("LOCATION/city", "positive", "Harrogate"),
        ),
        _p(
            "half the contributors were in Skelmersdale, oddly enough.",
            Span("LOCATION/city", "positive", "Skelmersdale"),
        ),
        _p(
            "there was a real North Yorkshire cluster of us for a while.",
            Span("LOCATION/region", "positive", "North Yorkshire"),
        ),
        _p(
            "most of the funding came out of the East Riding, which nobody expected.",
            Span("LOCATION/region", "positive", "East Riding"),
        ),
        _p(
            "the meetings were in the Belmont Wing at Ridgeway House, up on the third floor.",
            Span("LOCATION/building", "positive", "the Belmont Wing at Ridgeway House"),
        ),
        _p(
            "we had a desk in Calderfield Tower for about eighteen months.",
            Span("LOCATION/building", "positive", "Calderfield Tower"),
        ),
    ]

    # ---- ORG (outside production's entity set — reported separately) -------
    plants += [
        _p(
            "the sponsor was Calderfield Logistics, who I don't think ever used the software.",
            Span("ORG/company", "positive", "Calderfield Logistics"),
        ),
        _p(
            "and Brindlewood Systems paid for the servers for two years running.",
            Span("ORG/company", "positive", "Brindlewood Systems"),
        ),
        _p(
            "the pilot ran inside Northgate Bay NHS Trust, which was a whole other governance problem.",
            Span("ORG/hospital", "positive", "Northgate Bay NHS Trust"),
        ),
        _p(
            "St Aldhelm's Infirmary took it up next and that's when it got real.",
            Span("ORG/hospital", "positive", "St Aldhelm's Infirmary"),
        ),
        _p(
            "the University of Ashcombe hosted the mirror for the best part of a decade.",
            Span("ORG/university", "positive", "the University of Ashcombe"),
        ),
        _p(
            "and Pennington Metropolitan University ran the summer school every year.",
            Span("ORG/university", "positive", "Pennington Metropolitan University"),
        ),
    ]

    # ---- Structured identifiers -------------------------------------------
    plants += [
        _p(
            "my staff number was KX-40921, which I typed about nine thousand times.",
            Span("ID/employee", "positive", "KX-40921"),
        ),
        _p(
            "they filed it against employee 88317-BW and never told him.",
            Span("ID/employee", "positive", "88317-BW"),
        ),
        _p(
            f"she read her NHS number out on the call, {NHS_A}, which made me wince.",
            Span("ID/nhs", "positive", NHS_A),
        ),
        _p(
            f"the record was under {NHS_B} and it took a month to get it corrected.",
            Span("ID/nhs", "positive", NHS_B),
        ),
        _p(
            f"and the second patient, {NHS_C}, had exactly the same problem.",
            Span("ID/nhs", "positive", NHS_C),
        ),
        _p(
            "the postcode was HG2 8QN and the postman still couldn't find it.",
            Span("ID/postcode", "positive", "HG2 8QN"),
        ),
        _p(
            "we were registered at LS17 6RD for tax purposes, briefly.",
            Span("ID/postcode", "positive", "LS17 6RD"),
        ),
        _p(
            "he was born on the 14th of March 1979, so he'd have been what, nineteen?",
            Span("ID/dob", "positive", "14th of March 1979"),
        ),
        _p(
            "her date of birth is 02/11/1962 and it was wrong on every form.",
            Span("ID/dob", "positive", "02/11/1962"),
        ),
    ]

    # ---- NEGATIVE probes: must NOT be redacted -----------------------------
    # Product / project names, several of which are also real surnames or
    # given names. These are the sharp end of the precision measurement.
    plants += [
        _p(
            "we built the whole CI pipeline on Jenkins and regretted it within a year.",
            neg("Jenkins", "product_is_surname", "also a common surname"),
        ),
        _p(
            "half the numerical work moved to Julia around then and never came back.",
            neg("Julia", "product_is_given_name", "also a common given name"),
        ),
        _p(
            "and Ada was still being taught in the defence world long after everyone else moved on.",
            neg("Ada", "product_is_given_name", "language; also a given name"),
        ),
        _p(
            "once Swift went open source the whole calculus changed for that community.",
            neg("Swift", "product_is_surname", "language; also a surname"),
        ),
        _p(
            "the packaging story on Debian was miles ahead of anyone else at that point.",
            neg("Debian", "product"),
        ),
        _p(
            "we froze the tree every March and unfroze it later in the year, more or less.",
            Span("NEGATIVE/month_name", "negative", "March"),
        ),
        _p(
            "I wrote most of it in Perl, which I am not proud of.",
            neg("Perl", "product"),
        ),
        _p(
            "everything went through Bugzilla, which went down constantly.",
            neg("Bugzilla", "product"),
        ),
        _p(
            "the monitoring was Nagios, and it woke me up more than my own children did.",
            neg("Nagios", "product"),
        ),
        _p(
            "we standardised on Gentoo for the build hosts, which was a choice.",
            neg("Gentoo", "product"),
        ),
        _p(
            "Mercurial had the better model and lost anyway, which happens.",
            neg("Mercurial", "product"),
        ),
        _p(
            "the Linux Foundation was the obvious home for it once it outgrew us.",
            neg("the Linux Foundation", "org_as_subject"),
        ),
        _p(
            "the Apache Software Foundation had already solved most of that governance problem.",
            neg("the Apache Software Foundation", "org_as_subject"),
        ),
        _p(
            "Red Hat were doing the same thing from the other direction, commercially.",
            neg("Red Hat", "org_as_subject"),
        ),
        _p(
            "Frankly, none of us thought it would still be running in 2020.",
            neg("Frankly", "capitalised_sentence_start"),
        ),
        _p(
            "Honestly, the licence argument took more of my life than the code did.",
            neg("Honestly", "capitalised_sentence_start"),
        ),
        _p(
            "Curiously, nobody objected until the release notes went out.",
            neg("Curiously", "capitalised_sentence_start"),
        ),
        _p(
            "the big one was always the September release, which nobody enjoyed.",
            Span("NEGATIVE/month_name", "negative", "September"),
        ),
        _p(
            "it shipped in August, or possibly it shipped in October, memory is imperfect.",
            Span("NEGATIVE/month_name", "negative", "August"),
        ),
        _p(
            "we ran Emacs and a lot of shouting, in roughly that order.",
            neg("Emacs", "tool"),
        ),
        _p(
            "the Vim people and the other lot never did reach an accommodation.",
            neg("Vim", "tool"),
        ),
        _p(
            "Grafana came much later and made all of it look tidier than it was.",
            neg("Grafana", "product"),
        ),
        _p(
            "the whole thing was glued together with Bash, which is the honest answer.",
            neg("Bash", "product"),
        ),
        _p(
            "Kotlin turned up and half the Android people switched inside a year.",
            neg("Kotlin", "product"),
        ),
        _p(
            "Vala was lovely and almost nobody used it.",
            neg("Vala", "product"),
        ),
        _p(
            "Berkeley Unix is where a lot of this actually starts, if you go back far enough.",
            neg("Berkeley Unix", "product"),
        ),
        _p(
            "there was a real argument about whether Rust belonged anywhere near the kernel.",
            neg("Rust", "product"),
        ),
        _p(
            "we tested it on Fedora and pretended that was enough coverage.",
            neg("Fedora", "product"),
        ),
        _p(
            "Ubuntu arrived later and changed who was even in the conversation.",
            neg("Ubuntu", "product"),
        ),
        _p(
            "the Debian Social Contract is a genuinely strange and rather wonderful document.",
            neg("the Debian Social Contract", "product"),
        ),
        _p(
            "Nobody remembers who wrote the original spec, which is probably for the best.",
            neg("Nobody", "capitalised_sentence_start"),
        ),
        _p(
            "Autumn was always the busy period, then it went quiet until spring.",
            neg("Autumn", "capitalised_sentence_start"),
        ),
    ]

    return plants


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    seg_id: str
    session: str
    timecode: str
    speaker: str
    text: str
    offset: int = 0  # global char offset of ``text`` within corpus.txt


def read_segments(source: Path, sessions: list[str]) -> list[Segment]:
    out: list[Segment] = []
    for sess in sessions:
        path = source / f"{sess}.txt"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _SEGMENT_RE.match(line.strip())
            if not m:
                continue
            tc, speaker, text = m.groups()
            text = text.strip()
            if len(text.split()) < 25:
                continue  # skip one-liners; we want prose to hide plants in
            out.append(Segment(f"{sess}-{len(out):04d}", sess, tc, speaker, text))
    return out


_SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def insert_mid_utterance(text: str, sentence: str, rng: random.Random) -> tuple[str, int]:
    """Insert ``sentence`` at a sentence boundary inside ``text``.

    Returns (new_text, offset_of_sentence_within_new_text). Never at index 0 —
    the whole point is that the plant is mid-utterance, not a clean opening.
    """
    boundaries = [m.end() for m in _SENT_END.finditer(text)]
    if not boundaries:
        # No internal boundary: append after the existing prose instead.
        joined = text.rstrip()
        if not joined.endswith((".", "!", "?")):
            joined += "."
        new_text = f"{joined} {sentence}"
        return new_text, len(joined) + 1
    at = rng.choice(boundaries)
    new_text = text[:at] + sentence + " " + text[at:]
    return new_text, at


def build_corpus(
    source: Path, target_words: int, seed: int
) -> tuple[list[Segment], list[dict]]:
    rng = random.Random(seed)
    segments = read_segments(source, SESSION_ORDER)
    if not segments:
        raise SystemExit(f"No segments parsed from {source}")

    # Take segments in order until the word target is met, so the corpus reads
    # as continuous interview rather than shuffled fragments.
    chosen: list[Segment] = []
    words = 0
    for seg in segments:
        chosen.append(seg)
        words += len(seg.text.split())
        if words >= target_words:
            break

    plants = build_plants()
    # Plants outnumber segments (segments are long FOSSDA paragraphs), so
    # distribute round-robin — evenly spread, at most two per segment.
    if len(plants) > 2 * len(chosen):
        raise SystemExit(
            f"{len(plants)} plants but only {len(chosen)} segments — raise --words"
        )
    slots = [int(i * len(chosen) / len(plants)) for i in range(len(plants))]

    # Insert first, resolve offsets afterwards: a second insertion into the
    # same segment shifts the first one's offsets, so recording them at
    # insertion time is wrong.
    placed: list[tuple[Segment, Plant]] = []
    for plant, slot in zip(plants, slots):
        seg = chosen[slot]
        seg.text, _ = insert_mid_utterance(seg.text, plant.sentence, rng)
        placed.append((seg, plant))

    # Compute global offsets over the flat corpus.
    cursor = 0
    for seg in chosen:
        seg.offset = cursor
        cursor += len(seg.text) + 2  # "\n\n" join

    truth: list[dict] = []
    for seg, plant in placed:
        if seg.text.count(plant.sentence) != 1:
            raise AssertionError(f"planted sentence is not unique: {plant.sentence!r}")
        sent_off = seg.text.index(plant.sentence)
        for span in plant.spans:
            local = sent_off + plant.sentence.index(span.surface)
            truth.append(
                {
                    "category": span.category,
                    "kind": span.kind,
                    "surface": span.surface,
                    "note": span.note,
                    "seg_id": seg.seg_id,
                    "seg_start": local,
                    "seg_end": local + len(span.surface),
                    "start": seg.offset + local,
                    "end": seg.offset + local + len(span.surface),
                }
            )

    # Verify every recorded span really is where we say it is, both in the
    # flat corpus and in the segment production would actually analyse.
    flat = "\n\n".join(s.text for s in chosen)
    by_id = {s.seg_id: s for s in chosen}
    for item in truth:
        if flat[item["start"] : item["end"]] != item["surface"]:
            raise AssertionError(f"global offset drift for {item['surface']!r}")
        seg = by_id[item["seg_id"]]
        if seg.text[item["seg_start"] : item["seg_end"]] != item["surface"]:
            raise AssertionError(f"segment offset drift for {item['surface']!r}")

    return chosen, truth


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--words", type=int, default=7200, help="base-text word target")
    ap.add_argument("--seed", type=int, default=1729)
    args = ap.parse_args()

    segments, truth = build_corpus(args.source, args.words, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    flat = "\n\n".join(s.text for s in segments)
    (args.out / "corpus.txt").write_text(flat, encoding="utf-8")
    (args.out / "segments.json").write_text(
        json.dumps([asdict(s) for s in segments], indent=1), encoding="utf-8"
    )
    (args.out / "ground_truth.json").write_text(
        json.dumps(truth, indent=1), encoding="utf-8"
    )

    pos = [t for t in truth if t["kind"] == "positive"]
    negs = [t for t in truth if t["kind"] == "negative"]
    print(f"corpus:     {len(segments)} segments, {len(flat.split()):,} words, "
          f"{len(flat):,} chars")
    print(f"planted:    {len(pos)} positive spans, {len(negs)} negative probes")
    cats: dict[str, int] = {}
    for t in truth:
        cats[t["category"]] = cats.get(t["category"], 0) + 1
    for cat in sorted(cats):
        print(f"  {cat:34s} {cats[cat]}")
    print(f"written to: {args.out}")


if __name__ == "__main__":
    main()
