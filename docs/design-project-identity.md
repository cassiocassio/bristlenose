---
status: decided; phases 2, 4 and 5 built; 3 obviated; 6 half built, search needs a decision
last-trued: 2026-10-15
trued-against: HEAD@main on 2026-10-15
---

## Changelog

- _2026-10-24_ — a plain-terms summary under the status line: the problems designed out, the mechanism for each, and what might still bite, ranked. The owner marked everything from item 3 down low priority, for one day.

- _2026-10-23_ — §5: a session keeps the recording it was keyed by as its primary while it is in the group, so a later video cannot make it "new"; and an analysed session keeps the files it was analysed from, a file joining it later set aside as `added_after_analysis` (decision #129). Anchors: register row 57; `tests/test_late_file_set_aside.py`.

- _2026-10-21_ — §11a: identical *transcript* files with no recording fold too (decision #97), the copy set aside as `duplicate_transcript`. Anchors: register row 55; `TestDuplicateTranscript` in `tests/test_pipeline_duplicate_recording.py`.

- _2026-10-20_ — §11a's first departure closed (R49): identical bytes under two names are one session again, as §5 said; the copy is set aside and stated, its transcription never paid for. Anchors: register row 55; `tests/test_pipeline_duplicate_recording.py`.

- _2026-10-15_ — phases 2, 4 and 5 built: the marker, one study per database with fork collapse, content fingerprints and registry version 3, transcription keyed by content, the Re-analyse carry (2); the sidebar reads the marker, follows a moved folder and re-mints a copy (4); agent access keyed by study (5). Phase 3 is obviated. Phase 6 built the same day: Locate… searches for a study by id through a visible beacon file, and a copy's row says where it came from (§13a). §11a records where the build departed from this note.

- _2026-10-13_ — trued up: §2 carries the live S9 reproduction and the watcher route; §7 the Bin rule; §10 the WAL lag on the fork signal. Anchors: register rows 29, 35; `eb8509e1`.

# Project identity without paths

**Status: decided 13 Oct 2026, with the owner. Phases 2, 4, 5 and 6 built 15 Oct 2026;
phase 3 obviated (§13a).** Rows 29, 30 and 31 of
[design-lifecycle-failure-modes.md](design-lifecycle-failure-modes.md) are the
failures this closes.

## In plain terms (24 Oct 2026)

A summary for anyone arriving cold. The numbered sections below are the
design; §11a and §12 are the detail behind every line here.

The aim: a researcher can move, rename, copy or tidy their files, and
Bristlenose follows along, keeping their stars, tags and participant numbers.

### Problems designed out, and what does it

1. **Moving or renaming a study folder lost the study.** A study used to be
   its folder path, so a moved folder vanished from the sidebar or came back
   as a second, empty study, with the curation stranded on the old one (the
   12 Oct empty-report incident).
   *Mechanism:* each study carries its own ID inside `bristlenose-output/`, a
   hidden marker (`.bristlenose/study.json`) and a visible
   `bristlenose-study.txt` that Spotlight can find. The path is only a hint:
   tried first, checked, searched for when wrong. **Locate…** finds a moved
   study by its ID, not its name.
2. **Copying a study folder made two folders share one identity.** The copy
   could go on receiving the original's writes, or its agent access.
   *Mechanism:* the marker records where the study was created, so a folder
   found somewhere else is a copy and is given a new ID of its own. Its row's
   tooltip says "copied from…", and agent access stays with the original.
3. **Renaming or moving an interview file cost its curation**, renumbered
   participants and paid for transcription again.
   *Mechanism:* a recording is identified by its contents, a fingerprint of
   its size plus hashes of its first and last megabyte (§5). A file is matched
   to a session by content first, then its last known place, then its name,
   and a weaker match never takes a session a stronger one holds (§6).
4. **iCloud and Dropbox online-only files.** A file could not be recognised
   without downloading it, and one renamed while online-only was downloaded
   twice and treated as a new interview.
   *Mechanism:* each file's last known fingerprint is remembered, so an
   online-only file is not fetched when another interview is added. It is
   fetched early only when a session is missing and nothing else can identify
   it, and a download that times out stops the run with that reason rather
   than guessing.
5. **A file re-exported under the same name** would have played the new
   video against quotes timed to the old one.
   *Mechanism:* on import, the file's contents are checked against the
   session's fingerprint. Different contents are a different recording; the
   old session shows as missing and keeps its curation.
6. **Smaller problems, each fixed:**
   - The same recording or transcript dropped twice is one session, the copy
     set aside and named (§11a, first bullet).
   - A study analysed from Teams transcripts alone was renumbered once its
     recordings arrived.
   - Re-analyse lost stars and the "copied from" note; both carry over,
     matched by content (§8).
   - An old database holding two project entries is merged onto the curated
     entry at every import (§10).
   - On the Mac, a Spotlight result always goes through the open panel, which
     grants the sandbox permission; an ejected disk is not a move; one folder
     reached by two paths is not a copy.
   - On Windows, a file replace retries while another process holds the file
     open, and the server releases its database and logs when it stops.

### What might still bite, worst and likeliest first

The first two are the ones a typical Mac researcher may meet. **Everything
from 3 down is low priority, for one day** (owner, 24 Oct 2026): each needs an
unusual sequence, a small population, or is presentational.

1. **Trimming or re-exporting an interview after it has been analysed.** By
   design this is a new session, and the stars and tags stay on the old one,
   now shown as missing. Researchers do sometimes trim, so it is the likeliest
   to come up. There is no "this is the same interview, re-exported"
   affordance yet (§12).
2. **Two things were never tried by hand.** Locate-by-ID has not been run in
   the real sandboxed app (its tests drive the flow through a stand-in for the
   search), and OneDrive on the Mac has not been measured, only Dropbox (§12).
   Either could simply fail to work.
3. *Low priority.* **A cloud folder whose provider is signed out, or a network
   share, reads as a moved folder.** The "is the disk there?" check
   understands only `/Volumes/…`. The likely result is a confusing "can't
   find" or a second sidebar row, not lost data.
4. *Low priority.* **The app and the command line open on one study at
   once.** There is no lock; database writes queue safely, but two imports can
   race (§12, row 32).
5. *Low priority.* **Windows OneDrive online-only recordings are downloaded on
   every run.** Windows' kind of online-only file is not detected (§12). Slow
   and costly in bandwidth, command line only, a small population.
6. *Low priority.* **A different interview saved at the same path from another
   device** while the original was online-only inherits the old session and
   transcript, with no log line. The most severe of these, since it attaches
   the wrong participant, but it needs an unusual sequence; the import check
   refuses the new video once it downloads, though the old transcript stays.
7. *Low priority.* **A command-line fetch timeout ends in a Python
   traceback**, and the wait of up to 30 minutes prints nothing. It looks
   broken and is not; the Mac app shows a proper failed run.
8. *Low priority.* **Rare cases, each needing an odd sequence** (§11a):
   - A drop onto an ejected disk's row that was really a move leaves the old
     row behind; there is no merge on relocate.
   - A command-line copy opened while the original's disk is ejected keeps the
     original's ID.
   - A transcript-only session renamed and given its recording in the same
     run becomes a new session.
   - A duplicate copy, when both copies are online-only, is downloaded and
     transcribed once more.
   - A marker written by a future version that this one cannot read is
     treated as no marker.
   - A session from before content fingerprints still trusts a file
     re-exported over its recording.
9. *Low priority.* **On Windows, a stopped in-process report server still
   holds the database.** Seen only in the test rig so far; that test is
   skipped on Windows until the cause is found (`TODO.md`, 16 Oct 2026 entry).

## 1. The principle

"Bristlenose don't care" where the researcher puts things. On the Mac the
sidebar is their mental model and the filesystem sits underneath it. If they
move, rename or copy a study folder, or rename or reorganise an interview
file, nothing in Bristlenose should notice except to follow.

Three identities, each from what a thing *is*, never from where it is:

| Thing | Identity | Never |
|---|---|---|
| A **study** | what its folder carries: the database and a marker ID minted once | the folder's path or name |
| A **recording** | its content: a fingerprint of size plus hashes of the first and last megabyte | its name, path or modification time |
| A **path** | a remembered hint, tried first because it is free, verified, searched for when it fails, rewritten when found | compared to decide identity |

Two rejected shapes, both from the 12 Oct 2026 discussion. *Healing stored
paths* keeps paths as the identity and patches them after the fact; the
12 Oct empty-report incident and the moved-folder fork both came from that.
*Storing recording paths relative to the study folder* survives a folder
move and still breaks on ordinary tidying: a "Round 2" subfolder, a renamed
file. It cares about paths more than about "is this definitely X".

Ask the researcher only when no bytes anywhere match. A re-export or a trim
is different bytes, so it is legitimately a different recording.

The CLI may go on living with paths where it must. The Mac must not.

## 2. Where identity comes from today

Every surface derives it from a path, and each derivation is a separate
failure.

| Surface | Today | Fails when |
|---|---|---|
| Server project row | `importer._find_or_create_project` matches `input_dir` and `output_dir` by resolved path | folder moved with the app closed, or renamed with it open — the app follows and the restarted serve re-imports under the new path (row 29; measured 13 Oct 2026: two rows, one session each, sidebar *Report out of date*), copied (row 30) |
| Recording on disk | `SourceFile.path`, absolute; `/media/` rooted at the interview folder | folder moved, file renamed, file moved into a subfolder |
| Session number | `sessions.json` keyed on the filename stem (`s01_ingest.session_key`) until 15 Oct 2026; now content first (§11a) | file renamed: new session id, stars and tags orphaned (row 31, closed) |
| Transcription cache | manifest `input_hash` = (path inside the folder, size, mtime) since 12 Oct 2026; absolute path before | file renamed or moved within the folder: Whisper paid again |
| Scene colours | cache key = name, size, mtime | file renamed |
| Agent access | handshake `key` and `mcp_server._project_key` = SHA-256 of the resolved input path | folder moved: a configured agent loses the project |
| Mac sidebar | `Project.id` (a UUID of the row, not of the study), `path`, a security-scoped bookmark, `resourceIdentifier` | bookmark follows a move on one volume; a copy, a cross-volume move, or a re-drop from another spelling makes a second row |
| Re-drop | `findByPath`, exact string | any other spelling of the same folder |

What already points the right way: the Mac's bookmark resolution rewrites
`path` when the folder moved on the same volume, the folder watcher follows a
rename while the app runs (`presentedItemDidMove` → `relocateProject`, and the
security-scoped extension follows the folder — measured 13 Oct 2026, same
volume; cross-volume untested), the pipeline's transcription fingerprint no
longer carries the absolute path, and the importer heals a legacy row's
spelling. Each is a patch on a path, and the Mac's following is what makes
row 29 routine rather than rare. This note replaces the foundation under them.

## 3. The study marker

**File.** `bristlenose-output/.bristlenose/study.json`:

```json
{"schema": 1, "study_id": "6f1c…", "minted_at": "2026-10-13T10:02:11Z",
 "minted_by": "serve", "copied_from": null}
```

`study_id` is a UUID4. `minted_by` is `run`, `serve` or `app`. `copied_from`
is set only by a re-mint (§9) and is provenance, never looked up.

**Why there and not on the researcher's files.** Bristlenose manages nothing
in the interview folder (`design-project-storage.md` §1). No extended
attributes on their recordings, no sidecar files beside them. The output
folder is ours, and `.bristlenose/` is where the database, registry and
events already live. Whatever carries the database carries the marker.

**Minting.** The first toucher mints: whichever of `run`, `serve` or the app
creates `.bristlenose/` for a project that has none. There is one
implementation, `bristlenose/study_marker.py` (`read_or_mint(output_dir)`),
and `serve` creates the database eagerly on selection, so in the Mac app the
sidecar mints before the first run. Swift reads the file; it writes it in
exactly one case, the re-mint of a copy (§9), with a contract fixture pinning
the two writers to one shape (the `PipelineSummary` pattern).

**The database carries it too.** `projects.study_id`, written at mint and at
every import. Marker and row must agree, and when they do not, **the marker
wins and the database follows**, recording the previous value. This is what
makes a copy's re-mint take effect on next open without touching the
database. Marker missing, row has one: rewrite the marker from the row
(someone deleted our file). Both missing: mint.

**`--clean` keeps it.** Re-analyse stashes the whole output folder, marker
included. Before stashing, the run reads the marker and writes the same
`study_id` into the fresh output. A reset of the analysis is not a new study;
the sidebar row, the agent key and the report's identity all survive it. (§8
has the full carry-over.)

**Findable by Spotlight (phase 6, built 15 Oct 2026).** Spotlight does not
index dot-folders, so the marker itself cannot be searched for. Every writer
also puts the id in a visible `bristlenose-output/bristlenose-study.txt`,
which Spotlight indexes by content; Locate… searches for it and then confirms
against the marker (§13a). The beacon is a search aid, never identity.

## 4. One study, one database

A database belongs to exactly one study. The server stops being a
multi-project store with one project in it and becomes a study's database.

- **On open**, `serve` resolves its project row by `study_id`, never by
  path. There is one row; `app.py`'s `data-project-id="1"`, `last_run[1]` and
  the other sites that spell the row as a literal `1` (`bristlenose/server/CLAUDE.md`
  counts twelve) route through one resolver, `single_project_id(db)`, so the
  migration in §10 can keep a curated row whatever number it carries.
- **`input_dir` and `output_dir` on the row become hints** (§7): rewritten on
  every open from where the database actually is, never matched against.
- **The importer never creates a second row.** A run completing into a
  database that already has a row imports into it. The "forked import"
  ERROR of 12 Oct 2026 (`test_a_forked_import_is_logged_and_published_under_its_own_row`)
  stays as the guard that this cannot happen again, and is expected to never
  fire.

The `projects` table and its id column stay, because every table keys on
them and nothing is gained by removing a column from thirty foreign keys.

## 5. The recording fingerprint

```
fp = "v1:" + sha256( size_bytes | sha256(first 1 MiB) | sha256(last 1 MiB) )[:32]
```

A file under 2 MiB is hashed whole. Transcript files (`.vtt`, `.srt`,
`.docx`, `.txt`) use the same function; they are small and hash whole.

**Why head and tail, not the whole file.** Two megabytes read per recording,
whatever its length, so a twenty-session study fingerprints in well under a
second and iCloud never has to download anything to answer "which file is
this". The head holds the container header and the first frames; the tail
holds the index and the last frames. A re-export changes both. A trim changes
at least one. A rename, move or copy changes neither. Modification time and
name are deliberately absent: Finder, cloud sync and copy tools rewrite the
first, and the researcher rewrites the second ("p1 sarah").

**Identical files.** Two paths with one fingerprint in one study are one
recording. Ingest keeps the first by its current hint and records the second
as an alias in the registry (§6), with a log line. It does not become a
second session; the 0.31.3 re-drop fix already stops the copies at the door
on the Mac, and this is the same rule one layer down.

**Cloud placeholders.** A dataless file (`utils.fs.is_dataless`) cannot be
fingerprinted without a download, and fingerprinting never downloads, exactly
as ingest's duration probe never does. The rule: **keep the last known
fingerprint for that path hint.** A placeholder whose hint matches a known
entry keeps its identity; a placeholder never seen before is a session with
a pending fingerprint, grouped by stem as today, settled on the first run
that finds the bytes present. Nothing is renumbered when it settles.

**What a session is.** Grouping is unchanged: a recording and its subtitle
file share a stem and form one session (`s01_ingest.group_into_sessions`).
Identity is the fingerprint of the session's primary file, video before
audio before transcript. Grouping decides what sits together; the
fingerprint decides which session it is.

*23 Oct 2026:* "video before audio" would let a video dropped beside an
analysed audio file name the session, and a session keyed by the audio's
bytes would be found by nothing and analysed again as a new one. So a
session whose name already holds the content key of a recording still in
the group keeps that recording as its primary (`SessionRegistry._held_primary`;
an evicted one is known by its place). And an analysed session keeps the
files it was analysed from (decision #129): a file that joins it later is set
aside as `added_after_analysis` and stated, never read
(`pipeline._set_aside_late_files`). Which files those were is read back from
the transcription `input_hash`, which hashes exactly their content: the
subset of the session's files that hashes to it.

**Caches key on it.** The transcription `input_hash` becomes the fingerprint
plus, for transcript files, the parser version, so a rename inside the folder
costs nothing (today it re-pays Whisper). Scene colours, thumbnails and
extracted audio are keyed by session id and so follow for free once the
session id does. The manifest's `accept=` mechanism from 12 Oct 2026 takes
the old (relative path, size, mtime) form once, so no project pays twice on
upgrade.

## 6. Registry version 3

`sessions.json` keeps its job, sticky numbering, and changes its key.

| Field | v2 | v3 |
|---|---|---|
| `sessions` | grouping key (`stem:…`, `zoom:…`, `stamp:…`) → sid | fingerprint → sid; legacy keys still read |
| `starts` | sid → best start | **fingerprint** → best start, so a start survives `--clean` renumbering (§8) |
| `hints` | — | fingerprint → last known path inside the folder, and any aliases (§5) |
| `speakers`, `pins`, `participants_issued` | unchanged | unchanged |

**Reading v2.** A v2 file loads as today. On the first run that can
fingerprint the files, each legacy key is matched to a session by the same
grouping key it was written under, and rewritten under the fingerprint. A
legacy key whose files are placeholders stays legacy until the bytes arrive.
The file is written as v3 once any key has been rewritten; a release that
reads only v2 refuses it loudly, as the version rule already says.

**Validation** stays strict: a key that is neither a legacy shape nor a
`v1:` fingerprint is a reason to refuse the file, because every value in it
is an identity.

**The consequence the owner asked for.** Rename `Recording 2026-10-02 14.33
Zoom.mp4` to `p1 sarah.mp4` and the fingerprint is unchanged, so the
session keeps its number, its speaker codes, its stars and tags, and its
typed names. Row 31 closes.

## 7. Path hints and healing

A hint is a path we last saw a thing at. There are three: the row's
`input_dir` and `output_dir`, each `SourceFile.path`, and the registry's
`hints`. All are rewritten freely and none is ever compared to decide what
something is.

On every import and on every open, per session file:

1. The hint exists and its fingerprint matches: done.
2. The hint is a placeholder: keep it (§5).
3. Otherwise search the interview folder for a file with the fingerprint.
   Candidates are filtered by size first, so the search hashes only files of
   the right length, which is usually one. Found: rewrite the hint.
4. Not found: the file is missing. `verified_at` is cleared, playback
   degrades for that session, analysis stands (`design-project-storage.md`
   §1, "stay fully useful when source media is absent"). The sidebar and
   the Sessions grid say so; nothing is deleted and nothing asks.

`/media/` keeps its URL shape and is built from the healed hint at request
time, as the video map already is. The interview folder itself is wherever
the database's folder is: `project_input_dir` of the open database's
location, never the stored `input_dir`.

On the Mac, the order is bookmark first (free, and it already follows a
same-volume move), then the marker to confirm, then phase 6's search across
volumes — and never into the Bin: a destination under `.Trash` or `.Trashes`
is a deletion, not a move (`ProjectIndex.isInTrash`, 12 Oct 2026), so marker
healing refuses it as the watcher already does. `Project.resourceIdentifier` keeps its one job, cheap dedupe of a
drop, and stops being treated as identity.

## 8. What Re-analyse carries over

Re-analyse has two jobs: a deliberate reset of the analysis, and first aid
when the report is broken (`design-analysis-lifecycle.md` §1). Both mean the
output is rebuilt from the recordings. Two things cross the reset:

- the **study id**, read from the marker before the stash and written into
  the new output (§3);
- the **session starts**, keyed by fingerprint, so a start resolved from an
  iCloud container that is now evicted, or from a filename's local clock on
  another machine, is not replaced by a worse signal on the re-run.

They cross as a **validated extract**, never as the registry file: a UUID
that parses, fingerprints of the `v1:` shape, ISO timestamps with a zone and
a `source` the ranker knows. Anything else is dropped with a log line.
Speakers, pins, participant numbers and names do not cross; renumbering and
re-identification on a reset is the reset. Nothing that identifies a person
crosses.

## 9. A copy is an independent duplicate

Decided 13 Oct 2026. A copy of a study folder, however it was made, is a
second study that starts as the first was at that instant.

- **Finder duplicate is the primitive** and must work on its own. On the
  Mac's own disk APFS clones the folder, so it is instant and costs no space
  until files diverge. A File ▸ Duplicate item is a convenience over the same
  mechanic: it names the result, selects it, and can refuse during a run. It
  is not a safety requirement.
- **The copy carries everything**: recordings, the database with every star,
  tag, hidden quote, renamed section and person, transcripts, caches, run
  history, marker. It opens with no transcription and no LLM spend.
- **Re-mint on arrival.** When a folder reaches the sidebar carrying a
  `study_id` already bound to a *live* path, the newcomer gets a new id, with
  `copied_from` set. If the bound path no longer exists, it is a move: the row
  adopts the folder and keeps the id. The original keeps its identity, its
  sidebar position and its agent-access grant. If a drive with the original
  comes back later, two folders carry one id, and the second one touched is
  re-minted. No branch loses data: the id is a label, the database is the
  study.
- **From the first edit the two are unrelated.** Writes to one never reach
  the other. Outward links come along by design: a remembered Miro board, an
  export setting. What the researcher does with the board is theirs.
- **Naming.** The sidebar shows the folder's name ("Talismanic copy") and
  the researcher renames it; the report slug follows the name.
- **A clean copy** is Re-analyse in the copy. There is no second duplicate
  mode.
- **A copy taken during a run** is a half-written study and opens as an
  interrupted one, which the register already handles; a copy taken under an
  idle or mid-edit server is consistent, because the database runs in WAL
  mode and only complete transactions replay.

**Re-drop dedupes by marker.** The sidebar rule "no dedup, the same folder
dropped twice creates two projects" was retired the same day. It had been
dead in the shipped app since `754f0658` (8 Jun 2026), when re-drop started
selecting the existing row by exact path. The key moves from the path string
to the marker: a moved folder dropped again heals its stale row instead of
forking; a copy with its original live is re-minted; a symlinked or
`/Volumes` spelling is the same study. Two rows on one folder could never
have worked, since they would share one database and one output.

## 10. One migration

Runs once per project, on the first `run` or `serve` with the new code,
identically from the CLI and the Mac app, with no user action. Idempotent;
every step is a no-op when already done.

1. **Mint or adopt the marker.** No marker and no `study_id` on any row:
   mint. A row has one: write the marker from it.
2. **Collapse forked rows.** A database with more than one project row
   (rows 29 and 30 have been making them since the server existed) keeps the
   row holding the curation and deletes the rest. Curation is any row in
   `quote_states`, `quote_tags`, `quote_edits`, `heading_edits`, a person
   with a typed name, or a framework state; the row with the most wins, and
   a tie goes to the latest `imported_at`. The deleted rows' sessions are
   re-imported from the output on the next run, which is where their data
   came from. The kept row's id is whatever it is; §4's resolver reads it.
   The Mac's fork signal reads the row count with `?immutable=1`, so after a
   collapse it stayed on until the WAL was checkpointed (register row 35);
   since 20 Oct 2026 every serve commit checkpoints, so it clears at once.
3. **Registry v2 to v3** as §6 describes, as far as the bytes on disk allow.
4. **Manifest fingerprints** are accepted in their old form once and
   rewritten (`fresh_session_ids(accept=…)`, already built).
5. **Hints healed** per §7, including `SourceFile.path` rows that still
   carry a folder that moved months ago.

The migration logs one INFO line per step it took, with counts, and an
ERROR if step 2 found two rows with curation on both (expected to be rare,
and the loser's curation is left in place, not deleted, until a person
looks).

## 11. Agent access and other outward keys

`mcp_server._project_key` and the handshake `key` become the `study_id`
(first eight hex digits, as today's path hash is). An agent configured
against a project keeps it across a move or rename; a copy is a new project
to the agent, which is right. The MCP bearer is minted per serve start and
stored nowhere, so nothing in the Keychain is per-project today. Should a
later phase add one, the house rule applies: write the new item, never
delete the old.

The report title and the export filename already come from the row's name,
not the folder, and are unchanged.

## 11a. As built, 15 Oct 2026 — where phase 2 departed from this note

- ~~**Identical files stay two sessions**~~ (§5 said one recording, the second an
  alias). Ingest finds two, and register row 15 is "never drop a recording
  silently"; the registry keyed only the first by content and the second by
  name. A re-drop of copies is stopped earlier on the Mac. **Closed 20 Oct
  2026 (R49):** identical bytes under two names are one session, as §5 said.
  `SessionRegistry.apply` folds the copy that does not own the content key
  into the one that does (`s01_ingest.fold_duplicate_recording`): its
  recording is set aside as `duplicate_recording` — the row the Files bucket
  already shows for a second recording in one session, so row 15 holds — its
  transcript files join the session, and set-aside files are left out of the
  transcription fingerprint (`pipeline._transcribed_files`), so a copy added
  or removed beside an analysed interview does not run Whisper again. Which
  copy is used follows `owner_rank`: the key's owner, else name order; the
  set-aside copy's name is not remembered, so once the used copy is renamed
  name order decides between the two, and the session is unchanged either
  way. A fetched placeholder whose bytes are a resident recording's is folded
  too. Different bytes (a re-export, a trim) are still a different recording.
  A study analysed before this with the copy as its own session loses that
  session on its next run, as it would a removed interview — its stars sat
  on a duplicate: the fold retires that session (its name key becomes
  `retired:<sid>`, so deleting the kept copy cannot hand the survivor the
  copy's old number; the number stays reserved and its speakers, pins and
  starts are left in place). The run's totals — files by type, hours of
  audio, the time estimate — count the interview once. Identical
  *transcript* files with no recording (the same Teams `.vtt` or `.docx`
  downloaded twice) fold the same way since 21 Oct 2026 (decision #97,
  `s01_ingest.fold_duplicate_transcript`): same owner rank, same retire, the
  copy set aside as `duplicate_transcript` ("a second copy of this session's
  transcript") and never parsed — every file of the copy whose bytes the
  owner holds, so the `.docx` of a Teams pair is not read twice; a file that
  differs joins as a candidate. A pair downloaded twice can land its `.vtt`
  and `.docx` in a different order, so the sessions' first files (their
  keys) differ: sessions with no recording holding the same set of files are
  folded too. A recording and a transcript with one fingerprint are kept
  apart and said. An evicted transcript copy is not fetched to be
  compared (only a recording is): it is its own session until resident, then
  folds and that session is retired. A pair-folded copy from a study
  analysed before 21 Oct 2026 held its own content key, so its old session
  is not retired: if the kept pair is later deleted, the survivor is that
  old session, not the kept one. **Known limit:** a copy folded while resident has no place of its own
  in `hints`, so if both copies are later evicted it is a placeholder with
  no bytes, no place and no name — a new session for that run, downloaded
  and transcribed at transcription. Register row 55;
  `tests/test_pipeline_duplicate_recording.py`.
- **A session keeps a name key beside its content key** (§6 said fingerprint →
  sid). Content first, then the last known place, then the name, and a sid a
  stronger key claimed is never handed on by a weaker one. The name key is
  what keeps an *edited* transcript file (new bytes, same name) its session.
  A sid holds one name key and one content key, so the new bytes replace the
  old (two content keys on one sid made the next run refuse the file — review,
  15 Oct). For a **recording** the name never overrides known bytes: different
  bytes under a known name are a new session, as §5 says of a re-export, so a
  deleted interview's name reused does not inherit its participant.
- **Transcription keeps a placeholder's last known fingerprint** (§5's rule,
  applied to the cache as well as the registry): an evicted recording is
  neither downloaded nor transcribed again when another interview is added.
- **Curation, for fork collapse, is measured, not named by table.** The
  importer writes sentiment tags (`source="pipeline"`) and confirms speaker
  slots it carries from the registry, so neither counts; a tag from any other
  source and an AutoCode proposal do. (A first fix counted confirmed slots and
  every tag, which made every real fork permanent; a test on a fork made by a
  real import showed it.)
- **A place remembers only its latest recording**, so a deleted recording's
  place reused by another cannot hand the newcomer the old session when it is
  evicted.
- **Every Spotlight hit goes through the panel.** A hit carries no sandbox
  grant, and no bookmark can be made from it, so "Use This Folder" opens the
  panel at that folder, which grants, and the verdict is taken there. (Until
  the whole-body review it did so only when a marker existed; a study not
  yet served since the marker was introduced was relocated without a grant
  and then failed every read.) A dropped folder held under another spelling
  is matched by its file-system identity, links resolved, except on a network
  share, where a drop never reads another row's metadata.
- **Starts stay keyed by sid inside the registry** (§6 said by fingerprint).
  Within a study the sid is stable now; across a Re-analyse the starts cross
  as a separate hand-over keyed by content (`carried-starts.json`, §8), which
  is the only place a renumbering could lose them.
- **No `single_project_id` resolver** (§4). The importer never creates a
  second row in a study's own database and collapses old forks onto the
  lowest id, which is row 1, so the literal `1` the SPA reads stays right.
- **No ingest-facts path heal** (§7). Every run rewrites the transcript header
  with the recording's current place; the importer heals the source-file row
  whose file moved instead of adding one beside it. A heal from ingest facts
  was built, survived its mutant, and was removed.
- **Fork collapse runs at every whole import** (§10 said once), never at a
  run's progressive imports. It is cheap, and a database copied in from an
  older release gets it whenever it arrives.
- **Whole-body review, 15 Oct 2026.** A CLI copy is re-minted at its first
  import of any kind, before the path heal erases the evidence. Of two
  identical recordings, the one named first owns the content key, not the
  one ingest (date order) saw first. When a known recording is missing and an
  unseen cloud placeholder appears, the placeholder is fetched at ingest and
  identified by its bytes, so a rename while evicted is not paid for twice; a
  first analysis still fetches at transcription. A dropped study whose known
  folder sits on an ejected disk is neither a move nor a copy: it gets its
  own row with the id it carries, and the shared-id rule settles it when the
  disk returns (`StudyDropMatch.unsure`). Two spellings of one folder are not
  a copy of each other. `MCPTokenStore.revoke` is gone. A review of those
  fixes refined two: of identical copies, the one that already owns the key
  keeps it, then a renamed one, then name order (so neither a date flip nor a
  rename swaps them); and the early fetch runs only for `run` and
  `transcribe` (`apply(fetch=True)`), never serve's re-render, and never for
  a recording with a transcript beside it. **Left as known limits:** "is the
  disk mounted" reads only `/Volumes/…` paths, so a signed-out cloud-storage
  provider's folder reads as moved; the drop still checks that same-id rows'
  folders exist on the main actor; and an ejected-disk drop that was in fact
  a move leaves the old row behind, which a later Locate can point at the
  same folder as the new row (no merge-on-relocate yet). A last review fixed
  two more costs of keeping identical copies as two sessions: a content key
  is never handed from the session holding it to another, and a copy whose
  name belongs to another session is that session even when the keyed copy
  is gone; a re-exported recording's original, restored under its name,
  returns to its own session. **Still open:** when the keyed copy's name is
  absent and a copy under a new name appears (both renamed in one run, or
  one deleted in one run and the other renamed in a later one), the registry
  cannot tell which copy it is, so two identical copies may swap sessions.
  _(Moot since 20 Oct 2026: identical copies are one session.)_
- **Final whole-body review, 15 Oct 2026.** `run --skip-transcription` never
  fetches a placeholder (nothing would read it). A recording re-exported in
  place is no longer the old session's media: the importer checks its bytes
  against the session's fingerprint and drops the media row on a mismatch,
  as §12 promised. A Re-analyse of a study with no content keys yet carries
  its starts under a hash of the name key, never the name. On the Mac, Locate
  refuses a folder another sidebar row holds (a row from before the marker
  had nothing to disagree with), a re-drop under another letter case is the
  same folder, and a network holder's re-drop is `.unsure` rather than a
  re-mint of the live study. **Open, recorded rather than built:** on the
  CLI, a copy served while the original's disk is ejected keeps the
  original's id after the disk returns (only the app can see two folders);
  a placeholder at a known place inherits the session and its transcript
  with no log line if another interview was saved there on another device;
  `/api/health` caches the agent key for the serve's lifetime while the MCP
  key is computed live; a row found only by its volume-relative path
  is not part of the shared-id settlement at refresh; and a network re-drop
  left `.unsure` is settled by `captureStudyID`, which reads the share's
  folder identity on the main actor, and if it was the same folder leaves two
  rows on one study. The importer refuses a re-exported file as an old
  session's media by its bytes, but only for a session keyed by content: a
  session with no content key of its own (one from before content keys, or
  the unkeyed one of two identical copies, which stays unkeyed even after its
  twin is deleted) can still play a recording re-exported over its file.
  The alias model for duplicates would close this with the rest. _(The
  unkeyed twin is gone since 20 Oct 2026 — identical copies are one session;
  the session from before content keys remains.)_
- **Last whole-body review, 16 Oct 2026.** A recording arriving for a
  session analysed from its transcript alone joins that session (its
  content key held the transcript's bytes, so the re-export rule had
  refused it and renumbered every Teams-transcript study once its
  recordings were added). On the Mac, a Locate test now drives the real
  flow through a search seam, and a folder whose identity cannot be read is
  never re-minted as a copy of itself. **Still open:** a transcript-only
  session renamed and given its recording in the same run is a new session;
  nothing tests that `ServeManager` passes the study id when it resolves the
  agent token; and a marker this release cannot parse, read under a grant,
  is treated as no marker (Locate accepts the folder).
- **Review at the final HEAD, 16 Oct 2026.** A renamed placeholder still
  downloading after the full wait stops the run with that reason instead of
  becoming a new session (it would have finished downloading during
  transcription and been paid for twice). After the agent token is carried
  from a path to a study, the path gets a fresh token (an update, never a
  delete), so a different study later made at that path does not share it.
  A whole-body review at that point found nothing important remaining.
  **Still open, presentational:** on the command line the fetch timeout ends
  with Python's traceback rather than a plain sentence (the Mac app shows a
  failed run with the reason), and the up-to-30-minute wait prints nothing. §5 called a duplicate one
  recording with an alias; the build kept two sessions, one keyed, until
  20 Oct 2026 (the first bullet of this section).

## 12. What this does not do

- Touch anything in the interview folder. No attributes, no sidecar files,
  no renames.
- Use a relative path as identity. Hints may be relative for display; they
  are never compared.
- Lock a study against two instances (row 32). SQLite serialises writes;
  imports can still race. Out of scope here.
- Promise anything about network shares, ExFAT or an evicted database
  (row 33). The marker and fingerprints are plain files and plain reads, so
  nothing here makes those worse.
- Recognise a Windows cloud placeholder. On macOS every File Provider
  (iCloud Drive, Dropbox, and OneDrive since it moved to File Provider under
  `~/Library/CloudStorage/`) marks an online-only file dataless, and nothing
  here reads one; that was measured on Dropbox, not yet on OneDrive. On
  Windows, OneDrive's Files On-Demand uses a different mechanism
  (`FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS`) that `is_dataless` does not check,
  so fingerprinting downloads an online-only recording on every run.
- Replace a recording whose bytes changed. A re-export is a new recording;
  the old session shows as missing and keeps its curation. Offering "this is
  the same interview, re-exported" is a later, separate affordance.

## 13. Proof

Phase 2 flips the strict xfails `moved-while-closed` and `copied-elsewhere`
in `tests/test_lifecycle_scenarios.py` and adds rows for: a renamed
interview keeps its curation; an interview moved into a subfolder is not
re-transcribed; Re-analyse keeps a session's start after a rename; a copy
re-minted on arrival stops receiving the original's writes; a v2 registry
upgrades in place; a database with two rows keeps the curated one. Each is
proved red against the tree before its fix, as the register requires, and
each fix is mutated alone afterwards, because red-first proves a test can
fail and not that each fix is pinned.

The Mac side (phase 4) pins re-drop by marker, re-mint of a copy, and the
bookmark-then-marker order in `ProjectIndex` tests; the end-to-end driver
(fake LLM provider, Python replay of the app's process order) runs
add → analyse → move → reopen → copy → reopen before phase 2 lands.

## 13a. Phases 3 and 6, as found on 15 Oct 2026

- **Phase 3 is obviated.** No code creates a file-subset project any more:
  dropping loose files asks for a folder through a save panel, copies the files
  in, and makes a folder project (`ContentView.processDroppedURLs`). Subset
  projects in an older `projects.json` stay in their "can't be analysed" state
  (`UnsupportedSubsetView`, deleted with the loose-file study on 22 Oct 2026), carry no output folder and so no marker, and the
  sidebar treats them as having no study id. Whether to offer such a project a
  one-click move into a folder is a product call, not identity work.
- **Phase 6's search is built (15 Oct 2026), on a visible beacon.** The spike:
  Spotlight does not index the hidden `.bristlenose/study.json`, and does not
  search a JSON file's content, but it does index a visible text file's
  content (measured, macOS 27). So beside the marker every writer puts
  `bristlenose-output/bristlenose-study.txt`, holding only
  `bristlenose-study <id>` — nothing to translate. Python writes it with the
  marker and backfills it on the next run or serve for studies minted before
  (`study_marker.read_or_mint`); the app rewrites it when it re-mints a copy,
  so a copy's beacon names the copy. Locate… asks Spotlight first for
  `kMDItemFSName == "bristlenose-study.txt" && kMDItemTextContent == "*<id>*"`
  across every indexed volume (a lost study has usually moved to another
  disk), takes the folder above `bristlenose-output/` when exactly one hit
  is analysed, and otherwise falls back to the name search in the home folder.
  **The beacon is never read for identity:** the hit is still checked against
  the hidden marker once the panel grants the folder (`LocateFlow.verdict`),
  and a deleted or stale beacon only costs the search. The run's
  "output folder already exists" check counts the beacon as state, not a
  deliverable (`cli._has_no_deliverable`). The owner's decision to accept a
  visible file in the output folder is the one assumption here, and it is
  reversible: removing the writer and the search restores the name search.
  **Several hits** (a moved study plus a mounted backup, or a Finder copy
  not yet given its own id): the one whose database or manifest was written
  strictly last is offered, since that is the one in use. A backup clone keeps
  its original's times, so a fresh backup ties, and a tie or an unreadable
  time opens the panel without a name search, which could resolve the tie to
  whichever copy sits under the home folder. The
  confirm sheet shows the path either way (`SpotlightOneShot.newestStudy`).
  Offering every hit in the sheet is the next step if ties bite. A Re-analyse carries
  `copied_from` with the id (`cli.py`), and the committed smoke fixture
  ignores the marker and beacon an E2E serve mints.
- **A copy says where it came from.** The app records `copied_from` from the
  marker on the row (`Project.copiedFrom`), and the row's hover reads
  "Copied from <original's name today>", or "Copied from another project"
  when the original is not in the sidebar (`CopyProvenance`, resolved by
  study id, never by name). All 21 full locales.
- **The half that needs no decision is built** (15 Oct 2026): whatever folder
  Locate… lands on, by Spotlight or by the panel, is refused when it is an
  analysed project carrying a different study id (`LocateFlow.verdict`), with
  its own message in all 21 locales. Before, picking another analysed study
  relocated the row onto someone else's analysis.

## 14. Order

Phases, estimates and models are in the lifecycle handoff, kept outside the
public tree. In one line each: phase 0 quick wins (serve reclaims a stash,
leases on demand); phase 2 the Python half of this note; phase 3 file-subset
projects get their own output folder and go incremental, which they need
before they can carry a marker (two subsets of one parent would share one);
phase 4 the sidebar adopts the marker; phase 5 agent access keys on it;
phase 6 Locate… by marker across volumes after a Spotlight spike.
