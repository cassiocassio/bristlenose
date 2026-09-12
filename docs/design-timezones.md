# Timezones — what is broken, what is unknowable, and what an audit would have to cover

_Written 12 Sep 2026, from the time audit (`docs/time-defects.md`). **Not a beta
concern** — recorded now because the context was in hand and re-deriving it is
expensive. Every claim marked MEASURED was produced by running the code._

---

## 0. The good news first, because it bounds the work

Bristlenose handles three time data types (`time-defects.md` § 1), and **only one
of them has a timezone at all**:

| datum | has a zone? | why |
|---|---|---|
| **position** (timecode) | no | an offset within a recording — `05:30` means the same thing everywhere |
| **duration** | no | a span — 52 minutes is 52 minutes in any zone |
| **start time** | **yes** | a wall-clock instant, and the only one that needs a zone to mean anything |

So the timezone problem is exactly one third of the time problem, and the two
thirds that are zone-free are also the two the product leans on hardest — quote
deep links, clip boundaries, session lengths. **Nothing in the analysis pipeline
depends on knowing a timezone.** That is why this can wait.

---

## 1. The single most important fact

**The original timezone is not recoverable from anything we currently store.**

MEASURED: `session_date` is declared `Mapped[datetime | None] = mapped_column(default=None)`
in `server/models.py:220` — no `DateTime(timezone=True)`. A UTC-aware
`2026-05-09T13:23:00+00:00` goes into SQLite and a naive `2026-05-09T13:23:00`
comes out. The API emits that naive string (`routes/sessions.py:205`), and both
`new Date()` and Swift's parser read a naive ISO string as **local**.

Two consequences, and the second is the one that matters for planning:

1. A 14:23 BST recording renders **13:23** in the SPA, the Mac popover and the
   markdown. All three agree with each other; all three are off by the viewer's
   offset.
2. **No conversion can fix historical data.** There is no field that says what
   zone the session was recorded in, and the naive value cannot be distinguished
   from a correct local one. Any fix therefore has two separate halves: *start
   capturing the zone* (possible) and *correct what is already on disk*
   (impossible — the best available answer is to label it unknown).

That asymmetry should shape the work. It is not a bug fix; it is a schema
addition plus an honesty problem about existing projects.

---

## 2. What is wrong today

Each of these is in `time-defects.md` with its evidence; this is the timezone
slice.

**T1 — The offset is destroyed at the DB column.** MEASURED, § 1 above. The root
cause; everything downstream is a faithful renderer of a lossy value.

**T2 — `.replace(tzinfo=utc)` relabels instead of converting.** MEASURED.
`pipeline.py:2861` reads the transcript `# Date:` header as
`datetime.fromisoformat(s).replace(tzinfo=timezone.utc)`, which **overwrites** an
offset rather than converting it: `14:23+01:00` is stored as `14:23 UTC` when the
instant is `13:23 UTC`. `server/importer.py:83` reads the *same header* correctly
(relabels only when naive). So the CLI resume path and the server import path can
derive different instants from one file.

**T3 — The value is not the session's start time in the first place.** From
`SessionsFinderDate.swift`'s own KNOWN-WRONG note, which outranks everything
above: `session_date` is the source file's `st_birthtime`, taken raw —
MEASURED, `s01_ingest.py:461` is `min(f.created_at for f in group_files)` and
**nothing anywhere subtracts the duration**. For a save-at-close writer that is
the session's **end**, so the stored value is late by a whole duration.

See § 2b — this is more tractable than the note implies, and the correction the
note rules out is right for the commonest case.

**T4 — Transcript-only imports fabricate midnight.** A bare `YYYY-MM-DD` header
yields 00:00, which renders plausibly and is indistinguishable from a real
midnight session.

**T5 — Naive `now()` at four render sites.** `s12_render_output.py:81` and
`:178`, `s12_render/report.py:164`, `utils/markdown.py:493`. Does not crash
(MEASURED) because `format_finder_date` compares calendar dates rather than
subtracting, but it is a latent `TypeError` the moment anyone writes a
subtraction, and it is why markdown renders UTC.

**T6 — `finder_date` has three implementations and zero pinned cases** in
`tests/fixtures/shared-format-contract.json`, where `timecode` has 15 and
`duration_human` has 9. Nothing mechanical would notice any of the above.

## 2·5. Where a real start time could come from — a signal hierarchy

The KNOWN-WRONG note says `birthtime − duration` "is not a general correction",
which is true and was read as "so there is nothing to do". There is quite a lot
to do; the signals just have to be ranked and the weakest one labelled rather
than trusted.

**1. The cloud API's meeting start.** Authoritative and zone-qualified. Already
available on the Teams/Drive import paths. Nothing else competes with it.

**2. Container metadata — the best local signal, and we read none of it.**
MEASURED across the format-torture corpus (`trial-runs/folder-of-horrors`, 59
files) plus real recordings on this machine. `utils/audio.py` already shells out
to ffprobe for duration, so reading more tags costs nothing.

**(a) `com.apple.quicktime.creationdate` — the one field that answers the whole
question.** An iPhone MOV carries *both*:

```
com.apple.quicktime.creationdate   2020-06-21T13:34:08+0100    <- local time WITH OFFSET
creation_time                      2020-06-21T12:34:08Z        <- the same instant, UTC
```

The Apple tag is strictly more informative than anything else available: it gives
the wall clock the participant and researcher actually saw **and** the zone they
were in. That is the datum § 4 is asking about, written into the file by the
recorder. `creation_time` alone can only ever reconstruct a UTC instant; it can
never tell you it was 13:34 in the room.

**(b) `creation_time` is genuinely UTC — verified, not assumed.** Devices
mislabelling local time as `Z` is a common wart, so it was checked against a
BST-era file: `small2.mov` carries `2026-07-21T07:56:11Z` with a local birthtime
of `08:56:11` — exactly one hour apart, in July. The `Z` is honest.

**(c) It survives everything the filesystem does not.** `CR_In0a.m4a` carries
`2019-05-20T21:13:50Z` while its birthtime is `2026-04-06` — the container kept
the true recording time across seven years and a copy. This is exactly the case
(downloads, copies, the documented *download, rename, sometimes trim, then drop*
workflow) where birthtime is worthless.

**(d) Filename and container corroborate — or disagree by hours.** Two measured
cases, and the contrast is the finding:

| file | filename says | container says | verdict |
|---|---|---|---|
| `Meeting with Martin Storey-20260719_142007UTC-…mp4` | `20260719_142007UTC` | `2026-07-19T14:20:08Z` | **agree within 1s** — mutual corroboration |
| `System Audio 20220308 1316.mp4` | `20220308 1316` | `2022-03-08T17:16:30Z` | **4 hours apart** |

Nothing in either file says which is right. A resolver therefore needs a
precedence rule *and* a way to report disagreement, not just a best-effort pick.

**(e) Coverage is the catch.** Only **7 of 59** corpus files carry any
time-ish tag. That base rate is biased — 18 of them are ffmpeg-synthesised
(`encoder: Lavf…`), and ffmpeg drops the tag unless told to preserve it, which is
also why the FOSSDA `.mp4`s carry nothing. The pattern that matters: **recorder-
written files carry it, transcoded ones do not.** So this is a high-quality,
partial signal — it must degrade to § 3 and § 4, never be assumed present.

**(f) What else is in there, and one caution.** The same iPhone file carries
`com.apple.quicktime.location.ISO6709` (`+51.5214-000.0933`), from which a zone
could be derived when no offset is present. **That is participant location data**
and lands squarely in the consent-gradient governance
(`docs/methodology/consent-gradient.md`) — reading it is a deliberate decision,
not a free win, and it must not reach an export. Recorded here so the option is
known and its cost is known with it.

Also present: `com.apple.quicktime.make` / `.model` / `.software` (which would
*identify the writer class* — the thing § 4 needs to know whether to subtract the
duration), and on `.dv`, an SMPTE `timecode` track (`00:00:00:00`) — a tape
position, a fourth time concept distinct from all three in § 0.

**(g) Matroska carries the same datum, and ffprobe normalises it.** MEASURED:
an `.mkv` written with a `creation_time` comes back from ffprobe under **the same
`creation_time` key** as MP4/MOV — Matroska's `DateUTC` element is surfaced
identically. So one read path covers both container families; no per-format
branching is needed.

What that does *not* settle, and is still **UNMEASURED**: whether a real browser
or OBS capture populates it. Both `.mkv`/`.webm` files in the corpus are
ffmpeg-synthesised, so they carry nothing. The read path is proven; the
write-side coverage in the wild is not. One real capture would answer it.

**Bristlenose reads none of this today.** MEASURED: the only ffprobe call sites
are `utils/audio.py`'s duration probe and a `stream=codec_type` query;
`_get_creation_time` is pure `os.stat`.

**3. The filename.** Zoom, Teams and macOS Screen Recording all write the start
time into the name — and **Python already parses these patterns and then
discards the timestamp**. `_normalise_stem` (`s01_ingest.py:~400`) strips the
date/time *in order to group* files into sessions (`_TEAMS_SUFFIX_RE`,
`_ZOOM_CLOUD_TAIL_RE`, `_ZOOM_LOCAL_DIR_RE`, `_GMEET_TAIL_RE`). The best
available local signal is recognised, used for matching, and thrown away.

Swift does the opposite and does it well: `TeamsRecordingName` keeps the parsed
timestamp but sets `startedAtUTC = nil` unless the filename is **zone-qualified**
— *"the digits are somebody's local wall clock and we do not know whose, so there
is no honest Date to return"*. That is the discipline the whole area needs, and
it already exists in the tree.

**4. `birthtime − duration`, for save-at-close writers.** MEASURED against
filename ground truth on real macOS Screen Recordings:

| recording | duration | `birthtime − duration` vs the filename's start |
|---|---:|---:|
| `Screen Recording 2026-01-27 at 23.37.37` | 79 s | **+32 s** |
| `Screen Recording 2026-01-28 at 00.13.56` | 266 s | **+14 s** |

Both errors small and positive, consistent with finalise/encode overhead after
the recording stops. So for this writer class the correction recovers the start
to within about half a minute. Two files, one writer — indicative, not settled.

It is wrong elsewhere, which is why it needs a writer classifier and not a blanket
rule: a progressively-written file is created at *start* (subtracting makes it a
whole duration early), and a download's birthtime is when it landed on this Mac.

**5. Raw `birthtime`.** What ships today. Correct only for progressive writers.

**A discriminator that does NOT work:** `mtime − birthtime` looks like it should
separate save-at-close from progressive writers, and does not — MEASURED, the
FOSSDA files are downloads (so the delta is download time) and one Screen
Recording's `mtime` is *three months* after its birthtime because the file was
touched later. `mtime` is too easily disturbed to carry any signal.

**The domain check worth building in.** A researcher starts recording a few
minutes *into* the session, after asking consent — so a derived start should land
slightly **after** the calendar entry, never before. That sign test is a cheap
sanity assertion wherever a calendar time is available, and a derived start
*earlier* than the booking is evidence the writer class was misjudged.

### Prior art worth not re-deriving

`SessionsFinderDate.swift` already handles **the spring-forward gap**: a wall
time inside it does not exist, a strict `DateFormatter` rejects it, and JS's
`new Date()` shifts it forward to 03:30. The Swift parser therefore runs a
lenient second pass purely to match that behaviour, and documents the accepted
divergence. Somebody has already been here for one DST edge; the autumn repeated
hour is not handled anywhere.

---

## 3. The scenarios an audit would have to cover

The current corpus is single-timezone and single-DST-regime, so none of this is
exercised by anything we own.

### 3a. Across zones, one study

- Participant in Tokyo (UTC+9, **no DST at all**), researcher in London.
- Participant in Mumbai (UTC+**5:30** — a half-hour offset; anything assuming
  whole hours breaks).
- Participant in Kathmandu (UTC+5:45 — quarter-hour).
- A study spanning Auckland and São Paulo: **opposite hemispheres**, so their DST
  moves in opposite directions and there are weeks when the usual offset between
  them is off by two hours.

### 3b. The researcher moves

The case the user named, and the one most likely to embarrass us: **fieldwork
across several days with the researcher changing zone between sessions.**

- Sessions 1–3 recorded in London, 4–6 in New York, reviewed back in London.
- What does the Sessions grid sort by — the instant, or the local wall time?
  These give different orders.
- What does "Today" mean in the Finder-relative format when the viewer has moved
  since recording? MEASURED behaviour today: "Today" is computed against the
  *viewer's current* calendar day, from a value that is actually UTC-read-as-local
  — so it can be wrong in both directions at once.
- Two sessions recorded 30 minutes apart across a flight boundary can render
  hours apart, or in the wrong order.

### 3c. DST, and the fact that countries do not agree on the date

This is the part that cannot be reasoned about from one country's rules:

- **EU/UK**: last Sunday in October (and both change on the *same instant*, 01:00
  UTC — the UK and Ireland are the exception that changes at 01:00 local).
- **US/Canada**: first Sunday in November — so for one week in spring and one in
  autumn, London↔New York is **4 or 6 hours apart, not 5**.
- **Southern hemisphere** (Australia, NZ, Chile): opposite phase.
- **Lord Howe Island**: a **30-minute** DST shift.
- **Most of Asia, Africa, and all of India, China, Japan**: none at all.
- **Countries that have changed their rules recently** — a stored offset is not
  a stored zone, and `+01:00` does not tell you which rule set produced it.

Test dates worth pinning:

| date | why |
|---|---|
| 2026-03-29 01:30 Europe/London | **inside the spring-forward gap** — this wall time does not exist |
| 2026-10-25 01:30 Europe/London | **the repeated hour** — one wall time, two instants |
| 2026-03-08 / 2026-11-01 | US transitions, when the UK offset differs from the usual |
| 2026-04-05 Australia/Lord_Howe | a 30-minute transition |
| any date, Asia/Kathmandu | +5:45, to catch whole-hour assumptions |

---

## 4. The design question, stated but not answered

**Whose time is "the" time?** There are four candidates and they are all
defensible:

1. **The recording's local time** — what the clock on the wall said. What a
   researcher writing field notes would have put on the page.
2. **The participant's local time** — matters for "this was their 8am", which is
   a real analytical observation about fatigue and context.
3. **The researcher's local time at the moment of recording** — what their
   calendar said.
4. **The viewer's local time now** — what every current surface shows, by
   accident rather than decision.

These coincide in the single-zone study, which is why nothing has forced the
question yet.

Two broad shapes, and the choice between them is a product decision:

- **Normalise.** Store UTC plus the originating zone, display in one chosen frame
  consistently, sort by instant. Comparable across a study; requires the UI to
  say *which* frame, or it is just as ambiguous as today.
- **Show the assumption.** Display recording-local with an explicit zone label
  (`14:23 BST`, `09:23 EDT`), and let the reader do the comparison. Honest,
  noisier, and correct for the "this was their 8am" reading.

**The house position on absence applies here** (`feedback_absence_is_information`
and the appliance rule): where the zone is unknown — which is every session
recorded before the schema changes — the UI should say so rather than render a
confident wrong time. A session imported from a date-only header should not claim
midnight.

---

## 5. What an audit would actually have to do

Roughly in order, and the first item is the one that gates the rest:

1. **Decide what the datum is, and rank the signals** (§ 2b). `session_date` is
   currently "some filesystem timestamp", not "the session's start". No timezone
   work is meaningful until that is settled per source type — and the cheapest
   win is stopping `_normalise_stem` from discarding a timestamp it has already
   parsed.
2. **Read the container before touching anything else.** `utils/audio.py`
   already runs ffprobe for duration; adding `format_tags` to that call is a
   one-line change and yields `com.apple.quicktime.creationdate` (local time +
   offset), `creation_time` (UTC), and `make`/`model`/`software` (the writer
   class § (f)). This is the highest-value, lowest-cost item on the list, and it
   is independent of every product decision below.
3. **Capture the zone at ingest**, alongside the instant — an IANA identifier
   (`Europe/London`), not a bare offset, because an offset does not survive a
   rule change and cannot answer "was this during DST". Where only an offset is
   available (the Apple tag), store the offset and say so; where only UTC is
   available, store UTC and mark the zone unknown rather than guessing.
4. **Make the column `DateTime(timezone=True)`** and audit every writer for
   `.replace(tzinfo=…)` (T2).
5. **Decide the display frame** (§ 4) and apply it to all three surfaces at once
   — they are currently consistent, which is an asset worth not losing.
6. **Pin `finder_date` cases** in the shared-format contract, including the DST
   dates in § 3c (T6).
7. **Build a multi-zone corpus.** Nothing we own exercises any of this. The
   format-torture corpus (`experiments/folder-of-horrors/`) is the natural place.
8. **Decide what to say about historical projects**, which cannot be corrected.

---

## 6. Why this is not a beta concern

- The analysis pipeline does not read timezones. Quotes, clips, themes, deep
  links and durations are all zone-free.
- The three display surfaces are **consistent with each other** today; the error
  is a uniform offset, not a visible contradiction between two places the same
  user looks.
- The alpha cohort is one person in one timezone.
- The prerequisite (T3 — deciding what `session_date` even means) is a larger
  question than the timezone handling itself.

The cost of waiting is that every session recorded before the fix carries an
uncorrectable start time. That is worth knowing, and it is an argument for
capturing the zone early even if the display work is deferred — capture is cheap,
and it is the half that cannot be backfilled.

**Tracking:** an item for this belongs on the maintainer's planning notes kept
outside the public tree, as a post-beta audit.
