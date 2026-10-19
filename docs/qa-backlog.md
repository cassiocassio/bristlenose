# QA Backlog

Manual QA steps waiting to be confirmed. Per-item — say "QA done for X" to check off.

---

## Discussion lens — quotes are the report's own cards; empty questions are quiet

**Date:** 19 Oct 2026
**Branch:** main (`7940adc7`; the tab-bar fix `4a156328`)
**Context:** the lens draws the Quotes lens's card through the shared store; hidden quotes leave the counts and are counted beside their question; a question with nothing to show is a grey row and heading (`docs/design-discussion-lens-plan.md` §3). `serve --dev trial-runs/project-ikea`, then `/report/discussion/`.

- [ ] **A card works as on Quotes.** Hover a card: star and hide appear; star it, tag it with + (suggestions, grey completion, Enter), click the words to edit, remove the sentiment and restore it, accept and deny a dashed proposal.
- [ ] **Links.** A card's timecode opens the player at that moment; its speaker badge opens the transcript there. A question row's timecode plays its session; its `m1` badge opens the transcript at that turn; no star, hide or + on a question row.
- [ ] **Hiding.** Hide a card: it collapses, the question in All gains a blue "1 hidden quote" on the right, the guide's count drops by one; unhide from that list and it returns. In a session view the counter ends the question's block.
- [ ] **Quiet empty question.** Hide every answer to one question: its guide row goes grey and in All only its grey heading (with the counter) remains; no "No quotes from this question" anywhere; no "Grey: …" line in the key.
- [ ] **Keys.** Focus a question in the guide, click a card, press j/k (the cursor moves, the question stays lit), s, h, t; Esc once clears the card, again clears the question. Tab to a guide row with a card focused and press Enter: the row is pressed, nothing plays.
- [ ] **Loading.** Reload on the Discussion lens: a "Loading" line, never a lens of grey unanswered questions, before the cards arrive.
- [ ] **Mac app** (after `desktop/scripts/build-sidecar.sh` or a Cmd+R): ⌘A selects the lens's cards; the Quotes menu's Star/Hide/Tag act on a focused Discussion card.
- [ ] **Tab bar.** In a browser, drag the window slowly across ~1000–1200px on the Project page: the bar changes spacing once at a threshold and holds (owner confirmed in Safari, 19 Oct).

---

## Discussion lens — All sessions and the navigator measure

**Date:** 18 Oct 2026
**Branch:** main (`538a2869`…`083a4874`)
**Context:** All is the first and default session choice from two sessions; the rows' session chips became a measure (bar + count → strip → grid) chosen by the guide's width. Built overnight; reviewed by /usual-suspects (Findings 45–69, `docs/private/reviews/discussion-lens.md`). Checked headless in Chromium and WebKit, never in the app's window. Needs a ⌘R first (the bundled report rebuilds). Try `trial-runs/rockclimbing-fresh` (8 sessions).

- [ ] **Opens on All.** The Discussion lens opens on All with "All" lit in the session bar; each question once, a block per session led by its badge. (Since 19 Oct: only sessions with a quote to show get a block, and there is no "Not asked in" line — see the block below.)
- [ ] **The measure grows with the guide.** Drag the guide's edge: bar + count → a strip of cells → a grid under one-digit session numbers (10–12 squeezed into the same width). Dragging feels smooth in All (measured 33 ms a step on 1,800 quotes in WebKit).
- [ ] **Shading reads.** Empty slots are visible on the guide's tint; filled cells are clearly darker; the richest cells darkest. In light and dark. (The ramp changed to muted → ink for contrast — see the owner decisions in TODO.md.)
- [ ] **Cells and lead-ins open a session at the question.** Click a cell, or a session's badge in All: that session opens with the question lit; a not-asked cell does nothing. After clicking a lead-in with the keyboard, focus is on the question, not the top of the page (VoiceOver too).
- [ ] **The selected column reads lightly.** Pick a session in the Mac app: its column is a pale blue band behind the cells (one band per section, no gaps between rows) with the cells tinted blue-grey, no ring. Check strip and grid, light and dark, and with the window in the background (band and tint go grey). Then pick another session: the band should slide over quickly with a slight overshoot, and from All it should simply appear.
- [ ] **Leaving All lands at the top**, not part-way down the shorter session column; clicking a question whose heading is already in view does not jump.
- [ ] **A guide project** (Your guide tab): All shows the same questions on either tab, including those asked off the guide.


**Date:** 18 Oct 2026
**Branch:** main (`bd3698ea`, `7435256f`, `fad24516`)
**Context:** The transcript split control's caret pops a native NSMenu in the Mac app. Placement and VoiceOver are things no test reaches. Review: `docs/private/reviews/transcript-timeline-native-menu.md` Findings 11–13, 16, 18. Needs a ⌘R first (the bundled report rebuilds with the new web code).

- [ ] **Right edges line up.** Open a transcript with a timeline, click the caret: the menu opens just below the control with its right edge on the control's right edge. Take a 2× screenshot in light and dark; if off by a constant, fold a measured offset into `TimelineMenuEntry.origin`. Check on macOS 15 too if a machine is at hand (it draws tighter rows).
- [ ] **Sidebar open.** Same check with the projects column and the tag sidebar open: is the menu shifted sideways? (`viewRect` ignores a left safe-area inset; shared with the person picker.)
- [ ] **No double gap.** The separator above the "Timeline detail" header shouldn't read as a doubled space; if it does, drop the separator.
- [ ] **Picks work.** Each row changes the slot and the tick follows; choosing the ticked row does nothing; a double-click on the caret opens one menu, not two.
- [ ] **Keyboard and focus.** Tab to the caret, Space opens the menu, ↓ highlights the first row, Escape closes and the caret keeps focus with no stuck pressed shading. Hold Return on the caret once: it must not pick a row by itself. After a mouse pick, no focus ring should appear on the caret.
- [ ] **VoiceOver.** The subtitles ("Sections · Moderator · Participant", "+ Sentiment") are read after each title, and the menu opening is announced.

---

## macOS localisation — menu bar, Settings, and the failure surfaces

**Date:** 21 Sep 2026
**Branch:** main (`9c200e6b`..`cc4a4573`, 17 commits)
**Context:** 567 translated values across 21 locales, plus 525 more from the run-failure work on 21 Sep, plus two mechanisms
that only take effect at launch. Every item below is something **no test can
see** — the `.lproj` work is a bundle property, the menu bar is built once per
process, and the chip grid is a measured layout.

**Do items 1–3 after a RELAUNCH** (⇧⌘K then ⌘R if the build looks stale).

- [ ] **Apple's own menus are localised.** Set Settings ▸ Appearance ▸ Language to Türkçe, relaunch, and check `File / Edit / View / Window / Help` read `Dosya / Düzen / Görünüm / Pencere / Yardım` — and the items inside them (Minimize, Zoom, Bring All to Front, Cut/Copy/Paste, Enter Full Screen). These come from AppKit now that the app declares 22 `.lproj`; we translated none of them.
- [ ] **Our four menus follow too** — `Proje / Kodlar / Alıntılar / Video`. `Diagnostics` stays English by decision.
- [ ] **Nothing regressed for an existing install.** A profile that already had a language set should come up in it, not in English: the private `language` key still wins over the new `Bundle.preferredLocalizations` fallback.
- [ ] **Sentiment chips at 14".** Welcome ▸ the "Seven sentiments" card in **tr** — `Kafa karışıklığı` is +24% on the widest row, past the screen's documented +20% budget. The grid scales to fit; check it shrinks rather than clipping or colliding with the text beside it. Then check **ja/zh-Hant**, which are 35–49% *narrower*, do not look lost.
- [ ] **Settings language switch stays put.** Change language with Settings open: the six tabs flip AND the window stays on Appearance (it used to snap to General).
- [ ] **A failed cloud-import row speaks the language.** Easiest via Diagnostics ▸ Cloud Import ▸ a partial-failure fixture: the red rows should read e.g. `Dosyanın yalnızca bir kısmı ulaştı.`, not `Only part of the file arrived`.
- [ ] **A sign-in failure speaks the language.** Start a cloud sign-in and cancel it — expect the translated sentence. Microsoft/Zoom refusals that carry the provider's *own* reason are supposed to stay in the provider's words; that is not a bug.
- [ ] **A drag-and-drop refusal speaks the language.** Drop a folder containing nothing importable → translated toast.
- [ ] **A run-failure popover speaks the language** (added 21 Sep 2026). Diagnostics ▸ fixtures ▸ `failed_no_summary` puts a project into `.failed` with a category; click the row's error glyph. The body should be the translated sentence, and **switching language with the popover's project still selected should re-render it** — that is the whole point of deferring the resolve, and it is the half a test cannot reach. The `Category:` line below it is still English (register row 6, next commit).
- [ ] **The boot screen's failure line is in the right language** (added 21 Sep 2026). The hard one to stage: rename or move `Bristlenose.app/Contents/Resources/bristlenose-sidecar/` aside and launch — expect a localised sentence naming the path, under the already-localised "Couldn't start Bristlenose". Put it back afterwards.
- [ ] **The exit-code failure line still reads.** `desktop.boot.failure.exitedWithCode` appends a 5-line stderr tail below the sentence, and `BootView` sets `.lineLimit(3)` — so the tail was already being clipped before this change and still is. Look at whether the *sentence* survives the clip in a long locale (de, fi), since it is the part that carries meaning. Not a regression; a pre-existing shape worth a decision.
- [ ] **The named and generic sentences both read right.** With a provider configured, an LLM-category failure should name it (`Claude rejected the request.` → tr `Claude isteği reddetti.`); with none configured it should fall back to the `…Generic` sibling, which says "the AI provider" in the locale's own words rather than leaving `{{provider}}` on screen.
- [ ] **VoiceOver and the sighted row disagree on a failed project, and did before this change.** The row shows the short "Run failed" header; VO speaks the full summary. `ProjectRow.pipelineStateAccessibilityPhrase`'s own docstring says they must not drift. Decide which one is right — left alone rather than settled in passing.

---

## Keychain Security.framework migration

**Date:** 24 Mar 2026
**Branch:** main
**Context:** Rewrote `KeychainHelper.swift` from `/usr/bin/security` CLI to native `SecItemAdd`/`SecItemCopyMatching`/`SecItemDelete`. Same public API, backward-compatible with existing Keychain entries.
**Full QA script:** `docs/qa/keychain-security-framework.md`

- [ ] Key persistence round-trip: enter key in Settings → LLM, quit, relaunch, verify it's still there
- [ ] No subprocess: `ps aux | grep security` during key save — no `/usr/bin/security` process
- [ ] CLI interop: `security find-generic-password -a bristlenose -s "Bristlenose Anthropic API Key" -w` returns the key saved from the app
- [ ] Xcode console: no `[KeychainHelper]` error lines during normal key operations

---

## Sidebar 'analysing…' lie on re-open (drag-drop ingest)

**Date:** 16 May 2026
**Branch:** main (merge `bbc899b`)
**Context:** `ContentView.createProjectFromURLs` now branches on `LocateFlow.folderLooksAnalysed` — analysed-folder drops route to `pipelineRunner.scan` (manifest-derived state) instead of `.start` (auto-run). `PipelineRunner.scan` pre-sets `.scanning` to close the nil-state window. Rename-mode scoped to fresh-project drops only. Stricter than the original brief: marker present = no auto-run even for partial runs; existing Resume / Continue / Retry affordance is the entry point.

- [ ] Drop folder with complete `bristlenose-output/`: row shows no "Analysing…" subtitle; goes straight to ready state; **switching to another project does NOT trigger the cancel-confirmation modal**
- [ ] Drop folder with raw media, no `bristlenose-output/`: row shows "Analysing…" + auto-runs the pipeline; rename-mode TextField focuses (the auto-run path is unregressed)
- [ ] Drop folder with partial output (interrupted run — synthesise by Stop-ing a fresh run mid-flight, then Remove + re-drop): row resolves to `.partial` / `.stopped` / `.failed`; existing Resume / Continue / Retry affordance is the entry point; **no silent auto-run**
- [ ] Brief subtitle during scan reads localised `.scanning` text (a few frames on local SSD, longer on network mount). NOT "Analysing…" — if you see "Analysing…" briefly on the analysed-folder drop, the scan pre-set didn't take

---

## Warm-sidecar pool — project-switch edges (Phase A2)

**Date:** 21 Jun 2026
**Branch:** `warm-sidecar-pool` (commit `beaac38`)
**Context:** `switchProject` parks the outgoing serve sidecar and re-points to a warm one instead of teardown+restart. Single parked slot (Option B). Core path GUI-confirmed (rapid A↔B switch-back is fast and the report renders). These are the **unverified edges** — especially the silent-401 class the `.id`+port fix guards. Mechanism: `ServeManager.swift` (`switchProject`/`drainParked`/`dropParked`/`probeHealth`), `ParkedSidecar.swift`. Tiers + rationale: `docs/design-desktop-switch-performance.md`.

- [ ] **Warm switch-back renders DATA, not a blank/empty report** (the F1 silent-401 check): A→B→A, confirm A's quotes/sessions actually show — an *empty* report that loads fast is the failure, not just a spinner
- [ ] **≥3-project rapid switching** (A→B→C→A→B fast): no crash; the 3rd-project / evicted cases cold-start cleanly (they retain the pre-existing boot race by design — F13)
- [ ] **Prefs/provider change drains the pool** (F6): switch to A, switch to B, change provider/model in Settings, switch back to A → A **cold-starts fresh** (serves with the new config), does not re-point to a stale-env warm sidecar
- [ ] **Consent change drains the pool** (F7): with a warm slot, trigger a consent re-acknowledge → parked sidecar is torn down (no parked process serving under old consent)
- [ ] **Project removal drops its warm slot** (F16): switch to A then B (A parked), remove A from sidebar → A's sidecar is torn down, not left serving a removed project
- [ ] **Dead/wedged parked sidecar falls back to cold start, never blank** (F1/F3): if a parked sidecar dies while parked, switching back shows a real boot (`.starting`→`.running`) or failure, never a silent blank pane
- [ ] **Lifecycle log lines present**: `log stream --predicate 'subsystem == "app.bristlenose"'` shows `sidecar_parked` / `sidecar_repointed` / `sidecar_evicted` (+ `sidecar_parked_died` if one dies parked) at the matching moments

---

## Dev Run Inspector — visual render (run / llm / timing)

**Date:** 28 Jun 2026
**Branch:** `claude/debug-menu-instrumentation-4r9npy` (merge `252c1ce3`)
**Context:** Dev-only Run Inspector (`/api/dev/run`) is client-rendered (JS `JSON.parse` + DOM build), so the pytest/curl coverage only proves data + template are sound — the rendered surfaces need a real browser. Data + escaping + endpoint gating already verified against a real analysed project (≈18 captured LLM calls, OpenAI/gpt-4o). Native entry: **Debug ▸ Run Inspector** (⌃⌘R) in the DEBUG desktop build. Browser path: load `http://localhost:8150/report/` FIRST (sets the `bristlenose_auth` cookie), then `http://localhost:8150/api/dev/run`.

- [ ] **Run tab** renders the provenance header with real values (run_id ULID, status=completed, true wall-clock duration — NOT the stage-sum fallback) and the cost donut shows `—` for a null-cost run (an OpenAI run captures no cost), not a misleading `$0.00`
- [ ] **LLM tab** lists the per-call rows (provider/model/elapsed) for a run with a real `llm-calls.jsonl` (≈18 calls)
- [ ] **Timing tab** chart renders (calibration curve empty on real data today is expected — no timing-history store yet)
- [ ] **Native window** (Debug ▸ Run Inspector, ⌃⌘R) loads the same page authenticated via cookie — no 401, no blank pane
- [ ] **Live Diagnostic-fixtures submenu** applies a scenario to the selected project without relaunch
