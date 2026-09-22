---
status: partial
last-trued: 2026-09-12
trued-against: HEAD@main on 2026-09-12
---

> **Truing status:** Current with targeted edits (trued 2026-09-12). The `timecode` entry records the one breach of "one implementation per language" and its closure; `duration_human` records the 12 Sep move of its canonical body; `finder_date` moves from declined to deferred; a new "Open holes against this register" block names what the register asserts but does not test. See changelog.

## Changelog

- _2026-09-12_ — trued up against the time audit: timecode entry gains the H5 breach-and-closure and a forward-ref to the prompt-only sibling; duration_human records the canonical move to `utils/timecodes.py` and the superseded `1 h 0 min` shape; the zero fork stated as catalogued-but-unasserted and by-datum; finder_date deferred to Tier 2 with H9/H10; new "Open holes" block; the lint-rule item cites H5. Anchors: `bristlenose/miro_board.py:129-133`, `utils/timecodes.py:68`, `tests/test_shared_format_contract.py:105-120`, `docs/time-defects.md` H5/H7/H9/H10/H12.

# Shared formats across Python, TypeScript and Swift

**Status:** live register · established 22 Aug 2026 · trued 12 Sep 2026 against the time audit (`docs/time-defects.md`) · `plural_category` re-classified 22 Sep 2026 when Python gained a CLDR implementation
**Machine-readable companion:** [`tests/fixtures/shared-format-contract.json`](../tests/fixtures/shared-format-contract.json)
**Enforced by:** [`tests/test_shared_format_contract.py`](../tests/test_shared_format_contract.py) · [`frontend/src/utils/sharedFormatContract.test.ts`](../frontend/src/utils/sharedFormatContract.test.ts)

Bristlenose renders the same values in three languages. The pipeline and server
are Python, the report SPA is TypeScript, the macOS shell is Swift, and a
researcher moves between all three inside one task — a session's length appears
in a native window subtitle, in a web grid, and in a downloaded CSV. Each
language needs its own implementation; there is no shared runtime and there
should not be one. So the question is not *how do we avoid duplicating these*
but *how do we keep the duplicates honest*.

This document is the register. It records what exists, which entries agree,
which do not, and what has been deliberately decided to differ.

---

## 1. Two classes, and only one of them is dangerous

The distinction was already articulated in the codebase before this document
existed, in [`SessionsFinderDate.swift`](../desktop/Bristlenose/Bristlenose/SessionsFinderDate.swift):

> …these are independent local renderings, not a wire format, so a mismatch is
> cosmetic (unlike the Swift/Python `start_time` token, which is parsed).

That is the axis the whole register turns on.

**Class W — wire / parsed.** One side writes, another side reads. A mismatch
breaks function: a field goes undecodable, an enum case falls through, a run
reports the wrong outcome. These were already well handled before this
document — mirrors are named `Swift mirror of <python module>` in their header,
the canonical side is stated, and several are pinned by a shared JSON fixture.

**Class R — rendered.** Each side formats independently for a human to read.
A mismatch breaks nothing; it produces a visible inconsistency the user notices
and cannot explain. Before 22 Aug 2026 these had prose conventions and no
register, no back-pointer from the canonical implementation, and no gate.

Every drift measured during the 22 Aug audit was Class R.

### Why Class W was already fine

Class W has had a working mechanism since 7 May 2026:
[`tests/fixtures/pipeline-summary-contract.json`](../tests/fixtures/pipeline-summary-contract.json)
is read by both [`tests/test_swift_contract_parity.py`](../tests/test_swift_contract_parity.py)
and `PipelineSummaryTests.swift`, and both sides round-trip every scenario.
`test_swift_contract_parity.py` goes further and pins *optionality* parity,
having been written after a null-vs-non-optional mismatch reported a completed
run as failed.

**The Class R mechanism in this document is that same pattern, extended.** It is
not a new invention, which is most of why it is cheap.

---

## 2. The register

> **31 Aug 2026 — one new format, deliberately NOT registered, and one rule
> gap it exposed.**
>
> `frontend/src/utils/codebookReach.ts` renders *"28 tags · applied to 2 quotes
> in Ikea"* for the codebook browse card and its detail page. It is **TypeScript
> only** — no Python or Swift twin exists, verified — so by this register's own
> rule (a CLI-only format enrols *"if any of them ever gains a second
> implementation"*) it stays out. Recorded here so the absence reads as
> *checked* rather than *overlooked*, which is the whole value of a register.
>
> It also uses a **hand-rolled English ternary** for plurals, not i18next CLDR —
> a fourth mechanism beside the three the `plural_category` row names. That is
> intentional and time-boxed: codebook v2 is dev-gated and English-only until it
> graduates, which is also when its chrome needs locale keys. It is debt, and
> this is where a future contributor would grep for it.
>
> **The rule gap:** §5's one-stem rule governs *cross-language* families. This
> module was first written as `codebookCounts.ts` while `codebookCounts()`
> already existed in `lensSubtitle.ts`, returning something else entirely — two
> unrelated things under one stem, in the same language, which a grep for the
> family would have conflated. Renamed the same day. **The stem rule needs a
> same-language clause: a name must not collide with an existing helper in its
> own language either.** Note the two are also two renderings of the same datum
> — `lensSubtitle.ts` says "47 Tags" (localised, capitalised) for the window
> subtitle while this says "28 tags" (hand-pluralised, lowercase) in the page
> body. That is the `duration_human` story starting again inside one language.

| Format | Datum | Python | TypeScript | Swift | Status |
|---|---|---|---|---|---|
| `duration_human` | elapsed span | `format_duration_human` (`utils/timecodes.py`) | `formatDurationHuman` | `DurationFormat.human` | **aligned**, pinned |
| `finder_date` | Finder-style relative timestamp | `format_finder_date` | `formatFinderDate` | `SessionsFinderDate.format` | **aligned by pair**, one deliberate fork |
| `timecode` | position in a recording | `format_timecode` | `formatTimecode` | — | **aligned**, pinned · also parsed |
| `finder_filename` | middle-ellipsis truncation | `format_finder_filename` | `formatFinderFilename` | — | **aligned**, pinned |
| `plural_category` | count-dependent noun forms | `count_noun` (inflect, CLI) · `plural_category` (CLDR, server) | i18next CLDR | `I18n.pluralCategory` | **aligned by pair**, pinned ([`cldr-plural-contract.json`](../tests/fixtures/cldr-plural-contract.json)) |

Per-entry detail, measured values and the exact case tables live in the JSON
companion. The table above is a summary and will drift from it; the JSON is the
source of truth.

**`plural_category` stopped being a three-way fork on 22 Sep 2026.** It was
listed as *deliberately forked* because each surface had its own mechanism and
no two needed to agree: `inflect` for English terminal chrome, i18next in the
browser, `I18n.pluralCategory` for the Mac menus. Then the Miro board — a
deliverable, rendered server-side, in whatever language the researcher works in
— needed a CLDR category from **Python**, and the fork acquired a pair that must
agree. `bristlenose/i18n.py`'s `plural_category` was transcribed from the Swift
rule, which is precisely the kind of copy that is correct wherever you check it,
so neither side owns the answer: both assert
[`tests/fixtures/cldr-plural-contract.json`](../tests/fixtures/cldr-plural-contract.json),
whose counts are the *exception boundaries* — the teens, and the mod-10 carries
where pl says `many` and ru/uk say `one` at 21. A range of 1–10 passes against a
rule that is wrong everywhere it matters.

`count_noun` is untouched and stays the English answer for the terminal, which
is English by decision (root `CLAUDE.md` § CLI plurals). The stem rule holds:
one stem, house casing per language — `plural_category` / `pluralCategory`.

### Status vocabulary

- **aligned** — all implementations agree; the JSON carries a `cases` table and
  both test suites assert it. Drift fails a build.
- **aligned by pair** — two implementations are at deliberate parity and a third
  deliberately differs, with the reason recorded.
- **divergent** — implementations do not agree. The JSON records *measured*
  outputs so the gap is countable. **Nothing asserts these values as correct.**
- **deliberately forked** — different mechanisms on purpose; listed so nobody
  "discovers" it later and tries to unify it.

---

## 3. What is aligned

### `duration_human` — aligned 22 Aug 2026

**Moved 12 Sep 2026:** the canonical body now lives in
`utils/timecodes.py:format_duration_human`; `server/routes/dashboard.py`
delegates to it. Until then the helper *in the module named for timecodes* was a
different shape (`1 h 0 min`, and `1 min` for a 30-second span) with one caller —
the static report's total, which read `18 h 23 min` against the SPA's `18h 23m`
for the same number. Closed with the move (H7 in `docs/time-defects.md`).

`26m` / `1h 3m` / `1h` / `<1m`. Python feeds the `duration_human` and
`total_duration_human` API fields; Swift renders the window subtitle, the
sessions popover and the cloud-import list; TypeScript renders the Sessions
grid, the Dashboard session table and the Sessions sidebar.

Before that date there were four live renderings of this one value, two of them
`MM:SS`, which read as a *time of day* in a column that also carries dates and
start times. Measured across the 236 sessions in the local trial corpus, the
human form is also **narrower** than what it replaced (mean 3.28 characters
against 5.09, max 6 against 7), so terseness argued for the change rather than
against it.

**One deliberate divergence, recorded in the JSON.** A non-positive duration
renders `0m` in Python and Swift and an em-dash in TypeScript. Python and Swift
format aggregate totals, where a real zero is a real answer; the TypeScript
sites format a per-row cell, where zero means *unknown* — 8% of the corpus — and
`0m` would assert a measurement nobody made. Each side is right for its context,
so the case is excluded from the pinned table rather than forced — it is
catalogued in the entry's `divergences` with both outputs, but **no test reads
that array**, so nothing mechanical holds the fork in either direction (H12,
open). And the fork is by *datum*, not by language: Python's `routes/dev.py`
renders a per-row cell and shows the em-dash too.

The `h` / `m` abbreviations are knowingly unlocalised on all three sides.
Changing that is a separate decision with a 22-locale cost; see §6.

### `finder_date` — aligned by pair

The TypeScript and Swift implementations are at exact parity because the
sessions popover and the Sessions grid sit on the same lens and must agree; the
Swift side adopts the TypeScript contract by name. Python renders `Today at
16:59` against their `Today, 16:59`, targeting a markdown transcript header —
a different medium, deliberately a different separator.

Not machine-pinned: all three take a clock and a locale, so a fixture would need
injected time and Intl/CLDR-stable behaviour on three runtimes. The cost is real
and the payoff is small, since the pair is already documented on both sides.

**Deferred to Tier 2, not declined** (12 Sep 2026). The absolute-date branch
can be pinned once the wire carries an offset (`docs/design-timezones.md` § 5.3),
and it should be: the time audit found a fork this register did not know about —
`session_date` reaches the wire naive, so all three surfaces render the
viewer's-local reading of a UTC instant, off by the offset *together* (H9, H10
in `docs/time-defects.md`). "Exact parity" here is an assertion zero cases test.

**`SessionsFinderDate.swift`'s header is the exemplar contract docstring in this
codebase.** Read it before writing any new mirror. It names its source with a
file and line, enumerates four load-bearing details with the rationale for each,
names the third implementation and says why it differs, and carries a
KNOWN-WRONG section about the underlying value. That is the standard.

---

## 4. The gaps

Both gaps found in the 22 Aug 2026 audit closed the same day. Their records are
kept because *how* they closed is the useful part — one of them turned out not to
be the kind of format everyone assumed it was.

### `timecode` — closed 22 Aug 2026

Was 9 implementations across 3 formats. 8 of them were copy-paste duplicates of a
helper that already existed in the same language; the user-visible symptom was a
quote card rendering `05:30` while the CSV export of that same quote rendered
`5:30`.

**Decided:** pad the minute field, never the hour — `05:30` and `1:12:45`.
Minutes genuinely range 00–59, so padding buys column alignment down a list of
quotes. Hours never reach two digits in research data — the longest session in
ten years of the maintainer's practice is 90 minutes, and an all-morning
symposium tops out near 3h — so padding the hour reserves a column for
`09:34:23` that no interview will ever occupy and makes the reader parse a
leading zero that is meaningless 99% of the time. It also matches how video
editors render elapsed position, which is the tool researchers use to trim clips
from these same recordings. _One sibling deliberately breaks this rule, for a
reader that is not a person — see the prompt-only note below._

One implementation per language — **breached once and re-closed.**
`miro_board.fmt_timecode` was a fourth Python copy from 22 Aug to 12 Sep 2026
(`f"{total // 60}:{total % 60:02d}"` — minutes never rolled into hours, and from
100 minutes its output could not be parsed back; the corpus's longest session is
99.7). The enrolment gate did not see it: `test_no_second_python_timecode_impl`
asserts identity across four import sites of seven, and `miro_board.py`,
`s10_quote_clustering.py` and `s11_thematic_grouping.py` import directly. H5 in
`docs/time-defects.md`; its lesson is that the fix was never "add hours to the
Miro label" — it was a fourth copy of a format this register had closed. Now: `bristlenose/utils/timecodes.py` (re-exported
from `models.py`, imported directly by `export_core.py` and `mcp_server.py`) and
`frontend/src/utils/format.ts` (imported by the four components that each held a
private copy).

**This entry is the exception to the whole document: it has a parsed half.**
Transcript `.txt` / `.md` files are a *round-trip* format — the pipeline writes
them and reads them back on resume and re-analysis — so `timecode` is Class R on
screen and Class W on disk. Two things follow, and both are pinned in
`tests/test_transcript_writing.py`:

1. The reader's leading field must stay `\d{1,2}`. It was `\d{2}`, and when the
   hour stopped being padded a `[1:00:00]` segment stopped matching and was
   dropped **silently** — no error, a short transcript the only symptom. This was
   not predicted by checking `parse_timecode`, which was already tolerant; the
   transcript line reader is a *different* regex in `pipeline.py`, and it was the
   round-trip assertion in an existing test that caught it, not the check.
2. That tolerance is permanent backward compatibility. Transcripts already on a
   researcher's disk carry the old `[01:00:00]` form and must keep loading.

**A prompt-only sibling exists, deliberately outside this register.**
`format_timecode_prompt` (11 Sep 2026) renders zero-padded `HH:MM:SS` and is
called only by `full_text()` / `participant_text()` and s09's `boundaries_text`
— the text handed to an LLM, never to a person and never to disk. It looks like
a violation of the decision above ("pad the minute, never the hour") and is not:
that decision is about what a *reader* parses, and this string has no reader.
It exists because `format_timecode` omitting the hour left the prompt saying
`05:30` while the schema asked for `HH:MM:SS`, and `gpt-5.6-terra` resolved the
mismatch by appending `:00` — 63% of quote timecodes exactly 60x too large
(`experiments/quote-stability/FINDINGS.md` § 3). **Do not fold the two together.**
A tidy-up that routes the prompt back through `format_timecode` reinstates the
defect, and nothing user-facing would look wrong.

**The general lesson, and the reason this is recorded rather than quietly fixed:
before changing a rendered format, check whether anything parses it back — and
check every reader, not the one named after the format.**

### `finder_filename` — closed 22 Aug 2026

One operator. Both sides split the budget 2:1 front-to-back; Python floored the
front (`budget * 2 // 3`) and TypeScript ceiled it (`Math.ceil`). So they
disagreed for every 3-, 4- and 6-character extension and agreed only on 2- and
5-character ones — which is to say they disagreed on **every common media file**
(`.mov`, `.mp4`, `.vtt`, `.m4a`, `.wav`) and agreed on `.docx`. The original
"disagrees on 1 of 4 sampled names" reading was an artefact of the sample, not a
random off-by-one.

**Decided:** round up, adopting the TypeScript form. Neither lost information —
the difference was one character of balance, and both preserved the
discriminating parts of the real corpus's worst case (`09-heather-meeker-pt1.mp4`
against `10-heather-meeker-pt2.mp4`, which differ at *both* ends). TypeScript won
on two grounds: it is the live surface — the Sessions grid and Dashboard filename
column, where the Python side feeds only the sealed static render and the dev
route — so adopting it changed nothing any user sees; and it is the front-heavier
form, which is what the Python docstring said it wanted.

**The docstring was wrong too.** It claimed `format_finder_filename("Fishkeeping
Research S3.vtt")` returns `Fishkeeping Rese…S3.vtt` — an output *neither*
implementation ever produced, and much more front-heavy than either. Corrected in
the same commit. A worked example that no code path produces is worse than no
example, because it reads as the specification.

Verified by exhaustive sweep rather than by sampling: 472 synthetic names
(extension lengths 0–7 × stem lengths 1–59) plus the real trial-corpus
filenames, zero mismatches.

One thing this format is not, and is worth stating so nobody "fixes" it: the
character budget is an approximation by construction. Finder truncates by **pixel
width** with `NSLineBreakByTruncatingMiddle`, not by character count. These
functions match Finder's *shape*, not its arithmetic, and a proportional font
makes exact parity impossible anyway.

### Not a gap: two local `formatDuration` twins

[`AutoCodeToast.tsx`](../frontend/src/components/AutoCodeToast.tsx) and
[`ActivityChipStack.tsx`](../frontend/src/components/ActivityChipStack.tsx) hold
byte-identical private `formatDuration` helpers. They format a *different*
datum — how long a background job ran, not how long a session was — so they are
out of this register's scope. They are the same disease in a different organ,
and worth folding into one helper whenever either file is next touched.

---

## 5. Conventions

### Nomenclature: one stem, house casing per language

A shared format gets **one name**, spelled in each language's own convention:

```
duration_human   →   formatDurationHuman      →   DurationFormat.human
(Python)             (TypeScript)                 (Swift)
```

This is the part that was missing. Before 22 Aug the duration implementations
were called `_format_duration_human`, `formatCompactDuration` and
`DurationFormat.human` — no shared stem, so no grep found the set, and a fourth
rendering could be added without anyone meeting the other three. The stem is
what makes the family discoverable.

The stem is also the JSON key in the contract fixture, so the register, the
tests and the source all use the same word.

### Adding a new shared format

1. Name it — one stem, per §5.
2. Write the canonical implementation, and say in its docstring that it *is*
   canonical.
3. Each mirror's header names the canonical one **with file and line**, states
   what is load-bearing, and records any deliberate divergence with its reason.
   Model it on `SessionsFinderDate.swift`.
4. Add an entry to the JSON companion. If the implementations agree, mark it
   `aligned` and give it a `cases` table — both test suites pick it up
   automatically. If they do not, mark it `divergent` and record the measured
   outputs.

### Open holes against this register

The register asserts more than it tests. Standing gaps, each with a home in
`docs/time-defects.md`:

- **H5 — the enrolment gate covers 4 of 7 Python import sites.** A copy that
  imports `format_timecode` directly is invisible to it; `miro_board.py` was.
- **H10 — `finder_date` has three implementations and zero pinned cases.**
- **H12 — the zero-duration fork is catalogued, not asserted.**
- **Unregistered renderers in the canonical module and beside it:**
  `format_timecode_ms` (zero callers repo-wide — dead code),
  `format_clip_timecode` (`server/clip_manifest.py:107`, hour-eliding bounded
  by its caller and audited sound — `docs/design-export-clips.md`), and the
  prompt-only `format_timecode_prompt` (deliberate, above).

### Closing a gap

Promote the entry to `aligned`, register the implementation in `_python_impl`
(Python) and `IMPLS` (TypeScript), and give it `cases` — **in the same commit as
the fix**. Both suites carry a check that a `divergent` entry is still actually
divergent, so a fix without a register update fails with a message telling you
to promote it. That is the intended workflow, not an obstacle to it.

---

## 6. Deliberately not built

Recorded so these are not re-proposed as discoveries, and so the reasoning is
available if the trade-off ever changes.

- **Codegen from a schema.** These are five-line functions doing integer
  division. A generator would need a build step in three toolchains and would
  cost more than the drift it prevents. This matches the stance already taken in
  `test_swift_contract_parity.py`: *"Deliberately NOT a codegen step — one
  contract, four structs. If a third mirror appears, revisit."*
- **A shared native or WASM core.** Disproportionate for the same reason.
- **Server-side rendering of every string.** Would kill client-side locale —
  `formatFinderDate` takes `i18n.language` precisely so the *viewer's* locale
  decides — and would bake the server's locale into every export.
- **A Swift arm of the render-contract test.** The one Class R format Swift
  implements, `duration_human`, is already pinned by `DurationFormatTests.swift`
  against the same table, and both measured drifts were Python↔TypeScript. The
  precedent for wiring it exists and is cheap when wanted:
  `PipelineSummaryTests.swift` walks up from `#filePath` to `tests/fixtures/`,
  and `I18nTests.swift` uses the same fallback. Left as a named next step rather
  than built blind, since this session could not run the Xcode suite to verify
  it.

### What a later, more formal version might want

Not proposed now; listed so the direction is on record.

- Property-based agreement tests over a generated input range, rather than a
  fixed case table.
- A lint rule that fails a build when a `format*` function is defined outside
  its language's canonical module — which would have prevented all eight
  duplicate timecode helpers at the point they were written, and is probably the
  highest-value item here — H5 is the incident it would have caught: a fourth
  `timecode` copy in `miro_board.py`, live from 22 Aug to 12 Sep 2026.
- Extending the register to cover CLI-only formats (`format_cost_estimate`,
  `format_resume_summary`) if any of them ever gains a second implementation.
