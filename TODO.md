# Bristlenose — Where I Left Off

**Cross-session pickup map:** `docs/session-consolidation-2026-10-30.md` records
every known Claude/Codex session, merge result, parked item, stash, preservation
copy and remaining worktree after the 30 October consolidation.

**How this file works.** It holds the last week's entries (30 Oct onward), newest context first where it matters, and nothing older. Everything before 30 Oct is in [`docs/todo-archive.md`](docs/todo-archive.md), moved verbatim on 6 Nov 2026 (126 entries; nothing was edited or dropped). The standing sections at the bottom (task tracking, dependency maintenance, risk register, key files, URLs, design docs) stay here. Backlog lives in `docs/private/100days.md`; add a new entry at the top and move it to the archive when it is a week old and closed.

**Pushed state, checked 6 Nov 2026 against `origin/main`.** On `origin/main`: `cfe9697c3`, `62f8cc65f`, `4dda06ea6`, `28ef8783b`. Not found in the GitHub clone, so possibly local-only on the maintainer's Mac or rewritten since: `c344fdcd3`, `a672d2715`, `4ba513387`, `56b46608a`, `5a7830935`, `2bc0c5196`. An entry below that says "not pushed" for one of the second group may still be true; check the working checkout before assuming it landed. The `v0.44.0` tag is on `2a9e0769d` (released 2 Nov); the entry that said 0.44.0 was staged and unreleased is in the archive.

**Older entries that read as open, parked or owed** (headings only, from the archive, not re-verified; search the archive for the words):

- 16 Oct 2026 — open: on Windows, a stopped in-process report server still holds `bristlenose.db`.
- 6 Oct 2026 — the CLI welcome docs page is PARKED by the owner ("not now"); the reuse analysis is saved.
- 1 Oct 2026 — moderator identity: route C decided, the plan written, the pixels drawn; nothing built.
- 29 Sep 2026 — agents see a different project name from the researcher's, and a Code session's agent calls leave no trace in Claude's logs.
- 16 Aug 2026 — vendor branding for `File ▸ Import` designed, nothing built (`860aa0b2`, `docs/design-cloud-import.md` §9a).
- 6 Aug 2026 — Sessions lens is a responsive CSS grid; one i18n follow-up owed.
- 31 Jul 2026 — two i18n gaps seeded across 19 locales; three pre-existing defects and one terminology split left open.
- 20 Aug 2026 — the day has no session entry; these are its owed items, transcribed from the commit bodies so they are not only there.

**7 Nov 2026 — Minimap "you are here" rect, Mac app only (Claude Sonnet 5.5; committed on `main`, not pushed).** With the tag sidebar closed in the Mac app the blue rect was off-centre on the ticks and its right edge ran under the scrollbar: `.layout.embedded:not(.tags-open) > .minimap-slot` added `padding-right` (moves the ticks), the viewport is `position: absolute; right: 0` (ignores it). Fix: the slot's extra right padding is now `--bn-minimap-extra-pad-r`, which the viewport reads for its `right` (`sidebar.css`, `minimap.css`; tags-open unchanged). Verified in a real `serve --dev` browser SPA at 1280px (12px / 12px with tags open; 12px / 12px with the `embedded` class forced on, rect 24px inside the slot edge); targeted tests and whole-repo Ruff green. **Owed: the real Mac app was not checked** (computer-use access was denied): run the `Bristlenose (External Server)` scheme against `.venv/bin/bristlenose serve --dev trial-runs/project-ikea`, open Quotes, look with the tag sidebar closed and open; if wrong, `git revert` the commit. A reminder fires 10 Nov 2026 (`minimap-rect-mac-check`). Design record: `docs/mockups/minimap-viewport-rect-inset.html`. Release-note candidate: **The minimap's "you are here" box sat off-centre and under the scrollbar with the tag sidebar closed in the Mac app.**

**6 Nov 2026 — any-llm on the Snap and Fedora packages (pin 1.44.0), the README and doc truing, cross-harness docs (Claude Sonnet 5.5; all pushed to `origin/main`).**
Commits, oldest first: `44c0e87`/`4ebe6f6` README truing and link row; `df39cdf` any-llm on the Snap and RPM, pin 1.27.0 → 1.44.0 (1.44.0 is the first release since 1.27.0 that allows `anthropic>=1.0`); `f89db90`/`b461f26` AGENTS.md, CLAUDE.md, CODEX.md wired together plus `tests/test_agent_entry_docs.py`; `a7ab1a2` TODO.md trimmed (older entries verbatim in `docs/todo-archive.md`), DEVELOPMENT.md and CONTRIBUTING.md trued; then the review fixes `4ed2d61`, `15bf34a`, `49c9421`, `0320513` and the docs commit after them.
Verified: full pytest 9,731 passed, 1 failed (`test_a_locked_readme_never_fails_the_run`, fails on a clean tree too: the sandbox runs as root); ruff clean; real any-llm 1.44.0 probed offline against a stub server; CI job `any-llm-library` green on 1.44.0 (run 42308386742); a local `pip-audit` over `.[dev,serve,voice,any-llm]` finds nothing. Reviewed by `/usual-suspects` (code-review, silent-failure-hunter, security-review, Bach, a context-free reviewer, a compose-check and William): 11 findings resolved, 3 parked. The local log is `docs/private/reviews/any-llm.md`.
**Owed / open:** (1) **main's CI is red, none of it from this work**: `tests/test_gemini.py::TestGeminiCallEnds` (2 tests, every cell; `google-genai` 3.0.0 came out today, the sandbox has 2.34 — cause not confirmed), `tests/test_standby.py` on Windows (`preexec_fn`), Vitest load timeouts. (2) The `pip-audit` step's soft-gate disposition **expires 2026-11-30** (`docs/testing/soft-gates.json`): decide then whether it hardens. (3) The Fedora package picks up 1.44.0 only from the next release, because PyPI's 0.44.0 still pins 1.27.0. (4) Parked, owner's call: on the RPM the sdk-missing advice says "pipx, uv or pip" and the `pip` route installs a shadowing second copy, and keys stay behind when moving off a package; whether to adopt dependencies the day they ship, with no hashes or constraints file for the snap and the SRPM wheelhouse (true of all ~110 dependencies). (5) Not run here: `snapcraft` build, `mock` SRPM build (`BN_LOCAL_DIST`), the live-provider walk (`scripts/check-providers-live.py`), `mandoc -Tlint` on the man page. (6) `CONTRIBUTING.md` "Don't merge red CI" describes a branch-protection rule on `main` that the trunk workflow contradicts; GitHub settings could not be read from here. (7) The 30 Oct "no push is authorised" standing line in `CLAUDE.md` was left for the owner.
**Release-note candidate (a minor bump):** "The Snap and Fedora packages now include any-llm (Mistral, plus providers that need no add-on); the Fedora package gets it from the next release."

**6 Nov 2026 — The workbench index (Claude Sonnet 5.5; gitignored, nothing in the public tree).** `docs/private/directory/index.html` is a self-contained directory of the year's instruments: 312 pages (mockups, labs, design system, charts) with thumbnails, and 138 tools and docs, 49 of the docs with their key table or diagram as the thumbnail. A year-by-month strip filters everything by the month a thing was first committed; search and the mockup-lifecycle chips filter too. Regenerate: `scan.py`, `scan_tools.py`, `thumbs.mjs` (from `e2e/`), `doc_graphics.py`, `docshots.mjs`, `build.py`. Checked in Chromium: 446 links and 312 thumbnails resolve, no console errors, no phone overflow. Open: the value-versus-effort scatter the owner was adding to the trust map is not on this page or in `regen.py`; the key-graphic pick for a doc is a heuristic (most numbers), with no hand override list yet.

**3 to 6 Nov 2026 — any-llm cleanup, the salvage rulings, the Mac left-out display, and the upstream anthropic 1.x merge (Claude Sonnet 5.5; all committed on `main`, `35642a1bb` to `2305643f2`, nothing pushed by this session).**
Rulings: 62 keep, 48 persist drops, 56 Ollama salvages, 50 leave. Built: refused calls recorded `error` on Claude, ChatGPT, Azure, Gemini (`35642a1bb`); "unusable quote" wording; CI job `any-llm-library`; the left-out count kept on the stage-9 session record so a resume prints it (`87f549de9`); Ollama last-attempt salvage (`099891960`); doctor warns when a shared environment moved any-llm or anthropic (`bfb144aa3`); **the Mac says when a run left quotes out** (`10521b7f1`, `0d44004b0`, `c83a4a2fe`, `2305643f2`): `quotes_left_out` on the run summary (contract v9), the run reads as `completedPartial` ("3 of 3 sessions analysed" beside the warning glyph), the popover lists each session ("N quotes left out", key `desktop.pipeline.diagnostic.quotesLeftOut`, **21 locales drafted by Claude, native review owed**). Debug scenario `run_completed_quotes_left_out` forces it from Diagnostics ▸ Diagnostic fixtures. Mockup `docs/mockups/quotes-left-out-mac.html` (option C, owner chose "count it as Done with warnings"). Independent code-review agents covered every commit; fixes in the same series.
Verified: full Python at committed HEAD 9431 passed in a clean worktree; Swift 2971 passed in an isolated worktree, plus `PoolStarvationTimeoutTests` alone; the built-in Claude path live (`check-providers-live.py --provider anthropic` 3/3, and a real `run --llm claude` for $0.06). **Not seen:** the popover in the running app (rows and the whole popover were rendered in a test, `LeftOutRowsRenderTests`); a real malformed reply reaching `salvage_items` (three local runs, including a forced `json_object` fallback through a proxy, never produced one; `bristlenose/llm/gotchas.md`).
**Upstream:** the owner commented on mozilla-ai/any-llm#1370 on 3 Nov; tbille merged liukidar's #1593 and released any-llm 1.44.0 on 4 Nov, lifting the `anthropic<1` cap; Bristlenose is pinned to 1.44.0. The fork plan was never needed. **Open:** the openai 2.18 floor edge case for DeepseekProvider/MetaProvider (owner offered a patch); the Mac warning state hides "+N unanalysed" until the next run (owner chose to keep it).
Release-note candidates: **A resumed analysis still says how many quotes were left out of a session**; **A local model that breaks one quote no longer loses the whole session**; **The Mac app says when a run left quotes out** (done with warnings, with the session named in the popover); **A call the provider declined is no longer counted as a normal one in cost estimates**.

**6 Nov 2026 — Stray files left alone, `.docx` with no transcript refused, popover footer (Claude Sonnet 5.5, built, Fable-reviewed; UNCOMMITTED on local `main`, not pushed).**
Owner rulings (6 Nov): a format we never offered (`.py`, `.txt`, `.md`, `.pdf`, `.xlsx`, an unlisted media extension like `.opus`) is **left alone**, never a refusal; only offered formats can fail, with a reason. An unlisted recording is ignored in silence (option A). An untimed `.docx` with no speaker turns is refused as new reason `no_transcript`. "Supported formats" link only inside an already-open popover. Triggered by Talismanic reading "Partial completion" for ~30 stray files.
Changed: `events.py` (`NO_TRANSCRIPT`, `StageOutcome.left_alone`), `s01_ingest.py` (`split_left_alone`, quieter scan log), `pipeline.py` (both ingest sites, `_record_ingest_outcome(left_alone=)`, generalised docx branch), `s04_parse_docx.py` (`_has_speaker_turns`), `refusals.py`, `PipelineSummary.swift`, `ProjectDiagnosticPopover.swift` (footer, plaintext line), 21 locale files (3 keys), tests (`test_left_alone_files.py` new; `test_parse_docx`, `test_run_no_supported_files`, `IngestOutcomeTests` updated), docs (lifecycle, popover design, stage gotchas), mockup `docs/mockups/ingest-unreadable-files-states.html`.
Verified: full pytest 6262 passed before the last two test edits, then the touched files re-run green; `ruff check .` clean; `check-locales.py --strict` passes; Swift `IngestOutcomeTests`+`PipelineSummaryTests` 42 passed, `DiagnosticPopoverSizingTests` pass, Debug build succeeds. Fable review (5 findings fixed, see the commit): digit/CJK-colon labels, headed-section guides, end-to-end left-alone test, one shared filter. Swift full suite: 2 serve-fleet timing tests (`ServeReapingBusyTests`, `ServeManagerStartClaimsStandbyTests`) failed under full-suite load, 26/26 passed alone (flake, unrelated).
**Owed:** (1) the website's `supported-files.md` is reworded and committed (`4aa0775` in the website repo, not deployed; the popover link now targets `/docs/supported-files.html`). (2) Footer wording is mine ("Other files left alone: N", a label form to avoid per-language plurals): owner to rewrite if wanted, in all 21 locales. (3) The Swift `ScanSelection` mirror is untouched because classification did not change. (4) **Not fixed:** the report not refreshing after a partial completion (suspect `DetailPaneKind.reloadsOnCompletion` skipping `.completedPartial`; unconfirmed, could not reproduce). With strays no longer causing partial runs it will bite less often, not never. (5) Heuristic limit: a guide with `Q1:`/`Q2:` lines still reads as a transcript; an agency `.docx` with speakers on their own lines is refused.
Release-note candidates: **A folder with scripts, notes or spreadsheets in it no longer reads "Partial completion".** Files Bristlenose doesn't read are left alone; the problem popover says how many. **A discussion guide saved as Word is no longer analysed as an interview.** It is named as having no transcript in it.

**6 Nov 2026 — Serve-mode trust-boundary audit: wrapped for the week (Claude Sonnet 5.5, with Fable/Opus finders and reviewers; committed on local `main`, not pushed).**
Done: `/mcp` on a desktop-hosted serve refuses when there is no scoped token (`2bf362a10`); eight `tests/test_trust_*.py` gates (401 sweep, anonymised CSV, file modes, MCP name map, chat-lens corpus assembler, stage-5b log, and the pii_summary pre-existing-file case `9cfd6b859`), each shown to fail when its guard is removed. Fixed and pinned: `pii_summary.txt` is 0600 (`db7adad6d`), no names or quote text in the log (`0d6580519`), a hidden quote is no longer a codebook builder exemplar (`750b4a162`, owner ruling "hidden means hidden"). **Owner ruling:** raw text reaching the cloud model with redaction off by default is accepted by design (redaction is research ethics for what goes onward, not security); logs are debug output and must not leak names. Trust map rev 3: 139 routes, 80 crossings, with a draft risk and effort score on the 39 unpinned ones (draft judgement, not derived).
**Open:** the long tail is in `docs/private/100days.md` §6 Should ("Serve-mode trust map: the long tail"), ranked by risk per effort. Slice 2 is not cleared (the finders missed the hidden-quote leak); slices 3–7 are unaudited; two drafted messages (Defect mine, the performance orchestrator) are unsent. Report: `docs/private/audit-n6a1/followup-report.md`. Release-note candidate: **Your participants' names no longer appear in the log file, and `pii_summary.txt` is readable only by you.**

**3 Nov 2026 — Display control built, web and Mac, committed locally as `cfe9697c3` on `main` (Claude Sonnet 5.5; not pushed).**
One Display button: **Layout** (Columns · Single column), **Density** (continuous, 0–1, Normal at 0.5), **Break long paragraphs** (ON by default, owner 4 Nov 2026: `DEFAULT_BREAKS` and `DisplayPrefs.standard`), **Focus Mode**. Mac popover (`DisplayPopover.swift`, Quotes toolbar group): icon rows with an accent disc for Layout, a slider for Density (snaps to Normal), plain left-tick rows for the last two; the popover sends choices to the SPA (`setDisplay*` menu actions) and reads the SPA's `display-prefs` post, never UserDefaults. Web `DisplayMenu.tsx` (stays open on a choice): icon rows, density as three named stops, ticks. Store `DisplayPrefsStore.ts` (density a number, old words still load); CSS `organisms/display-prefs.css`; `QuoteCard` renders `breakIntoBlocks` blocks when on (idle only); persistence via mirrored prefs (`bn-display-layout|density|breaks`). Strings reuse the nine `common.toolbar.display*` keys from Swift (no new `desktop.json`). `breakParagraphs.ts` untouched (other session). Design variants: `docs/mockups/display-popover-variants.html`.
**Single column width (owner, 3 Nov):** held to `--bn-max-width` (52rem), the width Discussion uses, for the whole group so the hidden-quotes control stays with the cards; **Signals card stack also held to `--bn-max-width`** (owner, 3 Nov; `.signals-center .signal-cards`, SPA only, the card design and the stats block untouched; `tests/test_signals_card_width_css.py`). Not yet seen on the real Talismanic Signals page (the stats block, closed by default, floats right with the text round it; checked open on the smoke fixture only). **Fixed on the way:** Single column no longer switches `display` from masonry to grid (the owner saw quote text vanish in the Mac app; not reproduced in WebKit 26.4, so the cause is a hypothesis: contents of `content-visibility: auto` cards left unpainted after the switch); Escape closing a menu also cleared search/selection (`useKeyboardShortcuts`); outside-click pulled focus back to the trigger (`useMenuKeyboard`); popover clipped in Polish. Both shared-hook fixes also change the Export menu.
Verified: vitest (all pass except load-timeouts that pass alone), `npm run build`, bundle 210.5/222 kB, lint, ruff, Python theme/contract/locale-gate tests, Swift `DisplayPrefsMirrorTests`+`ReportPrefsMirrorTests` 22 passed; 19 web guards mutation-proved, Swift guards NOT; live Playwright checks in Chromium and WebKit (menu stays open, Single column 704 px, chrome heights unchanged, Normal identical to the old page across 143 elements, continuous density ends match the old Compact and Spacious, a long quote breaks with the chip on its last line); popover rendered live in dark and Polish. Reviewed: gruber (plan), a11y, i18n, code-review (fixes made); **the continuous-density rebuild and the new popover were not re-reviewed**.
**Owner to check:** the popover in the real app (VoiceOver on the slider and rows; the Single-column blank-text bug, which I could not reproduce); a project with long quotes for Break; the slider's feel and whether it needs a mark at Normal.
**Decided 4 Nov 2026:** Break defaults ON (done); Focus Mode persists (done: `bn-focus-mode` is a mirrored pref, applied before first paint); the Uncategorised floor follows Display fully, Break included, and so do Signals evidence quotes (`UncategorisedFloor.tsx` / `SignalsPage.tsx`, on main in `2c6c5d873` + `589c33df8`; reviewed by five agents 6 Nov, findings 9–15 in the private review log, 9/11/12/13 fixed). **Open from that review, owner's call:** in a Signals card the paragraph gap inside one quote (~11px) is wider than the gap between a speaker's consecutive quotes (~3px), so the grouping reads backwards — try an indent, a larger run gap, or unbroken runs on a long quote in a run, Focus Mode on and off (review Finding 10); plus the owner ruling (4 Nov) that Break moves to Settings and applies everywhere while Density and Layout stay Quotes-only (100days §8); a search highlight is not carried across a block break (accepted as unlikely to matter); "Display" wording researched 5 Nov (details: `design-display-preferences.md` §10.3): Apple's words for "how content looks" are View/View Options, never Display (the monitor), so the nine-locale difference between toolbar and Settings is correct; fi, uk and tr toolbar words are Apple's Appearance and want a native check; English "Display" itself is not Apple's word (owner to choose View/View Options or keep); Microsoft side NOT measured (needs the owner's OK to download the Terminology zip). **Owner rulings 6 Nov 2026 (design doc §10a):** View ▸ Display submenu added; scope stays Quotes and Signals; keep the word "Display"; Escape guard kept and pinned by a source-scan test. For the algorithm session: `…` (U+2026) is not recognised as a cut; `»` `“` not as sentence ends. Release-note candidate: **A Display menu in the toolbar** sets columns or one column, how roomy the quotes are, and breaks long quotes into paragraphs (new, so a minor).

**Display review, 6 Nov 2026** (4 agents, log `docs/private/reviews/display-preferences.md`, gitignored): finding 1 (Escape-guard test could pass with the handler deleted) fixed in `670fcc283`. Open, none blocking: (2) no test ties the three `menuAction("setDisplay…")` names and density stops to `AppLayout.tsx` (a ~15-line parity test); (3) the View ▸ Display items are sentence case under title-case siblings (needs `desktop.menu.view.display.*` keys, 21 locales); (5) `0.5` hardcoded instead of `DisplayPrefs.densityNormal`, Break setter ignores its new value; (7) stale comments/docs (Focus "resets to off", `design-focus-mode.md:274`, design-display Status line); owner calls: Focus Mode app-wide vs per project, density between stops ticks nothing. Not yet seen in the running Mac app: View ▸ Display, VoiceOver on the slider, the Single-column blank-text bug.

**3 Nov 2026 — any-llm cleanup and the owner calls on salvage (Claude Sonnet 5.5; committed on local `main`, not pushed).**
Owner's rulings: 62 keep (`configure any-llm` saves a proven key when the host check fails), 48 yes (persist drops), 56 follow the cloud pattern (Ollama salvages), 50 leave (per-attempt telemetry rows stay).
Commits: refused calls recorded `error` not `ok` on Claude, ChatGPT, Azure and Gemini (`35642a1bb`; four sites mutation-checked; "Empty response" rows left as they were), "unusable quote" wording (`0497b3547`), CI job `any-llm-library` installing the real extra plus a fake-vs-real `convert_exception` test and the walk-fix tests folded into `test_anyllm.py` (`c866b01da`, `81cbc23ed`, `b7486c55d`), the left-out count kept on the stage-9 session record so a resumed run prints it (`87f549de9`, pinned for `run` both cache paths, the readable chain and `analyze`), Ollama's last attempt salvages (`099891960`). Reviewed by independent code-review agents; fixes in the same commits.
**Open:** the Mac app still shows no drops (new surface, mockup under the R114 gate); nothing has run on a real local model (100days "Try a real local model on a big machine"); findings 13, 14, 15 in the private review log; the 502 `UpstreamProviderError` class is not in the fake's error table beyond the name; Toto and the owed paid walks untouched. Full Python 9434 passed with `test_locale_key_readers.py` and `test_welcome_timeline.py` deselected (both red from another session's uncommitted display-preferences and theme work).
Release-note candidates: **A resumed analysis still says how many quotes were left out of a session**, where only the first run did. **A local model that breaks one quote no longer loses the whole session**; the other quotes are kept, as with the cloud providers. **A call the provider declined is no longer counted as a normal one** in the cost estimates (Claude, ChatGPT, Azure, Gemini).

**3 Nov 2026 — `bristlenose serve` default port 8150 → 8484 (Claude Sonnet 5.5; on `main`: `62f8cc65f`, `55bdebe32`, `f2d290f53`, `93f5973f9`, `4dab5cee2` pushed; the review-fix commit `f7e6ed4f8` not yet).**
Owner ask (memorable, distinctive; IANA-unassigned; Grist, the one common claimant, is mostly a French public-sector deployment, not a researcher's `localhost`). Now one source, `bristlenose/ports.py` (`93f5973f9`); `tests/test_default_port.py` pins the text copies (vite, e2e, Settings table, `launch.json`, Xcode scheme, man page) and sweeps code for an unlisted one, `tests/test_env_name_parity.py` pins Swift's `_BRISTLENOSE_*` names to Python's, and CLAUDE.md has a Seams index (`4dab5cee2`). Plan reviewed by a Fable agent before building (its fixes made: man page added to the pinned copies, sweep scoped to code, the registry idea dropped because 13 `tests/fixtures/*-contract.json` files already are one). Built code reviewed 6 Nov by a code-review agent (no behaviour bugs, three false comments fixed) and a silent-failure hunt (seven ways a test could pass wrongly; four closed in `f7e6ed4f8`, each proved by a mutation; left as stated limits in the test docstrings: names without the leading underscore, a Python write counted as a read). **Owed:** the website's `docs-src/cli.md` and `connect-an-agent.md` say 8150 on `main` there; the change to 8484 is drafted and committed on the website repo's branch **`after-pypi/0.45.0`** (`65117c0`, one commit, unpushed, not deployed). The version in the name is a guess, because no next version is planned: rename it with `git branch -m` once the bump is decided (a higher number only holds it later, never lands it early). **Same session, the Snap listing:** `snap/snapcraft.yaml` summary and description rewritten from the README and install copy, "Everything runs locally" and the cost line dropped (`810a21066`, `03918b373`); reaches the Store only on the next snap publish, and `snap install` needs `--edge` until stable (promote at the App Store submission, 24 Nov). Screenshots (Ubuntu VM, Firefox, fixture recordings, mid-Nov), a banner, and Wave 10 of the private launch plan are filed in 100days §13. **Found, not changed (owner: leave it):** `desktop/scripts/reset-sandbox-state.sh` step 2 and `.claude/agents/security-review.md` (lines ~141-145, 315) still describe a per-project port range 8150-9149 with djb2 allocation; the Mac app passes `--port 0` (`ServeManager.swift:933`) and the allocation was removed in Apr 2026, so the script may miss a stray process outside that range and the review agent is told to flag a mechanism that no longer exists. **Considered and dropped (owner, 3 Nov): the Vite dev port (5173).** It is Vite's own default and every use is `serve --dev` only, so a drifted copy breaks a contributor's loop visibly and never reaches a user; the one quirk is that `serve --port 5173` switches on the SPA's dev-only UI (three `location.port` checks). Owner call: existing users are not a concern, bookmarked links and pasted agent configs on 8150 simply stop working. Bump: no capability added, a default changed. Release-note candidate: **The report now opens at `http://127.0.0.1:8484/report/`**, where it was 8150; bookmarks and any agent config pasted from the old address need the new one.

**2 Nov 2026 — Provider-problem pill, slice 1: key rejected and out of credit (Claude Sonnet 5.5; committed on local `main` `a918521a7`, `db481e43c`, `bf3e69c7b` and docs, not pushed).**
One title-bar pill replaces the out-of-credit pill and the DEBUG prototype: `ProviderProblem.swift` (pure rules), `ProviderProblemModel.swift` (state, persistence, recording),
`ProviderProblemPill.swift` (view); as-built record and the judgement calls made on the owner's behalf in `docs/design-provider-problem-pill.md`; design argument in
`docs/mockups/provider-problem-surface.html`. A refused run or report call lights it (a stored verdict from Settings no longer does); the x hides it; it is held to the key's
verdict. Reviewed in two rounds by Fable agents (code, silent failure, Mac-native, test placement), fixed, and re-checked; twelve of the fixes mutation-proved; Swift 2967 passed / 0 failed, Python 9417 passed (three timing-flaky `test_package_install` Ctrl-C tests failed under load and pass alone). **Open:** the report-call (AutoCode) path cannot check which key a refused call used. NOT seen running in the app: the hover
reveal, the fade, the centred `.status` placement, the VoiceOver announcement, macOS 15. The Diagnostics menu (Provider problem pill) forces any look.
**Owed:** native review of the eight new `desktop.providerProblem.*` keys in 20 locales (drafted by Claude); slice 2 (network diagnosis and the ladder) was briefed and probed by a separate session (`docs/design-provider-problem-diagnosis.md`, `experiments/provider-reachability/`, `d1a15a819`); slice 3 (switch-provider pull-down) is a Could in `100days.md` §8. The sidecar-fingerprint cost keeps a stale
**Placement experiment (3 Nov 2026, Claude):** a DEBUG-only switch (`c213f6749`, Release fix `683d6a249`) moves the pill to the head of the trailing toolbar group; the owner saw it right on macOS 27 and has not decided to ship it. Unchecked: the gap when the pill hides, macOS 15 and 26. Record in `docs/design-provider-problem-pill.md` § Placement experiment. Search sometimes losing the toolbar fold is filed P3 in `100days.md`.
`OutOfCreditModel` comment in `frontend/src/shims/bridge.ts` unfixed. Release-note candidate: **The title bar now says when your AI provider has rejected your key**, not only when
credit has run out, and it no longer stays lit for months over work that never needed the provider: it fades to a small mark after a day and a click on its x hides it.

**1 Nov — Agent Access save-failure alert removed (Claude; committed `c344fdcd3`, `a672d2715`, not pushed).**
Owner's ruling: the bare app-modal "Couldn't save your change." (observer in `BristlenoseApp.swift`, fired by
`.bristlenoseAgentAccessNotSaved`) is gone; the sidebar already shows the restored flag and the cause stays in the log
(`project-index`: "agent access write did not persist"). The notification is still posted (`AgentAccessWriteTests` pin it).
Files: `BristlenoseApp.swift`, `ProjectIndex.swift` (comment), `tests/test_desktop_app_observers_once.py`.
Verified at `a672d2715`: ruff clean, pytest 9338 passed / 6 xfailed, `test-swift.sh` 2905 passed / 0 failed.
Review: self-review of the diff only (found and fixed a stale "like the alert below" comment); no independent reviewer ran.
Found on the way: the Swift failure tests were putting this real alert on screen in the test host (four runs on 1 Nov).
**Open, owner's call:** a failed Turn Off now says nothing, so the researcher sees the antenna stay and no more. Whether
that needs a quiet mark (never a modal) is a mockup under the R114 UX gate. Card on the board (Todo, Broken, Must) and
`100days.md` §2 Must carry it. Release-note candidate: none (a failed save shows no alert).

**30 Oct to 6 Nov 2026 — Whisper first run on a clean Mac (Claude; `4ba513387` and the Windows lock-probe fixes `0223fa1e2`, `a8d9fc138` (other sessions) are in v0.44.0; `7675848e0` is after the tag, unreleased; `main` is not pushed).**
Found on clean Tart guests (macOS 15.7.7 / 26.6.2 / 27.0) running the 0.43.0 DMG's real sidecar: on 15 it SIGTRAPs in `mlx::core::metal::Device::Device()` 2 s
after launch (red pill, Retry dies at once); 26 and 27 fine. Cause: pip took MLX's `macosx_26_0` wheels (minos 26.2) on the macOS 27 build host for a 15.0-floor
app. Proven by swapping only the MLX files for the `macosx_15_0` wheels in the same bundle. Plan and review notes: `docs/private/plan-whisper-first-run-2026-10-30.md`.
**In 0.44.0:** `build-sidecar.sh` pins the 15 wheels (`_pin_mlx_to_floor`, tags in the deps fingerprint) and `check-sidecar-mlx-floor.sh` refuses a bundle that does not
(wired into build-sidecar / dmg / pkg); `doctor` and the status probe ask `module_installed`, and a CHILD process (`doctor --mlx-probe`) asks whether MLX starts (+1 sidecar
start per run preflight: ~1.1 s CPU, 9.5 s on a cold guest); `ensure_disk_room` refuses a fetch the disk cannot hold (model + 1 GB); auto-start floor 20 -> 10 GB;
`_fetch_retrying_network_loss` waits out a dropped network and restarts (an outage over ~15 s killed the download and Retry began at zero; bounded: 5 restarts, 300 s per
wait, 10 s per Hub question; the terminal first run too); dead-download partials are swept at the start (>120 s) and after success (>20 s), never one whose HF flock is held.
**After the tag:** `WhisperFailureCause` — the pill popover and Settings row say disk full / the connection dropped / a certificate not trusted in place of "The download
didn't finish." (unrecognised causes keep the old line; no new element; `desktop.modelDownload.cause{Disk,Network,Certificate}` in all 21 languages;
`tests/test_whisper_failure_cause.py` pins the Swift patterns to Python's retry markers). NOT seen rendered in the app: the Whisper `debugApply` harness has no menu entry.
**Website, live:** install page (no longer claims the model is bundled; ~4 GB free), docs privacy page, and the top-level `privacy.html` all say 10 GB (`2081472`, `ca48063`, `1cd2d29`).
**Method and results:** `experiments/whisper-download-battery/` (README: the matrix per OS, the measured thresholds, the traps) — the harness was in a scratch dir and was
lost on 4 Nov, reconstructed 6 Nov and re-run on a clean guest. Reviewed 4 rounds by Fable plus silent-failure-hunter (no blockers in the last); full Python 9,228 passed, Swift 2,911.
**Open:** a captive-portal HTML page fails fast but reads "Expecting value: line 1 column 1" (a fourth sentence in 21 languages); 407 / portal-403 are not retried; the probe has no
cache; Apple speech, an M5 and a real macOS 15 Mac are untested; Sarah's macOS version is unknown; the 0.44.0 changelog says the download "resumes" (it starts again from zero).
Release-note candidate (unreleased): **A failed Whisper download now says why** (disk full, the connection, a certificate), where it only said it failed.

**30 Oct to 1 Nov 2026 - Signals lens: grey until its first report exists; card click and scroll; sidebar "Picking up Signals…" (Claude Sonnet 5.5, the Signals session; on `origin/main`, unreleased).** Owner ask: no bare unfilled page; the lens greyed and unclickable, progress under the project name. Plan and as-built: `docs/design-signals-lens-readiness.md` (decisions §8, departures §9). Server `75179d809` + `3079045c6` (a counter noted where a run's overlay ends and for a whole codebook apply, ended in a `finally`; `/condition` withholds Signals only while no report with cards exists; `/signals/snapshot` says `pending`), page `b5982c72a` + `3079045c6`, 21 locale strings `4c2dc9a2f`, Mac `fde55d8f2` + `e099e3b4d` + `14c6227c1` + the real-cell render test, card click and scroll `8cc10ddec` + `72824bacf`, keyline `281c707e7`, `aria-current` `6cda170ba`. Every slice reviewed by Fable and fixed; reverse-edit checks on each fix. Verified: Swift 2,899 green, front-end 3,781 green (Node 24), targeted Python green, the withheld lens, the report landing, card click and scroll in Chromium and WebKit on a real server, and **in the running Mac app (1 Nov): lens dim and "Picking up Signals…" for about 59 s, Export Report disabled, then everything recovers.** Owner calls recorded: a card click switches the inspector tab; short pages are not padded; the crash pane offers feedback, no Retry; a double-click selecting a word also selects the card (accepted). **Open:** the "Show animation while analysing" label now also governs the status shimmer; a clean re-analysis misses the hand-over prior (one collapse and regrow); a codebook apply on a study with no report shows the line for the whole job; no cloud model can show it for up to two seconds; the German phrase is the shorter of two. `ActivityStore` vitest failures were this shell's Node 26, not the code. Release-note candidate (minor): **The first Signals report no longer shows half a page.** The Signals lens stays greyed with "Picking up Signals…" under the project name until its first report is ready, and then opens full. Selecting a card by clicking it, and a full outline on the selected card, are new in the same pass.

**30 Oct 2026 - Signal highlights: shorter, and at most two coloured bullets per card (Claude Sonnet 5.5; committed on local `main`, not pushed).** Owner ruling: "the shorter plus the budget". Prompt 0.6.0 (0.5.0 archived), `structured.py` descriptions, `_MAX_FRAGMENTS_PER_SIGNAL = 2` in `server/elaboration.py` (keeps the first two per signal, logs `fragment_budget`), `SIGNAL_SNAPSHOT_PAYLOAD_VERSION` 6. Commits: adoption `f68b59834` (its subject says "a quarter of the colour"; the measured drop is about half, 46% to 24% of the page), lab `3e7b8875e` to `3b2bb061b`. Method, the owner's 91 blind picks, every variant, spend ($3.45, 822 calls) and eight open items: `experiments/signal-highlight-lab/README.md`. **Effect on users:** every study re-runs its Signals narrative once at the next serve start when a cloud key is present (one paid batched call per study; headlines and claims are rewritten too, not only highlights); an existing report stays readable meanwhile. Verification: elaboration, snapshot and prompt tests 730 passed; two new budget tests (the first mutation-checked red, the second guards counting order and was not); ruff clean; full Python 9163 passed, 5 failed: `test_no_improvised_icons` x2 (frontend `IntensityDots.tsx` / `SignalsPage.tsx` from the other session's Signals commits, not touched here) and three Ctrl-C download tests that pass alone (load). No Swift or frontend run (none changed). Review: self-review only, no `/usual-suspects`. **Not done:** the joint check (Sonnet writing bullet and span together on a real project, about 0.30 GBP) before relying on it; the owner has not yet seen the adopted prompt's output; a small Haiku highlight step (best match to the owner's picks, not built); how strong the colour looks (CSS). Release-note candidate (improved): **Signal cards carry far less colour.** The highlighted words in each evidence bullet are now a short phrase that starts where the product did something and stops before the reaction, and at most two bullets per card are highlighted. Existing studies refresh once the next time the app starts with a cloud key.

**30 Oct — Codex consolidation and canonical checkout transfer complete.** The
canonical `/Users/cassio/Code/bristlenose` checkout is clean on local `main`, which now
contains `0b7eb11d5` (Zoom 30-day UTC/DST fix plus deterministic startup-probe
verification) and `c84c26606` (parked multi-Mac design/mockup bundle and trued
register). Full Python is green: **9,013 passed, 8 skipped, 133 deselected,
6 xfailed**. Full native is green: **2,851 passed, 0 failed**. Mockup-register,
Ruff, locale-key and staged-diff gates pass.

Its former 105-path inventory is fully
preserved and verified, including a byte-identical external copy at
`/Users/cassio/.codex/preservation/bristlenose-final-consolidation-2026-10-30`.
Claude's organising session owned no edits and intentionally deleted only three
untracked root strays (`the`, `with`, `uv.lock`). The explicit cleanup restored
42 tracked paths and removed 16 preserved untracked files. The redundant
integration worktree, spent Signals branch and eight other merged Codex branches
are retired. `codex/study-access-poc` remains parked and unmerged by decision;
the full source/bundle is preserved. Claude's scratch worktree remains. Two stale
app attachments are unregistered directories and were left intact after the app
archive safeguard could not verify this chat's old primary checkout. No push or release.

**30 Oct — sidebar Finder drops closed on local main.** Implementation 56b46608a
landed via 5a7830935; test corrections c92bba10a and 5120928de. Final pinned
Swift gate: 2,846 passed / zero failed; sidebar Python contracts: 44 passed.
The additional full Python run exposed broader failures, handed to recovery;
this is not a global green/release sign-off. Evidence, limits and archival:
`docs/sidebar-finder-drop-closeout.md`. Shared-checkout defaults for Codex:
`AGENTS.md`. No push/release.

**6 Nov 2026 — defect-gates session (Claude).** Local commits only (`4dda06ea6`..`28ef8783b`), nothing pushed. Owner rulings applied in `96449e677`: byte ceilings dropped, cutoff parity stays a regex test, quote start times cleaned at import (`clean_start_timecode`). One strict xfail remains in `tests/test_quote_id_hazards_pinned.py`: a dashed participant code can collide with another quote's id, which needs a ruling on what a participant code may contain. Hidden-exemplar gap was fixed by `750b4a162`. Report: `docs/private/bristlenose-defect-mining-2026-11-05/morning-report.md`. No uncommitted work of mine.

**30 Oct 2026 — tests no longer write the real `~/.config/bristlenose/timing.json` (`2bc0c5196`; Claude Code, self-reviewed only, not pushed).** The suite had given the default profile (mlx, `claude-sonnet-4-6`) n=16,262 `render` and ~12,000 per LLM stage at ~0.02 s per session, against 15 real runs, and a second profile (apple-speech) n=484, all tests. Cause: `cli._DOCTOR_SENTINEL_DIR` ignores `XDG_CONFIG_HOME`; conftest now redirects it and refuses an estimator on the real folder. The live file was cleaned by hand (apple-speech profile deleted; `render` and the four LLM stages deleted from the `sonnet-4-6` profile; `render` from the `sonnet-4-20250514` one; backups in the session scratchpad, not kept in the repo), so the ring has no stage weights and the ETA is transcription-only on this Mac until a few real runs refill it. **Owed:** an incremental run records new-session time over the whole session count (`pipeline.py` `input_size=_n_sessions`, ~3119/3527/3792/3915), which understates the rate; and `docs/design-progress-layer.md` §5's precondition can now be marked met. Full suite at this commit: 9,229 passed, 3 failed (two `test_no_improvised_icons`, one `test_swift_python_contract` issuesURL), all other sessions' in-flight work.

---

## Task tracking

**GitHub Issues is the source of truth for actionable tasks:** https://github.com/cassiocassio/bristlenose/issues

**Launch plan:** `docs/private/100days.md` — triaged by topic and MoSCoW priority.

This file contains: session reminders, untriaged captures, dependency maintenance, and reference tables.

---

## Dependency maintenance

Bristlenose has ~30 direct + transitive deps across Python, ML, LLM SDKs, and NLP. CI runs `pip-audit` + `npm audit` on every push (informational, non-blocking). Dependabot opens weekly PRs for both ecosystems. CodeQL SAST runs on push + weekly. See `SECURITY.md` for remediation SLA.

### Quarterly dep review (next: May 2026, then Aug 2026, Nov 2026)

- [x] **May 2026** — Run `pip list --outdated`. Bump floor pins in `pyproject.toml` only if there's a security fix, a feature you need, or the floor is 2+ major versions behind _(prophecy 8 Jun 2026 via Cassandra Entries 1+2; execution 9 Jun 2026: security wave `5c96058` (presidio + cryptography 44→48, cleared 3 OSVs, floor bumped) + graduated-holds wave `e3c0a87` (starlette 1.x pair + WTForms 3.2 pair, dependabot config updated). Cassandra tally 4/4/0. Wave-3 greens deferred — see `docs/private/handoffs/dep-wave-3-greens.md`.)_
- [x] **Aug 2026** — Done 3–5 Sep 2026 (Entry 7 in `docs/dependency-premortem-log.md`): nine Dependabot PRs triaged, Actions pins moved (codeql 4.37.9 as one SHA across init/autobuild/analyze, setup-node 7, download-artifact 8, repository-dispatch 4, `actions/attest`), `snapcore/*` → `canonical/*` on node24 (snap edge rev 14), Held register re-grounded — four release-predicates could never fire. Python floor decided in a sibling session: `>=3.12` on 1 Nov 2026 (`docs/design-python-floor.md`)
- [ ] **Nov 2026** — Same. Start with `scripts/check-python-band.py --latest`, `scripts/check-providers-live.py` and `scripts/check-whisper-sizes.py` (the banner's download sizes against the Hub); execute the 1 Nov floor move if it has not happened; the 3.15 / presidio ceiling question is due ~Mar 2027, not this review

### Annual review (next: Feb 2027)

- [ ] **Feb 2027** — Full annual review:
  - Python floor is 3.12 from 1 Nov 2026 — re-run `scripts/check-python-band.py --latest`; the 3.15 ceiling waits on presidio
  - Check faster-whisper / ctranslate2 project health
  - Check spaCy major version
  - Check Pydantic major version
  - Rebuild snap; review `pip-audit` CI output

### Risk register

| Dependency | Risk | Escape hatch |
|---|---|---|
| faster-whisper / ctranslate2 | High — fragile chain, maintenance varies | `mlx-whisper` (macOS), `whisper.cpp` bindings |
| spaCy + thinc + presidio | Medium — spaCy 3.x pins thinc 8.x | Contained to PII stage; can pin 3.x indefinitely |
| anthropic / openai SDKs | Medium — anthropic 1.x removed `temperature` from `messages.create`; GPT-5+ rejects `max_tokens` and non-default temperature; `AsyncMock` cannot see either | `tests/test_llm_sampling_params.py` introspects the installed signature; sunset lists in `client.py` fail closed |
| Pydantic | Low — stable at 2.x | Large migration but not urgent |
| Python itself | Decided — floor moves to 3.12 on 1 Nov 2026; band 3.12–3.14 (`docs/design-python-floor.md`) | `scripts/check-python-band.py` measures the band from wheel tags; ceiling waits on presidio `<3.15` |
| protobuf (transitive) | Low — CVE-2026-0994 (DoS); we don't parse untrusted protobuf | Resolves when patched |

---

## Key files to know

| File | What it does |
|------|-------------|
| `pyproject.toml` | Package metadata, deps, tool config (version is dynamic — from `__init__.py`) |
| `bristlenose/__init__.py` | **Single source of truth for version** (`__version__`) |
| `bristlenose/cli.py` | Typer CLI entry point |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/pipeline.py` | Pipeline orchestrator |
| `bristlenose/people.py` | People file: load, compute stats, merge, write, display name map |
| `bristlenose/stages/s12_render/` | HTML report renderer package |
| `bristlenose/theme/` | Atomic CSS design system |
| `bristlenose/theme/js/` | Report JavaScript modules (frozen — static render path only) |
| `bristlenose/llm/prompts/` | LLM prompt templates |
| `bristlenose/doctor.py` | Doctor check logic |
| `frontend/` | Vite + React + TypeScript SPA |
| `.github/workflows/` | CI (ci.yml), release (release.yml), snap (snap.yml) |
| `snap/snapcraft.yaml` | Snap recipe |

## Key URLs

- **Repo:** https://github.com/cassiocassio/bristlenose
- **Issues:** https://github.com/cassiocassio/bristlenose/issues
- **PyPI:** https://pypi.org/project/bristlenose/
- **Homebrew tap:** https://github.com/cassiocassio/homebrew-bristlenose
- **CI runs:** https://github.com/cassiocassio/bristlenose/actions

---

## Design docs

| Document | Covers |
|----------|--------|
| `docs/archive/design-reactive-ui.md` | Framework comparison, risk assessment (partially superseded by React migration) |
| `docs/design-react-migration.md` | **React migration plan** (Steps 1–10, all complete) |
| `docs/design-react-component-library.md` | 16-primitive component library (complete) |
| `docs/design-llm-providers.md` | Provider roadmap |
| `docs/design-performance.md` | Performance audit |
| `docs/design-export-sharing.md` | Export and sharing phases 0–5 (**superseded** — see 4 feature docs below) |
| `docs/design-export-slides.md` | Export dropdown (scope→format), per-quote copy icon, PowerPoint quote slides |
| `docs/design-export-quotes.md` | CSV + XLS spreadsheet export (11-column table) |
| `docs/design-export-clips.md` | Video clip extraction via FFmpeg |
| `docs/design-export-html.md` | Self-contained HTML export + cross-cutting export concerns |
| `docs/design-miro-bridge.md` | Miro API integration (OAuth, board creation, layout — post-beta) |
| `docs/design-html-report.md` | HTML report, people file, transcript pages |
| `docs/design-discussion-lens.md` | Discussion lens — the researcher's guide merged with the questions actually asked, as a navigator over quotes grouped by question; both channels. Shipped for beta 3 Oct 2026 (stage on by default, lens in nav, Mac rail and export); plan and what's owed: `docs/design-discussion-lens-plan.md` banner — real-corpus scoring, overrides, cohort baselines, a guide-language steer, a fail-closed anonymiser gate, the CHANGELOG entry (the guide as a left panel, the guide tabs and the Mac guide panel landed 4 Oct) |
| `docs/design-responsive-layout.md` | Responsive layout, density setting, breakpoints |
| `docs/design-doctor-and-snap.md` | Doctor command, snap packaging |
| `docs/design-serve-doctor.md` | Serve-mode doctor checks, Vite auto-discovery |
| `docs/design-research-methodology.md` | Quote selection, sentiment taxonomy, clustering rationale |
| `docs/design-pipeline-resilience.md` | Manifest, event sourcing, resume, provenance |
| `docs/design-logging.md` | Persistent log file, two-knob system |
| `docs/design-test-strategy.md` | Gap audit, Playwright plan, `data-testid` convention |
| `docs/design-desktop-app.md` | macOS app, SwiftUI, PyInstaller sidecar |
| `docs/design-session-management.md` | Re-import, enable/disable, quarantine |
| `docs/archive/design-codebook-island.md` | Migration audit, API design, drag-drop (v1 lens, archived 20 Sep 2026) |
| `docs/design-signal-elaboration.md` | Interpretive names, pattern types |
| `docs/design-transcript-editing.md` | Section strike, text correction, prior art |
| `docs/design-speaker-splitting.md` | LLM splitting for single-speaker transcripts |
| `docs/design-speaker-role-detection.md` | Generalised role detection (oral history, journalism, etc.) |
| `docs/design-speaker-editing.md` | Four transcript editing operations (name, reassign, split, merge) |
| `docs/design-transcript-speaker-editing-roadmap.md` | 11-layer work breakdown for transcript + speaker editing |
| `docs/design-sidebar.md` | Dual-sidebar layout (TOC left, Tags right) |
| `docs/design-windows-port.md` | Windows status: the CLI on Windows, CI, what is unexercised |
| `docs/design-winget.md` | winget plan (steps 1–6) and its decisions; `docs/release-winget.md` is the per-release procedure |
