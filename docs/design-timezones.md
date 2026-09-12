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

**(e) Coverage: the raw count understates it badly.** Only **7 of 59** corpus
files carry a time-ish tag, and that number is worth almost nothing as a base
rate. 18 of the 59 are ffmpeg-synthesised (`encoder: Lavf…`) and ffmpeg drops
the tag unless told to preserve it; the FOSSDA `.mp4`s are re-encoded downloads
of third-party archival footage and lose it the same way.

**Neither is the population that matters.** Researchers overwhelmingly create
their own recordings, and every recorder-written file measured here carries the
tag: macOS Screen Recording, an iPhone MOV (with the offset, § (a)), a Teams
download, a QuickTime capture. The pattern is **recorder-written files carry it;
transcoding strips it** — and transcoded third-party archive is the exception in
a real study, not the norm.

So the honest reading is the opposite of the raw count: **expect this signal to
be present for the files a researcher actually records.** It still must degrade
to § 3 and § 4 rather than be assumed — a shared/forwarded file may well have
been through a transcoder — but it should be the primary path, not a lucky
bonus.

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

## 5. The plan — Tier 2, in strict order

_Tier 0 and Tier 1 — the zone-free fixes — are in `docs/time-defects.md` § 7 and
do not depend on anything here. This is the start-time and timezone work. The
order is strict because each step is what makes the next one measurable._

### 5.1 ✅ LANDED 12 Sep 2026 — Read the container (`git log -S MediaTimeMeta`)

- `utils/audio.py` already runs `ffprobe` for duration. Extend that one call's
  `-show_entries` with `format_tags` and `stream_tags`, parse the JSON, and
  return a small dataclass beside the duration:
  `MediaTimeMeta(creation_utc, creation_local_with_offset, offset_minutes,
  make, model, software, encoder)`. All fields optional.
- Read `creation_time` (UTC) from the format tags, falling back to the first
  stream's — the iPhone and ReplayKit files carry it on both, Matroska on the
  format. Read `com.apple.quicktime.creationdate` for the offset-bearing local
  form; parse the trailing `±HHMM` into `offset_minutes`.
- Do not act on it yet. Persist it (5.3) and surface it in `bristlenose
  status`. This step is pure capture and is **retroactively applicable** —
  the metadata never leaves the file — so it can land alone, at any time, and
  a backfill (5.5) reaches every existing project whose media is still on disk.
- Proof: a unit test over the five `folder-of-horrors` files whose manifest
  already carries `creation_time` (`harvest.py` captured it), asserting the
  parsed UTC instant and, for `IMG_2544.MOV`, `offset_minutes == 60`.

_**What landed:** `MediaTimeMeta` on `InputFile`, populated at ingest by
`probe_time_meta`; `time_meta_from_ffprobe` is pure and tested on the measured
tag dictionaries. `bristlenose status` does not surface it yet — that is a CLI
surface change with man-page and README obligations, held for when § 5.4 gives
it something to say._

_**Judgement calls left for the maintainer, in order — none is a mechanical
step:** § 5.2's table has three owed measurements that need files not on this
machine (iPhone start-vs-end, Zoom local transcode, a real OBS/browser
capture); § 5.3 is a schema migration with a compatibility decision on
`session_date`; § 5.4's tolerance and precedence are product calls the
consent-delay sign test only informs; § 5.5 depends on § 5.3; § 5.6 is gated on
§ 4, which is the one that decides whose time is "the" time._

### 5.2 Classify the writer

The single question that decides whether `birthtime − duration` applies is
*does this writer create the file at the start or at the end?* — and the
container answers it with `make`/`model`/`software`/`encoder`, which 5.1 now
captures. Build a small table, each row **measured** before it is trusted:

| writer (as identified) | file created at | measured? |
|---|---|---|
| macOS ReplayKit (`com.apple.quicktime.author = ReplayKitRecording`) | **end** | yes — birthtime = container time = end, +14 s / +32 s after subtracting duration |
| iPhone camera (`make = Apple`, `model = iPhone …`) | ? | **owed** — one file, compare `creationdate` to a known start |
| Zoom local transcode | end (expected) | **owed** |
| Teams / Zoom cloud download | irrelevant — the cloud API start (5.4 rank 1) wins | — |
| OBS / browser capture (`.mkv`/`.webm`) | start (expected — progressive) | **owed**, and whether it writes `DateUTC` at all |
| ffmpeg-transcoded (`encoder = Lavf…`) | **unknown** — the tag is gone | measured: absent |
| unrecognised | unknown | — |

An unknown writer gets no subtraction and a `source = birthtime` label, never a
guess. The table lives next to the code as data, not as a chain of `if`s, so a
new writer is a row.

### 5.3 Schema

Add, and keep `session_date` untouched during migration so nothing reading it
breaks:

| column | type | meaning |
|---|---|---|
| `session_start_utc` | `DateTime(timezone=True)` | the resolved instant |
| `session_start_offset_min` | `Integer`, nullable | the recording's local offset from UTC, when known |
| `session_start_zone` | `String`, nullable | IANA identifier when known (cloud API, or a future capture at ingest); **never** derived from an offset |
| `session_start_source` | `Enum` | `cloud_api` · `container_local` · `container_utc` · `filename_zoned` · `filename_unzoned` · `birthtime_minus_duration` · `birthtime` · `header` · `none` |
| `session_start_conflict` | `Boolean` | two sources disagreed beyond tolerance (5.4) |

`timezone=True` is what stops the DB boundary destroying the offset (§ 1). It
is also the point at which T1-1's converted `# Date:` values start meaning what
they say.

### 5.4 The resolver — precedence, tolerance, and disagreement

One function, one session in, one `(instant, offset, source, conflict)` out.
Precedence, highest first:

1. cloud API meeting start
2. container `creationdate` (local + offset) — adjusted by `− duration` only when
   5.2 says the writer creates at end
3. container `creation_time` (UTC) — same adjustment rule
4. filename timestamp, **zone-qualified** (`…UTC`, `GMT-5`) — Swift's
   `TeamsRecordingName` already does this with the right refusal rule; port it,
   do not re-derive it
5. filename timestamp, **unqualified** — recorded as `filename_unzoned`, rendered
   with a "local time, zone unknown" marker, never converted
6. `birthtime − duration`, only for a 5.2 writer that creates at end
7. `birthtime` — what ships today; for a 5.2 writer that creates at start
8. transcript `# Date:` header (via T1-1's converter)
9. none — and the UI says so (§ 4, absence-is-information)

**Disagreement is a first-class output, not an error.** When two sources are
both present and differ by more than a tolerance — start at **5 minutes**, which
absorbs consent-delay and encode overhead but not the four-hour case measured
on `System Audio 20220308 1316.mp4` — the higher-ranked one wins, both are
logged at WARNING with their values, and `session_start_conflict` is set. The
UI renders the winner with a marker. Never silently pick.

The **consent-delay sign test** as a sanity assertion: where a cloud calendar
start is available, a resolved start *earlier* than the booking is evidence the
writer class was misjudged (recording starts a few minutes *into* the meeting,
after "are you happy for me to start recording?"). Log it; do not auto-correct.

### 5.5 Backfill

`bristlenose backfill-start-times <project>` — re-probe every session's media
on disk, run 5.4, write 5.3's columns, and print one line per session naming the
source that won and any conflict. **Dry-run by default, `--apply` to write**,
same shape as `experiments/quote-stability/repair_cached_boundaries.py`. Sessions
whose media is gone get `source = none` and are listed, not skipped silently.

### 5.6 Display — after, not before, the decision in § 4

Until § 4 is decided, one rule that is defensible under every option: render the
UTC instant in the **viewer's** zone (what the SPA and Swift already do, now
with a *correct* instant), and add a marker whenever `session_start_offset_min`
is known and differs from the viewer's — `14:23 (09:23 EDT)`, or an icon with
the recording-local time on hover. The three surfaces move together (§ 3b: they
are currently consistent, and that is an asset). Python's markdown adopts the
same instant and converts to the same frame; its `Today at` separator is a
catalogued divergence and stays.

### 5.7 Tests

- **Contract**: `finder_date` gains its first pinned cases (T0-7), with naive
  inputs until 5.3 lands and aware inputs after.
- **Resolver unit tests**: one per precedence rung; one per disagreement shape
  (agree, disagree-within-tolerance, disagree-beyond, one-missing); the sign
  test.
- **Corpus acceptance**: `trial-runs/folder-of-horrors/manifest.csv` gains
  `expected_start_utc`, `expected_offset_min`, `expected_source` for every row
  with container metadata (five today) plus the two Screen Recordings whose
  filenames give ground truth. A test runs 5.4 over the corpus and diffs.
  This is the harness for the whole tier and the files already exist.
- **DST cases** (§ 3c) as resolver inputs: the spring gap, the repeated hour,
  the US/UK mismatch week, Lord Howe's 30-minute shift, Kathmandu's +5:45.
  These are pure-function tests and need no media.

### 5.8 Measurements still owed before 5.2's table is trusted

- iPhone camera: start or end? One file with a known start.
- Zoom local transcode: does it write `creation_time`, and at which end?
- A real OBS/browser `.webm`: is `DateUTC` populated? (read path proven;
  write side not.)
- A second BST-era file from a different writer, to confirm the `Z` is honest
  beyond Apple's own tools.

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
