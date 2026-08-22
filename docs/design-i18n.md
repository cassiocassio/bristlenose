---
status: mixed
last-trued: 2026-08-21
trued-against: HEAD@main on 2026-08-21 (ae05b1c0)
split-candidate: true
---

# Internationalisation — Codebook & Sentiment Translation

## Changelog

- _2026-08-21_ — **First front-matter, and two sections that described the opposite of what ships.** This doc had no `status`/`last-trued` at all, so nothing signalled that a March-2026 body was carrying 20–21 Aug additions (the CJK punctuation finding, Catalan, the gotchas) on top of it. Corrected: (1) §"No in-app language picker on desktop" — there **is** one, a 22-entry autonym `Picker` at `AppearanceSettingsView.swift:63`, and the `UIPrefersShowingLanguageSettings` key it credited appears nowhere in `project.pbxproj`. Both halves false, and `docs/design-locale-negotiation.md` repeats both and has not been touched since May. (2) §"Toolbar overflow: `_short` keys" described a live mechanism — zero `common.nav.*Short` keys exist in any locale, so `Tab.localizedLabel` falls through every time; the es/fr table illustrates a convention rather than describing strings. **Left flagged rather than rewritten**, because they want a measuring pass not a banner: the namespace inventory (`common ~34` against a measured 539; 8 namespaces against 9; "~180 keys × 7 languages" against 1,445 × 21) and `findLocalesDirectory()`'s priority list, which is inverted and missing its first branch (`Bundle.main.resourcePath`). `docs/platform-text-map.md` already carries the correct counts, regenerated — two docs on one subject, one measured and one three orders stale.

## Why we localise at all — read this before evaluating any locale

**Localisation is recognition, not utility.** It is a positioning strategy, and the strategy in one
line is: **don't add ten more features — send a signal to researchers all over the world that you
see them.** Everything below this section is mechanics; this is the reason any of it happens.

The argument, four parts:

1. **The incumbents won't do this, and the reason is structural.** Dovetail and co. don't localise
   because San Francisco is the centre of the universe. They *could* buy twenty locales tomorrow;
   they won't, because the return doesn't clear their bar. That asymmetry is durable — it isn't a
   capability gap that funding closes, it's a priorities gap that funding *creates*. Localisation is
   one of the few moats a solo maintainer can dig that a well-funded US competitor will walk past.
2. **The mechanism is affective, not functional — and it works on fluent speakers too.** This is the
   part that spreadsheets miss. The maintainer's Italian boss has a decade in the UK and full
   professional English, and still switches to Italian with visible pleasure — *a little spark of
   joy*. For everyone whose first language isn't English, a localised UI is a small friction removed
   from the working day. You never know which emotional factor makes someone click **Get** and start
   a trial. It can just be one feature.
3. **The unit economics invert at our scale.** A locale that wins five users is noise to Dovetail and
   material to us. **We don't need a lot of users — every single one matters.** The same investment
   has completely different value depending on the size of the business making it, which is why
   copying the incumbent's prioritisation logic is a mistake rather than a shortcut.
4. **It is an explicit trade against feature surface.** Feature count is where an incumbent with more
   engineers wins. Recognition is a axis where they aren't competing at all. Spending the next
   increment on a locale instead of a feature is choosing the contested ground deliberately.

**Consequence for how locales get chosen — three inputs, none of them a gate.** There *is* a
commercial case, and the sequencing has followed real logic: the prioritisation chart below (Mac
reach × UR depth) is why `nl` went first, why the Nordics travelled together, why RTL is a
checkpoint rather than a locale, and why `zh-Hans` is parked. That reasoning stands. But it is **one
of three inputs**, not the decision procedure:

1. **Commercial logic** — the chart. Real, and it drives sequencing.
2. **Emotional and cultural** — the recognition argument above. Why a locale can be worth doing that
   the chart ranks low.
3. **Practicality** — *who we can ask a favour of*, and *which communities we want to present to*.
   Reviewer availability is the genuine bottleneck on every locale here (it is why `nl`/`fi`/`pl`/
   `ru`/`uk`/`tr` sit seeded-but-unreviewed), and conference audiences are a real input — the **UX
   Europe unconference crowd** is a community worth showing up for, and that legitimately shapes
   which languages get attention.

**The failure mode is letting a thin ROI estimate override inputs 2 and 3** — not having a
commercial view at all. That went wrong once (Catalan, 14 Aug 2026): a throwaway "five users, maybe
$1000?" became a de-risking framework that recommended holding a seed which was never a financial
decision. The chart informs; it does not adjudicate. The governing line is the maintainer's: **"Some
kinds of analysis are best done outside a spreadsheet."**

## Problem

Bristlenose processes interviews in any language — modern LLMs handle cross-lingual reasoning natively (English prompt + German transcript = fine). But the **display layer** should speak the researcher's language. A German ethnographer expects "Zitate" not "Quotes", and a Japanese UXR practitioner expects コード not "Codes".

Three layers, three strategies:

1. **UI chrome** (Codes, Codebook, Quotes, Sessions, Signals) → translate to UI language
2. **Sentiment tags** (7 values) and **built-in UXR codebook** (38 tags) → translate to UI language, verified by native UXR practitioners
3. **Third-party codebooks** (Don Norman, Morville, Garrett) → stay in author's language (future work)

## Strategy: why we don't translate prompts or transcripts

**Option rejected: translate prompts into target languages.** Would require maintaining N copies of every prompt for diminishing returns. Codebook concepts often originate in English — translating them adds a lossy step.

**Option rejected: translate transcripts to English.** Destroys nuance, idiom, and cultural context — exactly what UX researchers care about. "Das ist mir total egal" carries different weight than "I don't care at all". Adds a compounding-error pipeline stage.

**What works: cross-lingual LLM reasoning.** Send the LLM original-language transcripts with English codebook/prompts. The LLM tags in the codebook's language, extracts quotes verbatim in the original language, and generates summaries in the user's preferred language. Translation happens at the display layer only.

> **⚠️ Status correction (verified in code 14 Aug 2026): the third clause is NOT implemented.** The
> locale never reaches the prompt. `LLMClient.analyze()` takes no language or locale parameter; no
> prompt template in `bristlenose/llm/prompts/` mentions an output language; and `bristlenose.i18n`
> is never imported anywhere in the LLM or analysis path (only CLI, preflight, status page, run
> lifecycle, billing hints and the PII stage). The only language settings in the pipeline are
> `whisper_language` (transcription) and a hardcoded `language="en"` for spaCy in PII removal.
>
> So today: **quotes are genuinely verbatim in the original language** (extraction, not generation —
> that clause is true), but theme names, definitions and summaries are *generated* against an English
> system prompt with no output-language instruction, making their language undefined and probably
> inconsistent. **This is a gap across all 20 locales, not a per-locale one** — no non-English user
> gets analysis output in their language today. Wiring it would unlock deliverable-language for every
> locale already paid for, which is plausibly worth more than any single additional locale. Logged as
> an objective, not a resolved design. Written as settled fact above since Mar 2026; treat the
> paragraph as intent until this note is removed.

## Internal representation: English always

- `Sentiment.FRUSTRATION` enum — DB stores `"frustration"`
- Tags stored as English strings in DB (canonical)
- LLM prompts use English tag names, return English values
- Translation is display-only — tags are interoperable across languages
- A German user's tags are readable by an English user

**Localised defaults vs English-canonical defaults.** A placeholder *name* the user
immediately renames (a "rename seed") IS localised: `codebook.newGroup` / `codebook.newCode`
resolve in the active UI language at creation time, because nothing downstream keys off the
string — it exists to be typed over. The English-always rule above governs *canonical* values
only (enum keys, tags, LLM-facing strings, anything matched / joined / fed to a prompt). The
test when adding a defaulted field: **does anything downstream match, join, or feed this
string to an LLM?** If yes → store English. If it's a freeform field the user overwrites →
localise the default. (Contrast `project_name = "Untitled"` in `server/importer.py`, an
identifier-ish fallback that deliberately stays English.)

## Terminology research — what researchers actually call things

Sources: ATLAS.ti and MAXQDA localized interfaces (both German-origin QDA tools), NVivo, academic textbooks (Flick, Mayring, Kuckartz), UXR industry usage.

### Recommended UI chrome translations

| Concept | English | German | French | Spanish | Japanese | Korean |
|---------|---------|--------|--------|---------|----------|--------|
| **Codes** | Codes | Kodes | Codes | Códigos | コード | 코드 |
| **Codebook** | Codebook | Codebuch | Grille de codage | Libro de códigos | コードブック | 코드북 |
| **Tags** | Tags | Tags | Tags | Etiquetas | タグ | 태그 |
| **Quotes** | Quotes | Zitate | Verbatim | Citas | 発言 | 인용문 |
| **Sessions** | Sessions | Interviews | Entretiens | Sesiones | セッション | 세션 |
| **Signals** | Signals | Signale | Signaux | Señales | シグナル | 시그널 |

### Rationale notes

**Codes — Kodes (de)**
ATLAS.ti germanizes to "Kodes" (with K); MAXQDA keeps "Codes". Kodes is more deliberately German. The process is always "Kodierung" / "Kodieren" (coding). Academic literature (Mayring, Kuckartz, Flick) uses both interchangeably.

**Codebook — Codebuch (de) / Grille de codage (fr)**
MAXQDA uses "Codebuch". Academic German prefers "Kategoriensystem" (category system) or "Codierleitfaden" (coding guide), but Codebuch is what tool users see. French academic research strongly prefers "grille de codage" (coding grid) — "livre de codes" exists but is a literal calque that sounds unnatural.

**Tags**
"Tags" is borrowed as an English loanword in all 5 target languages — no native QDA equivalent exists in any tradition. The Tags/Codes distinction doesn't exist in academic QDA anywhere; all languages treat them as synonyms or only use "codes".

**Quotes — Zitate (de) / Verbatim (fr) / 発言 (ja)**
ATLAS.ti uses "Zitate" (quotations). MAXQDA uses the more technical "Codierte Segmente" (coded segments). Zitate is warmer and matches how researchers think about participant words.

All research traditions know "verbatim" (it's Latin) but use it differently. In English and German it stays academic — a transcription method ("we did a verbatim transcription"). In French it has uniquely become the **everyday product-level noun** for participant quotes — "voici les verbatim". French researchers say "verbatim" daily; using "citations" would sound cold/academic. This is the standout finding.

German "Zitate" (ATLAS.ti's term) is the warm, natural choice. Germans understand "Verbatim" but wouldn't expect it in a tool UI. Spanish "Citas" is ATLAS.ti's term and feels natural; Spanish researchers know "verbatim" as a transcription descriptor, not a noun for the quotes themselves.

Japanese UXR practitioners use **発言** (hatsugen = utterance/statement) for participant quotes. The academic term 引用 (in'yō = quotation) exists but feels more literary/citation-like.

**Sessions — Interviews (de) / Entretiens (fr)**
Neither German nor French QDA uses "session" — interviews are interviews. German "Sitzung" and French "séance" exist but are uncommon in research contexts. Japanese and Korean simply transliterate (セッション, 세션).

**Signals**
"Signals" has **no equivalent in any language's QDA tradition** — it's a Bristlenose-specific concept. The closest academic terms are patterns (Muster / パターン / 패턴) or themes (Themen / テーマ / 주제). We recommend transliterating: Signale / Signaux / Señales / シグナル / 시그널 — since it's our concept, we name it.

### Cross-cutting observations

- **Japanese and Korean** transliterate nearly everything into katakana/Hangul — the research communities work in English-origin terminology
- **German, French, Spanish** have genuine native vocabulary — use it for academic credibility
- **French "verbatim"** is the single most important finding — it's the natural, warm term French researchers use. Getting this right signals "this tool was built for us"

## Third-party codebooks (future work)

### Don Norman — The Design of Everyday Things

Translated into 20+ languages. Key finding for Japanese: the community uses **katakana transliterations** rather than native Japanese terms:
- アフォーダンス (afōdansu) = affordance
- シグニファイア (shigunifiaia) = signifier
- マッピング (mappingu) = mapping

This means Don Norman tags should stay in their original English for now, but Japanese translations would use these established katakana terms, not invented Japanese words. The professional community already knows them.

### Morville Honeycomb / Garrett Elements / Nielsen Heuristics — don't translate

Amazon sales rank data (Mar 2026) confirms these frameworks have negligible international traction:

| Book | Japan (amazon.co.jp) | France (amazon.fr) |
|------|---------------------|-------------------|
| **Norman** | **#5,251** (155 ratings) | #212,175 (#1 in category, 54 ratings) |
| Garrett | #255,896 (24 ratings) | #879,506 (3 ratings) |
| Morville | #149,288 (41 ratings) | **No French translation exists** |
| Nielsen | #532,405 (4 ratings) | **No French translation exists** |

Norman at #5,251 in Japan is a genuinely popular book still actively selling 10+ years after the revised edition. Everything else is noise. Morville and Nielsen were never even translated into French.

**Locally-authored UX books massively outperform translated anglosphere ones** (except Norman): Amélie Boucher's "Ergonomie web" has 344 reviews on Amazon.fr vs Garrett's 3. Masaya Ando's UX textbook ranks #22,176 in Japan vs Garrett's #255,896.

**Decision:** Translate Norman's codebook when we do third-party i18n. Garrett, Morville, and Nielsen stay English — their audience learned these frameworks in English.

### Strategy for Norman translation (future)

- Japanese: use established katakana transliterations (アフォーダンス, シグニファイア, マッピング) — the community already uses these
- German/French/Spanish: research the official published translations for each concept term
- Cross-check with what the professional community actually says (may differ from the book)
- Korean: likely Hangul transliterations, same pattern as Japanese

## String audit — full scope

**Already in i18n (34 keys):** nav tabs, basic buttons (Save/Cancel/Export/Close), sentiment enum names, speaker roles, settings panel labels, footer.

**Hardcoded (~180+ strings) — not yet in i18n.** Grouped by priority:

### Tier 1 — Core research vocabulary
The words researchers see constantly. Getting these right determines whether the tool "speaks their language".

- **Report structure:** Section, Theme, Sections, Themes
- **Analysis:** Signal, Signals, Concentration, Agreement, Intensity, "Composite signal strength", "concentration ratio", "agreement breadth (Simpson's diversity index)"
- **Coding:** Codes, Codebook, Tags, Tag signals, Sentiment signals
- **Data:** Quotes, Sessions, Participants, Interviews, Duration, Speakers
- **Actions:** Star, Hide, Unhide, Add tag, Search quotes, Filter quotes
- **Quote card:** sentiment badge labels, moderator question, "Revert to original", "Restore tags"

### Tier 2 — Action chrome
Buttons, modals, keyboard shortcuts — functional UI that users interact with but don't "read".

- Modal headings: "Export report", "Keyboard Shortcuts", "How is Bristlenose working for you?"
- Modal content: "Download a self-contained HTML file...", "Anonymise participants", "Remove participant names, keep codes..."
- Search: "Filter quotes…" (placeholder), "Clear search", "Search tags…"
- Keyboard shortcut descriptions (15 strings): "Next quote", "Previous quote", "Toggle select", etc.
- Transcript: "Show previous/next transcript segment", "Copy folder path"
- Codebook: "Create new codebook", "Browse codebooks", "Your codebooks", "Import a framework..."
- Feedback: "Frustrating" / "Needs work" / "It's okay" / "Good" / "Excellent"

### Tier 3 — About, settings, dev tools
Low-frequency content. Researchers see it once.

- Sentiment definitions ("Frustration — difficulty, annoyance, friction" etc.)
- Configuration reference labels (LLM Provider, Transcription, Privacy, all env var names)
- About panel content, version info, links
- Playground labels (dev-only — arguably never translate)

### Scale

~180 keys across 8 namespaces × 7 languages = ~1,260 translation strings total.

## Architecture: single source of truth (implemented, Mar 2026)

### Canonical locale directory

**`bristlenose/locales/{locale}/{namespace}.json`** — the only place translations live. Three codebases consume them:

| Consumer | How it reads locale files |
|----------|-------------------------|
| **Python** (`bristlenose/i18n.py`) | Direct filesystem read at runtime. `t("namespace.key")` |
| **React** (`frontend/src/i18n/`) | Vite `resolve.alias` (`@locales`) at build time. English bundled inline; other locales lazy-loaded via dynamic `import()` |
| **macOS desktop** (`desktop/.../I18n.swift`) | `I18n` class loads JSON from disk. `findLocalesDirectory()` priority (top wins): (1) `#filePath`-derived path relative to `I18n.swift` itself — resolves to the worktree's own `bristlenose/locales/` so each git worktree reads its own files, not the main repo's; (2) `~/Code/bristlenose/bristlenose/locales` legacy fallback; (3) bundled `.app` (`Bundle.main.resourceURL/sidecar/_internal/.../locales`); (4) Homebrew / pipx site-packages. Worktree-aware fallback added 2026-05-01 (commit `816ab65`) — without it, locale keys added in a worktree silently fail to resolve at runtime |

### Namespace inventory

| Namespace | Used by | Keys |
|-----------|---------|------|
| `common.json` | React + Desktop | ~34 (nav tabs, buttons, labels, footer) |
| `settings.json` | React + Desktop | ~15 panel labels + `pipeline.alternatives.*`, `pipeline.reasons.*`, `pipeline.backends.*` (v1.5 Pipeline-view keys; ~25 leaves) |
| `enums.json` | React + Python + Desktop | ~11 (sentiments, speaker roles) |
| `cli.json` | Python only | ~15 (CLI output) |
| `pipeline.json` | Python only | 4 (stage progress: `start`, `stageStart`, `stageComplete`, `done`). **Note:** the Pipeline-view editorial keys (`pipeline.reasons.*`, `pipeline.backends.*`, `pipeline.alternatives.*`, and v1.9's `pipeline.quality.*`) currently colocate under `settings.json`, not `pipeline.json`. Eventual housekeeping question — consolidate under one file or split semantically — tracked separately. |
| `server.json` | Python only | ~5 (API errors) |
| `doctor.json` | Python only | ~5 (health checks) |
| `desktop.json` | Desktop only | ~95 (menu bar, toolbar, native chrome, `boot.*` and `welcome.*` blocks added 2026-05-01) |

### Desktop locale flow

**Canonical design:** `docs/design-locale-negotiation.md` — covers desktop-vs-web split, why we delegate to System Settings → Apps, and the `UIPrefersShowingLanguageSettings` Info.plist key.

1. **macOS picks the locale.** `I18n.swift` reads `Bundle.preferredLocalizations(from: supportedLocales, forPreferences: nil).first ?? "en"` on every launch. Apple's BCP 47 lookup matcher reads `AppleLanguages` (set globally by System Settings → General → Language & Region, or per-app by System Settings → Apps → Bristlenose → Language).
2. `I18n.setLocale()` reloads JSON from disk → `@Published` triggers SwiftUI re-render. The setter is now used only for runtime locale propagation, not user choice.
3. `BridgeHandler.syncLocale()` pushes locale to web via `callAsyncJavaScript`.
4. Startup flash prevention: locale injected as `?locale=es` URL query param on WKWebView load → `LocaleStore.ts` detects synchronously before first render.
5. In embedded mode, the web language picker is hidden — System Settings is the single control point. The web picker remains visible and usable in real-browser CLI serve mode (no per-site language override exists in browsers, so the in-app picker is the only escape hatch there).
6. ~~**No in-app language picker on desktop.** Settings → Appearance contains a hint paragraph pointing users to System Settings → Apps → Bristlenose. `INFOPLIST_KEY_UIPrefersShowingLanguageSettings = YES` (in `project.pbxproj`) forces that section to appear in System Settings even for users with only one preferred language configured globally.~~

   > **False in both halves — corrected 21 Aug 2026.** Settings ▸ Appearance
   > ships a **22-entry `Picker`** listing every locale by its own autonym
   > (`AppearanceSettingsView.swift:63`), and it is the control the desktop
   > actually uses — it is registration site 9 of the ten a new language needs
   > (`docs/adding-a-language.md` Step 8). There is no hint paragraph. And
   > `UIPrefersShowingLanguageSettings` appears **nowhere** in `project.pbxproj`
   > (zero grep hits), so the System Settings mechanism this described was
   > either never wired or was removed without the doc moving. **Note
   > `docs/design-locale-negotiation.md` repeats both claims verbatim and has
   > not been touched since May 2026** — it inherits this correction and has
   > not yet had it applied.

### `CommandMenu` titles stay in English

SwiftUI's `CommandMenu("Project")` takes `LocalizedStringKey` which resolves from `.lproj` bundles, not runtime JSON. Rather than maintaining a second localisation format for 4 strings, menu titles ("Project", "Codes", "Quotes", "Video") stay in English. Menu *items* inside are translated via `I18n.t()`. This matches ATLAS.ti and MAXQDA precedent — both keep English menu titles even in localised UIs.

### Toolbar overflow: `_short` keys

> **The mechanism is live; the data is gone — measured 21 Aug 2026.** There are
> **no `common.nav.*Short` keys in any of the 22 locale directories**; the last
> one went with `8a99912a` ("drop `nav.codebookShort`, a key English never
> had"). `Tab.localizedLabel` (`Tab.swift:25`) still prefers a `…Short` key and
> so now falls through to the full label every single time, in every locale.
> The table below is therefore an illustration of a convention, not a
> description of shipped strings — neither `Códigos` nor `Codage` exists. Adding
> one back would work, and the fallback is doing its job; but nothing today
> uses it, so treat this section as available-and-unused rather than as
> in-force. (Other `*Short` keys — `stageShort`, `failedShort` — are a
> different convention in `server.json`/`desktop.json` and are unaffected.)

"Libro de códigos" (es) and "Grille de codage" (fr) are ~2× wider than "Codebook". The toolbar segmented control uses `common.nav.{tab}Short` keys where available, falling back to the full `common.nav.{tab}` key. Only add `_short` variants where the full label exceeds ~10 characters.

| Tab | Full (View menu) | Short (toolbar) |
|-----|-----------------|-----------------|
| codebook (es) | Libro de códigos | Códigos |
| codebook (fr) | Grille de codage | Codage |

## Terminology standards

### Per-namespace key convention

Two conventions coexist in the locale tree, applied per surface:

- **camelCase flat / shallow-nested** — short, sentence-ish action / progress strings authored fresh in JSON. Examples: `pipeline.json`'s `stageStart` / `stageComplete`; `common.json`'s `nav.codebook`; `enums.json`'s `speakerRole.participant`.
- **`<category>.<snake_case_leaf>`** — keys that map 1-to-1 to Python identifiers (predicate explainers, backend ids, quality note keys). Examples from `settings.json`: `pipeline.reasons.mlx_whisper_not_installed`, `pipeline.backends.local_ollama`, and v1.9's `pipeline.quality.local_quote_extraction_miss_rate`. The snake_case leaf preserves grep parity between the Python identifier and the i18n key — `grep miss_rate locales/` finds the locale entry; `grep miss_rate bristlenose/` finds the catalogue cell that references it.

The rule is **convention-by-origin, not convention-by-file**. New keys derived from Python identifiers (catalogue cells, requirement names, enum-like predicates) use snake_case leaves under their category. New keys authored fresh for UI chrome (button labels, panel titles, action verbs) use camelCase. When in doubt, look at the sibling keys in the same category block; consistency within a block matters more than uniformity across the file.

See [design-pipeline-view.md](design-pipeline-view.md) §Locale convention for the v1.9 instantiation of this rule.

### The "Cancel button problem"

Every language has a standard word for common UI actions. Getting it wrong makes the tool feel alien. Two authoritative databases exist:

- **[applelocalization.com](https://applelocalization.com/)** — searchable Apple glossary from official bilingual glossaries for macOS/iOS. Since Bristlenose is a macOS app, this is the primary reference. Also available as [DMG downloads](https://developer.apple.com/localization/resources/) from Apple Developer.
- **[termic.me](https://termic.me/)** — indexes Microsoft Terminology + 10,000 VS Code strings. Cross-reference when Apple's glossary doesn't cover a term. [Open source](https://github.com/Spidersouris/termic).

**Rule: for standard UI verbs (Save, Cancel, Delete, Close, Undo, Export, Search), always use Apple's term for the target platform.** Cross-check against Microsoft for general IT terms. If both agree, it's definitive. If they differ (rare for basics), prefer Apple since we're a macOS-native app.

### CJK punctuation: measured on the platform, not taken from a style guide

Corollary of the Apple-wins rule above, and it bites harder because the
"obvious" authority points the other way. Settled 20 Aug 2026 by counting
`.loctable` files, after a sweep that got the polarity exactly backwards in
both directions.

| | labels (`Name:`) | prose lead-ins (`Note:`, `e.g.:`) |
|---|---|---|
| Japanese | halfwidth `:` + space | fullwidth `：`, no space |
| Chinese (Hant + Hans) | fullwidth `：`, no space | fullwidth `：`, no space |

The counts: Apple ja 431 halfwidth to 2 fullwidth, and its own Save dialog
ships `名前:`; Microsoft ja 38,041 to 88; Apple zh-Hant 239 fullwidth to 0.
The same source string shows the per-language split is deliberate — `便名: %@`
in Japanese, `航班：%@` in Chinese.

**The JTF style guide says the opposite for Japanese**, and it is not wrong —
it is the right authority for a translated *document* and the wrong one for
macOS chrome. Both OS vendors classify `:` as an internationally-used symbol
rather than Japanese 約物, which is why they diverge from it. A label that
reads differently from every other label on the user's Mac is the defect,
whatever the guide says.

Two traps when auditing this. Fullwidth punctuation carries ~half an em of
built-in right side bearing, so `：` takes **no** following space — swapping
the character without deleting the space double-counts it. And kinsoku (禁則)
line-breaking tables are strings that enumerate punctuation
(`、。，．・：；？！…`), where the `：` is data rather than usage; 30 of
Microsoft's 118 fullwidth hits were these.

Full reasoning, counts and the reproduce command: `.claude/agents/i18n-review.md`
§6a and `docs/adding-a-language.md` Step 5a.

### Process for adding a new language

#### Step 1: Machine-translate as draft
Machine-translate all 8 namespace files. Use the English files as source. This gives you a working baseline that's ~80% correct for standard UI terms.

#### Step 2: Apple glossary cross-check (mandatory)

The canonical source for how Apple translates standard UI terms on macOS is `support.apple.com` in the target language — specifically the keyboard shortcuts page (e.g. `support.apple.com/es-lamr/102650` for Latin American Spanish). This page uses Apple's actual menu labels.

**Check every standard UI button/action against Apple's term.** The terms that matter most:

| English | What to look up |
|---------|----------------|
| Save, Cancel, Close, Delete, Undo, Redo | File/Edit menu terms |
| Copy, Cut, Paste, Select All | Edit menu terms |
| Find, Find Next, Find Previous | Edit > Find menu terms |
| Print, Export | File menu terms |
| Zoom In, Zoom Out, Fullscreen | View menu terms |
| Hide, Show, Settings/Preferences | App menu terms |
| Search | Toolbar/Spotlight terms |
| New, Open, Quit | File menu terms |

**Gotcha: Apple's shortcuts page uses informal descriptions, not menu labels.** The shortcuts page might say "Buscar otra vez" (search again) where the actual Edit menu says "Buscar siguiente" (Find Next). When in doubt, the menu label wins — open a Mac app (Safari, Finder, TextEdit) in the target locale and look at the actual menu text. Or use [applelocalization.com](https://applelocalization.com/) which indexes the actual `.strings` files.

**Gotcha: "Delete" has two senses in Apple's terminology.** "Suprimir" is the keyboard Delete key; "Eliminar" is the destructive action (delete a file, remove an item). Bristlenose uses Delete as an action → use the action form, not the key name.

**Gotcha: Apple changed "Preferencias" to "Ajustes" in macOS Ventura (2022)**, matching iOS. Old documentation may still say "Preferencias". Use "Ajustes" for macOS 13+.

#### Step 3: Cross-check domain vocabulary

Check our research terminology table (earlier in this document) for the target language. The domain terms (Quotes, Codebook, Sessions, Signals, Codes) were researched from ATLAS.ti, MAXQDA, and academic QDA literature — they override any machine translation.

#### Step 4: Toolbar overflow check

Check whether `common.nav.codebook` exceeds ~10 characters in the target language. If so, add a `common.nav.codebookShort` key. Check other tab labels too — `sessions` is "Interviews" (10 chars) in German and "Entretiens" (10 chars) in French, both borderline.

#### Step 5: Native-speaker review

Send the draft to a native-speaking UXR practitioner. Key review questions:
- Do the domain terms (Codebook, Quotes, Sessions) match what this community actually says?
- Are button labels natural or stilted?
- Gender conventions: inclusive slash form ("Investigador/a") vs parenthetical ("Investigador(a)") vs neutral
- Formality: formal "usted" vs informal "tú" (varies by country for Spanish; Japanese has even more registers)

#### Step 6: Machine translation QA — domain term grep

Machine translation reliably handles standard UI verbs but **frequently leaves domain-specific nouns as English loanwords** in the middle of otherwise-translated sentences. The v0.14.1 batch left "codebook" untranslated in ~15 keys per language (es/fr) while correctly translating the same term in nav labels and headings.

**After every machine translation batch, run this check:**

```bash
# For each domain term, grep for the English word in every non-English locale
for lang in es fr de ko; do
  echo "=== $lang ==="
  for term in codebook quotes sessions signals codes tags sentiment; do
    hits=$(grep -i "\"[^\"]*\b${term}\b[^\"]*\"" bristlenose/locales/$lang/*.json \
           | grep -v "\"${term}\":" | wc -l)
    [ "$hits" -gt 0 ] && echo "  $term: $hits untranslated values"
  done
done
```

Any English domain term appearing in a **value** (not a key) is a miss. Keys like `"codebookTags"` are internal identifiers and should stay English.

**Common failure patterns to watch for:**

1. **Loanword in modifier position** — "codebook tags", "browse codebooks" get half-translated ("Explorar codebooks" instead of "Explorar libros de códigos"). The machine translates the verb but leaves the noun as English
2. **Inconsistency across namespace files** — desktop.json may get the correct translation while common.json doesn't (different translation passes or prompts)
3. **Article gender cascades** — when the translated term changes grammatical gender, articles and adjectives throughout the sentence must change too. French: "un nouveau codebook" → "une nouvelle grille de codage" (grille is feminine). Spanish: "de codebook" → "del libro de códigos" (de + el contracts)
4. **Preposition contractions** — Spanish "de + el" = "del", "a + el" = "al". French doesn't contract with feminine articles. Getting these wrong sounds jarring to native speakers
5. **Singular/plural form mismatch** — the glossary should include both forms: "libro de códigos" / "libros de códigos" (es), "grille de codage" / "grilles de codage" (fr), "Codebuch" / "Codebücher" (de)

**Prevention: build a glossary before translating.** Give the machine translator a term table (English → target language, singular + plural) and instruct it to use these terms exclusively. Then grep to verify.

#### Step 7: Track review status

Add a progress entry to the "Progress" section below with: language, date, reviewer name/location, review status, open questions.

### Spanish cross-check results (23 Mar 2026)

All Spanish translations verified against [Apple's macOS keyboard shortcuts page (es-lamr)](https://support.apple.com/es-lamr/102650). Results:

| English | Ours | Apple | Verdict |
|---------|------|-------|---------|
| Save | Guardar | Guardar | ✓ |
| Cancel | Cancelar | Cancelar | ✓ |
| Close | Cerrar | Cerrar | ✓ |
| Copy | Copiar | Copiar | ✓ |
| Delete | Eliminar | Suprimir (key) / Eliminar (action) | ✓ action sense correct |
| Undo | Deshacer | Deshacer | ✓ |
| Redo | Rehacer | Rehacer | ✓ |
| Search/Find | Buscar | Buscar | ✓ |
| Find Next | Buscar siguiente | Buscar otra vez (informal) | ✓ menu label is "Buscar siguiente" |
| Print | Imprimir | Imprimir | ✓ |
| Hide | Ocultar | Ocultar | ✓ |
| Open | Abrir | Abrir | ✓ |
| Fullscreen | Pantalla completa | Pantalla completa | ✓ |
| Settings | Ajustes | Ajustes (post-Ventura) | ✓ |
| Export | Exportar | Exportar | ✓ |
| Zoom In | Ampliar | Aumentar el tamaño (informal) | ✓ short form used in actual menus |
| Zoom Out | Reducir | Reducir el tamaño (informal) | ✓ short form used in actual menus |
| Accept | Aceptar | Aceptar | ✓ |
| Apply | Aplicar | Aplicar | ✓ |
| Reset | Restablecer | Restablecer | ✓ |

**No changes needed.** All translations match Apple's canonical menu-level terms.

## Community translation: Weblate

### Why Weblate

[Weblate](https://weblate.org/) is a libre (GPLv3) translation platform. The hosted instance at `hosted.weblate.org` is **free for libre/FOSS projects** — equivalent to the 160k strings tier (€114/month value). Unlimited projects, components, translators. All features included.

Bristlenose qualifies (AGPL-3.0) and was approved for the Libre plan on 29 Apr 2026 after a multi-week trial-and-merge-conflict saga (see `project_weblate_ticket_2013688.md` memory for the operational history). **This is the path forward for the foreseeable future** — the alternatives below were considered and ruled out, the merge-conflict failure modes are now understood, and the gratis hosting unlocks community translation without ongoing cost.

The Libre plan carries one condition: attribution. Mention Weblate in the README (done — see translation section) and on bristlenose.app (outstanding). Content for both can be pulled verbatim from the Community menu of the Weblate project.

### How it works

1. Weblate connects to the GitHub repo, reads `bristlenose/locales/` (i18next JSON v4 format — [first-class support](https://docs.weblate.org/en/latest/formats/i18next.html))
2. Contributors get a URL like `hosted.weblate.org/projects/bristlenose/`
3. They see each English string with context, suggestions, and a text box — no JSON, no Git
4. Weblate commits translations to a branch and opens PRs
5. We review and merge

### What contributors see

- Source string (English)
- Localization comment (what the string is for, what variables mean)
- Screenshot or context description
- Glossary entries (Apple/Microsoft standard terms loaded as a Weblate glossary)
- Machine translation suggestions (DeepL, Google, etc.)
- Other translations of the same string in other projects

### Setup steps

1. Create project at `hosted.weblate.org` ✓
2. Add 8 components (one per namespace), file mask `bristlenose/locales/*/{ns}.json`, monolingual base `bristlenose/locales/en/{ns}.json` ✓
3. Upload Apple + QDA glossary (`bristlenose/locales/glossary.csv`) as Weblate glossary ✓
4. Add "Help translate Bristlenose" link to About panel + README + CONTRIBUTING ✓
5. CI validation (`scripts/check-locales.py`) runs on PRs touching locale files ✓
6. Japanese (ja) stub files created for community translation ✓
7. Translator guide: `TRANSLATING.md` ✓

**Implemented 24 Mar 2026.** Weblate submits translations as pull requests; all PRs require human review.

### Live configuration

**Project URL:** [hosted.weblate.org/projects/bristlenose/](https://hosted.weblate.org/projects/bristlenose/)

**Hosting:** Libre plan (160k strings, 0 EUR) — **approved 29 Apr 2026**. Attribution required (mention Weblate in README and on bristlenose.app); README already links Weblate from the translation section, website mention pending.

**Components (8):**

| Component | File format | File mask | Strings |
|-----------|------------|-----------|---------|
| common | JSON nested structure | `bristlenose/locales/*/common.json` | ~275 |
| settings | JSON nested structure | `bristlenose/locales/*/settings.json` | ~28 |
| enums | JSON nested structure | `bristlenose/locales/*/enums.json` | ~13 |
| cli | JSON nested structure | `bristlenose/locales/*/cli.json` | ~22 |
| pipeline | JSON nested structure | `bristlenose/locales/*/pipeline.json` | ~4 |
| server | JSON nested structure | `bristlenose/locales/*/server.json` | ~7 |
| doctor | JSON nested structure | `bristlenose/locales/*/doctor.json` | ~7 |
| desktop | JSON nested structure | `bristlenose/locales/*/desktop.json` | ~115 |

**VCS integration:**
- Version control system: GitHub pull request (Weblate forks and opens PRs)
- Repository branch: `main`
- Push branch: empty (Weblate manages its own fork)
- GitHub webhook: `https://hosted.weblate.org/hooks/github/` (push events only, no secret)

**Format settings:**
- JSON indentation: 2 spaces
- Monolingual base: `bristlenose/locales/en/{ns}.json` for each component
- Components share the same repo clone via `weblate://bristlenose/common`

**Glossary:** uploaded from `bristlenose/locales/glossary.csv` — Apple HIG terms + QDA domain terms (Codebook, Quotes, Sessions, etc.) across es/fr/de/ko/ja/cs/it/pl/ru/uk.

**Translation instructions:** linked to `TRANSLATING.md` in project settings.

**Languages discovered:** en (source), es, fr, de, ko (100% translated), ja (0% — empty stubs, manually added as language since Weblate skips all-empty files).

**Gotchas learned during setup:**
- Weblate auto-discovers files from the repo but ignores locales where every value is an empty string (Japanese stubs). Must add the language manually via the + button on the component's Languages page
- The "Source code repository" field on the create-component form pre-fills with a label prefix (`Source code repository: https://...`) — this must be cleared to just the bare URL or git clone fails with "protocol not supported"
- JSON indentation defaults to 4 — must change to 2 to match our files, otherwise Weblate reformats every file on first commit
- Second+ components should use "From an existing component" tab and select `common` to share the repo clone

### Czech (`cs`) — community-initiated

**Language code, not country code.** The locale is ISO 639-1 `cs` (the Czech _language_),
**not** `cz` (the ISO 3166-1 country code for Czechia — what's on Praha number plates). The
`cz` git branch is a label only; every locale dir, `SUPPORTED_LOCALES` entry, `glossary.csv`
row, and language-picker tag uses `cs`. (Slovak, which split from Czech administratively in
1993, is the separate language code `sk`; `cs` is unambiguously Czech.)

Czech is the first locale Bristlenose didn't plan. A volunteer signed up on Weblate and
started a `cs` translation _before_ we'd added the language to the product — the first
_organic_ demand signal for a locale we've had, and evidence of at least one Czech-speaking
researcher in the wild. We treated it as a delight opportunity rather than a backlog item:
instead of handing the volunteer a blank slate, we machine-seeded a complete Czech baseline
across all eight namespaces (+ `preflight`), with proper Czech four-form CLDR plurals
(`one`/`few`/`many`/`other`), for them to react to and correct.

**Fill-empty-only invariant.** The MT seed is additive: for each English key it writes a
Czech value _only_ where `cs` is currently empty or missing — it never overwrites a
non-empty value, because that value may be a human contribution. The guarantee is structural
(file-level) and re-runnable. On Weblate's side, its database is authoritative for any string
translated in its UI, so on the next sync a human translation wins over our machine seed (the
conflict self-heals in the right direction: human > MT). Before the final Weblate pull,
trigger **Commit + Push** in Weblate so any not-yet-committed UI translations land in the repo
first; fill-empty then skips them.

#### Czech plurals — the pernickety one/few/many/other rule

Czech is the first locale Bristlenose ships that inflects nouns by count beyond a
singular/plural binary, and the wrong form is **immediately wrong-sounding** to a
native speaker. The same trap exists for every Slavic language we might add later
(Polish, Russian, Ukrainian, Slovak — each with its own boundary rules); the
mechanism described here is generic, the seeded values are Czech-specific.

**The four CLDR categories for Czech**, with the noun _rozhovor_ ("interview") as
the worked example. The boundary rules use CLDR's `i` (integer part) and `v` (number
of visible fraction digits):

| Category | Rule (CLDR) | Integer counts | Example string |
|----------|-------------|----------------|----------------|
| `one`   | `i = 1 ∧ v = 0`        | `1`         | `1 rozhovor` |
| `few`   | `i ∈ {2,3,4} ∧ v = 0`  | `2, 3, 4`   | `3 rozhovory` |
| `many`  | `v ≠ 0`                | _(none)_    | `1,5 rozhovoru` _(fractional)_ |
| `other` | everything else        | `0, 5, 6, …` | `7 rozhovorů` |

The single-letter ending changes are the whole point — _rozhovor_ → _rozhovory_
→ _rozhovoru_ → _rozhovorů_ is the **same word in four cases**, not four
different words. Machine translation routinely picks the wrong one (the genitive
plural `-ů` is the most common machine error in `few` contexts), which is why
every machine-seeded `_few` value needs native review.

**Why `many` is in the locale files but never actually rendered.** Bristlenose's
UI displays integer counts only — interview counts, hidden-quote counts, etc. —
so the `many` form (decimals) is never selected at runtime; `pluralCategory` for
Czech only ever returns `one` / `few` / `other`. We seed `_many` anyway because
(a) CLDR considers the four-form set canonical and Weblate / glossary tooling
expect it, (b) it documents the rule for anyone reading the locale file, and
(c) it's a zero-cost guard against a future Decimal-aware call site.

**The mechanism.** `I18n.pluralCategory(_ count: Int) -> String`
(`desktop/Bristlenose/Bristlenose/I18n.swift`) returns the CLDR category for the
active locale. Call sites resolve `<base>_<category>` and fall back to
`<base>_other` if the form is missing — so a half-translated locale renders
"plain plural" rather than the raw key. The two reference implementations are
`ProjectDiagnosticPopover.localisedOverflowText` and `ProjectRow.deltaText`; copy
one of them when you add a new pluralised desktop string. (Pattern reference:
§ Process philosophy, item 3 above.)

**Inventory of Czech four-form values, as of `bc72b7a` (cz branch, 8 Jun 2026) —
machine-seeded, awaiting native review.** Every entry below is a best-effort
Czech form generated mechanically and **may be wrong in a way that's invisible
to anyone who doesn't speak Czech**. A native-speaker pass is the gate, not
the seed.

| Key prefix (under `chrome.` or `pipeline.diagnostic.`) | English source | Seeded cs forms |
|--------|----------------|------------------|
| `interviewCount` | `{{count}} interview(s)` | `1 rozhovor` / `{{count}} rozhovory` / `{{count}} rozhovoru` / `{{count}} rozhovorů` |
| `unanalysedSubtitle` | `+{{count}} unanalysed` | `+1 neanalyzovaný` / `+{{count}} neanalyzované` / `+{{count}} neanalyzovaných` / `+{{count}} neanalyzovaných` |
| `missingSubtitle` | `{{count}} missing` | `1 chybí` / `{{count}} chybí` / `{{count}} chybí` / `{{count}} chybí` _(verb-final; invariant)_ |
| `overflow` (diagnostic) | `… and {{count}} more failures truncated` | `… a {{count}} další chyba skryta` / `… a {{count}} další chyby skryty` / `… a {{count}} další chyby skryto` / `… a {{count}} dalších chyb skryto` |

Note that `missingSubtitle` uses the verb `chybí` ("is/are missing") which doesn't
inflect for count, so all four forms are deliberately identical. `interviewCount`
and `unanalysedSubtitle` are the entries where a native reviewer will most likely
correct an ending; `overflow` involves a full sentence and is the most likely to
need wording revision beyond endings. The current cs overflow seed also translates
"truncated" as `skryta/skryty/skryto` (literally _hidden_), which is a small
semantic drift from the English — flag for the reviewer.

**For the native-speaker reviewer (Pavel and successors).** The forms above were
generated to satisfy CLDR's grammar shape, not to read naturally. Likely areas
to correct: (a) the `-ý` / `-é` / `-ých` adjective endings on
`neanalyzovaný / -é / -ých` (these agree with the noun's gender + case + number,
and the seed assumes a default that may not match how the UI reads — Bristlenose
displays these strings without an explicit noun, so the form choice is doing
double duty); (b) word order and the elided noun in `unanalysedSubtitle` —
you may want to make the noun explicit, e.g. _neanalyzovaných souborů_; (c) the
participle choice in `overflow` (`skryta` / `skryty` / `skryto`), and whether
_hidden_ is the right translation of _truncated_ in this UI. Edit in Weblate or
directly in `bristlenose/locales/cs/desktop.json` — chrome counts are top-level
`chrome.*` keys; overflow lives under `pipeline.diagnostic.*` in the same file.
**You don't need to touch `_many` unless you want to** — it's CLDR-canonical
shape, never rendered in our UI.

#### Polish / Russian / Ukrainian plurals — shipped 3 Jul 2026 (branch `slavic`, machine-seeded)

Polish (Phase 1, `a3995ecb`) then Russian + Ukrainian (Phase 2) extend the same
four-form mechanism, with **two boundary differences from Czech** that are easy to get
wrong:

1. **`many` fires for integers.** Unlike Czech (where `many` is decimals-only and never
   renders in our integer-only UI), pl/ru/uk return `many` for real integer counts —
   Polish `many` covers 0, 5–21, 25–31…; ru/uk `many` covers 0, 5–20, 11–14, 25–30…. So
   `_many` is **not** dead CLDR shape here — it renders constantly, and every count-bearing
   key carries a genuine `_many` form.
2. **`_one` recurrence differs by language.** Polish `one` = `n == 1` only, so its `_one`
   may hardcode "1" (like en). **Russian/Ukrainian `one` = `n%10==1 ∧ n%100!=11`** — it
   recurs at 21, 31, 41, 101… so a ru/uk `_one` string **must interpolate `{{count}}`**,
   never hardcode "1" (else "21 сесія" would render as "1 сесія"). The parity checker
   enforces this per-locale (`_one` must carry `{{count}}` for ru/uk count-driven groups).

Russian and Ukrainian share the **identical** integer rule (one shared `case "ru", "uk":`
branch in `pluralCategory`). Polish is standalone. Both branches + boundary tests
(`pluralCategory_polish_integerRule`, `pluralCategory_russianUkrainian_shareIntegerRule`)
landed in Phase 0 (`0aca876b`). The Python tests `test_four_form_locales_carry_all_forms` /
`test_chrome_count_four_form_locales_carry_all_forms` gate on `_few` presence, so a new
four-form locale auto-acquires coverage without a test edit.

**Register (Apple-sourced):** pl uses the **imperative** for menu commands (Zapisz, Cofnij);
ru/uk use the **infinitive** (Сохранить/Зберегти, Отменить/Скасувати), addressing formally
(вы / ви). Native-reviewer briefs, the cited localization-research terminology table, and the
UX-community terminology findings are kept in the branch's gitignored review notes. Machine-seeded
— native review is the gate, not the seed.

**Slovak (`sk`)** remains the one un-started Slavic candidate — same mechanism, its own
boundary rule, no demand signal yet.

### Future locales (deferred)

Breadcrumbs so the analysis isn't re-derived.

**Status update (3 Jul 2026):** Portuguese (`pt-BR`/`pt-PT`) shipped; the Slavic wave (pl/ru/uk), the
Scandinavian wave (`da`/`sv`/`nb`), and **Turkish (`tr`)** shipped on branch `slavic` (machine-seeded,
pending native review). Turkish is also CLDR `one`/`other` binary (no plural branch; note the no-plural-
after-a-number rule makes `_one`/`_other` count strings identical); register is formal `siz` + imperative;
the Mac-idiom Cancel is **Vazgeç** (not İptal).
**Scandinavian are CLDR `one`/`other` binary** — same shape as es/de/it, so no Swift `pluralCategory`
branch and no four-form seeding; the mechanical cost was low. `nb` (Bokmål) is the correct code (Apple
canonicalizes `no`→`nb`); a `no`→`nb` auto-detection mapping at the three ingress points is an open
follow-up. The still-deferred set below is the accurate remainder.

#### Prioritisation chart — Mac reach × UR-community depth (3 Jul 2026)

Which locale next is a two-axis question, and population is the *wrong* first axis.
Bristlenose is Mac-first and sold into the user-research profession, so the two
axes that actually predict payoff are: **x = Mac-installed reach** (macOS
penetration × market size) and **y = depth of the local user-research community**.
Plotting the un-done candidates on those axes (bubble ≈ speaker market):

```
UR-community depth
  high │            · he(RTL)
       │                        ● nl        ← high/high: build first
       │            · fi
       │        · hu     · id
   mid │   · el · ro · th · vi   ○ zh-Hans     · ar(RTL)
       │        · hi
       │
   low │
       └──────────────────────────────────────────  Mac-installed reach →
          low                mid               high

  ●  recommended next (build)      ·  long tail / low effective fit
  ○  parked (consent/market)       (RTL) gated behind one-time bidi lift
```

Ranked, with the rough per-axis read (0–10; **estimates from macOS-share and
community priors, not hard data** — treat as a sketch, not a measurement):

| Candidate | Mac reach | UR depth | Verdict |
|---|---|---|---|
| **Dutch `nl`** | 7.6 | 9.0 | **Build first.** Only high/high candidate — top EU Mac share + the deepest ResearchOps/UX community in Europe (UXinsight, Amsterdam). No RTL, `one`/`other` plurals. **Branch `nl` opened 3 Jul 2026**, native reviewer lined up. |
| **Finnish `fi`** | 5.6 | 6.6 | **Completes the Nordics** (da/sv/nb shipped). High Mac share, design heritage; small absolute market → demand-gated. **Branch `fi` opened 3 Jul 2026**, native reviewer lined up. `one`/`other`. |
| Hebrew `he` | 5.0 | 7.6 | High UR-per-capita (startup-nation), high Mac share, small market. **RTL** — gated behind the one-time bidi engineering checkpoint. |
| Arabic `ar` | 6.6 | 5.0 | Large Gulf market, high Mac share, fast-growing design investment. **RTL** — same gate as `he`; the two share one bidi lift. |
| Simplified `zh-Hans` | 6.0 | 5.9 | **Parked** deliberately (consent + mainland out-of-scope) — see the Chinese entry below. Population is large but effective fit is not. |
| Hindi `hi`, Indonesian `id` | ~3 | ~4 | Large populations, but UR is conducted overwhelmingly in English → localised UI moves few users. Low effective fit. |
| Hungarian, Romanian, Greek, Thai, Vietnamese | ~3–3.7 | ~3.5–5 | Long tail — volunteer- or demand-driven only (like `ta`). |

**RTL is a checkpoint, not a locale.** Hebrew and Arabic are both gated behind a
single one-time bidi engineering lift (mirrored chrome across SPA + WKWebView +
report surfaces); once paid, it unlocks both. Schedule it as its own roadmap
item rather than slipping one RTL language in beside the LTR ones. Parked as of
3 Jul 2026.

**Portuguese (`pt-PT` + `pt-BR`) — light; a later-summer-weekend seed.** Romance, Latin
script (no script subtag), `one`/`other` plurals — same shape as `es`/`fr`/`de`, so MT-seed
quality is high and mechanical cost is low. Two locales though: lexical divergence
(`ecrã`/`utilizador` PT vs `tela`/`usuário` BR) → two native reviews eventually. `pt-BR`
(Brazil) is the larger market (reach); `pt-PT` is more completeness. Normal App Store
regions, providers reachable.

**Decided: two full locales, not `pt` base + `pt-BR` override.** Every controlled-vocabulary
exemplar ships two independent variants; none ships a neutral `pt` base with deltas. (1) **CLDR**
makes `pt-BR` the *default-content locale* for `pt` — bare `pt` has no data of its own and
resolves to Brazilian content, so a "neutral base" doesn't exist; "`pt` base + override" would
really be "`pt`(=BR) + `pt-PT` override" under a misleading name. (2) **Apple**: *"use `pt` …
for Portuguese as it is used in Brazil and `pt-PT` … as it is used in Portugal"* — no neutral
Portuguese; best practice is shipping both, and because both share the language code `pt`, a
half-populated shared locale can serve *pt-PT strings to a pt-BR user* instead of falling back to
English (QA1828). (3) **Microsoft** maintains two separate style guides + terminology sets
(`por-bra-StyleGuide.pdf` / `por-prt-StyleGuide.pdf`). (4) **Mozilla** runs `pt-BR` and `pt-PT`
as fully independent Pontoon teams — no `pt` team, no base+override. The Acordo Ortográfico (1990)
harmonised some *spelling* but the load-bearing UI divergence (`ficheiro`/`arquivo`,
`utilizador`/`usuário`, `ecrã`/`tela`) is *lexical*, untouched — and it lands on exactly the
high-frequency words in every menu. **Implications:** two locale artifacts + two native reviewers,
but production is still delta-driven (MT-seed `pt-BR`, fork the `pt-PT` deltas — ~1.2× not 2×);
bare-`pt` fallback resolves to `pt-BR` (answers the handoff's region-subtag audit Q6); never let
one variant borrow the other's strings at runtime — gate each to "reviewed" independently.

**Chinese — don't touch before autumn/winter 2026. The commercial unit is a Traditional
*pair*: `zh-Hant` (Taiwan) + `zh-Hant-HK` (Hong Kong).** Both ship in the App Store `.app`
and the CLI package (PyPI / Homebrew → `serve` + SPA), targeting the two ordinary
international storefronts (no mainland ICP / firewall / hosting friction; Claude/ChatGPT/Gemini
all resolve). Simplified (`zh-Hans`) is **parked** — see below. Decision: two Traditional
variants (resolved 29 Jun 2026, deep-research-backed — HK and Taiwan Traditional diverge in
high-frequency UI vocabulary and the l10n industry treats `zh-TW`/`zh-HK` as separate locales:
`軟體/軟件`, `網路/互聯網`, `解析度/解像度`, `論壇/討論區`, `筆記型電腦/手提電腦`).

- **`zh-Hant` (Traditional, Taiwan) — the primary, full-weight locale.** CLDR's default region
  for `zh-Hant` is TW, so bare `zh-Hant` = Taiwan content. This is the commercial bet and the
  heavyweight translation: MT-seed + a **Taiwan-native** reviewer (gating dependency). Recruit
  via **UXTW** (台灣使用者經驗設計協會), **HPX / 悠識 (UserXper)**, or the gated FB UR group
  **使用者經驗研究分析**. An auto-convert from Simplified gets glyphs but not idiom — must be a
  Taiwan native.
- **`zh-Hant-HK` (Traditional, Hong Kong) — a thin override fork off `zh-Hant`.** Machine-seed
  from the Taiwan locale with **OpenCC** (`t2hk` / phrase-aware configs auto-swap most regional
  vocabulary — no script conversion, both are Traditional), then an HK reviewer catches the
  rest via a curated TW→HK term table + one full read. **The London HK diaspora is the *right*
  reviewer here** (they produce HK idiom, which is exactly what `zh-Hant-HK` wants — the
  convenience/correctness conflict that ruled them out for Taiwan reverses for HK); backed by
  **UXHK** / **IxDF Hong Kong**. Cheaper than a Hant↔Hans fork (no one-to-many glyph
  ambiguity): the pair ≈ **1.25–1.3×** a single Traditional locale. **Accepted risk:** HK is
  English-fluent (Dovetail serves HK in English today) and may treat its localisation as a
  curiosity — done *because* it's a near-free delta, not because HK demands it.
- **Fallback policy — deliberately *unlike* the `pt` rule.** Allow `zh-Hant-HK` → `zh-Hant` →
  `zh` to fall through: a missing HK string resolving to the Taiwan one is acceptable because
  TW/HK Traditional are **mutually intelligible** (same script, vocab-only delta), far better
  than dropping to English. This is what makes `zh-Hant-HK` an override layer, not a full
  independent locale — the opposite of `pt-PT`/`pt-BR`, which must never cross-borrow because
  they read foreign to each other.
- **Simplified (`zh-Hans`) is parked, not killed.** No longer in the commercial critical path.
  Fork it later via OpenCC `t2s` off whichever Traditional variant is most mature, when a
  Singapore / Malaysia / diaspora reviewer appears (reachable e.g. via **Design Research SG**,
  English-operating — no mainland engagement). It carries the local-model product-fit story
  (Ollama runs DeepSeek/Qwen/GLM/Kimi for in-language analysis) and serves Singapore/diaspora
  + passive mainland GitHub-finders, but mainland stays **out of scope as a target** (no App
  Store, no ICP, no mainland build/mirror/reviewer).
- **First locales with *script + region* subtags.** `zh-Hant` / `zh-Hant-HK` force the flat
  two-letter registry (hand-duplicated across React `LOCALE_LABELS`, Swift `supportedLocales`,
  Python `_ALL_LOCALES`) to learn both a script (`Hant`) and a region (`HK`) subtag, plus
  matching `.lproj` names (`zh-Hant.lproj`, `zh-Hant-HK.lproj`) and App Store Connect
  localisations. More plumbing than a flat-locale copy-paste. Plurals are trivial
  (`other`-only, like `ja`/`ko`); CJK typography mostly rides existing `ja`/`ko` handling.
- **CLI terminal chrome is English-only in alpha**, so the localised Chinese experience appears
  via `bristlenose serve` + the SPA (shipped inside both the CLI package and the `.app`).

**Catalan (`ca`) — glossary-first, deliberately out of chart order (planned 3 Aug 2026; glossary
built and locale seeded 14 Aug 2026 — 1,247 keys, `9aa11beb` + `b983a7ae`).** **The ratification step
this approach is built around has not run** — the glossary was assembled from Apple's shipped `ca`
strings, the Microsoft style guide and Softcatalà/TERMCAT, and the seed was built against it unreviewed.
Nothing here, glossary or strings, has been seen by a native reviewer yet; the table goes to them first. Catalan does
not appear on the prioritisation chart above and would not score well on it: small absolute market,
modest Mac-installed reach, and a UR community that is real (Barcelona design industry — Elisava,
IED, BAU) but concentrated. It is being built anyway because **the chart measures the wrong scarce
resource.** Every locale in this project is gated on a native reviewer, not on translation capacity —
that is precisely why `nl`, `fi`, `pl`, `ru`, `uk` and `tr` all sit machine-seeded and unreviewed
today. Catalan has native reviewers lined up (Mallorca) and a glossary built to spend them on the ~30
decisions that propagate rather than on 1,247 strings, which is what would invert the usual
bottleneck — *if* the ratification pass happens before they are asked to proofread. Reviewer availability is a legitimate override of the two-axis model;
the chart ranks *candidates we would have to go and find someone for*.

**The real reason, recorded so it is not re-litigated on the wrong axis (14 Aug 2026).** The
paragraph above is the *mechanical* justification and it is true, but it is not why this is being
built. Catalan is a relationship and a cultural gesture, not a return-on-investment play. In the
maintainer's words: he knows the island and the love people have for their language; asking educated
friends to look at his Catalan translation *is a flag that he cares about this place and their
culture*; it costs a few tokens; and it will be a nod in a talk at a Barcelona FOSS or UR group that
he will almost certainly give **in English**. That last detail is the whole point — the gesture is
legible as respect precisely because it was not demanded and is not for the audience's convenience.

**Do not build a business case for this locale, and do not let a weak one argue against it.** The
market analysis has already been run once and produced exactly the wrong recommendation: a
throwaway "five users, maybe $1000?" got turned into a de-risking framework, and a code finding
(see the output-language gap below) got used as ammunition to hold the seed. Both were optimising a
variable that was never in play. The governing line is the maintainer's: **"Some kinds of analysis
are best done outside a spreadsheet."** Sibling instance of [[feedback_product_call_beats_technical_logic]].

**The only real gate on seeding is mechanical** — `en/common|desktop|settings.json` going clean, so
the seed is not stale on arrival. Not a market probe, and not the output-language wiring.

- **One locale, `ca` — the Valencian fork question is closed, and not on preference.**
  `ca-ES-valencia` is a registered BCP-47 *variant* subtag and exists in CLDR, but variant subtags
  are not selectable as OS UI languages — Apple platforms top out at Language+Script+Region, the
  ceiling `zh-Hant-HK` already tested. There is no shippable second artefact to debate, and Apple's
  own metadata list says "Catalan", singular. **This is the opposite situation to `pt-PT`/`pt-BR`**
  (two locales, must never cross-borrow) and to `zh-Hant`/`zh-Hant-HK` (base + thin override): here
  the platform admits exactly one. Should Valencian ever be wanted, it is a *fork*, not an override
  layer, and it needs a platform that can select it first.
- **Balearic reviewers are correct for standard `ca`, not a complication.** Mallorquí differs
  phonologically and in some lexis, but sits *under* the IEC written standard; Valencian is the
  variety with a separate normative body (AVL), which is why it earned a subtag and Balearic did
  not. **Native attestation (14 Aug 2026), which settles it better than the structural argument:**
  Mallorcan speakers with Barcelona scientific degrees describe mallorquí as something they *adjust
  out of* to be accepted in educated Barcelona circles and flip back to at dinner on the island —
  textbook diglossia. The standard **is** the professional register; the dialect is the intimate one.
  Nobody expects professional software UI in the island dialect, so the dialect-leakage risk is
  essentially nil and needs no special guarding.
- **Their code-switching is an asset, for a narrower reason than I first claimed.** An earlier draft
  said Balearic reviewers were "unusually well placed" to catch **castellanismes** — that was an
  overclaim; spotting Spanish calques is a general native-Catalan competence, not a Balearic one.
  The real edge is **register sensitivity**: habitual code-switchers have conscious access to the
  formal/intimate boundary, which is exactly the judgement UI copy needs (Apple-HIG imperative for
  commands, impersonal for body text). Still brief them to flag calques — Spanish interference is
  the dominant Catalan MT failure mode because web-scraped training data carries it heavily — just
  don't justify the reviewer choice on that basis. The reviewer choice is justified by availability
  and nativeness, which is the scarce resource this whole plan turns on.
- **Apple ships Catalan properly — verified on-device 14 Aug 2026, not just from docs.** macOS
  ships a **full** Catalan UI: menu bar, AppKit save panel, System Settings. Confirmed by screenshots
  of a Catalan-set Mac, which is the only evidence that settles it — the web record is actively
  misleading here. `support.apple.com/ca-es/` serves **Spanish**, and at least one secondary source
  claims macOS has no Catalan menu localisation; both are wrong about the OS-strings corpus and cost
  a full flip-flop mid-session before the screenshots resolved it. **Don't re-derive this from search
  results — it's settled, and the answer is yes.** So the mandatory Apple-HIG cross-check (Step 2) is
  a real lookup against Apple's own `ca` strings, a better starting position than most locales here.
  App Store Connect accepts Catalan metadata, so the `.app` can ship a genuine `ca.lproj` **and** a
  Catalan store listing. *Caveat:* Apple provides no Catalan spellcheck on macOS, which touches
  inline quote/heading editing — cosmetic, but real.
- **Plurals: no new work.** CLDR Catalan is `one` / `many` / `other`, but `many` is
  `i % 1000000 = 0` — the compact-decimal/exact-millions category. It is unreachable at Bristlenose's
  count magnitudes (quotes, sessions, tags), and `pluralCategory`'s `default` branch already returns
  the correct one/other with `_other` fallback covering the rest. Same effective shape as `es`/`it`/
  `nl` — **no Swift `pluralCategory` branch, no four-form seeding.**

**Register and form — settled 14 Aug 2026 by two independent authorities.** Apple's shipped `ca`
strings and Microsoft's `cat-esp` style guide were checked against each other; they agree, so these
are not open questions and should not be re-litigated with the reviewer:

- **Commands take the imperative — never the infinitive.** Microsoft §4.1.19 is explicit: *"For
  commands instructions suggestions and similar text always use the imperative form not impersonal
  forms or infinitives. (Use the second-person singular of the imperative tu to address the system.
  **Unlike English and Spanish the infinitive form should never be used in Catalan.**)"* Apple's menus
  bear it out throughout — Desa, Obre, Tanca, Copia, Retalla, Enganxa, Desfés, Refés, Imprimeix,
  Exporta, Mostra, Oculta, Surt. **This is the single highest-value fact in the Catalan glossary:** it
  splits `ca` from `es`/`fr`/`pt` (all infinitive) and aligns it with `it`. An MT seed trained on
  Spanish-adjacent data will get this wrong across every command string.
- **Titles take nouns**, even where English uses a verb — menus, tabs, window titles, and dialog-box
  titles (questions excepted). Affects the `desktop.json` menu namespace specifically. Apple concurs:
  "Usuaris i grups", "Tipus de lletra".
- **Progress and status use the pronominal passive with `es`, in complete sentences** — "S'està desant
  el fitxer", never "Desant el fitxer". **This lands directly on our pipeline status strings**, which
  are exactly that shape.
- **`tu` vs `vós` is genuinely open and belongs to the reviewer.** Microsoft: immersive apps use `tu`,
  formal contexts `vós`; Office 365 and Skype chose `vós`. Note the imperative-addresses-the-*system*
  rule is separate and already settled — this decision governs user-directed prose only.
- **Orthography that tooling can break:** `Cancel·la` carries the interpunct (U+00B7), and Catalan
  elides constantly with a typographic apostrophe (`l'app`, `d'escriptura`, `Temps d'ús`) — same
  family as the German typographic-quote gotcha. Apple also uses *pronoms febles* correctly
  (`Selecciona-ho tot`); Microsoft warns these get dropped under Spanish influence, so their absence
  is a cheap castellanisme tell for the reviewer to grep for.

**Two term collisions worth naming.** (1) **Focus Mode has no safe direct translation** — Apple `ca`
calls system Focus **"Modes de concentració"**, so `Mode concentració` is unavailable to us for the
same reason `it` had to reach for *Full Immersion*. Seeded provisionally as `Mode immersió`, flagged
for review. (2) **Tags → `Etiquetes`** — Apple's own term (Finder tags, the save panel's "Etiquetes:"
field). Catalan should use it rather than keep the English loanword the way `es`/`fr`/`it` did;
Microsoft's *barbarismes* rule points the same way. `Tags` isn't a `glossary.csv` row yet — add it as
a full term-block when it is.

**Second source: Microsoft, and who adjudicates.** Windows Catalan is a **Language Interface Pack**,
not a full language pack — a partial layer requiring en-US/en-GB/es-ES/fr-FR beneath, so it falls back
to the base language where untranslated (structurally like our `zh-Hant-HK`). The useful artefact is
the **Catalan Localization Style Guide** (`cat-esp-StyleGuide.pdf`, 63pp, current — it covers Copilot),
sibling to the `por-bra`/`por-prt` guides already cited for Portuguese. Both Microsoft and Softcatalà
defer to **TERMCAT** as the official terminology body, so when Apple and the Recull disagree, TERMCAT
adjudicates.

**Corrections to the first draft** (recorded so they aren't reintroduced): Delete is **`Elimina`**, not
`Suprimeix`; Hide is **`Oculta`**, not `Amaga`; Settings is **`Configuració`** — Catalan did *not*
follow the Spanish post-Ventura rename to *Ajustes*, so don't inherit it. Apple uses `Elimina` for
**both** Delete and Remove, so the Remove disambiguation is ours to make and is seeded as `Suprimeix`
pending review.

**Process inversion — spend the reviewer on the glossary, not the proofread.** The documented
seven-step process MT-seeds all **1,246 keys** (flattened across the 9 `en` namespaces — measured, not
the line count) and puts native review last (Step 5). That ordering is
what leaves locales stranded: the scarce human is spent proofreading 1,246 strings. Because the
Catalan reviewers are available *first*, run it backwards:

1. **Build the glossary before translating** — ~30 rows in `glossary.csv` (`es` has 23, `it` 30),
   Apple-HIG terms sourced from Apple's actual Catalan `.strings`, plus the QDA/domain set.
2. **Reviewer ratifies the term table** — this is the "core vocab" pass, ~30 minutes rather than an
   afternoon. Live calls: **Quotes** (`Cites` vs a `Verbatim` loan — French's standout finding may
   or may not carry to Catalan), **Codebook** (`Llibre de codis` vs a Catalan analogue of French
   *grille de codage*), **Signals** (our own coinage → likely `Senyals`), **Tags** (loanword or
   `Etiquetes`), and formality register.
3. **Then MT-seed all 9 namespaces against the locked table** — which is what the existing Step-6
   guidance already asks for ("build a glossary before translating"), now with a *human-ratified*
   table instead of an assumed one.
4. **Grep-verify domain terms + toolbar overflow**, then an optional second reviewer pass on full
   strings.

Net effect: the scarce human makes ~30 decisions that propagate to 1,246 strings, instead of
reviewing 1,246 strings that were already fixed by an unratified guess. **If this works, it should
become the default process for reviewer-gated locales** and the seven-step order above should be
rewritten to match.

**Mechanics.** Registration is **10 sites, not the 9 in CLAUDE.md** — `tests/test_pipeline_diagnostic_locale_keys.py`
is a tenth that commit `25d3217d` enrolled for `nl`. ~~`_PLURAL_LOCALES` is only for non-default
plural shapes, so `ca` joins `_ALL_LOCALES` only.~~ **Wrong — corrected 14 Aug 2026 against the code.**
`_PLURAL_LOCALES` means *inflects by count*, not *has an unusual plural shape*: `es`, `fr` and `de` are
all one/other-shaped and all enrolled in it. It drives two live assertions —
`test_plural_locales_have_one_and_other` (`overflow_one`/`_other`) and
`test_chrome_count_plural_locales_have_one_and_other` (every `_CHROME_COUNT_PREFIXES` stem) — so a
locale left out of it **silently loses its plural coverage**: `test_every_locale_dir_is_classified`
checks membership of `_ALL_LOCALES | _FALLBACK_ONLY_LOCALES` only, and never notices the omission.
Every full locale therefore goes in `_ALL_LOCALES` **plus exactly one** of `_PLURAL_LOCALES` /
`_SINGLE_FORM_LOCALES`, which is what CLAUDE.md says and what `ca` is actually enrolled as (both
tuples, correctly). `scripts/check-locales.py` is the local gate **for a locale that lags English** — it cannot see a
surface English never had (see the absent-en-key gotcha below). **Sequencing:** do not seed `ca` while `en/common.json`, `en/desktop.json` or `en/settings.json`
carry uncommitted changes — the seed would be stale on arrival. Steps 1–2 are unaffected and can run
against the current English at any time, which is convenient given they are the human-gated ones.

**Reviewer handoff — what is ratified vs what is machine-seeded (14 Aug 2026).** Step 11 asks for this
catalogue explicitly, so the scarce human spends their pass on the unratified half.

*Ratified, do not re-open:* the ~30 glossary decisions in `bristlenose/locales/glossary.csv`, each
carrying its source in the `note` column — Apple macOS `ca` verified **on-device**, not from the web
record, which is actively wrong about Catalan on macOS. Includes the castellanisme traps (`Desa` not
*Guardar*), the `Cancel·la` interpunct (U+00B7 — watch JSON escaping and font fallback), and the
Delete/Remove split Apple collapses (`Elimina` / `Suprimeix`) which is **ours to make and flagged
pending** in the CSV.

*Machine-seeded, wants the native pass:* the remaining ~1,220 keys. Highest-value targets, in order —
(1) **the 80 plural stems** (54 `common`, 24 `desktop`, 2 `preflight`), full parity with `en` but
never read by a Catalan speaker; `ca` is one/other so it rides `pluralCategory`'s `default` branch,
meaning a wrong stem fails silently rather than loudly. (2) The **register rule** — imperative for
buttons/commands, pronominal passive (`S'ha completat…`) for system status and ongoing processes,
**nouns in title slots**; that last scoping is where the 14 Aug adversarial pass found all six defects
(`b983a7ae`), so it is the proven weak seam. (3) Domain vocabulary that the glossary does not cover —
the QDA terms a working researcher would actually say.

*Verified mechanically and not worth reviewer time:* 33 elision sites (including `la IA`,
`la instal·lació`, `l'histograma`, `l'LLM`), ~40 pronominal-passive number agreements, `tu`
consistency, the article-before-program-name rule that `es`/`it`/`fr` all skip, and absence of
castellanismes. `pipeline.json`'s `stageComplete` is `"S'ha completat {stage}"` — participle before a
postposed subject, invariable, which is the one Romance locale that gets this right; see TODO.md for
the latent agreement bug the other five carry.

### Alternatives considered

| Platform | Why not |
|----------|---------|
| **Crowdin** | Proprietary SaaS. Free for OSS but requires 3+ month old project + OSI licence. Good in-context editing. Would work but not FOSS-aligned |
| **Transifex** | Free tier requires "no funding, revenue, or commercialisation model" — would disqualify us if Bristlenose ever has a paid tier |
| **Tolgee** | Best in-context editing (ALT+click). Newer, smaller community. Worth revisiting if we want that UX |
| **Pontoon** | Mozilla's tool. Primarily Fluent format, heavy to self-host |

## Testing: pseudo-localisation

### What it is

Replace every translated character with an accented equivalent and wrap in brackets: `"Settings"` → `"[Ṡëëttîîñgṡ]"`. Expand strings by 30–40% to simulate German/Finnish length. Any text on screen without brackets = a hardcoded string that was never extracted for translation.

Reference: [Google's canonical explanation](https://opensource.googleblog.com/2011/06/pseudolocalization-to-catch-i18n-errors.html) (2011, still definitive).

### Implementation

Add [`i18next-pseudo`](https://www.npmjs.com/package/i18next-pseudo) as a dev dependency. Register as an i18next postProcessor. Add a pseudo-locale (`qps`) selectable in the dev playground. Run it before every new language launch to catch missed strings.

### String length testing

German is typically 30% longer than English. Finnish even more. Japanese/Korean are typically shorter in character count but may need different font metrics. The pseudo-locale's 40% expansion catches overflow before real translations arrive.

## Process philosophy (from Mozilla, Shopify, and others)

Key lessons from [Mozilla's L10N best practices](https://mozilla-l10n.github.io/documentation/localization/dev_best_practices.html) and [Shopify's linguistics guide](https://shopify.engineering/internationalization-i18n-best-practices-front-end-developers):

1. **Every string gets a localization comment** — explain what variables mean, where the string appears, and any length constraints. Even if it seems obvious. Translators work in a spreadsheet-like UI without seeing the app.

2. **Same English word ≠ same translation key** — "Post" (noun: a blog post) and "Post" (verb: to submit) need different keys because they translate differently in most languages. If a word is ambiguous, split the key.

3. **Never concatenate fragments** — `"You have " + count + " items"` breaks word order in German, Japanese, Arabic. Always use full-sentence interpolation: `t("items.count", { count })` with i18next's plural rules.

   - **Desktop (Swift `I18n.swift`) uses CLDR plural categories — `_one` / `_few` / `_many` / `_other` snake_case suffix keys selected via `I18n.pluralCategory(_ count:)`.** React uses the same i18next suffix convention (CLDR auto-suffix). The Swift selector returns the category for the active locale — cs: one=1, few=2–4, other=0/5+; fr: 0,1=one else other; ja/ko: always other; en/es/de (and any unmapped locale): one=1 else other. Call sites resolve `<base>_<category>` with an `_other` fallback. Reference implementations: `ProjectDiagnosticPopover.localisedOverflowText` (diagnostic overflow text) and `ProjectRow.deltaText` (sidebar chrome counts).
     - **Historical note (closed).** Before 8 Jun 2026 the desktop count strings used a Swift `count == 1` ternary on camelCase `One` / `Other` keys (e.g. `chrome.interviewCountOne` / `chrome.interviewCountOther`, captured 15 May 2026 in `multi-project-folder-watcher`). That binary split rendered Czech counts 2–4 in the `Other` form — `"2 rozhovorů"` where Czech grammar wants the `few` form `"2 rozhovory"`. Finding 1 introduced `pluralCategory` for the diagnostic overflow (8 Jun 2026); Finding 14 (`bc72b7a`, cz branch) migrated the three remaining chrome prefixes (`interviewCount`, `unanalysedSubtitle`, `missingSubtitle`). There are now **no `*One` / `*Other` camelCase keys anywhere** in `bristlenose/locales/`. The earlier chrome guidance ("don't introduce `_one` / `_other` suffixes") is **superseded** — snake_case CLDR forms are the only correct path.
     - **Adding a new desktop count string:** seed `<base>_one` + `<base>_other` for en/es/fr/de (one+other), `<base>_other` only for ja/ko (single-form), and the full `<base>_one` / `_few` / `_many` / `_other` for cs (four-form — see the "Czech plurals" subsection above for what each form means). Route the Swift call site through `i18n.pluralCategory(count)` → `<base>_<category>` with `_other` fallback. The parametrised tests in `tests/test_pipeline_diagnostic_locale_keys.py` (chrome-count and overflow blocks — derive the four-form requirement from presence of `_few`) auto-extend to any new prefix that follows this shape; mirror the existing Swift `@Test` (`chromeInterviewCount_czech_selectsCldrForm` / `localisedOverflowText_czech_selectsFewForm`) for the cs end-to-end assertion.

4. **Respect grammatical gender** — "1 item selected" vs "1 photo selected" may need different adjective forms in French/German/Spanish. Use i18next's `context` feature when the noun changes the sentence.

5. **Don't hardcode punctuation** — French puts a space before `:` and `?`. Japanese uses full-width punctuation (`。` not `.`). Let the translation include its own punctuation.

6. **Descriptive string IDs** — `desktop.menu.file.exportReport` not `str_47`. The ID is documentation for the translator.

## Implementation plan

### Phase 1: UI chrome terminology
Add the 6 core terms to `common.json` for all 5 non-English locales.

Files: `bristlenose/locales/{de,fr,es,ja,ko}/common.json`.

### Phase 2: Sentiment translations
Populate the 4 missing locale files (ja, fr, de, ko) with the 7 sentiment tag translations. (Spanish done in v0.13.7.)

Files: `bristlenose/locales/{locale}/enums.json`.

### Phase 3: UXR codebook translation layer
- YAML stays English (single source of truth for IDs, definitions, `apply_when`, `not_this`)
- Add `bristlenose/locales/{locale}/codebook_uxr.json` mapping English tag name → translated display name + group name + subtitle
- Update codebook display components to use i18n lookup with English fallback
- Adding a new language = one JSON file per codebook

Key files: `bristlenose/server/codebook/__init__.py`, `bristlenose/server/codebook/uxr.yaml`, `frontend/src/islands/QuoteCard.tsx`, `frontend/src/components/TagInput.tsx`.

### Phase 4: Quality gate
- Machine-translate Phases 1–3 as draft
- Cross-check standard UI terms against applelocalization.com (mandatory)
- Create review checklist for native-speaking UX researchers per language
- Track review status per locale (reviewed/unreviewed flag)

### Phase 5: Weblate setup ✓
Complete. Project live at [hosted.weblate.org/projects/bristlenose/](https://hosted.weblate.org/projects/bristlenose/), Libre plan approved 29 Apr 2026, glossary uploaded, translator guide at `TRANSLATING.md`, README links it. See "Live configuration" section above for component breakdown and lessons from setup. **Outstanding:** Weblate attribution mention on bristlenose.app website (Libre plan condition).

### Phase 6: Pseudo-localisation QA
- Add `i18next-pseudo` to dev dependencies
- Add `qps` pseudo-locale to playground
- Run visual scan to catch remaining hardcoded strings
- Extract missed strings to locale files

## Progress

### Spanish (es) — machine-translated, v0.13.7 (16 Mar 2026)

All 102 existing i18n strings machine-translated across 8 files (3 frontend, 5 backend). Cross-checked against the terminology table above — "Citas", "Libro de códigos", "Sesiones", "Señales" all match the recommended terms.

**Review status:** awaiting native-speaker review (Lidia, Sevilla).

**Open questions for reviewer:**
- "Delight" → "Entusiasmo" or "Deleite"? Machine translation chose "Entusiasmo" (enthusiasm); "Deleite" is closer to the UX/design sense of delight. Both are valid — needs a native UXR practitioner's judgement
- "Libro de códigos" — ATLAS.ti's term, recommended by our research. Confirm it feels natural vs alternatives like "Manual de códigos"
- "Investigador/a" for Researcher — gender-inclusive slash form. Confirm this is the convention Lidia prefers (vs "Investigador(a)" or just "Investigador")

### Korean (ko) — machine-translated, v0.14.x (23 Mar 2026)

All 8 namespace files (common, settings, enums, cli, pipeline, server, doctor, desktop) machine-translated. First CJK locale. Cross-checked against the terminology table above — "인용문", "코드북", "세션", "시그널" all match the recommended terms. Apple Korean glossary cross-checked (see table below).

**Speech register:** formal 합쇼체 (-습니다/-ㅂ니다) for sentences, noun forms for buttons/actions. Matches Apple Korean and professional tool conventions.

**No `_short` keys needed.** All Korean tab labels are 2–5 syllable blocks — much shorter than their English equivalents.

**Apple Korean cross-check results:**

| English | Ours | Apple KO | Verdict |
|---------|------|----------|---------|
| Save | 저장 | 저장 | ✓ |
| Cancel | 취소 | 취소 | ✓ |
| Close | 닫기 | 닫기 | ✓ |
| Copy | 복사 | 복사 | ✓ |
| Delete | 삭제 | 삭제 (action) | ✓ action sense correct |
| Undo | 실행 취소 | 실행 취소 | ✓ |
| Redo | 실행 복귀 | 실행 복귀 | ✓ |
| Search/Find | 검색/찾기 | 검색/찾기 | ✓ |
| Find Next | 다음 찾기 | 다음 찾기 (menu label) | ✓ page says "다시 찾기" (informal) |
| Find Previous | 이전 찾기 | 이전 찾기 | ✓ |
| Print | 프린트 | 프린트 | ✓ |
| Fullscreen | 전체 화면 | 전체 화면 | ✓ |
| Settings | 설정 | 설정 (post-Ventura) | ✓ |
| Export | 내보내기 | 내보내기 | ✓ |
| Zoom In | 확대 | 확대 | ✓ |
| Zoom Out | 축소 | 축소 | ✓ |
| Accept | 승인 | 승인 | ✓ |
| Apply | 적용 | 적용 | ✓ |
| Reset | 재설정 | 재설정 | ✓ |

**No changes needed.** All translations match Apple's canonical Korean terms.

**Review status:** awaiting native-speaker review (no reviewer identified yet — need Korean UXR practitioner, ideally in Seoul).

**Open questions for reviewer:**
- "Quotes" → 인용문 or 발언? 인용문 (quotation text) is more academic; 발언 (utterance) is closer to how UXR practitioners talk about participant words. Which feels more natural in a research tool?
- "Delight" → 기쁨 or 감동? 기쁨 is general joy/delight; 감동 is being moved/touched (deeper resonance). In UX sentiment tagging, which better captures "product delight"?
- "Confidence" → 확신 or 자신감? 확신 is conviction about something external; 자신감 is self-confidence. Which is more appropriate for a participant expressing confidence in a product?
- "Frustration" → 좌절감 or 답답함? 좌절감 is defeat/setback (strong); 답답함 is feeling stifled/stuck (more UX-appropriate?). Which maps better to user-research friction?
- Speech register: confirm formal 합쇼체 (-습니다) is appropriate, or whether polite 해요체 (-해요) would feel more natural. Modern Korean tech companies (Toss, Kakao) sometimes use 해요체 for a warmer tone

**CJK-specific CSS tasks (separate from translation):**
- Add `word-break: keep-all` for Korean text — browsers break mid-syllable-block without it
- Audit `max-width` constraints against full-width character widths (56px analysis cells will truncate)
- Test line-height with Korean glyphs (may need adjustment from Latin 1.3–1.5)

### Unified architecture — v0.14.x (23 Mar 2026)

Single source of truth implemented. `frontend/src/locales/` deleted — all imports now point to `bristlenose/locales/` via Vite alias. Desktop `I18n.swift` reads the same JSON files. Desktop `desktop.json` namespace added (en + es) with ~75 native-only strings (menu bar, toolbar, chrome). Bridge locale sync with startup flash prevention (URL query param). Web language picker hidden in embedded mode.

**TODO:** cross-check all Spanish UI terms against applelocalization.com before next release.

### Translation quality gotchas — lessons from the v0.14.1 review

Seven patterns that machine translation gets wrong. Use this list as a pre-flight checklist before shipping a new language.

1. **False cognates in semantic fields.** "길이" (length) was used for time duration — it literally means physical length/distance. Machine translation picked the most common English→Korean mapping without distinguishing temporal from spatial meaning. *Fix:* flag column headers and data labels for domain-specific review. Maintain a glossary of measurement terms per language (time, distance, count, size)

2. **Keyboard hint strings need grammatical context.** English "for Help" is a sentence fragment that reads naturally after `<kbd>?</kbd>`. Korean "도움말" (just "help" as a noun) drops the grammatical connector, producing "? Help" instead of "? for Help". *Fix:* annotate locale keys with rendering context — e.g. `// rendered as: <kbd>?</kbd> {this}`. Translators can't produce correct fragments without knowing the surrounding UI

3. **Identical translations for different concepts are sometimes correct.** French `buttons.cancel` and `buttons.undo` are both "Annuler". This looks like an error but is standard macOS French — Apple's Edit → Undo is "Annuler". *Fix:* before "fixing" apparent duplicates, cross-check against the platform's native localisation (applelocalization.com). Document known-correct duplicates in the review notes

4. **Gender-inclusive language is a style choice, not a bug.** German "Teilnehmer" vs "Teilnehmer:innen" — Apple/Microsoft German localisations consistently use the masculine generic for data labels. *Fix:* establish a gendering policy per language up front and document it in the review template. Don't let it be ad-hoc per string

5. **Column headers need brevity constraints.** Korean "소요 시간" (3 syllable blocks) is wider than "길이" (2). Column headers have strict width budgets. *Fix:* add a max character count annotation to column header keys. Use `_short` variants (already used for `codebookShort`) for languages where translations overflow

6. **Machine translation doesn't know platform conventions.** Multiple issues stem from machine translation ignoring macOS/Apple localisation conventions — the "Annuler" duplicate, "Teilnehmer" gendering, "Réglages" vs "Préférences". *Fix:* enforce the Apple glossary cross-check as a gate — no language ships without a completed review doc in `docs/locales/`

7. **Duplicate keys across namespaces drift independently.** `sessions.colDuration` and `dashboard.colDuration` both had "길이" — fixing one without the other creates inconsistency. *Fix:* grep for all occurrences of a concept before fixing. Consider extracting shared column labels into a `columns` sub-namespace

8. **CLDR plural categories ≠ "missing translations".** Korean and Japanese have a single plural category (`other`) per CLDR. i18next emits `_one` / `_other` variants from English source, so a diff against EN reports the `_one` keys as missing for ko/ja — but those keys are not translatable strings in those languages. As of 30 Apr 2026 this accounts for ~3% of the apparent ko gap on Weblate (19 of 26 "missing" keys are `_one` plurals; the remaining 7 are deliberate identicals — brand name `bristlenose`, acronym `LLM`, `ID`, and pure-placeholder strings like `"{label}"`). *Fix:* if Weblate's component config exposes plural-rule overrides, set ko/ja to skip `_one` form-counting. Otherwise, document the floor and stop chasing it

## Frontend extraction lessons (24 Mar 2026)

Lessons from wiring ~200 hardcoded strings across ~35 React components to i18next.

### What went well

- **Test-setup-first**: adding `import "./i18n"` to `test-setup.ts` meant `t("nav.project")` returned `"Project"` in all tests — zero test rewrites needed for the basic wiring
- **Batched approach**: 11 batches from outside-in (NavBar/Header/Footer shell first, then content, then modals, then accessibility) meant intermediate states were never jarring
- **`Intl.DateTimeFormat` migration**: replacing hardcoded `MONTH_ABBR`/`DAY_ABBR` arrays with `Intl.DateTimeFormat(locale)` was cleaner than adding 60 month/day keys to locale files
- **Sentiment translation in Badge**: a single `t("enums:sentiment.${text}", { defaultValue: text })` in `Badge.tsx` translates all sentiment labels everywhere — quotes, codebook, analysis, dashboard

### What we got wrong

1. **Incomplete string audit upfront** — missed SettingsModal (separate component from SettingsPanel), CodebookSidebar headings, AnalysisSidebar headings, SidebarLayout "Contents" title, "Browse codebooks" button. Each required a QA cycle to discover. A `grep -r '"[A-Z][a-z]' --include='*.tsx' frontend/src/` upfront would have caught them

2. **`useMemo([t])` doesn't work** — the `t` function reference doesn't change on locale switch. Arrays built with `useMemo(() => [...], [t])` go stale. Fix: `[t, i18n.language]` as dependency, or skip `useMemo` for small arrays

3. **Terminology inconsistency in machine-translated keys** — agent-generated translations used "codebook" as an English loanword in es/fr browse/import/restore keys while the heading used the localised term ("Libro de códigos" / "Grille de codage"). The terminology table in this doc existed but wasn't enforced during generation

4. **`en` vs `en-GB` date order** — `Intl.DateTimeFormat("en")` gives US order ("Feb 12"), breaking tests that expected British order ("12 Feb"). Default is now `en-GB`

5. **Capitalization in sentiment enums** — `enums.json` has `"frustration": "Frustration"` (capitalised). Tests that expected lowercase API values (`"frustration"`) broke when Badge started translating

### Patterns established

| Pattern | When to use | Example |
|---------|-------------|---------|
| `useTranslation()` hook | Inside React component functions | NavBar, Header, Footer |
| `import i18n` + `i18n.t()` | Stores, announce calls, non-component code | QuotesContext, AppLayout |
| Inline array (no memo) | 2–5 items with translated labels | ViewSwitcher options |
| `useMemo([t, i18n.language])` | 8+ items passed as props | HelpModal nav items |
| `enums` namespace lookup | Sentiment/role labels from API data | Badge, CodebookPanel |
| `colour_set === "sentiment"` | Identifying built-in sentiment group | CodebookPanel group translation |
| `name === "Uncategorised"` | Identifying default codebook group | CodebookPanel group translation |
| `Intl.DateTimeFormat(locale)` | Date/time formatting | format.ts |
| `toLocaleString(i18n.language)` | Number formatting | Dashboard stat cards |

### Process for future extraction passes

1. Grep all `.tsx` for hardcoded English strings — build complete inventory
2. Cross-reference inventory against locale file keys — identify gaps
3. Define terminology glossary upfront (this doc's table) — enforce during translation
4. Add `import "./i18n"` to test-setup if not already present
5. Wire components in outside-in order (shell → content → modals → accessibility)
6. Add keys to ALL 5 locale files in the same edit — never leave gaps
7. Run `npm test && npm run build` after each batch
8. Review agent-generated translations against terminology table before committing
9. QA with language switching in full browser — preview tools don't work for Bristlenose

### Not in scope
- Translating LLM prompts (not needed — cross-lingual works)
- Translating codebook `definition`/`apply_when`/`not_this` fields (LLM-facing, English performs best)
- `analysis_language` setting for LLM-generated summaries/themes (separate feature)
- New locales beyond the 6 already supported

## Mixed-language interview scenario

A German researcher using Don Norman's framework against mixed German/English interviews:
- Read Don Norman in English → thinks about "affordances" in English
- Interviews in German/English mix → participants code-switch naturally
- Wants tags like "affordance", "signifier" → already English, matching the framework
- Wants quotes in whatever language the participant used → preserved verbatim
- Wants UI chrome in German → "Zitate", "Codebuch", "Interviews"
- Wants theme summaries → configurable via `analysis_language` (future)

The LLM handles this natively. The display layer translates. No prompt or transcript translation needed.

## Divergence markers — recording that a difference is on purpose

**The problem they solve.** Three of the five i18n failure modes are invisible to
a key-set diff (`docs/i18n-defects.md`), and the nastiest is **value drift**: an
`en` value gets reworded and the translations keep the old words. A detector can
find it by comparing when `en` last changed against when each locale last
changed — but that same detector cannot tell drift from a divergence someone
*meant*, because the two are byte-for-byte identical in the data.

Both live cases arrived within a day of each other:

- `desktop.welcome.aiSetup` — `en` keeps the noun **Setup**, the 20 locales take
  a verb (`ca Configura`, `de Konfigurieren`, `fi Ota käyttöön`). Deliberate:
  part of speech follows each language's UI convention, not English's.
- `desktop.menu.video.pictureInPicture` — `it`, `pt-BR` and `pt-PT` keep the
  English because Apple does; the other 17 use their own name.

Neither is a defect. Both would be re-reported on every sweep forever, and —
worse — would train whoever runs the sweep to skim past exactly the shape that
hid the Codebook Library rewording for five weeks.

**The convention.** A `_divergent_<leaf>` pseudo-key, sibling to the key it
describes, in **`en` only** — it describes the relationship between English and
every locale, so a per-locale copy would be 21 places to keep true instead of one.

```json
"welcome": {
  "aiSetup": "Setup",
  "_divergent_aiSetup": "en:7013af \u2014 English keeps the noun; the 20 locales take a verb (ca Configura, de Konfigurieren\u2026). Part of speech follows each language's UI convention, not English's. Deliberate \u2014 see 89b11f5a and the call-site comment in WelcomeHomeView.swift."
}
```

`en:<6 hex>` is the first six characters of `sha256` of the English value the
note was written against. `scripts/check-locales.py` recomputes it and **errors**
when it no longer matches.

**The pin is the whole point.** A bare "this divergence is intended" flag rots
the way any status rots — item 2 of the defect register is a "deliberate"
rationale that was already false when it was written, and nothing re-checked it.
Pinning the value means the note can only stay silent while the thing it
describes is unchanged. Reword `Setup` -> `Set Up` and CI stops:

```
X en/desktop.json: `welcome.aiSetup` divergence marker is STALE - it was
  written against a different English value (pinned en:7013af, current
  en:75f9c0 = 'Set Up'). Re-read the reason: if the divergence still holds,
  re-pin it; if the reword undid it, delete the marker and re-translate.
```

Three failures, all errors rather than warnings, because a marker is an
*assertion* and a false assertion is worse than none: **stale pin**, **marker
for a key that doesn't exist** (typo, or the key was deleted and the note left
behind), and **malformed** (no pin - the error prints the pin you need).

**Writing one.** Get the pin from `value_pin()` in `scripts/check-locales.py`, or
just write `en:000000` and let the error tell you the right value - that is the
intended workflow, not a hack. Then say *why* in prose. The prose is the part
that matters; a future reader needs the reasoning, not permission to ignore a
warning. Name the commit or the call-site comment that carries the fuller
argument.

**What this is not.** It is not a suppression list for translations nobody has
got to yet - that is a missing translation, and `--strict` is the gate for it.
It is not per-locale: if one locale diverges for its own reason, say so in the
prose. And it does not make a drift *detector* exist - the detector is still
recommendation 1 in `docs/i18n-defects.md`. This is the half that makes the
detector's output trustworthy once it does.

## i18n Implementation Gotchas (from CLAUDE.md)

Reference material moved from root `CLAUDE.md` to reduce CLAUDE.md bloat. Core i18n rules still live there; these are the detail-level gotchas.

- **Toolbar `_short` keys** — `common.nav.codebookShort` exists for languages where the full label overflows the segmented control (es: "Códigos" instead of "Libro de códigos"). `Tab.localizedLabel()` checks `_short` first
- **Apple glossary cross-check is mandatory** before shipping a new language — use [applelocalization.com](https://applelocalization.com/) or the macOS keyboard shortcuts page in the target locale. See Spanish cross-check results elsewhere in this doc for the process
- **`useMemo` deps for translated arrays** — `t` function identity doesn't change on locale switch. Use `[t, i18n.language]` as dependency, or skip `useMemo` entirely for small arrays (2–5 items). See `ViewSwitcher.tsx` (inline) vs `HelpModal.tsx` (useMemo with language dep)
- **`i18n/index.ts` initialises test-setup** — `frontend/src/test-setup.ts` imports `"./i18n"` so all tests get English translations by default. `t("nav.project")` returns `"Project"` in tests — no test rewrites needed for i18n wiring
- **Sentiment tag translation in Badge** — `Badge.tsx` looks up `enums:sentiment.${text}` when `sentiment` prop is truthy. This translates API-returned lowercase sentiment names ("frustration") to locale-correct labels ("Frustration" / "Verwirrung"). Tests must expect capitalised forms
- **Built-in codebook groups translate client-side** — sentiment group (`colour_set === "sentiment"`) and uncategorised group (`name === "Uncategorised"`) have their names/subtitles translated in `CodebookPanel.tsx` using locale keys. Other codebook names are user data and stay untranslated
- **`format.ts` uses `Intl.DateTimeFormat`** — `formatFinderDate` and `formatCompactDate` accept an optional `locale` param. Callers pass `i18n.language`. Internally, any `en*` locale (including bare `"en"` from i18next and `"en-US"` from jsdom in tests) is mapped to `"en-GB"` to preserve day-month order ("12 Feb" not "Feb 12"). Non-English locales pass through unchanged. `formatFinderDate` uses `Intl.RelativeTimeFormat` for "today"/"yesterday"
- **`<html lang>` tracking** — `i18n.on("languageChanged")` in `i18n/index.ts` sets `document.documentElement.lang`. Required for screen reader pronunciation
- **Korean has no plural forms** — only `_other` keys needed in locale files (no `_one`). i18next CLDR rules handle this automatically
- **Data-level vs chrome-level translation** — UI chrome (buttons, headings, labels) translates via `t()`. API data (codebook names, quote text, section labels) stays in the original language. Exceptions: sentiment group name/subtitle and uncategorised group are server constants that get client-side translation
- **German typographic quotes break JSON** — `„"` (U+201E / U+201C) look like JSON string delimiters to parsers. Escape as `\u201e` / `\u201c` in locale JSON files. Caught in `de/desktop.json` during platform text fork work
- **Tests that mock `../utils/platform` must include `isDesktop`** — `HelpModal.test.tsx` mocked only `isMac`, which broke when `ContributingSection` started importing `dt()` (which imports `isDesktop`). Always mock `{ isMac, isDesktop, _resetPlatformCache }` together
- **…and three more holes below that one, all sharing a cause: every gate we own asks "is the key there?", never "is the value right?" or "does anyone read it?"** Found by sweep on 21 Aug 2026; full account and detection recipes in `docs/i18n-defects.md`. **(3) Value drift** — `en` gets reworded and the translations keep the old words. The key is present on both sides, so a key-set diff sees nothing. Live instance: the Codebook Library rewrite (`7530106e` 17 Jul, `e8745070` 26 Jul) changed 13 `codebook.*` values — Browse→Library, Import→**Install**, Remove/Hide→**Uninstall**, "AutoCode quotes"→**Apply** — and 19 locales kept the July words for five weeks. `codebook.autoCodeQuotes` labelled one button "Apply" in English and "✦ AutoCode citas" in Spanish. Detect by comparing, per key, the last commit that changed `en`'s value against the last that changed each locale's. **(4) Untranslated value** — a locale's value is byte-identical English. Same blindness, opposite direction. 28 findings, the largest being the whole `preflight.*` surface sitting in English in **de/es/fr/ja/ko**, the five *oldest* locales, which never received the wave the later ones did (and which `bristlenose --lang=de` reaches today). Detect by byte-comparing values against `en` and discarding the legitimately-invariant ones — shell commands, URLs, pure-`{placeholder}` strings. **(5) Orphan key** — present in every locale, read by no call site. `3f49d170` retired the SPA help modal and left three `dt()` overrides behind in 21 files. Detect by grepping the **fully-qualified** key; a bare-leaf match finds doc comments and test fixtures and will report dead keys as alive, which is exactly what happened on the first pass here.
- **An absent `en` key can never be reported missing — `check-locales.py` is blind to a surface that was never enrolled in English.** The script flattens every `en/<ns>.json` key and diffs each locale *against* it, so English is the iteration domain: a view whose strings are all hardcoded literals has nothing to be missing **from**, in any locale, and the run is green. This is a **different hole** from the allow-list one (`tests/test_pipeline_diagnostic_locale_keys.py` checking hardcoded lists rather than real parity), and unlike that one **no `--strict` closes it** — `--strict` only promotes warnings drawn from the same en-derived set. Shipped instance: the macOS Settings ▸ Accounts pane, 18 Aug 2026, every string a Swift literal and the pane title hardcoded while its five siblings read `desktop.settingsTabs.*`; `check-locales.py` was green throughout, and `design-cloud-import.md` §10 had predicted this exact recurrence in writing two days earlier. Fixed in `d0478b15`. **The only gate is the diff** — a new user-facing view gets read for `i18n.t(` / `t("` call sites when it lands, because nothing mechanical will ask again. Applies to `.swift` as much as `.tsx`; the 18 Aug instance was Swift, which no `frontend/src` grep would have reached
