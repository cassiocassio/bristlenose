# Signals lens: grey until its report is ready

Status: plan, 30 Oct 2026. Not built. Owner ask, from walking the new Signals page: do not show the bare, unfilled page at all. Show the Signals lens grey and unclickable, and show progress under the project name in the sidebar, as a run does.

## 1. What the owner saw, and why

On the first open of the IKEA project the page showed cards with a chip and quotes only (no signal name, no lead, no bullets, no metrics), the sidebar showed 12 Signals, and a moment later everything filled in and the count became 11. Cause, from the code:

- A study with no stored Signals snapshot (or one older than `SIGNAL_SNAPSHOT_PAYLOAD_VERSION`) gets one built in the background when the sidecar starts (`app.py`, `_materialise_missing`, behind `app.state.initial_signal_snapshot_pending`). The build is a model call that writes the names, leads and bullets. The same build runs after a run completes (`_reapply_after_run`, source `new_interviews`) and after a codebook apply (`routes/autocode.py`).
- While no snapshot exists, `SignalsPage.tsx` (the `merged` list, `hasSentimentGroup` branch) falls back to the live sentiment cards from `/signals/sentiment`. Those are computed without commentary, so they carry no name, no lead and no `Problem:` word on the chip, and there is one card per sentiment value, which is why the count differs. When the snapshot lands the page swaps them for the real cards.
- A second open is a plain read of the stored snapshot, so it is full from the first moment (checked on Talismanic and IKEA, 30 Oct).

So the bare form is the sentiment-lens fallback shown while the first snapshot is being written. It is not a loading state anyone designed.

## 2. What already exists and should be reused

- **Progressive lenses** (`docs/design-progressive-lenses.md`). `server/lens_readiness.py` derives which lenses can be selected; `GET /projects/{id}/condition` serves it as `lenses`; the SPA posts it over the `lens-availability` bridge message (`shims/bridge.ts`); the Mac greys and gates the lens rows (`LensAvailability`, `LensRail`, the View menu). Signals is already withheld during a first run (`signals: progress.joined`). The rule from that work: dim is cheap and honest, lit then dim is a lie walked back.
- **The sidebar subtitle under a project name.** One winner from a precedence chain (`SubtitleVariant` in `ProjectSubtitle.swift`), with the running case composed by `RunProgressSubtitle` ("Analysing…" is the floor with no measured signal).
- **The reader contract.** A snapshot is stored only when every card has its name and lead (`_signal_snapshot_has_complete_narratives`), so anything read from the snapshot is complete by construction.

## 3. Proposal (revised after review, 30 Oct 2026)

A Fable review checked the first draft against the sidebar, bridge and UX code. Its corrections are folded in below; where the review changed a decision, the reason is given.

### 3.1 Server: say that the first report is being prepared

- **"Has a report" means a stored snapshot that has at least one card.** A never-analysed project already gets an empty snapshot at serve start (an empty analysis counts as complete, `signals.py` `_signal_snapshot_has_complete_narratives`), so "no snapshot row" is false straight after a first run and the lens would be lit and blank. A snapshot with no cards does not count.
- **One boolean on `app.state`, not a per-project set.** A serve holds one project folder, and the existing startup flag has this shape. Name it for what it says (signals preparing).
- **Set it where the lens would otherwise light.** The `run_completed` handler clears `progress` (`app.py` around 1363), which lights Signals at once; the snapshot build only starts after the codebook re-apply has finished, which can take minutes. So set the flag in that handler, before the task is created, and clear it in the task's `finally`. Setting it at the top of `materialise_completed_signal_snapshot` would leave a window where the lens is lit and then dim, the exact failure the progressive-lenses design forbids. The startup path keeps its existing flag, set the same way.
- **`lens_readiness` takes the new input.** It takes only `Progress` today; pass the fact in at `routes/runs.py` (the `/condition` handler) and add a case to `tests/test_lens_readiness.py`. Signals is withheld when there is no snapshot with a card AND the flag is set.
- **`/signals/snapshot`'s `pending` reads the union** of the startup flag and the new one. The page polls only while `snapshot is null and pending`, and `pending` is false once the startup task has finished, so after a run the page would stop polling and never fill in.
- **No `data_version` bump.** The first draft proposed one. `ConditionStore` already re-posts `lens-availability` whenever `lenses` changes, so the lens lights within one 3 second poll without it, and a bump would make every lens re-read and play its hand-over dim for a Signals-only event.
- A rebuild over an existing report never greys the lens (the old report keeps being served).
- No cloud model: the flag is never set on that path (`_materialise_missing` and the run path return before it), so the lens is lit.

### 3.2 SPA

- When Signals is withheld the page renders no cards, no sentiment fallback, no spinner, no sentence, and not the shipped `signals.noData` sentence either.
- The sentiment fallback goes only where there is no snapshot. Check before deleting: readers of `/signals/sentiment` are `SignalsPage.tsx` (the cards fallback and the heatmap matrices), `signalDedup.ts` (styling by column label, fallback cards only), `routes/export.py` (the embed set) and two server tests. A study whose sentiment framework is switched off would show no sentiment cards if the fallback is deleted outright, because the Sentiment group is matched by name (`_is_sentiment_group`); keep the fallback behind "a snapshot with cards exists" if that case is real.
- **The Mac redirects off a withheld lens.** `LensAvailability.redirect(from:)` runs on every `lens-availability` post and moves the reader to Sessions. So on the Mac a restored last lens or a deep link to Signals never shows the empty page; it shows Sessions with Signals dim. The empty page is reachable only in a browser, in the exported report, or in a window the redirect has not reached. The plan accepts the redirect (no departure from shipped behaviour) and the mockup says so.
- **Export.** While any lens is withheld the SPA's `isReportPartial()` is true and File, Export Report and the web Export button are refused. So Export would dim for as long as Signals prepares, right after a run, which is when a researcher exports. This is an owner call (question 2); the server's own 409 only fires during a run, so the two gates would disagree if only one is changed.

### 3.3 Mac: no new bridge message, one new subtitle variant

- **No bridge message.** `lens-availability` already carries `lenses.signals`, and `ProjectSubtitle.resolve` can read "Signals withheld while no run is in flight" from `lensReadiness` plus `pipelineState`. The one new fact lives in `/condition`. If a field is wanted anyway the conventions are: a member of the bridge message union, a case in `BridgeHandler`, reset in `reset()` and on the status-page path, an equality guard, a contract fixture asserted from pytest and vitest, and Swift and vitest tests.
- **Where it sits.** An idle-tier variant, beside `exportingReport` and `readingScreens`, not in the running tier. Its nearest sibling is a background job the researcher did not start, seconds to a minute, with no ring (a ring promises a stop that does not exist). It must rank above `readingScreens`, which can run for hours and would otherwise hide a 20 second status entirely. Kind is `MessageKind.info`: no glyph, no hint.
- **What must change in code.** The new case enters every exhaustive switch: `glyphAction` and `glyphKind` in `ProjectSubtitle.swift`, `SidebarSubtitleText.text`, `activityText` and `tooltip(for:)`, and `shimmerSubtitle` in `ProjectSidebarOutline.swift`.
- **Shimmer.** The shipped gate is `.running` only, behind "Show animation while analysing" and Reduce Motion. Extending it to this variant is one line but a departure; question 5.
- **The hand-over from a run.** A run's subtitle ends when the process exits, but the preparing fact arrives from a 3 second poll of a webview that is itself reloading, so the row would collapse to one line and grow again. The house shape is a native prior held until the bridge confirms (`ArtifactPrior`, and the 2 second floor on `.addingInterviews`): hold "a first analysis of this study just completed and this window has not yet heard `signals: true`". The same floor stops the status flashing for under a second when a small study builds quickly.
- **Window scope.** The status comes from the window's own bridge state, as the crash overlay does, so it shows only in the window where this study is selected. A second window that lists the study without selecting it shows nothing. The honest app-wide source is the serve fleet's per-serve health poll, which is a bigger change (question 1).
- **Wording and length.** The draft "Picking up Signals…" is 19 characters; the row budget is about 22 at the 240 pt sidebar. German ("Signale werden vorbereitet…", 27) and Finnish (25) would truncate, and the new variant has no tooltip for the full form unless one is added. Precedent: the German report-error headline was shortened to fit. Stage verbs name the work ("Finding quotes", "Grouping themes", "Building report"), so "Writing Signals…" or "Building Signals…" is more in family than "Preparing". Every locale reuses that locale's own word for the lens (`common.nav.signals`), one new key in 21 full locales (zh-Hant-HK only if it differs), `check-locales.py --strict`.
- **Estimates.** Indeterminate is correct by the ladder's own rule (no measured signal returns the floor). There is no estimator for this phase (it runs in the serve, emits no run progress, and a fake stage id would fail `test_swift_python_contract.py`), and the only measurement is the nearby note of a median of 25.8 s and a maximum of 54.3 s for the same elaboration calls. An n of m is possible later because chunks are yielded one at a time, and at about 30 seconds it is not worth the ring it would imply.

## 4. Edge cases

1. **No cloud model.** Lit, flag never set (3.1).
2. **Build fails or is skipped.** The flag clears in the `finally`; the lens lights and shows its empty state; the next open retries. No retry control.
3. **Slow build.** Indeterminate (3.3). Chunks of 6 (`ELABORATION_CHUNK`, marked a guess in the code).
4. **A run in flight.** The run subtitle wins; Signals is already withheld until the join barrier. Hand-over: 3.3.
5. **Second window.** Each window shows the status only if the study is selected there (3.3).
6. **Export HTML.** Reads the snapshot; with none, Signals is absent from the export. The Export button dimming is 3.2.
7. **MCP.** Leave alone. `get_signals` computes live and never calls a model; making it say "not ready" would couple a read-only tool to the serve's build state and diverge it from the chat lens.
8. **Startup before the sidecar serves.** Nothing shows until the SPA's first poll; the boot pane covers it.

## 5. Not doing

- No progress bar, percentage, retry button or explanatory sentence in the empty page.
- No second flag or setting, no change to when a snapshot is built, no change to the reader contract, the quote reference shape or the hide filter.
- No MCP change.

## 6. Slices

1. Server: the boolean, set in the `run_completed` handler, cleared in `finally`; "has a report" means a snapshot with a card; `lens_readiness` input at `runs.py`; `pending` reads the union. Tests: grey with no snapshot and the flag, lit with an older snapshot, lit with an empty snapshot and no flag, lit with a local provider, cleared on failure and skip, grey with an empty snapshot while the flag is set.
2. SPA: no bare page while withheld; the fallback decision from 3.2; poll keyed on the union; vitest.
3. Swift: the subtitle variant in the idle tier with all the exhaustive switches, the native prior and 2 second floor, the locale key in 21 files with pins, Swift tests for precedence and hand-over.
4. Real check in the Mac app from the main checkout: no snapshot, empty snapshot, old snapshot, local provider, a second window.

## 7. Gate

New user-visible string and a removed page state, so a UX change: this plan, the mockup `docs/mockups/signals-lens-readiness.html`, and the owner's go before any code.

## 8. Owner decisions (30 Oct 2026)

Decided:
1. **A window-scoped status is acceptable.** It shows only in the window where the study is selected.
2. **Export dims while Signals prepares.** The report counts as partial for that time.
4. **Wording: "Picking up Signals…"** (owner's draft; a small, deliberate whimsy that fits the signal metaphor). It names the lens rather than the work, a small departure from the stage-verb register ("Finding quotes", "Grouping themes"). The idiom does not travel, so each of the 21 locales gets a plain phrase meaning gathering or finding Signals, written with that locale's own word for the lens (`common.nav.signals`), not a literal rendering. Length: 19 characters in English, as before; German and Finnish still need a shorter phrase or a tooltip.
5. **Shimmer on this line.** The owner's reasoning: shimmer on small status text means "the AI is thinking", and that is true here (the build is model calls). This extends the shipped running-only gate, so it stays behind the same "Show animation while analysing" preference and Reduce Motion; check that the preference's label still describes it.

Also decided:
6. **The Mac's redirect off a withheld lens to Sessions is accepted** (shipped behaviour, no departure). A restored or deep-linked Signals lens lands on Sessions with Signals dim.

3. **"Picking up Signals…" ranks above the Screens status** in the idle tier. The owner's reasoning: show Signals because it will not be around for long, and Screens will be. The Screens count returns when the build ends.

Nothing open. Next: the owner's go to build, after the sidebar mockup is approved.
