---
status: current
last-trued: 2026-10-19
trued-against: HEAD@main (52f7e722) on 2026-10-19
---

## Changelog

- _2026-10-19_ — register opened. Six sweeps of HEAD (the planning docs, the existing registers and QA notes, the report and server code, the Mac app in four areas, the pipeline and CLI), deduplicated into the rows below. Raw agent output is kept in the maintainer's private notes, per the rule that unverified findings stay private and conclusions go public; nine security- or privacy-shaped findings are held there too and are not rows here.

# Felt reliability: the register

> "The doors of software need to clunk like an expensive car." — the owner, 19 Oct 2026

From 19 Oct 2026 the lenses are feature-complete, and the work is reliability. This
register is the list of every known way Bristlenose makes a researcher **doubt it**:
an action that does not land solid, immediate, honest and final. A researcher under
deadline judges whether to trust the analysis by the small things: whether a star
stays starred, whether Stop stops, whether "exported" means there is a file.

**What belongs here.** The clunk has three sources, and a row belongs to one of them.

**1. It does the right thing, predictably.** Good engineering: the same action gives
the same result every time, with no race, no luck and no silent degradation. Most
rows today are this family.

| Class | The door that does not clunk |
|---|---|
| `LOSS` | the researcher's own work (stars, tags, edits, names, codebook, settings) is lost or reverted |
| `FAKE` | the product says done, saved, exported or applied, and it is not |
| `SILENT` | something failed and nothing said so |
| `WEDGE` | a spinner, a state or a run with no way out but quitting |
| `SPEND` | the researcher's API credit or an hour of their time spent invisibly |
| `STALE` | the screen shows the old state after an action, until a reload or relaunch |
| `DEAD` | a control is offered and does nothing |
| `CRASH` | a crash, a blank page, a traceback, raw wire text or an untranslated key |

**2. It signals clearly.** Trust signals: feedback, stillness, speed, a layout that
explains itself, and the information offered at the moment it is needed.

| Class | The door that does not clunk |
|---|---|
| `LAG` | a click takes longer to show than its budget (below) |
| `JUMP` | the interface moves under the pointer: flicker, reflow, a vanished selection |
| `PROMPT` | an operating-system dialog with no lead-in |
| `BURIED` | what the researcher needs at this step is not offered here, or not yet, or only somewhere else |
| `UNCLEAR` | the layout makes them hunt, guess or misread what they are looking at |

**3. It does what was expected.** The behaviour matches the researcher's mental model
and follows the workflow they imagined (download, rename, gather in a folder, drop,
read, curate, share, come back with more).

| Class | The door that does not clunk |
|---|---|
| `SURPRISE` | it does something other than what they expected, or asks for steps out of the order they work in |

**The latency budget** is prior art, not invention (Card, Moran and Newell; Nielsen's
three limits): **0.1 s** for direct manipulation (star, hide, select, toggle, switch
lens, type in a search) to show; **1 s** before anything slower shows progress, and
progress must start within 0.1 s; **10 s** is the limit of attention, past which the
wait needs determinate progress and a way to cancel. `LAG` rows are measured, never
read off the code.

**How the families are found.** Family 1 by reading the code and probing it. Family 2
by measuring (click-to-paint timing) and by looking. Family 3 by walking the
researcher's workflow step by step against what they would expect. A `SURPRISE` found
by an agent's walkthrough is a hypothesis about someone else's mental model, so it
enters as `unproven` and is confirmed on a human walk.

**What does not belong.** Missing features; release and CI machinery only the
maintainer sees; security findings (private notes).

**Current focus: family 1.** The first job is to shrink the functional bug surface,
so that at launch the complaints are about taste, not breakage. The sweeps so far
cover family 1; families 2 and 3 are defined so a row found along the way has a
home, and get their own sweeps (a click-to-paint measurement, a workflow walk)
later.

## How a row is ranked

Each row records **how often** a researcher meets the failure (`every` session,
`most` projects, `some`times, `rare`ly) and **what it costs** them when they do
(`high`: lost work, lost money, or a reason to distrust the analysis; `med`; `low`).
Priority follows from those two cells by a fixed rule, so rank is a fact about the
row, not an argument about it:

- **P1** — high cost met at least sometimes, or medium cost met on most projects.
- **P2** — high cost but rare; medium cost met sometimes; low cost met on most projects.
- **P3** — the rest.

`scripts/check-reliability-register.py` computes each row's P and the score below
from the table; `tests/test_reliability_register.py` fails the build when the
document disagrees with its own rows. Change a frequency, cost or status, then run
the script with `--write`.

**Status.** `open`: understood from the code and reproducible. `unproven`: the code
path is read, the failure has not been made to happen — reproduce it before fixing it.
`decision`: waiting on an owner call, not on engineering. `fixed <sha>`: closed, with
the commit and a test that was red before it. `withdrawn`: on investigation not a
failure; the row stays so the reasoning that made it look like one is not repeated.

## The score

<!-- score:begin (generated by scripts/check-reliability-register.py) -->

| | Open | of which unproven | of which awaiting a decision |
|---|---|---|---|
| **P1** | 16 | 1 | 0 |
| **P2** | 60 | 8 | 4 |
| **P3** | 48 | 15 | 1 |
| **All** | 124 | 24 | 5 |

**0 of 124 closed (0%).**

<!-- score:end -->

### Burndown

| Date | Rows | Closed | Open | P1 | P2 | P3 |
|---|---|---|---|---|---|---|
<!-- burndown:begin (one line per --record) -->
| 2026-10-19 | 124 | 0 | 124 | 16 | 60 | 48 |
<!-- burndown:end -->

## The register

Rows are grouped by **root cause**, because the burndown is fastest when one fix
closes a cluster. A row keeps its id for life. Line anchors are HEAD on the date
in the front matter; `ContentView.swift`, `BridgeHandler.swift`, `MenuCommands.swift`
and `FeedbackSheet.swift` anchors are from HEAD, not a working copy.

### C1 — Curation writes replace the whole map

Every curation write (`putTags`, `putStarred`, `putHidden`, `putEdits`) sends the
client store's entire map, and the server treats it as the truth for every quote in
the project: `put_tags` deletes every tag row on every quote, AutoCode's included,
then re-inserts what the client sent (`server/routes/data.py:895-904`). Anything the
store does not hold is erased by the next gesture. **Fix shape:** per-quote delta
writes; until then, scope the deletes to the quotes the client can see and refresh
the store after any background tag write.

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R1 | Tags AutoCode re-applied after new sessions vanish at the next tag gesture | LOSS | most | high | P1 | open | `routes/data.py:878-951`; `app.py:1243-1256` runs the re-apply after `last_run` is published and nothing refetches |
| R2 | Undo a speaker recode and the quotes come back without their stars, tags, edits and hides | LOSS | some | high | P1 | open | `speaker_slots.py:366-405` hides them from `/quotes`; `_quote_ids_for_project` (`data.py:248`) still covers them |
| R3 | A deleted tag or uninstalled codebook comes back under Uncategorised; denied proposals reappear | LOSS | some | high | P1 | open | `QuotesContext.tsx:228-254` (`replace=false` keeps removed tags); `data.py:922-944` re-creates unknown names |
| R4 | Fast gestures, or an act then ⌘Z, leave the server in the opposite state to the screen | LOSS | rare | med | P3 | unproven | `api.ts:214` `firePut` is unqueued; the routes run in a threadpool |

### C2 — Optimistic writes with no rollback or no message

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R5 | Accepting or denying an AutoCode proposal looks done when it failed | SILENT | some | med | P2 | open | `QuotesContext.tsx:684,701`; `ThresholdReviewModal.tsx:145-178` — `console.error` only |
| R6 | Renaming, creating, deleting, moving or merging codebook tags fails without a word | SILENT | some | med | P2 | open | `hooks/useCodebookAuthoring.ts:111-214`; a tag-name clash is a 409 the client never pre-checks |
| R7 | "Couldn't save" appears, and the star, hide, tag or edit stays on screen anyway | FAKE | rare | med | P3 | open | `QuotesContext.tsx:354-660`; `firePut` toasts but never rolls back |
| R8 | A codebook on/off switch fails and badges stay hidden (or shown) against the server | FAKE | rare | med | P3 | open | `CodebookV2Sidebar.tsx:276-295`; `putFrameworkStates` never rejects, so the `.catch` is dead |
| R9 | Undoing a paragraph split or join fails silently, and Edit then offers Redo | SILENT | rare | med | P3 | open | `paragraphEdits.ts:101,115,133`; `UndoStore` moves the entry before awaiting |
| R10 | Deleting a badge, accepting or denying a proposal, or a codebook change can't be undone; a denied proposal is gone for good | LOSS | some | med | P2 | open | `QuotesContext.tsx:642,666,689` push no undo; `ThresholdReviewModal.tsx:80` shows pending only |

### C3 — Background work the report never hears about

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R11 | AutoCode says "Coded ✓" but no proposals appear on the Quotes lens until a reload | STALE | most | med | P1 | open | `AppLayout.tsx:851-857` dispatches only `codebook-changed`; the islands listen for `bn:tags-changed` |
| R12 | Re-enabling a codebook starts paid re-coding with no chip and no visible result | DEAD | some | med | P2 | open | `routes/data.py:1471` returns `catchUp`; `CodebookV2Sidebar.tsx:292` discards it |
| R13 | An activity chip spins forever after a server restart or failed polls | WEDGE | some | med | P2 | open | `ActivityChipStack.tsx:191-199`; clips map `idle` to running (`AppLayout.tsx:747`) |
| R14 | A reload during a job loses its chip, and its result is never shown | STALE | some | med | P2 | open | `contexts/ActivityStore.ts` is memory-only, never rehydrated |
| R15 | View Report on the AutoCode chip, before Codebook was ever opened, goes there and opens nothing | DEAD | some | low | P3 | unproven | `AppLayout.tsx:870` fires before the lazy `CodebookV2` listens |
| R16 | After AutoCode the tag list is a wall of zeros, so it reads as broken | FAKE | most | low | P2 | open | `TagRow.tsx:151-153`; design settled in 100days § Captured |

### C4 — Re-analyse and the guard on curation (Mac)

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R17 | Star or tag, then Re-analyse: it starts without the "you'll lose N edits" sheet and the work is gone (lifecycle row 35) | LOSS | some | high | P1 | open | `CurationCountsReader.swift:70` opens `?immutable=1`, blind to the WAL (`db.py:87`); only the importer checkpoints (`importer.py:169`); `ContentView.swift:1781-1785` skips the sheet on zero |
| R18 | Re-analyse while another study is running: it queues, drops `--clean`, and ends "ready" on the old analysis | FAKE | some | high | P1 | open | `PipelineRunner.swift:1308-1313` queues ids only; `:1414-1417` admits it; `:1921` |

### C5 — Quit, Stop and who owns a run (Mac)

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R19 | Quit mid-run: on relaunch it says "Resuming…", then fails; queued studies are dropped | LOSS | some | high | P1 | unproven | run output piped to the app (`PipelineRunner.swift:1519-1521`); no `applicationShouldTerminate`; Rich exits on a broken pipe (probed) |
| R20 | Stop during transcription sits on "Stopping…" for minutes | WEDGE | some | med | P2 | open | `PipelineRunner.swift:1326-1331` sends SIGINT only; escalation exists for reattached runs (`:1391-1410`) |
| R21 | Stopping a run the app started leaves the row blank; the same Stop on a reconnected run says "Stopped" | STALE | some | low | P3 | open | `PipelineRunner.swift:1659-1666` writes `.idle` |
| R22 | A run the app doesn't own (a CLI run on a sidebar study) shows "Analysing" forever, Stop does nothing, and the Mac never sleeps | WEDGE | rare | high | P2 | open | `EventLogReader.swift:242-244`; `applyScanResult` never overwrites `.running` (`PipelineRunner.swift:1014`) |
| R23 | A run that finishes as another starts leaves its study "Analysing" forever | WEDGE | rare | high | P2 | open | `PipelineRunner.swift:1648` clears `currentlyRunning` before the await; `:1682` |
| R24 | Stopping a reconnected run that needed force shows "Failed", and a Re-analyse's old report stays set aside | FAKE | some | med | P2 | open | `PipelineRunner.swift:1402-1405`; the stash restore is in a `finally` SIGKILL skips |
| R25 | The failure popover says "unknown" while the traceback that explains it lands a moment later | SILENT | some | med | P2 | unproven | `PipelineRunner.swift:1669` snapshots before the reader drains (`:1531-1555`) |
| R26 | On a large study the progress ring and readable count freeze partway | STALE | rare | med | P3 | unproven | `EventLogReader.swift:150-166` reads the last 64 KB and needs `run_started` in it |
| R27 | The progress ring sits nearly full for a long time, so the run looks stuck | WEDGE | every | low | P2 | open | the ring is elapsed over predicted time, with no stage weighting |
| R28 | Studies behind one whose sidecar can't be found stay "Queued" for ever | WEDGE | rare | low | P3 | open | `PipelineRunner.swift:1468,1479-1482` return without `startNextQueued()` |
| R29 | A run that succeeded reads "Can't be reached" on a slow disk | STALE | rare | low | P3 | unproven | `PipelineRunner.swift:1739-1748`; nothing re-scans |
| R30 | Lid closed mid-run: calls in flight don't survive sleep or a network change, and nothing resumes on its own | WEDGE | some | med | P2 | unproven | 100days § Captured, "Run resilience"; three slices landed (`bf71f81c`, `2e629f8d`) |

### C6 — Runs that look hung, or are

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R31 | First launch on a new Mac: "Bristlenose didn't finish starting"; Retry works | FAKE | most | high | P1 | open | `ServeManager.swift:706-711`, a flat 15 s timer; the cause is first-launch signature checks |
| R32 | First analysis in the app spins silently through a 1.6 GB Whisper download | WEDGE | most | med | P1 | open | the honest pill (`WhisperDownloadModel.swift:220,231`) is behind a parked flag |
| R33 | One long, dense interview runs for about 70 minutes and then fails; split in two it works | SPEND | some | high | P1 | open | `s09_quote_extraction.py:418` splits only on truncation; `client.py:665` 600 s × 6 retries |

### C7 — Settings that save on the wrong gesture (Mac)

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R34 | Tabbing through the API-key field rewrites the key, bills a validation call and reloads the report; the slider and Azure fields reload it per step | JUMP | some | med | P2 | open | `LLMSettingsView.swift:366-369,413-421,570-572,600-605`; `ServeFleet.swift:284` never compares envs |
| R35 | A setting changed while a study is opening never reaches it — a new key, a provider switch, Anonymise | STALE | some | high | P1 | open | `ServeEnvStaleness.swift:90-92` returns `.nothing` during `.starting` |
| R36 | A key that failed to save looks saved | FAKE | rare | high | P2 | open | `LLMSettingsView.swift:413-419` repaints and still posts the change |
| R37 | A key first set up in Terminal can't be removed in the app: it comes straight back | FAKE | rare | high | P2 | open | `KeychainHelper.swift:576-584` (delete refused), `:794-805` (re-adopted) |
| R38 | A pasted key not committed with Return is thrown away on ⌘W or a row change | LOSS | some | med | P2 | unproven | `LLMSettingsView.swift:364-369,386-390` |
| R39 | Opening Settings ▸ LLM Provider can raise a keychain dialog with no lead-in | PROMPT | rare | med | P3 | open | `LLMSettingsView.swift:364-365,386-389` read with interaction allowed on appear |
| R40 | The "Out of credit" pill stays lit after a top-up and a successful run | STALE | rare | med | P3 | open | `OutOfCreditModel.swift:79` is sticky; nothing re-validates |
| R41 | Accounts says "Not connected" over a sign-in it can't read, and offers no Disconnect | STALE | rare | med | P3 | open | `CloudGrantStore.swift:502-547` drops failed loads |
| R42 | Install for Claude Desktop falls back silently, or does nothing | SILENT | rare | med | P3 | open | `MCPAgentsSettingsView.swift:1447-1471` |
| R43 | A second cloud account isn't shown and can't be removed | STALE | rare | low | P3 | open | `AccountsSectionModel.swift:237` takes `.first` |
| R44 | Choosing a default project folder can do nothing at all | SILENT | rare | low | P3 | open | `GeneralSettingsView.swift:190` ignores the refusal |

### C8 — Drops and adds that accept, then do nothing or the wrong thing (Mac)

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R45 | Dropping an iCloud-offloaded recording hangs the copy; Cancel does nothing; only force-quit clears it | WEDGE | some | high | P1 | open | `CopyMachinery.swift:170` blocking `copyItem` on a dataless file; cancel checked only between files (`:153`) |
| R46 | A drop on the empty "Drop a folder" pane makes a second row for a study already listed, or an empty project from PDFs | FAKE | some | high | P1 | open | `ContentView.swift:3717-3720` bypasses `handleDrop` |
| R47 | Dropping on a running, queued or failed study highlights it, accepts, and does nothing | SILENT | some | med | P2 | open | `ContentView.swift:3456-3459,2446` (the default SwiftUI sidebar never refuses) |
| R48 | Unsupported files get a "+" cursor and then vanish; File ▸ Add Files lets you pick them | SILENT | some | med | P2 | open | `ProjectSidebarOutline.swift:1218-1261`; `ContentView.swift:1338-1352` sets no content types |
| R49 | The same interview under two names is transcribed, paid for and counted as agreement | SPEND | rare | high | P2 | open | TODO.md, duplicate recordings; a re-drop of one file is recognised, a renamed copy is not |
| R50 | A study added without a usable bookmark looks fine, then reads "Can't be read" next launch | FAKE | rare | med | P3 | unproven | `ProjectIndex.swift:1203-1215` stores a nil bookmark and adds the row |

### C9 — The sidebar moves under the pointer (Mac)

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R51 | Every study vanishes from the sidebar after a damaged `projects.json`, and nothing says why (lifecycle row 36) | LOSS | rare | high | P2 | open | `ProjectIndex.swift:1657-1672` sets it aside and shows an empty Welcome |
| R52 | Removing the selected study selects nothing and drops the window to the empty state | JUMP | some | med | P2 | open | `ContentView.swift:1925-1929`; Finder and Mail select a neighbour |
| R53 | A new study lands off-screen and the drop's acknowledgement flash never shows (AppKit sidebar) | JUMP | some | med | P2 | open | `ProjectSidebarOutline.swift:582-600` never scrolls; `dropTargetProjectID` is not plumbed in |
| R54 | Deleting a sidebar folder scatters its studies among the root rows, and can't be undone | JUMP | some | low | P3 | open | `ProjectIndex.swift:868-874` keeps in-folder positions |
| R55 | Renaming the study folder in Finder doesn't rename its sidebar row | STALE | some | low | P3 | decision | `ProjectIndex.swift:1529-1578`; no written decision either way |
| R56 | The sidebar stops updating while a rename field is open | STALE | some | low | P3 | unproven | `ProjectSidebarOutline.swift:570` |
| R57 | A row grows and shrinks a line as work starts and ends (AppKit sidebar; the default sidebar reserves the line) | JUMP | rare | med | P3 | open | `ProjectSidebarOutline.swift:1838-1848`; `ProjectRow.swift:210-212` is the fix already made |
| R58 | ⌘N: the new study's icon goes blank while you type its name (AppKit sidebar) | JUMP | rare | low | P3 | open | `ProjectSidebarOutline.swift:596-599,645,662-665` |
| R59 | Launching, or plugging in any drive, can raise a "Connect to server" dialog or a beachball for a study on a sleeping share | PROMPT | rare | high | P2 | unproven | `ProjectIndex.swift:1240-1252` resolves without `.withoutUI`/`.withoutMounting` on the main thread; `ProjectFolderDefaults.swift:222-234` |
| R60 | The app stalls while a study's share is mounted but unreachable | JUMP | rare | high | P2 | unproven | `ProjectAvailability.swift:129-131`, a `fileExists` read about seven times per row per redraw |

### C10 — Controls that are live when the action can't run

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R61 | Export Report during a first analysis, or after a stopped one, does nothing | DEAD | some | med | P2 | open | `AppLayout.tsx:566` `break`; `MenuCommands.swift:642-646` gates on the channel only |
| R62 | Send to Miro is enabled and does nothing when the report server isn't running | DEAD | some | med | P2 | open | `MenuCommands.swift:1725-1728`; `ContentView.swift:1624-1628` |
| R63 | Analyse is offered on a study whose drive was ejected, and runs against a missing path | DEAD | some | med | P2 | open | `ProjectSidebarOutline.swift:2126-2129,2336,2369`; `PipelineRunner.start` has no availability guard |
| R64 | Project ▸ Re-analyse stays dimmed after a first analysis until you reselect the study | STALE | most | low | P2 | open | `ContentView.swift:1458` computes it only on selection change |
| R65 | Hovering a session row on the Project tab highlights it; clicking does nothing | DEAD | every | low | P2 | open | `Dashboard.tsx:262` `CompactSessionRow` (the Sessions lens was fixed in `729033bb`) |
| R66 | Folder ▸ Archive is always there and always dimmed | DEAD | every | low | P2 | open | `ProjectSidebarOutline.swift:2234` |
| R67 | Toolbar search on Sessions, Codebook and Signals takes typing and filters nothing | DEAD | every | low | P2 | decision | `ContentView.swift:2862-2878`; documented as deliberate in `desktop/CLAUDE.md` |
| R68 | Quotes ▸ Reveal in Transcript does nothing | DEAD | some | low | P3 | open | `useKeyboardShortcuts.ts:850` needs a `data-anchor` no card sets |
| R69 | ⌘P on the Welcome screen raises "doesn't support printing" | PROMPT | some | low | P3 | open | `MenuCommands.swift:695` — a disabled item doesn't swallow its key |
| R70 | After the sidecar dies, the Quotes, Video and Undo menus stay enabled and do nothing | DEAD | rare | low | P3 | open | `BridgeHandler.swift:397-402` clears only `hasChannel` |
| R71 | Send to Miro with no exportable quotes ends in a red "export failed" | DEAD | rare | low | P3 | open | `miro_export.py:416` |

### C11 — Exports that don't say whether they worked

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R72 | Reveal in Finder on a finished clips or screens export does nothing in the app (clips even reports success) | FAKE | some | med | P2 | open | `routes/clips_export.py:918-927`; `AppLayout.tsx:735,795`; the native `reveal-in-finder` (`BridgeHandler.swift:1379`) is unused |
| R73 | A quote the researcher hid still comes out as a clip | FAKE | some | med | P2 | open | `clips_export.py:186` filters on starred only |
| R74 | Ticking Anonymise in the save panel throws away the Save and asks again | FAKE | some | med | P2 | open | `WebView.swift:644-657` cancels and re-requests |
| R75 | A server error during export can be saved as though it were the report | FAKE | rare | high | P2 | unproven | `WebView.swift:589-662` never checks the status before the save panel |
| R76 | Export Report shows nothing until the save panel appears; pressing again queues a second | SILENT | some | low | P3 | unproven | `AppLayout.tsx:223-240` |
| R77 | Two quotes from one participant starting in the same second: exports keep only one | LOSS | rare | med | P3 | open | the quote's DOM id is participant plus whole second (`server/CLAUDE.md`) |
| R78 | A Miro status check that fails shows the Connect screen, as if signed out | FAKE | rare | low | P3 | open | `MiroExportPanel.tsx:255` |
| R79 | A Miro board reads "ready" with no link, and Open in Miro does nothing | FAKE | rare | low | P3 | unproven | `MiroAPI.swift:256` substitutes `""` |

### C12 — Feedback that may never arrive

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R80 | A feedback send that fails never says so: no "Sending…", a 60 s wait, then "Copied to clipboard" with nowhere to send it | SILENT | some | med | P2 | open | `FeedbackSheet.swift:102-116`; `FeedbackSubmission.swift:136-157` |
| R81 | The feedback sheet can sit on a spinner with no Cancel and no Esc | WEDGE | rare | med | P3 | open | `FeedbackSheet.swift:164-168`; `FeedbackHealth.load` has no timeout |
| R82 | Send Feedback opens a sheet in every window, or in none | DEAD | some | low | P3 | open | `MenuCommands.swift:1939-1945`; `BridgeHandler.swift:1351-1362` |
| R83 | Report feedback text is lost when both the send and the clipboard fallback fail | LOSS | rare | med | P3 | unproven | `FeedbackModal.tsx:103-117` |
| R84 | Nobody has checked end to end that feedback from an expired build lands | SILENT | rare | low | P3 | unproven | `AlphaExpiryFlow.swift:14` "send failures are silent" |

### C13 — Errors shown raw, or one crash that takes everything

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R85 | One crash in any lens blanks the whole report, navigation and sidebars included | CRASH | rare | high | P2 | open | `router.tsx:36` has the only `errorElement`, on the parent |
| R86 | Raw wire errors ("GET /transcripts/s3 404: …") and hard-coded English, with no Retry | CRASH | some | med | P2 | open | `TranscriptPage.tsx:408,890`; `QuoteSections.tsx:188`; `Dashboard.tsx:680`; `CodebookV2.tsx:768` |
| R87 | After a CLI `serve` restart an open tab can't save anything and doesn't say to reload | WEDGE | some | med | P2 | open | no 401-means-stale path (`LastRunStore.ts`, `ConditionStore.ts:83`) |
| R88 | A quote edit in progress is lost when the lens is switched from the native sidebar or ⌘1–5 | LOSS | some | med | P2 | unproven | `QuoteCard.tsx:282-293,358-369` commit on pointer/blur only |
| R89 | The report forgets zoom, grouping and panel widths every time the Mac app relaunches | STALE | every | low | P2 | open | `AppLayout.tsx:171`, `QuoteGroupingToggle.tsx:39` and others write `localStorage`, which the app discards |
| R90 | Toasts appear in every open window, not the one that acted | JUMP | some | low | P3 | open | one app-wide toast store (`BristlenoseApp.swift:180`) |
| R91 | A screenshot that failed once stays "unavailable" until a reload | STALE | rare | low | P3 | open | `islands/screens/ScreensLens.tsx:277,297,336` |
| R92 | A transcript's Timeline button disappears after one failed fetch | STALE | rare | low | P3 | open | `TranscriptPage.tsx:657-663` |
| R93 | A hidden tag group's eye snaps back | JUMP | rare | low | P3 | unproven | `SidebarStore.initHiddenTagGroups` (`:577`) has no generation guard |
| R94 | A Miro error arrives in English while the app is in another language | CRASH | rare | low | P3 | open | `docs/i18n-defects.md` row 46 |
| R95 | The Codebook page loads something that 404s | CRASH | rare | low | P3 | unproven | `e2e/ALLOWLIST.md` CI-A4; cause unknown |
| R96 | The expired `.dmg` sits on "starting" behind its expiry message | WEDGE | rare | low | P3 | open | `ServeManager.swift:516` returns early, leaving `.idle` |

### C14 — Analysis that is quietly wrong

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R97 | One failed call during speaker identification fixes wrong roles or names, and reruns never retry it | SILENT | some | med | P2 | open | `pipeline.py:2222-2229` marks every session complete |
| R98 | "Thank you." and words nobody said, over music or noise, become transcript and then quotes | FAKE | some | med | P2 | open | `s05_transcribe.py:151` gates true silence only; no voice-activity filter on the Mac |
| R99 | Quotes counted in Signals include ones the researcher hid | STALE | some | med | P2 | decision | `server/routes/signals.py` never reads hidden state; owner call deferred 16 Oct |
| R100 | The folder holds interviews, and the app says there is nothing to analyse | FAKE | some | med | P2 | decision | `server.json` `noRunDesktopShort`; `ProjectIndex.driftGated` (`:1492`) |
| R101 | A Meet doc with an empty Transcript tab: Gemini's summary is analysed as if participants said it | FAKE | rare | high | P2 | decision | `s04_parse_docx.py:187` falls back to plain paragraphs |
| R102 | A provider retires a model and every analysis fails with "the provider rejected the request" | CRASH | rare | high | P2 | open | `failure_classifier.py:48` reads it as a generic bad request; no EOL watch |
| R103 | On Windows, re-analysing while the report is open overwrites it with no safety net | LOSS | rare | high | P2 | open | `docs/design-windows-port.md` § Open, in order |
| R104 | Setup says the key is fine, then the run fails on it | FAKE | rare | med | P3 | open | `preflight/api_key.py:217` sends none of the pipeline's parameters |
| R105 | Runs on a local model fail far more often than on a cloud one | CRASH | rare | med | P3 | unproven | 100days § 2, about 85% against 99%; parse-failure patterns not studied |
| R106 | An unknown session length shows as "0m" in the app and the CLI, "—" in the report | FAKE | rare | low | P3 | unproven | `docs/time-defects.md` H12 |

### C15 — A run that is interrupted, degraded or retried spends or loses what it had

The pipeline's resume and stash machinery is sound on the paths it was built for
(Ctrl-C, SIGTERM and SIGKILL all leave an honest state; a failed `--clean` restores
the old report). These rows are where it is not: the moments between a run's start
and its first copied-forward record, and the judgement of what counts as success.

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R107 | Stop a re-run early and the next run re-transcribes and re-pays for every session | SPEND | some | high | P1 | open | `pipeline.py:1475` makes a fresh manifest and `:1520` writes it holding only ingest; the previous records live only in memory (probed) |
| R108 | A Re-analyse where most sessions fail (4 quotes back instead of 353) still throws away the old report and its curation | LOSS | some | high | P1 | open | `cli.py:1430` counts any quote as success; `:1448` discards the backup |
| R109 | A failed Re-analyse keeps its paid work aside, and the only retry deletes it and pays again | SPEND | some | med | P2 | open | `output_backup.py:185`; nothing reads `.bristlenose-output-failed/` back |
| R110 | A Re-analyse cleanup cut short brings the old report back over the new one on the next run | LOSS | rare | high | P2 | open | `output_backup.py:203-208` logs "discarded" whatever happened; `:316-334` restores without checking the run completed (probed) |
| R111 | A corrupt progress record (`pipeline-manifest.json`) crashes `run` and `status` with a traceback until it is deleted by hand | CRASH | rare | high | P2 | open | `manifest.py:155-160` unguarded; `write_manifest` (`:177-179`) doesn't fsync (probed) |
| R112 | A typo in `people.yaml`, or one truncated intermediate file, stops the report from opening at all | WEDGE | some | high | P1 | open | `cli.py:2115` `_auto_render` → `pipeline.py:4329-4358`, `people.py:127-130` uncaught (probed) |
| R113 | A CLI `--clean` deletes curation with no count and no question, and the CLI's own refusal points people at it | LOSS | some | med | P2 | open | `cli.py:1176,1241-1245`; the Mac app counts and asks |
| R114 | Two machines on one synced study folder each treat the other's live run as dead | LOSS | rare | high | P2 | unproven | `run_lifecycle.py:270-291,787-797` — no `O_EXCL`, no hostname in the lock |
| R115 | Using `analyze` on a `run` project drops its caches; `transcribe` re-transcribes an analysed one | SPEND | rare | med | P3 | unproven | `pipeline.py:3599,3620`; `transcribe` has no cache (`:3253+`) |

### C16 — Inputs refused, ignored or misread without a clear word

| # | What the researcher meets | Class | Meets | Cost | P | Status | Where |
|---|---|---|---|---|---|---|---|
| R116 | An empty folder, or one holding only unsupported files, ends "✓ Done" with an empty report | FAKE | some | med | P2 | open | `pipeline.py:1486-1488,3538-3540`; `cli.py:1490-1491`; `help` lists `.txt`, which ingest rejects (probed) |
| R117 | Empty or unreadable subtitle files get green ticks, and the reason given is "nothing was said" | FAKE | some | med | P2 | open | `pipeline.py:1975-1990`; the CLI summary never prints stage failures (probed) |
| R118 | Subtitles saved as Windows-1252 or UTF-16 are refused; one such `.txt` crashes `analyze` | CRASH | some | med | P2 | open | `s03_parse_subtitles.py:216,255`; `pipeline.py:4469` (probed) |
| R119 | `analyze` silently skips plain-text transcripts with no timecodes | SILENT | some | med | P2 | open | `pipeline.py:4572` (probed) |
| R120 | A Word lock file (`~$…docx`) and a loose discussion guide become sessions; the guide becomes a participant | SPEND | some | med | P2 | open | `s01_ingest.py:204,236` (probed) |
| R121 | `transcribe` and `analyze` print a 60-line traceback when they give up | CRASH | some | low | P3 | open | `cli.py:1631-1641,1752-1776` (probed) |
| R122 | Closing the terminal tab mid-run is recorded as "stopped unexpectedly", not a cancel | STALE | some | low | P3 | open | `run_lifecycle.py:99-103` — no SIGHUP (probed) |
| R123 | An accented filename splits a recording from its transcript; a symlinked folder duplicates sessions | SPEND | rare | med | P3 | open | `s01_ingest.py:433-457` no Unicode normalisation; `:228-234` (probed) |
| R124 | A malformed subtitle timestamp quietly moves one cue to 0:00 and drops the next | SILENT | rare | low | P3 | open | `s03_parse_subtitles.py:216`, pysrt's silent default (probed) |

## Also open elsewhere, indexed not copied

- **Lifecycle failure modes** — `design-lifecycle-failure-modes.md` § Open. Rows 35 and
  36 are R17 and R51 here because they are where a researcher feels them most; the
  rest (a study on a network share, two machines on one folder, races during a failed
  re-analysis) stay in that register with their proofs.
- **Security- and privacy-shaped findings** — the maintainer's private notes. A
  verified fix is summarised here when it lands.

## Keeping it true

- **A reliability defect found tomorrow gets a row before its fix lands**, with its
  frequency and cost — then `--write`. Rank is the rule's, never a hunch.
- **Closing a row is a claim with an anchor**: `fixed <sha>`, and the test that was
  red before the fix. An `unproven` row is reproduced first; if it will not reproduce,
  it is `withdrawn` with the reason, not deleted.
- **Record the burndown when a cluster closes, and at each release**:
  `scripts/check-reliability-register.py --record` appends today's totals (and
  replaces today's line if run twice).
- **Re-sweep after each release.** The register was built from six sweeps; it is a
  floor, not a census, and the next sweep will find rows this one did not.
