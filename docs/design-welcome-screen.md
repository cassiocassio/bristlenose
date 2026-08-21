---
status: partial
last-trued: 2026-08-20
trued-against: uncommitted working tree @main on 2026-08-20
---

# Welcome screen — content & design source

## Changelog

- _2026-08-20_ — **The shelf stopped scaling its own prose, and key references became real keycaps.** Two rules this doc already asserted turned out to be asserted-but-not-enforced, and both are now true in code. (1) **§2's "fonts stay at fixed semantic sizes"** was false in `BookShelfView`, which wrapped caption, fan and link in one `scaleEffect`: at the 700pt minimum window the scale reaches **0.29**, rendering `.title3` smaller than the *unscaled* `.subheadline` cell tag beside it — the type hierarchy inverted, and the shipping default window (1000pt, sidebar out) already sat at 0.75, so it had never once rendered at its intended size. The scale is now scoped to the cover fan alone and applies on **both axes** — the fan is 208pt wide at four covers against a ~165pt cell at minimum window, so a height-only scale drops the fourth cover off the edge; the old whole-shelf scale had been hiding that by shrinking the fan horizontally too. The fan's box carries the fan's natural ratio (`aspectRatio(208/152, .fit)`) because `scaleEffect` is a *drawing* transform that never changes the reserved frame: when width was binding the two disagreed, and the covers spilled over the Learn-more link while the unused reserve read as a gap. The caption bends by losing **words** instead — `ViewThatFits` over full line → clause cut → ellipsis, via the new `WelcomeClauseFit` (em dash / en dash / semicolon only, outermost-first, refusing head-final scripts, short stumps and orphaned brackets). Same pass: `slotView`'s illustration frame moved `.leading` → `.topLeading`, since `.leading` centres *vertically* and that was invisible only while every illustration filled its box. (2) **Key references are now drawn caps** — Skin A · Flat, in every slot pool, via one shared `welcomeKeyText` helper. They need an explicit **baseline correction** (`baselineOffset(-5.19)` at `fontSize` 11, derived from `NSFont` metrics, not eyeballed): `Text` puts an interpolated image's *bottom edge* on the text baseline, so an uncorrected cap floats above the line. See §Cell 1's key-reference note and keycaps §3 decision 3. Decided the same day and tracked separately: the copy itself gets rewritten inverted-pyramid so a clause cut is safe by construction, across all 45 slots. Experiment record for all of it — four strategies, a stress corpus, and the measurements quoted here — is **Diagnostics ▸ Degradation Lab** (`WelcomeDegradationLab.swift`, DEBUG), kept deliberately as-is so the rejected alternatives stay legible.
- _2026-08-14_ — **All illustration animation moved onto one tempo — 60% speed, 3-second rests (the set played too "look at me").** `WelcomeTempo` (`WelcomeBaton.swift`) is the single knob set: group `speed = 0.6` (every authored duration stretches by 1/speed), a per-illustration `pace(_:)` local multiplier on top (the five tool webviews keep the ×1.3 they were hand-tuned to, so their effective stretch is ×2.17), and two absolute holds — `leadInSeconds = 3` resting on the opening frame before any motion, `holdEndSeconds = 3` resting on the finished frame before looping or handing the baton on. Plumbing: webview scripts interpolate `PACE`/`LEAD` (their shared `sleep()` now scales, `nap` is an alias; kickoffs are `setTimeout(run, LEAD)` — Reduce Motion still stills instantly), natives route beats through `stretch(for:)`/`nap(_:)`, and `welcomeTurn` **derives** from the same numbers (base play length × stretch + both holds), so turn lengths track any tweak. Micro-transitions (fades, presses, the caret, flap-unflip) deliberately stay at their authored speeds — the cadence between beats is what calms; slowing a 250ms fade just reads as lag.
- _2026-08-14_ — **§Cell 1: the last three PNG screenshots are drawn, completing the 2 Aug "no screenshots long-term" decision — and the illustration left edge is now flush with the cell's type.** **Ingest** (`.ingest`, native SwiftUI): one example of every kind of file or folder Bristlenose imports — SF Symbols for the icons, SF Pro for the names, each name **surtitled** with its kind + the formats that path ingests (the four decode paths of `classify_file` + the folder shapes); icons **blink** in, names **type** out. **Video clips** (`.clips`, native SwiftUI): the real Export-menu row ("Extract Video Clips…" / "Trimmed clip per quote", film icon) clicked by a pointer — with the macOS highlight flash — then three clips land one at a time, fake thumbnail first, filename assembling **one logical unit per beat** (participant · timecode · snippet · .mp4); pause, loop back to the menu. **Send to Miro** (`.miro`, webview): just the stickies, no board chrome — the famous pink + two yellows sampled from a real capture, the exact caption text with **hand-set `<br>` wrapping** (the sameness is the trick), Inter-led stack (Miro's face isn't freely licensable), Miro's soft shadow, appearing in order. The `image:` PNG mechanism and the three imagesets are **deleted** — `SlotItem` no longer has an image field. Same pass: **`.agentChat` re-authored full-width** (normal flow, left origin — was absolutely-centred at scale ≤0.9) with type up a notch (11.5 → 12.5px). **Alignment rule this settles (§2 corollary):** the Swift frame owns the cell inset (16pt content margin + 8pt vertical); illustration content starts at x = 0 — no second, illustration-side padding. New pieces comply; `.autocode`/`.manualTags` (12px body pad), `.tag`/`.starHide` (14px, gutter load-bearing for the pointer arc) and the centre-scaled `.signal` still owe the same pass.
- _2026-08-14_ — **§2 Cell tints: working candidate picked in the new gradient playground.** `docs/mockups/welcome-gradient-playground.html` explores gradient-across-cells variants (strength ramps, hue walks, other mechanisms) with three global layers: **Reverse** (flips any ramp), **Glow** (radial accent wash on the pane behind the spiral) and **Glass** (cell translucency). Current pick, wired as the playground's defaults: **Whisper reversed** — accent 11·8·6·4·2 % (colour on the stage, quiet eye) — over glow 11 % anchored at the stage corner, cells at 72 % opacity for a slight glassiness. Open decision #3 stays open but now has a candidate — **ported to Swift the same day behind `BristlenoseWelcomeTintCandidate`** (off by default; v1 3→26 % still ships). **Future tint experiments go in that playground, not new one-off mockups.**
- _2026-08-02_ — **§Cell 1 pool trued to the shipped carousel, and two decisions recorded.** The table had drifted a long way: it listed 8 tools all carrying PNGs, with pre-fine-tune CTAs and one link each. Reality is **8 live slots** — five drawn illustrations (`.autocode`, `.manualTags`, `.tag`, `.starHide`, `.agentChat`), three remaining PNGs, per-tool CTAs, and a **two-CTA** Codebooks slot (`linkLabel2`/`href2`). **Connect an AI agent** (added 1 Aug with the MCP extension) was missing entirely. Decisions: (1) **no screenshots long-term** — the three remaining convert to themed Swift or webviews; (2) **Redact PII withheld** from the desktop pool because the `.app` cannot run it (Presidio + spaCy excluded from the sidecar; CLI-only flag; no desktop control) — commented out verbatim in `studyTools` as the reference copy. Also: the `ScienceIllustration` enum was renamed **`WelcomeIllustration`** (it stopped being science-only five cases ago) and its `.shoal` case renamed **`.emergentThemes`** (it renders `EmergentThemesView`, *not* the real `ShoalView` — the old name asserted the opposite of the §Cell 2 decision). Four superseded imagesets deleted.
- _2026-07-25_ — **Re-open entry SHIPPED — as Help ▸ Welcome, not Window ⌘⇧1.** The explicit way home moved out of §0 "Not yet built": it's a **Help menu** item ("Welcome to Bristlenose"), **no keyboard shortcut** (rare, unmemorable destination; discoverability comes from living in Help). Clears the project selection (`selection = []`), same effect as the empty-space deselect that already existed (`SidebarDeselectMonitor`). Corrects the prior spec on two counts: (1) it's under **Help**, not Window/⌘⇧1 (the ⌘⇧1/Window "Xcode precedent" was weighed and rejected — Welcome isn't a window or a file, it's semantically help; superseded rationale preserved in §1); (2) the claim "not click-empty-space (unreliable on macOS)" was already false — empty-space deselection ships and the Help item reuses it. §0 row 2 (launch-surface checkbox) and all other §0 rows remain accurate. Also relevant: the View-menu sidebar toggle became dynamic **Hide/Show Projects** — catalogued in `design-desktop-menu-actions.md`, not here.
- _2026-07-19_ — **Study-tools cell gained per-tool illustrations.** Cell 1 is now an 8-tool pool (AutoCode · Codebooks · Tag · Star & hide · Video clips · Send to Miro · Ingest · Redact PII — Export split into clips + Miro), each slot showing a **draft PNG screenshot** between the line and the CTA (85% native, own aspect, faint keyline, 8pt padding, `@2x` imagesets; text-only fallback via `NSImage(named:)` nil-guard). Redact PII art still pending. Per-tool CTA labels replace "Learn". Key references adopt the **text-only path** of `design-keycaps.md` (lowercase bare `t`/`s`/`h` in a mono run). Body line `.callout`→`.body` (13pt). Fixed a pre-existing bug where the chevron hit-strip shadowed the CTA links. i18n still held; draft-art + i18n tracked as an in-flight debt.
- _2026-07-15 (second pass)_ — `§7` supersession line trued: `WelcomeView.swift` is **deleted** (`a310bca6`), not "kept on disk pending a delete decision". Recorded the locale-key retention decision under §Copy & i18n — the retired view's keys are deliberately kept, and three are verbatim-live in `WelcomeHomeView`. Anchors: `WelcomeHomeView.swift:157,189,190`; `ContentView.swift:2340` (mount). Rest of the doc spot-checked fresh (Archetype B).

> **Truing note (2026-07-15).** Authored alongside the Swift build in the same session, and the code moved under it several times. This pass separates **shipped** from **spec**. The content pools are deliberately spec-ahead-of-code (the doc is the source; the Swift carries a subset) — those are marked *shipped subset: N of M*. Everything else now describes what exists. See **§0 Not yet built**.

**Status:** design in flight. Mockups in `docs/mockups/welcome-*.html`; Swift in `desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift`. Single source of truth for the cells and their content.

**Copy & i18n:** copy is hand-tuned **English** while the layout iterates — **do not add locale keys or wire i18n yet.** The localisation pass (German et al., which will stress the fixed geometry — expected, and handled *then* by editorial fit + condense-to-fit) is deliberately deferred to *much* later, post-iteration. No rush.

**The retired view's locale keys are kept on purpose — do not sweep them as orphans.** `desktop.welcome.*` and `desktop.chrome.{welcomeTitle,noProjectSelected,selectProject}` survive in the 21 full locales (22 directories counting the `zh-Hant-HK` override fork — this said 20 until 21 Aug 2026; Catalan landed 14 Aug) even though `WelcomeView.swift` is gone (`zh-Hant-HK` carries only its genuine `welcome.subtitle` override and inherits the rest, per the override-fork rule). Two reasons: they are already-translated raw material for the deferred localisation pass above, and three of them are **verbatim-live copy today** — `welcome.dropFolderTitle` ≡ "Drop a folder" (`WelcomeHomeView.swift:189`), `welcome.dropFolderHint` (`:190`), `welcome.aiPrivacyLink` (`:157`). A grep for unreferenced keys will flag all of them; that grep is wrong here. (`chrome.emptyStateHint` is separately live — sidebar chrome, `ContentView.swift:1810`.)

British spelling. Terminology follows `docs/glossary.md` (quote, theme, session, codebook/code/tag, sentiment, signal, speaker code). Only shipped features appear — nothing aspirational (no slides export, no Word export, no Focus Mode).

---

## 0. Not yet built

Spec'd here, absent from `WelcomeHomeView.swift` — do not read the sections below as shipped:

| Item | Where spec'd | Note |
|---|---|---|
| "Show Welcome when Bristlenose opens" checkbox | §1 | Still absent from `AppearanceSettingsView` (verified 21 Aug 2026). But "restore-last is unconditional" is stale: since `292c96da` a window opens on a study only if its seed names one, so **Welcome-on-launch** is what is unconditional. |
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
3. ~~**Launch with projects → restore the last project + lens** (macOS state restoration, the Mac-library convention). Welcome is *not* the launch surface. If the last project was deleted between sessions, restore falls back to Welcome.~~

   > **Reversed 20 Aug 2026 (`292c96da`) — Welcome *is* the launch surface now,
   > and this entry was still saying the opposite when the doc was last edited
   > the same afternoon.** A window opens on a study **only if its seed names
   > one** (`ContentView.swift:700-719`). There is deliberately no last-used
   > fallback: it was tried and removed, because it made ⌥⌘N from a Welcome
   > window open a study, and because it conjured a sidecar on a study the
   > researcher had not chosen. So a genuine restore still comes back on its own
   > study — each window on the study it wrote back, not five copies of the last
   > selected — but **launch with nothing to restore, and a Dock reopen, land on
   > Welcome.**
4. **Help ▸ Welcome to Bristlenose** — the explicit, re-openable way home once projects exist (no keyboard shortcut). Clears the project selection (`selection = []`), landing on state 2.
5. **Click the sidebar's empty space** — `SidebarDeselectMonitor` clears the selection, same as (4). The Help item is its discoverable, labelled twin (a click can't advertise itself).

**One view serves all of these.** `WelcomeHomeView` takes no mode parameter — there is no `.firstRun` / `.noSelection` variant split. (An earlier draft proposed one; the content is identical in both states, so it never earned the branch. If a returning-user variant is ever wanted, that's open decision #6.)

**Menu placement — Help, not Window (decided 2026-07-25).** The re-open entry lives under **Help** with no shortcut. It is deliberately *not* a sidebar "Home" target (that reads as primary nav for a surface belonging to no project). _Superseded baseline:_ an earlier spec proposed `Window ▸ Welcome to Bristlenose` (⌘⇧1), citing the Xcode precedent. That was weighed and rejected — Welcome is neither a window nor a file; it's semantically *help*, so Help is the honest home. The keyboard shortcut was dropped as unmemorable (discoverability comes from living in Help). This matches the prior-art consensus — an empty-state affordance for the primary action plus a re-openable menu item as the optional layered supplement, never a blocking onboarding wizard (NN/g, Apple HIG, IBM Carbon; the Xcode/VS Code/Omniverse re-open pattern). The prior "not click-empty-space (unreliable on macOS)" note is retired: empty-space deselection ships (entry point 5) and the Help item reuses it.

**Still planned, not built** — see §0: the Appearance checkbox. Note what it is
*for* changed on 20 Aug: Welcome is already the launch surface for a window with
no seeded study, so the checkbox is no longer the thing that would make it one.
What remains unbuilt is the **user's control over it** — today the behaviour is
unconditional in both directions.

So the rotating content is seen **when you visit home** (first run / after closing the last project / new study), not literally every launch.

---

## 2. Layout & style

- **Golden ("Fibonacci") spiral, variant A** — five squares, biggest → smallest: Study tools · Scientific background · Tip · AI · Delight.
- **Spacing ladder** (`docs/design-figma-setup.md`): 4 / 8 / 16 / 24 / 32; radii 8 / 10; content margin 20. *Two deliberate departures:* the drop card uses 14pt padding (16 crowded the dashed border against the 15pt title), and the chevron/icon strips use 26/30pt — SF Symbol glyph metrics, which the ladder doesn't govern.
- **Cell tints:** each fill mixed from the palette **accent** into the card base, scaling **3 % (biggest) → 26 % (smallest)** — big spaces calm, small ones carry colour. Tracks Default + Edo, light + dark automatically. ⚠️ *Open decision:* tinting backgrounds departs from the seam-alignment discipline (natively only the accent tracks palette; surfaces stay system-semantic). Weigh before shipping. **Working candidate (14 Aug 2026, built behind a flag — off by default):** reverse the ramp and halve the volume — accent **11·8·6·4·2 %**, colour on the stage, quiet eye — over a pane-level radial **glow** (accent 11 % into paper, anchored at the stage corner) with cells at **72 % opacity** so they pick the wash up (slight glassiness). Ported the same day: `WelcomeCellTint` carries both ramps (pinned by `WelcomeCellTintTests`), `WelcomeGlow` renders the pane wash, glass lives in `WelcomeCellStyle`, and Reduce Transparency keeps cells opaque. Flip `BristlenoseWelcomeTintCandidate` (documented in `BristlenoseFlags.swift`) via `defaults write` — live, no relaunch — or per-run in Xcode with launch argument `-BristlenoseWelcomeTintCandidate YES`. Tuned in `docs/mockups/welcome-gradient-playground.html`, whose defaults *are* this candidate — take future gradient experiments there. **Removed from the app 20 Aug 2026 (Martin):** the two *global* layers — the pane-level radial glow (`WelcomeGlow`) and the 72 % cell glass (`WelcomeTintExperiment.cellAlpha`) — are gone from `WelcomeHomeView.swift`, and cells are opaque again so a cell's tint reads as its own colour rather than as 72 % of it over a wash. The **ramp** survives unchanged behind `BristlenoseWelcomeTintCandidate` — that is still the open decision. Glow and glass now live *only* in the playground, which is where the tinkering belongs; `WelcomeCellTintTests` lost the two expectations that pinned their values and keeps the three that pin the ramps.
- **Alignment:** every cell is **top-leading** — tag top-left, content flush left. No cell centres its content.
- **Colours:** from Default + Edo palettes only; accent via `.tint` (Default `#007AFF` / Edo `#0F5C9E`, dark variants free).
- **Rotation:** each rotator cell shows one item from its pool **per visit to home**, stable while viewing. Next-per-visit, not random — see §3a.
- **Geometry is fixed architecture.** The φ-spiral is exact and does **not** reflow; cells never resize to their content. It **grows as wide as the content area, keeps its φ proportions** (height = width / 1.618), and is **pinned to the top** — the space beneath is left for later. **Fonts stay at fixed semantic sizes** (no scaling); cell content aligns **top-leading**. _Asserted here since the first build, but not actually enforced until 20 Aug 2026 — `BookShelfView` scaled its own caption and link along with its covers, reaching 0.29 at the minimum window. If you are adding an illustration that carries real prose, the scale belongs on the un-reflowable furniture only._ Copy is cut to fit **editorially** (written/translated to length); overflow handling (condense-to-fit or per-locale editing) is a later pass. Never squish the architecture to fit the prose.
- **The study-tools cell is a SQUARE, and it scales with the viewport.** Worth stating because it isn't obvious from "φ-spiral": the spiral is framed `width: w, height: w / 1.618` (`WelcomeHomeView.swift:207`) and `GoldenSplit(.horizontal)` hands the major cell `width: (w − 8) × 0.618`, while its height is the spiral's full height, `0.618w`. Both ≈ `0.618w`, so the cell is square to within the gutter's ~5pt share and **both dimensions grow linearly with window width**.
- **Full-bleed slot — DECIDED 2 Aug 2026, not yet built.** The illustration should share the *cell's* content edge (**16pt left, 16pt right** — the `welcomeCell(large:)` padding the `STUDY TOOLS` tag already sits on), run full width, stay **leading** so slack opens on the **right** at any max width, and grow **downwards to fill the depth it is given** ("as deep as makes"), so the CTA lands at the bottom of the slot instead of floating mid-cell. Four load-bearing details:
  1. **This is the geometry rule working, not breaking.** The cell stays the same fixed square; only the content inside it bends. Today the *content* is the fixed thing (per-kind caps of 160–190pt) and the cell carries dead air — the rule inverted. The caps encode one assumed cell size (~400pt, the size they were tuned at), so the emptiness **grows with the display**: an illustration fills ~46% of its available depth at a 600pt cell and ~28% at 850pt.
  2. **The CTA bottoms out ABOVE the 26pt nav row, not on the cell's true bottom edge.** A bottom-pinned *leading* CTA would land in the leading chevron disk's hit band and resurrect a bug already fixed once (25 Jul 2026 — the full-height chevron strip was stealing clicks from the leading `Learn →`; the fix scoped the tap to the disk band, commented *"clear of the link above"* at `WelcomeHomeView.swift:685`). Stopping above the nav row preserves exactly that clearance and needs no change to the chevrons.
  3. **The Drop-a-folder card is a fixture, not a tenant to evict.** It rules off the square and is the final implicit CTA. So "bottom of the cell" means bottom of the *slot's* content area — above the nav row and above the drop card.
  4. **Relaxing the frame alone changes nothing on screen.** The four flow webviews are `body{display:flex; align-items:center}` and the two scaled ones clamp at `Math.min(0.9, …)`, so a taller box buys *air*, never content. Each illustration must be re-authored to stretch — and because the furniture is a near-constant ~210–230pt of depth, the illustration's box swings from roughly **2.2:1 (a wide letterbox) at a 400pt cell to 1.4:1 (near-square) at 850pt**. That swing is the design brief, and it's why *growing by quantity* (more cards) beats *scaling one composition*, which can only be right at one aspect. Prototype: the **⌗ Full-bleed slot** section of `docs/mockups/welcome-studytools-animations.html`, which measures its box and stops when the next card won't fit.
- **Interaction (current treatment, not a hard rule):** only the **Delight** cell is whole-card clickable. The **AI** cell's card is inert — its `Setup →` link is the sole target. The info cells use a discrete `Learn →` / `More →` link. Per-cell clickability can move around freely as it's tuned — the *only* firm requirement is that ignorable info must not *read* as a control.

---

## 3. The cells

### Cell 1 — Study tools (biggest)
- **Tag:** `Study tools`
- **Content:** one rotating capability per visit, each carrying a **concrete example** between the line and the CTA — the point is to plant the toolset in a first-time user's mind. Slot order: tag → title → line → illustration → CTA. Still *ignorable* and **not** a numbered rail / not navigation (an earlier segmented rail was cut for looking like primary nav).
- **Also contains:** the **Drop-a-folder** card — the one real action in this cell. Its **own** `dropCard` view using `.dropDestination(for: URL.self)`, wired to `ContentView.createProjectFromURLs` (directories and loose files split at the call site). It is *not* the sidebar's `dropTargetCard`/`.onDrop` — that one is `List`-coupled. Dotted border, background one notch lighter than the cell (paper). ⚠️ *Open decision:* drop wells traditionally read as recessed/deeper (darker + inner shadow); current treatment is lighter/raised — revisit.
  - Icon: `tray.and.arrow.down` · **Drop a folder** · "Drag a folder of recordings or transcripts here to add it as a project."

**Pool** — **8 live slots** in the Swift carousel (render order below), every one carrying a real drawn looping illustration (`illustration:` → `WelcomeIllustration`, built in `WelcomeIllustrations.swift`). The draft-PNG era is over (last three converted 14 Aug 2026; the `image:` field is gone from `SlotItem`). A ninth slot, **Redact PII**, is **withheld** — see below the table.

**Illustration treatment:** each takes a per-kind natural height as a *cap* (`illustrationNaturalHeight`) and self-scales below it, so the φ-geometry never reflows. **One exception, and it is the rule not the anomaly:** `.books` carries real prose, so only its cover fan scales — see §Books shelf. Any future illustration carrying prose does the same. Content starts at **x = 0** — the Swift frame owns the cell inset (16pt content margin, 8pt vertical rhythm); an illustration adds no horizontal padding of its own (14 Aug 2026 rule; the four older webviews still owe this pass). CTA labels are per-tool and this table is canonical for them — keep it in step with `WelcomeHomeView.swift`'s `studyTools` `linkLabel`.

| # | Tool | Line | Illustration / image | CTA | Link |
|---|---|---|---|---|---|
| 1 | AutoCode | Let AutoCode propose tags across every quote — you Accept or Deny. | `.autocode` ✅ | AI helps tag → | `/docs/use-codebooks.html` |
| 2 | Codebooks | Build a codebook, or start from a ready-made framework. | `.manualTags` ✅ | Code by hand → **+** Research frameworks → | `/docs/tag-for-meaning.html` **+** `/docs/codebook-frameworks.html` |
| 3 | Tag | Select one or more quotes, and press `t` to tag them with a code from your codebook. | `.tag` ✅ | Manual tagging → | `/docs/tag-for-meaning.html` |
| 4 | Star & hide | Press `s` to keep the quotes that matter, `h` to hide the rest. | `.starHide` ✅ | Keyboard shortcuts → | `/docs/keyboard-shortcuts.html` |
| 5 | Video clips | Turn selected quotes into video clips. | `.clips` ✅ | Export options → | `/docs/export-clips.html` |
| 6 | Send to Miro | Send quotes to a Miro board. | `.miro` ✅ | Connect to Miro → | `/docs/send-to-miro.html` |
| 7 | Connect an AI agent | Chat to your data from Claude Code, Claude Desktop, or any MCP agent. | `.agentChat` ✅ | Connect an agent… **+** Learn more → | **Settings ▸ MCP Agents (in-app)** **+** `/docs/connect-an-agent.html` |
| 8 | Ingest | Drop a folder of recordings or transcripts — Bristlenose transcribes, analyses and reports back. | `.ingest` ✅ | Import options → | `/docs/first-analysis.html` |

**Two slots carry two CTAs** (`linkLabel2` / `href2` on `SlotItem`), for different reasons:
- **Codebooks** — two honest entry points to the same feature: build one by hand, or start from a supplied framework.
- **Connect an AI agent** — **setup first, reading second** (2 Aug 2026). Its primary CTA is the only one in the pool that *doesn't* open a web page: it calls `SettingsWindow.shared.show(pane: .mcpAgents)`, the same destination as the **Bristlenose ▸ Connect an Agent…** menu item, landing the reader on the control instead of on a page about the control. The docs keep their route as `Learn more →`. Punctuation carries the distinction, per macOS convention: **`…` opens something here, `→` leaves for the browser** — so the two links in this slot are visibly different kinds of thing.

**How an in-app CTA is declared.** `SlotItem.primaryDestination: SlotDestination?` — set it *instead of* `href` (which the slot leaves empty) and the renderer swaps the `Link` for a `Button` styled to read as the same accent link. It is a plain tag, **not** a stored closure: `SettingsWindow` is `@MainActor` while the `WelcomeContent` pools are non-isolated `static let`s, so the call belongs in the view (`SlotRotator.slotView`, mirroring the AI cell's `Setup →`) and the content model stays pure data. Note the rotator path is the one that renders these — `slotBody`, used only by the unreachable configured-AI branch, does not handle `primaryDestination`.

**Withheld — Redact PII (2 Aug 2026).** Was slot 9 ("Remove personal details automatically, before analysis." → `/docs/redact-pii.html`). Commented out verbatim in `studyTools` because the `.app` cannot run it: Presidio + spaCy are in the sidecar spec's `excludes=[]`, `pii_enabled` defaults false and is settable only by the CLI's `--redact-pii`, and no desktop control exists. It also contradicted §Cell 3, which deliberately *skips* `redact-pii` from the Tip curriculum for being CLI-only. Restore the line when the capability ships on the Mac (tracked in the maintainer's private planning notes, §2 Broken ▸ Should).

_Set changes: (19 Jul 2026) Export split into **Video clips** + **Send to Miro** as separate illustrated tools; **Tag** kept with its own art; copy reuses existing house lines (Tips pool for clips/Miro). (1 Aug 2026) **Connect an AI agent** added as a new slot when the MCP extension shipped — not one of the original eight. (2 Aug 2026) **Redact PII** withheld; the four superseded screenshot imagesets (`welcome-{autocoding,codes,tag,star}`) deleted now their slots are drawn. (14 Aug 2026) The last three imagesets (`welcome-{clips,miro,ingest}`) deleted with their slots drawn; the `image:` mechanism removed from `SlotItem` and `slotView`._

_Key references render as **real drawn keycaps** — Skin **A · Flat**, the inline-prose default of [`design-keycaps.md`](design-keycaps.md) §2 — since 20 Aug 2026. **Bare keys stay lowercase** (`t` / `s` / `h`, not `T`/`S`/`H` — the unmodified-key rule), authored as markdown backticks and rendered by `welcomeKeyText` in `WelcomeHomeView.swift` — **one helper for every pool**, so Study tools, Tip, Science and AI all pick a cap up from the same backtick and none of them can drift. Caps are **baseline-corrected**: `Text` aligns an interpolated image's bottom edge to the text baseline, so an uncorrected cap floats visibly above the line (seen in both the Study-tools and Tip cells, 20 Aug 2026). `KeycapInline.run` returns the cap with the correction already applied — prefer it to `image(_:dark:)`, which does not. Derivation and the rule: [`design-keycaps.md`](design-keycaps.md) §3 decision 3. This replaced the text-only path (a same-size monospaced run) that shipped 19 Jul 2026 as a deliberate stand-in, on the stated condition that it be revisited "when the shared `Keycap` primitive graduates out of `#if DEBUG`" — which it now has (keycaps §Implementation-plan step 3). **The constraint that forced the stand-in is still true and explains the implementation:** a cap is a `View`, and a `View` cannot flow inside a wrapping `Text`. Rebuilding the sentence as a flow layout of word-views would fix that and lose everything else `Text` owns — truncation, `lineLimit`, and the `ViewThatFits` ladders that pick a shorter reading in a short cell. So `KeycapInline` rasterises the cap once per key and appearance and interpolates it as an image, which flows and breaks lines natively; the sentence stays a single `Text`, and markdown bold survives because the parse runs first and only `code` runs are substituted. Appearance is passed explicitly — `ImageRenderer` resolves colours against the app appearance, not the view's `colorScheme`, so an implicit read silently yields a light cap on a dark cell._

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

#### Cell 2 illustrations (built — 19 Jul, revised 25 Jul 2026)

Each science slot carries a tiny looping illustration in the example area (between the line and `Learn →`), one per concept. `SlotItem.illustration: WelcomeIllustration` selects it; `slotView` renders it (fixed height for the decorative ones so the φ-geometry never reflows; the books shelf sizes to content since it owns its own caption + link). Only the current rotator slot is alive, so a webview/animation exists only while shown. Impl: `WelcomeIllustrations.swift`. Reference spec: `docs/mockups/welcome-science-animations.html`.

**The rotator is 5 cells** — themes, books, sentiments, signals, dignity. Themes / signals / sentiment each keep their own cell because they *show a feature*; the books cell is the single **hat-tip** shelf that *credits the people*, not the feature (the A/B "framework authors vs reading list" split collapsed into one — it's all books & thinking you can leverage; the per-book line names the contribution).

| Slot | Illustration | Build |
|---|---|---|
| Seven sentiments | Seven chips rest as a readable 2-row grid and **deal** out from a gathered deck / gather back, staggered; upright, widths measured to centre the rows (`PreferenceKey`) | **native** (`SentimentFanView`) |
| Books (one cell) | Hat-tip **shelf** of the source books: covers overlap + slide front-to-back, and the **author + one-line contribution + Learn-more link sync to the top cover**; real covers (`welcome-book-*` imagesets) with typographic-card fallback | **native** (`BookShelfView`) |
| Signals | The real analysis signal card — histogram, four metrics + tooltips, pattern label — ticking through example signals with a split-flap flip | **webview** (`SignalIllustrationView`) |
| Dignity without distortion | Verbatim quote → strike the filler → collapse to the tidy quote → restore | **webview** (`QuoteIllustrationView`) |
| Emergent themes | Demo quote-fragments swirl as one flock → swoop into two labelled themes → rejoin | **webview** (`EmergentThemesView`) |

**Native vs webview split (decided with Martin, TF-play).** Native where cheap and clean (the sentiment deal, the book shelf). Webview where reusing the approved mockup verbatim beats re-deriving feel, or where the artefact is a real web component: the signal card **is** the shipped React/CSS card (rebuilding natively would fork a second source of truth vs `AnalysisPage.tsx`); the dignity quote + emergent-themes swoop were "perfect" in the mockup, so we reuse them rather than risk the feel. The **real `ShoalView` (boids) is deliberately NOT used** for emergent themes — it's the delight/analysing screensaver: it wants a big canvas and is for-fun, whereas a make-a-point cell needs the simple two-theme swoop.

**Books shelf.** `BookShelfView` is the only illustration that carries real content, so it is **NOT** `accessibilityHidden` (the decorative ones are; `slotView` gates this on `illustration == .books`) and it renders its own author/line/link — the science pool item leaves title/text/href empty. Front cover cycles ~3.8 s, caption cross-fades in step, caption height reserved (38pt, two `.body` lines) so the fan doesn't jump. **Only the fan scales** (20 Aug 2026): caption and link hold fixed semantic sizes and bend by losing *words* — `ViewThatFits` over full line → `WelcomeClauseFit.shortened` → 2-line ellipsis — while the fan scales on **both axes** inside an `aspectRatio(fanWidth/cardH, .fit)` box. The aspect box is load-bearing, not tidiness: `scaleEffect` is a drawing transform and never changes the frame the layout reserved, so when width was the binding constraint the drawn fan was taller than its frame and spilled over the Learn-more link, while in the converse case the unused reserve read as a gap under the caption. Matching the box to the fan's natural ratio makes reserved frame and drawn size the same thing. Cards `106×152` (~33% up from the first cut), peek `off = 34`, all four shown, block **left-aligned** — the three size/spread knobs (`cardW`/`cardH`/`off`) are constants at the top of the view. Extend by adding a `Book` (author, title, hat-tip line, docs href, spine, imageset) + a `welcome-book-<slug>.imageset`; only the front ~4 covers show, so it scales. Covers live in `Assets.xcassets/welcome-book-{norman,nielsen,braun-clarke,lazarus}.imageset` (single `2x` file each).

**Webview mechanics.** `IllustrationWebView` (`NSViewRepresentable`): `loadHTMLString` (no external resources — sandbox-clean; system font, slight rendering differences accepted), transparent via `setValue(false, forKey:"drawsBackground")`, `.allowsHitTesting(false)`, reloads on appearance/palette/reduce-motion change (keyed `.id`). The signal card renders at a fixed natural width and is uniformly transform-scaled to fit (max 90%, like the tools-cell images) — a fixed-width **flex item's `min-width:auto` inflated it to min-content and reflowed**, so it's absolute-positioned + transform-scaled instead.

**Open items (none blocking, TF-play state):** signal-card cell-height crowding (trimmed 2-metric variant candidate); split-flap glitch on the last char mid-flip; per-illustration timing/size tuning; emergent-themes word set; more books (Laws of UX / Yablonski next — one `Book` + one imageset); the author-outreach/affiliate idea (ask forgiveness + offer Amazon UK/US affiliate links → covers could become clickable affiliate links); whether these should also render on the docs pages (would tilt the split further toward web).

### Cell 3 — Tip (3rd)
- **Tag:** `Tip` (top-left). **No icon** — a lightbulb was built and cut (cheesy).
- **Content:** one rotating tip. Three ideas, all landed 25 Jul 2026 (`WelcomeHomeView.swift`):
  1. **An ambient map of the docs, not loose trivia.** The tip set is ~one tip per docs
     page, and the array order **mirrors the website's sidebar curriculum** (`bristlenose-website`
     `build.py` `NAV` → `ORDER`: Get started → How-to → Understand → Reference,
     i.e. getting-started → obscure). Over a month of launches the rotating blue links build
     a mental map of the whole help surface — ambiently, without anyone reading a tour. Keep
     the array in `NAV` order; it's the source of truth. Curation: the five provider-setup
     pages collapse to **two** tips (Set up Claude + Ollama); CLI-only (`cli`, `redact-pii`)
     and pure-chrome (`welcome`, `install`, `changelog`, `academic-sources`) pages are skipped.
  2. **Descriptive link, not "More →".** Each blue link is a **1–3 word label naming the
     destination page** (label ← page `title`), so the link itself teaches the topic.
  3. **Responsive copy inside the fixed cell (never a trim).** Each tip carries a **core**
     sentence sized to fit the small cell, plus an optional **follow-up** (`SlotItem.more`,
     ← page `lead`) shown **only when a larger cell can display the whole thing un-truncated**.
     Implemented with `ViewThatFits(in: .vertical)` (stock primitive; core+more first, core
     fallback second) — geometry stays fixed, content bends.
- **Rotation:** curriculum-then-random. `SlotRotator(curriculum: true)` walks the list in
  order for the first `count` launches (one per launch, persisted `…tip.visits`), then goes
  random (no back-to-back repeat). Science / Study-tools rotators keep plain next-per-visit.

**Set** — ~24 tips in `NAV` order (label ← title, follow-up ← lead). `supported-files` earns
two tips (skip-transcription + filename-merge, distinct labels). All slugs verified live in
`bristlenose-website/build.py`. The old free-standing 12-item pool is superseded by this
curriculum-derived set; add a new tip only when the docs gain a page.

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
3. **Cell tints** — accept the departure from seam-alignment discipline, or keep surfaces system-semantic and tint only accents. *Shipped as tinted while undecided — the code is the straw man, not the verdict.* Working candidate + the tool to iterate: §2 (Whisper reversed + glow + glass) / `welcome-gradient-playground.html`.
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
- Mockups: `docs/mockups/welcome-fibonacci-rotating.html` (canonical), `welcome-fibonacci-composed.html`, `welcome-fibonacci-refine.html`, `welcome-fibonacci-variants.html`, `welcome-layout-experiments.html`, `welcome-carousel-playground.html`, `welcome-gradient-playground.html` (cell-tint gradient variations with global Reverse/Glow/Glass layers; its defaults are the current working candidate — **the home for future tint experiments**, feeds open decision #3).
- Swift: `desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift`. Mounted from `ContentView.swift`'s empty-state branch.
- Live docs: `https://bristlenose.app/docs/`.
- Grounding: `docs/glossary.md`, `docs/design-research-methodology.md`, `docs/design-figma-setup.md`, `docs/design-native-colour-alignment.md`.
- **Superseded and deleted (`a310bca6`, 15 Jul 2026):** `WelcomeView.swift` — the previous empty-state pane (card + lifecycle rail, `.firstRun` / `.noSelection` variants). It had gone orphaned: no Swift references, no `pbxproj` entry — but the target's `PBXFileSystemSynchronizedRootGroup` kept auto-compiling it into the binary, so it was dead weight rather than merely dead source. Its locale keys were **kept** — see §Copy & i18n.
