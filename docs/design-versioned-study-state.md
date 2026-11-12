---
status: proposal
updated: 11 Nov 2026
---

# Versioned study state ("go back in time")

> **Status: an idea, post-beta, filed in the project backlog under "Post 100 days".** Nothing here is built.
> It came out of one conversation on 10–11 Nov 2026 about what a Re-analyse that stops halfway should leave
> behind, and grew into the larger design the owner called the versioning engineering: "we can't do a much
> much better UX and reliability until we really do that." Prior-art claims below (other products' names for
> this) are from memory and have not been checked.

## The promise

**Go back in time.** A researcher can return to an earlier state of a study. Re-analyse stops being a
destructive act and becomes a fork they can step back from; a crash, an abort or a mistake costs a click, not
the work. This is the internal north star. In user-facing copy it is never stated as a promise: the copy
lists exactly what a version holds and what it does not.

## What v1 does instead (decided, owner, 11 Nov 2026)

The 23 Oct 2026 rule stands. A fresh analysis (Re-analyse, `run --clean`) replaces the old report as soon as
it holds one analysed session; nothing else replaces a report. The Re-analyse sheet (and `--clean`'s
question) is the warning: "Your work on this study will be discarded", counting nine kinds of work since
N131. A researcher who breezes past it and then stops, quits or crashes ends with what was processed (say 2
of 8 interviews, no stars). Plain **Analyse** is non-destructive and finishes the other six from cache. No
complaint is owed. The previous report's exports (clips, screens) are already carried across
(`output_backup.carry_exports`). This closes the "Re-analyse that stops halfway" question and the
N117/N116 reliability rows by design.

**Settled and built (owner, 12 Nov 2026):** the Mac saves the in-flight run's `--clean` flag in its run queue
and restores it on the next launch (`PipelineRunner+QueueRestore.swift`). That was deliberate (R18): a stopped
Re-analyse put the old report back, so resuming as a plain run would end "ready" on the old report. But once
the fresh run has produced a session the old report is already gone, and a relaunch after a quit or crash
would have set the finished interviews aside and paid for them again. Now the queue keeps the run in flight
as a plain Analyse from the moment its fresh analysis holds a session, so a relaunch resumes from cache.
Before that moment it stays a Re-analyse, as before. The runner asks while the run is live
(`FreshRunProbe`, `PipelineRunner.noteFreshRunProgress`); the probe copies Python's
`holds_an_analysed_session` and the set-aside folder's name, held together by
`tests/fixtures/fresh-run-probe-contract.json`. Written from the code and tests, not from a real quit
mid-Re-analyse on the Mac.

## The shape of it

Three things, in increasing cost. None copies the recordings.

1. **A curation snapshot.** The researcher's own work: stars, hides, human-applied tags, quote edits,
   heading names, speaker choices, removed sentiment badges, transcript edits. Kilobytes to megabytes. It is
   the data the importer already re-attaches to quotes on every re-run by the quote identity key (session,
   speaker, exact start, ordinal), written out and kept. `people.yaml`, the researcher's names, is the
   precedent for state that lives in a file they own. It needs a **pending store**: after an abort, only
   quotes in the finished interviews can take their curation back, so entries for the others must wait,
   unattached, and re-attach as each session returns from an ordinary Analyse.
2. **A full non-media version.** The whole apparatus apart from the recordings and the extracted-audio
   cache: database, transcripts, intermediate files, report, exports. Tens to hundreds of MB. It keeps the
   paid analysis (transcription time, model spend), so restoring it is a true revert, which a curation
   snapshot is not.
3. **A duplicate or branch.** The same thing shown as a second project in the sidebar over the same
   recordings. Harder: a study's identity is a marker in its folder (a copy needs a freshly minted one or the
   app confuses the two), and output currently lives inside the input folder, so this needs more than one
   output slot per input folder. It is the same shape as the two-Macs-on-one-folder problem (R114).
   Start with versions *inside* one study; treat a branch as a later extension.

## What it reuses

`bristlenose/utils/output_backup.py` already keeps **one** "previous" slot: it moves the old output tree
aside, restores it if the run produces nothing, and discards it when the run's analysis holds a session. It
has a settle lock, a carry of exports, and a server that rebinds to the right tree atomically (commit
`642f49a7d`). Versioning is that slot generalised: N named slots, a retention rule, and a UI to list and
restore them.

## Naming (undecided)

- **"Version history" / "Restore this version":** the words Google Docs and Drive, Microsoft 365, Dropbox,
  Figma and Apple's own document Versions use. Probably what researchers already say, since their work lives
  on Teams, SharePoint and Drive. Those are mostly automatic timelines; a named version ("Name current
  version" in Drive) fits a hybrid of automatic and deliberate points.
- **"Snapshot":** Final Cut Pro's "Duplicate Project as Snapshot" (the closest prior art: a copy that does
  not duplicate the media), Lightroom and Photoshop snapshots, virtual machines. Implies a deliberate,
  immutable point. Risk: next to the Screens lens (stills of participants' screens) it can read as a screen
  capture.
- **Fallbacks:** "Save point", "Checkpoint".
- Check any candidate against `bristlenose/locales/glossary.csv` and each locale's existing vocabulary
  before choosing (21 locales).

Natural verbs once chosen: an automatic version before every Re-analyse, named like "Before re-analyse, 11
Nov 14:32"; a deliberate "save a version"; "Version history…"; "Restore this version".

## Engineering issues

- **Copying a live database.** A plain `cp` of a SQLite file the server is writing can corrupt it. Use the
  SQLite backup API or `VACUUM INTO`.
- **Disk and sync.** APFS `clonefile` makes a copy near-free until files diverge. A hidden folder inside the
  study syncs through iCloud or Dropbox, so versions either live outside the synced folder or are excluded,
  or they multiply sync traffic.
- **Shared tables.** Persons, tag definitions and the codebook are instance-scoped (shared across studies by
  design). A restore must not clobber another study's rows.
- **Format over time.** A snapshot taken at one schema version must still load after later database
  migrations, so the format is versioned and migrated.
- **Privacy and retention.** Versions hold real names and edited quote text. "Delete the study" must delete
  its versions, `SECURITY.md`'s deletion procedure (the `rm -rf` lines that name every folder holding a copy,
  the set-aside report included) must name the versions too, and a
  retention rule says how many are kept and for how long.
- **No drift.** The promise only holds if nothing escapes. A structural test should fail when a table of
  researcher work is added without being classified "in the version" or "derived", the way
  `tests/test_serve_export_coverage.py` fails on an unclassified route.
- **Quote identity.** How well curation re-attaches after a re-analysis depends on how far a quote may move
  or change wording and still count as the same quote (importer `_match_quotes_to_rows`; the 1:1 rule is
  ruled, the tolerance question is open).
- **Restore under a live server.** A server binds to one tree. The existing restore/rebind machinery is the
  mechanism; a restore while a report is open needs the same settle discipline.
- **New UI.** A history list, a restore control and new strings in 21 locales need a mockup and explicit
  owner approval first (the 28 Oct UX gate), reusing existing patterns.

## A smaller stepping stone (considered, not for v1)

On a failed Re-analyse that produced at least one session, **hold the set-aside copy until the researcher
chooses** "Restore previous version" or continues with what was processed:
- Not a modal. A button in the existing failed-run popover (beside Show Log and the Copy details icon; the popover has no Retry, which lives in the sidebar menu and the toolbar);
  continuing is simply pressing Analyse.
- The waiting state must survive a quit or crash, so the question is asked at the next launch.
- The held copy is discarded when the new analysis is whole or when the researcher continues (the second is
  irreversible, so it confirms with Cancel not the default).
- After the researcher's own Stop the plain "Analysis stopped" stays; the same restore sits in the row's menu.
- A CLI equivalent: one plain line saying the previous report was kept and how to restore it.
- Privacy: the held copy must go with the study.
- It reuses the existing restore path, so it is a small feature, but it is still a feature in a beta meant to
  have almost none.

## What it would dissolve or soften

The stops-halfway question; reliability rows N117 and N116; R54 (undo a deleted sidebar folder, at a
different scale); N130 (Re-analyse warns about names the pipeline filled in, which a typed-by record would
fix exactly); and part of R114 (two Macs on one synced folder). It also gives backups and a way to hand a
study to a colleague without the recordings.

## Open questions

1. Name: version history, snapshot, or another word (check the Screens collision and the 21 locales).
2. Is the unit a curation snapshot, a full non-media version, or both from the start?
3. Where do versions live: inside the study folder (travels with it, syncs) or in the app's own storage?
4. What does a restore do to work done since: replace it, or take a version first (a restore that is itself
   undoable)?
5. Retention: how many, how long, and who can delete them.
6. The quote-identity tolerance, which decides how well curation re-attaches.
7. ~~Should the Mac's restored run queue drop `--clean` once the fresh run holds a session?~~ Yes, built (see above); a real quit mid-Re-analyse on the Mac is still worth one hands-on pass.
