# Shared formats across Python, TypeScript and Swift

**Status:** live register · established 22 Aug 2026
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

| Format | Datum | Python | TypeScript | Swift | Status |
|---|---|---|---|---|---|
| `duration_human` | elapsed span | `_format_duration_human` | `formatDurationHuman` | `DurationFormat.human` | **aligned**, pinned |
| `finder_date` | Finder-style relative timestamp | `format_finder_date` | `formatFinderDate` | `SessionsFinderDate.format` | **aligned by pair**, one deliberate fork |
| `timecode` | position in a recording | 4 implementations | 5 implementations | — | **divergent** — 3 formats |
| `finder_filename` | middle-ellipsis truncation | `format_finder_filename` | `formatFinderFilename` | — | **divergent** — off-by-one |
| `plural_category` | count-dependent noun forms | `count_noun` (inflect) | i18next CLDR | `I18n.pluralCategory` | **deliberately forked** |

Per-entry detail, measured values and the exact case tables live in the JSON
companion. The table above is a summary and will drift from it; the JSON is the
source of truth.

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
so the case is excluded from the pinned table rather than forced.

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

**`SessionsFinderDate.swift`'s header is the exemplar contract docstring in this
codebase.** Read it before writing any new mirror. It names its source with a
file and line, enumerates four load-bearing details with the rationale for each,
names the third implementation and says why it differs, and carries a
KNOWN-WRONG section about the underlying value. That is the standard.

---

## 4. The gaps

Recorded, not fixed. Each needs a decision before it needs code.

### `timecode` — 9 implementations, 3 distinct formats

| Rendering | Implementations |
|---|---|
| `05:30` / `01:05:30` / `00:45` | `utils/timecodes.py`, `models.py` |
| `5:30` / `1:05:30` / `0:45` | `export_core.py`, `mcp_server.py`, and 4 local TypeScript copies |
| `05:30` / `1:05:30` / `00:45` | `frontend/src/utils/format.ts` — matches neither Python family |

**User-visible today:** a quote card renders `05:30`, and exporting that same
quote to CSV renders `5:30`. One click apart, same datum, same surface.

**Decided 22 Aug 2026 (Martin): timecodes carry leading zeros; durations do
not.** That eliminates the unpadded family — six of the nine implementations.
One sub-detail is still open: whether the *hour* field also pads, `01:05:30` as
both shared-library Python helpers do, or `1:05:30` as `format.ts` and every
unpadded variant do. That needs resolving before anyone writes the fix.

Note that 8 of the 9 are copy-paste duplicates of a helper that already exists
in the same language. Deduplicating to one implementation per language is most
of the work, and is mechanical once the format is settled.

### `finder_filename` — off-by-one

Python renders `interview-wi…n-final.mov`; TypeScript renders
`interview-wit…-final.mov`. They disagree on 1 of 4 sampled realistic filenames
and agree on the rest, which is why it has never surfaced. Low impact, low fix
cost — but it still needs a decision on which front/back split is correct, so it
is not trivial-by-inspection.

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
  highest-value item here.
- Extending the register to cover CLI-only formats (`format_cost_estimate`,
  `format_resume_summary`) if any of them ever gains a second implementation.
