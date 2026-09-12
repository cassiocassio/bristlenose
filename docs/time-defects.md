# Time in Bristlenose — three data types, their ranges, and an end-to-end audit

_Audited 12 Sep 2026, across Python, TypeScript and Swift. Every claim below was
measured by running the code, not read off it; where something is inferred it
says so. **Diagnosis only — nothing here is fixed.**_

_**Eleven findings stand. H6 was raised and withdrawn** — it is kept in place,
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

| | realistic | design ceiling | absurd |
|---|---|---|---|
| position / duration | 0 – 3 h | **10 h** | > 24 h |

That matters because one live helper breaks at **100 minutes** (§ 4, H5) and the
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
| `1:2:3` | third-party, unpadded | **decide** — currently refused everywhere (§ H3) |
| `90:00` | minutes past 60 | accept (5400) — our own Miro output emits this |
| `100:00:00` | ≥100 h | refuse or accept, but *consistently* (§ H2) |
| `00:01:23 extra` | malformed line | **should refuse** — currently accepted (§ H4) |
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

| input | why |
|---|---|
| `2026-05-09T14:23:00+01:00` | **BST** — the common London case; must stay 13:23 UTC |
| `2026-05-09T14:23:00Z` | explicit UTC |
| `2026-05-09T14:23:00` | naive — must decide *and document* whether this means local or UTC |
| `2026-05-09` | legacy date-only |
| `2026-03-29T01:30:00+00:00` | **inside the UK DST spring-forward gap** |
| `2026-10-25T01:30:00+01:00` / `+00:00` | **the repeated hour** — same wall time, two instants |
| midnight / 23:59 | day-boundary rollover for "Today"/"Yesterday" |
| a time zone away from the viewer's | a session recorded abroad, reviewed at home |

---

## 3b. Conventions by surface — and the crossings between them

The question this section answers: *do filenames, the webview and the Mac app
follow the same rules, and is the join between Swift and the webview invisible?*

| datum | filename | webview (SPA) | Swift native | CLI | markdown / static | API wire |
|---|---|---|---|---|---|---|
| **position** | `03m45` · `0h03m45` | `05:30` · `1:12:45` | — *(none; Mac positions go through the SPA)* | — | `05:30` · `1:12:45` | float seconds |
| **duration** | — | `26m` · `1h 3m` · `—` at 0 | `26m` · `1h 3m` · `0m` at 0 | `3m 41s` · `0.1s` | *(dead helper: `26 min`)* | float + `duration_human` string |
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

### H1 — Two `parse_timecode` implementations, and the tests guard the dead one

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

### H2 — `format_timecode` output above 99 h cannot be parsed back

`format_timecode(360000)` → `100:00:00`; the canonical parser's hour group is
`\d{1,2}` and refuses it. Far outside the realistic range, so the *impact* is
nil — the finding is that **format and parse have different domains and nothing
declares either**.

### H3 — Unpadded third-party timecodes are dropped silently

`1:2:3` is refused by the canonical parser, and the docx/subtitle regexes
(`s04_parse_docx.py:22-46`) require `\d{2}` for minutes and seconds, so such a
line never reaches the parser — it simply does not match and is skipped, with no
error and no count. A short transcript is the only symptom. This is the same
shape as the `\d{1,2}` hour incident already in CLAUDE.md, one field to the
right. **Not verified: whether any real third-party export emits unpadded
seconds.** Worth one pass over the format corpus before deciding.

### H4 — The canonical parser accepts trailing garbage

`parse_timecode("00:01:23 extra")` → `83.0`. It uses `re.match`, not
`re.fullmatch`, so a malformed line yields a plausible number instead of an
error. Silent-wrong beats loud-wrong everywhere else in this codebase.

### H5 — `miro_board.fmt_timecode` never rolls minutes into hours, and breaks at 100 minutes

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

It is not a latent default. `clips_export.py:370` derives
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

### H7 — Four Python duration formatters, three formats, and the obvious home holds a dead one

| implementation | 0 | 30 | 3600 | 66180 |
|---|---|---|---|---|
| `dashboard._format_duration_human` **(canonical)** | `0m` | `<1m` | `1h` | `18h 23m` |
| `utils/timecodes.py:format_duration_human` **(0 callers)** | `0 min` | **`1 min`** | `1 h 0 min` | `18 h 23 min` |
| `pipeline._format_duration` | `0.0s` | `30.0s` | `60m 00s` | `1103m 00s` |
| `dev._format_duration` | `—` | `00:30` | `1:00:00` | `18:23:00` |

Three things here:

1. The canonical implementation lives in a **route module**, while the module
   named `timecodes.py` holds a dead sibling with a different format. A new
   caller reaching for "the duration formatter" finds the wrong one first.
2. That dead sibling renders a 30-second span as **`1 min`** — asserting a minute
   that did not elapse, where canonical says `<1m`.
3. `dev._format_duration` renders a duration in **timecode shape**
   (`18:23:00`) — precisely the conflation the register records as fixed on
   22 Aug 2026. Dev-only surface, but it is the documented anti-pattern, live.

`pipeline._format_duration` is a legitimately different context (sub-second CLI
stage timing), though its minutes also overflow (`1103m 00s`).

### H8 — Start time is *relabelled*, not converted — and two readers of the same header disagree

`pipeline.py:2861` reads the transcript `# Date:` header as:

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
for `finder_date` and pins **no cases at all** (`timecode` has 15,
`duration_human` has 9). The register describes it as "aligned by pair, one
deliberate fork" — that is an assertion nothing tests, and H9 is the fork it did
not know about.

### H11 — Naive `datetime.now()` at four render sites

`s12_render_output.py:81` and `:178`, `s12_render/report.py:164`,
`utils/markdown.py:493`. Mixed with an aware `session_date`. It does **not**
crash (measured — `format_finder_date` compares calendar dates rather than
subtracting), but it is the mechanism behind H9 and would raise the moment
anyone writes a subtraction.

### H12 — Duration zero means two things, and the contract pins neither

TypeScript returns an em-dash for `seconds <= 0` (unknown); Python and Swift
return `0m` (measured zero). This is **deliberate and documented** in
`format.ts`. But `duration_human` has no zero case in the contract, so nothing
stops a future edit collapsing the fork in either direction.

---

## 5. Test coverage

| format | pinned cases | ceiling | gap |
|---|---|---|---|
| `timecode` | 15 | **3930 s (65 min)** | nothing at the 3 h realistic max, nothing at either break (H2, H5) |
| `duration_human` | 9 | 66180 s | **no zero case** (H12), no negative |
| `finder_date` | **0** | — | three implementations, nothing pinned (H10) |

Untested entirely: `miro_board.fmt_timecode`, `utils.format_duration_human`,
`format_timecode_ms`, `dev._format_duration`, `pipeline._format_duration`, and
every timezone behaviour in § 3c.

Tested but pointed at the wrong object: `tests/test_models.py`'s
`parse_timecode` round-trip (H1).

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
- **Whether any real third-party export emits unpadded seconds** (H3's live
  exposure, as opposed to the parser's refusal, which is measured).
- **DST edge behaviour end-to-end.** § 3c lists the cases; nothing in the tree
  was run against them.
