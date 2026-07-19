---
status: partial
last-trued: 2026-07-15
trued-against: HEAD@main 27647fbf on 2026-07-15
---

# Welcome screen — content & design source

## Changelog

- _2026-07-19_ — **Study-tools cell gained per-tool illustrations.** Cell 1 is now an 8-tool pool (AutoCode · Codebooks · Tag · Star & hide · Video clips · Send to Miro · Ingest · Redact PII — Export split into clips + Miro), each slot showing a **draft PNG screenshot** between the line and the CTA (85% native, own aspect, faint keyline, 8pt padding, `@2x` imagesets; text-only fallback via `NSImage(named:)` nil-guard). Redact PII art still pending. Per-tool CTA labels replace "Learn". Key references adopt the **text-only path** of `design-keycaps.md` (lowercase bare `t`/`s`/`h` in a mono run). Body line `.callout`→`.body` (13pt). Fixed a pre-existing bug where the chevron hit-strip shadowed the CTA links. i18n still held; draft-art + i18n tracked as an in-flight debt.
- _2026-07-15 (second pass)_ — `§7` supersession line trued: `WelcomeView.swift` is **deleted** (`a310bca6`), not "kept on disk pending a delete decision". Recorded the locale-key retention decision under §Copy & i18n — the retired view's keys are deliberately kept, and three are verbatim-live in `WelcomeHomeView`. Anchors: `WelcomeHomeView.swift:157,189,190`; `ContentView.swift:2340` (mount). Rest of the doc spot-checked fresh (Archetype B).

> **Truing note (2026-07-15).** Authored alongside the Swift build in the same session, and the code moved under it several times. This pass separates **shipped** from **spec**. The content pools are deliberately spec-ahead-of-code (the doc is the source; the Swift carries a subset) — those are marked *shipped subset: N of M*. Everything else now describes what exists. See **§0 Not yet built**.

**Status:** design in flight. Mockups in `docs/mockups/welcome-*.html`; Swift in `desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift`. Single source of truth for the cells and their content.

**Copy & i18n:** copy is hand-tuned **English** while the layout iterates — **do not add locale keys or wire i18n yet.** The localisation pass (German et al., which will stress the fixed geometry — expected, and handled *then* by editorial fit + condense-to-fit) is deliberately deferred to *much* later, post-iteration. No rush.

**The retired view's locale keys are kept on purpose — do not sweep them as orphans.** `desktop.welcome.*` and `desktop.chrome.{welcomeTitle,noProjectSelected,selectProject}` survive in the 20 full locales even though `WelcomeView.swift` is gone (`zh-Hant-HK` carries only its genuine `welcome.subtitle` override and inherits the rest, per the override-fork rule). Two reasons: they are already-translated raw material for the deferred localisation pass above, and three of them are **verbatim-live copy today** — `welcome.dropFolderTitle` ≡ "Drop a folder" (`WelcomeHomeView.swift:189`), `welcome.dropFolderHint` (`:190`), `welcome.aiPrivacyLink` (`:157`). A grep for unreferenced keys will flag all of them; that grep is wrong here. (`chrome.emptyStateHint` is separately live — sidebar chrome, `ContentView.swift:1810`.)

British spelling. Terminology follows `docs/glossary.md` (quote, theme, session, codebook/code/tag, sentiment, signal, speaker code). Only shipped features appear — nothing aspirational (no slides export, no Word export, no Focus Mode).

---

## 0. Not yet built

Spec'd here, absent from `WelcomeHomeView.swift` — do not read the sections below as shipped:

| Item | Where spec'd | Note |
|---|---|---|
| `Window ▸ Welcome to Bristlenose` (⌘⇧1) | §1 | No `CommandMenu` item, no shortcut. The view is reachable only by *having no project selected*. |
| "Show Welcome when Bristlenose opens" checkbox | §1 | Not in `AppearanceSettingsView`. Restore-last is unconditional today. |
| Delight cell — swimming fish | §3 Cell 5 | Placeholder link only. |
| AI cell — configured-state **rotator** | §3 Cell 4 | Configured pool exists but picks **once at construction**, at random. Not a `SlotRotator`. |
| AI cell — set-up links (`Docs`) | §3 Cell 4 | Only a single `Setup →` deep-link to Settings. |
| Delight — in-app AI-consent sheet | §3 Cell 5 | Opens the docs URL instead. |
| `aiConfigured` detection | §3 Cell 4 | Hardcoded `false` — the configured branch is unreachable at runtime. |

---

## 1. What this surface is

The macOS first-run / empty-state pane. **Not a sales pitch** — the user has already downloaded and installed. It is a *"learn something every launch"* surface: each visit teaches one study tool, one piece of science, and one tip, without a tour, wizard, account wall, or animated character.

**It is not a lens.** The lenses (Project · Sessions · Quotes · Codebook · Analysis) are views onto a *selected project*. This surface is app-level and belongs to no project.

**Entry points (as shipped):**
1. **First run**, no projects → Welcome.
2. **No project selected** (closed/deleted the selected one) → Welcome.
3. **Launch with projects → restore the last project + lens** (macOS state restoration, the Mac-library convention). Welcome is *not* the launch surface. If the last project was deleted between sessions, restore falls back to Welcome.

**One view serves all of these.** `WelcomeHomeView` takes no mode parameter — there is no `.firstRun` / `.noSelection` variant split. (An earlier draft proposed one; the content is identical in both states, so it never earned the branch. If a returning-user variant is ever wanted, that's open decision #6.)

**Planned, not built** — see §0: ⌘⇧1 (`Window ▸ Welcome to Bristlenose`, the Xcode precedent for an explicit way home) and the Appearance checkbox that would make Welcome the launch surface instead of restore-last. Deliberately *not* a sidebar "Home" target, and not click-empty-space (unreliable on macOS).

So the rotating content is seen **when you visit home** (first run / after closing the last project / new study), not literally every launch.

---

## 2. Layout & style

- **Golden ("Fibonacci") spiral, variant A** — five squares, biggest → smallest: Study tools · Scientific background · Tip · AI · Delight.
- **Spacing ladder** (`docs/design-figma-setup.md`): 4 / 8 / 16 / 24 / 32; radii 8 / 10; content margin 20. *Two deliberate departures:* the drop card uses 14pt padding (16 crowded the dashed border against the 15pt title), and the chevron/icon strips use 26/30pt — SF Symbol glyph metrics, which the ladder doesn't govern.
- **Cell tints:** each fill mixed from the palette **accent** into the card base, scaling **3 % (biggest) → 26 % (smallest)** — big spaces calm, small ones carry colour. Tracks Default + Edo, light + dark automatically. ⚠️ *Open decision:* tinting backgrounds departs from the seam-alignment discipline (natively only the accent tracks palette; surfaces stay system-semantic). Weigh before shipping.
- **Alignment:** every cell is **top-leading** — tag top-left, content flush left. No cell centres its content.
- **Colours:** from Default + Edo palettes only; accent via `.tint` (Default `#007AFF` / Edo `#0F5C9E`, dark variants free).
- **Rotation:** each rotator cell shows one item from its pool **per visit to home**, stable while viewing. Next-per-visit, not random — see §3a.
- **Geometry is fixed architecture.** The φ-spiral is exact and does **not** reflow; cells never resize to their content. It **grows as wide as the content area, keeps its φ proportions** (height = width / 1.618), and is **pinned to the top** — the space beneath is left for later. **Fonts stay at fixed semantic sizes** (no scaling); cell content aligns **top-leading**. Copy is cut to fit **editorially** (written/translated to length); overflow handling (condense-to-fit or per-locale editing) is a later pass. Never squish the architecture to fit the prose.
- **Interaction (current treatment, not a hard rule):** only the **Delight** cell is whole-card clickable. The **AI** cell's card is inert — its `Setup →` link is the sole target. The info cells use a discrete `Learn →` / `More →` link. Per-cell clickability can move around freely as it's tuned — the *only* firm requirement is that ignorable info must not *read* as a control.

---

## 3. The cells

### Cell 1 — Study tools (biggest)
- **Tag:** `Study tools`
- **Content:** one rotating capability per visit, each carrying a **concrete screenshot example** between the line and the CTA — the point is to plant the toolset in a first-time user's mind. Slot order: tag → title → line → image → CTA. Still *ignorable* and **not** a numbered rail / not navigation (an earlier segmented rail was cut for looking like primary nav).
- **Also contains:** the **Drop-a-folder** card — the one real action in this cell. Its **own** `dropCard` view using `.dropDestination(for: URL.self)`, wired to `ContentView.createProjectFromURLs` (directories and loose files split at the call site). It is *not* the sidebar's `dropTargetCard`/`.onDrop` — that one is `List`-coupled. Dotted border, background one notch lighter than the cell (paper). ⚠️ *Open decision:* drop wells traditionally read as recessed/deeper (darker + inner shadow); current treatment is lighter/raised — revisit.
  - Icon: `tray.and.arrow.down` · **Drop a folder** · "Drag a folder of recordings or transcripts here to add it as a project."

**Pool** — 8 tools, all in the Swift carousel (render order below). Illustrations are **draft PNG screenshots** (light-mode captures) while the set is tuned — each sits between the line and the CTA. Ingest + Redact PII render **text-only** until their art lands (`image` nil → no blank frame).

**Image treatment (starting guess, 19 Jul 2026):** rendered at **85% of native size** at the shot's own aspect ratio — *not* stretched to the cell width, never upscaled past 85% (shrinks only when the cell is narrower). A faint separator-colour keyline (0.5pt, radius 8) frames each — deliberately reading as *illustration, not live UX*. **8pt** (one macOS grid square) vertical padding top and bottom. `@2x` imagesets (Retina captures). All tunable in `SlotRotator.slotView`. The **CTA** column is "Learn" everywhere for now — fine-tune per tool, then update here (canonical) and in `WelcomeHomeView.swift`'s `studyTools` `linkLabel`. Image = the `Assets.xcassets` imageset name.

| # | Tool | Line | Image | CTA | Link |
|---|---|---|---|---|---|
| 1 | AutoCode | Let AutoCode propose tags across every quote — you Accept or Deny. | `welcome-autocoding` | AI helps tag | `/docs/use-codebooks.html` |
| 2 | Codebooks | Build a codebook, or start from a ready-made framework. | `welcome-codes` | Research frameworks | `/docs/use-codebooks.html` |
| 3 | Tag | Select one or more quotes, and press `t` to tag them with a code from your codebook. | `welcome-tag` | Manual tagging | `/docs/tag-for-meaning.html` |
| 4 | Star & hide | Press `s` to keep the quotes that matter, `h` to hide the rest. | `welcome-star` | Keyboard shortcuts | `/docs/keyboard-shortcuts.html` |
| 5 | Video clips | Turn selected quotes into video clips. | `welcome-clips` | Export options | `/docs/export-clips.html` |
| 6 | Send to Miro | Send quotes to a Miro board. | `welcome-miro` | Connect to Miro | `/docs/send-to-miro.html` |
| 7 | Ingest | Drop a folder of recordings or transcripts — Bristlenose transcribes, analyses and reports back. | `welcome-ingest` | Import options | `/docs/first-analysis.html` |
| 8 | Redact PII | Remove personal details automatically, before analysis. | _pending_ | Strip names and more | `/docs/redact-pii.html` |

_Set change (19 Jul 2026): Export split into **Video clips** + **Send to Miro** (separate illustrated tools). **Tag** kept, with its own screenshot. Copy reuses existing house lines (Tips pool for clips/Miro)._

_Key references follow the **text-only path** of [`design-keycaps.md`](design-keycaps.md) (chosen 19 Jul 2026): **bare keys stay lowercase** (`t` / `s` / `h`, not `T`/`S`/`H` — the unmodified-key rule) and render as a same-size **monospaced** run (markdown backtick → `welcomeKeyMarkdown` in `WelcomeHomeView.swift`), *not* a drawn keycap — a drawn cap can't flow mid-sentence in SwiftUI `Text`. When the shared `Keycap` primitive graduates out of `#if DEBUG` (keycaps §Implementation-plan step 3), revisit whether these want real caps._

### Cell 2 — Scientific background (2nd)
- **Tag:** `Scientific background`
- **Content:** one rotating piece of the intellectual grounding. `Learn →`
- **Honesty rule:** attach a citation only where the docs actually claim one. **"Signal" is Bristlenose-coined — never academicise it.**

**Pool** — *shipped subset: 5 of 6* (Dignity is spec-only):

| Card | Line | Link | Shipped |
|---|---|---|---|
| Emergent themes | Themes emerge from participants' own words, not a fixed taxonomy — inductive thematic analysis (Braun & Clarke, 2006). | `/docs/research-foundations.html` | ✅ |
| Don Norman | The codebook frameworks draw on Don Norman's principles of human-centred design. | `/docs/codebook-frameworks.html` | ✅ |
| Jakob Nielsen | The UX codebooks build on Nielsen's usability heuristics. | `/docs/codebook-frameworks.html` | ✅ |
| Seven sentiments | Seven sentiments, grounded in appraisal theory (Scherer) and core affect (Russell). | `/docs/signals.html` | ✅ |
| Signals | A signal marks where sentiment or tags concentrate more than you'd expect — a measure we coined. | `/docs/signals.html` | ✅ |
| Dignity without distortion | Quotes are tidied but never twisted; the participant's voice is honoured. | `/docs/research-foundations.html` | — |

The two framework cards point at **`/docs/codebook-frameworks.html`** (the framework explainers), not `research-foundations.html` — the reader wants the frameworks themselves, not the methodology essay.

*Candidates (from `academic-sources.html`, add if wanted):* peak-end rule (Kahneman), working-memory limits (Miller), think-aloud as data (Ericsson & Simon).

#### Cell 2 illustrations (built — 19 Jul 2026)

Each science slot carries a tiny looping illustration in the example area (between the line and `Learn →`), one per concept. `SlotItem.illustration: ScienceIllustration` selects it; `slotView` renders it at a **fixed height** so the φ-geometry never reflows; only the current rotator slot is alive, so a webview/animation exists only while shown. All are decorative (`accessibilityHidden`, inert), reduce-motion aware. Impl: `WelcomeIllustrations.swift`. Reference spec: `docs/mockups/welcome-science-animations.html`.

| Slot | Illustration | Build |
|---|---|---|
| Seven sentiments | Left-hinged fan of the 7 sentiment chips (SF Mono + sentiment colour tokens) opening with rotation + vertical spread — every word readable, only just overlapping | **native** (`SentimentFanView`) |
| Don Norman / Jakob Nielsen | One fan of framework book covers, overlap + slide, no rotation (typographic placeholders pending cover art) | **native** (`BookFanView`) |
| Signals | The real analysis signal card — histogram, four metrics + tooltips, pattern label — ticking through example signals with a split-flap flip | **webview** (`SignalIllustrationView`) |
| Dignity without distortion | Verbatim quote → strike the filler → collapse to the tidy quote → restore | **webview** (`QuoteIllustrationView`) |
| Emergent themes | Demo quote-fragments swirl as one flock → swoop into two labelled themes → rejoin | **webview** (`EmergentThemesView`) |

**Native vs webview split (decided with Martin, TF-play).** Native where cheap and clean (fan, books). Webview where reusing the approved mockup verbatim beats re-deriving feel, or where the artefact is a real web component: the signal card **is** the shipped React/CSS card (rebuilding natively would fork a second source of truth vs `AnalysisPage.tsx`); the dignity quote + emergent-themes swoop were "perfect" in the mockup, so we reuse them rather than risk the feel. The **real `ShoalView` (boids) is deliberately NOT used here** — it's the delight/analysing screensaver: it wants a big canvas and is for-fun, whereas a make-a-point cell needs the simple two-theme swoop.

**Webview mechanics.** `IllustrationWebView` (`NSViewRepresentable`): `loadHTMLString` (no external resources — sandbox-clean; system font, slight rendering differences accepted), transparent via `setValue(false, forKey:"drawsBackground")`, `.allowsHitTesting(false)`, reloads on appearance/palette/reduce-motion change (keyed `.id`). The signal card renders at a fixed natural width and is uniformly transform-scaled to fit (max 90%, like the tools-cell images) — a fixed-width **flex item's `min-width:auto` inflated it to min-content and reflowed**, so it's absolute-positioned + transform-scaled instead.

**Open items ("many things to improve", 19 Jul — none blocking, TF-play state):** signal-card cell-height crowding (trimmed 2-metric variant candidate); split-flap glitch on the last char mid-flip; per-illustration timing/size tuning; emergent-themes word set; book cover art (copyright TBD); whether these should also render on the docs pages (would tilt the split further toward web).

### Cell 3 — Tip (3rd)
- **Tag:** `Tip` (top-left). **No icon** — a lightbulb was built and cut (cheesy).
- **Content:** one rotating practical tip. `More →`

**Pool** — *shipped subset: 5 of 12*:

| Tip | Link | Shipped |
|---|---|---|
| Already have transcripts? Drop `.vtt`, `.srt` or `.docx` — transcription is skipped. | `/docs/supported-files.html` | ✅ |
| No API key? Run Ollama locally — free, no account, nothing uploaded. | `/docs/set-up-ollama.html` | ✅ |
| Name `p1.srt` next to `p1.mp4` and they merge into one session. | `/docs/supported-files.html` | ✅ |
| Click any transcript timecode to jump the video to that moment. | `/docs/run-an-analysis.html` | ✅ |
| Export a self-contained HTML report anyone can open — optionally anonymised. | `/docs/share-report.html` | ✅ |
| Press `s` to star, `h` to hide — then filter to what matters. | `/docs/keyboard-shortcuts.html` | — |
| Turn selected quotes into video clips. | `/docs/export-clips.html` | — |
| Send quotes to a Miro board. | `/docs/send-to-miro.html` | — |
| Export quotes to a spreadsheet. | `/docs/export-quotes.html` | — |
| Bristlenose covers 16 formats — Zoom, Teams and Meet transcripts included. | `/docs/supported-files.html` | — |
| Switch AI provider or model anytime in Settings. | `/docs/configuration.html` | — |
| The Analysis tab shows where sentiment concentrates. | `/docs/signals.html` | — |

### Cell 4 — AI (4th, stateful)
- **Tag:** `AI`
- **Unconfigured (the only reachable state today):** a subdued icon that gently cross-fades through SF Symbols (~20 s cycle), then a single **`Setup →`** link that deep-links to Settings ▸ LLM (via `@AppStorage("settingsSelectedTab")` + `SettingsLink`).
  - ⚠️ *Open decision — what the icon cycles through.* Shipped provisionally as tasteful SF Symbols (`sparkles`, `brain`, `cpu`, `bolt`, `cloud`) that *suggest* "the AIs" without real provider logos (trademark). Alternative still open: monogram marks.
- **Configured:** repurposes into model education. **Not built as a rotator** — `aiConfigured` is hardcoded `false`, and the pool below picks once at random on construction rather than stepping per-visit. Making it a `SlotRotator` (per §3a) is the intended shape.

**Configured pool** (unreachable at runtime — see §0):

| Card | Line | Link |
|---|---|---|
| About local models | Ollama runs entirely on your Mac — no account, nothing uploaded. | `/docs/set-up-ollama.html` |
| Switch anytime | Change provider or model whenever you like, in Settings. | `/docs/configuration.html` |
| Local or cloud | Local models are free; cloud models are faster and sharper. | `/docs/cloud-or-local.html` |

**Set-up links** (spec — not built; the cell has no `Docs` link): `/docs/set-up-claude.html` · `set-up-chatgpt` · `set-up-gemini` · `set-up-azure` · `set-up-ollama` · chooser `/docs/cloud-or-local.html`.

### Cell 5 — Delight (smallest, bottom-right)
- **Intended:** a single, gently **swimming fish** — the bristlenose namesake. Quiet, tasteful, no mascot/guide. Later it could react to real activity (a finishing run disturbs it).
- **Interim placeholder (shipped):** a whole-card-clickable **Review AI & privacy settings…** link that opens `/docs/privacy.html` in the browser. *In-app it should re-open the AI consent sheet* — not wired (§0).
- **Candidates considered:** murmuration/shoal (on-brand with existing motion language, could react to activity); lone fish (chosen direction); rotating aphorism (safe, inert).

---

## 3a. Rotator cells (manual carousels)

Study tools · Scientific background · Tip are **rotator cells** — a manual, in-place content carousel (`SlotRotator` in `WelcomeHomeView.swift`). All three are rolled out (proven first on Study tools, then a one-line drop-in for Science and Tip; each has its own `storageKey`).

- **Content cross-fades in the same frame** — no card slide, so no edge-peek problem. Reduce-motion → instant swap. **Wraps around** (past-last → first): seamless *because* it cross-fades — a wrap on a sliding carousel teleports, a cross-fade wrap is invisible. Chevrons never dim at the ends.
- **No auto-advance.** (The "carousels are bad UX" critique is aimed at auto-rotation; a manual deck of 3–7 with hover controls is exactly the case it doesn't condemn — see the carousel research pass.)
- **Four drivers:** two-finger / Magic-Mouse horizontal **swipe** (discrete, one step per gesture — `SwipeCatcher` NSView `scrollWheel`); **hover-revealed edge chevrons** (tiny SF Symbol on a `.regularMaterial` glass disk — survives content underneath; hover-only, *not* focus-driven — focus-reveal caused a stuck-always-on bug since focus persists; keyboard uses arrow keys instead); **arrow keys**; and **dots** (indicator-first — small, muted, active ~2× width, 17pt hit-slop; *not* the primary click target — the tiny visible dot is a nightmare to hit, so swipe/chevrons/arrows are the real navigation. Could hover-reveal with the chevrons later — one line, tie dot opacity to `revealed`).
  - **The chevron TAP TARGET is the disk band, not the full strip (fixed 19 Jul 2026).** The strip stays full-height for *positioning* (so the disk bottom-aligns to the dots line) but is `.allowsHitTesting(revealed)` and only the disk's `controlRow`-tall band takes the tap. A full-height, always-live leading strip sat directly on top of the leading-aligned `Learn →` link and **stole its clicks** (ran "previous" instead of opening the URL). So: tap area = disk only, and the strip is inert unless the pointer is over the cell. Trade-off accepted: the chevron is no longer a "tall forgiving strip" (swipe/arrows/dots cover forgiveness); working content links win.
- **All nav chrome sits on one line at the bottom.** The chevron disks are *bottom-aligned* within their strips so their centres land on the dots' centre line — the two share the `SlotRotator.controlRow` constant (26pt = disk diameter = dots-row height; equal **by construction**, and the alignment breaks if one moves without the other). Earlier the disks centred on the *content* box, i.e. directly over the body text they had to compete with; the strip stays full-height and forgiving, only the visible disk moved down. Consequence: the dots row is 26pt tall, not 17 — the dots keep their 17pt hit-slop and just centre inside it.
- **Next-per-visit:** opens one step past where you last left off (`@AppStorage` per cell) — not random (random reads as a slot machine).
- **VoiceOver:** an `.accessibilityAdjustableAction` (the cell has no selection/focus model and doesn't need one — VO swipe-up/down = prev/next).
- Active-dot colour = muted accent (`accentColor.opacity(0.6)`) — tunable (muted-grey is the calmer alternative).
- Playground: `docs/mockups/welcome-carousel-playground.html`.

**The AI cell is not a rotator** — see §3 Cell 4 and §0.

## 4. Provider naming (glossary)
User-facing: **Claude · ChatGPT · Azure OpenAI · Gemini · Ollama** (local). Never the company name. Local = "Ollama" (tool) / "local models" (mode). AutoCode is cloud-only (not Ollama).

## 5. Open decisions
1. **Delight cell** — build the swimming fish (bristlenose); shoal is the fallback.
2. **Morphing icon set** — SF Symbols (shipped provisionally) vs monogram marks. *Shipping the provisional pick doesn't close this.*
3. **Cell tints** — accept the departure from seam-alignment discipline, or keep surfaces system-semantic and tint only accents. *Shipped as tinted while undecided — the code is the straw man, not the verdict.*
4. **Drop well depth** — lighter/raised (current) vs recessed/deeper (traditional; darker + inner shadow).
5. **Science copy length** — two-pillar (themes + UX heuristics) vs fuller (adds sentiment/signal).
6. **Returning-user New-project affordance** — keep Drop-a-folder, or soften it for the no-selection case. *Would need a mode parameter on `WelcomeHomeView`, which today has none (§1).*
7. ~~Panel size vs type floor~~ — **resolved:** fixed geometry, full-width + φ, pinned top, fixed fonts (§2). No scaling, no per-cell floor. Space-below and overflow handled later.

## 6. Type ladder (Swift mapping)

**Rule:** semantic text styles only — no custom sizes (`design-figma-setup.md:167`, `design-native-typography-grid.md:137`). `.system(size:)` is for SF Symbol glyphs only. Floor is caption2 ≈ 10pt.

Sizes are **one notch up from the floor** (the floor version felt small in the mockup).

| Element | Swift style | macOS pt |
|---|---|---|
| Cell tag (uppercase) | `.subheadline` | 11 |
| Cell title (`.t`) | `.title3` (semibold) | 15 |
| Body line (study tools / science) | `.body` | 13 |
| Tip body | `.body` | 13 |
| Drop-a-folder title | `.title3` | 15 |
| Drop-a-folder subtitle | `.body` | 13 |
| Rotator links (`Learn →` / `More →`) | `.callout` | 12 |
| Delight link (privacy) | `.body` | 13 |
| AI label / `Setup →` | `.callout` | 12 |
| Chevron glyph | `.system(size: 11, weight: .semibold)` | — |
| Drop / AI icons (SF Symbols) | `.system(size:…, weight:.light)` | — |

All choices are sanctioned semantic styles — no custom sizes.

## 7. References
- Mockups: `docs/mockups/welcome-fibonacci-rotating.html` (canonical), `welcome-fibonacci-composed.html`, `welcome-fibonacci-refine.html`, `welcome-fibonacci-variants.html`, `welcome-layout-experiments.html`, `welcome-carousel-playground.html`.
- Swift: `desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift`. Mounted from `ContentView.swift`'s empty-state branch.
- Live docs: `https://bristlenose.app/docs/`.
- Grounding: `docs/glossary.md`, `docs/design-research-methodology.md`, `docs/design-figma-setup.md`, `docs/design-native-colour-alignment.md`.
- **Superseded and deleted (`a310bca6`, 15 Jul 2026):** `WelcomeView.swift` — the previous empty-state pane (card + lifecycle rail, `.firstRun` / `.noSelection` variants). It had gone orphaned: no Swift references, no `pbxproj` entry — but the target's `PBXFileSystemSynchronizedRootGroup` kept auto-compiling it into the binary, so it was dead weight rather than merely dead source. Its locale keys were **kept** — see §Copy & i18n.
