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

| Message | Source (already there) | Kind | Today | On the row |
|---|---|---|---|---|
| Copying files in | `CopyMachinery.inFlight` | info | toolbar pill | "Copying · 3 of 5 files" |
| Downloading from iCloud | `inCloud(downloading: Progress?)` | info | static glyph | "Downloading from iCloud · 60%" |
| Cached / cold-run ladder | `run_progress` (the `cached-run-emit` fix) | info | frozen "Analysing…" | "Extracting quotes · ~1 min left" |
| Mid-run health | `run_progress` + a `health` field | info | silent | "Extracting quotes · retrying" *(UX TBD — empirical)* |
| Starting… (sidecar) | `ServeManager.starting` | info | detail-pane only | "Starting…" *(only if slow)* |

Routing: the Python-sourced ones ride `run_progress`; the Swift-sourced ones (copying, iCloud,
starting) need only that the subtitle resolver *read existing `@Published` state* — no new channel.

### The kinds — operational rule (user, 18 Jun 2026)

Defined empirically, case by case ("I know it when I see it"), not by abstract rule:

- **info** = it's just *happening* (progress), or it's *weather* — environmental, self-resolving, not
  actionable (offline, network).
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
| partial completion | warning | something didn't go right |
| drive unplugged / volume ejected | warning | project not usable |
| analysed files missing from disk | warning | "beyond neutral" — files gone |

### Precedence — starting order (tweak when seen in reality)

When several conditions are true, the row shows one winner (never composed), most-demanding first:

`drive-unplugged (cantFind) › failed › running` *(the verb ladder; retries ride it as info)* `›
stopped / partial › copying › downloading-from-iCloud › files-missing › unanalysed › starting ›
ready`

Baked-in rulings (user, 18 Jun 2026): **`cantFind` / drive-unplugged outranks ALL activity states**
(failed, running, copying) — you can't open the report if the folder's gone, `copying` ⊥ `cantFind` by
construction (you can't copy media into a folder you can't find, so that pairing never co-occurs), and a
run against a vanished folder is already doomed, so "can't reach the folder" is the only honest line.
This matches the shipped `subtitleVariant` early-return. And **drive-unplugged outranks files-missing**
(whole project gone vs source drift). The self-resolving states below activity (`downloading-from-iCloud`
is "weather", not a dead end) keep a *starting* order, to be tuned once it's seen live.

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
3. **Python's verdict, Swift only renders it.** Run outcome (ready / failed / partial) + the failure
   category — read from `pipeline-events.jsonl` (`cause.category` / `message`). Swift doesn't
   re-derive *why* it's "quota" vs "auth"; it renders Python's call.

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
| **File import / copy** | drag-import byte progress, disk-space precheck · `CopyMachinery` | **toolbar pill + sheet + toast — not the row** | progress on the **target project's row** |
| **Source watch / count** | # interviews, unanalysed/missing delta · `ProjectFolderWatcher`, `SourceFilesReader` | title-right count + subtitle delta + tooltip | a "scanning…" tick; evicted-vs-deleted split in "missing" |

Borderline, deliberately *off* the row (different surface): export (toolbar chip), AI-consent
(global gate), provider online/offline (global Settings badge — an unavailable provider blocks
*every* project, so it's not a per-row signal).

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

## 6. The gap — what bucket 1 lacks that bucket 2 has

Bucket 2 has *two* disciplines bucket 1 has **neither** of:

**(a) No unified status model / contract.** There's no `ProjectStatus` type and no reporter
protocol. Each source publishes independently (`PipelineRunner`, the project's computed
`availability`, the watcher's count, `CopyMachinery`, `ServeManager`), and the **view** arbitrates:
`ProjectRow.subtitleVariant` — a *private computed property on the view* running the precedence
chain by hand. Tellingly, the bucket-2 *leaf* (`RunProgressSubtitle.compose`) is a pure testable
helper, but the cross-source *precedence* wrapping it is not — which quietly violates the house rule
"a decision a view makes belongs in a testable helper, not the view" (`desktop/CLAUDE.md`).

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
2. a **pure resolver** — `ProjectStatus.resolve(...) -> RowState` — running the precedence *outside*
   the view, mirroring `RunProgressSubtitle.compose` (so it's testable and the view just renders);
3. optionally a **redacted append-only event log** as its companion (replayable / debuggable like
   the pipeline events, the obvious substrate for a pane-side timeline).

**The payoff** (and why it matters for the detail-pane work): a resolver outside the view lets the
**sidebar row (compact)** and the **detail pane (spacious)** render the *same* arbitrated state at
two fidelities. Today they couldn't share it even if you wanted them to — the arbitration is trapped
in `ProjectRow`'s body. This is the substrate the "design the detail-pane states as a set" project
would build on.

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

- **Code:** `ProjectRow.swift` (`subtitleVariant`, `SubtitleVariant`), `RunProgressSubtitle.swift`,
  `EventLogReader.swift`, `ProjectAvailability.swift`, `SourceFilesReader.swift`,
  `PipelineRunner.swift` (`PipelineState`, `categoriseFailure`), `ServeManager.swift`,
  `CopyMachinery.swift`; Python `bristlenose/events.py`, `bristlenose/timing.py`.
- **Handoffs (internal):** `cached-run-progress-emit` (bucket-2 coverage, ready), `warm-sidecar-pool`
  (Phase A2 fast switching), `progress-text-detail-pane` (the demoted during-run pane item, folded
  into the detail-pane-set design).
- **Memory:** `feedback_exception_precedence_chain`, the multi-project phase roadmap.
- **Related:** `design-sidebar-activity-indicators.md` (the 0a/0b progress work),
  `design-pipeline-diagnostic-popover.md` (the failure-popover MessageKind vocabulary).
