# Guest walk — coverage, now and the whole of it

What the walk captures today, against every screen state the code has (an
inventory taken 20 Oct 2026 of `desktop/Bristlenose/Bristlenose/`,
`frontend/src/` and `bristlenose/server/`; about 180 states). The long-term goal
is a capture of every dialog, screen and component in every state, added a
stage at a time. **Integrations that need a sign-in are out of v1** and listed
at the end.

Each stage says what it needs. "Frozen project" means an analysed project made
once on the host, so the lens content is the same every night. The model's output
differs night to night, which a fresh run's lens screens showed on 20 Oct (4 of 26
screens pink, all of them model text).

## Now: 22 steps, 26 captures, about 4 min a night (macOS 27 vanilla)

- First launch: Welcome window (animated cards masked), AI consent sheet
- Empty main window ("Drop a folder")
- Settings: all six tabs at their defaults, plus LLM Provider ▸ Ollama selected and online
- About window
- New Project: inline rename, Add Files Open panel, file selected, Create Project Folder sheet
- A real run on the host's Ollama through the tunnel, waited on by its terminus event
- Lenses after the run: Project, Sessions, Quotes, Codebooks, Signals, Discussion
- The whole menu tree, enabled state and shortcut, at every step

## Stage 2: no new fixture, only more steps (about 30 captures)

- Bristlenose ▸ AI & Privacy… (the consent sheet in review mode); Help ▸ Welcome to Bristlenose
- Help ▸ Send Feedback: the sheet in each state (open it, never send)
- Settings sub-states: General ▸ Choose other… (Open panel, cancel); Appearance ▸ Language
  change → relaunch alert (cancel); Transcription toggles; Ollama row with the tunnel down
  ("unavailable")
- Sidebar: context menu, Rename, Choose Icon… popover, Move To ▸, New Folder, multi-select
  pane, Remove from Sidebar → undo toast → Edit ▸ Undo
- File ▸ New Window ⌥⌘N
- Run lifecycle: Stop Analysis mid-run (stopping → stopped); a run with no provider
  (failed row, serve status page, row diagnostics popover); two runs queued
- After the run: Sessions switcher popover, a transcript page, the toolbar Export popover
  on each lens, File ▸ Export Report… save panel with the Anonymise accessory (cancel),
  Save Spreadsheet CSV / XLSX panels (cancel), Page Setup / Print panels (cancel)
- Re-analyse… confirm sheet (star a quote first, so there is something to lose)
- New-files sheet: drop a second file on the analysed project

## Stage 3: the frozen project (deterministic lenses)

- Every lens with real content and the same content each night, so pink means the UI changed
- Quotes: search, All / Starred, focus mode, grouping toggle, tag autocomplete, bulk actions
- Codebooks: browse library, a codebook page, create / rename / merge / delete dialogs,
  uninstall sheet
- Signals: heatmap inspector, sidebar; Discussion: not-run, add your guide (Open panel),
  full view
- Person picker popover, transcript timeline menu, Contents / Tags / minimap panels

## Stage 4: video (the screens fixture: `fixture/make.sh`, 75 KB, 36 s, three pages)

- Screens lens: reading progress, board, a screen page with its screenshot and linked quote,
  context menu (Tidy, Return to automatic), View ▸ next / previous screenshot
- Video pop-out player; Quotes ▸ Extract Clips and Burn Subtitles (activity chip, Reveal)
- File ▸ Export Screens… / Copy Screens
- **Constraint found 20 Oct:** Vision OCR fails inside a macOS 27 guest (an unsandboxed
  control program fails too: `e5rt_e5_compiler_compile` code 11) and works in the 26.6
  guest and on the host. So until 27 guests can run Vision, the Screens part runs on a
  Tahoe vanilla base, or on a frozen project whose screen text was read on the host.

## Stage 5: Diagnostics fixtures (in the Developer-ID build, no sign-in)

- Diagnostics ▸ selected-project fixtures: run_completed_partial, run_failed_abandoned,
  running, queued, stopped, failed_no_summary, showcase states → every sidebar row and
  detail-pane state without engineering each one
- Diagnostics ▸ Cloud Import ▸ <platform> ▸ every scenario (signed out, loading, populated,
  empty, scope declined, partial failure, …): the import window's states with no account
- Diagnostics ▸ Check Health window (loading / loaded / unavailable); Shoal screensaver (masked)

## Stage 6: lifecycle edges

- Project unavailable: folder moved (Locate… panel, Spotlight "is this the folder?" sheet,
  wrong-folder alert), volume gone (the unsupported-loose-files pane was retired 22 Oct 2026)
- Ollama setup pill and popover phases (no daemon, choosing a model); Whisper download
  pill (needs about 1.6 GB of network, so once a week, not nightly)
- AutoCode on a codebook (runs on Ollama, so no sign-in): job chip, threshold review modal

## Later: the trivial call per provider

A £0.05 call to each of Claude, ChatGPT, Gemini and Azure, on capped keys, to prove
each provider's path still works end to end. `scripts/check-providers-live.py` already
makes one real call per offered model at release time and is the thing to extend.

## Out of v1: needs a sign-in

- File ▸ Import ▸ Google Meet / Teams / Zoom, live (OAuth); importing-batch row states
- Miro sheet; Settings ▸ Accounts connected / attention / disconnect states
- LLM Provider cloud states (online / invalid / out of credit) and the out-of-credit pill
- MCP Agents: Claude extension install / update states, ChatGPT plugin row
- FigJam needs no sign-in on the Mac side, so it can move up to v1 with its flag on
