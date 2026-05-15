---
status: stub
scope: v2 — bulk import + harder disambiguation
last-updated: 2026-05-15
---

> **Status:** Stub. Captures the V2-shaped problems deferred out of [`design-sidebar-drop-behaviour.md`](design-sidebar-drop-behaviour.md). Not designed in detail; surfaces the questions that V2 will have to answer, with rough tentative directions from the V1 design conversation.

# Sidebar Drop Behaviour — V2

## Vocabulary

V2 uses the four-kind folder taxonomy established in [V1 §"Folder taxonomy"](design-sidebar-drop-behaviour.md#folder-taxonomy):

- **Tracked project** — BN already has it in the sidebar
- **Untracked project** — has `bristlenose-output/` but BN doesn't track it
- **Source folder** — has media at depth ≤ 1, no project marker
- **Other** — none of the above

V1 handles single-classification cases. V2 takes on the cases where a single folder _contains multiple_ classifiable items (typically multiple untracked projects in a parent folder), and cases where the disk structure is deeper than one level.

## Scope

V2 takes on the cases V1 deferred. Most stem from researchers expressing structure-bearing intent — dropping a parent folder that contains multiple projects, or a folder organised by client/study/quarter. V1 refused these cleanly so that V2 can pick them up with proper UX, not as ad-hoc patches.

## Cases V2 handles

### 1. Bulk import: folder containing multiple Untracked projects

`ClientFoo/{project-baa, project-bob, project-alice}` — three nested projects dropped on the sidebar. Each nested project may be Tracked or Untracked; V2 needs to handle both:

- **All children Untracked** → bulk import. Create a sidebar folder named after the dropped folder; each becomes a child.
- **Some children Tracked, some Untracked** → import the Untracked ones into a sidebar folder; flash the existing entries for the Tracked ones to acknowledge them. The user may have intended either "show me what I have" or "import what's missing"; doing both serves both intents.
- **All children Tracked** → no import needed; flash the existing entries (probably collectively, or scroll to the first and select it). Reuse the V1 "tracked → empty sidebar" select-and-flash gesture.

V2 should:

- Detect all nested projects at depth 1 (Swift extension of today's `containedAnalysedProjectName` → return a list).
- For each nested project, classify as Tracked or Untracked using the same `ProjectIndex.tracks(url:)` predicate V1 introduces.
- Create a sidebar folder named after the dropped folder if any imports happen.
- Add each Untracked project as a child of that folder.
- Flash any Tracked entries to acknowledge them (or collapse to a single sidebar scroll if many).

**Open questions:**

- **Name collision.** What if a sidebar folder named "ClientFoo" already exists? Finder-style "(2)" append, or merge into existing? _Leaning: append._
- **Mixed contents.** `ClientFoo/{project-baa, loose-media-folder/, notes.txt}` — direct children include one project and other things. V2 leaning is "import the project, ignore the rest." But this conflicts with the "create-from-media" path (V1 rule 2d): the loose-media-folder _at depth 1_ would normally trigger create-project. Priority needs nailing down: does discovering even one nested BN project suppress the create-project path entirely? _Tentative: yes — projects are deliberate artefacts; mixed-bag drops favour import over create._
- **Project ordering.** Imported in directory order? Alphabetical? Honour `createdAt` from each project's manifest? _Leaning: alphabetical (predictable), but `createdAt` is more research-meaningful. Cohort feedback decides._

### 2. Folder-of-folders: leaf-parent collapse

`BN work / Client X / Project Foo` — Projects at depth 2 inside a parent organised by client. V1 refuses (depth > 1). V2 options, in increasing complexity:

- **(a) Refuse.** Same as V1. Pushes the problem to "drag the inner level." Honest but inconvenient at scale.
- **(b) Leaf-parent collapse.** Walk arbitrarily deep, find all BN projects, group each under a sidebar folder named after _its immediate parent on disk_. So `BN work / Client X / Project Foo` becomes sidebar folder "Client X" containing "Project Foo." Outer "BN work" wrapper is dropped. Preserves the organisationally meaningful level.
- **(c) Mirror-the-tree.** Multi-level sidebar hierarchy. Requires outline-style sidebar support (currently one-level only — `DisclosureGroup` in `List`, see [project-sidebar.md](design-project-sidebar.md)).

_Leaning: (b)._ The constraint is "we have one level of sidebar folders to spend; spend it on the most analytically meaningful level," which is the leaf-parent in most researcher organisations.

**Footgun:** "I dropped my entire Documents folder" — recursive scan that does no harm (returns zero BN projects) but does a lot of `stat()`. Needs a soft depth cap (4? 5?) to bail on pathological cases.

### 3. Mixed-platform _multi-project_ folder (specifically multi-project case)

V1's create-project path (rule 2d) handles single-project mixed-platform input natively via `s01_ingest.group_into_sessions()`. The _multi-project_ case is V2 territory and reduces to the bulk-import problem above — once V2 detects nested BN projects, mixed-platform doesn't change anything; each nested project is its own self-contained artefact.

So no separate handling needed; V2's bulk-import implementation covers it.

### 4. Multiple nested projects (V1's rule 2c)

V1 refuses `folder containing N>1 BN projects` with a no-entry cursor. V2's bulk-import implementation flips this to an accept. Mechanically the same code path as case (1) above.

## Cases V2 does _not_ take on

- **Merge two projects.** Drop-project-on-project becomes a real action ("Combine Projects..."), but the design work is bigger than V2 — needs the merge command itself, schema work for combined manifests, re-clustering, etc. → V3+.
- **Cross-project drag.** Move interviews between projects via drag. → V3+.
- **Import-time version compatibility.** Importing an old project may need migration. V1's version-stamp parking lot covers the cheap thing to do now; the full path is V3+.

## Implementation sketch

V2 changes are mostly Swift; Python is already nested-project-agnostic in the right way (the discovery is "look for `bristlenose-output/`" — same predicate regardless of how many you find).

Swift work:

- Extend `containedAnalysedProjectName(in:)` → `nestedProjectsList(in: depth:)` returning `[URL]` with configurable depth.
- Extend `DropEvaluator` to return `.acceptAsBulkImport([URL])` cases.
- Implement bulk-import flow: atomic creation of one sidebar folder + N project entries.
- Sidebar folder naming with collision handling.

Python work:

- Probably none. `ProjectIndex` and the pipeline already handle multiple independent projects fine; bulk-import is just "do N independent imports atomically."

## Open questions parked for V2 design

1. **Depth cap for the leaf-parent walk.** 4? 5? Configurable?
2. **Should V2 also do platform-aware drag-enter** so a folder of folders without any BN projects but with media nested at depth 2 (e.g. Zoom local folders inside a `Research/` wrapper) lights green? Or stays V1-strict and refuses? _Tentative: stay strict — the V1 rule "media at depth ≤ 1" is honest and the user drops one level deeper. Recursion-for-discovery is an explicit V2 _bulk_ feature, not a relaxation of the V1 create-project rule._
3. **UI for ambiguous drops.** If a folder _could_ be interpreted as either bulk-import or create-project (it contains a project AND it also has loose media), is there ever a case for a "what did you mean?" prompt? The V1 conversation pushed against this (Mac apps trust the user, don't lecture). _Leaning: priority order resolves it deterministically, no prompt._

## References

- [`design-sidebar-drop-behaviour.md`](design-sidebar-drop-behaviour.md) — V1 spec
- [`design-project-sidebar.md`](design-project-sidebar.md) — sidebar architecture, folder support
- [`design-multi-project.md`](design-multi-project.md) — data model
