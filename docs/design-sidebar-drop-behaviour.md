---
status: draft
scope: v1 — unambiguous cases only
last-updated: 2026-05-15
---

> **Status:** Draft V1. Captures the unambiguous-cases-first revision of drop behaviour. **Sequenced after the current `multi-project-drag-onto` branch ships** — see §"Relationship to current branch work" below. The toasts live through cohort 1; this design picks them up for cohort 2 once the wordless-cursor model has been validated against real researcher use. Harder cases (bulk import, multi-project folders, multi-platform mixed folders, merge semantics) are deferred to a sibling V2 doc — `design-sidebar-drop-v2.md`.

# Sidebar Drop Behaviour — V1

## Phase plan

| Phase | Scope | Where |
|---|---|---|
| **Cohort 1** | What's shipping on the current `multi-project-drag-onto` branch: drop-onto-row copy workflow, localised row-state toasts as placeholders, NewFilesSheet stub, accent flash on self-drop. | branch — already in tree |
| **V1** (this doc) | The seven unambiguous cases. Toast → wordless cursor-state refusal. Folder-containing-project → import. BN-project-on-project → accent flash no-op. New single-nested-project import path. | here, post cohort 1 |
| **V2** | Bulk import (folder-of-folders). Multi-nested-project disambiguation. Platform-aware drag-enter for mixed-platform bulk import. Refined depth handling. | `design-sidebar-drop-v2.md` |
| **V3+** (parked) | Merge two projects (drop-on-project becomes a real action). Import-time version compatibility. Cross-project drag (move interviews between projects). | not written |

Cohort 1 ships first because it adds *capability* (real file copy into projects, the pill, rollback, the sheet stub). V1 is a polish pass that swaps placeholder toasts for HIG-correct wordless feedback once cohort 1 has validated that researchers understand the gestures. V2 lands once V1 is in and cohort feedback has shown which of the harder cases researchers actually hit. V3+ is shaped by usage patterns we don't yet have.

## Folder taxonomy

Any folder a user drags from Finder onto the sidebar is exactly one of four kinds. The drop logic decides what to do by classifying first, acting second.

| Kind | What it is on disk | How we detect it |
|---|---|---|
| **Tracked project** | A Bristlenose project this instance already knows about — has a sidebar entry, a path in `projects.json`, possibly cached pipeline output. | Path matches an entry in `ProjectIndex.projects` (after `URL.standardizedFileURL` canonicalisation). |
| **Untracked project** | A Bristlenose project on disk (has `bristlenose-output/` + at least one canonical artefact) that this instance does _not_ have in its sidebar. Typical cause: user reinstalled, opened a colleague's folder, restored from backup. | `LocateFlow.folderLooksAnalysed(url:)` returns true AND no path match in `ProjectIndex`. |
| **Source folder** | Interview media (audio/video) and/or transcripts. Not a project — has no `bristlenose-output/`. The thing that becomes a project when the pipeline runs over it. | Contains files matching `ALL_EXTENSIONS` at depth ≤ 1. |
| **Other** | Anything else — folder of spreadsheets, screenshots, documents, an empty folder, a `.zip`, the user's Music library, etc. | None of the above predicates match. |

These four classifications are mutually exclusive in priority order: Tracked → Untracked → Source → Other. A tracked project that also happens to contain raw media at depth ≤ 1 is still classified as Tracked (the project marker wins). A folder containing media but no project marker is Source.

This taxonomy applies symmetrically to the **drop target** (where the user is releasing) and the **dragged content** (what they're holding). Drop behaviour is a function of both: e.g. dropping a Source folder onto a Tracked project means "add files," dropping a Tracked project onto a Tracked project means "duplicate gesture / merge" depending on relationship, dropping Other onto anything means refuse.

## TL;DR

Outcomes for empty-sidebar drops and for drop-onto-row, expressed in the taxonomy:

| Dragged content | Empty-sidebar drop | Drop onto a project row |
|---|---|---|
| **Tracked project** | Select existing entry, accent-flash to point at it. Nothing changes. | Accent flash on target, no-op _(merge = V3+)_. Includes drop-on-self (already shipped). |
| **Untracked project** | **New: import** — create a sidebar entry pointing at the folder. | Accent flash on target, no-op _(merge with disk-only project = V3+)_. |
| **Source folder** | Create new project _(existing path)_. | Copy files into the target's folder _(cohort 1 shipped)_. State-guard rules apply (running / failed / unreachable refuse during drag). |
| **Other** | Refuse during drag (no-entry cursor). | Refuse during drag (no-entry cursor). |

Zero toasts. One new import path. Drop-target highlighting designed for the eventual merge distinction. Failed/unreachable/running collapse into "row doesn't highlight on hover" — wordless and HIG-correct.

**Note on duplicate-drop:** dropping a Tracked project onto the empty sidebar is no longer treated as an error (today's `DuplicateDropAlert` modal). It's a navigation gesture — "show me this one." Select the existing entry and flash it; that's the answer the user is asking for. Modal alerts are reserved for destructive or unrecoverable actions; this is neither.

**What V1 explicitly does not handle:**

- Folder containing _multiple_ BN projects → V2.
- Folder-of-folders structure (`ClientFoo/{p1, p2, p3}`) → V2.
- Drop matrix when multiple platforms (Teams + Zoom + Meet) are mixed in a single folder for _import_ — the _create-project_ path handles this natively today via `s01_ingest.group_into_sessions()`; the _multi-import_ case waits for V2.

## Relationship to current branch work

The `multi-project-drag-onto` branch shipped (in tree, awaiting QA) a substantial body of drag-and-drop work that V1 inherits and builds on rather than replaces. The split:

### Already shipped (V1 inherits — don't redo)

- **`.dropDestination(for:action:isTargeted:)` per-row.** Replaces the previous SidebarDropDelegate + GeometryReader + custom hit-test machinery. Sidesteps macOS Cocoa-vs-SwiftUI coordinate-space bugs around `DropInfo.location` ([Apple Forums thread 732076](https://developer.apple.com/forums/thread/732076), [thread 667994](https://developer.apple.com/forums/thread/667994)). This is the modern Apple pattern; V1's drag-enter evaluator plugs into it as the `action`/`isTargeted` closure logic.
- **`CopyMachinery.swift`** — same-volume `clonefile` via `FileManager.copyItem`, cross-volume real copy with `Progress`, Cancel + rollback, disk-space precheck. Drop-onto-row's "add files to this project" workflow now actually moves bytes. V1 doesn't touch this; it's the cohort-1 capability that V1's polish pass leaves alone.
- **`CopyProgressPill.swift`** — toolbar pill mirroring `PipelineActivityItem` visual envelope; shows label + progress + Cancel.
- **`NewFilesSheet.swift`** — stub for [#14](https://github.com/cassiocassio/bristlenose/issues/14) (folder watcher); replaced when that lands.
- **`containedAnalysedProjectName(in:)`** helper for detecting parent-folder-contains-BN-project shape. V1 generalises this from "return first" to "return list of all nested" but the scan logic is in place.
- **Self-drop accent flash** (0.4s, [ContentView.swift:942-948](../desktop/Bristlenose/Bristlenose/ContentView.swift#L942)). Matches V1 rule 6 exactly — keep as-is.
- **Row-state guard dispatch.** The decision logic for running/queued/ready/failed/unreachable is already in place; V1 swaps the toast for cursor-state refusal at the same dispatch sites.
- **Localised row-state toasts** (running/analysed/failed/unreachable, 4 keys × 6 locales) + copy-related keys (pill, cancelling, disk-space, folder-contains-project). V1 deletes the row-state toast keys but keeps the copy-related ones — they're describing a real workflow.

### Cohort 1 placeholder behaviour (V1 changes)

The current branch keeps these as cohort-1 placeholders because the wordless model is new and we want the explanatory text in front of testers before we trust them to read the cursor:

- **Toasts for row-state rejections** (running/analysed/failed/unreachable). V1's move: cursor-state refusal on drag-enter (no-entry cursor, target row doesn't highlight) at the same dispatch sites that fire the toast today. The toast keys delete; the dispatch logic stays.
- **Toast for folder-contains-project.** V1's move: detect on drag-enter, route as **import** (rule 2b), no toast.
- **Toast for BN-project-on-project.** V1's move: accent flash no-op, same 0.4s pulse as the self-drop case.

These are sequenced swaps, not rewrites. The cohort-1 work establishes the dispatch points and the helpers; V1 changes the leaves.

### Not affected by the current branch

The V1 cases that don't touch what cohort 1 shipped:

- **Empty-sidebar drops** for folder-that-is-a-project (rule 2a) and folder-containing-one-project (rule 2b) — new import paths, no cohort-1 equivalent.
- **Drag-enter evaluator as a composed predicate.** Today's logic is "evaluate at drop time, refuse with toast." V1's move is "evaluate at drag-enter, drive the cursor." Same data, different timing.

## Why we're revisiting

The shipped behaviour on `multi-project-drag-onto` (see [ContentView.swift:916-986](../desktop/Bristlenose/Bristlenose/ContentView.swift#L916)) refuses several drop shapes with after-the-fact toasts. The conversation behind this doc (14–15 May 2026) identified four problems:

1. **Toasts aren't HIG.** Apple's vocabulary is alerts, notifications, badges, status, haptics. "Floating pill that fades after 3s" is a web/Material import. Mac apps that use it (Bear, Things, some Sketch flows) are borrowing from web; the HIG has no entry for it.
2. **Some "rejections" are valid user intents.** Folder-that-is-a-BN-project should be **import**, not error. The toast hid a missing code path.
3. **Some "rejections" duplicate information already on screen.** Failed / unreachable / running state is already on the toolbar pill and sidebar row glyph. The toast was a second channel for state already shown.
4. **The "Added N interviews" success toast duplicates the sidebar update.** The row's file count changes, children appear. The state change _is_ the confirmation.

Together: the seven-toast matrix collapses to zero toasts + one new code path (import) + cursor-driven drag feedback.

## The V1 rule, in code-shaped detail

Two evaluators compose: **classify the dragged content** (one of the four taxonomic kinds), then **classify the drop target** (empty sidebar, project row, sidebar folder), then look up the action.

### Classifying dragged content

```
classify(url):
  if url is a recognised media file:
    return .sourceFolder([url])    # treated uniformly with folder-of-media

  if url is a folder:
    if projectIndex.tracks(url):                              # path match
      return .trackedProject(projectID)
    if LocateFlow.folderLooksAnalysed(url):                   # bn-output marker
      return .untrackedProject(url)
    if containedAnalysedProjects(url).count == 1:             # exactly one nested
      return .untrackedProject(containedAnalysedProjects(url)[0])
    if containedAnalysedProjects(url).count > 1:              # V2 territory
      return .multipleNestedProjects(...)
    if containsRecognisedMedia(url, depth: 1):                # media at depth ≤ 1
      return .sourceFolder([url])
    return .other

  return .other
```

Priority order is Tracked → Untracked (direct or one-nested) → Source → Other, mirroring the taxonomy. Multiple-nested-projects is a V2 case; V1 refuses it cleanly.

### Classifying drop target

```
classifyTarget(location):
  if location is over a project row:
    if row.state is .running or .queued or .failed or .unreachable:
      return .refusedRow(state)
    return .acceptingRow(projectID)

  if location is over a sidebar folder row:
    return .sidebarFolder(folderID)   # internal-drag: reorder destination
                                      # finder-drag: create project inside
                                      # (shipped sidebar-drop-folder-row, 19 May 2026)

  if location is over a project row's gap (between rows):
    return .reorderGap

  return .emptySidebar
```

### Action table

| Dragged | Target | Cursor | Action |
|---|---|---|---|
| Tracked project | empty sidebar | green plus | Select existing entry + 0.4s accent flash. No model change. |
| Tracked project | acceptingRow (different) | green plus, on release: flash | Accent flash on target, no-op. _(merge = V3+)_ |
| Tracked project | acceptingRow (self) | green plus, on release: flash | Self-drop flash _(already shipped)_. |
| Tracked project | refusedRow | no-entry | Refuse. |
| Untracked project | empty sidebar | green plus | **Import** — new sidebar entry. |
| Untracked project | acceptingRow | green plus, on release: flash | Accent flash on target, no-op. _(merge with disk-only = V3+)_ |
| Untracked project | refusedRow | no-entry | Refuse. |
| Source folder | empty sidebar | green plus | Create new project _(existing path)_. |
| Source folder | acceptingRow | green plus | Copy files into project _(cohort 1 shipped)_. |
| Source folder | sidebarFolder | green plus | **Create new project *inside* the project-sidebar-folder.** Auto-expand the folder on drop. _(shipped sidebar-drop-folder-row, 19 May 2026.)_ |
| Source folder | refusedRow | no-entry | Refuse. |
| Untracked project | sidebarFolder | green plus | **Import as new project *inside* the project-sidebar-folder.** Auto-expand. Adoption path (existing analysed folder), `scan` not `start`. _(shipped sidebar-drop-folder-row, 19 May 2026.)_ |
| Tracked project | sidebarFolder | green plus | Move into the project-sidebar-folder _(internal-drag, already shipped via String payload — typed `ProjectDragID` upgrade captured as follow-up branch)_. |
| Multiple nested projects | empty sidebar | no-entry | V1 refuses _(V2 = bulk import)_. |
| Other | any | no-entry | Refuse. |

**Vocabulary note (19 May 2026, Gruber pass on sidebar-drop-folder-row).** This doc and code comments distinguish "project-sidebar-folder" (the `Folder` model in our sidebar) from "Finder folder" (a directory on disk). User-facing strings collapse to "folder" — sidebar context disambiguates. Do not surface "project-sidebar-folder" in i18n keys or UI copy.

**Follow-up: true Finder-style hover-spring-load.** sidebar-drop-folder-row landed *post-drop* auto-expand (Q4=a) as the floor — confirmation-by-visible-change after the drop commits. The destination is Finder's spring-loaded-folder gesture: hover over a collapsed `sidebarFolder` row for ~500ms (honouring System Settings → Accessibility → Pointer Control → Spring-loading delay) and the disclosure opens *during* the drag, letting the user drop deeper. `DisclosureGroup` doesn't get this for free; needs an `isTargeted`-tied timer. Not in scope for the gap-closing branch; log here so it doesn't evaporate.

**Why the action table, not the predicate cascade I had before.** The old form ("rule 2a wins over rule 2b...") collapsed `classify(content) × classify(target)` into a single linear cascade and lost the structure. The two-stage form makes it obvious that (a) the same dragged content takes different actions depending on the target, and (b) Tracked-vs-Untracked is a real distinction that drives different behaviour even when targets are identical.

**BN-project marker.** Folder contains `bristlenose-output/.bristlenose/pipeline-manifest.json` (the canonical "analysed" artefact, matching what `PipelineRunner.readManifestState` reads). Same predicate as `LocateFlow.folderLooksAnalysed(url:)` ([LocateFlow.swift:59](../desktop/Bristlenose/Bristlenose/LocateFlow.swift#L59)). Tightened 2026-05-15 (sidebar-analysed-honesty, `626cca7`) — was previously `["manifest.json", ".bristlenose"]`; the bare `.bristlenose/` directory is a "looks started" marker (created early in stage 1), not "looks analysed."

**Media allowlist.** `bristlenose.models.ALL_EXTENSIONS`:

```
{.wav, .mp3, .m4a, .flac, .ogg, .wma, .aac,           # AUDIO
 .mp4, .m4v, .mov, .avi, .mkv, .webm,                  # VIDEO
 .srt, .vtt, .docx}                                    # TRANSCRIPTS
```

Swift mirrors this list statically. If it ever drifts, the failure mode is "we don't light up green plus for a format we technically support" — mild.

**Depth.** Strictly ≤ 1. Mirrors [`s01_ingest.discover_files()`](../bristlenose/stages/s01_ingest.py#L42), which recurses one level. Deeper trees refuse cleanly during drag; the user drops one level deeper and it works.

**No pre-flight modal.** The CLI's `_MAX_SESSIONS_NO_CONFIRM = 16` prompt is a terminal-shaped affordance. The desktop equivalent is: accept the drop, create the project, let the pipeline pill report "Found N sessions" as ingest discovers them. User reads N, hits Stop on the pill if they didn't mean it. Non-destructive — the project is still in the sidebar; they adjust the input folder or remove it. Sidecar invocations from the desktop pass `skip_confirm=True` so the underlying prompt never fires.

## Drag-enter contract

Called frequently as the cursor moves. Must be:

- **Cheap.** One `iterdir` on the drop target + one `iterdir` per direct sub-folder. No content reads.
- **Cacheable per drag session.** Same target → same answer until the drag ends.
- **Wordless.** Returns an enum, no human-readable strings.
- **Platform-agnostic.** Knows nothing about Teams, Zoom, Meet. The seven-extension allowlist and the `bristlenose-output/` marker are all the structural knowledge it has.

Swift signature sketch:

```swift
enum DraggedKind {
    case trackedProject(Project.ID)
    case untrackedProject(URL)          // direct or single-nested
    case sourceFolder([URL])
    case multipleNestedProjects([URL])  // V2 candidate
    case other
}

enum DropTargetKind {
    case acceptingRow(Project.ID)
    case refusedRow(state: PipelineState)
    case sidebarFolder(Folder.ID)
    case reorderGap
    case emptySidebar
}

enum DropAction {
    case selectExisting(Project.ID)              // tracked → empty sidebar
    case importUntracked(URL)                    // untracked → empty sidebar
    case createNewProject(URL)                   // source → empty sidebar
    case copyIntoProject(targetID: Project.ID, source: [URL])  // source → row (cohort 1)
    case flashAndNoOp(Project.ID)                // self-drop / tracked-onto-row / untracked-onto-row
    case reorder(...)
    case reject
}

enum DropEvaluator {
    static func classify(_ url: URL, against index: ProjectIndex) -> DraggedKind
    static func evaluate(_ kind: DraggedKind, on target: DropTargetKind) -> DropAction
}
```

Two pure functions; cursor badge and target highlight are driven directly off the returned `DropAction`. Both functions testable without a UI.

## Cross-channel ownership

All platform-specific intelligence (Teams/Zoom/Meet naming, session grouping, pairing rules) stays in the Python sidecar's [`s01_ingest.py`](../bristlenose/stages/s01_ingest.py). Swift's drag-enter knows only the extension allowlist and the `bristlenose-output/` marker.

**V1 consequence:** the create-new-project path (rule 2d) handles _any_ platform mix natively today, because `discover_files()` + `group_into_sessions()` already do. A folder with three Teams interviews, one Zoom-local meeting folder, and one Google Meet pair drops cleanly and produces five sessions. No platform-specific Swift code involved.

**V2 consequence (deferred):** the bulk-import path (folder containing multiple BN projects) needs Swift to enumerate the nested projects and the sidebar-folder feature to group them. The Python side doesn't need to know — the discovery is structural (look for `bristlenose-output/`), not platform-specific. See V2 doc for details.

## What to add / remove / keep (relative to cohort 1)

### Add (V1 net-new work)

- **`containsRecognisedMedia(url:)` in Swift.** Sibling to existing `containedAnalysedProjectName`. Scans top level + one level down for files matching the seven-extension allowlist. ~30 lines.
- **`DropEvaluator`.** Pure function that composes predicates and returns `DropAcceptance`. Testable without UI. Lives next to `LocateFlow.swift` patterns; unit-tested via the helper extraction convention in `desktop/CLAUDE.md` ("If a SwiftUI view is making a decision, the decision belongs in a testable helper"). Today's row-state rejection logic in `handleDropOnProject` becomes one of the `DropEvaluator` cases.
- **Drag-enter cursor-state wiring.** Today the per-row `.dropDestination` closure sets `dropTargetProjectID` only when targeted; V1 also drives `dropTargetIsRefused` (or similar) so the cursor + highlight reflect the rejection during the drag, not after the release.
- **Single-nested-project import code path.** When `DropEvaluator` returns `.acceptAsSingleNestedImport(url)`, create a project entry pointing at the nested folder. Existing `ProjectIndex.addProject` shape; new caller.
- **Empty-sidebar evaluator branches** for rule 2a (folder-is-a-project → import) and rule 2b (folder-contains-one-project → import-the-one). Currently the empty-sidebar drop only creates new projects from media; these are new accept cases.
- **Accent-flash no-op for project-on-project drops.** Generalises today's self-drop flash — set `dropTargetProjectID = id` for 0.4s on any merge-shaped no-op. The visual machinery exists; just a new dispatch case.
- **Generalise `containedAnalysedProjectName(in:)` → `nestedAnalysedProjects(in:)`** returning `[URL]` (or `[String]`) so rule 2b can check "exactly one" and the V2 bulk-import path can enumerate.

### Remove (cohort 1 placeholders V1 retires)

- **Row-state rejection toasts.** Four call sites in `handleDropOnProject` ([ContentView.swift:955, 960, 966, 972](../desktop/Bristlenose/Bristlenose/ContentView.swift#L955)). Replaced by drag-enter cursor-state refusal at the same dispatch sites.
- **Folder-contains-project rejection toast** ([ContentView.swift:936](../desktop/Bristlenose/Bristlenose/ContentView.swift#L936)). Replaced by routing to import (rule 2b).
- **BN-project-on-project rejection toast** ([ContentView.swift:924](../desktop/Bristlenose/Bristlenose/ContentView.swift#L924)). Replaced by accent-flash no-op.
- **`removeBlockedByRun` toasts** ([ContentView.swift:692, 716](../desktop/Bristlenose/Bristlenose/ContentView.swift#L692)). Out of scope for the drop matrix but on the same removal list — disable the menu item instead.
- **i18n keys** for the above: `desktop.chrome.dropProjectOntoProjectToast`, `desktop.chrome.dropFolderContainsProject`, `desktop.chrome.dropOntoRunningProject`, `desktop.chrome.dropOntoAnalysedProject`, `desktop.chrome.dropOntoFailedProject`, `desktop.chrome.dropOntoUnreachableProject`, `desktop.toast.removeBlockedByRun`. Seven keys × six locales = 42 entries removed. The copy-related keys (pill, cancelling, disk-space) stay — they describe a real ongoing workflow.

### Keep (cohort 1 work V1 builds on)

- **Per-row `.dropDestination(for:action:isTargeted:)`.** Modern Apple pattern; V1's evaluator plugs in as the action/isTargeted logic.
- **`CopyMachinery` + `CopyProgressPill` + `NewFilesSheet` stub.** Unchanged. The drop-onto-row workflow they implement is orthogonal to V1's empty-sidebar concerns.
- **`LocateFlow.folderLooksAnalysed(url:)`.** Reused as rule 2a / 2b detector.
- **`containedAnalysedProjectName(in:)` scan logic.** Generalised to return a list (see Add); the directory-walking is already correct.
- **`s01_ingest.discover_files()` + `group_into_sessions()`.** Unchanged. The post-drop pipeline runs these exactly as the CLI does today.
- **Self-drop accent flash.** Already correct under V1's model.
- **Stop button on the pipeline pill.** Universal "I changed my mind" affordance; covers the drop-too-big case.
- **Copy-related i18n keys** (pill label, cancelling, disk-space alert). Describe real workflow, not placeholder text.

## Mac-native rationale, briefly

- **Apple HIG, Feedback page:** _"Reserve [success] confirmation for activities that are sufficiently important — because people typically expect their action or task to succeed, they only need to know when it doesn't."_ Drops the `addedInterviews` toast.
- **Apple HIG, Alerts page:** Alerts are for "critical information" and "destructive actions." Drops the rejection toasts — none are critical or destructive.
- **Melton/Jobs, Safari status-bar story (DF, 2026-04-15):** _"Who looks at URLs when you hover your mouse over a link?"_ Don't add a dedicated surface for transient information; find an existing element already in the user's gaze. Project state is already on the toolbar pill + sidebar row glyph. The drop verdict is already on the cursor badge + target highlight. Toasts duplicated both.

## V1 footguns and parking lot

- **Multiple nested projects (rule 2c).** V1 refuses with no-entry cursor. Researcher drags the inner folders one at a time. V2 lands bulk-import. _Tracked: V2 doc._
- **Deep nesting (`Research/Zoom/2026-01-15.../`).** Refuses cleanly during drag. User drops one level deeper. Acceptable for V1. _Parked._
- **Import-time version compatibility.** Importing a BN project produced by an older Bristlenose may eventually hit schema mismatches. Out of scope for V1. Cheap thing to ensure now: every project carries a `bristlenose_version` stamp in its manifest. _Parked, V3+._
- **Merge-as-future-feature.** Drop-project-on-project is conceptually "combine these." V1: accent flash, no-op. V3+ ships a real "Combine Projects..." command and this gesture becomes its trigger. _Parked._

## Open questions

1. **Single-file drop project name.** `Sarah-interview.mp4` dropped directly creates a one-file project. Filename stem (`Sarah-interview`) as the project name? Prompt? _Tentative: filename stem, user can rename inline._
2. **Drop on empty sidebar vs onto a project row.** This doc treats them uniformly under the V1 predicate. Existing code distinguishes (`handleDropOnProject` adds files to an existing project; sidebar drops create new projects). Need to decide: does dropping media onto an existing project row still mean "add to this project"? _Tentative: yes, that's the explicit user aim; predicates only apply to empty-sidebar drops._
3. **Drift-detection for the extension allowlist.** Swift static-with-test, or sidecar-served at launch? _Tentative: static-with-test. The list has changed once in the project's lifetime._

## Out of scope

- Drag-out (dragging a project _from_ the sidebar to Finder). Different gesture.
- Drag-reorder within the sidebar. Existing `.draggable` + position field handles it; unaffected.
- Drag from one project to another (move interviews between projects). V3+.
- Multi-window drag. SwiftUI's drag system already supports it across windows.

## References

- [Apple HIG — Feedback](https://developer.apple.com/design/human-interface-guidelines/feedback)
- [Apple HIG — Alerts](https://developer.apple.com/design/human-interface-guidelines/alerts)
- [Daring Fireball — Melton: Memories of Steve](https://daringfireball.net/linked/2026/04/15/melton-jobs)
- [Hacker News — "Toasts are bad UX"](https://news.ycombinator.com/item?id=41298794)
- `design-project-sidebar.md` — current shipped sidebar behaviour and drop matrix
- `design-multi-project.md` — data model, ProjectIndex, folder grouping
- `design-sidebar-drop-v2.md` — V2 scope (bulk import, multi-nested, advanced disambiguation)
- `bristlenose/stages/s01_ingest.py` — platform-aware ingest, canonical source of platform smarts
- `bristlenose/models.py` — `ALL_EXTENSIONS` allowlist
- `desktop/Bristlenose/Bristlenose/LocateFlow.swift` — `folderLooksAnalysed()`
