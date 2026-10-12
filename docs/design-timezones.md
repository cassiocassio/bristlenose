---
status: partial
last-trued: 2026-10-12
trued-against: HEAD@main on 2026-10-12
---

> **Truing status:** Partial by design. § 5.1 landed 12 Sep 2026; **§ 5.4's resolver, a § 5.2 writer table, a never-downgrade store standing in for § 5.3, and the T1 wire fix landed 11 Oct 2026** — what was built, and where it departs from the plan below, is § 5.9. § 5.3's schema, § 5.6's markers and the § 4 decision are still open and listed in § 5.10. § 1 and § 2 carry ✅ markers where a defect closed. See changelog.

## Changelog

- _2026-10-12_ — trued after the recorder pass (commits "session start: gopro, zoom field recorders, voice memos" and "session start: voice memos keep their tags when shared — measured"): § 5.8 marks the second-writer `Z` check answered (Teams honest, GoPro not); the judgement-calls paragraph names what is still owed. The § 5.9 tables and § 5.10 item 7 already carried the new rows. Research notes: `docs/research/research-gopro.md`, `research-zoom-recorders.md`, `research-voicememos.md`.
- _2026-10-11_ — **the start time is resolved, not read off the file.** New § 5.9 records what was built (`utils/session_start.py`, the registry's `starts`, `iso_utc`, the importer refresh, the renderer's conversion) and its four departures from § 5.4; § 5.2's table gains the 11 Oct measurements (Teams downloads and ReplayKit measured, iPhone inferred, a Mac-made capture date); § 5.10 lists what is still owed. T1, T3 and T4 marked. Anchors: `git log -S resolve_session_start`.
- _2026-09-12_ — trued up after § 5.1 landed: § 1 scoped to "persist"; T2/T5 marked fixed; § 2·5's "we read none of it" heading and body rewritten to "we read it since § 5.1"; § 5.1's plan bullets labelled as the plan with an accurate what-shipped (Pydantic model, tuple return, eight fields, one corpus test); (f) records the GPS allowlist as shipped code; new § 5.1a listing what the capture does not do; anchors re-pointed (`s01_ingest.py:467/470/393`, `pipeline.py:2904`); `timecode` count 15→21. Anchors: commits "ingest captures container time metadata", "time: review fixes — one probe…".

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

**The original timezone is not recoverable from anything we currently persist.** _(Since 12 Sep 2026 the ingest capture — § 5.1 — holds the recorder's own offset in memory on `InputFile.container_meta`; the database column still drops it, so for every stored session the sentence stands.)_

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
cause; everything downstream is a faithful renderer of a lossy value. _✅ Worked
around at the wire 11 Oct 2026: the column still drops the offset, but every
writer stores UTC, so `utils.timecodes.iso_utc` marks the emitted value UTC
(`/sessions`, `/dashboard`, MCP) and both clients convert it to the viewer's
clock. The column itself is § 5.3, still open._

**T2 — ✅ FIXED 12 Sep 2026 — `.replace(tzinfo=utc)` relabelled instead of converting.** MEASURED at the time.
`pipeline.py` (then `:2861`; `:2904` now, via the shared `parse_header_datetime`) read the transcript `# Date:` header as
`datetime.fromisoformat(s).replace(tzinfo=timezone.utc)`, which **overwrites** an
offset rather than converting it: `14:23+01:00` is stored as `14:23 UTC` when the
instant is `13:23 UTC`. `server/importer.py:83` reads the *same header* correctly
(relabels only when naive). So the CLI resume path and the server import path could
derive different instants from one file. One reader now.

**T3 — The value is not the session's start time in the first place.** _✅ Fixed
11 Oct 2026 by the resolver (§ 5.9); the paragraph below is the record of the
defect._ From
`SessionsFinderDate.swift`'s own KNOWN-WRONG note, which outranks everything
above: `session_date` is the source file's `st_birthtime`, taken raw —
MEASURED, `s01_ingest.py:467` and `:470` are `min(f.created_at for f in group_files)` and
**nothing anywhere subtracts the duration**. For a save-at-close writer that is
the session's **end**, so the stored value is late by a whole duration.

See § 2b — this is more tractable than the note implies, and the correction the
note rules out is right for the commonest case.

**T4 — Transcript-only imports fabricate midnight.** A bare `YYYY-MM-DD` header
yields 00:00, which renders plausibly and is indistinguishable from a real
midnight session. _Partly addressed 11 Oct 2026: it is now **local** midnight
(`parse_header_datetime`), so once the wire was marked UTC the day stays the day
west of London. It is still a fabricated time — § 5.10._

**T5 — ✅ FIXED 12 Sep 2026 (`local_now()`, aware and local, at all four) — Naive `now()` at four render sites.** `s12_render_output.py:81` and
`:178`, `s12_render/report.py:164`, `utils/markdown.py:493`. Does not crash
(MEASURED) because `format_finder_date` compares calendar dates rather than
subtracting, but it is a latent `TypeError` the moment anyone writes a
subtraction, and it is why markdown renders UTC.

**T6 — `finder_date` has three implementations and zero pinned cases** in
`tests/fixtures/shared-format-contract.json`, where `timecode` had 15 (now 21) and
`duration_human` has 9. Nothing mechanical would notice any of the above.

## 2·5. Where a real start time could come from — a signal hierarchy

The KNOWN-WRONG note says `birthtime − duration` "is not a general correction",
which is true and was read as "so there is nothing to do". There is quite a lot
to do; the signals just have to be ranked and the weakest one labelled rather
than trusted.

**1. The cloud API's meeting start.** Authoritative and zone-qualified. Already
available on the Teams/Drive import paths. Nothing else competes with it.

**2. Container metadata — the best local signal, and since § 5.1 (12 Sep 2026) we read it.**
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
known and its cost is known with it. **Shipped as a code-level allowlist** (12 Sep
2026): `time_meta_from_ffprobe` reads named keys only, the comment beside them
calls it a privacy boundary, and `test_gps_is_excluded_by_the_allowlist` asserts
ISO6709 is never retained.

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

**Bristlenose reads this since 12 Sep 2026** (§ 5.1): `probe_media` requests
`-show_entries format:stream_tags` in the one ffprobe call ingest makes
(`utils/audio.py`). Before that — MEASURED on the day — the only ffprobe call
sites were the duration probe and a `stream=codec_type` query;
`_get_creation_time` was, and still is, pure `os.stat`.

**3. The filename.** Zoom, Teams and macOS Screen Recording all write the start
time into the name — and **Python already parses these patterns and then
discards the timestamp** _(until 11 Oct 2026 — `utils/session_start.py` now keeps it; § 5.9)_. `_normalise_stem` (`s01_ingest.py:393`) strips the
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

_(The plan as written on 11 Sep; what shipped is under **What landed** below.)_

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
`probe_media` — one ffprobe call (`-show_entries format:stream_tags`) returning a
`(duration, meta)` tuple, not a widened `probe_duration`; `MediaTimeMeta` is a
Pydantic model, not a dataclass, with eight fields — `creation_utc`,
`creation_local` (the offset-bearing local form), `offset_minutes`, `make`,
`model`, `software`, `encoder`, `author`; the corpus proof is one skipif-gated
test on `IMG_2544.MOV` (`offset_minutes == 60`) plus pure-parser tests over the
measured tag dicts, not five corpus files; `time_meta_from_ffprobe` is pure and tested on the measured
tag dictionaries. `bristlenose status` does not surface it yet — that is a CLI
surface change with man-page and README obligations, held for when § 5.4 gives
it something to say._

_**Scope limit, stated (review Finding 36):** the rule "a naive `creation_time`
means UTC" was verified against **one** writer, a macOS MOV, and is applied to
all 24 accepted containers. It is definitionally false for
`com.apple.quicktime.creationdate`, which is the room's wall clock — a naive one
is now logged and left unstamped rather than relabelled. For `creation_time` the
assumption stands until a second writer family is measured (§ 5.8)._

### 5.1a — What the capture does NOT do

The preconditions § 5.4's resolver reads (since 11 Oct 2026), in one place:

- **Not persisted.** `container_meta` lives on `InputFile` in memory for the run; the database column (`server/models.py:220`) still drops the offset. § 5.3 is the schema step.
- **Not surfaced.** `bristlenose status` shows nothing of it — a CLI surface with man-page and README obligations, held until § 5.4 gives it something to say.
- **Not a zone.** What is captured is an *offset* (`offset_minutes`) when the container carries one; an IANA name is never derived from it (§ 5.3's rule).
- **One writer's word on UTC.** "a naive `creation_time` means UTC" is verified on one macOS MOV and applied to 24 containers (§ 5.8 owes the second family); a naive `creationdate` is logged and left unstamped, never relabelled.
- **`author` is held, not decided.** Bounded to 256 chars at the dict layer, in memory only, pending the keep/drop/redact decision (review Finding 5) that § 5.3 must settle before anything persists.

_**Judgement calls left for the maintainer, in order — none is a mechanical
step:** § 5.2's table has three owed measurements that need files not on this
machine (iPhone start-vs-end, Zoom local transcode, a real OBS/browser
capture) — _still owed on 12 Oct 2026; GoPro, Zoom field recorders, Voice Memos
and ⇧⌘5 window capture were measured instead, § 5.9_; § 5.3 is a schema migration with a compatibility decision on
`session_date`; § 5.4's tolerance and precedence are product calls the
consent-delay sign test only informs; § 5.5 depends on § 5.3; § 5.6 is gated on
§ 4, which is the one that decides whose time is "the" time._

### 5.2 Classify the writer

_Partly done 11 Oct 2026 — the measured rows are in § 5.9's table and `_END_WRITERS`; the owed rows are § 5.10 item 4. The plan below stands as written._

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

**Deliverable owed with this step, not after it:** a paragraph in `SECURITY.md`'s
"what Bristlenose writes to your machine" inventory stating what is read from
media containers, why (writer classification for start-time resolution), that
location is deliberately excluded, and — once persisted — the retention and
erasure answer. And the `author` keep/drop/redact decision (review Finding 5)
must be made before the column exists.

### 5.4 The resolver — precedence, tolerance, and disagreement

_✅ Landed 11 Oct 2026, with four departures recorded in § 5.9 (filenames above the container; unzoned local names converted; container sanity checks; `session_date` rewritten in place). The plan below is the original._

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

_Superseded 11 Oct 2026: a re-run is the backfill (§ 5.9) — ingest re-resolves, the registry keeps the best start, the importer refreshes the database. No separate command was built._

`bristlenose backfill-start-times <project>` — re-probe every session's media
on disk, run 5.4, write 5.3's columns, and print one line per session naming the
source that won and any conflict. **Dry-run by default, `--apply` to write**,
same shape as `experiments/quote-stability/repair_cached_boundaries.py`. Sessions
whose media is gone get `source = none` and are listed, not skipped silently.

### 5.6 Display — after, not before, the decision in § 4

_Half landed 11 Oct 2026: the instant is right and renders in the viewer's zone on all three surfaces (§ 5.9). The marker for a differing or unknown zone is still owed (§ 5.10)._

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
  beyond Apple's own tools. _✅ Answered 11–12 Oct 2026: a Teams download's `Z`
  is honest (18:07:38Z against a name stamped 20:07 CEST); a GoPro's is **not**
  (the camera's local clock with a false `Z`, six models measured against their
  own GPS) — § 5.9._

### 5.9 ✅ LANDED 11 Oct 2026 — the resolver, as built

`bristlenose/utils/session_start.py`, called from `s01_ingest.group_into_sessions`.
Every session's `session_date` is now its resolved start, and
`InputSession.session_start_source` says which signal won.

**Precedence as built** — and the four places it departs from § 5.4, each made in
review on the day:

1. `cloud_import` — Bristlenose's own download stamp, **only in the exact form
   `CloudDownloadVerification.filename` writes** (`2026-09-03 1000 — Title` with an
   em dash, the bare stamp for an untitled meeting, a ` (2)` part). A hand-typed
   `2026-05-01 0001 - P1` is not read: a researcher's typed time is often the
   booking, and a sequence number looks the same. Read as this machine's local
   wall clock, because Swift wrote it on one.
2. `filename_zoned` — names that state a zone: Teams `…_142007UTC-Meeting
   Recording`, Zoom cloud `GMT…`, Pixel `PXL_…`, a Meet recording with `GMT±n`.
3. `filename_local` — names on a local clock: the Zoom local folder, macOS
   Screen Recording (localised, 12-hour, meridiem-first `오후`/`午後`), Android,
   OBS, Windows Game Bar, a Meet recording named in this Mac's zone. WhatsApp's
   `… at 14.30.22` is the message time and is not read.
4. `container` — Apple's capture date (`creationdate`) when present, else
   `creation_time`; moved back by the duration only for ReplayKit.
5. `birthtime` — unchanged, never adjusted.

- **Departure 1 — filenames outrank the container.** § 5.4 put the container
  first. A recognised filename *states* the start; the container is either
  derived (ReplayKit end − duration, which a trim shortens: a 20-minute trim
  came out 20 minutes late) or from a writer nobody has measured (Zoom's local
  transcode is expected to stamp the end, which would lose the folder's exact
  start on every Zoom session). The container still beats birthtime. § 5.4's
  order can return once § 5.2's table is complete.
- **Departure 2 — an unzoned filename IS converted**, as local time, where
  § 5.4 rung 5 said "never converted". Without § 5.3's columns and § 5.6's
  marker there is nowhere to keep a zoneless value, and the machine's zone is
  right for a file this Mac's own recorder named. **An unzoned Teams name is
  not read at all** — measured: `…-20260815_200732-…` carries 20:07 against a
  container of 18:07Z, i.e. the organiser's CEST, not this Mac's BST.
- **Departure 3 — a container time is refused** before 2000 or later than the
  file's creation + 5 min (a recorder cannot stamp a file after it exists).
  Measured case it catches: a web recorder whose files carry `creation_time`
  exactly 4 h after their creation (`20241206 0945 Recording.mp4`).
- **Departure 4 — `session_date` is rewritten in place**, where § 5.3 said keep
  it untouched during a migration. There is no migration; the field now means
  what every surface already took it to mean.

**Conflict**: two non-birthtime signals more than 5 min apart → the higher rung
stands and a `session_start_conflict` WARNING names both files. Birthtime is
excluded (for a download it is the download moment). The log is the only place
it reaches — § 5.10.

**Never downgrade** (stands in for § 5.3's `session_start_source`): the session
registry (`.bristlenose/sessions.json`, optional `starts`) keeps each sid's best
start and source; a later run replaces it only with a strictly better-ranked
signal (`SessionRegistry.settle_starts`). So an iCloud-evicted recording, whose
container ffprobe cannot read, does not fall back to its file date, and a
re-run on a Mac in another zone does not move a filename-read start.

**Numbering**: a new project, or one with a registry, is numbered by resolved
start; a project analysed before the registry existed (transcripts, no
`sessions.json`) keeps the old creation-time order, because moving it would
carry stars and names between interviews (`pipeline._may_order_by_start`).

**Reaching the screen**: the importer refreshes `session_date` on every import
(it used to set it at creation only, so a re-run never reached the database);
`iso_utc` marks the wire UTC; `format_finder_date` converts an aware value to
the system zone (per instant, so DST is right on both sides of a change); the
dev sessions page tags the naive DB value UTC.

**Backfill (§ 5.5)** is a re-run: ingest re-resolves, the registry settles, the
transcript headers are rewritten and the importer copies them. No separate
command.

**§ 5.2's table, as measured 11 Oct 2026** on the media files on the
maintainer's Mac (metadata only; placeholders skipped):

| writer (as identified) | stamps | evidence |
|---|---|---|
| macOS ReplayKit (`author = ReplayKitRecording`) | **end** | 32 files: container − birthtime is 0 or −1 s on every one |
| Teams recording download (no writer tags, brand `isom`) | **start** | container within 1 s and 6 s of the filename's start on 2 files |
| iPhone camera (`make = Apple`, `model = iPhone …`) | start — **INFERRED** | capture date = `creation_time` on 7 files; start-vs-end needs a known start |
| QuickTime Player / Photo Booth on a Mac (`model = Mac…`) | capture date = start side; `creation_time` = save | 1 file: capture date 34 s before `creation_time`, which equals the file's creation |
| GoPro HERO5/6/7/8, MAX, Fusion (`firmware` HD5.–HD8., H19., FS1.) | **start**, on the camera's local clock with a false `Z` | 6 public sample files (gopro/gpmf-parser `samples/`), each checked against the GPS time in its own `gpmd` stream: 7 h (April) or 8 h (Jan/Nov) = Pacific, where they were shot; set clocks drift −44 s to +40 s from GPS |
| Zoom F8, Zoom H1 (bext `Originator` "ZOOM F8" / "ZOOM Handy Recorder H1") | **start** (OriginationDate/Time), local, no zone | public BWF fixtures (iluvcapra/wavinfo `tests/test_files/zoom_F8`, and an H1 set); ffprobe exposes it as `date` + a bare `creation_time`; `time_reference` is timecode, not the clock |
| Voice Memos (`encoder = com.apple.VoiceMemos …`) | end — **INFERRED** | a July copy: `creation_time` 4 m 27 s before the file existed with 6 m 5 s of audio, so it cannot be the start. **Measured 12 Oct 2026:** a memo recorded on the Mac and shared three ways (drag out, Mail, WhatsApp) — all three copies keep identical tags (`encoder`, `voice-memo-uuid`, `creation_time`), renamed to the memo's title; no `date` tag. The encoder, not the filename, is what identifies a Voice Memo |
| a device clock that lost its setting | 1 January — refused | a Zoom H1 at 2010-01-01 counting up from power-on; a GoPro HERO7 at 2016-01-01 |
| an unidentified web recorder (`Web Recording 20240604 1356.mp4`) | wrong clock | `creation_time` exactly 4 h after creation — refused |
| Voice Memos, WhatsApp audio (no writer tags) | unclear | not classifiable from tags; taken as written |

**Tests**: `tests/test_session_start.py`, `tests/test_session_start_surfaces.py`,
and `TestStickyStart` in `tests/test_pipeline_platform_transcripts.py` (through
the real `Pipeline.run`). Every guard was mutation-checked: removing it turns
its own test red.

**Coverage — which recordings get a real start (11 Oct 2026).** By the
signal that decides them; "measured" means checked against real files, "named"
means the app's own documented naming states it.

| source of the recording | how its start is read | basis |
|---|---|---|
| Bristlenose cloud import (Teams, Meet, Zoom via the Mac app) | the download stamp | the platform's own start, written by us |
| Teams recording, hand-downloaded | `…UTC-Meeting Recording` name, else the container (stamps start) | measured, 2 files |
| Zoom cloud download | `GMT…-…_Recording` name (UTC) | named |
| Zoom local recording | the dated folder | named |
| Google Meet recording, hand-downloaded | ` - YYYY/MM/DD HH:MM zone - <kind>` name, media files only | named; `GMT±n`/`UTC`, or this Mac's own zone name |
| macOS Screen Recording (⇧⌘5, whole screen or one window, mic on or off) | the name, else the container moved back by duration | measured: 7 distinct files, 3 with audio; untouched files land +11 to +32 s, trimmed copies −3 to −4 min — the name wins |
| QuickTime Player / Photo Booth movie | the capture date | measured, 1 file |
| iPhone camera | the container (capture date) | inferred start |
| Apple Voice Memos, the original file | the `YYYYMMDD HHMMSS-XXXXXXXX` name, local | reported (forensic write-ups); the folder is privacy-protected and was not measured |
| Apple Voice Memos, any copy with the `com.apple.VoiceMemos` encoder | the container moved back by duration | inferred end, from one file |
| GoPro (HERO5 onwards, MAX, Fusion; `firmware` tag) | `creation_time` read as the camera's **local** wall clock, despite its `Z` | measured on 6 models against their own GPS: the start |
| Zoom field recorders (H1n, H2n, H4n, H5, H6, H8, F-series) and other Broadcast WAV | the `bext` origination date and time, local | measured on a Zoom F8 and an H1; documented in Zoom's manuals and EBU Tech 3285 |
| Android camera (`VID_`, Samsung), screen recorders | the name, local | named |
| Google Pixel camera | `PXL_` name, UTC | named |
| OBS Studio (default naming), Windows Game Bar | the name, local | named |
| a copied, downloaded or renamed file from any recorder that writes `creation_time` | the container | survives copying |
| everything else | the file's creation date — the old behaviour | — |

### 5.10 Still owed — the next pass

In rough order of value; none of these blocks the store launch on its own.

1. **§ 4, whose time is "the" time** — the product decision every item below
   waits on.
2. **§ 5.3's schema** — persist the offset and the source on the session row,
   and `DateTime(timezone=True)`. The registry's `starts` is the stopgap.
3. **§ 5.6's marker** — a conflict and a fabricated time (T4's local midnight,
   an unzoned local reading) should be visible, not only in the log. Today
   nothing on screen distinguishes them from a measured start.
4. **The rest of § 5.2's table**: iPhone start-vs-end against a known start;
   Zoom's local transcode (does it write `creation_time`, at which end?); a
   real OBS/browser `.webm`; Voice Memos. Then reconsider restoring § 5.4's
   container-first order for measured writers.
5. **Google Meet named zones** — a Meet recording's name is read (media files
   only, so the Gemini notes Doc's later stamp never decides) when its zone is
   `GMT±n`/`UTC`, or a name that is this Mac's own zone at that moment (`BST` on
   a London Mac in July). Any other name (`CEST` on a London Mac) is not read:
   abbreviations are ambiguous (`IST`, `BST`), and mapping them needs the
   tenant's zone, which only the cloud import knows.
6. **The consent-delay sign test** (§ 5.4) — needs a calendar start, which only
   the cloud import has.
7. **Recorders still to research with real files.** GoPro, Zoom field
   recorders, Voice Memos and ⇧⌘5 window capture were researched 11–12 Oct 2026
   (tables above; full notes with every source URL in `docs/research/research-gopro.md`,
   `research-zoom-recorders.md`, `research-voicememos.md`). Still open:
   - **Voice Memos originals** — measure 5–10 with Full Disk Access granted:
     filename vs the `date` tag vs `creation_time` vs the app's database
     (ZDATE, ZDURATION), and one memo each after Trim, Enhance and resume.
     _(12 Oct 2026: a memo shared by drag, Mail and WhatsApp kept its
     `com.apple.VoiceMemos` encoder in all three, so sharing does not strip it.
     The July copy without tags came by an unknown route.)_ Still owed: one
     memo of a minute or more with its start noted to the second, to turn
     "end" from inferred to measured.
   - **GoPro HERO9–13** — no public sample; whether HERO11+ (which has a
     timezone setting) still writes local time is open. The exact zone is
     recoverable from the GPS time in the `gpmd` stream (its difference to
     `creation_time`, rounded to 15 min) — not built; today a GoPro is read on
     this Mac's clock, right when the camera was set to the zone it is being
     analysed in.
   - **Zoom recorders' chained files** — over 2 GB a recording continues in a
     new file named for when it continued; the session starts at the earliest.
     Grouping such a chain into one session is not built. Zoom's
     `YYMMDD-HHMMSS` naming is not read (the date order is user-set, so the
     name alone is ambiguous); iXML `FILE_UID` is not read (ffmpeg ignores
     iXML).
   - WhatsApp (message time; deliberately unread), Webex,
     Lookback/UserTesting/Riverside/Loom exports (naming unknown), other action
     cameras (Insta360, DJI).
8. **Measure the "named" rows.** Zoom cloud's GMT prefix, Pixel's UTC names
   and the Android/OBS local names are each documented behaviour, not files we
   have checked; one real file per row would make them "measured".
9. **Old projects without a registry** keep creation-time numbering forever;
   a one-off migration that writes their `sessions.json` from the current
   database would let them be renumbered safely. Owner's call (3 Oct 2026:
   not migrated).

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
