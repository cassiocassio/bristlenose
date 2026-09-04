# "Waiting for iCloud…" — the cloud-wait label

**Status: future enhancement, not scheduled.** Written 4 Sep 2026 to hold a
question that had been argued three times in six weeks — for in
`design-project-storage.md` §3 (29 Jul), walked back in
`design-sidebar-activity-indicators.md`, re-proposed on 4 Sep without noticing
either — so that the fourth time starts here. Scope and policy below are
**decided**; §5 is the one measurement still open; §7 is what a pick-up
would build. Candidate for the maintainer's private planning board.

## 1. What it is

One line of text in the project row's subtitle slot, while a drag-in copy is
blocked on a cloud provider materialising a file:

> Waiting for iCloud…  ·  Waiting for Google Drive…  ·  Waiting for OneDrive…

It replaces "Copying 3 of 12…" for as long as the read is blocked and gives
the slot back when the read returns. Nothing else: no pie, no per-file list,
no button on the label (the existing copy cancel stays where it is), no
setting. It is the "Resuming…" pattern applied to a different quiet moment —
narrate the suspicious silence, don't manage it.

Tiny, and still meaningful: today the row says "Copying…" while nothing
copies, for as long as the provider takes, with no way to tell a slow disk
from a slow network from a hang.

## 2. Scope — decided 4 Sep 2026

- **Three stores: iCloud Drive, Google Drive, OneDrive.** The stores that
  pair with the meeting platforms — iCloud for the personal Mac, Google Drive
  with Meet, OneDrive with Teams. Dropbox, Box, pCloud, Proton, a NAS: the
  generic "Copying…" they show today. The storage doc's Dropbox examples were
  a measurement test bed, not a scope.
- **Storage axis only.** Not import: the Teams / Zoom / Meet download flows
  have their own progress (`design-cloud-import.md`). A researcher can store
  on OneDrive and import from Teams at once; this label is about the store.
- **The label is scoped; correctness is not.** Reading any File Provider
  correctly — detect dataless, bound the read, surface the failure — stays
  unconditional. Only the *words* are per-provider.

## 3. Policy — decided, don't reopen

- **Bristlenose manages nothing.** No eviction, no pinning, no "download all",
  no per-folder rule (`design-project-storage.md`; memory
  `project_storage_cloud_policy_decided`). Apple's abstraction is that the
  disk is a disk; we live in that idiom rather than fighting it.
- **Hydrate on demand, bound it, log it.** The sidecar's `fs.py` already does
  detect-then-bounded-materialise; the desktop copy path mirrors it
  (`design-copy-error-surfacing.md` §6 Tier 2). The label is what the bounded
  wait *says* while it waits.
- **Failure is a sentence, not a state.** A read that times out or is refused
  surfaces through `CopyError` → `LocalizedError` (surfacing doc Tier 0) —
  Foundation's words, or Finder's — never a permanent row state.

## 4. Reality — what a third-party app can actually know

Everything the OS exposes to us, per store. "Measured" cites this repo's own
probes; "documented" is Apple's reference; "not found" means two research
passes (4 Sep 2026, `design-copy-error-surfacing.md` §8) looked and found no
public API and no shipping app using one.

| Capability | iCloud Drive | Google Drive / OneDrive | Basis |
|---|---|---|---|
| **Is this file dataless?** | `ubiquitousItemDownloadingStatus == .notDownloaded`; also the `SF_DATALESS` flag | the `SF_DATALESS` flag (`getattrlist` / `st_flags`) — `fileExists` says yes and lies | measured (storage doc); TN3150 |
| **Ask for it** | `startDownloadingUbiquitousItem` — returns in 1–3 ms, file lands later | any read *is* the request: under this app's policy (ON, measured) the syscall blocks in `msleep` with no timeout until the provider delivers | measured, pass 1 |
| **Is it downloading right now?** | `ubiquitousItemIsDownloading` — a Bool, per URL | **not found** | documented |
| **How far along?** | `NSMetadataUbiquitousItemPercentDownloadedKey` via `NSMetadataQuery`, external-documents scope for a file outside our container — **unmeasured on 26.x FP-backed iCloud, from a sandboxed app** | **not found** | documented; Forums 690124 and Clement (2023) unanswered |
| **Finder's pie** | driven by the provider extension's `fetchContents` `Progress`, consumed by the system | same | documented (extension side only); no consumer API found |
| **Cancel mid-file** | `Task.cancel()` cannot break a blocking copy inside a file; only the bounded read's own timeout returns control | same | `desktop/CLAUDE.md`, 19 Jun 2026 |
| **Failure wording** | Finder: "The item couldn't be downloaded. Please check your internet connection, then try again." | provider-specific, unpublished | user report, May 2022 |

**So: label yes, pie no.** For Google Drive and OneDrive that is definitive
— there is nothing to build a pie from. For iCloud a pie is *possibly*
reachable and §5 is the one probe that says. Even if it is, a pie in a
sidebar row is not this app's idiom — the ring is for Bristlenose's own work —
and the honest maximum would be "Waiting for iCloud… 40%".

## 5. The one open measurement

Whether iCloud's per-file progress is readable at all on today's stack. A
Swift Testing probe in the sandboxed test host, same shape as
`DatalessPolicyProbeTests` (results written to the container's temp dir,
never `/tmp`):

1. An evicted file in iCloud Drive, **tens of MB at least** — pass 1's
   probes materialised ≤ 2 bytes and could not have seen a percent.
2. A security-scoped URL to it (that is how a drag arrives).
3. `NSMetadataQuery` with `NSMetadataQueryUbiquitousExternalDocumentsScope`
   on that URL; `startDownloadingUbiquitousItem`; sample
   `NSMetadataUbiquitousItemPercentDownloadedKey` and
   `ubiquitousItemIsDownloading` every 100 ms until `.current`.
4. In the same run, `Progress.addSubscriber(forFileURL:)` on the URL — the
   other public channel a system component *might* publish through.
5. Evict it back with `evictUbiquitousItem` so net state is unchanged.

Uses the maintainer's iCloud and bandwidth: **ask first, then run**. Three
outcomes, each a one-line edit to §4: percent arrives (iCloud pie possible);
only the Bool arrives (label only, as assumed); neither arrives (iCloud is no
better than the other two, and the label leans on the dataless flag alone).

## 6. What the field ships

From pass 2 (first-hand: vendor docs, release notes, cloned sources):
Carbon Copy Cloner and Arq hydrate silently, bound the batch, and *log*;
Hazel makes it a per-folder policy; Finder shows the pie; **no shipping Mac
app shows a wait label or a per-file cancel.** The HIG asks for a cancel on
any long process and nobody does it here, because nobody can (row 6 above).

The label is therefore a small step *past* the field, not a catch-up. That is
fine — it costs one line and it is true — but it should be described that
way, not as parity.

## 7. What a pick-up would build

Small. About a day, probe and locale seeding included.

- **Detect** — in `CopyMachinery`, per file, before `copyItem`: dataless? If
  so, which store — by path root (`~/Library/Mobile Documents/com~apple~CloudDocs`,
  `~/Library/CloudStorage/GoogleDrive-…`, `~/Library/CloudStorage/OneDrive-…`;
  the storage doc has the table). Set `InFlight.waitingOn: CloudStore?` for
  the three; leave it `nil` for anything else.
- **Bound** — the read gets the timeout `fs.py` uses; on expiry, throw
  `CopyError.underlying(error)` and let Tier 0 render it.
- **Render** — one new `ProjectSubtitle` variant, composed the way
  `RunProgressSubtitle` composes: while `waitingOn != nil` the slot reads
  "Waiting for {{provider}}…"; when it clears, "Copying n of m…" resumes.
- **Localise** — one key, `chrome.copy.waitingFor` with `{{provider}}`, in
  the 21 full locales (not `zh-Hant-HK`). Store names are proper nouns and are
  not translated; check `glossary.csv` for the three before seeding.
- **Pin** — one test on the compose function (which variant wins, and that
  the store outside the three composes to the generic text); the probe from
  §5 stays as a canary if it found anything.
- **Draw first.** The row states below are the spec to scrutinise; an HTML
  mockup in `docs/mockups/` (with its register entry — CI requires one) is
  the first step of the pick-up, per the mockup-is-the-spec rule, not
  something this doc substitutes for.

| Row state | Subtitle | Right slot |
|---|---|---|
| Idle, analysed | *(none — Schema E: clean rows show no status line)* | — |
| Copying, local disk | Copying 3 of 12… | copy ring |
| Copying, blocked on a scoped store | **Waiting for OneDrive…** | copy ring (unchanged) |
| Copying, blocked on any other store | Copying 3 of 12… | copy ring |
| Read timed out | *(row returns to idle; the failure is a sheet or alert with Foundation's sentence — Tier 0)* | — |

## 8. Where the earlier arguments live

- `design-project-storage.md` §3 — the case *for* a label, with the Dropbox
  measurements that were a test bed.
- `design-sidebar-activity-indicators.md` — the Cloud-section reconciliation
  note, which records that the two docs disagreed and, since 4 Sep, the
  three-store scope.
- `design-copy-error-surfacing.md` §8 — both research passes' evidence tables,
  including everything in §4 and §6 here.

When the next session proposes "Fetching from Dropbox…", it is this doc's §2
that answers.
