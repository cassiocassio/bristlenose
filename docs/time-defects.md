---
status: partial
last-trued: 2026-09-12
trued-against: HEAD@main on 2026-09-12
---

> **Truing status:** Partial — the findings and their outcomes are current (trued 2026-09-12, same day as the fixes); the pre-fix measurement tables in § 4 and the § 3b surface matrix are retained as the baseline the fixes are measured against. § 3c and Tier 2 items are correctly open. See changelog.

## Changelog

- _2026-09-12_ — trued up after the fixes landed: preamble no longer says nothing is fixed; finding count twelve; § 3a parse table shows the decided outcomes; § 3b duration cell and H7's table gain a post-fix line; H10/H12/§ 5 counts moved 15→21 and the zero fork stated as catalogued-but-unasserted; § 5's "untested" list reduced to `format_timecode_ms` and § 3c; new "Landed guard-rails" subsection; anchors re-pointed (`miro_board.py:129-133`, `pipeline.py:2904`, `dashboard.py:503`, `clips_export.py:370-371`); `_iso_lenient` named as the historical name of `parse_iso_lenient`; T0-6 marker and body reconciled. Anchors: commits "time: tier 0 and tier 1 of the audit", "time: review fixes — one probe, a parser that cannot crash a scan, and tests that can fail".

# Time in Bristlenose — three data types, their ranges, and an end-to-end audit

_Audited 12 Sep 2026, across Python, TypeScript and Swift. Every claim below was
measured by running the code, not read off it; where something is inferred it
says so. **Diagnosed 12 Sep 2026; Tiers 0–1, § 5.1 and the review fixes landed the same day** (`git log -S parse_iso_lenient`) — each finding carries its outcome._

_**Twelve findings stand (H1–H13 less H6). H6 was raised and withdrawn** — it is kept in place,
because the reasoning that made a correct design look like a defect is the
reasoning a future auditor will repeat._

Companion: `docs/design-shared-formats.md` (the cross-language register) and
`tests/fixtures/shared-format-contract.json` (the pinned case table).

**The timezone slice of this audit is split out into `docs/design-timezones.md`**
— multi-zone studies, a researcher moving between sessions, and DST regimes that
disagree on the date. Explicitly post-beta; that doc says why, and why the
zone-capture half is worth doing early even so.

---

## 1. Three data types, and why they get confused

| | datum | domain | rendered | parsed back? |
|---|---|---|---|---|
| **position** | offset into a recording | `[0, session duration]` | `05:30` · `1:12:45` | **yes** — round-trip off disk |
| **duration** | an elapsed span | `[0, session duration]` | `26m` · `1h 3m` | no (display only) |
| **start time** | a wall-clock instant | any date, any time, any zone | `Today, 14:23` · `9 May 2026, 14:23` | yes (ISO on disk) |

All three can render as `01:30:00`, which is the whole problem. The register
already records the cost: conflating *position* with *duration* made the Sessions
grid show a duration in a column beside dates, where `26:31` reads as a time of
day (fixed 22 Aug 2026).

A fourth, quieter confusion sits underneath: **position and duration share a
numeric domain but not a zero.** A position of 0 is the start of the recording, a
real and common value. A duration of 0 is almost always *unknown* — 19 of 236
sessions in the local corpus (8%) carry `duration_seconds == 0` because nothing
probed them.

---

## 2. Parameters — what we actually have to cope with

**Session length.** `design-shared-formats.md` states the practice: the longest
session in ten years of the maintainer's work is **90 minutes**, and an
all-morning symposium tops out near **3 hours**. The measured corpus agrees and
sits uncomfortably close to a cliff — the two longest FOSSDA sessions are **99.7
min** (s5) and **94.3 min** (s3).

So the design range is:

| | typical max | supported | beyond |
|---|---|---|---|
| position / duration | 0 – 3 h | **up to 9:59:59** (one hour digit) | exists, not commonly supported |

**Why those two numbers, and why they are different.** Three hours is the
*typical* likely maximum from real practice — the upper limit of human
concentration in a research session. An interview is booked for an hour; a
workshop runs to three at the outside; past that a recorder is capturing people
who need lunch, not research data.

The *supported* boundary is a separate fact: **one hour digit gives 9:59:59,
which is longer than a working day.** That is the natural edge of the
unpadded-hour format `design-shared-formats.md` decided on, and it comfortably
contains every session the practice produces. Research contexts with longer
recordings exist; they are not something the product needs to commonly support,
and the right behaviour past the edge is to fail loudly rather than render
something plausible.

So the two numbers answer two questions — *what will we see?* (3 h) and *what
must never render wrongly?* (up to a single hour digit) — and a future argument
to move either has to be about what a research session is, not about what a
disk can hold.

That mattered because one helper broke at **100 minutes** (§ 4, H5 — fixed 12 Sep) and the
corpus already contains a 99.7-minute session.

**Start time.** Any time of day, any date, and — because the maintainer is in
London — **both sides of a DST boundary**. A session started at 14:23 BST is
13:23 UTC. Which of those the researcher sees is currently surface-dependent
(H9).

### The elide-the-hour convention — a decided house rule, not an accident

**An hour field is shown only when something in view actually reaches an hour.**
This is deliberate, documented in two places, and it is the rule most of the
findings below have to be read against.

*Why.* Almost every interview is **booked** for an hour, and recording starts
after the initial chit-chat, so a session booked 1h and overrunning to 1h04 in
the room is commonly **52 minutes** on disk. The sub-hour case is not an edge —
it is the overwhelming default. A human writing that timecode writes `17:32`,
never `00:17:32`; the leading `00:` is a significant figure that is real to a
computer and meaningless to a reader 99% of the time.

*Where it is written down.*

- `design-shared-formats.md` § "`timecode` — closed 22 Aug 2026": *"pad the
  minute field, never the hour… padding the hour reserves a column for
  `09:34:23` that no interview will ever occupy and makes the reader parse a
  leading zero that is meaningless 99% of the time. It also matches how video
  editors render elapsed position."*
- `design-export-clips.md` § Filenames: *"Sessions under 1 hour: `{mm}m{ss}`…
  If **any** session in the project exceeds 1 hour: all timecodes switch to
  `{h}h{mm}m{ss}`"* — and it is in that doc's QA checklist (line 270).

*The scope subtlety worth keeping.* Clip filenames elide per **export**, not per
clip: if one session in the project passes an hour, every filename in that export
gains the hour field. That is right for a Finder window sorted by name, where
mixed widths would sort and scan badly — the question "does anything here reach
an hour?" is asked of the set, not the item.

*The one place the convention is deliberately suspended:* `format_timecode_prompt`
pads always, because the LLM schema asks for `HH:MM:SS` and the mismatch between
what the prompt showed and what the schema asked is what caused the 60x defect
(§ `time` history in `FINDINGS.md` § 3). A prompt has no human reader, so the
convention's rationale does not apply.

**Display formats**, as decided and pinned:

- position — minutes padded, hours never: `05:30`, `1:12:45`
- duration — `<1m` · `26m` · `1h` · `1h 3m`, hours/minutes only, unlocalised `h`/`m`
- start time — Finder-relative: `Today, 14:23` / `Yesterday, 14:23` / `9 May 2026, 14:23`

---

## 3. The challenge set

What correct code must survive. Values marked **✗** are where something in the
tree currently fails; the reference column is what a correct implementation
returns.

### 3a. Position (timecode)

| seconds | why it is interesting | `format_timecode` |
|---|---|---|
| 0 | start of recording; a real value, not "missing" | `00:00` |
| 1, 59 | sub-minute | `00:01`, `00:59` |
| 60 | first minute rollover | `01:00` |
| 599 / 600 | 1→2 digit minutes | `09:59` / `10:00` |
| 3599 / 3600 | **the format switch** | `59:59` / `1:00:00` |
| 5999 / 6000 | **99→100 minutes** — H5 breaks here | `1:39:59` / `1:40:00` |
| 10800 | 3 h — the realistic ceiling | `3:00:00` |
| 35999 / 36000 | 1→2 digit hours | `9:59:59` / `10:00:00` |
| 359999 / 360000 | **99→100 hours** — H2 breaks here | `99:59:59` / `100:00:00` ✗ |
| 83.456 | fractional input | `01:23` (truncate, not round) |
| 3599.9 | fractional at the switch — must NOT round up to `1:00:00` | `59:59` |
| −1 | never legitimate; must not render `-1:-1` | clamp to `00:00` |

**Parse side** — strings a reader must accept or refuse *deliberately*:

| input | source | correct |
|---|---|---|
| `05:30`, `1:30:00`, `01:30:00` | our own output | accept |
| `00:01:23,456` | SRT | accept (83.456) |
| `00:01:23.456` | VTT | accept (83.456) |
| `1:2:3` | third-party, unpadded | refused, by measurement — 344 real files, zero in the wild; pinned (H3) |
| `90:00` | minutes past 60 | accept (5400) — our own Miro output emits this |
| `100:00:00` | ≥100 h | refused — the declared limit, pinned (H2) |
| `00:01:23 extra` | malformed line | refused since `fullmatch` (H4, pinned) |
| `""`, `"later on"` | junk | refuse loudly |

### 3b. Duration

| seconds | why | canonical |
|---|---|---|
| 0 | **unknown vs measured zero** — the one genuine fork (§ H12) | `0m` (aggregate) / `—` (cell) |
| 30, 59 | sub-minute must not round up to `1m` | `<1m` |
| 60 | `1m` |
| 1591 | 26m31s — seconds truncate | `26m` |
| 3600 | whole hour drops the minutes | `1h` |
| 3661 | `1h 1m` |
| 66180 | 18h 23m — the spec's own example | `18h 23m` |
| negative | never legitimate | `0m` / `—` |

### 3c. Start time

**The requirement first, because the table below is a list of instances and
must not be read as the list.** A start time can be in **any zone**, under
**any daylight-saving convention**, including a convention that **changes after
the recording was made** — governments do this (Mexico abolished DST in 2022,
Egypt reinstated it in 2023, Kazakhstan collapsed to one zone in 2024). So the
property correct code has, and the property each case tests for, is:

> The code depends on the **rule table** (`tzdata` / IANA names), never on a
> remembered offset. A stored `+01:00` says what the clock did once; a stored
> `Europe/London` says what it will do under whatever rules apply when the
> value is next read. An offset cannot be converted back to a zone, so any
> path that keeps only the offset has already lost the answer.

Which means the deepest test in this set is not a date at all: **does the
result survive a `tzdata` update?** If a value's rendering depends on which
version of the rule table was installed when it was *stored*, the design is
wrong regardless of how many of the rows below pass.

The rows are UK-heavy because that is the maintainer's practice and the
corpus; each is an instance of the requirement, not its boundary.

| input | why |
|---|---|
| `2026-05-09T14:23:00+01:00` | BST — the common London case; must stay 13:23 UTC |
| `2026-05-09T14:23:00Z` | explicit UTC |
| `2026-05-09T14:23:00` | naive — must decide *and document* whether this means local or UTC |
| `2026-05-09` | legacy date-only |
| `2026-03-29T01:30:00+00:00` | inside the UK DST spring-forward gap — this wall time does not exist |
| `2026-10-25T01:30:00+01:00` / `+00:00` | the repeated hour — same wall time, two instants |
| midnight / 23:59 | day-boundary rollover for "Today"/"Yesterday" |
| a zone away from the viewer's | a session recorded abroad, reviewed at home |
| `Asia/Kathmandu` (+5:45), `Pacific/Chatham` (+12:45) | non-whole-hour offsets — catches every `hours = offset // 60` assumption |
| `Pacific/Kiritimati` (+14) against `Pacific/Pago_Pago` (−11) | 25 hours apart — two different calendar dates are "today" at once, so "Today" needs a zone to mean anything |
| `Asia/Tokyo`, `Asia/Kolkata` | no DST at all — a rule that fires "in summer" must not fire here |
| `Australia/Lord_Howe` | a **30-minute** DST shift |
| `America/Mexico_City`, a 2021 recording | a zone whose DST rule was **abolished after the recording** — the stored instant must not move when the rules do |
| a future rule change, unknown today | the case the joke is about, and the one the IANA-name design handles for free: the rule arrives in `tzdata`, the stored name resolves under it, nothing is re-computed by us |

The scenario set for multi-zone studies and a researcher who moves between
sessions is in `design-timezones.md` § 3; the schema rule that follows from all
of this — store the IANA name, never derive it from an offset — is § 5.3
there.

---

## 3b. Conventions by surface — and the crossings between them

The question this section answers: *do filenames, the webview and the Mac app
follow the same rules, and is the join between Swift and the webview invisible?*

| datum | filename | webview (SPA) | Swift native | CLI | markdown / static | API wire |
|---|---|---|---|---|---|---|
| **position** | `03m45` · `0h03m45` | `05:30` · `1:12:45` | — *(none; Mac positions go through the SPA)* | — | `05:30` · `1:12:45` | float seconds |
| **duration** | — | `26m` · `1h 3m` · `—` at 0 | `26m` · `1h 3m` · `0m` at 0 | `3m 41s` · `0.1s` | `26m` · `1h 3m` (one helper since T0-4) | float + `duration_human` string |
| **start time** | — | `Today, 14:23` **(viewer-local)** | `Today, 14:23` **(viewer-local)** | — | `Today at 16:59` **(UTC)** | **naive** ISO, no offset |

**Position — different notation, same rule.** Filenames use `03m45` rather than
`05:30` because a colon is hostile in a filename and sorts badly in a listing;
letters keep the field order legible in a Finder window. Both spellings elide the
hour by the same rule (§ 3a). This is a deliberate notation fork over a shared
convention, not drift. The only time that reaches a filename at all is the clip
timecode — no dates, no durations.

**Duration — aligned, with one documented fork.** SPA and Swift render
identically; they differ only at zero, where the SPA shows an em-dash (a per-row
cell, where 0 means *unknown* — 8% of the corpus) and Swift shows `0m` (an
aggregate subtitle, where 0 is a real total). That fork is written down in
`format.ts` and is correct. The CLI's `3m 41s` is a different context
(sub-second stage timing), not the same format.

**Start time — the surfaces agree; the wire is where it goes wrong.**
`SessionsFinderDate.swift` is an explicit, heavily-reasoned mirror of the
TypeScript contract — same `en*→en_GB` mapping, same forced 24-hour clock, same
`DateComponents`-based Today/Yesterday, same em-dash for absent. **The Swift ⇄
webview join is genuinely invisible here, by construction and on purpose.**

### The crossings, and what each loses

| crossing | what happens | verdict |
|---|---|---|
| Python → **SQLite** | `session_date` is `Mapped[datetime]` with no `timezone=True`. Measured: stored `2026-05-09T13:23:00+00:00`, read back `2026-05-09T13:23:00`, `tzinfo=None`. | **the offset is destroyed here** |
| SQLite → API | `sess.session_date.isoformat()` (`routes/sessions.py:205`) emits the naive string | faithful to what it was given |
| API → TypeScript | `new Date("…13:23:00")` — no offset, so parsed as **local** | faithful; wrong input |
| API → Swift | naive parsed as local, *deliberately*, to match JS | faithful; wrong input |
| Python → markdown | no crossing — renders the aware value directly | the **only** surface showing UTC |

So a 14:23 BST recording reads **13:23** in the SPA, **13:23** in the Mac
popover, and **13:23** in the markdown. The three agree on the number and all
three are an hour off the researcher's wall clock. The two surfaces the user
would compare are consistent with each other; the information was gone one layer
below both of them.

That reframes the "different conventions in different places" worry: the
**conventions** are in good order, deliberately mirrored and documented. The
**data** loses its timezone at a DB column definition, and every faithful
renderer downstream then renders the wrong instant faithfully.

### One more Swift-internal duplicate

`ProjectRow.formatBareDate` is a *fourth* rendering — a progressive-coarsening
relative date ("Just now", "Today", then absolute) for **project last-activity**,
which is a different datum from session start and reasonably has its own shape.
It is duplicated verbatim in `SidebarSubtitleText.swift:193`, which says so in a
comment. Two copies in one language is the condition the register closed
`timecode` to avoid.

## 4. Holes

_**Status, 12 Sep 2026 — Tier 0 and Tier 1 landed** (`git log -S parse_header_datetime`).
Fixed: H1, H2 (declared), H3 (closed by measurement), H4, H5, H7, H8, H11, and
H13 below. Still open: H9's DB-column half, H10's pins (`finder_date`, zero cases) and H12's assertion (the zero fork is catalogued in `divergences`, but no test reads that array), which
belong to Tier 2 (`design-timezones.md` § 5). H6 withdrawn._

### H1 — ✅ FIXED — Two `parse_timecode` implementations, and the tests guard the dead one

`bristlenose/utils/timecodes.py:84` (regex, canonical, used by every production
call site) and `bristlenose/models.py:441` (split-on-colon, **zero production
callers**). They are not the same object and disagree on 5 of 14 probed inputs:

| input | utils (production) | models (tested) |
|---|---|---|
| `100:00:00` | ValueError | 360000 |
| `00:01:23,456` (SRT) | 83.456 | ValueError |
| `00:01:23 extra` | 83.0 | ValueError |
| `5:3` | ValueError | 303 |
| `1:2:3` | ValueError | 3723 |

`tests/test_models.py` imports `parse_timecode` **from `bristlenose.models`**, so
the format→parse round-trip test — the one the register calls the guard for a
Class-R format — exercises the implementation nothing ships. Changing the
canonical parser would not redden it.

### H2 — ✅ DECLARED — `format_timecode` output above 99 h cannot be parsed back

_Review Finding 38, answered: "declared" is honest and "closed" would not be.
The formatter still emits a string its own parser refuses above 99 h; the
`# Duration:` header reader turns that into a silent `0.0`. It is a residue of
the H1/H2 class, pinned as a limit because nothing a research session produces
reaches it (§ 2) — not because the asymmetry is gone._

`format_timecode(360000)` → `100:00:00`; the canonical parser's hour group is
`\d{1,2}` and refuses it. Far outside the realistic range, so the *impact* is
nil — the finding is that **format and parse have different domains and nothing
declares either**.

### H3 — ✅ CLOSED BY MEASUREMENT — Unpadded third-party timecodes are dropped silently

`1:2:3` is refused by the canonical parser, and the docx/subtitle regexes
(`s04_parse_docx.py:22-46`) require `\d{2}` for minutes and seconds, so such a
line never reaches the parser — it simply does not match and is skipped, with no
error and no count. A short transcript is the only symptom. This is the same
shape as the `\d{1,2}` hour incident already in CLAUDE.md, one field to the
right.

**Measured 12 Sep 2026:** 344 real transcript-like files on disk
(`.txt/.md/.srt/.vtt/.docx`), **zero** unpadded timecodes. The seven regex hits
were Stephanus citations in Plato texts (`Republic 3:4`). No export produces
this shape, so refusal is the contract and is pinned
(`TestUnpaddedIsRefused`).

### H4 — ✅ FIXED — The canonical parser accepts trailing garbage

`parse_timecode("00:01:23 extra")` → `83.0`. It uses `re.match`, not
`re.fullmatch`, so a malformed line yields a plausible number instead of an
error. Silent-wrong beats loud-wrong everywhere else in this codebase.

### H5 — ✅ FIXED — `miro_board.fmt_timecode` never rolls minutes into hours, and breaks at 100 minutes

`bristlenose/miro_board.py:125` is `f"{total // 60}:{total % 60:02d}"`. Measured:

| seconds | emits | parses back |
|---|---|---|
| 5658 (94.3 min) | `94:18` | 5658 ✓ |
| 5982 (99.7 min) | `99:42` | 5982 ✓ |
| **6000 (100 min)** | `100:00` | **ValueError** |
| 36000 (10 h) | `600:00` | **ValueError** |

The corpus's longest session is 99.7 minutes — **eighteen seconds** from the
cliff. **No test references it.**

Read against the elide-the-hour convention above, this is not merely a third
rendering — it is the one implementation that follows **neither** rule. The
convention has two halves: below an hour, omit the hour field; at or above one,
show it. `fmt_timecode` does the first and then, instead of the second,
**overflows the minute field past 60** — an hour renders `60:00`, three hours
`180:00`, ten hours `600:00`. No human writes a timecode that way, which is the
same standard the convention is derived from. And because the minute field is
`\d{1,2}` in the parser, the overflow is precisely what makes the output
unreadable at 100 minutes: the two faults are one fault.

So the fix is not "add hours to the Miro label" — it is that this is a fourth
copy of a format the register closed to one per language in August.

### H6 — WITHDRAWN: `format_clip_timecode`'s hour eliding is correct

*Raised, then disproved on 12 Sep 2026. Kept because the reasoning that made it
look like a defect is the reasoning a future auditor will repeat.*

The claim was that `format_clip_timecode(use_hours=False)` discards the hour —
`0s` and `3600s` both render `00m00` — and that the function is "only safe
because one caller remembers" to pass the flag. Both halves were wrong.

It is not a latent default. `clips_export.py:370-371` derives
`max_duration = max(session_durations.values())` and sets
`use_hours = max_duration >= 3600`. A clip's start is bounded by its own
session's duration, which is ≤ `max_duration`. So when the flag is `False`, **no
clip start can reach an hour**, and eliding a field that is provably zero is
lossless. The collision is impossible by construction, not avoided by vigilance.

And the behaviour is specified, not incidental — `design-export-clips.md` § 85-86
states the per-export switch, with a QA step for it.

**Residual, and it is narrow.** The bound rests on `duration_seconds` being
accurate. A session with an unknown duration (`0`) whose quotes run past an hour
would break it. Measured across the local corpus: **98 sessions, 4 with a zero
time axis, none with a quote past an hour** — theoretical, unobserved. Worth
knowing only if duration probing ever becomes less reliable.

**What this corrects in the audit's method:** "the default argument is the unsafe
value" is a code smell, not a finding. Whether it is a defect depends on what
bounds the inputs, and that lived one file away in the caller.

### H7 — ✅ FIXED — Four Python duration formatters, three formats, and the obvious home holds the wrong one

*Corrected 12 Sep 2026: the first draft called `utils.format_duration_human`
"dead, 0 callers". That was a grep artefact — the search excluded `dashboard.py`
to skip the route module and thereby also hid `stages/s12_render/dashboard.py`,
a different file with the same basename. It has one live caller.*

| implementation | 0 | 30 | 3600 | 66180 |
|---|---|---|---|---|
| `dashboard._format_duration_human` **(canonical)** | `0m` | `<1m` | `1h` | `18h 23m` |
| `utils/timecodes.py:format_duration_human` **(1 caller: the static render)** | `0 min` | **`1 min`** | `1 h 0 min` | `18 h 23 min` |
| `pipeline._format_duration` | `0.0s` | `30.0s` | `60m 00s` | `1103m 00s` |
| `dev._format_duration` | `—` | `00:30` | `1:00:00` | `18:23:00` |

_The table is the 12 Sep pre-fix measurement, kept as the baseline. Post-fix: `utils/timecodes.py:format_duration_human` is the one canonical implementation and renders the first row's column; `routes/dashboard.py` delegates to it; `dev.py` renders an em-dash at zero and the canonical shape otherwise; `pipeline._format_duration` rolls into hours (`1h 03m 41s`) and remains a deliberate sub-second exception._

Three things here:

1. The canonical implementation lives in a **route module**, while the module
   named `timecodes.py` holds a sibling with a different format. A new caller
   reaching for "the duration formatter" finds the wrong one first — and one
   already did: `s12_render/dashboard.py:503` renders the static report's total
   session time as `18 h 23 min` where the SPA dashboard shows `18h 23m` for the
   same number. A live fork between the two renders of one stat — closed 12 Sep (T0-4).
2. That sibling renders a 30-second span as **`1 min`** — asserting a minute that
   did not elapse, where canonical says `<1m`.
3. `dev._format_duration` renders a duration in **timecode shape**
   (`18:23:00`) — precisely the conflation the register records as fixed on
   22 Aug 2026. Dev-only surface, but it is the documented anti-pattern, live.

`pipeline._format_duration` is a legitimately different context (sub-second CLI
stage timing), though its minutes also overflow (`1103m 00s`).

### H8 — ✅ FIXED — Start time is *relabelled*, not converted — and two readers of the same header disagree

_Correction from review (Finding 34): the "stored an hour late" harm was a
**reasoned hazard, not a measured incident**. Every Bristlenose writer emits an
aware `isoformat()` with `+00:00`, so the overwrite could only ever bite a
hand-edited or third-party header. The live effect of the fix is on the
importer's path into the database, where an offset-bearing header now lands as
the correct instant._

`pipeline.py` (then `:2861`; the read is at `:2904` now) read the transcript `# Date:` header as:

```python
session_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
```

`.replace(tzinfo=…)` overwrites the offset instead of converting. Measured on
`2026-05-09T14:23:00+01:00`: stored as **14:23 UTC**, correct answer **13:23
UTC** — a one-hour error for every BST recording.

`server/importer.py:83` reads the *same header* and gets it right, relabelling
only when the value is naive. So the CLI resume path and the server import path
can derive **different instants from one file**.

### H9 — REFRAMED: the timezone is destroyed at the DB column, not at a surface

*Raised as "Python renders UTC, TypeScript renders local"; that is true but it is
the symptom, and naming it as a rendering fork points the fix at the wrong layer.*

`session_date` is declared `Mapped[datetime | None] = mapped_column(default=None)`
— no `DateTime(timezone=True)`. Measured round-trip through SQLAlchemy + SQLite:
an aware `13:23+00:00` goes in and a **naive** `13:23` comes out. The API then
emits that naive string, and both JS and Swift parse a naive ISO string as local
time.

Consequence: a 14:23 BST recording renders **13:23 everywhere** — SPA, Mac
popover and markdown all agree, and all three are off by the viewer's UTC offset.
Python's markdown differs only in separator (`Today at 16:59` vs `Today, 16:59`),
which `SessionsFinderDate.swift` already records as a cosmetic, accepted fork.

**Upstream of all of it, and already tracked:** `SessionsFinderDate.swift`'s own
KNOWN-WRONG note says the value being formatted is the source file's
`st_birthtime` — file *creation* time, not session start. For a save-at-close
writer that is the session's **end**; a transcript-only import fabricates
midnight from a date-only header. So even with the timezone fixed, the datum is
not reliably the session's start time. Worth reading before anyone "fixes" the
timezone and declares start times correct.

### H10 — `finder_date` has three implementations and **zero** pinned cases

`shared-format-contract.json` lists Python, TypeScript and Swift implementations
for `finder_date` and pins **no cases at all** (`timecode` had 15, now 21;
`duration_human` has 9). The register describes it as "aligned by pair, one
deliberate fork" — that is an assertion nothing tests, and H9 is the fork it did
not know about.

### H11 — ✅ FIXED — Naive `datetime.now()` at four render sites

`s12_render_output.py:81` and `:178`, `s12_render/report.py:164`,
`utils/markdown.py:493`. Mixed with an aware `session_date`. It does **not**
crash (measured — `format_finder_date` compares calendar dates rather than
subtracting), but it is the mechanism behind H9 and would raise the moment
anyone writes a subtraction.

### H12 — Duration zero means two things, and the contract pins neither

TypeScript returns an em-dash for `seconds <= 0` (unknown); Python and Swift
return `0m` (measured zero). This is **deliberate and documented** in
`format.ts`. The zero case is now catalogued in the entry's `divergences` with both
outputs — but no test reads `divergences` (zero grep hits in either contract test), so
it is documented, not asserted, and nothing mechanical stops a future edit collapsing the fork.

### H13 — ✅ FIXED — TypeScript `formatTimecode` did not clamp a negative

Found by the fixture, as designed: adding `[-1, "00:00"]` to the `timecode`
contract made vitest red. Python clamps via `max(0, int(seconds))`;
`format.ts` did not, and rendered `-1` as `"-1:-1"` and `-61` as `"-2:-1"`.
A one-line clamp; the case stays in the fixture so it cannot come back.

---

## 5. Test coverage

| format | pinned cases | ceiling | gap |
|---|---|---|---|
| `timecode` | 21 (was 15) | 36000 s (10 h) | closed 12 Sep: `3599.9`, `5999`, `6000`, `10800`, `35999` and `-1` pinned (T0-7, H13) |
| `duration_human` | 9 | 66180 s | zero catalogued in `divergences`, **unasserted** (H12); negative pinned in pytest |
| `finder_date` | **0** | — | three implementations, nothing pinned (H10) |

Untested entirely: `format_timecode_ms` (zero callers repo-wide — an H1-shaped dead sibling
in the canonical module) and every timezone behaviour in § 3c. The others this list named
on 12 Sep — `fmt_timecode`, `format_duration_human`, `dev._format_duration`,
`pipeline._format_duration` — are now pinned in `tests/test_time_tier0.py`.

Was pointed at the wrong object: `tests/test_models.py`'s `parse_timecode`
round-trip (H1) — repointed to the canonical parser (`tests/test_models.py:8`).

### Landed guard-rails (12 Sep 2026)

Four mechanical guards now share one framing — *refuse or bound at the edge, log what was refused, never absorb*:

- **Domain refusal** — `parse_timecode` `fullmatch`es and refuses `>99 h`, trailing text and unpadded fields (`utils/timecodes.py`; `TestParserRefusesTrailingText`, `TestUnpaddedIsRefused`, `test_domain_ceiling_is_declared_not_implicit`).
- **A 256-char bound at the dict layer** on every container string (`utils/audio.py:_tags`) — deliberately not a Pydantic `max_length`, which *rejects* and would re-create the whole-scan abort the review found.
- **The tag allowlist as a privacy boundary** — `time_meta_from_ffprobe` reads named keys only; GPS is never retained (`test_gps_is_excluded_by_the_allowlist`).
- **Three-way probe degradation** — tool didn't run / ffprobe refused (with its stderr) / a tag didn't parse (duration kept, meta `None`), each with its own log line (`utils/audio.py:probe_media`, `TestProbeMediaWiring`).

Worth noting what *is* solid: `timecode` and `duration_human` are genuinely
aligned across the three languages within their pinned ranges, asserted from both
pytest and vitest, with `DurationFormatTests.swift` mirroring. The failures above
are all **outside** the pinned range, or in implementations the register never
enrolled.

---

## 6. What this audit did not check

- **Video/player seek.** Whether the SPA player's seek target agrees with the
  quote timecode was not exercised.
- **The `.srt`/`.vtt` writers** (as opposed to readers).
- **Swift's own date parsing** (`TeamsSource.parseISO`, `TeamsRecordingName.date`)
  beyond confirming it exists — cloud-import paths, separate surface.
- ~~Whether any real third-party export emits unpadded seconds~~ — measured later
  the same day: 344 files, zero (H3).
- **DST edge behaviour end-to-end.** § 3c lists the cases; nothing in the tree
  was run against them.

---

## 7. Plan — Tier 0 and Tier 1

_The sequencing that matters: **Tier 0 needs no product decision and does not
touch the start-time work.** It is worth doing regardless of anything decided in
`design-timezones.md`. Tier 2 (start time, timezones) lives there, § 5._

Every item states the file, the change, the **proof test** — written first and
shown red — the behaviour that changes, and the risk. Effort is a guess; the
proof step is not optional, because this area's existing tests are pointed at
the wrong code (H1).

### Tier 0 — independent, cheap, zone-free

**T0-1 ✅ · Retire `models.parse_timecode`; repoint the round-trip test. Do this
first** — it is what makes the rest of the tier verifiable.
- `bristlenose/models.py:441-449`: delete. No production caller (H1); every
  stage imports from `utils.timecodes`.
- `tests/test_models.py:7`: import `parse_timecode` from
  `bristlenose.utils.timecodes` (keep `format_timecode` from `models`, which
  re-exports it).
- Proof: after the change `from bristlenose.models import parse_timecode`
  raises `ImportError`; `test_parse_timecode_round_trip_*` now exercise the
  canonical parser and still pass (verified: every input they use round-trips
  on it).
- Add: `pytest.raises(ValueError)` for `parse_timecode("100:00:00")` — this
  *declares* the domain ceiling (H2) instead of leaving it implicit.
- Risk: none in-tree. An out-of-tree script importing from `models` breaks
  loudly, which is the right way to break.

**T0-2 ✅ · `parse_timecode` uses `fullmatch`.**
- `bristlenose/utils/timecodes.py:84-105`: `.match` → `.fullmatch` on both
  patterns, after the existing `strip()`.
- Every caller passes an isolated token, verified: s03 passes
  `caption.start`/`.end`; s04 passes regex groups; `pipeline.py:2867/2892` pass
  a stripped header value / regex group; s08/s09 pass LLM fields and already
  catch `ValueError` into the guard's `*_timecode_unparseable` log line.
- Proof: `parse_timecode("00:01:23 extra")` returns `83.0` today → test
  asserts it raises. Red before, green after.
- Behaviour change: an LLM answer with trailing text goes from silently-`83`
  to logged-unparseable-and-zeroed. That is the intent — the guard exists to say
  so. The measured terra wire strings were clean `HH:MM:SS`, so expected rate is
  ~0.
- Risk: low. If a real transcript format turns out to carry trailing text on the
  timestamp token, the fix is in *that* parser's regex, not here.

**T0-3 ✅ · `miro_board.fmt_timecode` delegates to `format_timecode`.**
- `bristlenose/miro_board.py:129-133`: body becomes `return format_timecode(seconds)`.
  Keep the name — `miro_export.py:27` imports it.
- Proof: `fmt_timecode(6000) == "1:40:00"` and `parse_timecode(fmt_timecode(6000)) == 6000`.
  Red before (`"100:00"` → `ValueError`), green after.
- Behaviour change on Miro boards: `90:00` → `1:30:00` above an hour; `5:30` →
  `05:30` below (minute padding, the house rule). Cosmetic, and the second is
  what every other surface already shows.
- Risk: `miro_export._parse_timecode` must read the new shape — it does
  (`h:mm:ss` and zero-padded `mm:ss` both parse; verified by reading it). While
  there: that parser returns `0.0` on *any* failure including fractional
  seconds. Replace with the canonical `parse_timecode` inside the existing
  `try` — same tier, same file, five lines.

**T0-4 ✅ · One `format_duration_human`, in `utils/timecodes.py`, canonical.**
- Move the body of `server/routes/dashboard._format_duration_human` into
  `utils/timecodes.py:format_duration_human` (replacing the `"1 min"` variant).
  Make the route function a one-line delegate. `s12_render/dashboard.py:32`
  needs no change — it already imports the utils name and now gets the canonical
  shape.
- Update the register's Python pointer (`design-shared-formats.md` table and
  the fixture's `implementations.python`) to the utils path. The contract tests
  keep passing: the route's output is unchanged.
- Proof: `format_duration_human(30) == "<1m"` (today `"1 min"`),
  `format_duration_human(3600) == "1h"` (today `"1 h 0 min"`). The fixture's nine
  cases apply directly.
- Behaviour change: the static report's total goes `18 h 23 min` → `18h 23m`,
  matching the SPA. The sealed-byproduct rule says design changes go to the SPA
  only; this *removes* a divergence rather than adding a design, and is the
  smaller change. Flag it in the commit.
- Risk: a test pinning the static dashboard HTML's `" min"` would be pinning
  the fork. Checked — none does. The static total changes freely.

**T0-5 ✅ · `dev._format_duration` uses the canonical helper.**
- `server/routes/dev.py:79-88`: `return "\u2014" if seconds <= 0 else format_duration_human(seconds)`.
  Em-dash stays — it is a per-row cell, the SPA convention.
- Proof: `_format_duration(66180) == "18h 23m"` (today `"18:23:00"`).
- Depends on T0-4 for the import. Dev-only surface; lowest stakes in the tier.

**T0-6 ✅ · `pipeline._format_duration` overflows minutes** (`66180` → `1103m 00s`).
CLI stage timing, realistically seconds-to-minutes; a long transcription can
cross an hour. Fix is `divmod` into `h`/`m`/`s`. Landed the same day
(`pipeline.py:140-143`, `test_cli_stage_timer_rolls_into_hours`).

**T0-7 ✅ (timecode cases + H13; `finder_date` pins deferred to Tier 2, see below) · Extend the contract fixture** (`tests/fixtures/shared-format-contract.json`).
- `timecode.cases`, add: `[3599.9, "59:59"]` (truncation at the switch — must
  not round to `1:00:00`), `[5999, "1:39:59"]`, `[6000, "1:40:00"]`,
  `[10800, "3:00:00"]`, `[35999, "9:59:59"]`.
- `timecode.cases`, add `[-1, "00:00"]` — **and vitest will fail, measured.**
  Python clamps (`max(0, int(seconds))`); TypeScript's `formatTimecode` does not:
  `formatTimecode(-1)` → `"-1:-1"`, `formatTimecode(-61)` → `"-2:-1"`. A real,
  currently-unpinned divergence (call it **H13**), and the fix is a one-line
  clamp in `format.ts`. Add the case *before* the clamp so the red run is on
  record.
- `duration_human`: **do not** add `0` to `cases` — TS returns an em-dash there
  on purpose. Add it to the entry's `divergences` with both expected outputs, so
  the fork is pinned in the direction it was decided (H12).
- `finder_date`: pin the **absolute-date branch only**, which is deterministic:
  `"2026-02-10T09:12:00"` → `"10 Feb 2026, 09:12"` (TS and Swift). The relative
  branch needs an injectable `now`, which TS lacks — add a `now` parameter to
  `formatFinderDate` first, or leave that branch catalogued. Record Python's
  `Today at 16:59` separator in `divergences` (H10). Inputs must be **naive**
  strings to match today's wire (`design-timezones.md` § 1).

**T0-8 ✅ · Round-trip property test** — `tests/test_timecode_roundtrip.py`.
- For `s in range(0, 360000, 7)`: `int(parse_timecode(format_timecode(s))) == s`,
  and the same for `format_timecode_prompt`. That is ~51k cases in well under a
  second and covers every field boundary. (`hypothesis` is not a dependency;
  a stride is enough.)
- Assert `parse_timecode(format_timecode(360000))` raises — the declared limit
  from T0-1, now pinned from the formatting side too.
- This is the test that would have caught H1 and H2, and is the one H1
  currently defeats.

### Tier 1 — one measurement or one decision each

**T1-1 ✅ · `# Date:` header reader converts instead of relabelling** (H8).
- `pipeline.py` (`# Date:` read, now `:2904`): replace `.replace(tzinfo=timezone.utc)` with the exact
  logic `server/importer.py:83` already uses — relabel only when
  `dt.tzinfo is None`, otherwise `astimezone(timezone.utc)`. Better: extract that
  four-line function to `utils/timecodes.py` and call it from both readers, so
  the two paths cannot disagree again.
- Proof: `"2026-05-09T14:23:00+01:00"` → `13:23 UTC`. Red before (`14:23`),
  green after. Naive input unchanged.
- The **decision** folded in: a naive header value means UTC, because that is
  what the writer emits (aware `isoformat()` produces an offset; naive only
  appears in legacy files written before the time-of-recording fix, which were
  UTC). State it in the docstring.

**T1-2 ✅ · Unpadded third-party timecodes** (H3) — **measured: zero in 344 files; refusal pinned.**
- One script over every `.docx`/`.srt`/`.vtt`/`.txt` transcript on disk
  (`trial-runs/`, the format corpus): count lines matching an unpadded field
  (`\b\d:\d\b` or `:\d\b` at end of token). Zero in the wild → declare
  refusal the contract, add a test that pins it, close H3. Non-zero → widen the
  s04 regexes and the parser's seconds group to `\d{1,2}`, with the
  offending format named in the commit.
- Do not widen speculatively: a looser regex matches more non-timecode text.

**T1-3 ✅ · Naive `now()` at four render sites** (H11).
- `s12_render_output.py:81,178`, `s12_render/report.py:164`,
  `utils/markdown.py:493`: `datetime.now()` → `datetime.now(timezone.utc)`.
  Removes the latent `TypeError` on any future subtraction against an aware
  `session_date`. It does **not** change what is displayed — the display frame
  is a Tier 2 decision (`design-timezones.md` § 4) and this must not pre-empt it.
- Proof: a test that subtracts `format_finder_date`'s `now` default from an
  aware datetime; raises today, does not after.

### What Tier 0/1 leave alone, deliberately

- `format_timecode_prompt` — correct, tested, and outside the register on
  purpose.
- `format_clip_timecode` — H6 withdrawn; sound by construction.
- The Swift/webview start-time rendering — consistent with each other; the
  defect is upstream (`design-timezones.md` § 1) and belongs to Tier 2.
- `ProjectRow.formatBareDate`'s verbatim copy in `SidebarSubtitleText.swift` —
  a Swift-internal duplicate of a *different* datum (project activity). Fold
  into a Swift tidy-up, not this plan.

### Review pass, 12 Sep 2026 — what it changed

Six agents plus a compose-check and a parsimony pass over Tiers 0–1 and § 5.1
raised 39 findings (`docs/private/reviews/timezones.md`, gitignored). Thirty-
three resolved the same day (`git log -S probe_media`), four parked with
reasons, one superseded, one answered. The ones that changed what this
document said:

- **T1-3 was wrong as first landed.** `datetime.now(timezone.utc)` removed the
  latent `TypeError` and silently moved every "Generated:" stamp and "Today at
  HH:MM" header to UTC — the § 4 display-frame decision, made by accident. The
  grep test written to guard it would have *rejected* the correct fix. Now
  `local_now()` (aware and local) at all four sites, with a behavioural test.
- **The "one reader" claim was one header short**: `# Duration:` still had two.
- **The first version of `parse_iso_lenient` (then a private `_iso_lenient` in `audio.py`) could abort a whole folder scan** on a five-
  character offset — proven end to end with a crafted MOV. Three of the
  obvious fixes interacted destructively as proposed (a `max_length` validator
  rejects and would have re-created the abort; folding the probes under one
  `except` would have cost a file its duration for one bad date tag; a naive
  `creationdate` must never be relabelled UTC). The compose-check caught all
  three before they landed.
- **The tier's own tests could not fail on the defects they named** — four of
  them asserted source *presence*. Replaced by behaviour.

### Deferred from T0-7, deliberately: `finder_date` pins

The absolute-date branch could be pinned today, but the relative branch needs an
injectable `now` that `formatFinderDate` (TS) lacks — an API change on a
function three components call. And any case written now must use a **naive**
input to match the current wire, which Tier 2 § 5.3 changes. Pinning twice is
worse than pinning once after the wire settles. Recorded here so it is not
mistaken for forgotten.
