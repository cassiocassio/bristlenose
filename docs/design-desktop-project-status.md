---
status: partial
last-trued: 2026-08-27
trued-against: HEAD@main (2ac83f6d) on 2026-08-27 (the glyph rule + files popover)
---

> **Trued 27 Aug 2026.** Three line anchors into `ProjectSubtitle.swift` had
> rotted — the second time for these — after the file gained `glyphKind`,
> `glyphAction` and `UnreachableReason`. `resolveIdle` had moved 129 lines and is
> now anchored **by name as well as by number**, so the next drift is survivable.
> The enum's case count is unchanged at 17; nothing was added, only classified.
>
> §"The glyph rule" is new this session and is the authority on which states earn
> a glyph and which earn a door.


## Changelog

- _2026-08-18_ — **Truing pass (`--topic cloud-import`).** Three corrections, one addition. (1) **The 29 Jul "two shipped branches are unreachable" finding has half-expired** — `lastPipelineRunAt` gained a write site on **30 Jul**, *one day after* it was written up (`ProjectIndex.recordPipelineRun`, `ProjectIndex.swift:586`, called from `ContentView.swift:591`; commit *"desktop: Connect Agent sheet + menu item, and /api/health advertises the mount"*). So `+N unanalysed` **does** render now, and the TRAP below is closed rather than pending. `.ready(date:)` is still never drawn — but by Schema E's design, not by accident, which is the opposite kind of fact. Left as the clearest example in this doc of why a dated counterfactual needs re-checking before it's cited. (2) **The precedence chain named 9–10 states against an enum that has 17** — completed, with the idle tier's real order read off `resolveIdle`. (3) **Schema E's "the collapse rule is exactly one state" is now two.** (4) **Cloud import added to §4's catalogue** — a per-project transfer whose window can be closed, carrying three rulings that were only in code comments. Also fixed §4's "File import / copy" row, stale since 19 Jun and self-flagged as unaddressed in the 15 Jul entry.
- _2026-07-29_ — **Schema E: the clean row is silent** (new subsection below, after Precedence). A `.ready` row with no delta now renders **no subtitle at all** and collapses to a single line; only exceptions get a line. Supersedes the June "every row shows a date" deferral **on its merits** — the deferral's trigger (concurrent multi-project execution) has *not* fired. Three further corrections from the same walk. (1) **The "never composed" hard rule is now overridden for `.completedPartial`** — see the new subsection; the rule survives everywhere else. (2) **Two shipped branches are unreachable and were never noticed**: `lastPipelineRunAt` has no write site in any build, so `.ready(date:)` never rendered *and* `ProjectIndex.swift:892` gates the `+N unanalysed` delta on it, so that never rendered either. (3) **Cloud fetch/eviction is an extension of this model, not a separate feature** — new rulings folded into the kinds table; spec in `docs/mockups/cloud-fetch-states.html` + the cloud-fetch handoff.
- _2026-07-15_ — **Truing pass (`--topic` failure-taxonomy).** Two corrections. (1) **§4: `.status` is a multi-pill shelf, not a single pill.** The 19 Jun "app-global only (the Ollama download)" wording read as *one* pill; three now mount (Ollama download, provider out-of-credit, alpha-expiry), each its own `ToolbarItem(placement: .status)` sharing the new `StatusPill` envelope. The axis is unchanged and still right — only the singular framing was stale. Ordering/contention between co-occurring pills is now an **open question** (only pairwise non-co-occurrence is encoded in code). (2) **§3: "Swift only renders it" is no longer strictly true** — an `out_of_credit` verdict now mutates app-global Swift state (sticky verdict → the pill), and the stderr fallback re-derives a provider-scoped credit/rate split when a crash leaves no structured cause. Also: `quota` narrowed to rate-limit, `out_of_credit` added (see [design-pipeline-resilience.md](design-pipeline-resilience.md)). **Not addressed** (pre-existing, flagged): §4's "File import / copy" catalogue row still says copy surfaces in a toolbar pill — stale since 19 Jun and contradicted by this doc's own §§ above; §9 Anchors omits the new pill/model files.
- _2026-06-23_ — added the **native window title + subtitle** as a third per-project status surface (project identity + a lens-contextual count), shipped on `mac-app-layout-reorg`. Updated the Shipped block + the §4 placement axis; the old toolbar-pill title + `WindowTitleManager` are gone (see `desktop/CLAUDE.md` "Native window title + subtitle live on the DETAIL view"). The two-streams framing (row + detail pane) is now three (+ window chrome).
- _2026-06-21_ — trued up, no material changes. The §"Shipped (19 Jun 2026)" block + §4 placement axis verified against `ProjectSubtitle.resolve` precedence (`ProjectSubtitle.swift`, `ProjectSubtitleTests.swift`) and copy-on-row (`ProjectRow.swift`; standalone `CopyProgressPill` deleted). Added front-matter + an inline marker on the pre-decision proposal table so a cold reader doesn't read its projected strings ("Copying · 3 of 5 files", "toolbar pill") as current.

# Desktop project status — the two streams behind the sidebar row and detail pane

**Status:** captured understanding, **not a build plan.** §7's consolidation is a *direction*
(deferred — the post-TestFlight "workspace" horizon); the immediate, ready progress work is the
separate `cached-run-progress-emit` handoff. The detail-pane UX itself is an **open product
requirement** — this doc frames the *state model* that would feed it, deliberately **not** the
screens.

**Why this exists:** the desktop surfaces a project's status across several scattered slots with
no shared model. Before designing the detail-pane "can't show a report" states as a coherent set,
this captures *what's known, where it comes from, and how it's currently arbitrated* — so that
work builds on a map, not a re-discovery. Written 18 Jun 2026 from a code-grounded walk of the
surfaces.

## The proposal (settled 18 Jun 2026) — surface five messages, fitted to the grammar

The grammar already exists and is cross-language-pinned: **`MessageKind`** (`success ✓ · info ℹ ·
warning ⚠ · error ✗ · skipped —`, `bristlenose/ui_kinds.py`, mirrored in `MessageKind.swift`) and
**`run_progress`** (verb · N-of-M · ETA). This is **not** a new system. The concrete work is
surfacing the handful of messages that already have the data but never reach the row — each tagged
with a kind, a rendered string, and a precedence tier — plus eventually lifting the resolver out of
the view (§7). The *only* genuinely-new emission is a mid-run `health` signal — **kept** (see below);
everything else is wiring data that already exists.

**The five (data exists; only the routing is missing):**

> **Note (superseded by "Shipped" below, 2026-06-21):** this table is the *pre-decision projection*. Its "On the row" strings are illustrative — shipped reality differs (copy renders as a byte-`"Copying · N%"`, not "3 of 5 files"; the toolbar pill was removed). See the "Shipped (19 Jun 2026)" block below for what actually landed.

| Message | Source (already there) | Kind | Today | On the row |
|---|---|---|---|---|
| Copying files in | `CopyMachinery.inFlight` | info | toolbar pill | "Copying · 3 of 5 files" |
| Downloading from iCloud | `inCloud(downloading: Progress?)` | info | static glyph | "Downloading from iCloud · 60%" |
| Cached / cold-run ladder | `run_progress` (the `cached-run-emit` fix) | info | frozen "Analysing…" | "Extracting quotes · ~1 min left" |
| Mid-run health | `run_progress` + a `health` field | info | silent | "Extracting quotes · retrying" *(UX TBD — empirical)* |
| Starting… (sidecar) | `ServeManager.starting` | info | detail-pane only | "Starting…" *(only if slow)* |

Routing: the Python-sourced ones ride `run_progress`; the Swift-sourced ones (copying, iCloud,
starting) need only that the subtitle resolver *read existing `@Published` state* — no new channel.

**Shipped (19 Jun 2026, `project-status-line`).** The cached/cold ladder shipped earlier (`78acbf6`).
This branch (a) lifted the precedence chain into a pure, unit-tested `ProjectSubtitle.resolve`
(§7 point 2, realised for the subtitle), and (b) surfaced **Copying** on the row — `"Copying · N%"`,
byte fraction from `CopyMachinery.inFlight` matched by `projectID` (byte-%, not "N of M" — no
file-item source exists) — on the row because copy is a per-project op (the placement axis, §4). Of
the other three: **Starting…** was evaluated and **dropped** — one serve
follows the selected project, so the only row that could show it is the selected one, whose detail
pane already shows the BootView (always-redundant; the table's "open" hedge resolved to "no").
**iCloud download** was **skipped** — `inCloud(downloading:)` is always nil (no observer), and a
download affordance was rejected (F49); the `Progress?` field stays vestigial. **Mid-run health** is
**deferred** — it needs cross-layer plumbing (retry signal → pipeline emit) plus a render the brief
defers to empirical play. So the shipped row vocabulary is: cantFind › failed › running ›
stopped/partial › **copying** › missing › unanalysed › ready.

**Shipped (23 Jun 2026, `mac-app-layout-reorg`).** A **third** per-project status surface
landed — the **native window title + subtitle** (Mail/Notes pattern), distinct from the row
(activity) and the detail pane (report/empty states). The project *name* is the window title
(`.navigationTitle`); a **lens-contextual count** is the subtitle (`.navigationSubtitle`,
keyed on `bridgeHandler.activeTab`):

- **Sessions/Project** — `"16 Sessions · 18h 23m"`: session count + summed
  `sessions.duration_seconds`, read Swift-side from the project DB (`SourceFilesReader` →
  `DurationFormat.human`, mirroring the dashboard's `_format_duration_human`). Stable, painted
  instantly before the report loads.
- **Quotes/Codebook/Analysis** — `"163 Quotes"` / `"3 Codebooks · 47 Tags"` / `"13 Signals"`:
  **live** counts (Signals don't exist in the DB; visible-quote/tag counts shift as the
  researcher edits), computed by the React SPA (`LensSubtitleSync`, `lensSubtitle.ts`) and
  pushed over a new `lens-subtitle` bridge message → `BridgeHandler.lensSubtitle`, rendered
  only when `lensSubtitleTab == activeTab` (so a tab switch never flashes the prior count — a
  cross-process SPA→bridge→Swift timing guard, not unit-testable from either side alone).

This **removed** the old custom `.navigation` title `ToolbarItem` (icon+name pill) and the
`WindowTitleManager` NSViewRepresentable. So the project's *identity + count* now lives in the
window chrome; the **row** keeps *activity* (run progress + copy), the **detail pane** keeps the
report/empty states. Placement axis (§4): per-project *identity + count* → window title/subtitle;
per-project *activity* → row; app-global → the `.status` zone (a multi-pill shelf as of Jul 2026 —
see §4). (`63c731a`, `73b85a6`, `0ac06bf`.)

### The kinds — operational rule (user, 18 Jun 2026)

Defined empirically, case by case ("I know it when I see it"), not by abstract rule:

- **info** = it's just *happening* (progress), or it's *weather* — environmental, self-resolving, not
  actionable (offline, network).
  > **Amended 27 Aug 2026 — `info` also covers "fine, but a bit abnormal; here's
  > something you should know".** `+N unanalysed` is *actionable* and does *not*
  > self-resolve, so by the letter above it is neither `info` nor `warning`
  > (nothing went wrong and the project is perfectly usable). The gap is real:
  > this table classifies **pipeline message outcomes**, and "there is material
  > the report hasn't read" is a standing property of the project, not the
  > outcome of a run. It renders `info` — blue `info.circle` — because nothing
  > failed and the researcher put the files there themselves; orange would be the
  > app scolding someone for using Finder. Recorded here rather than left as a
  > silent stretch of the rule.
- **warning** = a human needs to look — either *something didn't go right*, or *the project isn't
  usable* (even if the user caused it).
- **error** = it actually failed (run can't proceed).

Discriminator is **usability + whether it self-resolves**, *not* cause. (Offline iCloud comes back on
its own → info; an ejected drive kills the project now → warning.)

Worked rulings (the precedents):

| Case | Kind | Why |
|---|---|---|
| retry after rate-limit (mid-run) | info | "just progress" — transient auto-recovery |
| interview transcribed to silence | warning | human needs to look; not a failure |
| iCloud-evicted while offline | info | "like the weather" — will resolve |
| fetching from a cloud provider | info | just happening; indeterminate (progress is *not* observable — providers swap the file in atomically) |
| still fetching after ~3 min | warning | a human should look, but nothing failed and the run continues |
| fetch never completed (30 min) | error | the run stops; the file never arrived |
| file resident but unreadable | error | genuinely damaged — the message the fetch states exist to stop firing wrongly |
| partial completion | warning | something didn't go right |
| drive unplugged / volume ejected | warning | project not usable |
| analysed files missing from disk | warning | "beyond neutral" — files gone |

### The glyph rule — attention, not action (settled 27 Aug 2026)

Precedence picks the winner and Schema E decides whether it is drawn; this
decides whether it earns a **glyph**, and separately whether that glyph has a
**door**. They are two questions, and conflating them is how the sidebar grows
controls.

**A row shows a glyph when there is something the researcher would want to
*know* and might not — not when there is something they *could do*.** That
distinction does the real work: `Stopped` and `Transcribed` both have an
available act (resume, analyse) and get **no** glyph, because the researcher
caused them and already knows. `+3 unanalysed` has the same shape of act and
**does** get one, because the app noticed something that happened outside it.
News, not opportunity.

**A glyph buys attention, not action.** `design-pipeline-diagnostic-popover.md`
is explicit that inline glyphs are typographic markers, and the sidebar's rule is
"attention, not affordance". So a glyph owes no click. `.cantFind` marks the
condition and its act — **Locate** — stays in right-click, because the one fact
worth disclosing (the volume or host name) is already on the row.

**A glyph and its status text are one control.** Wherever there is a door, both
open it. The glyph is a **10pt** target — small on a trackpad, unkind at any
accessibility setting — while the text beside it is a comfortable one; and they
are one message, so splitting the hit region between them is an implementation
artefact rather than a design. The accepted cost is that the subtitle strip stops
being row-selection area: clicking "Run failed" opens the popover instead of
selecting the project. Someone aiming at those words is asking why, and the title
line — the larger half of the row — remains the row's own target. (Added 27 Aug
2026 after the two halves were briefly inconsistent: the text became a target
while the unanalysed delta had no glyph, then it gained a ⓘ and nothing went
back.)

**A door exists only where there is detail with no other home.** A context menu
shows verbs and cannot show a list, so a *list* earns a popover; a single fact
already printed in the subtitle does not. The converse is a hard invariant: **a
door implies a glyph** — a click target the researcher cannot see is worse than
no target at all.

| | glyph | door |
|---|---|---|
| `failed` · `failedDiagnostic` · `completedPartial` | ✗ / ⚠ | diagnostics — a list of per-session failures |
| `unreachable` | ⚠ / ✗ by reason | diagnostics — the reason and the folder path, which appear nowhere else |
| `cantFind` | ⚠, reason-specific symbol | **none** — Locate is a project verb; right-click owns it |
| `deltaOnly(.missing)` | ⚠ | files — which recordings have vanished |
| `deltaOnly(.unanalysed)` | ⓘ | files — which files are waiting, plus **Analyse** |
| everything else | none | none |

Both halves are lifted out of the view and unit-tested —
`SubtitleVariant.glyphKind` and `.glyphAction`, pinned by
`SubtitleGlyphContractTests`. They were a private `default: return nil` in
`ProjectSidebarOutline` until 26 Aug 2026, which is how two states came to draw
no glyph with nothing asking why.

### Precedence — starting order (tweak when seen in reality)

When several conditions are true, the row shows one winner (never composed), most-demanding first:

`drive-unplugged (cantFind) › failed › running` *(the verb ladder; retries ride it as info)* `›
stopped / partial › adding-interviews › importing-batch › copying › downloading-from-iCloud ›
files-missing › unanalysed › starting › ready`

**`SubtitleVariant` is the single source of truth and currently has 17 cases**
(`ProjectSubtitle.swift:11-96`) — more than this chain names. The chain is the *architecture*, and
deliberately skips the mechanical companions (`.copyCancelling`, `.stopping`, `.queued(position:)`,
`.failedDiagnostic`, `.unreachable`, `.deltaOnly`, `.placeholder`), each of which sits immediately
beside the state it qualifies. Read the enum for the full list; read this for the ordering argument.
The **idle tier**'s real order is settled in `resolveIdle` (`ProjectSubtitle.resolveIdle`, `ProjectSubtitle.swift:347`):
`.addingInterviews` › `.importingBatch` › `.copying` / `.copyCancelling` › delta › `.ready`.

Baked-in rulings (user, 18 Jun 2026): **`cantFind` / drive-unplugged outranks ALL activity states**
(failed, running, copying) — you can't open the report if the folder's gone, `copying` ⊥ `cantFind` by
construction (you can't copy media into a folder you can't find, so that pairing never co-occurs), and a
run against a vanished folder is already doomed, so "can't reach the folder" is the only honest line.
This matches the shipped `subtitleVariant` early-return. And **drive-unplugged outranks files-missing**
(whole project gone vs source drift). The self-resolving states below activity (`downloading-from-iCloud`
is "weather", not a dead end) keep a *starting* order, to be tuned once it's seen live.

### Schema E — the clean row is silent (settled 29 Jul 2026)

Precedence picks a winner; **Schema E decides whether the winner is drawn at all.** A `.ready` row
with no delta renders **no subtitle line** and collapses to a single 32pt row. Almost everything else
in `SubtitleVariant` has something to say, so the collapse rule was exactly one state when it was
settled — **it is two since 18 Aug 2026**. `.importingBatch` also draws nothing, but on the SwiftUI
row only, and for an unrelated reason: that row passes `importBatch: nil` because the cloud batch is
published to the AppKit sidebar (`ProjectRow.swift:232-237`). Schema E is a *design* silence; that
one is a *migration* silence, and it disappears at the AppKit cutover.

This **supersedes** the June position ("for TF/alpha every row shows a date so the rhythm is
consistent and the few non-`.ready` rows stand out") — it does **not** fulfil its trigger, which was
concurrent multi-project execution and has not fired. Recorded so a later reader doesn't
reverse it back. Three reasons:

- **The counterfactual already ran.** `lastPipelineRunAt` had no write site in any build, so
  `.ready(date:)` was permanently unreachable and the bare date **never once rendered** — months of
  daily use, every cohort build, and nobody filed it.
  > **The evidence expired on 30 Jul 2026, one day after this was written** — the field gained a
  > write site (`ProjectIndex.swift:586`). The *argument* survives intact and is why Schema E stands:
  > nobody missed the date across all those months. But it can no longer be cited as a live
  > observation, and a reader reaching for it as proof should reach for the months, not the nil.
- **The June reasoning was backwards against `absence is information`.** A subtitle on every row
  distinguishes exceptions by *content*, which must be read; absent subtitles distinguish them by
  *presence*, which is pre-attentive. User: *"a whole wall of greens and one red is not helpful —
  you just need the red."*
- **A run date is low-value on a single-user machine.** A timestamp earns chrome when it records
  *someone else's* action (that's why Mail has dates). The revisit trigger is therefore
  **multi-user, not multi-project**: when a run can be started by someone who isn't you.

**Variable row height is the design, not raggedness.** A taller row is taller because it has more to
say — the height delta is a second pre-attentive channel alongside the glyph colour. Most runs
succeed, so the list is a uniform stack of single-line rows with the occasional taller one.

**An Appearance pref to restore the always-on date is noted for a future experiment — not built.**

**TRAP — `lastPipelineRunAt` must still be written**, even though the date is no longer displayed.
`ProjectIndex.swift:1152` gates the `+N` drift delta on it being non-nil (the F14 policy: no drift
before an analysis baseline exists). Skip the write on the grounds that "we don't show the date any
more" and the sidebar is permanently blank while *looking* finished. The field is **write-only** —
a reviewer must not delete it as unused.

> **Closed 30 Jul 2026** — the write site landed the day after this trap was written:
> `ProjectIndex.recordPipelineRun` (`ProjectIndex.swift:586`), called on run completion from
> `ContentView.swift:591` via `CompletionRescan.projectsFinishingRun`. **`+N unanalysed` renders.**
> The invariant above is unchanged and still load-bearing — it is now *maintained* rather than
> *pending*, so the danger has inverted: the risk is no longer forgetting to add the write, it is
> deleting it during a cleanup because the date it feeds is never displayed.
>
> `.ready(date:)` **does** remain undrawn, and that half of the 29 Jul finding still holds — but for
> a different reason: `resolveIdle` takes `lastRunAt` and deliberately never returns `.ready(date:)`
> (`ProjectSubtitle.resolveIdle`). That is Schema E working as designed, not a dead branch.

> **Retired 21 Aug 2026 — the trap above is void, and its "Closed" note was half true.**
> The gate no longer reads `lastPipelineRunAt` at all. It reads `sessionCount` — the analysis DB's
> own answer to "is there a baseline" — via the now-pure `ProjectIndex.driftGated`. So the field is
> genuinely unread, and a reviewer deleting it is no longer breaking the sidebar. It is retained for
> the deferred Appearance pref, which is a weaker reason than the one stated above; if that pref is
> abandoned, the field and its write site go together.
>
> **Why the trap was wrong, and why it read as right for three weeks.** `lastPipelineRunAt` was
> only ever a *proxy* for "has been analysed", with a single write site reached only when a run
> finishes **in the app**. Anything analysed by the CLI, imported, or analysed by a build predating
> 30 Jul therefore read as never-analysed and had its drift silently deleted — while `hasWorkToDo`,
> three lines downstream, read the same project as *already* analysed from `sessionCount`. The two
> compose into a dead end: no delta on the row, and **Analyse** hidden, because the evidence for it
> had been erased before the predicate ran. "`+N unanalysed` renders" was true only for the projects
> the write site could reach, which is why nobody caught it.
>
> The generalisable lesson, and the reason this is written up rather than quietly patched: **a gate
> and the predicate it feeds must measure the same thing.** Two questions that sound identical
> ("has this been analysed?") resolved against two different sources, and the disagreement was
> invisible precisely because each half was individually defensible. Fixed in `06b57843`, pinned by
> `DriftGateTests` — which had to be created, because the gate was a private `if` and nothing in
> the suite could reach it.

**Open — the drift and failure clauses can describe the same file.** `newFiles` is
"on-disk and not in the DB's ingested set" (`ProjectFolderWatcher.performScanLocked`), and a file
that *failed* to analyse has no session row — so it counts as new. After a partial run, the one
unreadable interview appears in **both** halves of the composed line. Needs resolving before
`.completedPartial` composes: either exclude known-failed basenames from `newFiles` (needs the
failed set readable by the watcher), or scope the drift to files added *since* the run.

### Decided — keep the health signal; UX by empirical play

The degraded-but-running signal **stays** — *rate-limited but still working* is real signal, worth
surfacing. It's **info-level**, not a warning (consistent with retry = info): it conveys the *texture*
of progress, not a call to act. The exact UX is deferred to **empirical play** — e.g. flicker the
subtitle between "Retrying…" and "Extracting quotes" so the user sees both *throttled* and *still
working*, or a suffix, or something else; decide by playing with it. The `health` field on
`run_progress` is the one genuinely-new emission (Python emits the retry / throttle / fallback state);
how it renders is TBD. (User, 18 Jun 2026.)

## 1. One status, two surfaces, two fidelities

A project has *status* — what it's doing, what's wrong, what's waiting. It surfaces in two places:

- **Sidebar row** (compact): one subtitle line + one trailing slot + a leading glyph. The glance.
- **Detail pane** (spacious): the content area when there's no report to show. Room to explain.

Both draw from the *same* underlying state, at different resolutions. Two facts about today:
- They don't render the same subset — e.g. the during-run verb ladder shows on the **row** but the
  **pane** still shows the serve's "Nothing to see here, yet." page mid-run.
- There's no shared model behind them; each surface reaches into the sources independently (§6).

## 2. Two streams feed the status

### Bucket 2 — Python pipeline run-progress (the mature contract)

What the *pipeline* is doing. Measured, timed, and predicted in Python, emitted as an append-only
structured event stream and consumed by Swift:

- **Channel:** `pipeline-events.jsonl` — append-only NDJSON (`bristlenose/events.py`):
  `run_started` / `run_progress` / `run_completed` / `run_failed`.
- **Vocabulary:** a deliberately *coarse* 6-stage ladder — `transcribe → speakers → topics →
  quotes → cluster → render` (`bristlenose/timing.py` `ALL_STAGES`). **Not** the 12 manifest stages;
  ingest / extract-audio / merge / PII fold into neighbours.
- **Prediction:** Welford per-stage estimator → ETA (`timing.py`), gated on ≥4 prior runs.
- **Render:** `RunProgressSubtitle.compose` — a *pure, unit-tested* function: a bare stage id → the
  verb; appends session-count + ETA when present; degrades to "Analysing…" with no signal.
  - **Resume variant (Jun 2026):** `compose(resuming:)` — when the row's run was reconnected from a
    live subprocess at app launch (`PipelineProgress.attachedFromOrphan`), the *generic* lead verb
    becomes "Resuming…" instead of "Analysing…", but only in the indeterminate gap; a known stage
    still leads with its own verb. Silent inline recovery (no banner/toast), per `absence is
    information` + HIG passive-status. Locale `chrome.pipeline.resuming`, all 7 `desktop.json`.
- **Parity:** this is ≈ the set the CLI surfaces as checkmark lines, coarsened for one row. One
  contract, CLI ≡ desktop.

### Bucket 1 — desktop-only per-project activity

What the Mac app knows that Python never sees: project availability, the queue / stop / scan
*brackets* around a run, sidecar lifecycle, file-import copy, source-file watching + counts.
Swift-detected, in-memory. Catalogue in §4.

## 3. The Swift↔Python boundary — three categories

Not a clean "Swift vs Python" line; it's *who detects/owns the state*:

1. **Pure Swift — Python never sees it.** Availability (iCloud eviction, volume unmount via
   NSFilePresenter + volume notifications), queue position, stopping/scanning, sidecar process
   lifecycle, file copy.
2. **Swift detects *over* Python data.** Session count + unanalysed/missing delta —
   `ProjectFolderWatcher` diffs the live folder against `bristlenose.db` (Python-written) via
   `SourceFilesReader` (read-only `?immutable=1`). Python owns the baseline; Swift owns the live
   observation **and the diff** ("there are 2 new files since the last run" is Swift's conclusion;
   Python never makes that comparison).
3. **Python's verdict, Swift renders it — and, since Jul 2026, may act on it.** Run outcome
   (ready / failed / partial) + the failure category — read from `pipeline-events.jsonl`
   (`cause.category` / `message`). Swift doesn't re-derive *why* it's "quota" vs "auth"; it renders
   Python's call.

   Two amendments as of Jul 2026, both worth knowing before you trust the "only renders" framing:
   - **A verdict can now mutate app-global Swift state.** On `cause.category == out_of_credit`,
     `PipelineRunner.deriveFailureState` calls `OutOfCreditModel.recordActiveProviderOutOfCredit`,
     which writes a *sticky* verdict into `LLMValidator`'s cache and lights the app-global pill. Still
     Python's call — Swift doesn't decide it's a billing failure — but the render is no longer
     side-effect-free. It's the one place a run's verdict escapes its own project's row.
   - **The stderr fallback does re-derive.** When a run crashes before writing a terminus event there
     is no structured cause, so `categoriseFailure` regexes the stderr tail — including a
     provider-scoped `out_of_credit` vs `quota` split (Claude/ChatGPT only), mirroring
     `bristlenose/llm/failure_classifier.py`. Fallback only; the structured cause always wins.

On (3): the sidecar is **not a black box** — Swift sees the whole structured stream (every event,
stdout, the log), just not Python's *decision logic*, and can't introspect or steer (one-way,
contract-bounded). It **degrades** to a black box only on the fallback: `PipelineRunner.categoriseFailure`
regex-scrapes the stderr tail when there's no structured cause — which is exactly where it has
misclassified (the LLM-404-rendered-as-Whisper bug). **Rule:** trust the structured verdict; the
stderr guess is an unreliable last resort (`desktop/CLAUDE.md`).

## 4. The bucket-1 catalogue

Structural map (full enum cases + the exact user-facing strings live in the inventory; this is the
architecture, not a string reference):

| Kind | What it knows · source | Surfaced today | Could surface (gap) |
|---|---|---|---|
| **Availability / storage** | folder reachable — volume / network / bookmark / iCloud · `ProjectAvailability`, `ProjectFolderWatcher` | leading glyph + subtitle qualifier + row dim + tooltip | iCloud **download progress** (`Progress?` captured, shown as a static glyph); auto-retry-on-remount |
| **Run lifecycle (desktop brackets)** | queue / stop / scan / orphan-attach + Python's outcome+category · `PipelineRunner` | subtitle (precedence chain) + activity pill + diagnostic popover | a "Preparing…" beat before the first Python event; queue-position movement |
| **Sidecar / serve** | is *this project's* serve process up · `ServeManager`, `BootView` | **detail-pane BootView only — not the row** | whether a per-row "starting…" belongs there (open) |
| **File import / copy** | drag-import byte progress, disk-space precheck · `CopyMachinery` | **the target project's row** — `.addingInterviews` ack, then `.copying(fraction:)` + hover-cancel ring | evicted-source precheck; a copy that outlives the window |
| **Cloud import (Meet / Teams)** | per-batch done/total for a remote fetch into this project · `CloudImportStore.batch` | **the row** — `.importingBatch` renders "3 of 4" with **no verb**, reusing `Kind.ring` + hover-cancel → `stopFetch` (AppKit sidebar; the SwiftUI row draws nothing) | per-file granularity on the row (the window has it); reopening the window from the ring |
| **Source watch / count** | # interviews, unanalysed/missing delta · `ProjectFolderWatcher`, `SourceFilesReader` | title-right count + subtitle delta + tooltip | a "scanning…" tick; evicted-vs-deleted split in "missing" |

### The placement axis — per-project on the row, app-global in the title-bar pill (settled, user 19 Jun 2026)

What surfaces on a project's row is what's *scoped to that project*: its run progress (already moved
there) and a drag-import **copy into** it ("Copying · N%"). You dragged onto *that* row, so the
feedback appears on *that* row — Mac **direct manipulation**. Run progress set the pattern; copying
follows the same logic, which is *why* it belongs on the row and not (only) in the toolbar pill.

App-global / cross-project concerns go in the **title-bar status zone** instead: provider
online/offline (an unavailable provider blocks *every* project, so it's not a per-row signal), an
**Ollama model download**, and other bristlenose-global operations. The toolbar *copy* pill was
**removed** (19 Jun 2026): copy is a per-project op, so its progress *and* cancel now live on the row —
a determinate ring + hover-cancel + "Copying · N%", exactly like a run's ring + Stop (cancel is also
in the row's "Cancel copy" context-menu item, the keyboard/VoiceOver path). The `.status` zone is
now app-global **only** — no per-project state. This is the resolution to the review concern that
copying-in-pill *and* on the row was "redundant" — it wasn't a duplicate to keep, it was a scope
convention to *finish*: one indicator, on the row the bytes land in.

> **Updated 2026-07-15 — `.status` is a multi-pill shelf, not a single pill.** The 19 Jun wording
> ("the `.status` pill zone is now app-global only (the Ollama download)") read as *one* pill; three
> now mount there, each its own `ToolbarItem(placement: .status)` sharing the
> [`StatusPill`](../desktop/Bristlenose/Bristlenose/StatusPill.swift) envelope (capsule + bottom-anchored
> light-dismiss popover): **Ollama model-download**, **provider out-of-credit**
> ([`OutOfCreditPill.swift`](../desktop/Bristlenose/Bristlenose/OutOfCreditPill.swift) — the "provider
> online/offline" case above, now shipped rather than hypothetical), and **alpha-expiry**. The axis
> itself is unchanged and still correct: per-project → the row; app-global → `.status`. What's new is
> that the zone hosts several, so **ordering / contention is now an open question** — only pairwise
> non-co-occurrence is encoded in code (out-of-credit is cloud-only, the Ollama pill is local-setup, so
> they can't both be live for one active provider), and alpha-expiry can co-occur with either. No
> ordering rule is written down yet.

> **Updated 2026-08-31 — the shelf opts out of macOS 26's shared toolbar background.**
> Tahoe wraps *every* toolbar item in its own glass capsule, and all three pills already
> draw one (`StatusPill`'s 0.08 fill / 0.25 stroke / 10×4 padding — `OllamaDownloadPill`
> still hand-rolls the identical values rather than adopting the envelope, so the chrome
> matches even though the type doesn't). The result was a capsule nested inside a brighter
> capsule. Each `ToolbarItem(placement: .status)` now carries `withoutSharedBackground()`
> (in `StatusPill.swift`), which is `sharedBackgroundVisibility(.hidden)` behind an
> `#available(macOS 26.0, *)` gate — the app deploys to **15.0**, and the `26.1` in the
> pbxproj belongs to the *test* target. The pill keeps its own capsule; that was never the
> problem (user, 31 Aug 2026). Applied to all three siblings, not only the one that was
> visible, because they share the envelope and would otherwise drift.

Also deliberately *off* the row, different-surface: export (toolbar chip), AI-consent (global gate).

### The availability split that matters

"Availability" lumps two **opposite** physical conditions:

| Condition | Reality | CLI experience | Desktop state |
|---|---|---|---|
| **iCloud-evicted** | dataless, same path | slow read → **succeeds** (online) | `inCloud` |
| **Volume ejected** | path genuinely gone | **`FileNotFoundError`** — hard fail | `cantFind(.unmountedVolume)` |

One says *wait*; one says *cannot proceed*. Same glyph family, opposite severity — they must never
collapse together in the precedence chain. (And the CLI is *right* to do nothing about iCloud —
macOS materialises the file on read; the only gap is offline, where the read hangs instead of
downloading.)

## 5. The arbitration — the exception-precedence chain

One subtitle line, one trailing slot — but several conditions can be true at once. Pick one, never
compose. Three tiers, in order:

1. **Severity** — most severe wins, and an unreachable project tops it. The order:
   `cantFind → failed → running / stopped / partial → ready+missing → ready+unanalysed → ready`.
   (Ruling, user 18 Jun 2026: `cantFind` / availability beats ALL activity — you can't open the report,
   can't copy into a folder you can't find, and a run against a vanished folder is doomed. Matches the
   shipped `subtitleVariant` early-return.)
2. **Causation** — at comparable severity, the *cause* beats the *effect*. (The volume-eject-mid-run
   case that first motivated this now resolves one tier up, since `cantFind` tops severity — but the
   principle still governs any future same-severity cause/effect pair.)
3. **Recency** — last resort, when severity and causation can't separate two events.

**Hard rule:** never put two conditions on one line. The detail pane is where the *non-winners*
would get room — that's its reason to exist. (Memory: `feedback_exception_precedence_chain`.)

**One sanctioned exception (29 Jul 2026): `.completedPartial` composes.** The row shows
`⚠ +3 new, 1 failure` — drift *and* failure. The rule was written against a character-count
estimate that measurement disproved: the subtitle has **163pt** at the 220pt ideal sidebar width
(220 − 10 leading − 20 icon − 6 gap − 13 glyph − 4 gap − 4 trailing), and the composed string needs
**78–95pt**. A partial run is genuinely two live facts — *these are ready to read* and *this one
needs attention* — and every single-clause option drops one of them. The rule still governs
everywhere else; don't generalise this, and don't "fix" it back.

## 6. The gap — what bucket 1 lacks that bucket 2 has

Bucket 2 has *two* disciplines bucket 1 has **neither** of:

**(a) No unified status model / contract.** ~~Each source publishes independently and the **view**
arbitrates by hand~~ — **partly resolved (19 Jun 2026).** The cross-source *precedence* is now a pure,
unit-tested helper, `ProjectSubtitle.resolve(...) -> SubtitleVariant` (file-scope, no `i18n`/
`DateFormatter`/SwiftUI); `ProjectRow.subtitleVariant` is a thin marshaller and `subtitleContent`
renders the winner. That closes the house-rule violation ("a decision a view makes belongs in a
testable helper", `desktop/CLAUDE.md`) — the bucket-2 leaf (`RunProgressSubtitle.compose`) and the
cross-source precedence wrapping it are now *both* pure helpers. **Still missing:** a single
per-project **`ProjectStatus` value** aggregating the sources (availability + run + count + copy +
sidecar) — today `resolve` takes the already-separate inputs; there's no one aggregate type, and no
reporter protocol.

**(b) No append-only event log.** Bucket 2 has `pipeline-events.jsonl`; Swift is a *reader* of it
(`EventLogReader`), never a writer — there is **no `EventLogWriter`**. Bucket-1 transitions live in
ephemeral `@Published` state + scattered `os.Logger` diagnostics (the OS unified log — unstructured,
partial, never read back) + one-shot files (`projects.json` snapshot, `pipeline.pid`,
`last-run-failure.log` *dump*). A volume ejecting, a copy starting, the queue advancing — none is
captured in a replayable stream. **And there's a privacy reason it's thin:** an explicit rule —
*"never write basenames to os_log, pipeline-events.jsonl, or any persisted channel"*
(`ProjectFolderWatcher.swift`, `NewFilesSheet.swift`) — keeps the re-identification-key data
(filenames, paths, volume names) out of persisted logs. Any bucket-1 log must be redacted the way
Python's stream already is.

## 7. The consolidation direction (deferred — a Could, post-TF)

If bucket 1 is to earn bucket 2's discipline, the shape is:

1. a single per-project **`ProjectStatus` value** aggregating the sources (availability + run +
   count + copy + sidecar);
2. ~~a **pure resolver** — running the precedence *outside* the view~~ — **DONE (19 Jun 2026):**
   `ProjectSubtitle.resolve(...) -> SubtitleVariant`, mirroring `RunProgressSubtitle.compose`
   (pure, testable, view just renders). It takes the separate source inputs directly; folding them
   into the point-1 `ProjectStatus` aggregate is the remaining step.
3. optionally a **redacted append-only event log** as its companion (replayable / debuggable like
   the pipeline events, the obvious substrate for a pane-side timeline).

**The payoff** (and why it matters for the detail-pane work): a resolver outside the view lets the
**sidebar row (compact)** and the **detail pane (spacious)** render the *same* arbitrated state at
two fidelities. As of 19 Jun the subtitle's arbitration is no longer trapped in `ProjectRow`'s body
(point 2 above) — a detail pane could call the same `resolve` today. The remaining substrate for the
"design the detail-pane states as a set" project is the point-1 aggregate + point-3 event log.

## 8. What this is NOT

- **Not the detail-pane UX.** The screens are an open product requirement — owner's call. This frames
  the *state* behind them only.
- **Not a build plan.** §7 is a direction; nothing here is scheduled. The immediate, ready work is
  the separate `cached-run-progress-emit` handoff (bucket-2 coverage — the verb ladder on cached /
  cold-estimator runs), which needs none of §7.
- **Not concurrency.** Instant switching (warm-sidecar pool, Phase A2) and running N projects at once
  (cap-2, multi-window) are separate roadmap rungs; this doc is about *status surfacing*, not
  execution.

## 9. Anchors

- **Code:** `ProjectSubtitle.swift` (`resolve`, `SubtitleVariant`, `SubtitleDelta` — the pure
  precedence resolver + its tests `ProjectSubtitleTests.swift`), `ProjectRow.swift` (marshals inputs,
  renders the winner), `RunProgressSubtitle.swift`, `EventLogReader.swift`, `ProjectAvailability.swift`,
  `SourceFilesReader.swift`, `PipelineRunner.swift` (`PipelineState`, `categoriseFailure`),
  `ServeManager.swift`, `CopyMachinery.swift`; Python `bristlenose/events.py`, `bristlenose/timing.py`.
- **Code (sidebar rendering, added 18 Aug 2026):** `ProjectSidebarOutline.swift` (the **AppKit**
  source list — the path new sidebar work lands on; `ProjectRow.swift` above is the being-deleted
  SwiftUI one, see `design-desktop-sidebar-appkit.md`), `SidebarSubtitleText.swift`,
  `SidebarActivityRing.swift`, `ProjectRowActivityIndicator.swift`, `CloudImportStore.swift`
  (`BatchProgress`), `CompletionRescan.swift` (the `lastPipelineRunAt` write path), `StatusPill.swift`,
  `OutOfCreditPill.swift` (the last two flagged in the 15 Jul entry and unactioned until now).
- **Handoffs (internal):** `cached-run-progress-emit` (bucket-2 coverage, ready), `warm-sidecar-pool`
  (Phase A2 fast switching), `progress-text-detail-pane` (the demoted during-run pane item, folded
  into the detail-pane-set design).
- **Memory:** `feedback_exception_precedence_chain`, the multi-project phase roadmap.
- **Related:** `design-sidebar-activity-indicators.md` (the 0a/0b progress work),
  `design-pipeline-diagnostic-popover.md` (the failure-popover MessageKind vocabulary).
