---
status: in-progress — pipeline half landed 1 Oct 2026; import half written blind the same day, built and green on the Mac the same evening (§0c); live-tenant measurements and owner decisions open
last-trued: 2026-10-01
owner: cloud import + pipeline
supersedes-in-part: docs/design-cloud-import.md §3 "Google's transcript is out of scope" (v1 descope, 16 Aug 2026)
---

# Cloud import brings the transcript too — plan

**The goal.** A researcher ticks one checkbox against a meeting in the import window. Bristlenose
fetches the recording *and* the platform's transcript. Both land in the project as one pair, and the
report's speakers are the platform's real names for every turn. No LLM guesses who spoke, and no
Whisper-and-splitter pass runs on audio that already has an authoritative transcript.

**Why now.** On 30 Sep 2026 an audit of the Talismanic study found the failure this plan removes. For a
bare video, `split_single_speaker_llm` reads only the first 5–8 minutes, and every later segment
inherits the last label. In session 2 that attributed the last 29 minutes to the moderator. When a
real transcript sits beside the video, none of this happens: the Talismanic Teams `.docx` session kept
both names across all 214 turns. So the transcript is the fix. What is missing is getting it in
automatically, and a pipeline that is safe to hand it to.

The evidence is in three working reports and a set of stubbed harnesses (no paid calls) in the
maintainer's gitignored scratch area. The facts each phase depends on are restated inline, labelled
**MEASURED** (observed by running code), **VERIFIED** (quoted from a vendor's live documentation,
30 Sep 2026) or **INFERRED**.

---

## 0. After review (30 Sep 2026): the recommended first slice

A review by eight agents plus a compose-check and a parsimony pass (log: the maintainer's private review
notes, 50 findings) found the plan **over-scoped**, and found **four designs in it that would not work as
written**. Those are corrected here; the sections below are kept as the full map and are marked where the
review changed them.

**Designs that were broken, and what replaces them:**

1. **The t=0 check could never fire.** It checked the tail *after* clamping, and it only caught δ in
   one direction. Replacement:
   - Check the edge cues *before* slicing, against the **probed** media duration.
   - Meet: `endTime − startTime` must equal the probed duration within 1 s.
   - Write `media-duration:` into the NOTE, and have the pipeline refuse the transcript (Whisper, with the
     reason stated) if the file's length has changed. That covers a QuickTime trim after import, which is
     routine.
   - Probe the container's `start_time`.
   - The silence-alignment check stays **optional** until one live measurement per platform shows the
     offset is ever non-zero.
2. **The analysis hold only held in the window.** Media sat in the watched folder, so any later run
   Whispered it anyway. And bringing a transcript in *after* analysis re-cuts quotes the researcher may
   have starred, which was on the main Teams path. **Replacement (1 Oct 2026, owner: "wait for the
   transcript"):**
   - **Waiting means not importing yet, and it is evident and hard to get round** (owner, 1 Oct
     2026). A row whose transcript is *Expected* has a **disabled** checkbox, and Status says
     *Waiting for transcript*. That is where the window already explains every other disabled box.
     Recordings don't expire for weeks or months (§1a), so the wait costs nothing. Nothing sits
     half-imported in the project waiting to be analysed by mistake.
   - **The only way round it is in the footer** (owner's layout, 1 Oct 2026): the count, then a
     checkbox **"Include {N} waiting on transcription"**, then Project and **Import**, whose count is
     what the researcher will get. A checkbox, not a switch, because it is about this batch, not a
     setting. Off each time the window opens, never remembered. **The checkbox and its text are not
     drawn at all when nothing is waiting.** On, it enables the waiting rows, still unticked.
     Plural key: `includeWaiting_one/_other` ("Include {{count}} waiting on transcription").
   - **The row looks unfinished and finishes itself while the window is open** (owner, 1 Oct 2026:
     "nobody reads anything" straight after a session). The title is in secondary colour, the
     checkbox is disabled, and Status shows a spinner with *Waiting for transcript*: the cue the
     Teams chat gives. The open window re-checks waiting rows (~30 s on Teams, ~60 s on Meet and
     Zoom). When a transcript lands, the row turns *Available*, ticks itself, and the Import count
     updates. **Window-scoped only**: no persisted pending state, no tokens used while the window is
     closed. The import session's objection to a background poller doesn't apply.
   - **Teams "Expected" may become certain.** Teams posts a transcript system message in the meeting
     chat (`callTranscriptEventMessageDetail`, VERIFIED to exist; when it is posted is unmeasured).
     If the admin approval also covers reading the meeting chat, the inference becomes a signal. Add
     it to the Teams probe. Until then the inference errs long (4 h): waiting too long costs a
     minute's patience, giving up too early costs the speaker names.
   - Bulk ticks (⌘A, a meeting's header checkbox) never include a waiting row.
   - **Final states are never gated.** Needs approval, Unavailable and No transcript stay tickable, so
     an IT refusal never stops work.
   - When the window is next opened, the row reads *Available* and is ticked by default.
   - Everything that is imported is analysed at once; there is no hold.
   - A `.bristlenose/importing` sentinel, carrying a pid and an age, still stops a run from starting
     while a pair is half-landed.
3. **An unnamed transcript went back to the 5–8-minute splitter**, which is the defect this plan exists
   to remove. Replacement: `speakers: none`, like a single account, means **"speakers not separated"**,
   and the splitter does not run.
4. **Fetching the missing half later** could write a transcript beside the wrong recording, because the
   local match is by duration and siblings often share a length. It could also rebuild a different
   filename after a time-zone change. Deferred with the hold. When it returns, it must pair by a
   recorded platform id (for example an extended attribute on the media file), not by name or duration.
   The researcher renames files as a matter of routine, so name-only matching would never complete a
   renamed pair.

**The first shippable slice: "one checkbox imports recording + transcript with real names", on Meet
(no new permission).**
- **Pipeline:**
  - 0a, plus popping the *stage* record when any session's cache is discarded; an absent fingerprint
    means recompute; the quote input includes the transcript hash.
  - 0c.
  - 0d, with named beating unnamed before format.
  - 1a and 1b, with the replacement in 3 above.
  - From 1d, only "the platform name beats the LLM" and "a masked phone number is never a name".
  - The parser version goes into the transcribe input hash.
- **Contract:**
  - §4, plus escaping: the writer escapes `& < >`, strips newlines and `-->`, and keeps NOTE values on
    one line; s03 unescapes.
  - `language:` is a BCP-47 tag, reduced to the primary subtag only for Whisper.
  - `media-duration:`.
  - One **golden `.vtt`**, written by the Swift writer, checked byte-for-byte in Swift and parsed by
    pytest.
- **Import:** Phase 2, same-batch only. Option A grid; about 7 transcript states for Meet.
- **Separate commits, live today:**
  - `CloudDownloader` publishes with remove-then-move (`CloudDownloader`'s publish step: cite it by function name, because the progress sampler added on 30 Sep moved the lines) instead of
    `replaceItemAt`.
  - Meet's download re-attaches the token on any redirect host.
  - `--redact-pii` leaves the meeting title in the `# Source:` header of the cooked transcripts.

**Pipeline half of the slice — landed on `main`, 1 Oct 2026** (seven commits, each test-first; the
Swift half — writer, grid, transport — is still to do and must produce the golden `.vtt` files
byte for byte):

| Item | What landed | Where |
|---|---|---|
| 0a | `SessionRecord.input_hash` per stage (files + parser version / segments / transcript / transcript + topic map); `fresh_session_ids` reuses a record only on a match, and a record with no fingerprint is recomputed; an input change *demotes* the stage instead of popping it; `_is_speaker_stage_verified` checks inputs before files; quotes watch the transcripts | `manifest.py`, `pipeline.py`; `tests/test_pipeline_platform_transcripts.py::TestPerSessionFingerprints` |
| 0c | stamped files group by (stamp, title); an unstamped file joins only a unique match | `s01_ingest._group_by_stem`; `tests/test_ingest.py::TestRecurringMeetings` |
| 0d | one transcript per session: named > coverage (10 % tolerance) > cloud VTT > VTT/SRT > DOCX; losers stated in log + CLI | `stages/transcript_choice.py`; `tests/test_transcript_choice.py` |
| 1a | NOTE block read (1.x accepted, other majors refused loudly), multi-voice cues split with time shared by text length, names and text html-unescaped, BCP-47 `language` exposed; cues carry `source="cloud-vtt"`; the colon heuristic is off for cloud files | `s03_parse_subtitles`; `tests/test_parse_subtitles.py`; golden fixtures `tests/fixtures/platform-transcripts/cloud-transcript-{named,unnamed,rebased-drops}.vtt` |
| 1b | `split_gate()`: a platform transcript with a real name, or a cloud transcript with none, is `NOT_SEPARATED` — kept whole and stated; Whisper and bare caption tracks split as before | `s05b_identify_speakers`; `tests/test_speaker_splitting.py::TestSplitGate` |
| 1c | `Name: text` accepts any script with combining marks, commas, `(Guest)`, pronouns, the fullwidth colon; a sentence-opener list and a six-word cap refuse `Honestly:`, `Note:`, `Gern:`, `http:`; the 22 xfails are passes | `s03._looks_like_speaker_name`; `tests/test_international_names.py` |
| 1d | platform label beats the LLM's `person_name`, participants only; names keyed by speaker code; phone labels (masked or whole) are never names | `people.py`; `tests/test_name_extraction.py` |
| — | `--redact-pii` writes `# Source: [REDACTED]` in cooked transcripts; the importer takes the media path from the raw sibling | `s07`, `server/importer.py` |

Two judgement calls made while building, both reversible and worth the owner's eye:

- **`_inputs_changed` tolerates a stage-level key the stored record never recorded** (compared on what
  the record knew, stamped on the hit, strict from then on). Strict comparison would have re-extracted
  every existing project's quotes once on upgrade when the quote stage began watching the transcripts
  — paid LLM calls and a reshuffled report nobody asked for. The *parser version* is deliberately
  exempt from that tolerance (folded into the transcribe `source_files` value), so a parser fix does
  reach a project that has a transcript file; the cost is that such a project re-Whispers its bare
  recordings once, because their pre-fingerprint records cannot prove themselves fresh.
- **"Speakers not separated" is stated on the terminal and in the log**, not in `PipelineSummary` — no
  slot for a non-failure note exists, and inventing one is a Swift-side change. If the Mac should show
  it, that is a new `StageOutcome` field plus the fixture bump, per the three-altitude rule in
  `CLAUDE.md`.

What the harnesses in the scratch area did (reproduce each §2 defect through the real `Pipeline.run`
with Whisper and the LLM stubbed) now lives in `tests/test_pipeline_platform_transcripts.py`.

**Deliberately later:**
- **0b sticky ids**, with rename carry-over, a re-identification-key file, atomic and locked writes, and
  a migration seeded from the serve DB. Imports get birthtime = download date, so they sort last and
  renumber nothing. **So §5f, dating files to the meeting, must not ship before 0b**, or every import of
  an older meeting cross-wires stars.
- 1c, study-wide moderator codes (by platform participant id, not display name), 1e and 1f.
- Phases 3 (Teams) and 5 (Zoom), and Phase 4.

The pre-existing cross-wiring bug (§2, "adding an older recording") is still live for hand-dropped
files, and **0a alone does not protect researcher edits**. It is worth doing on its own merits, as 0b,
soon after the slice.

---

## 0a. Build on what exists — the reuse map (review, 1 Oct 2026)

This is an iterative enhancement of a feature that already ships with **~345 Swift tests in the cloud
import area** and a substantial pytest suite on the pipeline paths it touches. Every item below names
the existing code and tests it must **extend**. Where the earlier draft proposed a parallel
implementation, the verdict says so.

| Plan item | Already built and tested | Verdict |
|---|---|---|
| Download a transcript file (Zoom VTT, Graph VTT) | `CloudDownloader` + `CloudDownloadVerification`: `.part` + atomic publish, status/content-type checks, and **`MediaFormat.webvtt` with BOM handling already exists**. `CloudDownloadTests` (30), `CloudTransportTests` (33) | **Reuse unchanged.** `ExpectedFile(expectedFormat: .webvtt)` |
| Write a *rendered* VTT (Meet entries) | the same publish step | **Do not write a second atomic writer.** The draft's `PlatformTranscript.writeAtomically` duplicated it. Extract `CloudDownloader`'s publish step and call it, once the other session's edits to that file have landed |
| Zoom `Name:` → speaker | `ZoomTranscript.splitSpeaker` (`ZoomRecordingModel.swift:489`), tested in `ZoomImportTests`, including "the ratio was 3:1" | **Reuse** in the Swift VTT writer |
| Hand-dropped `Name:` files (pipeline) | `_COLON_SPEAKER_PATTERN`, and **`tests/test_international_names.py` already pins the defect as ~20 `xfail`s** (umlaut, accents, CJK, Arabic, the Zoom comma) | **Enhance the regex until those xfails pass.** No new suite. Add the false-positive cases (`Honestly:`, `Gern:`) beside them |
| VTT parsing, `<v>` tags | `s03_parse_subtitles._parse_vtt` (the design doc measured the Teams `.vtt` working) | **Extend:** read the NOTE, split multi-voice cues, unescape |
| `.docx` turns | `s04_parse_docx` with observed specimens, `tests/test_parse_docx.py` (24) | **Extend** (turn ends); specimens stay the oracle |
| Pairing recording + transcript | `_normalise_stem`, `_BN_DOWNLOAD_PREFIX_RE`, `_TEAMS_SUFFIX_RE`, `_GMEET_TAIL_RE`; `tests/test_ingest.py` (50), with real specimens | **Extend** for recurring titles (0c). The tested case "cloud video + hand-fetched transcript become one session" (the reason the prefix strip exists) must stay green |
| Splitter gate | `split_single_speaker_llm` guard; `tests/test_speaker_splitting.py` (15) | **Extend** the guard (named platform transcripts never split) |
| Names in people.yaml | `auto_populate_names`, `extract_names_from_labels`; `tests/test_name_extraction.py` | **Contract change, flagged.** `test_llm_priority_over_label` pins "LLM beats label". "Platform beats LLM" applies **only to platform-transcript labels**. Re-home that test's contract rather than invert it, because it still holds for generic labels |
| Moderator codes | `tests/test_people.py::test_multi_session_moderator_codes_collide_and_are_warned` pins the collision as a *known limitation* (Layer 11) | **Deferred** (study-wide codes are out of the first slice). That test stays as is |
| Resume caches (0a) | `tests/test_pipeline_resume.py` (37), `test_manifest*` | **Extend**; the stubbed harnesses become new cases here |
| Admin approval (Teams) | `TeamsOAuth`'s `adminApprovalRequired` classifier (AADSTS90094 / 65001) and its `signInAdminApproval` copy; `TeamsSignInFailureTests`. `signIn(scopes:)` already takes a scope list | **Reuse** for the Request Approval round trip: same classifier, same failure copy. New code is only the second `signIn` call and the bar |
| Teams listing | `TeamsSource` calendar join, `TeamsRecordingName`; `TeamsSourceTests` (30) pin the request sequence, `TeamsRecordingNameTests` (12) | **Append** the meeting/transcript calls after today's; update the sequence tests deliberately |
| Zoom adapter | `ZoomSource` / `ZoomOAuth` / `ZoomRecordingModel` (≈1,900 lines, flagged off), `ZoomImportTests` (37), `ZoomGrantTests`, Diagnostics fixtures, Store a Test Zoom Sign-In | **Carried along as is** (§1b). Additions: the VTT download, the preflight-driven Expected / No transcript states, and the multi-part pairing fix. The sign-in needs the Associated Domains entitlement restored |
| Meet listing | `GoogleMeetSource` conferenceRecords join on the scope already held; `GoogleMeetImportTests` (46) | **Extend** with `transcripts.list` / `participants.list` |
| Status column words and glyphs | `statusKind`, `StatusCellView.configure(text, kind:)`; `CloudImportStatusKindTests` | **Reuse:** the Transcript cell is the same view; *Waiting for transcript* joins the glyphless keys |
| Column sizing | `CloudImportStatusColumn.minimumWidth` + `preferredWidth` (committed `b496085c`, `1912ab56`), `reportMinimumWidth`, and `fitWindowToOpeningWidths()`, which widens the window once per open so every column fits at its opening width | **Generalise** the measurer to take a key list and give Transcript the same **minimum/preferred pair**. Add the column **in `makeNSView`, before attach**, so the one-time opening fit counts it; a column added later gets no second fit. Expect the Teams window to open ~140–175 pt wider |
| Column add/remove | `syncScheduledColumn` / `syncExpiresColumn`; `CloudImportScheduledColumnTests` | Same shape for Transcript, sharing a helper if a third copy appears |
| Scheduled, Expires, attendee line | `showsScheduledColumn`, `expiresView` (orange < 7 days), `AttendeeLine`; tested | **Unchanged** (owner decisions, 1 Oct) |
| Footer | `arithmeticLine`: **untested**. `JoinArithmetic` is tested | Move the new "show the fetchable split?" decision into a testable helper next to `JoinArithmetic` before changing it (`desktop/CLAUDE.md`: decisions belong in testable helpers) |
| Handoff | `CloudImportHandoff.decide`; `CloudImportHandoffTests` (20) | **Unchanged** (§5d) |
| Local match | `CloudImportLocalMatch`; tests (27) | **Unchanged** in the first slice (§5a) |
| File identity, if 0b ever needs rename survival | `CopyMachinery`'s proven content identity (`holdsSameContent`, 0.31.3) | **Reuse** that notion. Do not invent a third identity scheme (the reviewers' "size + duration + first-MB hash") |
| Decisions record | `docs/design-cloud-import.md` (§3, §8 and §9 hold the platform decisions) | When code lands, fold the settled decisions back into that doc. Keep this file as the implementation plan only, so the same claim doesn't live in two places |

**The genuinely new code, then, is small:**
- the transcript fetch inside each adapter's existing `fetch`;
- a Swift WebVTT *writer*, for rendering Meet entries and normalising Zoom, plus the NOTE;
- one column;
- one footer checkbox;
- the window re-checking waiting rows while it is open;
- pipeline guards and parser extensions.

Everything else is extending code that is already tested.

## 0b. What the other sessions said (1 Oct 2026)

Five sessions working nearby were asked whether their thinking is committed, and what this plan must
take on or avoid. Answers so far:

- **Speaker splitting** (experiment `3a302803`; no product code, no decisions yet, hand-labelling in
  progress):
  - **Don't change** `split_single_speaker_llm`'s sample window, its propagation, or the splitting
    prompt. That is the open question the labelling answers; the Whisper path behaves as it does now.
  - **Don't delete or freeze the splitter** because platform transcripts make it unnecessary. Bare
    video dragged in still depends on it.
  - "No names or a single account name means *speakers not separated*" is an **interim** rule, not a
    permanent one. If whole-transcript splitting proves reliable, one shared account (two people in a
    room) is exactly where a fixed splitter should run.
  - Agreed: "never split a named platform transcript", and "platform name beats LLM person_name" for
    platform labels.
  - Noted: Teams' own announcements ("Recording started by you…") turn up as speech in a Whisper
    transcript of a Teams recording. A platform transcript avoids that too.
- **Names** (investigation only, nothing to commit):
  - **1d names participants only in the first slice.** `people.yaml` and the SPA name editor both key
    on the speaker code, and every session's moderator is `m1`. So writing moderator names would make
    the last session processed win, and the SPA editor for `m1` is itself broken: it opens in every
    session with an `m1`, the editors steal focus, and the edit collapses (`SessionsTable.tsx:443`,
    measured in Chromium and WebKit). Moderator names wait for study-wide moderator identity.
  - **Don't parse names from filenames.** The owner rejected it: filename conventions are "all over
    the place".
  - "Names populate" is not "names are editable": a Mac-app editing regression is reported and
    unconfirmed. A save persists only if `GET /people` succeeded on load.
- **Import window** (status column, download progress, scope control; all committed):
  - "Queued but not processing" was download progress, not the handoff. `CloudDownloader` now samples
    bytes received, so a transcript fetched through it gets progress for free.
  - Column sizing, the opening-width fit, the Every Status fixture, status precedence and neutral
    chrome are folded into §0a and §5e.
- Still to answer: the Meet status-labels session. The status-column session's answer came via the
  import-window session above.

## 0c. The import half, written blind (1 Oct 2026) — pick up on the Mac

**On the Mac, 1 Oct 2026 (evening).** Rebased onto `main` and built. The app target compiled first
time; the test bundle needed two `#expect(xs.allSatisfy(\.keyPath))` rewritten as closures (the macro
reads a key-path argument as a throwing function) and one `== -12.4` compared at millisecond grain
(`Date` subtraction carries ~1e-7). Then **1732 passed, 0 failed**, every transcript suite by name;
pytest 5789 passed; `check-appearance-seam.sh` and `check-menu-routing.sh` clean. A code review of the
compiled half found and fixed three things:

- **Coverage measured from the last cue's end alone** accepted a transcript switched on late — cues
  from minute 30 to 40 of a 40-minute interview read as full coverage. `MeetTranscriptAssembly.coverage`
  is now the first-to-last span; `lateStartIsSparse` pins it. A hole in the middle is still not caught.
- **A refused `transcripts.list` read *Couldn't match* at listing and *No transcript* after Import**,
  because the plan stored `?? []`. `MeetTranscriptPlan.transcripts` is optional now, and a second
  refusal at fetch is `.notFetched(.notResolved)`.
- **A row whose plan a re-list wiped kept *Available* after Import** with no `.vtt` written: it is now
  *Didn't arrive* (or *Not imported* if it was still expected). Zoom's grey *Available* is decision 4
  below, unchanged.
- **The re-check could overlap a re-list** (`list()` rebuilds the plans off the main actor). The store
  now re-checks only while `phase == .loaded`, and drops answers if the listing changed during the await.

Raised and left for the owner: decision 6 below (fail closed when the duration probe fails), an arrival
re-ticking a row the researcher had deliberately unticked, and `CloudDownloader.publish` replacing a
stray `X.vtt` already sitting where the new media's transcript goes. Still unrun: the live-tenant
measurements below, and **Diagnostics ▸ Cloud Import ▸ Meet ▸ Every Status** by eye.

**Status.** The Swift half of the first slice (§0) is on the branch, **uncompiled**: written in a cloud
session with no Xcode, reviewed there by five agents (code-review, silent-failure-hunter,
what-would-james-bach-say, i18n-review, what-would-gruber-say), with every finding that could be
applied blind applied. Nothing in it has run. The half of the contract that *can* be proven without a
Mac is green: `check-locales.py --strict`, the pytest locale gates (`test_swift_i18n_keys_resolve.py`
sees every `cellKey` literal; `test_locale_key_readers.py` the orphans; `test_cloud_transcript_keys.py`
the plural forms), and a Python oracle that reproduced the three VTT goldens byte for byte. **Treat
every Swift claim below as a claim about intent until the first `test-swift.sh` run** — including the
ones in §5a–§5e that this section says are done.

### What is on the branch

Six commits, oldest first; each Swift one says "(Swift, uncompiled)" in its subject:

1. **The writer and the clock** — `PlatformTranscript.swift`: `PlatformTranscriptWriter` (§4: NOTE block,
   `<v>` per cue, escaping, `HH:MM:SS.mmm`) and `PlatformTranscriptRebase` (§5c: integer-millisecond
   shift, drop wholly-outside, clamp, count drops, tail check *before* clamping). Goldens under
   `tests/fixtures/platform-transcripts/cloud-transcript-{named,unnamed,rebased-drops}.vtt`, read via
   `#filePath` so Python and Swift pin the same bytes.
2. **Schema** — `TranscriptAvailability` on `CloudImportRow` (nine states, `cellKey`/`cellKind`/
   `bringsColumn`), `TranscriptOutcome` on `FetchOutcome.imported`, `isSelectable(includingWaiting:)`,
   `isWaitingForTranscript`, `withTranscript(_:)`, `recheckTranscripts(rowIDs:)` on the protocol.
3. **Meet transport** — `transcripts.list` once per recorded call (sequential after that call's
   `recordings.list`, so the transport tests can queue stubs), `participants.list`,
   `transcripts.entries.list`, `MeetTranscriptPlan` keyed like `driveFileIDs`, `fetchTranscript` inside
   `fetch` after the media publishes, `recheckTranscripts`, `CloudImportLocalMatch.mediaDuration(of:)`.
4. **The grid** — the Transcript column (`syncTranscriptColumn` after Size, remove-not-hide,
   `CloudImportTranscriptColumn.minimumWidth` through the real cell), the waiting row (disabled box,
   secondary title, *Waiting for transcript* in Status with a spinner), the footer checkbox
   (`CloudImportWindow.includeWaitingToggle`), `watchTranscripts()` on the window's `.task`.
5. **Strings** — ten keys in 21 locales, glossary rows for *Transcript*, the pytest gate.
6. **Review fixes** — the list below.

Tests, all unrun: `PlatformTranscriptTests`, `CloudImportTranscriptTests` (three suites),
`MeetTranscriptDecisionTests`, `MeetTranscriptAssemblyTests`, `CloudImportTranscriptColumnWidthTests`;
edits to `CloudTransportTests` (two Meet tests gained transcript stubs, one new) and
`CloudImportHandoffTests` (the outcome's new argument).

### What the review changed, applied blind

- **Slice, then judge.** `tailRunsPast` ran over the whole call's cues, so any Meet transcript that
  outlasted the recording by more than 2 s was refused — always the earlier half of a stop/restart
  recording. `MeetTranscriptAssembly.assemble` now slices entries to the recording's API window when
  `endTime` is known (counted as `slicedAfterEnd`), and the tail check runs only when it is not.
- **Every overlapping transcript must be `FILE_GENERATED`** for *Available*; one generated beside one
  still `ENDED` is *Expected*, because the generated half alone is half a conversation the pipeline
  would then trust over Whisper. `generatedBesideStartedStillWaits` replaces the first draft's
  opposite expectation.
- **A coverage floor** — `MeetTranscriptAssembly.coverageFloor = 0.5`: cues ending before the midpoint
  of the media are refused as `.sparseCoverage`, the §1a truncated-entries case made mechanical. Every
  successful fetch logs `coverage=`, so the floor can be tuned from real runs rather than argued.
- **`participantNames` returns nil on failure.** It returned `[:]`, which wrote every cue unnamed with
  `speakers: none` — the pipeline's *leave this interview unseparated* signal — and marked the row
  Imported. Entries that named participants none of whom resolved are refused (`.noSpeakerResolved`).
- **A refused `transcripts.list` at listing time reads *Couldn't match*, not *No transcript*.**
  `MeetHarvest.Record.transcripts` is optional so "could not ask" survives to the row; the
  transport test `refusedTranscriptListDoesNotClaimNone` pins it.
- **Patience on an empty list for a live call** — a call whose `endTime` Google never served no longer
  holds its recording *Expected* for ever.
- **`TranscriptOutcome.notFetched(TranscriptAvailability)`.** A row listed *No transcript* keeps that
  word after Import; `.notImported` (the cyan *skipped*) is exactly the researcher's own choice — they
  went ahead while it was *Expected*. `FetchOutcome.imported` lost its default so Teams and Zoom say
  `.notFetched(row.transcript)` explicitly. *Imported* in the Transcript column is its own key,
  `transcriptImported` (fr *Importée*, ca *Importada*; every other locale reuses its Status word).
- **The transcript half's failure cells are honest about who failed.** No listing token or no media
  on disk → `.didNotArrive`, logged; a missing plan (a re-list wiped them mid-batch) →
  `.notFetched(row.transcript)`.
- **Re-check hygiene.** `recheckTranscripts` snapshots the plans at entry and reads the token on the
  main actor; a listing grant that will not renew tells every row *Couldn't match* rather than
  spinning; the store re-checks `isFetching` after the await; an arrival ticks only a visible row with
  no outcome; `includeWaiting` resets on every `load()`; turning it off mid-batch unticks nothing.
- **Grid.** `shouldSelectItem` honours the footer checkbox (the one way round the wait was
  mouse-only); a waiting row the researcher has included and ticked stops drawing as waiting (title
  colour and Status both — `drawsAsWaiting` in the coordinator, and `Column.meeting` joined
  `refreshChangedRows` for it); the dead header over an all-waiting meeting says the wait, not
  *allAlreadyHere*; the Transcript column has a `maxWidth`; the spinner is hidden from accessibility
  and left out under Reduce Motion.
- **One atomic writer.** `CloudDownloader.publish(_:to:)` is extracted from the download's step 5 and
  `fetchTranscript` calls it (§0a's "do not write a second atomic writer").
- **`parseRFC3339` trims 6- and 9-digit fractions to 3** before Foundation's parser sees them.
- **Strings:** ko / zh-Hant / ja `includeWaiting_other` now name the counted noun; it / pt-PT /
  zh-Hant use the glossary's speaker word; fr takes the typographic apostrophe (and its
  `statusWaitingPermission` twin with it).

### Build and test on the Mac

```bash
# the whole Swift suite — through caffeinate, because the sidebar harness fails while the display sleeps
caffeinate -d -i env BN_DERIVED_DATA=/tmp/bn-dd desktop/scripts/test-swift.sh

# or only the new suites, once it builds
cd desktop/Bristlenose
xcodebuild build-for-testing -scheme Bristlenose -configuration Debug -destination 'platform=macOS,arch=arm64'
xcodebuild test-without-building -scheme Bristlenose -destination 'platform=macOS,arch=arm64' \
  -only-testing:BristlenoseTests/PlatformTranscriptTests \
  -only-testing:BristlenoseTests/MeetTranscriptDecisionTests \
  -only-testing:BristlenoseTests/MeetTranscriptAssemblyTests \
  -only-testing:BristlenoseTests/TranscriptAvailabilityTests \
  -only-testing:BristlenoseTests/TranscriptWaitingRowTests \
  -only-testing:BristlenoseTests/TranscriptStoreTests \
  -only-testing:BristlenoseTests/CloudImportTranscriptColumnWidthTests \
  -only-testing:BristlenoseTests/CloudTransportTests
```

A single test wants the trailing `()` (`desktop/CLAUDE.md`). Expect the build to fail first; the
places to look are listed next. Then the checks that cannot run here: `desktop/scripts/check-appearance-seam.sh`,
`check-menu-routing.sh`, a `test-swift.sh` run of the *whole* suite (the schema change touches every
cloud-import test), and **Diagnostics ▸ Cloud Import ▸ Meet ▸ Every Status** by eye — the twelve new
fixture rows (`st-t-*`) are there for the column widths and the glyph colours, which no test sees.

### Compile unknowns — where to look first

- `GoogleMeetSource.fetchTranscript`: `let (rebased, refusal) = MeetTranscriptAssembly.judge(…)`
  destructuring a labelled tuple; `switch availability` with a `default`; `Logger` interpolations such
  as `\(claimed ?? -1, privacy: .public)`.
- `GoogleMeetSource.harvest`: `Self.transcripts(ofRecord:)` — the local `let transcripts` shadows the
  static, hence `Self.`; written as an `if` statement because `await` may not sit to the right of `?:`.
- `usableListingToken()` is `@MainActor` on a class that is not; `transcriptPlans` is read from
  nonisolated async methods, as `driveFileIDs` already is (Swift 5 language mode).
- `TranscriptOutcome.cellKind` is `MessageKind?`; `transcriptView` binds `let kind: MessageKind?` from
  both branches of an `if`.
- `Coordinator.RowState` gained `waiting` and `awaitingGrant`; one construction site (`rowState(for:)`).
- Swift Testing shapes: `arguments:` with a `struct Row: Sendable` table and with array literals of an
  enum with an associated-value case; `try #require` then `#expect` in an `async throws` test;
  `guard case .sparseCoverage(let fraction)? = refusal`.
- `StatusCellView.configureWaiting`: an `NSProgressIndicator` in the glyph slot of an `NSStackView`,
  `NSWorkspace.shared.accessibilityDisplayShouldReduceMotion`, `setAccessibilityElement(false)`.
- `CloudImportTranscriptColumnWidthTests`: the ~103 pt fitting floor and the glyph `alignmentRect`
  widths are the parts only a Mac can measure; the oracle is Status's.
- The transport tests assume `StubURLProtocol`'s FIFO order per call is recordings → transcripts →
  `spaces.get`. With one record per test that holds; the harvest's concurrency across records is
  unchanged.

### Live-tenant measurements the code is waiting for

- **`endTime − startTime` vs the probed duration.** `recordingDurationTolerance = 1 s`; every fetch
  logs `meet_transcript clock probed= claimed= delta=`. If every row says `duration_mismatch`, the
  tolerance is wrong or the probe is — not Google. §0 item 1 asked for exactly this measurement.
- **Fractional seconds** in Google's timestamps through `parseRFC3339` (now trimmed to 3 digits).
- **`AVFoundation` duration on a Drive-served MP4** (`CloudImportLocalMatch.mediaDuration(of:)`);
  `probe_failed` in the log means the NOTE carried Google's figure and the clock check was skipped.
- **429s.** `participants.list` and `entries.list` run sequentially per fetch; the listing's
  `transcripts.list` runs once per recorded call inside the existing concurrent harvest.
- **Coverage of a finished transcript** (`coverage=`), to set `coverageFloor` from data.
- Whether `transcripts.list` ever omits `startTime` (then `overlapping` keeps it, by design).

### Owner decisions, open

1. **The footer checkbox's verb.** *Include {N} waiting on transcription* **enables** the rows; it
   does not tick them (the design says enable). Gruber: either make turning it on tick them, or rename
   it *Allow…*. Nothing changed pending the call.
2. **The spinner** in the *Waiting for transcript* cell. Gruber: drop it (glyphless grey, like
   Queued) or gate it. Gated (Reduce Motion, accessibility-hidden), not dropped.
3. **A meeting header over one ticked half and one waiting half reads mixed**, while a *held* child is
   still ignored (HIG; Gruber and Bach). code-review preferred ignoring waiting children too. Decided
   mixed — a held file is out of the batch for good, a waiting one can still join it, and *mixed* is
   what says there is more here to tick. `headerReadsMixedOverWaitingChild` carries the reasoning.
4. **Zoom lists `.available`** when the recording carries a `TRANSCRIPT` file and never fetches it
   until Phase 5, so after Import its cell reads *Available* in grey. Acceptable for a flag-off
   adapter; revisit with Phase 5.
5. **A held row's Transcript cell** shows the listing's word; its Status is blank by design. Blank
   both?
6. **`probed ?? claimed`.** When the probe fails, the NOTE records Google's duration and the clock
   check is skipped (logged). Refuse instead?
7. **Deliberately not built** (per §0's scope): the two footer rewordings and the footer arithmetic
   split (§5e); "ticked by default on next open"; the `.bristlenose/importing` sentinel; the pipeline
   reading `media-duration:`; Teams Phase 3 and Zoom Phase 5; `.sparseCoverage` has no Teams/Zoom
   analogue (no entries there).
8. **Strings left for a native reading.** i18n-review suggested ru/uk `transcriptAvailable` →
   *Доступно*, pl → *Dostępne*, cs `transcriptDidNotArrive` → *Nedoručeno*. Not applied: each current
   value agrees in gender with the glossary's transcript noun, so the suggestion is a register choice
   (impersonal, like the Status column) rather than a fix. Likewise *Speaker* glossary rows for the
   twenty locales without one (ja has it) — a glossary row is an agreed term, and these would be
   seeded from machine translations.

### Also found while writing

- `Coordinator.RowState` had no `awaitingGrant` field, so the Status cell's switch from *Waiting for
  permission* to *Queued* never redrew on its own. Pre-existing; fixed in passing.
- `transcripts.list` is the first per-record lookup made *after* `recordings.list` rather than
  alongside it; the harvest's per-call cost is one more round trip on a per-minute quota.

## 1. What each platform will give us

| | Teams / OneDrive | Google Meet | Zoom (flagged) |
|---|---|---|---|
| Recording | OneDrive `/Recordings`, `Files.Read`, no admin needed (shipped) | Picker `drive.file` grant (shipped) | recordings list, bearer download (built, flagged) |
| Transcript door | Graph `/me/onlineMeetings/{id}/transcripts` → `metadataContent` or `content?$format=text/vtt` | Meet API `transcripts.entries.list` + `participants.list` | a `TRANSCRIPT` file (`.vtt`) in the same `recording_files[]` list |
| Permission | **`OnlineMeetingTranscript.Read.All`, admin consent always required, even delegated** (VERIFIED). Lookup needs `OnlineMeetings.Read`. | `meetings.space.readonly`, **already held**, classed sensitive (VERIFIED) | the recordings scopes already requested; the Marketplace app also needs `user:read:user` and `user:read:settings` (VERIFIED missing) |
| Speaker names | `<v Name>` in VTT; `speakerName` in metadataContent (VERIFIED) | participant → display name; phone users show as a masked number (VERIFIED) | a `Name: text` prefix per cue (community samples only) |
| Timing | absolute cue times in metadataContent | per-entry start and end, absolute | relative to the recording |
| Ready when | after the meeting ends; no documented not-ready state | `FILE_GENERATED`, but entries can arrive **truncated** (4 → ~500 in one report) | appears in the recordings list only once ready, often hours later |
| Gone when | the meeting object expires, 60 days (+60 if joined or updated) | **30 days** after the meeting, entries and the whole conference record (VERIFIED) | `auto_delete_date` on each meeting |
| Kill switches | tenant: `403 GraphAccessToTranscriptsDisabled`; `403 SpeakerAttributionNotAllowed`, which falls back to text without names (VERIFIED, Jul 2026) | Workspace Business Standard and above only; 8 transcript languages | host setting "Create audio transcript"; 19 languages now, per Zoom's KB (its own pages disagree) |

**Teams, in the owner's words: "at work I can download both."** That is true, and the transcript is
indeed stored *with* the recording in OneDrive/Stream (VERIFIED). That is why `/Recordings` shows only
the `.mp4`. But Microsoft documents **no** API that reads it from there. The only supported door for an
app acting as the researcher is the Graph transcript API, and Microsoft makes that one admin-approved in
every tenant (VERIFIED on the Graph permissions reference and the `callTranscript` page). Two things
follow:

- **Recordings stay admin-free.** The transcript permissions are asked for only when the researcher
  presses **Request Approval…**, never at sign-in (§5b).
- **Sign-in may already be admin-gated today.** The app asks for `Calendars.Read` at sign-in
  (`TeamsOAuth.swift:51`). Microsoft's default consent policy ("Let Microsoft manage", the default for
  new tenants) excludes `Calendars.Read`, `Calendars.ReadBasic` and `OnlineMeetings.Read` from user
  consent (VERIFIED, policy page dated 17 Jun 2026). So on such a tenant, today's sign-in may need an
  admin too. `Files.Read` is not on that list. **Check this before Phase 3**: it might mean splitting
  `Calendars.Read` out of first sign-in as well.

### 1a. Which arrives first, how long it takes, and whether a transcript is coming

Researched 1 Oct 2026 from vendor documentation and community reports (forum reports are labelled
REPORTED).

| | Teams | Meet | Zoom |
|---|---|---|---|
| Order | either; usually the transcript first (REPORTED) | either | **recording first**, transcript later (VERIFIED) |
| One-hour meeting | recording 15–30 min, sometimes hours; transcript via Graph 5–30 min (REPORTED; no vendor figure) | transcript "usually within a few hours… up to 24 hours" (VERIFIED) | recording "about twice the recorded duration", up to 24 h; transcript "a couple of hours" after, sometimes more than a day (VERIFIED + REPORTED) |
| Does recording give a transcript? | **by default yes** — "when you record a meeting, transcription starts automatically" — but it can be stopped separately, or forbidden by policy (VERIFIED) | **no**, separate toggles; admins or hosts can make it automatic (VERIFIED) | only if the host's "Create audio transcript" is on (VERIFIED) |
| Signal that one is coming | **none documented**: Graph lists a transcript only once it is ready | **certain**: a transcript resource in `STARTED`/`ENDED` | **good guess**: the setting is on and the recording is listed without its `TRANSCRIPT` file |
| Expected → No transcript after | 4 h | 24 h | 24 h after the recording appears |

What follows for the product:

- **The import row can say "Expected" truthfully on Meet, and fairly on Zoom.** On Teams it is an
  inference for the first few hours, then *No transcript*.
- **The usual case is no wait at all.** Researchers mostly import well after the call, by which point
  the transcript has normally arrived.
- **A recording can have several transcripts**, when transcription is stopped and restarted. A row is
  built from every transcript that overlaps it.
- **Graph pairs exactly**: `callTranscript.contentCorrelationId` links a transcript to its recording
  (VERIFIED). This strengthens §5c's Teams route.
- **Zoom transcripts can silently never arrive** (REPORTED, Jun 2026). This is why a wait ends with a
  stated outcome, not an open-ended "Expected".

**Zoom corrections to the existing adapter** (VERIFIED against Zoom's OpenAPI specs):
`GET /meetings/{id}/transcript` serves the *AI Companion* transcript, not the recording's VTT, so it is
the wrong readiness check (`ZoomRecordingModel.swift:121`). Readiness is simply the `TRANSCRIPT` file
appearing in the recordings list. A stopped-and-restarted meeting has several media files and several
transcripts, so pair them by time overlap, not "first transcript" (`ZoomRecordingModel.swift:162`).
"English only" (`CloudPlatform.servesTranscript`, and the design doc) is stale. A private Zoom app
cannot be shared outside its own account, so real researchers need a published Marketplace app.

---

### 1b. Zoom: built, flagged off, never run against a real account, carried along as is

The owner is setting up the Zoom admin side over a weekend. This section brings the existing Zoom UX and
implementation into this plan **as they are**. Nothing is redesigned; the transcript work adds to it.

**What is built** (≈1,900 lines, `ZoomOAuth.swift`, `ZoomSource.swift`, `ZoomRecordingModel.swift`;
`ZoomImportTests` 37 + `ZoomGrantTests` 5; fixture states in **Diagnostics ▸ Cloud Import ▸ Zoom**,
plus **Store a Test Zoom Sign-In**). It sits behind `BristlenoseFlags.cloudImportZoom`, off by default.
Background: the parking brief in the maintainer's private handoffs, and `docs/design-cloud-import.md`'s
4 Sep note.

- **Sign-in:** public-client PKCE. The **HTTPS callback** uses `ASWebAuthenticationSession`
  `.https(host:path:)` to `https://bristlenose.app/auth/zoom`, because Zoom refuses custom schemes
  for a General App. Refresh tokens are single-use and rotate; the persistence for them is built.
- **Preflight:** one `GET /users/me/settings` reads cloud recording on/off, "Create audio transcript"
  on/off and the auto-delete settings.
- **Listing:** `GET /users/me/recordings` in month-long chunks, every page enumerated before any
  download. Each meeting **instance** (`uuid`) is one row.
- **Row as drawn:** the title is the meeting topic; **no attendee line** (the list call carries no
  roster); **no Scheduled column** (no calendar); Recorded shows the start time, with duration in
  whole minutes; Size is the chosen file; **Expires comes from `auto_delete_date`**, orange under a
  week as everywhere else.
- **Media choice:** `ZoomFileSelection.choose` **prefers the audio-only M4A** over the video files,
  and also identifies the `TRANSCRIPT` VTT. Today only the media is downloaded. Downloads use a
  bearer token, following the redirect by hand and stripping the `Authorization` header.

**Transcript work for Zoom** (Phase 5; all extensions):
- Download the `TRANSCRIPT` file beside the media, through the same `CloudDownloader` path
  (`ExpectedFile(expectedFormat: .webvtt)`).
- Normalise `Name: text` to `<v Name>` with the existing `ZoomTranscript.splitSpeaker`, then write the
  contract VTT (§4). The cue times are already on the recording's clock (`rebased-by: 0s`).
- **States:**
  - *Available*: the file is listed.
  - *Expected*: "Create audio transcript" is on and the file isn't listed yet, under 24 h after the
    recording appeared. The row waits, as on the other platforms.
  - *No transcript*: the setting is off, or nothing arrived within 24 h.
  - *No speaker names*: the VTT has no `Name:` prefixes.
- **The setting off is account-wide, so it is said once, not per row.** The bar above the grid reads
  "“Create audio transcript” is off in your Zoom settings, so recordings will import without
  transcripts." Under the "no empty columns" rule, the Transcript column is then absent. The sentence
  already exists as `ZoomPreflight.transcriptCaveat` (English, never rendered); it gets a locale key.
- `makeRow`'s `transcript: … : .unsupported` is the line its own comment says is wrong. It becomes
  Expected or No transcript using the preflight, as that comment asks.

**Corrections from the 30 Sep research** (Zoom's OpenAPI specs and KB; fix the comments and code
when Zoom resumes):
1. **"English only, every plan" is stale.** Zoom's KB (updated 29 Sep 2026) lists 19 transcript
   languages, but the default is English unless the host changes it, and Zoom's own pages disagree. A
   non-English interview can arrive transcribed by an English model. **Risk for the pipeline:** words
   in the wrong language. Measure it on a non-English test call; if it bites, a Zoom transcript in a
   language other than the one Whisper detects is refused.
2. **The readiness endpoint in the comments (`GET /meetings/{id}/transcript`) serves the AI Companion
   transcript, not the recording's VTT.** Readiness is simply the file appearing in the recordings
   list. Nothing calls that endpoint today; fix the comment in `ZoomRecordingModel.swift:121`.
3. **Scopes:** the adapter calls `/users/me` and `/users/me/settings`, which need `user:read:user` and
   `user:read:settings`. `ZoomScopes.requested` lists neither. Add them to the Marketplace app and to
   `ZoomScopes`.
4. **One meeting, several files.** A stop/restart recording carries several M4A/MP4 files and several
   transcripts. `choose` takes the *first* of each, so later parts are silently dropped. Pair media and
   transcript by `recording_start` overlap, one row per part. This is an existing defect, independent
   of transcripts.
5. **Sharing:** a private app can't be shared outside its own Zoom account (beta links need
   security evidence and expire). Fine for the weekend's own-account test; real researchers need a
   published Marketplace app.
6. **Plan:** the KB says Pro or higher for transcripts; the `transcript_completed` webhook doc says
   Business, Education or Enterprise. Measure it on the test account.

**Blocker found 1 Oct 2026: the Associated Domains entitlement is gone.** The parking brief lists it as
"banked", but it was a skip-worktree edit, removed on 12 Sep 2026 when the app group landed (`11d9cb6f`),
and the App ID's Associated Domains capability was switched off in the portal the same day.
`ZoomOAuth.presentConsent` depends on it: without it, the browser opens, the user consents, and
**nothing comes back**. The website half is fine: `https://bristlenose.app/.well-known/apple-app-site-association`
serves `200 application/json` with `webcredentials` for `Z56GZVA2QB.app.bristlenose` (measured 1 Oct).

**Weekend checklist** (parking brief steps, updated):
1. **Zoom:** one Pro seat (£11.99, monthly). Turn on **cloud recording** and **"Create audio
   transcript"** *before* recording anything; neither applies retroactively. On a multi-seat account,
   pre-approve the app in the admin console (Marketplace pre-approval is on by default).
2. **Marketplace General App:**
   - Use Public Client OAuth; take the *public* client ID.
   - Redirect and allow list: `https://bristlenose.app/auth/zoom`, strict match.
   - Scopes, all **required**: `cloud_recording:read:list_user_recordings`,
     `cloud_recording:read:list_recording_files`, `user:read:user`, `user:read:settings`.
   - Don't submit for review.
3. **Apple side (code + portal):**
   - Re-add `com.apple.developer.associated-domains = ["webcredentials:bristlenose.app"]`
     (`webcredentials`, not `applinks`; an `applinks`-only entry hangs) to `Bristlenose.entitlements`
     and `BristlenoseDebug.entitlements`. Decide whether the Developer-ID `.dmg` carries it too.
   - `tests/test_entitlements_split.py` pins exactly which keys differ between the files: update it in
     the same commit.
   - Re-enable Associated Domains on the App ID and regenerate the **Manual** Mac App Store profile, or
     the next release archive fails to sign. Debug signing re-mints automatically.
   - `swcutil reset` if a failed lookup is cached.
4. **Wire the client:** `defaults write app.bristlenose ZoomOAuthPublicClientID "<id>"`,
   `defaults write app.bristlenose ZoomOAuthRedirectURI "https://bristlenose.app/auth/zoom"`, and
   `defaults write app.bristlenose BristlenoseCloudImportZoom -bool YES`.
5. **Record two short test calls, one in a language other than English**, and wait (roughly twice the
   recording's length, plus the transcript). Then sign in, list, import, and check: the bytes arrive;
   the M4A is chosen; Expires shows; the VTT exists and its speaker names parse; and the transcript's
   language (correction 1).

## 2. What happens today when a transcript sits beside a video

| Link | Today | Evidence |
|---|---|---|
| Import downloads the transcript | **No**, on all three platforms | `TeamsSource.swift:762`, `GoogleMeetSource.swift:1486`, `ZoomSource.swift:656`: media only |
| Recording + transcript become one session | Yes, by filename stem | MEASURED; `s01_ingest.py:388` strips BN's download stamp |
| Transcript used instead of Whisper | Yes | MEASURED; `s02_extract_audio.py:67`, `pipeline.py:2942` |
| Splitter skipped when 2+ names | Yes | MEASURED; `s05b_identify_speakers.py:219` |
| **Transcript arriving after the video was analysed** | ~~**Ignored** if the same batch brings a new recording; otherwise it re-Whispers *every* session~~ **Fixed 1 Oct 2026 (0a)**: the changed session is redone, the rest are kept | MEASURED, real `Pipeline.run` with stubs; pinned in `tests/test_pipeline_platform_transcripts.py` |
| **Adding an older recording** | **Cross-wires sessions**: one interview's transcript under another's id; a researcher's star and typed name move to a different interview; the wrong video plays | MEASURED through a scratch serve DB. Pre-existing, not cloud-specific |
| Same-titled meetings on different days | ~~**Merged into one session**~~ **Fixed 1 Oct 2026 (0c)** | MEASURED; grouped by (stamp, title) |
| One named speaker (in-room interview) | ~~Splitter overwrites the real name with "Speaker A/B"~~ **Fixed 1 Oct 2026 (1b)**: kept whole, stated | MEASURED |
| Non-ASCII names in `Name: text` files | ~~Lost (`José Álvarez` → no speaker); "Honestly:" becomes a speaker~~ **Fixed 1 Oct 2026 (1c)** | MEASURED |
| Moderator names | All sessions' `m1` share one name, sometimes the wrong person's (open: 0b / study-wide codes); ~~a platform name loses to the LLM's guess ("Pri")~~ **participants fixed 1 Oct 2026 (1d)** | MEASURED |
| `.docx` turns | zero duration: talk time 0%; the transcript page highlights the *next* turn | MEASURED / INFERRED |
| `.vtt` + `.docx` for one meeting | ~~every turn twice~~ **Fixed 1 Oct 2026 (0d)**: one is used, the other stated as superseded | MEASURED |
| Refused `.docx` beside a video | the session is lost; no Whisper fallback | MEASURED |

The last eight rows are pipeline defects that bite **hand-dropped** transcripts today. Import makes
them routine.

---

## 3. The plan, in order

Each phase ships on its own and leaves `main` better.

**Phase 0: stop the pipeline corrupting a project (pipeline, M).** This comes first because every
later phase adds files to existing projects, and adding files is what triggers the damage.

- **0a Interim guard (S).**
  - Record each session's file list in `SessionRecord`. Discard every per-session cache (transcribe,
    speaker-info, topics, quotes) for a session id whose file list changed.
  - In `_is_speaker_stage_verified` (`pipeline.py:~305-341`), check input hashes before the
    file-exists loop.
  - This fixes the ignored late transcript and the pipeline-side cross-wiring.
  - Test: `test_late_transcript_with_new_recording_is_not_ignored`.
- **0b Sticky session ids and sticky speaker slots (M).**
  - Add `<output>/.bristlenose/sessions.json` mapping the session grouping key to a sid, and
    `(session key, speaker label)` to a speaker code.
  - Migrate by seeding from the `# Source:` headers in `transcripts-raw/`, so upgrading never
    renumbers.
  - This is `docs/design-people.md` decision 1 (codes are globally numbered *slots*) made stable. It is
    the only fix that protects researcher edits: stars, tags and typed names stay with their interview.
  - Tests:
    - `test_session_ids_are_sticky_when_an_older_recording_arrives`
    - `test_adding_an_older_recording_does_not_cross_wire_transcripts`
    - `test_star_stays_with_its_interview_after_an_older_recording_is_added`
    - `test_typed_name_stays_with_its_speaker_after_a_session_is_inserted`
    - migration test
- **0c Recurring meetings stay separate (S).**
  - A file carrying BN's `YYYY-MM-DD HHMM — ` stamp is grouped by (stamp, title).
  - An unstamped file joins a stamped group only when **exactly one** group matches.
  - Prototyped on 7 filename sets.
  - Tests in `tests/test_ingest.py`: `test_recurring_bn_titles_stay_separate`, and two siblings.
- **0d One transcript per session (S).**
  - Precedence: cloud VTT, then other VTT/SRT, then DOCX. The others are recorded as superseded, not
    silently dropped.
  - A refused transcript beside media falls back to Whisper (M).

**Phase 1: the pipeline trusts platform names (pipeline, M).** Hand-dropped transcripts benefit
immediately.

- **1a Read the provenance NOTE** (§4); the colon heuristic is off for those files. Split multi-voice
  cues into one segment per voice.
- **1b The splitter never runs on a named platform transcript.**
  - Zero names: split on the transcript's own cues, without Whisper.
  - Exactly one name means *the account*, not a voice (product call Q3, §8).
- **1c File-level `Name:` rule.**
  - Accepted as speaker names only when ≥60% of cues carry one, there are at most 8 distinct names, and
    each appears at least twice.
  - Names may be Unicode, and may carry `(Guest)`; the colon may be fullwidth.
  - Rejects `Honestly:`, `Note:` and German `Gern:`.
- **1d Names.**
  - Every named **participant** gets a name, not just the dominant one. **Moderators are not named
    from labels in the first slice** (§0b: one `people.yaml` entry per code, and the `m1` editor bug).
  - The platform name beats the LLM's `person_name`.
  - A masked phone label is never a name.
  - **Platform-named moderators get study-wide codes by display name**: Martin is `m1` in every
    session, Mike `m2`. Product call Q4.
- **1e `.docx` turns get real ends.** Each turn ends at the next turn's start, capped by a
  words-per-second estimate; the last turn ends at the media's duration.
- **1f Language.** The transcript's language comes from its NOTE, as a BCP-47 tag (`de`, `pt-BR`,
  `en-US`), reduced to the primary subtag only for Whisper. The header reads
  `# Language: de (transcript)`. A previous Whisper "en (detected)" is never carried onto it.

**Phase 2: the pair in the import window, Meet first (Swift, M–L).** Meet needs **no new permission**,
so it proves the whole chain end to end at the lowest cost.

- Schema, grid, handoff and the shared `PlatformTranscript.swift` (§5).
- **Meet transport.**
  - List `transcripts` for their state, and `participants` for names.
  - Page the entries, slice them to each recording's `[startTime, endTime]`, and rebase to the
    recording's t=0.
  - Accept the transcript only once two reads at least 60 s apart return the same entry count
    (truncation).
  - If the recording's `startTime` is absent, the transcript is refused (`.notResolved`), never guessed.
- Waiting rows (Expected) are not importable unless the researcher includes them (§0 item 2), so there is no analysis hold and no change to `CloudImportHandoff` (§5d).

**Phase 3: Teams (Swift, L).**

- Incremental admin consent (§5b).
- Meeting lookup: calendar event → `joinWebUrl` → `onlineMeetings` → `transcripts`.
- Exact pairing and t=0 by `callRecording`, which needs `OnlineMeetingRecording.Read.All` in the
  **same** admin approval (§5c).
- Cues from `metadataContent`.
- Both 403 kill switches.
- **Dogfooding needs a tenant where you are the admin**, or an admin willing to approve (Q1).

**Phase 4: a late transcript re-processes only its own session (pipeline, M–L).**

- Per-session input fingerprints through transcribe, speaker ID, topics and quotes. The quote input
  gains the transcript hash (MEASURED: stale quotes).
- Then the handoff's "transcripts only" decline becomes "analyse". One `case`, pinned by a test.

**Phase 5: Zoom, when unparked (Swift, S–M).** Built adapter, corrections and weekend checklist in §1b.

- Download the VTT alongside the media and convert `Name:` prefixes to voice tags.
- Readiness means the file appears in the list; re-list with back-off and give up after 24–48 h.
- Pair media and transcript by time overlap.
- Fix the scopes and the wrong readiness endpoint.
- Plan a Marketplace listing.

**Not in this plan:**

- Meet's Doc-tab fallback after the 30-day expiry (v2).
- Transcript-only rows for invitees (Q2).
- Merging a platform transcript's names with Whisper's words (§8 of the cloud-import doc; separate
  study).
- The Stream player's undocumented transcript endpoint: tempting, unsupported, not shipped.

---

## 4. The file contract between import and pipeline

Agreed between the two working sessions and measured through `s01`/`s03`.

1. **Name.** Beside the media, with the **byte-identical stem** including any ` (n)` part:
   `2026-09-24 0934 — P07 Interview.mp4` + `2026-09-24 0934 — P07 Interview.vtt`. Built by
   `CloudDownloadNaming.filename(…, fileExtension: "vtt", part:)` from the media's own `startsAt` and
   `part`, never derived twice.
2. **Format.** Always *our* writer's WebVTT, UTF-8, never vendor bytes verbatim. Cue times are relative
   to the **media file's t=0**, with end > start.
3. **Cues.** Exactly one `<v Display Name>text</v>` per cue (MEASURED: a two-voice cue gives the whole
   cue to the first voice). No `Name:` prefix is left in the text. An unnamed transcript has **no**
   `<v>` at all, and never an invented "Speaker 1".
4. **Provenance** (MEASURED: webvtt-py skips it):
   ```
   WEBVTT

   NOTE bristlenose-cloud-transcript 1
   source: teams|meet|zoom
   speakers: named|none
   language: pt-BR
   media: 2026-09-24 0934 — P07 Interview.mp4
   media-duration: 3131.420s
   rebased-by: -12.400s
   dropped-outside-media: 3
   ```
5. **Order.** `.part` then an atomic rename, published **after** its media. A lone cloud `.vtt` never
   lands, because it would become a text-only session.

---

## 5. Import side

### 5a. Schema (`GoogleMeetModel.swift`, `CloudImportSource.swift`)

**Smallest change that carries a pair; revised 1 Oct 2026 against what is built.**

- **A row stays one recording.** Its transcript is a *half* of the row. Row ids, ticks, outcomes and
  the outline's grouping of several recordings under one call are unchanged.
- **The transcript field already exists and is not replaced.** `CloudImportRow.transcript`
  (`GoogleMeetModel.swift:520`, init `:597`) is filled by all three adapters and read by nothing.
  The first slice **fills it honestly and renders it**. Whether it grows into a `TranscriptPlan`
  struct, or the existing `ArtifactAvailability` gains the few new cases (Expected, No speaker names),
  is decided when the code is in front of us. Extending the enum keeps the compiler pointing at every
  exhaustive switch (`isWithheld`, `statusKind`, `statusLabel`). Those switches are tested, and that
  is a reason to extend them, not to work around them.
- **`fetch(row:destination:progress:)` keeps its signature.** The adapter fetches the transcript
  inside the same call, after the media is published. `FetchOutcome.imported` gains an optional
  transcript artifact and shortfall. The `parts:` parameter and "fetch only the missing half" belong
  to the deferred missing-half work (§0 item 4), so they are not built now.
- **`CloudImportLocalMatch` is not changed in the first slice.** Its duration matching is deliberate
  (researchers rename files) and has 27 tests. It changes only when missing-half fetching returns.
- **Waiting rows** (Expected) become non-selectable through the existing `isSelectable` /
  `drawsTicked` / meeting-header path. That is the code `CloudImportModelTests` and
  `CloudImportOutlineTests` already pin; extend those tests, don't write a parallel selection model.

### 5b. Teams incremental consent

The shape, with the full sequence diagram in the import report:

1. Sign-in stays `Files.Read`, `Calendars.Read`, `User.Read`, `offline_access`.
2. The listing marks transcripts `.needsAdminApproval`, shown as **one banner** with
   **Request Approval…**.
3. That runs a second authorisation adding `OnlineMeetings.Read`, `OnlineMeetingTranscript.Read.All` and
   `OnlineMeetingRecording.Read.All`.
4. Microsoft shows its own "request approval" form. The admin approves in Entra, and Microsoft emails the
   researcher.
5. The app never observes the decision; the next token either carries the scopes or it doesn't.

A test pins that no admin-gated scope is ever in first sign-in
(`transcriptScopesNeverInFirstSignIn`).

### 5c. Putting the transcript on the video's clock (the silent-failure risk)

A transcript whose t=0 is wrong by δ shifts every clip, every deep link and the word glow by δ, while the
text and speakers look perfect. That is the expensive invisible error in medical UR. So:

- **Where t=0 comes from.**
  - Meet: the recording resource's `startTime`.
  - Zoom: native.
  - Teams: `callRecording` `createdDateTime`, matched to the OneDrive file by duration and end time,
    and to the transcript by `contentCorrelationId`.
  - Teams without the recording permission would need the mp4's `creation_time` atom and the filename
    stamp to agree within 2 s. Both are unmeasured, so that route does not ship alone.
- **Rebase rule.** `s = S − t0`. Drop a cue that falls wholly outside `[0, D]`, clamp the rest, count
  the drops, and never produce a negative time.
- **Checks.**
  - Swift refuses the transcript (`.notResolved`) if the tail runs past `D + 2 s`, or if two t=0
    sources disagree.
  - The pipeline later slides the cues against `ffmpeg silencedetect` speech intervals (±30 s). If the
    best fit is not within ±1 s of zero, it marks the session misaligned and falls back to Whisper.
    This is an optional Phase 1/3 item.
- **One live measurement per platform before shipping**: Teams callRecording start against the video's
  t=0, and whether Meet's recording `startTime` is actually present.

### 5d. When analysis starts

**No change to `CloudImportHandoff`** (revised 1 Oct 2026). Waiting rows are never imported unless the
researcher includes them (§0 item 2), so everything that lands is ready to analyse. The existing rule,
"a folder-shaped batch that landed something analyses", stays as it is, with its 20 tests in
`CloudImportHandoffTests`. The earlier draft's `.transcriptsPending` / `.transcriptsOnly` declines
and "Analyse Without Transcripts" are **withdrawn**. The window's footer checkbox replaced them.

### 5e. The grid

See `docs/mockups/cloud-import-transcript-pairs.html`.

- **One checkbox per recording** fetches everything that belongs to it.
- **Option A (decided 1 Oct 2026):** a **Transcript** column placed **after Size** (before Status when Expires is absent, as on Meet; `syncExpiresColumn` already moves Expires to just before Status).
  - **Width rules from the Status-column session (1 Oct):**
    - Call the sync before `reportMinimumWidth`, and `sizeToFit` when a column grows above its minimum.
    - Measure glyphs by `alignmentRect`.
    - `StatusCellView`'s fitting size never drops below ~103 pt.
    - The spinner state takes the glyph's slot: measure it through the cell.
    - Register Transcript in `openingWidths`.
    - Classify the new keys so `everyStatusKeyIsClassified` passes, and give Transcript its own classified list and oracle test.
    - **Today's Teams floor is already ~769 pt in English and ~834 pt in Italian** (Status's English minimum is 133 pt). Quote measured figures, not the estimates below.
  - **Sized like Status** (committed `b496085c`). A `CloudImportTranscriptColumn.minimumWidth(i18n)`
    measures every transcript state through the real cell, in the active language.
    `reportMinimumWidth` already sums the column set and hands it to the window (`onMinimumWidth`,
    floor `max(760, grid)`).
  - **Added and removed by a `syncTranscriptColumn`** shaped like `syncScheduledColumn`, never
    hidden, so `autosaveTableColumns` cannot restore a stuck-hidden column. It is present only when
    some row could have a transcript.
  - **Width cost** (estimated; the code measures it): about 142 pt in English and 175 pt in German. The
    Teams window's floor goes from 760 to about 820 pt in English and 880 pt in German. Meet, which
    has no Expires column, is about 90 pt narrower.
- **Scope guard (owner, 1 Oct 2026): the goal is the pair plus this one column.** The Teams window is
  otherwise drawn exactly as it ships (Meeting from the filename, Recorded, Size, Expires, Status). No
  new calendar-derived UI.
- **Columns are shown when they would have something in them: no empty columns** (owner,
  1 Oct 2026). This is not an "every row populated" test. Permission is usually all or nothing, but it
  can arrive partway through the window, and then some calls have data and some don't, which is fine.
  - **Scheduled on Teams: take it when we can get it.** Today's rule already does this.
    `showsScheduledColumn` (`CloudImportOutline.swift:272`) shows the column if *any* row has a time.
    So no permission gives no column (the shipped Teams window, screenshot 1 Oct). Permission with
    some matches gives the column, with blanks for calls that have no event. **No code change.** A
    refused calendar read doesn't need telling apart from an empty one, because both mean no column.
    Calendar access would arrive with the transcript approval: `Calendars.Read` is already in the
    app's requested permissions.
  - **Transcript follows the same rule.** `syncTranscriptColumn` adds the column when at least one row
    has a transcript to show or one on its way. Every row "No transcript", or an account that can't
    have one, means no column.
- **The window is for recognition, not inspection** (owner, 1 Oct 2026). The researcher ticks the
  right calls by day, meeting title, then the external names from the invite (the existing attendee
  line: you dropped, decliners dropped, outsiders first). That is enough. The Transcript cell reports
  availability only. Speaker counts, speaker names, and using transcript speakers to fill the attendee
  line are all **out of scope at this point in the flow**; that information belongs after import.
- **Transcript states and their kinds (agreed 1 Oct 2026).** The cell reuses `StatusCellView.configure(text, kind:)`, so a kind looks identical in Transcript and Status. The word and the glyph are tinted together: success green `checkmark.circle`, info blue `info.circle`, warning orange `exclamationmark.triangle.fill`, error red `xmark.circle.fill`, skipped cyan `minus.circle.fill`. Pending has no kind and is drawn as glyphless grey (per `bristlenose/ui_kinds.py`).

  | Cell | Kind | Teams signal | Meet signal | Zoom signal | Tick |
  |---|---|---|---|---|---|
  | Available | none (plain grey) | transcript paired by `contentCorrelationId` | `FILE_GENERATED`, count settled | `TRANSCRIPT` file listed | ticked |
  | Expected | none (glyphless); Status says *Waiting for transcript* | recording < 4 h old, none yet (inference) | `STARTED`/`ENDED`, or still settling (certain) | setting on, no file, < 24 h | **disabled**; the footer's *Include {N} waiting on transcription* enables it |
  | No transcript | info | none after 4 h | no transcript resource on an ended call | setting off, or none after 24 h | ticked; Bristlenose transcribes |
  | No speaker names | info | `403 SpeakerAttributionNotAllowed` (text only) | — | VTT without `Name:` | ticked; speakers left unseparated |
  | Needs approval | glyphless; the bar carries the warning | transcript permission not granted | — | — | ticked |
  | Needs access (`statusNeedsAccess`) | warning | — | `meetings.space.readonly` declined | — | ticked |
  | Unavailable (`statusUnavailable`) | warning | `403 GraphAccessToTranscriptsDisabled` | edition or language | plan | ticked |
  | Couldn't match (`statusNotResolved`) | warning | no recording with that correlation id, or the timing check fails | `startTime` missing, or the duration check fails | — | ticked; Bristlenose transcribes |
  | No longer available (`statusNoLongerAvailable`) | warning | meeting object expired | 30 days | auto-deleted | ticked |
  | In this project | info | — | — | — | disabled, as today |
  | *after a fetch:* Imported | success, regular weight | | | | |
  | *after a fetch:* Didn't arrive | **warning** (the row is partial) | | | | |
  | *after a fetch:* Not imported | skipped (you went ahead without waiting) | | | | |

  Deliberately not shown (recognition, not inspection): speaker count or names, language, partial
  coverage, STARTED vs ENDED, and "Requested" (the app can't observe the admin's decision). Six of the
  cells reuse existing Status words or kinds. The new strings are Available, Expected, No transcript, No
  speaker names, Needs approval, Imported, Didn't arrive and Not imported.
- **Footer arithmetic: show the fetchable/withheld split only when it is work for the researcher**
  (owner, 1 Oct 2026). The footer leads with the bold count ("**7 meetings**", or "3 meetings ·
  **4 recordings**" where Meet has more recordings than meetings). "· N you can fetch" is added only
  when some row is withheld **for a reason the researcher could act on**. Implement it as the
  existing `counts.withholding` predicate (`isWithheld`, `GoogleMeetModel.swift:699`), which already
  decides the permissions link. Every footer state is drawn in the mockup's frame 6.
  - Needs access, Needs a paid plan and Unavailable: re-consent, or ask IT.
  - Someone else's meeting: ask the organiser. The existing "N organised by others" clause is
    already this case.

  Rows withheld for reasons that need no thought don't trigger the split:
  - In this project: already here.
  - Not recorded: nothing to get.
  - No longer available: gone, and the row's Status already says so.
  - Waiting on transcription: the "Include {N} waiting on transcription" checkbox already speaks for it.

  The code is `arithmeticLine` in `CloudImportWindow.swift` (that file's other work is committed as of
  1 Oct). It extends the footer's existing rule of mentioning recordings
  only when they differ from meetings.
- **Two shipped footer strings reworded** (owner, 1 Oct 2026): `footerOrganisedByOthers` "{{count}}
  organised by someone else" → "{{count}} organised by others", and `footerPermissionsLink` "About
  recordings permissions" → "Recordings permissions". Each is a 21-locale change (reword `en` and
  propagate in the same commit; CLAUDE.md i18n). `it/desktop.json`'s pending edit is committed.
- A blanket refusal is **one bar** (a system Label), not N badges. The admin-consent sheet is about 67
  words.
- **The footer gets one plural key per clause:** "7 meetings · 6 you can fetch · 3 transcripts · 1
  transcript expected". The button names transcripts only when a tick fetches one alone.
- **Strings.** About 25 new keys × 21 locales. Look for already-translated twins before seeding ("Not
  Now"), and add glossary rows (Transcript in every locale; administrator vs IT team) first.
- **Every Status fixture** (Diagnostics ▸ Cloud Import ▸ ‹platform› ▸ Every Status, `everyStatusRows` / `diagnosticSeed` in `CloudImportSource.swift`) gets every new state: Available, Expected, No transcript, No speaker names, Needs approval, Didn't arrive, Not imported, Waiting for transcript. The owner checks column widths by eye there. **Status precedence** in `statusView` stays progress > outcome > awaiting grant > Queued > row label. A disabled *Waiting for transcript* row goes through the row-label path, so it can't collide with Queued. **Chrome stays neutral:** the footer checkbox and any new non-link text stay out of the window's tint (the scope control lost its blue on 30 Sep).

### 5f. Also found

The downloader sets no file dates, so an imported meeting is dated the day it was **downloaded**
(`s01_ingest.py` reads birthtime). Set the files' creation and modification dates to the meeting start
(S, Swift).

---

## 6. Tests

Every test above is named in the reports. The rule for all of them: **each is written red against today's
tree first** (the harnesses already reproduce every defect), then turned green. Swift tests run through
`desktop/scripts/test-swift.sh`. The pipeline tests are ports of the stubbed harnesses.

---

## 7. Effort and risk

| Phase | Effort | Main risk |
|---|---|---|
| 0 pipeline safety | M | migrating existing projects without renumbering: a fixture per real project shape |
| 1 names | M | the single-account rule (Q3) |
| 2 Meet pair + schema + grid | M–L | truncation threshold unmeasured; `startTime` presence unmeasured; 30 keys × 21 locales |
| 3 Teams | L | admin consent is outside our control; publisher verification may be needed for the multi-tenant registration; t=0 needs one live measurement |
| 4 per-session fingerprints | M–L | cache-invalidation bugs are silent: prove each red first |
| 5 Zoom | S–M | Marketplace publication |

App Store: no new entitlement. Import is ingress; consent was already settled on 22 Aug 2026.

---

## 8. Questions for the owner

- **Q1 Teams test tenant.** **Answered 1 Oct 2026: yes, a tenant with an admin is set up**, so Phase 3 can be
  dogfooded end to end, including the approval flow. The rest of the question stands: Do you have a Microsoft tenant where you are the admin, so the approval can
  be granted and Phase 3 dogfooded? And will your clients' IT approve a third-party app reading meeting
  transcripts? If they typically won't, the manual fallback (Stream player ▸ Download `.vtt`, drop it
  in) needs to be a first-class, documented path. Phase 1 already makes it work well.
- **Q2 Transcript-only rows.** Invitees can read a meeting's transcript without owning its recording.
  Offer those as text-only sessions? Proposed: **no** for v1, so every session keeps its recording.
- **Q3 One account, two people in the room.** When a transcript names one account for everyone: keep
  the platform text and mark the session "speakers not separated" (proposed), or fall back to Whisper
  plus the splitter?
- **Q4 Moderators across sessions.** When the platform names the moderator, should they get a
  study-wide code (Martin = `m1` everywhere)? This fits decision 1 in `docs/design-people.md`.
- **Q5 The grid.** **Decided 1 Oct 2026: Option A**, a Transcript column, measured and added or removed
  the way Status and Scheduled already are (§5e). Speaker names go in the cell's tooltip.
- **Q6 Holding analysis.** **Answered 1 Oct 2026: wait for the transcript, by leaving the row unticked
  and saying "Expected"** (§0 item 2, §1a). The question below is kept for the record: Is **Analyse Without Transcripts** the right verb, or should the default be
  "analyse now, and say so"?
- **Q7 Order.** The plan puts Meet before Teams because Meet needs no new permission and proves the
  chain. Teams is the one you use at work. Keep that order?
- **Q9 Guest researchers.** Contractors often join a client's Teams as a *guest*. A delegated token from
  their own tenant probably cannot read the client tenant's transcripts. Is that how you and your cohort
  work? If so, Teams transcript import helps only researchers employed by the client, and the manual
  `.vtt` drop matters more.
- **Q10 Publisher verification.** Microsoft tenants that allow only verified publishers refuse an
  unverified multi-tenant app outright, possibly already at today's sign-in. Are you willing to verify the
  app in Microsoft's Partner Center before Phase 3? We should also give researchers a paste-able
  justification and a one-page data-flow statement for the admin (what is read and kept, and which LLM
  provider receives the text).
- **Q11 Renamed files.** Your routine is download, rename, sometimes trim. Should a transcript fetched
  later find its recording by a platform id stored on the file (an extended attribute that survives
  renaming), accepting that some sync clients drop extended attributes?
- **Q8 Sessions table order.** With sticky session ids, an older interview added later becomes `s7`.
  Sort the table by date instead of id?
