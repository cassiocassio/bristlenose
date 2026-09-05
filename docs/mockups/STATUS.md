# Mockup status register

Every mockup, its last edit, and its lifecycle. States and their meaning are
defined in [README.md](README.md#lifecycle).

**A file whose last entry is `IMPLEMENTED` is the current truth** — that is the one
to point at. `SUPERSEDED` and `ABANDONED` entries say *why* in a clause; that clause
is what stops the same idea being proposed again.

**All 150 are classified** as of 4 Sep 2026 — 85 IMPLEMENTED · 29 SANDPIT ·
18 SUPERSEDED · 12 PROPOSED · 5 PARKED · 1 ABANDONED. A new mockup should be added
here when it lands, or it becomes the next backlog.

Dates come from `git log`; regenerate rather than hand-edit them. Where a timeline
carries no date the evidence gave none — the state is still evidenced, the day is not.

## analysis

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `analysis-failure-states.html` | 3 Sep 2026 | IMPLEMENTED — the popover half of the sidebar failure states; cited as the mockup (“16 states, real SF Symbols”) by `design-pipeline-diagnostic-popover.md`, and `ProjectDiagnosticPopover.swift` ships |
| `analysis-inspector-panel-v2.html` | 19 Mar 2026 | PROPOSED 19 Mar 2026 · SUPERSEDED 19 Mar 2026 by `analysis-inspector-panel-v3.html` — second iteration |
| `analysis-inspector-panel-v3.html` | 19 Mar 2026 | PROPOSED 19 Mar 2026 · IMPLEMENTED — `InspectorPanel.tsx` ships |
| `analysis-inspector-panel.html` | 19 Mar 2026 | PROPOSED 19 Mar 2026 · SUPERSEDED 19 Mar 2026 by `analysis-inspector-panel-v2.html` — first iteration |
| `analysis-lifecycle-states.html` | 22 Aug 2026 | IMPLEMENTED — the analysis lifecycle states ship on the sidebar row |

## chat-lens

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `chat-lens-ask-in-quotes.html` | 30 Jul 2026 | IMPLEMENTED — the cited question box ships |
| `chat-lens-sidebar-lens.html` | 30 Jul 2026 | IMPLEMENTED — the chat lens ships (`server/chat_lens.py`) |

## cloud-fetch

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `cloud-fetch-states.html` | 1 Aug 2026 | IMPLEMENTED — “Every state, message and copy rule … **open it, it’s the visual spec**” |

## cloud-import

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `cloud-import-consent-reality.html` | 17 Aug 2026 | IMPLEMENTED — the consent surface ships |
| `cloud-import-failure-states.html` | 17 Aug 2026 | IMPLEMENTED — cloud-import failure states ship |
| `cloud-import-recordings-grid.html` | 16 Aug 2026 | IMPLEMENTED — the recordings grid ships |
| `cloud-import-recordings-only-toggle.html` | 17 Aug 2026 | IMPLEMENTED — the recordings-only toggle ships |
| `cloud-import-scope-choice.html` | 17 Aug 2026 | IMPLEMENTED — the scope choice ships |
| `cloud-import-sidebar-progress.html` | 17 Aug 2026 | IMPLEMENTED — `ProjectSubtitle.importingBatch` renders “3 of 4” per this |
| `cloud-import-states.html` | 15 Aug 2026 | IMPLEMENTED — cloud import ships (16 Swift files); MS + Google tenants live |
| `cloud-import-three-platforms.html` | 16 Aug 2026 | IMPLEMENTED — Teams / Google / Zoom surfaces ship |

## codebook

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `codebook-audit.html` | 17 Feb 2026 | PROPOSED 17 Feb 2026 · IMPLEMENTED — the vanilla-JS→React migration audit; that migration is complete, so this is a historical record, not a plan |
| `codebook-disable-old-vs-new.html` | 26 Jul 2026 | IMPLEMENTED — the switch-off treatment ships |
| `codebook-header-library-button.html` | 21 Aug 2026 | IMPLEMENTED — the Browse Library button ships in the header |
| `codebook-library-states.html` | 1 Aug 2026 | IMPLEMENTED — enabled/disabled library states ship |
| `codebook-llm-state-matrix.html` | 3 Sep 2026 | PROPOSED 3 Sep 2026 — the codebook × LLM state audit and the decisions taken against it |
| `codebook-section-headers.html` | 19 Feb 2026 | SANDPIT — a section-header style audit |
| `codebook-v2-author.html` | 29 Aug 2026 | IMPLEMENTED — author attribution ships on codebook cards |
| `codebook-v2-autocode-button.html` | 31 Aug 2026 | PROPOSED 31 Aug 2026 · IMPLEMENTED 31 Aug 2026 — the Install → Uninstall → Review arc |
| `codebook-v2-autocode-progress.html` | 31 Aug 2026 | IMPLEMENTED — the AutoCode progress chip ships |
| `codebook-v2-external-links.html` | 30 Aug 2026 | IMPLEMENTED — external author links ship |
| `codebook-v2-messages.html` | 3 Sep 2026 | PROPOSED 30 Aug 2026 · IMPLEMENTED 30 Aug 2026 — drove `ae050e56`, `1d1eb3a0`, `96de7724`; its “what this needs” section is a diagnosis of a fixed problem |
| `codebook-v2-parity.html` | 29 Aug 2026 | IMPLEMENTED — the v1→v2 parity checklist; v2 is the lens |
| `codebook-v2-prototype.html` | 30 Aug 2026 | IMPLEMENTED — the v2 lens ships |
| `codebook-v2-rail.html` | 29 Aug 2026 | IMPLEMENTED — the navigator moved to the standard left sidebar |
| `codebook-v2.html` | 29 Aug 2026 | IMPLEMENTED — “**The mockup is the spec.**” The v2 lens ships |

## dashboard

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `dashboard-10-ideas.html` | 9 Jul 2026 | PROPOSED 9 Jul 2026 — salvaged from a **discarded** native-experiment branch (`03a260d3` postmortem); an idea catalogue, never a plan |
| `dashboard-assembled.html` | 25 Jul 2026 | SANDPIT — “the assembly at real viewport width, no stage: **resize the browser**”. An instrument for the parked signal-grid work, not a design in its own right |
| `dashboard-autolayout.html` | 14 Jul 2026 | PROPOSED 14 Jul 2026 · **PARKED** — “Vision (parked, **do NOT build now**)”; the dashboard responsive redesign is post-TestFlight |
| `dashboard-coverage-box.html` | 22 Feb 2026 | PROPOSED 22 Feb 2026 · IMPLEMENTED — coverage renders on the Dashboard |
| `dashboard-heatmap-encoding-collision.html` | 17 Jul 2026 | SANDPIT — the demonstration behind a ruling: “**full evidence in** `dashboard-heatmap-encoding-collision.html`”. It shows an encoding failing, so it stays useful whether or not the grid is ever built |
| `dashboard-signal-grid-sizing.html` | 19 Jul 2026 | SANDPIT — called a “**size sandbox**” by its own design doc; the sizing instrument behind the parked signal grid |
| `dashboard-signal-grid.html` | 17 Jul 2026 | PROPOSED 17 Jul 2026 · **PARKED** — “**the widget**” of the signal-grid design. Not shipped: no signal grid in `frontend/src`, none on the Dashboard, and its design doc records the effort as parked alongside `dashboard-autolayout.html` |
| `dashboard-theme-list-stress-test.html` | 17 Jul 2026 | SANDPIT — a stress test, not a design |
| `dashboard-widget-gallery.html` | 25 Jul 2026 | PROPOSED 25 Jul 2026 · **PARKED** — the widget half of the parked dashboard vision |

## edo

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `edo-colour-palette.html` | 2 Jul 2026 | IMPLEMENTED — `theme/colors/palette-edo.css` ships |
| `edo-theme-studio.html` | 2 Jul 2026 | SANDPIT — the Edo palette tuner; `colors/palette-edo.css` ships |

## export

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `export-menu-comparison.html` | 22 Jun 2026 | PROPOSED 22 Jun 2026 · IMPLEMENTED — export reached macOS parity; the “parked” note inside refers to Miro push and PowerPoint slides, not to this mockup |
| `export-popover-lenses.html` | 22 Jun 2026 | PROPOSED 22 Jun 2026 · IMPLEMENTED — the per-lens export surface ships |

## mcp

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `mcp-agents-pane.html` | 22 Aug 2026 | IMPLEMENTED — “the pane design is … drawn at the shipped” size; `MCPAgentsSettingsView.swift` ships |
| `mcp-extension-ux.html` | 3 Aug 2026 | IMPLEMENTED — the `.mcpb` extension shipped 1 Aug 2026 |
| `mcp-spike-ux-walkthrough.html` | 1 Aug 2026 | PROPOSED 1 Aug 2026 · IMPLEMENTED — the spike accepted 30 Jul 2026 |

## miro

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `miro-flow.html` | 23 Jun 2026 | PROPOSED 23 Jun 2026 · IMPLEMENTED — **design of record** for the Miro flow; cited by `design-miro-bridge.md` and `design-board-integrations.md` |
| `miro-native-flow.html` | 28 Jun 2026 | PROPOSED 28 Jun 2026 · IMPLEMENTED — the macOS-native half; `MiroConnectionStore.swift` ships |
| `miro-setup-help.html` | 23 Jun 2026 | PROPOSED 23 Jun 2026 · IMPLEMENTED — the setup help page; cited by `design-miro-bridge.md` |

## move

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `move-to-picker-mock.html` | 8 Jul 2026 | SANDPIT — an “interactive send-to picker … **with live toggles** for the three open UX decisions”, drawn as one data point for the browser family. An instrument for choosing, not the thing chosen: a native submenu shipped, not a picker |
| `move-to-spec.html` | 8 Jul 2026 | PROPOSED 8 Jul 2026 · IMPLEMENTED — “the full interaction spec: 2 apps × 2 phases … tagged built/new/risk”. **Move to** ships as a native submenu in both the menu bar and the sidebar context menu (`desktop.menu.project.moveTo`) |

## other

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `agent-scope-v1.html` | 20 Aug 2026 | IMPLEMENTED — “**The mockup is the spec:** six states”, per `design-mcp-*` |
| `background-runs-view-switch-storyboard.html` | 16 Jun 2026 | PROPOSED 16 Jun 2026 · IMPLEMENTED — the storyboard that forced out the view-switch race; `ServeManager.swift` carries the guard (`drainParked`, `restartIfRunning`) |
| `bracket-colour-explore.html` | 24 Feb 2026 | SANDPIT — the colour exploration behind the live-edit signal; “colour explored in …”, per `CSS-REFERENCE.md` |
| `button-catalogue.html` | 31 Aug 2026 | SANDPIT — the button range at a glance; `atoms/button.css` ships |
| `control-surface-parity.html` | 2 Jul 2026 | IMPLEMENTED — **approved Jul 2026**; the canonical cross-surface × cross-locale terms |
| `debug-inspector-mockup.html` | 1 Aug 2026 | SANDPIT — debug instrument |
| `desktop-nav-toolbar-rearrangement.html` | 21 Jun 2026 | IMPLEMENTED — “the interactive mockup” accompanying `design-desktop-nav-toolbar-rearrangement.md`; the menu/toolbar arrangement ships |
| `docs-site-mockup.html` | 26 Jun 2026 | PROPOSED 26 Jun 2026 · IMPLEMENTED — self-declared throwaway, but the docs site was built: per-topic Markdown in the website repo’s `docs-src/`, published at bristlenose.app/docs/ |
| `editable-themes-prototype.html` | 1 Aug 2026 | SANDPIT — theme-editing prototype |
| `focus-mode-lab.html` | 4 Aug 2026 | SANDPIT — “Sandpit: real quote-card markup”; Focus Mode itself shipped in 0.24.0 |
| `font-weight-tuner.html` | 22 Feb 2026 | SANDPIT — quote-pop vs UI-chrome weight tuner |
| `grid-lanes-quotes.html` | 17 Jun 2026 | PROPOSED 17 Jun 2026 · IMPLEMENTED — the masonry bake-off. **It calls itself a throwaway and that is now wrong**: `display: grid-lanes` ships as progressive enhancement in `theme/organisms/responsive-grid.css`. *Its one linked stylesheet is a dead path (`/report/assets/…`), so it renders bare* |
| `icloud-sync-architecture.html` | 13 Jul 2026 | PROPOSED 2026 · **PARKED** — its design doc opens “**Status: FUTURE MADNESS — parked, not planned**”. The iCloud references in Swift are iCloud *Keychain* (credential sync, settled 18 Aug 2026), a different thing |
| `incremental-analysis-flows.html` | 7 Jul 2026 | IMPLEMENTED — “**Not the spec — the mockup is.**” Incremental analysis shipped in 0.20.0. (Its §7 “modal rejected as friction” rejects one *option inside* the file, not the file) |
| `ingest-refusal-surfaces.html` | 19 Aug 2026 | IMPLEMENTED — ingest refusals surface as named reasons |
| `journey-chain-stress-test.html` | 23 Feb 2026 | PROPOSED 23 Feb 2026 · IMPLEMENTED — journeys ship. *Linked theme CSS was repaired 3 Sep 2026 (see README); it rendered unstyled before that* |
| `keycap-gallery.html` | 19 Jul 2026 | SANDPIT — keycap rendering gallery |
| `lead-sentence-playground.html` | 31 Aug 2026 | SANDPIT — lead-sentence instrument |
| `llm-availability-exposure.html` | 3 Sep 2026 | PROPOSED 3 Sep 2026 — the tier argument for exposing LLM availability. Superseded in substance by `codebook-llm-state-matrix.html` §6, which settles that the control never changes; kept for the reasoning and the surface inventory |
| `measure-aware-leading.html` | 15 Mar 2026 | PROPOSED 15 Mar 2026 — line-height varying with column width (Bringhurst §2.1.2). **Not built**: the `--bn-text-*-lh` tokens are still fixed per size |
| `mini-heatmaps-dashboard.html` | 19 Mar 2026 | PROPOSED 19 Mar 2026 — **not built on the Dashboard**. Heatmaps ship on the Analysis lens instead; no decision recorded either way, so this is an idea that went elsewhere rather than one that was refused |
| `mockup-analysis.html` | 10 Feb 2026 | PROPOSED 10 Feb 2026 · IMPLEMENTED — the Analysis lens ships |
| `mockup-autocode-lifecycle.html` | 3 Sep 2026 | PROPOSED 19 Feb 2026 · SUPERSEDED 29 Aug 2026 by `codebook-v2-autocode-button.html` — a nine-step storyboard of the v1 flow, where importing a codebook and coding with it were separate acts; 0.29.0 made Install *be* apply |
| `mockup-checkbox-options.html` | 28 Feb 2026 | SANDPIT — checkbox style options, side by side |
| `mockup-codebook-badges.html` | 7 Feb 2026 | PROPOSED 7 Feb 2026 · IMPLEMENTED — v5 “final decisions”; `Badge.tsx` ships |
| `mockup-codebook-default-uxr.html` | 19 Feb 2026 | PROPOSED 19 Feb 2026 · SUPERSEDED 29 Aug 2026 by `codebook-v2-prototype.html` — the v1 codebook *picker*, replaced by Browse Library |
| `mockup-codebook-garrett.html` | 19 Feb 2026 | PROPOSED 19 Feb 2026 · SUPERSEDED 29 Aug 2026 by `codebook-v2-prototype.html` — as above |
| `mockup-codebook-norman.html` | 19 Feb 2026 | PROPOSED 19 Feb 2026 · SUPERSEDED 29 Aug 2026 by `codebook-v2-prototype.html` — as above |
| `mockup-codebook-panel.html` | 7 Feb 2026 | PROPOSED 7 Feb 2026 · IMPLEMENTED · **ABANDONED 29 Aug 2026** — this is `CodebookPanel`, the v1 codebook lens, deleted in `baa1aa0e` when v2 became the lens. Built, shipped for months, then removed |
| `mockup-delete-button.html` | 9 Feb 2026 | PROPOSED 9 Feb 2026 · IMPLEMENTED — `Badge` `variant="deletable"` ships |
| `mockup-desktop-rail-removal.html` | 27 Jun 2026 | PROPOSED 27 Jun 2026 · IMPLEMENTED — cited by `frontend/CLAUDE.md` for “Desktop embedded: rails removed” |
| `mockup-discussion-evidence-strength.html` | 26 Jul 2026 | PROPOSED 26 Jul 2026 — evidence-strength treatment for the unbuilt discussion lens |
| `mockup-discussion-guide-distillation.html` | 26 Jul 2026 | PROPOSED 26 Jul 2026 — guide distillation for the unbuilt discussion lens; two US-federal examples |
| `mockup-discussion-heading-options.html` | 26 Jul 2026 | PROPOSED 26 Jul 2026 — heading options for the unbuilt discussion lens (see `mockup-discussion-lens.html`) |
| `mockup-discussion-lens.html` | 26 Jul 2026 | PROPOSED 26 Jul 2026 — “UX is mockup-proven”, but `design-discussion-lens.md` is `status: pending` and says in terms there is “no shipped reality to reconcile against”. There is no discussion lens in the code |
| `mockup-header-redesign.html` | 28 Feb 2026 | PROPOSED 28 Feb 2026 — the mockup for `design-breathing-logotype.md`. **Not built**: nothing in the theme, frontend or desktop implements a breathing logotype |
| `mockup-minimap-columns.html` | 26 Jul 2026 | SANDPIT — “multi-column **prototype** — detection + N-column redraw + single/multi A/B”; the minimap itself ships |
| `mockup-minimap.html` | 10 Mar 2026 | PROPOSED 10 Mar 2026 · IMPLEMENTED — the minimap ships as column 4 of the sidebar grid |
| `mockup-native-feedback-window.html` | 10 Jul 2026 | IMPLEMENTED — `FeedbackSheet.swift` + `FeedbackSubmission.swift` ship |
| `mockup-pii-wiring-spec.html` | 26 Jul 2026 | IMPLEMENTED — the Privacy tab + failure surface wiring; PII removal is stage 7 and the Settings pane ships. (Two *config* keys named in `config.py` remain unimplemented — `pii_llm_pass`, `pii_custom_names` — and now fail loudly rather than warn) |
| `mockup-privacy-settings.html` | 26 Jul 2026 | IMPLEMENTED — the privacy Settings pane ships |
| `mockup-proposed-badge-actions.html` | 22 Feb 2026 | PROPOSED 22 Feb 2026 · IMPLEMENTED — the badge action pill ships; see `docs/design-badge-action-pill.md` |
| `mockup-signal-cards.html` | 26 Jul 2026 | SANDPIT — signal card variants; signal cards ship on the Analysis lens |
| `mockup-tag-count-zero-suppression.html` | 2 Jul 2026 | SANDPIT — “**sandbox to reproduce the decisions**”, real theme CSS over real project data; the CSS trap it documents is in CLAUDE.md |
| `mockup-tag-placement.html` | 7 Feb 2026 | SANDPIT — tag placement comparison |
| `mockup-toolbar.html` | 7 Feb 2026 | PROPOSED 7 Feb 2026 · IMPLEMENTED — the Toolbar island ships |
| `mockup-transcript-annotations.html` | 26 Jul 2026 | IMPLEMENTED — `theme/js/transcript-annotations.js` ships (in the frozen vanilla renderer, now a sealed byproduct) |
| `moderator-question-pill.html` | 23 Feb 2026 | PROPOSED 23 Feb 2026 · IMPLEMENTED · **PARKED 5 Aug 2026** — built and tested, then withheld as not intuitive enough. Flag `moderatorQuestionPill: false`; revisit conditions in `docs/design-moderator-question-pill.md`. Do not delete the code and do not re-propose the idea |
| `native-colour-alignment.html` | 2 Jul 2026 | IMPLEMENTED — the Apple-blue seam alignment shipped |
| `nightfall-focus.html` | 9 Jul 2026 | PROPOSED 2026 · **SUPERSEDED** — named a “superseded mockup” in its own design doc; hand-rolled rather than on the theme |
| `ollama-setup-popovers.html` | 3 Jun 2026 | PROPOSED 3 Jun 2026 · IMPLEMENTED — cited three times across the design docs; `OllamaDownloadPill.swift` ships |
| `person-actions-everywhere.html` | 27 Aug 2026 | IMPLEMENTED — person actions ship across surfaces |
| `quotes-spatial-arrow-nav.html` | 4 Aug 2026 | IMPLEMENTED — `utils/spatialNav.ts` ships (0.25.0) |
| `reanalyse-sheet-pixels.html` | 22 Aug 2026 | IMPLEMENTED — the re-analyse sheet ships on the Mac |
| `release-machine-paths.html` | 23 Aug 2026 | IMPLEMENTED — “companion mockup” to `design-release-machine.md`; `scripts/release.sh` ships |
| `report-freshness-banner.html` | 3 Sep 2026 | PROPOSED 2026 — **not built**. (The “freshness” in `ServeManager`/`AgentActivity` is the MCP tool-call window, an unrelated thing) |
| `responsive-quote-grid.html` | 19 Feb 2026 | IMPLEMENTED — “the **original grid**”, against which `grid-lanes-quotes.html` was the masonry bake-off. Interactive, with a slider and HUD, so it doubles as an instrument |
| `settings-accounts-generalised.html` | 18 Aug 2026 | IMPLEMENTED — Settings ▸ Accounts ships |
| `shimmer-tuner.html` | 19 Jul 2026 | SANDPIT — shimmer-animation tuner |
| `sparkline-explore.html` | 12 Feb 2026 | PROPOSED 12 Feb 2026 · IMPLEMENTED — sentiment sparklines ship |
| `tentative-bars.html` | 19 Mar 2026 | PROPOSED 19 Mar 2026 · IMPLEMENTED — the two-tone `MicroBar` ships (`tag-micro-bar-tentative`), pale tentative + solid accepted, with “N tentative + M accepted” on hover |
| `tooltip-gallery.html` | 22 Feb 2026 | SANDPIT — “6 variants (A–F) with interactive comparison and dark mode toggle”; **variant D was chosen**, per CLAUDE.md |
| `typography-comparison.html` | 15 Feb 2026 | PROPOSED 15 Feb 2026 · IMPLEMENTED · SUPERSEDED — as above |

## out-of-credit

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `out-of-credit-ux.html` | 15 Jul 2026 | PROPOSED 14 Jul 2026 · IMPLEMENTED 14 Jul 2026 — **design of record** for the out-of-credit pill and popover; §3 settled that reaching for AutoCode while out of credit gets nothing new |

## people

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `people-lens-scopes.html` | 27 Aug 2026 | IMPLEMENTED — the people lens ships |
| `people-provenance-paths.html` | 19 Aug 2026 | SANDPIT — provenance-path diagrams for the people lens |

## pipeline

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `pipeline-popover-rolling-log.html` | 22 Aug 2026 | PROPOSED 22 Aug 2026 — the deferred “Future direction” appendix of the popover doc: rolling logs / collapsing phase itinerary. Not built |
| `pipeline-popover-sizing.html` | 22 Aug 2026 | IMPLEMENTED — `ProjectDiagnosticPopover` owns its own size, per this |

## provider

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `provider-status-glyph-vocabulary.html` | 3 Sep 2026 | PROPOSED 7 Jun 2026 · SUPERSEDED 7 Jun 2026 by `LLMProvider.swift` — explored three treatments for the provider dot; a fourth shipped (colour + an always-visible localised label). Six `ProviderStatus` cases ship, this names five. The a11y reasoning stands |

## release-train

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `release-train-marey.html` | 5 Sep 2026 | PROPOSED 5 Sep 2026 — sketch A of three for the build-and-release "watching GUI": Marey/Ibry train chart, stations across (build → gates → tag → channels), time down, one polyline per release; effort is the slope. Options in `docs/design-release-train-dashboard.md` |
| `release-train-board.html` | 5 Sep 2026 | PROPOSED 5 Sep 2026 · IMPLEMENTED 5 Sep 2026 as `scripts/release-board.template.html` + `scripts/release-board.py` (the channel count is read from `project.conf`, not written anywhere) — sketch B: one fixed 16" screen (1728×1117), build stack left, nine channel cards right, irreversible line between, event log + activity strip along the bottom. Grid of grids, no scrolling |
| `release-train-scroll.html` | 5 Sep 2026 | PROPOSED 5 Sep 2026 — sketch C: long scrolling page, time down to scale (1 px = 6 s), swimlanes by architecture chunk, every bar anchored to the event line that emitted it; gaps are waiting |

## sessions

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `sessions-grid-playground.html` | 6 Aug 2026 | SANDPIT · design settled 6 Aug 2026 — the width-at-three-widths instrument behind the Sessions grid |
| `sessions-popover-navigation.html` | 14 Aug 2026 | IMPLEMENTED — the native session switcher replaced the embedded left panel (0.25.0) |

## sidebar

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `sidebar-activity-indicators.html` | 14 Jun 2026 | PROPOSED 14 Jun 2026 · IMPLEMENTED — `ProjectRowActivityIndicator.swift` ships |
| `sidebar-all-tabs-v1.html` | 18 Mar 2026 | PROPOSED 18 Mar 2026 · SUPERSEDED 18 Mar 2026 by `sidebar-all-tabs-v2.html` — first iteration |
| `sidebar-all-tabs-v2.html` | 18 Mar 2026 | PROPOSED 18 Mar 2026 · SUPERSEDED 18 Mar 2026 by `sidebar-all-tabs-v3.html` — second iteration |
| `sidebar-all-tabs-v3.html` | 18 Mar 2026 | PROPOSED 18 Mar 2026 · SUPERSEDED 19 Mar 2026 by `sidebar-all-tabs-v4.html` — third iteration |
| `sidebar-all-tabs-v4.html` | 19 Mar 2026 | PROPOSED 19 Mar 2026 · IMPLEMENTED — last of four iterations. *Linked theme CSS repaired 3 Sep 2026* |
| `sidebar-seam-window-edge.html` | 2 Sep 2026 | IMPLEMENTED — cited from `SeamLabView.swift`’s own source comment; the seam lab ships |
| `sidebar-status-vocabulary.html` | 27 Aug 2026 | IMPLEMENTED — `ProjectCellSpec` / `ProjectSubtitle` carry this vocabulary |
| `sidebar-tidyup-before-after.html` | 14 Aug 2026 | SANDPIT — a before/after comparison of the sidebar tidy-up |

## signal

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `signal-card-expanded.html` | 23 Feb 2026 | PROPOSED 23 Feb 2026 · IMPLEMENTED — signal cards ship on the Analysis lens |
| `signal-elaboration.html` | 23 Feb 2026 | PROPOSED 23 Feb 2026 · IMPLEMENTED — `server/elaboration.py` ships |
| `signals-sidebar-row-layouts.html` | 31 Aug 2026 | SANDPIT — row-layout options for signals in the sidebar |

## type

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `type-scale-audit.html` | 13 Feb 2026 | PROPOSED 13 Feb 2026 · IMPLEMENTED · SUPERSEDED — drove the v1 type scale; `tokens-typography-v2.css` is the live one |
| `type-scale-comparison.html` | 27 Mar 2026 | PROPOSED 27 Mar 2026 · IMPLEMENTED · SUPERSEDED — drove the v1 type scale; `tokens-typography-v2.css` is the live one |

## website

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `website-bento-welcome.html` | 22 Aug 2026 | IMPLEMENTED — the website bento welcome shipped (separate deploy repo) |
| `website-hero-platform-cta.html` | 27 Aug 2026 | IMPLEMENTED — the website hero CTA shipped |

## welcome

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `welcome-carousel-playground.html` | 15 Jul 2026 | SANDPIT — carousel instrument from the same series; `welcome-fibonacci-rotating.html` is canonical |
| `welcome-fibonacci-composed.html` | 15 Jul 2026 | PROPOSED 15 Jul 2026 · SUPERSEDED by `welcome-fibonacci-rotating.html` (canonical) |
| `welcome-fibonacci-refine.html` | 15 Jul 2026 | PROPOSED 15 Jul 2026 · SUPERSEDED by `welcome-fibonacci-rotating.html` (canonical) |
| `welcome-fibonacci-rotating.html` | 15 Jul 2026 | IMPLEMENTED — the **canonical** fibonacci welcome; the others in the series are its drafts |
| `welcome-fibonacci-variants.html` | 15 Jul 2026 | PROPOSED 15 Jul 2026 · SUPERSEDED by `welcome-fibonacci-rotating.html` (canonical) |
| `welcome-gradient-playground.html` | 19 Aug 2026 | SANDPIT — gradient tuner for the welcome surface |
| `welcome-layout-experiments.html` | 15 Jul 2026 | PROPOSED 15 Jul 2026 · SUPERSEDED by `welcome-fibonacci-rotating.html` (canonical) |
| `welcome-science-animations.html` | 25 Jul 2026 | IMPLEMENTED — “**reference spec**” for `WelcomeIllustrations.swift`, and the website welcome cells were ported from it |
| `welcome-science-disclosure.html` | 19 Jul 2026 | SANDPIT — disclosure variants for the science welcome cell; the cell itself ships (`welcome-science-animations.html`) |
| `welcome-studytools-animations.html` | 20 Aug 2026 | IMPLEMENTED — cited from `WelcomeHomeView.swift`’s own doc comment |

## window

| Mockup | Last edit | Lifecycle |
|---|---|---|
| `window-master-child-states.html` | 19 Aug 2026 | IMPLEMENTED — master/child window states ship |
| `window-menu-naming.html` | 19 Aug 2026 | IMPLEMENTED — the Window menu naming shipped |
