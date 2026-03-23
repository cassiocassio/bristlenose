# Internationalisation — Codebook & Sentiment Translation

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

## Internal representation: English always

- `Sentiment.FRUSTRATION` enum — DB stores `"frustration"`
- Tags stored as English strings in DB (canonical)
- LLM prompts use English tag names, return English values
- Translation is display-only — tags are interoperable across languages
- A German user's tags are readable by an English user

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

~180 keys across 8 namespaces × 6 languages = ~1,080 translation strings total.

## Architecture: single source of truth (implemented, Mar 2026)

### Canonical locale directory

**`bristlenose/locales/{locale}/{namespace}.json`** — the only place translations live. Three codebases consume them:

| Consumer | How it reads locale files |
|----------|-------------------------|
| **Python** (`bristlenose/i18n.py`) | Direct filesystem read at runtime. `t("namespace.key")` |
| **React** (`frontend/src/i18n/`) | Vite `resolve.alias` (`@locales`) at build time. English bundled inline; other locales lazy-loaded via dynamic `import()` |
| **macOS desktop** (`desktop/.../I18n.swift`) | `I18n` class loads JSON from disk. Discovers locale files from dev repo, bundled .app, or Homebrew paths |

### Namespace inventory

| Namespace | Used by | Keys |
|-----------|---------|------|
| `common.json` | React + Desktop | ~34 (nav tabs, buttons, labels, footer) |
| `settings.json` | React + Desktop | ~15 (settings panel labels) |
| `enums.json` | React + Python + Desktop | ~11 (sentiments, speaker roles) |
| `cli.json` | Python only | ~15 (CLI output) |
| `pipeline.json` | Python only | ~5 (stage progress) |
| `server.json` | Python only | ~5 (API errors) |
| `doctor.json` | Python only | ~5 (health checks) |
| `desktop.json` | Desktop only | ~75 (menu bar, toolbar, native chrome) |

### Desktop locale flow

1. User picks language in native Settings (Cmd+,) → `@AppStorage("language")`
2. `I18n.setLocale()` reloads JSON from disk → `@Published` triggers SwiftUI re-render
3. `BridgeHandler.syncLocale()` pushes locale to web via `callAsyncJavaScript`
4. Startup flash prevention: locale injected as `?locale=es` URL query param on WKWebView load → `LocaleStore.ts` detects synchronously before first render
5. In embedded mode, the web language picker is hidden — native Settings is the single control point

### `CommandMenu` titles stay in English

SwiftUI's `CommandMenu("Project")` takes `LocalizedStringKey` which resolves from `.lproj` bundles, not runtime JSON. Rather than maintaining a second localisation format for 4 strings, menu titles ("Project", "Codes", "Quotes", "Video") stay in English. Menu *items* inside are translated via `I18n.t()`. This matches ATLAS.ti and MAXQDA precedent — both keep English menu titles even in localised UIs.

### Toolbar overflow: `_short` keys

"Libro de códigos" (es) and "Grille de codage" (fr) are ~2× wider than "Codebook". The toolbar segmented control uses `common.nav.{tab}Short` keys where available, falling back to the full `common.nav.{tab}` key. Only add `_short` variants where the full label exceeds ~10 characters.

| Tab | Full (View menu) | Short (toolbar) |
|-----|-----------------|-----------------|
| codebook (es) | Libro de códigos | Códigos |
| codebook (fr) | Grille de codage | Codage |

## Terminology standards

### The "Cancel button problem"

Every language has a standard word for common UI actions. Getting it wrong makes the tool feel alien. Two authoritative databases exist:

- **[applelocalization.com](https://applelocalization.com/)** — searchable Apple glossary from official bilingual glossaries for macOS/iOS. Since Bristlenose is a macOS app, this is the primary reference. Also available as [DMG downloads](https://developer.apple.com/localization/resources/) from Apple Developer.
- **[termic.me](https://termic.me/)** — indexes Microsoft Terminology + 10,000 VS Code strings. Cross-reference when Apple's glossary doesn't cover a term. [Open source](https://github.com/Spidersouris/termic).

**Rule: for standard UI verbs (Save, Cancel, Delete, Close, Undo, Export, Search), always use Apple's term for the target platform.** Cross-check against Microsoft for general IT terms. If both agree, it's definitive. If they differ (rare for basics), prefer Apple since we're a macOS-native app.

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

#### Step 6: Track review status

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

Bristlenose qualifies (AGPL-3.0). No application process — create the project and go.

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

1. Create project at `hosted.weblate.org`
2. Add component pointing to `bristlenose/locales/*/common.json` (repeat for each namespace)
3. Upload Apple glossary terms as a Weblate glossary (prevents "Cancel" → wrong synonym)
4. Add "Help translate Bristlenose" link to About panel + README
5. Configure auto-merge for translations that match the glossary; require review for others

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

### Phase 5: Weblate setup
- Create project on hosted.weblate.org
- Upload Apple glossary as Weblate glossary
- Add "Help translate" link to About panel
- Announce in README

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

### Unified architecture — v0.14.x (23 Mar 2026)

Single source of truth implemented. `frontend/src/locales/` deleted — all imports now point to `bristlenose/locales/` via Vite alias. Desktop `I18n.swift` reads the same JSON files. Desktop `desktop.json` namespace added (en + es) with ~75 native-only strings (menu bar, toolbar, chrome). Bridge locale sync with startup flash prevention (URL query param). Web language picker hidden in embedded mode.

**TODO:** cross-check all Spanish UI terms against applelocalization.com before next release.

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
