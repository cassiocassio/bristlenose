# Renaming the Analysis lens to Signals

_Last updated: 20 Sep 2026_

**Status: IMPLEMENTED 20 Sep 2026** — Phases 1–5 landed in five commits
(`2aba263b`, `c93d9c92`, `94e23670`, `a7e2a153`, and this one). Every count
below was measured *before* the work and is kept as the record the plan was
made against; where the tree disagreed once work started, §10 says so.

---

## 1. The rule

**Three senses, two words** — and the product currently spends one word on all
three.

> **Signals** is a feature: the Signals lens, the signal cards it makes, and the
> signal strength it reports. One sense, bounded by its own vocabulary.
>
> **Analysis** is two things, and keeps the word for both:
> **(a)** the pipeline running on data — the run the researcher commands; and
> **(b)** the human act of interpreting the results of that run.

**The test for any occurrence:** does it name the signal feature, or does it
name a run or an interpretation? Feature → *signals*. Run or interpretation →
*analysis*.

Note that (a) and (b) are genuinely distinct — the machine performs the run, the
researcher performs the interpretation — but nothing in the product needs to
tell them apart, and one word serves both honestly. What the word cannot also
carry is the feature. Calling one lens "Analysis" claims the other four are not
analysis, which is false under sense (b): tagging in the Quotes lens is
interpretation, revising a codebook is interpretation. The rename removes a
claim we do not mean.

The earlier formulation of this rule — *"Analysis is what a researcher does"* —
was close but imprecise at its own boundary: the researcher does not perform the
pipeline run, they command it, so sense (a) fell outside the definition that was
supposed to contain it. Every classification in §3 was made correctly
regardless, and the sharper rule reclassifies nothing. It resolves one case §5
had flagged as worth a second look: `announce.pipelineCompleted` ("Analysis
updated") fires from `LastRunStore` when a run completes, which is sense (a)
outright rather than a borderline call.

## 2. State of play — the rename is already half-done

Measured 20 Sep 2026. These surfaces already say **Signals**, in all 21 full
locales:

| Surface | Where |
|---|---|
| Toolbar label and tooltip | `desktop.json toolbar.signals`, `toolbar.showSignals` |
| View menu | `desktop.json menu.view.showSignals` / `hideSignals` |
| Window title count | `common.json titlebar.signals_one` / `_other` |
| Help content | `common.json help.navSignals`, `help.guide.signalsTitle`, `help.signals.*` |
| Native lens label | [MenuCommands.swift:819](../desktop/Bristlenose/Bristlenose/MenuCommands.swift#L819) — `case .analysis: return "Signals"` |
| MCP tool | `mcp_server.py` `get_signals` |
| Database | `models.py` `signal_key`, `uq_dismissed_signal`, `uq_elaboration_project_signal` |
| Website page | `bristlenose-website/docs-src/signals.md` |

These still say **Analysis**:

| Surface | Where |
|---|---|
| Nav rail | `common.json nav.analysis` |
| Page heading (×3 call sites) | `common.json analysis.heading` → [AnalysisPage.tsx:1278,1289,1324](../frontend/src/islands/AnalysisPage.tsx#L1278) |
| Settings config category | `settings.json configReference.categories.analysis` |
| Swift fallback label | [Tab.swift:19](../desktop/Bristlenose/Bristlenose/Tab.swift#L19) |
| About panel heading | `AboutPanel.tsx:94` — a hardcoded `<h3>`, not i18n'd |
| Welcome cell | [WelcomeHomeView.swift:138](../desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift#L138) |

The welcome cell is the drift caught mid-act: its body says *Analysis tab*, its
link label says *Signals →*, and it points at `signals.html`.

**The translations are already paid for.** `toolbar.signals` and
`analysis.signals` carry reviewed values in all 21 full locales and they agree —
Senyals, Signály, Signale, Señales, Signaux, Segnali, シグナル, 시그널, Сигналы,
訊號. Per the house rule on already-translated twins, lift rather than translate.
`zh-Hant-HK` correctly has neither and inherits `zh-Hant`.

## 3. Scope — what moves and what does not

Every line in the tree matching `analys` was classified by the §1 rule.

| Area | Stays (activity/run) | Renames (feature) |
|---|---:|---:|
| `frontend/src` | 33 | 382 |
| `bristlenose/` | 105 | 341 |
| `desktop/**.swift` | 675 | 145 |
| `tests/` | 50 | 231 |
| `e2e/` | 0 | 8 |
| **Total** | **863** | **1,107** |

Swift is 82% *stays*. That is the rule working, not an accident: the Mac chrome
is almost entirely about the run the researcher commanded.

Of the 1,107 renames, roughly 570 are mechanical (import paths, symbols, routes,
string literals) and roughly 630 are prose and doc comments. Those figures come
from two passes with slightly different filters — treat both as ±10%.

**The mechanical half can be scripted. The prose half must not be.** A bulk
substitution produces "the signals pass", "re-signals", "thematic signals",
"Tagging is signals" — each a broken sentence in a file nobody re-reads. The
863 stays and the 630 prose renames are interleaved line by line in the same
files.

### Explicitly staying

- The run verbs: `Analyse`, `Re-analyse…`, `Stop Analysis`, `Analysing…`,
  `showAnalysisAnimation`, `projectsLeavingAnalysis`, "the analysis pass".
- The methodology prose: "thematic analysis", "Tagging is analysis", "the
  revision itself is the analysis", the Braun & Clarke citations.
- `grounding.py` `INVARIANTS` — "tag counts are only comparable within one
  analysis, never across analyses" is the activity sense, and it is model-facing
  on both assistant surfaces.
- The CLI verb `bristlenose analyze` and the website pages `first-analysis.md`
  and `run-an-analysis.md` — which the shipped welcome screen hardlinks
  ([WelcomeHomeView.swift:102,112](../desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift#L102)),
  so renaming either breaks the app.
- `CHANGELOG.md` and the README changelog section (7 lens-sense hits). They
  record what shipped under the old name, and the website renders the changelog
  live from this repo — editing it rewrites published history.
- The frozen vanilla renderer `bristlenose/theme/js/analysis.js`. Data-integrity
  fixes only; a rename is a design change to a sealed surface.
- **The whole static byproduct, decided in §6.3** — `theme/templates/analysis.html`,
  `global_nav.html:7`, `toc.html:24`, and the output file
  `<output_dir>/analysis.html` that `OutputPaths.analysis_file` writes. Two
  thirds of that page is heatmaps, so `signals.html` would name a third of it.
  The byproduct keeps a coherent vocabulary of its own.

### No env-var breakage

Checked: there are **no `ANALYSIS_*` environment variables**. The settings in
the Analysis config category use `DEFAULT_TOP_N` and siblings. Renaming the
category costs nothing to anyone's shell profile.

### No persisted lens identifier

Checked: no `localStorage` key, no Swift `@AppStorage`, no database column
stores the lens. The only `analysis`-named preference is
`showAnalysisAnimation`, which is the run and stays. **A route change strands no
user state** — only bookmarks, which `hashRedirect.ts` already exists to handle.

## 4. Sequencing against the signal card

**Gen-4 shipped on 20 Sep 2026, and this section's reason to wait is
discharged.** What is left of gen-4 collides with a *different* phase, so the
answer changes rather than simply expiring.

This section originally read: gen-4 is *DECIDED IN MOCKUP, NOT IMPLEMENTED*,
its work list is *items A–G*, and it is about to restructure `AnalysisPage.tsx`
and `analysis.css` — the two files Phase 4 renames — so do Phase 1, then gen-4,
then Phases 2–5. Every load-bearing clause of that is now false. The work list
runs **A–M**, not A–G; all of it is ✓ except **L**, which is DEFERRED; and
`design-signal-card.md` carries `status: current` / `last-trued: 2026-09-20`
rather than a mockup banner. Its own evidence expired too — *"Item G deletes
`.signal-rank`"* was cited as pending, and `analysis.css:738` is now a tombstone
comment recording the deletion. The four commits are `451a43ca`, `9e9af6fd`,
`96323e58`, `08b4bb93`.

**Phase 4's two files are free.** Tiers 1 and 2 were the frontend work and both
landed, so there is no longer a restructure in flight for a rename diff to sit
on top of.

**But the residual gen-4 work sits in Phase 3's blast radius, not Phase 4's** —
which is the thing to carry forward, because it is the opposite of what this
section used to warn about:

| gen-4 item still open | lives in | the phase that moves it |
|---|---|---|
| **L** — `MIN_WEIGHT`, DEFERRED pending a study in the right volume regime | `bristlenose/analysis/sentiment_label.py` | **Phase 3** (`bristlenose/analysis/` → `bristlenose/signals/`) |
| the **escape hatch** — the prompt able to return *no finding* (§8.3; M shipped without it) | `llm/prompts/signal-elaboration.md`, `server/elaboration.py` | Phase 3 touches `routes/analysis.py`, not these — mostly clear |
| **§7.7** — custom codebooks, needs tags to carry definitions | data model | outside all five phases |
| the **clarity signal** | on the board | unscoped |

**Recommended order, as of 20 Sep 2026:** Phases 1, 2, 4 and 5 are unblocked —
nothing in flight touches what they rename. **Phase 3 is the one to time**: do
not run it while L or the escape hatch is mid-flight, because both land in
`bristlenose/analysis/` and a package rename underneath an open change is the
same wasted work this section was always about, just one directory over.

The original advice not to interleave still holds, for the same reason.

---

## 5. Phases

### Phase 1 — the user-visible label

Changes **values only**. No keys move, no routes move, no symbols move. This is
the whole user-visible rename and it is independently shippable.

**This repo**

| File | Edit |
|---|---|
| 21 × `locales/*/common.json` | `nav.analysis` value → the locale's existing Signals word |
| 21 × `locales/*/common.json` | `analysis.heading` value → same |
| 21 × `locales/*/settings.json` | `configReference.categories.analysis` value → same |
| `Tab.swift:19` | `case .analysis: "Signals"` |
| `SeamLabView.swift:134` | `"Analysis"` → `"Signals"` (DEBUG-only seam lab) |
| `WelcomeHomeView.swift:138` | `"The **Signals** tab shows where sentiment concentrates."` |
| `AboutPanel.tsx:94` | `<h3>Signals</h3>` |

**Website repo** (`/Users/cassio/Code/bristlenose-website`)

| File | Edit |
|---|---|
| `docs-src/signals.md:1` | "on the Analysis page" → "in the Signals lens" |
| `docs-src/signals.md:21` | "the analysis grid" → "the signals grid" |
| `docs-src/connect-an-agent.md:8` | "the Analysis lens" → "the Signals lens" |
| `docs-src/welcome.md:59` | "the analysis page" → "the Signals lens" |

No screenshots or SVGs carry the label — the only site assets are two Snap Store
badges and two export glyphs. Nothing to re-shoot.

**Tests to update:** `NavBar.test.tsx:43,96`, `router.test.tsx:92`,
`AboutPanel.test.tsx:128-129`, `e2e/tests/lenses-load-clean.spec.ts:57`.

**Locale edit technique.** Do not round-trip `json.load`/`json.dump` — the
files mix literal Unicode with `\u` escapes and either `ensure_ascii` setting
rewrites hundreds of untouched lines. Use a targeted text replace anchored on
the key, and `json.dumps(value, ensure_ascii=True)` to encode the new string.

**`analysis.heading` is the lens title, and the flush-to-datum first heading.**
The three call sites at `AnalysisPage.tsx:1278,1289,1324` are the loading,
no-data and loaded *branches* of one page, not three sections — so one value
change is correct. The comment above `:1324` records that the previous first
heading was a section title standing in for a lens title, and that removing it
took the datum enrolment with it. Phase 1 changes the value only, so
`lens-datum.spec.ts` (which matches on a selector) is unaffected.

**QA this one in the `.app`, not just the browser.** After Phase 1 both the
window subtitle (`analysis.signals`, via `AppLayout.tsx:727`) and the page
heading (`analysis.heading`) read "Signals" in embedded mode. Before Phase 1
they read "Signals" and "Analysis", so the doubling is new. It may read fine —
but no test can see it, and the acceptance rule for this class is to open the
app and look.

**Gates:** `scripts/check-locales.py`, `pytest tests/`, `npm test` in
`frontend/`, `desktop/scripts/test-swift.sh`, `cd e2e && npm test`.

**Done when:** every user-visible surface reads Signals and no key, route or
symbol has moved.

### Phase 2 — route and `Tab` enum

**The coupling that forces these together.** `Tab.localizedLabel` builds its key
as `"common.nav.\(rawValue)"` ([Tab.swift:25](../desktop/Bristlenose/Bristlenose/Tab.swift#L25)).
Renaming the Swift raw value therefore renames the locale key it looks up. The
locale key move and the enum rename are one commit or the Mac label silently
falls back to the English `label`. (Checked: no locale defines
`nav.analysisShort`, so the `_short` branch needs nothing. `"nav"` is unique in
every `common.json`, so the key move can be scoped to that block safely.)

| Change | Where |
|---|---|
| `case analysis` → `case signals` | `Tab.swift:8` |
| `route` → `/report/signals/` | `Tab.swift:52` |
| `from(path:)` prefix | `Tab.swift:78` |
| 24 Swift call sites | 6 source files, 5 test files — enumerated below |
| `nav.analysis` → `nav.signals` | 21 × `common.json`, scoped to the `nav` block |
| `TAB_ROUTES` | `hashRedirect.ts:11` — add `signals`, **keep `analysis` as a legacy alias** |
| Nav item | `NavBar.tsx:26` |
| Route derivation | `LensSubtitleSync.tsx:30`, `AppLayout.tsx:222,223,361`, `Dashboard.tsx:67`, `useAppNavigate.ts`, `router.tsx` |
| Shortcut + anchor routing | `useKeyboardShortcuts.ts` (2 route refs), `useAnchorReporter.ts` |
| Bridge shim | `shims/navigation.ts` — the `switchToTab` `TAB_ROUTES` half of the wire contract |
| Settings surface | `SettingsModal.tsx:183` — `id: "analysis"` |
| e2e | `routes.ts:20`, `lens-datum.spec.ts:55`, `lenses-load-clean.spec.ts:57`, `export-file-url.spec.ts:45` |
| Frontend tests | `useKeyboardShortcuts.test.ts` (5 refs), `useAnchorReporter.test.ts` (4 refs) |

**Add a React Router redirect** `/report/analysis/*` → `/report/signals/` so
bookmarked links survive, and keep `#analysis` in `hashRedirect`.

**Swift call sites (24):** `MenuCommands.swift:819,856`; `LensItem.swift:39`;
`Tab.swift:8,19,52,67,78`; `ContentView.swift:445,2102,2112,2280,2299`;
`LensAnchor.swift:58,67`; and in tests `LensItemTests.swift:16,51`,
`TabTests.swift:35,66,100,117`, `DocumentStateTests.swift:105,106`,
`LensAnchorTests.swift:34,52`.

**New test required.** `Tab: String` raw values are the wire contract for
`window.switchToTab(tab)`, and nothing currently asserts the two sides agree —
`test_swift_contract_parity.py` compares only the intersection of declared
fields, so one side moving is green. Add a test that reads `Tab`'s cases and
`TAB_ROUTES`' keys and asserts set equality. **Prove it bites:** revert one side
and watch precisely that test go red before committing.

**Done when:** `/report/signals/` serves the lens, `/report/analysis/` redirects,
the Mac toolbar label still resolves from `nav.signals`, and the new parity test
fails when either side is reverted.

### Phase 3 — API paths and the Python module

| Change | Where |
|---|---|
| `routes/analysis.py` → `routes/signals.py` | 3 routes at `:452`, `:807`, `:858` |
| `/projects/{id}/analysis/{sentiment,tags,codebooks}` → `/signals/…` | same |
| `EMBED_PATH_TEMPLATES`, `SERVER_ONLY_PATH_TEMPLATES` | `export.py:48-80` |
| API client | `api.ts:462,469`; `exportData.ts` + `exportData.test.ts:44,45,184-201` |
| `bristlenose/analysis/` → `bristlenose/signals/` | 40 importers, incl. 5 in `grounding.py` |
| 7 module docstrings | every one currently defines itself as "the analysis page" |
| ~21 `filePath` strings across **two** files | `SettingsPanel.tsx` (10) **and** `SettingsModal.tsx:177,186-195` (11) |
| `id: "analysis"` → `"signals"` | `SettingsPanel.tsx:291` — React key + scroll ref, purely local |
| 8 test files `test_analysis_*` → `test_signals_*` | `tests/` |

**There are two settings surfaces and they duplicate the config reference.**
`SettingsModal.tsx` carries its own copy of the same category — same `id`, same
`labelKey`, and eleven more `bristlenose/analysis/*` paths. Both are rendered as
`title={s.filePath}` hover tooltips, so both are user-visible, and the house
rule about keeping these two in sync is already documented for `LOCALE_LABELS`.
Moving one and not the other leaves half the tooltips pointing at a package
that no longer exists, with nothing red.

**The module rename forces one real decision**, because the package already
contains `signals.py` and `generic_signals.py` — `signals/signals.py` stutters.
Proposed:

```
analysis/signals.py          → signals/sentiment.py        (sentiment signals)
analysis/generic_signals.py  → signals/codebook.py         (arbitrary columns)
analysis/generic_matrix.py   → signals/codebook_matrix.py
analysis/matrix.py           → signals/matrix.py
analysis/metrics.py          → signals/metrics.py
analysis/models.py           → signals/models.py
```

This is a design call, not a rename. Give it its own commit.

**Export compatibility:** none needed. An exported report is self-contained — it
carries its own React bundle and its own JSON keys — so reports exported before
this phase keep working unchanged. `tests/test_serve_export_coverage.py` reads
`app.openapi()` and will fail loudly if a renamed route is classified in
neither set. That is the gate working; let it.

**Done when:** `pytest tests/` green, the export coverage gate green, and the
Settings config reference tooltips name paths that exist.

### Phase 4 — symbols, CSS and the locale namespace

| Change | Notes |
|---|---|
| `AnalysisPage.tsx` → `SignalsPage.tsx` | 8 importers |
| `AnalysisSidebar.tsx` → `SignalsSidebar.tsx` | 6 importers |
| `AnalysisSignalStore.ts` → `SignalStore.ts` | 8 importers; the current name is a tautology |
| `AnalysisTab.tsx` → `SignalsTab.tsx` | 2 importers |
| Five interfaces in `utils/types.ts:414,421,435,450,463,508` | `AnalysisMatrixCell`, `AnalysisMatrix`, `TagAnalysisResponse`, `CodebookAnalysis`, `CodebookAnalysisListResponse`, `SentimentAnalysisData` |
| Lazy import + island mount | `main.tsx:48,59,98-101` |
| Bridge lens identifiers | `shims/bridge.ts` (4 refs), `contexts/CodebookFocusStore.ts` (2) |
| `.analysis-*` CSS classes (7) | `organisms/analysis.css` (4), `organisms/inspector.css` (3) |
| `locales/*/common.json` `analysis.*` namespace (43 keys) | 21 files — **not** `zh-Hant-HK` |

**`#bn-analysis-root` at `main.tsx:98` appears to be dead.** It is the only
occurrence in source — no template in `bristlenose/theme` or `stages/` emits
that id, so the legacy island mount has nothing to mount into. Confirm and
delete rather than rename.

**Three traps in this phase, all measured.**

1. **`.analysis-center` is load-bearing in a gate.** `e2e/tests/lens-datum.spec.ts:7,97`
   uses it as the flush-to-datum enrolment selector, and the enrolment has been
   lost to a refactor once already (`f69f0e7f`). Rename both sides in one commit.

2. **`theme/organisms/analysis.css` is named in `theme_assets.py:92`**, which
   the sealed static renderer reads. Renaming the file requires updating that
   list. And the export inlines the **per-project baked**
   `<output_dir>/assets/bristlenose-theme.css` in preference to the bundled
   source, so a class rename will not appear in an already-rendered project —
   QA against a freshly imported one.

3. **`"analysis"` appears TWICE in every `common.json`** — `nav.analysis` (a
   string, line 10 in `en`) and the top-level `analysis` namespace (a dict, line
   448). This is the `"codebook"` double-block trap. A first-match replace hits
   `nav.analysis`, which also needs renaming, so the script reports success and
   silently never touches the namespace. **Select the block by content — the one
   carrying `heading` — asserted unique, or by fully-qualified path.**

   Note `export.css` and `print.css` name no `analysis` or `signal` class, so
   `tests/test_export_css_selectors.py` will neither break nor protect this
   phase.

**One key needs a better name, not a mechanical move:** `analysis.signals`
would become `signals.signals`. Its single call site is `AppLayout.tsx:727`.
Rename it `signals.title` or fold it into `nav.signals`.

**Done when:** no `Analysis`-stemmed symbol remains in `frontend/src` outside the
run sense, and the full suite plus e2e is green.

### Phase 5 — documents

- True the developer docs that say "analysis lens": `design-signal-card.md`,
  `design-signal-elaboration.md`, `design-signal-strength.md`,
  `design-inspector-panel.md`, `design-dashboard-stats.md` and siblings (82 files
  mention it; most are the run sense and stay).
- Rename `docs/design-analysis-future.md` → `design-signals-future.md`. Its own
  title is "Analysis Page — Future Phases", so it is squarely the feature.
- **Keep** `design-analysis-lifecycle.md`, `design-incremental-analysis.md`,
  `design-cli-analysis-register.md` — all three are about the run.
- Update `CLAUDE.md`: the Architecture section's "Analysis page:
  `bristlenose/analysis/`" line, and the reference-docs list.
- `README.md:301` — the Roadmap category heading `### Analysis`. Optional; it is
  a work area, not the lens.
- **18 frontend files carry prose-only references** and need no code change —
  fix them as you touch the files, never in a sweep: `ActivityChip.tsx`,
  `ActivityChipStack.tsx`, `CodebookAuthoring.tsx`, `CodebookV2Sidebar.tsx`,
  `CodebookV2Browse.test.tsx`, `InspectorPanel.tsx` (9 refs), `InspectorStore.ts`,
  `Metric.tsx`, `MicroBar.tsx`, `SectionHeading.tsx`, `SidebarLayout.tsx` + test,
  `QuotesContext.tsx`, `UncategorisedFloor.tsx`, `leadSentence.tsx`,
  `signalDedup.ts`, `useAnchorReporter.ts`, `useVerticalDragResize.ts`.

---

## 6. Decisions

All three settled 20 Sep 2026. None outstanding.

### 6.1 The locale namespace moves, inside Phase 4

`analysis.*` (43 keys, 21 files) becomes `signals.*`. It is the
highest-volume, lowest-visibility item in the plan and it is **not** deferred,
for one reason: deferring is the option that fails by default. Nothing tests
the namespace, no user will ever report it, and there is no forcing function
that would bring it back — the same shape as `design-ci.md`'s "informational
initially — promote to blocking once stable", where the promotion never came
and a suite went unrun for three months. A deferred namespace is a permanent
one, and a permanent half-rename is the artefact this whole plan exists to
remove.

It is also cheaper inside Phase 4 than after it. The call sites —
`t("analysis.heading")` and siblings — live in the files Phase 4 is already
rewriting, so deferring means touching them twice.

**Two things it is not:** `zh-Hant-HK` takes nothing (it inherits `zh-Hant`),
and `analysis.signals` must not become `signals.signals` — rename that key
`signals.title`, single call site `AppLayout.tsx:727`.

**Technique.** Parse with `json`, locate the block **by content** — the one
carrying `heading` — and assert that match is unique before writing; `"analysis"`
appears twice in every `common.json` and a first-match selector silently takes
the wrong one. Write with a targeted text replace and `json.dumps(…,
ensure_ascii=True)` per value, never a `json.dump` round-trip. Review the full
diff of one locale before repeating across the other twenty, then `json.loads`
each result to prove it still parses.

### 6.2 No release of its own

**The rename does not drive a release.** It rides with whatever else is in the
next minor (`0.29.x → 0.30.0`), which that other work earns on the usual rule —
a feature bumps the minor. No dedicated version, no release built around the
rename, and the changelog entry sits alongside the rest rather than heading it.

This also removes the sequencing pressure in §4: if generation 4 of the signal
card is in the same minor, the rename simply lands in the same train, and the
only thing that matters is that the two do not interleave *within* a phase.

### 6.3 `analysis.html` keeps its name

`OutputPaths.analysis_file` ([output_paths.py:95](../bristlenose/output_paths.py#L95))
writes `<output_dir>/analysis.html`, a file the researcher sees in Finder. It
was raised as a rename candidate and **is not one: the page is not just
signals.** `theme/templates/analysis.html` is eleven lines carrying three
blocks:

| Block | Content |
|---|---|
| Key findings | `#signal-cards` |
| Section × Sentiment | `#heatmap-section-container` |
| Theme × Sentiment | `#heatmap-theme-container` |

Two of the three are heatmaps — the contingency matrices, not the signals
computed from them. `signals.html` would name a third of the page. The file is
the analytic output as a whole, which is the §1 activity sense, so it keeps the
activity's word.

This settles the static-render templates with it: `global_nav.html:7`,
`toc.html:24` and `theme/templates/analysis.html` all stay. The sealed byproduct
keeps a coherent vocabulary of its own rather than half-adopting the app's.

**The lens is a different case and survives the same objection.** The SPA lens
also carries heatmaps, but as the *inspector* — a bottom panel reached by
drilling into a card, whose own label is `analysis.heatmapSources` and whose
selection syncs from the card. The heatmap is the evidence behind a signal
there, not a peer section. On the static page the three blocks are siblings.

## 7. Rollback

Each phase is one or a few commits on `main` and reverts cleanly with
`git revert`. The only phase with an external artefact is Phase 1's website
edit, which is a separate repo and a separate manual deploy — revert and
redeploy.

Nothing in any phase writes to user data, migrates a database, or changes a
persisted key. **There is no state to roll forward.**

## 8. Working notes

- **Do not run this alongside a second Claude session.** The mechanical passes
  touch hundreds of files; the shared-index hazard and the swept-commit hazard
  are both at their maximum here. Use `git commit -F- -- <paths>` throughout.
- Verify each bulk edit actually changed files (`git status`, re-grep) rather
  than trusting a clean exit — zsh does not word-split unquoted variables, so a
  list-driven sweep can report success having changed nothing.
- After any scripted edit to a Python file, import the module before believing
  it: `python -c "import bristlenose.signals"`.
- `bristlenose/server/static/` is gitignored build output. After Phase 2 or 4,
  the bundled `.app` serves a pre-rename bundle until `build-sidecar.sh` runs —
  it rebuilds the frontend itself and the freshness gate flags a stale one, so
  this is caught, but QA in the app only after that rebuild.

## 9. Review log — 20 Sep 2026

This plan was reviewed against HEAD after drafting. The review found six
defects, all now fixed above. Recorded because the misses are the instructive
part.

| # | Defect | Fix |
|---|---|---|
| 1 | `OutputPaths.analysis_file` writes `analysis.html` **into the researcher's own folder** — a user-visible artefact name, omitted entirely | new open decision §6.1 |
| 2 | Two line references were wrong: `localizedLabel` is at `Tab.swift:25` (cited 29-35), `TAB_ROUTES` at `hashRedirect.ts:11` (cited 12-20) | corrected |
| 3 | 27 frontend files carrying `analysis` references were never enumerated — the plan named ~24 of ~51 | classified and distributed across Phases 2, 4 and 5 |
| 4 | `utils/types.ts` holds **six** of the interfaces to rename and was absent from Phase 4 | added with line refs |
| 5 | `SettingsModal.tsx` **duplicates the whole config reference**, including 11 more `bristlenose/analysis/*` tooltip paths — Phase 3 costed one file, not two | Phase 3 corrected; sync requirement stated |
| 6 | Phase 1 makes the embedded window subtitle and the page heading both read "Signals" — a new doubling no test can see | QA-in-the-app note added to Phase 1 |

Four assumptions were checked and **held**: no locale defines
`nav.analysisShort`; `"nav"` is unique in every `common.json`; `export.css` and
`print.css` name no `analysis`/`signal` class; and all four named gate scripts
exist. One incidental find: `#bn-analysis-root` (`main.tsx:98`) is emitted by
nothing and is probably dead.

## 10. What the plan got wrong — measured during implementation

The plan was written against HEAD on the afternoon of 20 Sep 2026 and executed
that evening. Five of its claims did not survive contact.

| # | The plan said | What was true |
|---|---|---|
| 1 | Phase 2 needs a **new** parity test for the `Tab.rawValue` ↔ `TAB_ROUTES` wire contract | `tests/test_tab_route_parity.py` already existed and does exactly that. Mutation-tested during Phase 2 — reverting the shim alone fails with *"Tab case(s) with no TAB_ROUTES entry: ['signals']"* |
| 2 | `routes/analysis.py` has **three** routes | Four. Gen-4 added `/elaborations` after the plan was measured, and the module docstring still said "Three endpoints" |
| 3 | `analysis.*` is a **43-key** namespace, `heading` first | 47 keys by the time work started; gen-4 inserted `alsoReadAs`, `labelPositive`, `labelNegative`, `labelMixed` **ahead of** `heading`, which broke the first anchor written against the old shape |
| 4 | Seven CSS classes move | Six. `.analysis-heatmap` is emitted by the **frozen** `theme/js/analysis.js`, so renaming it needs a freeze exception. It keeps its name, and `organisms/signals.css` now carries a comment saying why |
| 5 | `bristlenose/analysis/` holds 7 modules | 8 — `sentiment_label.py` arrived with gen-4 |

Two more surfaced that no plan could have listed:

- **`tests/test_lead_paragraph_atom.py` hardcodes the stylesheet filename**, so
  `organisms/analysis.css` → `signals.css` had to reach into a test about a
  different atom. Caught by the suite, not by reading.
- **Import order is not rename-neutral.** `signals` sorts differently from
  `analysis`, so ruff's I001 fired 16 times in Phase 3 and twice more in Phase 4.
  Auto-fixable, but it means a package rename is never purely mechanical.

### Left undone, deliberately

- **`main.tsx`'s island-mount block appears wholly dead.** Four roots —
  `bn-analysis-root`, `bn-quote-themes-root`, `bn-transcript-page-root`,
  `bn-dashboard-root` — and **zero** source sites emit any of them. The review
  flagged the analysis one as probably dead; measuring the siblings showed the
  whole block is pre-SPA legacy. Deleting only the renamed one would have been
  inconsistent, and deleting all four is a different change. Left intact.
- ~~**Three prose strings are English-only.**~~ **Five, and they landed 21 Sep
  2026.** `signals.loadingData`, `signals.noData` and `signals.tagError` were
  rewrites rather than swaps — and so were `help.guide.signalsBody` and
  `help.signals.intro`, which this bullet did not list: the same commit changed
  "The analysis page surfaces signals —" to "The Signals lens surfaces …" and
  left 20 translations on the old sentence. All five were translated the day
  after the release, against each file's own vocabulary, with *lens* rendered
  per the new `docs/glossary.md` rule (Apple's View noun or the bare name —
  never the optical word). No gate reported any of it: `check-locales.py`
  compares key presence, not value freshness (`docs/i18n-defects.md` item 21).
- **The `analysis-heatmap` class** — see row 4 above.

## 11. Verified in the app — 21 Sep 2026

The mechanical gates were green from Phase 1 onward (pytest 4698, Swift 1463,
vitest 1792, e2e 44, ruff, `check-locales.py`, `tsc`). None of them can see what
the pane *says*, so the bundled `.app` was built at two commits and compared.

| Surface | pre-rename (`8ae8c534`) | post (`02381817`) |
|---|---|---|
| Sidebar lens rail | Analysis | **Signals** |
| Page heading | Analysis | **Signals** |
| Left panel header | Signals | Signals |
| Window subtitle | 13 Signals | 13 Signals |

**The pre-rename screenshot is the argument for the whole change.** That build
says *Signals* in its own left panel header and in its own window subtitle,
while the rail and the heading beside them say *Analysis* — three surfaces of
one lens, disagreeing with each other, in a shipped build.

**The doubling flagged in §5 is a non-issue, and only looking could show that.**
Phase 1 warned that the window subtitle and the page heading would both read
"Signals" where they had read "Signals" and "Analysis". In the app they do not
collide: the subtitle carries a count ("13 Signals") and the heading does not,
so they read as a count and a title rather than as the same word twice. No
change needed. Recorded because the concern was legitimate and the resolution
is evidence, not reasoning.

Both builds are DEBUG, `sandbox=on`, `sidecar=bundled`, so the sidecar is the
real bundled one rather than a dev server — the SPA, the locale files and the
route all came through the shipped path.

## 12. Released — 0.30.0, 21 Sep 2026

**Shipped.** Tag `v0.30.0` on `f5309362`, TestFlight build 3578, the notarised
`.dmg`; PyPI and the downstream channels follow the tag run (`release.sh verify`
is the record). The release itself failed four times before it built — none of
them the rename's fault, one of them mine — and is written up in
`docs/release-log.md` § 0.30.0 and `docs/release-premortem.md` incidents 23–27.

The paragraph below is what this section said before the release, kept as
written because its reasoning about ordering was correct and still applies to
the *website* commit, which waits on `verify`.

> The rename is on `main` and in **no released build**. Every channel is still
> 0.29.1; `main` is 488 commits past that tag, of which this work is six.

- **The website commit (`12981ac`) stays local until the release.** It documents
  a lens called Signals; publishing it before a build exists that says so would
  tell a reader that ⌘5 opens Signals while their app says Analysis. Nothing
  auto-deploys — no workflows in that repo, `deploy.sh` is the only path — so
  the ordering is enforced by there being no trigger.
- **The changelog entry is release-time work and is not written.** `release.sh`
  *commits* `CHANGELOG.md` during its bump step but does not compose it, and
  there is no Unreleased section to add to. The entry will cover 488 commits,
  not six.
- **Bump kind: minor.** Settled in §6.2 — the rename earns no version of its
  own and rides with whatever else the minor carries.
