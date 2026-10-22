---
status: decided
last-trued: 2026-10-22
trued-against: HEAD@main on 2026-10-22 (ProjectAvailability.swift, CopyMachinery.swift, utils/fs.py, utils/audio.py, events.py)
---

# Files in the cloud — what we can know, and what we show

**Decided 21–22 Oct 2026 by the owner. This is the one statement; every other doc that touches
iCloud, File Providers, dataless files or a "waiting for the cloud" surface points here. Read it
before proposing anything iCloud-shaped. The question has been re-proposed five times; the answer
is below, and it is not reopened by a new framing.**

## The rule

**Bristlenose's whole job with cloud-backed files is a correct read path.** It detects a
placeholder, reads it with a time limit, and when the limit fires it fails honestly, as an
ordinary failure a retry can fix. It never predicts, narrates, explains or manages what iCloud
(or any File Provider) is doing, and it never guesses why a folder has gone.

No "Waiting for iCloud…", no "Fetching from…", no cloud glyph or arrow, no "In iCloud" state, no
provider-specific advice ("download it in Finder", "turn off Optimise Mac Storage"), no progress,
no ETA.

**Naming the provider is allowed; managing the situation is not** (owner, 22 Oct 2026).
Researchers think "it's on my Dropbox", so naming iCloud Drive, Dropbox, OneDrive, Google Drive, Box
or any other sync vendor is helpful context: Settings ▸ General's "~/Documents — in iCloud Drive",
and cloud import's "not downloaded, on Dropbox". Nothing goes past the name: no wait state, no fetch,
no download offer, and no change in behaviour because a folder is in the cloud. The name lets the
researcher manage their own expectations. The owner rejected dropping the name as "engineering
thinking", so read it as neither permission to build a wait state nor redundant code to delete.
The names come from `ProjectIndex.cloudProviderLabel` and are structural: the
`~/Library/CloudStorage/<Vendor>-<account>` folder name, plus iCloud's `Mobile Documents` and the
File Provider flag. There is no allowlist, so an unknown vendor keeps its own name.

**Decided non-goal: a folder outside Apple's File Provider layout is just a folder** (owner,
22 Oct 2026, "not our problem in 2027 launch"). An old-style `~/Dropbox` install, or any sync client
that doesn't live under `~/Library/CloudStorage`, gets no name and no special case. Don't "fix" it.

## What we measured

The measured record is public:
<https://github.com/cassiocassio/iCloud-wizzard-behind-the-curtain> (probes and verbatim results
per OS version, 4 Sep 2026). The app-side measurement of the same kernel is
`design-copy-error-surfacing.md` §5. The record is the measurement, not the spec: its §4
recommends a "Waiting for iCloud Drive…" label to any app that reads, and warns that a spinner with
no provider and no bound is the hang. That is general advice, and this page is Bristlenose's
decision against the label. Our read has the bound and the row says what work is happening, so it
is not the bare spinner §4 warns about. Short version:

- **A placeholder is a kernel fact.** `SF_DATALESS` is set on a file whose bytes are in the cloud,
  not on the Mac. Reading the flag is a `stat`, which never fetches.
- **What a read does depends on who launched the reader, not on the file.** Anything descended
  from the GUI has the materialisation policy ON: a read blocks until the bytes arrive. That is this
  app, its sidecar, Terminal (`DatalessPolicyProbeTests`). A launchd job has it OFF: the read fails
  at once with `EDEADLK` (errno 11 on macOS).
- **`stat`, `open`, listing a folder, and `mv` or `rm` over a placeholder are safe.** `read`,
  `mmap`, `copyfile` and `FileManager.copyItem` block (ON) or fail (OFF).
- **Eviction follows how recently a file was used, not free space.** 31,134 of 36,201 files were
  evicted with 189 GiB free. Re-eviction keeps no schedule: once after two minutes, another time
  after more than four.
- **A blocking read cannot be cancelled.** The thread sits in the kernel; only our own time limit
  gets control back, at the next file. `Task.cancel()` does nothing to a synchronous `copyItem`.
- **Third-party apps cannot pin a file** (Apple DTS: "There is no API for developers to
  programmatically set the option").

## What we can and cannot know

| Question | Knowable? |
|---|---|
| Is this file a placeholder? | **Yes.** `SF_DATALESS`; on iCloud also `ubiquitousItemDownloadingStatus` |
| Is it being fetched right now? | iCloud only, a yes/no flag. Other providers: no |
| How far along is the fetch? | **No.** A percent key exists on paper, unmeasured from a sandboxed app; other providers have nothing |
| How long will it take? | **No.** Nobody can say |
| Will it stay local, or be evicted again? | **No** |
| Does the study folder exist at its path? | **Yes.** An evicted folder is still at its path |
| Is the drive we recorded mounted? | **Yes.** We stored its volume name and can see `/Volumes/<name>` |
| *Why* has a folder gone (moved, deleted, iCloud Drive off, signed out)? | **No.** Not us, not Finder |

### Finder's cloud icon

Finder's cloud icon on a file is the same per-file placeholder flag, and that is public API. We
could draw it truthfully for a file that exists. We don't, for three reasons:

1. **It goes stale.** Eviction keeps no schedule, so the icon is a snapshot that needs constant
   watching to stay true, and Finder does that watching with Apple's own machinery.
2. **It isn't a state of the study.** A study folder is usually a mix of local files and
   placeholders, and "some recordings aren't on this Mac right now" changes nothing for the
   researcher: the run fetches each one when it reads it.
3. **Policy.** The 1 Aug 2026 mockup already decided "no at-rest cloud state", and the rule above
   forbids narrating iCloud.

So the distinction to keep straight: **"drive not connected" is shown because that absence is
observable. "This file is in the cloud" is knowable and deliberately not shown. "Why is this
folder gone" is not knowable by anyone.** iCloud Drive is not a volume, so it has no
"not connected" equivalent: an iCloud folder is either at its path or it isn't.

## The four patterns

Every cloud-file situation is one of these. If a proposal doesn't fit one, it is new UX and needs
the owner.

| | Situation | What we know | What Bristlenose does |
|---|---|---|---|
| **A** | A file we need is a placeholder (a run, a clip, a still, a drag-in copy) | It's a placeholder | **Invisible correctness.** Read it with the bound (`fs.ensure_materialised`, 30 min). A drag-in copy refuses up front rather than `copyItem` a placeholder, because that copy can't be bounded or cancelled (`CopyMachinery`, `c9176819`). The row keeps saying what work is happening; nothing about the cloud |
| **B** | That read times out | Our bound fired | **An ordinary per-file failure**, retryable (`CauseCategoryEnum.CLOUD_FETCH`), worded as a fact ("wasn't downloaded to this Mac in time") with no provider and no advice. One slow file never sinks the other sessions |
| **C** | The study folder isn't at its path | Only that it's absent | **The existing "can't find the folder" pane with Locate…**, whichever store it used to live on. Never an iCloud-flavoured state |
| **D** | The folder was on a drive we recorded, and that drive isn't mounted | The absence is observable | The existing "drive not connected" state. The only case where a cause is shown, because it is the only one we can see |

## What this rules out, and has already been proposed

Each of these was proposed, at least once, as a helpful touch. Each is either unknowable (it would
be a guess presented as a fact) or knowable but excluded by the rule:

- A "Waiting for iCloud…" / "Fetching from {provider}" label, with or without a percent: proposed
  in `design-project-storage.md` §3 (29 Jul), walked back in
  `design-sidebar-activity-indicators.md`, drawn in `mockups/cloud-fetch-states.html` (1 Aug),
  re-proposed 4 Sep (`design-cloud-wait-label.md`, now marked won't-build), offered again as a
  trust fix 21 Oct. **Won't build.**
- An "In iCloud" availability state with a cloud arrow and a "download it" pane. It was built
  (`ProjectAvailability.inCloud`), and it only ever fired for a folder that had *gone*, labelled
  with where it used to live. That is pattern C mislabelled; remove it.
- A cloud glyph on rows or sessions (Finder's icon), "Keep Downloaded"/pinning, "download all",
  turning Optimise Mac Storage off: see above and `design-project-storage.md` (Bristlenose
  manages nothing).

## As built on 22 Oct 2026, and what is still open

Not everything shipped matches the rule yet. Until the owner decides each item, none of them is
a precedent to copy:

- **The read-path fix (pattern B)** lands with this page: a timed-out read in stage 2 used to
  abort the whole run as a toolchain failure (`AudioToolError`), and on the audio-only path was
  labelled a Whisper failure. It is now a per-session `cloud_fetch` failure, retried next run, with
  the user-facing sentence "Wasn't downloaded to this Mac in time." The provider and filename stay
  in the log line only.
  **One accepted exception:** a renamed recording that is also a placeholder is fetched early, by the
  session registry, to identify it (`session_registry._fingerprint_after_download`). If that times out
  the run still stops, now labelled `cloud_fetch` (retryable) rather than "unknown". Guessing its
  identity instead would risk analysing, and paying for, the same session twice.
- **Two refusals still advise** "Download it in Finder, then drop/choose it again"
  (`desktop.chrome.copySourceNotDownloaded`, `desktop.discussion.guideNotDownloaded`). The refusal
  is pattern A; the advice is the open question.
- **The Screens lens says** "the recording is still downloading from cloud storage"
  (`common.screens.couldNotRead.cloudDownloading`). We only know our bound fired.
- **Cloud import's held row** says "Already imported — the file is on {provider} and needs
  downloading there". The name is settled (allowed); "needs downloading there" is advice, and open.
- **`Location.LocationType.cloud`** is still stored on each study (old `projects.json` files decode
  it) and has no reader. It never changes availability, copy or wording.

## Where else this lives

- `design-project-storage.md` — the storage policy: Bristlenose manages nothing.
- `design-copy-error-surfacing.md` §5 — the app's measured materialisation policy.
- `design-cloud-wait-label.md` — the label's history; status won't-build, superseded by this page.
- `desktop/CLAUDE.md` — the `copyItem` hang gotcha.
- `tests/test_cloud_files_policy.py` — the guard: fails if an English UI string or a hard-coded
  Swift literal narrates cloud storage. Its `ALLOWED` list is exactly the open items above.
- The public measured record above — re-measure there before asserting anything new about
  dataless files.
