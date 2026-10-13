---
status: decided
last-trued: 2026-10-13
trued-against: HEAD@main (eb8509e1, 030b568b) on 2026-10-13
---

## Changelog

- _2026-10-13_ — trued up: §2 carries the live S9 reproduction and the watcher route; §7 the Bin rule; §10 the WAL lag on the fork signal. Anchors: register rows 29, 35; `eb8509e1`.

# Project identity without paths

**Status: decided 13 Oct 2026, with the owner. Design for phases 2 to 6 of the
lifecycle plan; nothing here is built yet.** Rows 29, 30 and 31 of
[design-lifecycle-failure-modes.md](design-lifecycle-failure-modes.md) are the
failures this closes.

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
| Session number | `sessions.json` keys on the filename stem (`s01_ingest.session_key`) | file renamed: new session id, stars and tags orphaned (row 31) |
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

**Open for phase 6.** Spotlight does not index dot-folders, so Locate…
cannot search for the marker by content. The spike decides the findable
form; a candidate is a small visible file in `bristlenose-output/` holding
the id, which costs nothing and is ours to write.

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
   collapse it stays on until the WAL is checkpointed (register row 35).
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

## 14. Order

Phases, estimates and models are in the lifecycle handoff, kept outside the
public tree. In one line each: phase 0 quick wins (serve reclaims a stash,
leases on demand); phase 2 the Python half of this note; phase 3 file-subset
projects get their own output folder and go incremental, which they need
before they can carry a marker (two subsets of one parent would share one);
phase 4 the sidebar adopts the marker; phase 5 agent access keys on it;
phase 6 Locate… by marker across volumes after a Spotlight spike.
